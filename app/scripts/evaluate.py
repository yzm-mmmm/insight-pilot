"""
评测入口脚本

用法：
    uv run python -m app.scripts.evaluate -c eval/cases.yaml

初始化全量客户端后逐条跑评测集，最后汇总「SQL 正确率、召回命中率、
端到端通过率」三张分数，输出 JSON 报告并打印 Markdown 汇总表。
评测依赖完整服务栈（MySQL/Qdrant/ES/Embedding/LLM），请先启动 docker 基础服务。
"""

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import (
    dw_mysql_client_manager,
    meta_mysql_client_manager,
)
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.core.log import logger
from app.evaluation.cases import load_cases
from app.evaluation.runner import EvaluationRunner, summarize
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository


def _percent(value) -> str:
    """把 0~1 的小数转成百分比字符串，None 表示不适用"""
    return "—" if value is None else f"{value:.0%}"


def render_markdown(summary: dict, cases: list[dict]) -> str:
    """把汇总与逐条结果渲染成 Markdown 报告"""
    lines = [
        "# InsightPilot 评测报告",
        "",
        f"- 用例总数：{summary['total']}",
        f"- SQL 正确率：{summary['sql_correct']}/{summary['total']} "
        f"= {summary['sql_accuracy']:.1%}",
        f"- 端到端通过率：{summary['e2e_pass']}/{summary['total']} "
        f"= {summary['e2e_accuracy']:.1%}",
        f"- 字段召回命中率（平均）：{_percent(summary['column_recall_avg'])}",
        f"- 指标召回命中率（平均）：{_percent(summary['metric_recall_avg'])}",
        "",
        "| 用例 | 问题 | SQL | 字段召回 | 指标召回 | 端到端 | 说明 |",
        "| ---- | ---- | --- | -------- | -------- | ------ | ---- |",
    ]
    for case in cases:
        sql_mark = "✅" if case["sql_correct"] else "❌"
        e2e_mark = "✅" if case["e2e_pass"] else "❌"
        detail = case["sql_detail"] or case["error"] or ""
        lines.append(
            f"| {case['case_id']} | {case['question']} | {sql_mark} | "
            f"{_percent(case['column_recall'])} | {_percent(case['metric_recall'])} | "
            f"{e2e_mark} | {detail} |"
        )
    lines.append("")
    return "\n".join(lines)


async def evaluate(
    cases_path: Path, out_path: Path, limit: int | None, ids: list[str] | None
):
    """初始化依赖并跑一次全量评测"""
    meta_mysql_client_manager.init()
    dw_mysql_client_manager.init()
    qdrant_client_manager.init()
    embedding_client_manager.init()
    es_client_manager.init()

    async with (
        meta_mysql_client_manager.session_factory() as meta_session,
        dw_mysql_client_manager.session_factory() as dw_session,
    ):
        runner = EvaluationRunner(
            meta_mysql_repository=MetaMySQLRepository(meta_session),
            dw_mysql_repository=DWMySQLRepository(dw_session),
            column_qdrant_repository=ColumnQdrantRepository(qdrant_client_manager.client),
            metric_qdrant_repository=MetricQdrantRepository(qdrant_client_manager.client),
            value_es_repository=ValueESRepository(es_client_manager.client),
            embedding_client=embedding_client_manager.client,
        )

        cases = load_cases(cases_path)
        if ids:
            selected = set(ids)
            cases = [case for case in cases if case.id in selected]
        if limit is not None:
            cases = cases[:limit]

        logger.info(f"开始评测，共 {len(cases)} 条用例")
        results = [await runner.run_case(case) for case in cases]

    await meta_mysql_client_manager.close()
    await dw_mysql_client_manager.close()
    await qdrant_client_manager.close()
    await es_client_manager.close()

    summary = summarize(results)
    cases_payload = [asdict(result) for result in results]
    report = {"summary": summary, "cases": cases_payload}

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = render_markdown(summary, cases_payload)
    out_path.with_suffix(".md").write_text(markdown, encoding="utf-8")

    print(markdown)
    print(f"\n报告已写入：{out_path} 与 {out_path.with_suffix('.md')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="问数 Agent 系统化评测")
    parser.add_argument("-c", "--conf", required=True, help="评测用例 YAML 路径")
    parser.add_argument(
        "-o", "--out", default="eval/results.json", help="JSON 报告输出路径"
    )
    parser.add_argument("--limit", type=int, default=None, help="只跑前 N 条用例")
    parser.add_argument("--ids", default=None, help="只跑指定用例编号，逗号分隔")
    args = parser.parse_args()

    ids = [item.strip() for item in args.ids.split(",")] if args.ids else None
    asyncio.run(evaluate(Path(args.conf), Path(args.out), args.limit, ids))
