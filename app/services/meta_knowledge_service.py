"""
元数据知识构建服务

负责组织元数据知识库构建的核心业务流程，位于脚本入口和仓储层之间
一方面接收配置文件，另一方面协调元数据库和数仓查询仓储

当前这条主线已经覆盖表字段入库 字段向量索引 字段取值全文索引
以及指标入库和指标向量索引构建逻辑
"""

import uuid
from dataclasses import asdict
from pathlib import Path

import yaml
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from omegaconf import OmegaConf

from app.agent.llm import get_llm
from app.conf.meta_config import MetaConfig
from app.core.log import logger
from app.entities.column_info import ColumnInfo
from app.entities.column_metric import ColumnMetric
from app.entities.metric_info import MetricInfo
from app.entities.table_info import TableInfo
from app.entities.value_info import ValueInfo
from app.prompt.prompt_loader import load_prompt
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository


class MetaKnowledgeService:
    """负责串联元数据知识库构建流程的应用服务"""

    def __init__(
        self,
        meta_mysql_repository: MetaMySQLRepository,
        dw_mysql_repository: DWMySQLRepository,
        column_qdrant_repository: ColumnQdrantRepository,
        embedding_client: HuggingFaceEndpointEmbeddings,
        value_es_repository: ValueESRepository,
        metric_qdrant_repository: MetricQdrantRepository,
    ):
        # meta repository 负责结构化元数据的落库
        self.meta_mysql_repository: MetaMySQLRepository = meta_mysql_repository
        # dw repository 负责到教学数仓中读取真实表结构和示例值
        self.dw_mysql_repository: DWMySQLRepository = dw_mysql_repository
        # 字段向量集合的创建和写入统一交给 Qdrant Repository
        self.column_qdrant_repository: ColumnQdrantRepository = column_qdrant_repository
        # 向量化动作放在 Service 层
        self.embedding_client: HuggingFaceEndpointEmbeddings = embedding_client
        # 字段值全文索引的写入统一交给 ES Repository
        self.value_es_repository: ValueESRepository = value_es_repository
        # 指标向量集合和字段向量集合分开管理，便于后续按对象类型独立召回
        self.metric_qdrant_repository: MetricQdrantRepository = metric_qdrant_repository

    async def _save_tables_to_meta_db(
        self, meta_config: MetaConfig
    ) -> list[ColumnInfo]:
        """把配置里的表字段信息补齐后写入 Meta MySQL"""
        table_infos: list[TableInfo] = []
        column_infos: list[ColumnInfo] = []

        for table in meta_config.tables:
            # 先把配置里的表定义整理成业务实体，后面统一交给 Meta Repository 落库
            table_info = TableInfo(
                id=table.name,
                name=table.name,
                role=table.role,
                description=table.description,
            )
            table_infos.append(table_info)

            # 字段类型属于数仓里的真实信息，所以这里仍然要回到 DW 查询
            column_types = await self.dw_mysql_repository.get_column_types(table.name)

            for column in table.columns:
                # 这里只拿少量示例值，目的是让字段元数据更容易被人和模型理解
                column_values = await self.dw_mysql_repository.get_column_values(
                    table.name, column.name
                )
                # 字段 id 使用 table.column 形式，后续在向量索引和全文索引里都会复用
                column_info = ColumnInfo(
                    id=f"{table.name}.{column.name}",
                    name=column.name,
                    type=column_types[column.name],
                    role=column.role,
                    examples=column_values,
                    description=column.description,
                    alias=column.alias,
                    table_id=table.name,
                )
                column_infos.append(column_info)

        async with self.meta_mysql_repository.session.begin():
            self.meta_mysql_repository.save_table_infos(table_infos)
            self.meta_mysql_repository.save_column_infos(column_infos)

        return column_infos

    async def _save_column_info_to_qdrant(self, column_infos: list[ColumnInfo]):
        """把字段元数据继续推进成可语义检索的 Qdrant 向量点"""
        await self.column_qdrant_repository.ensure_collection()

        points: list[dict] = []
        for column_info in column_infos:
            # 一个字段不会只生成一个向量点，而是把名字 描述 别名都拆开建立语义入口；
            # 描述/别名可能为空，空文本无法向量化（TEI 会报 inputs cannot be empty），跳过
            texts = [column_info.name, column_info.description, *column_info.alias]
            for text in texts:
                if not text:
                    continue
                points.append(
                    {
                        "id": uuid.uuid4(),
                        "embedding_text": text,
                        "payload": asdict(column_info),
                    }
                )

        # 先把待向量化文本抽出来，再分批调用 Embedding 服务
        # 这样更容易控制单次请求大小
        embeddings: list[list[float]] = []
        embedding_texts = [point["embedding_text"] for point in points]
        embedding_batch_size = 20
        for i in range(0, len(embedding_texts), embedding_batch_size):
            batch_embedding_texts = embedding_texts[i : i + embedding_batch_size]
            batch_embeddings = await self.embedding_client.aembed_documents(
                batch_embedding_texts
            )
            embeddings.extend(batch_embeddings)

        ids = [point["id"] for point in points]
        payloads = [point["payload"] for point in points]

        await self.column_qdrant_repository.upsert(ids, embeddings, payloads)

    async def _save_value_info_to_es(
        self, meta_config: MetaConfig, column_infos: list[ColumnInfo]
    ):
        """把允许同步的字段真实取值写入 Elasticsearch 全文索引"""
        await self.value_es_repository.ensure_index()

        # 不是所有字段都要同步真实值，是否同步由配置里的 sync 显式控制
        column2sync: dict[str, bool] = {}
        for table in meta_config.tables:
            for column in table.columns:
                column2sync[f"{table.name}.{column.name}"] = column.sync

        value_infos: list[ValueInfo] = []
        for column_info in column_infos:
            sync = column2sync[column_info.id]
            if sync:
                # 这里拿的是字段真实值全集，不再是第 8 章里的少量 examples
                current_column_values = (
                    await self.dw_mysql_repository.get_column_values(
                        column_info.table_id, column_info.name, 100000
                    )
                )
                current_values_infos = [
                    ValueInfo(
                        id=f"{column_info.id}.{current_column_value}",
                        value=current_column_value,
                        column_id=column_info.id,
                    )
                    for current_column_value in current_column_values
                ]
                value_infos.extend(current_values_infos)

        await self.value_es_repository.index(value_infos)

    async def _save_metrics_to_meta_db(
        self, meta_config: MetaConfig
    ) -> list[MetricInfo]:
        """把配置里的指标信息和字段依赖关系写入 Meta MySQL"""
        metric_infos: list[MetricInfo] = []
        column_metrics: list[ColumnMetric] = []

        for metric in meta_config.metrics:
            # MetricInfo 表达指标本身，当前直接用指标名作为稳定业务 id
            metric_info = MetricInfo(
                id=metric.name,
                name=metric.name,
                description=metric.description,
                relevant_columns=metric.relevant_columns,
                alias=metric.alias,
            )
            metric_infos.append(metric_info)
            for column in metric.relevant_columns:
                # ColumnMetric 单独表达“某个指标依赖某个字段”这层关系
                column_metric = ColumnMetric(column_id=column, metric_id=metric.name)
                column_metrics.append(column_metric)

        # 指标本身和字段关系要放在同一笔事务里，避免只写入其中一部分
        async with self.meta_mysql_repository.session.begin():
            self.meta_mysql_repository.save_metric_infos(metric_infos)
            self.meta_mysql_repository.save_column_metrics(column_metrics)

        return metric_infos

    async def _save_metrics_to_qdrant(self, metric_infos: list[MetricInfo]):
        """把指标元数据继续推进成可语义检索的 Qdrant 向量点"""
        await self.metric_qdrant_repository.ensure_collection()

        points: list[dict] = []
        for metric_info in metric_infos:
            # 和字段一样，一个指标也会拆成名字 描述 别名这几类语义入口；
            # 描述/别名可能为空，空文本无法向量化，跳过
            texts = [metric_info.name, metric_info.description, *metric_info.alias]
            for text in texts:
                if not text:
                    continue
                points.append(
                    {
                        "id": uuid.uuid4(),
                        "embedding_text": text,
                        "payload": asdict(metric_info),
                    }
                )

        # 先把待向量化文本抽出来，再分批调用 Embedding 服务
        # 返回的 embeddings 要继续和前面的 id payload 按顺序对齐
        embeddings: list[list[float]] = []
        embedding_texts = [point["embedding_text"] for point in points]
        embedding_batch_size = 20
        for i in range(0, len(embedding_texts), embedding_batch_size):
            batch_embedding_texts = embedding_texts[i : i + embedding_batch_size]
            batch_embeddings = await self.embedding_client.aembed_documents(
                batch_embedding_texts
            )
            embeddings.extend(batch_embeddings)

        ids = [point["id"] for point in points]
        payloads = [point["payload"] for point in points]

        await self.metric_qdrant_repository.upsert(ids, embeddings, payloads)

    async def build(self, config_path: Path):
        """读取配置并依次构建 Meta MySQL Qdrant 和 ES 中的元数据索引"""
        context = OmegaConf.load(config_path)
        schema = OmegaConf.structured(MetaConfig)
        meta_config: MetaConfig = OmegaConf.to_object(OmegaConf.merge(schema, context))

        # 先清空上一次构建的产物，保证脚本可以重复执行
        # MySQL 是 INSERT 入库、Qdrant 使用随机 id，不清空会导致主键冲突或向量累积
        # 但 `s{id}_` 前缀的镜像表由数据源同步链路维护，这里要保留它们
        async with self.meta_mysql_repository.session.begin():
            await self.meta_mysql_repository.clear()
        mirror_ids = await self.meta_mysql_repository.list_mirror_table_ids()
        await self.column_qdrant_repository.delete_except_table_ids(mirror_ids)
        await self.metric_qdrant_repository.clear()

        # 根据配置文件判断后续要进入哪条构建链路
        if meta_config.tables:
            # 将表信息和字段信息保存到 Meta MySQL
            column_infos = await self._save_tables_to_meta_db(meta_config)
            logger.info("保存表信息和字段信息到 Meta MySQL")
            # 对字段信息建立向量索引
            await self._save_column_info_to_qdrant(column_infos)
            logger.info("为字段信息建立向量索引")
            # 对指定的维度字段取值建立全文索引
            await self._save_value_info_to_es(meta_config, column_infos)
            logger.info("为字段取值建立全文索引")

        # 根据配置文件同步指定的指标信息
        if meta_config.metrics:
            # 将指标信息和字段依赖关系保存到 Meta MySQL
            metric_infos = await self._save_metrics_to_meta_db(meta_config)
            logger.info("保存指标信息到数据库成功")

            # 对指标信息建立向量索引
            await self._save_metrics_to_qdrant(metric_infos)
            logger.info("为指标信息建立向量索引成功")

    async def _describe_mirror_columns(
        self, mirror_name: str, column_specs: list[dict]
    ) -> dict[str, dict]:
        """用 LLM 为镜像表字段生成中文描述与别名，失败时降级为空描述

        镜像表字段名来自源表 DDL（通常是英文/拼音），没有手写的中文语义，中文
        问题在向量召回阶段会因语义不匹配而漏掉。这里按「表名 + 字段结构 + 示例
        值」批量推断中文描述与别名，让字段在 Qdrant 里有中文语义入口。
        LLM 失败不阻断爬取主流程，仅回退为无描述（仍能按英文列名召回）。
        """
        try:
            prompt = PromptTemplate(
                template=load_prompt("describe_mirror_columns"),
                input_variables=["table_name", "columns"],
            )
            chain = prompt | get_llm() | JsonOutputParser()
            result = await chain.ainvoke(
                {
                    "table_name": mirror_name,
                    "columns": yaml.dump(
                        column_specs, allow_unicode=True, sort_keys=False
                    ),
                }
            )
            return {col["name"]: col for col in result.get("columns", [])}
        except Exception:  # noqa: BLE001 —— 描述生成是增强项，失败不阻断爬取
            logger.exception("为镜像表 {} 生成字段中文描述失败，降级为空描述", mirror_name)
            return {}

    async def sync_mirror_tables(self, prefix: str, table_names: list[str]):
        """对镜像表自动爬取元数据：写 table_info/column_info 并建立字段向量索引

        表 id 直接用带前缀的镜像表名，保证与其它源/默认表不冲突；字段角色按
        「主键 / 其它」做启发式标记，中文描述与别名由 LLM 自动生成。
        """
        if not table_names:
            return
        mirror_names = [f"{prefix}_{name}" for name in table_names]

        table_infos: list[TableInfo] = []
        column_infos: list[ColumnInfo] = []
        for mirror_name in mirror_names:
            column_types = await self.dw_mysql_repository.get_column_types(mirror_name)
            primary_keys = set(
                await self.dw_mysql_repository.get_primary_key(mirror_name)
            )
            # 先收集字段名/类型/示例值，交给 LLM 推断中文描述与别名，避免镜像表
            # 只剩英文列名一个语义入口，导致中文问题在向量召回时匹配不到
            column_specs = []
            for column_name, column_type in column_types.items():
                examples = await self.dw_mysql_repository.get_column_values(
                    mirror_name, column_name
                )
                column_specs.append(
                    {"name": column_name, "type": column_type, "examples": examples}
                )
            descriptions = await self._describe_mirror_columns(mirror_name, column_specs)

            table_infos.append(
                TableInfo(id=mirror_name, name=mirror_name, role="fact", description="")
            )
            for spec in column_specs:
                column_name = spec["name"]
                role = "primary_key" if column_name in primary_keys else "dimension"
                desc = descriptions.get(column_name, {})
                column_infos.append(
                    ColumnInfo(
                        id=f"{mirror_name}.{column_name}",
                        name=column_name,
                        type=spec["type"],
                        role=role,
                        examples=spec["examples"],
                        description=desc.get("description", ""),
                        alias=desc.get("alias", []),
                        table_id=mirror_name,
                    )
                )

        # 先删旧元数据再写入，保证重复同步幂等；向量同理
        async with self.meta_mysql_repository.session.begin():
            await self.meta_mysql_repository.delete_by_table_ids(mirror_names)
            self.meta_mysql_repository.save_table_infos(table_infos)
            self.meta_mysql_repository.save_column_infos(column_infos)

        await self.column_qdrant_repository.ensure_collection()
        await self.column_qdrant_repository.delete_by_table_ids(mirror_names)
        await self._save_column_info_to_qdrant(column_infos)
        logger.info("已为 {} 张镜像表爬取元数据并建立向量索引", len(mirror_names))

    async def delete_mirror_tables(self, prefix: str, table_names: list[str]):
        """删除镜像表的元数据与向量（源表被 drop 时清理）"""
        if not table_names:
            return
        mirror_names = [f"{prefix}_{name}" for name in table_names]
        async with self.meta_mysql_repository.session.begin():
            await self.meta_mysql_repository.delete_by_table_ids(mirror_names)
        await self.column_qdrant_repository.delete_by_table_ids(mirror_names)
        logger.info("已清理 {} 张镜像表的元数据", len(mirror_names))
