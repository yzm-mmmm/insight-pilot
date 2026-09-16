"""
数仓 MySQL 仓储

这一层对应文档里的 DW Repository，职责是到真实数仓中补齐配置文件里
没有显式维护的信息，例如字段类型和字段示例值。Service 层只关心
“需要哪些信息”，具体怎样查数仓由仓储层统一封装
SQL 生成闭环中的数据库环境读取 SQL 校验和最终查询执行也集中放在这里
"""

import datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sql_guard import assert_allowed_tables, assert_read_only_sql


def _json_safe(value):
    """把数据库返回的非 JSON 类型转成可序列化类型

    column_info.examples 与 ES 全文索引都是 JSON 存储，而 DECIMAL/DATE/TIME
    列经驱动返回的是 Decimal / datetime.date / datetime.timedelta 等对象，
    直接写入会抛 "Object of type ... is not JSON serializable"。这里统一在
    取值源头归一化，避免元数据爬取在 INSERT 阶段静默失败。
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time, datetime.timedelta)):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    return str(value)


class DWMySQLRepository:
    """负责查询数仓真实表结构和字段样例值"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_column_types(self, table_name: str) -> dict[str, str]:
        """查询整张表的字段类型，作为 ColumnInfo.type 的真实来源"""
        sql = f"show columns from {table_name}"
        result = await self.session.execute(text(sql))
        result_dict = result.mappings().fetchall()
        return {row["Field"]: row["Type"] for row in result_dict}

    async def get_column_values(
        self, table_name: str, column_name: str, limit: int = 10
    ) -> list:
        """抽样查询字段示例值，供元数据入库和后续检索链路复用"""
        sql = f"select distinct {column_name} from {table_name} limit {limit}"
        result = await self.session.execute(text(sql))
        return [_json_safe(row[0]) for row in result.fetchall()]

    async def get_primary_key(self, table_name: str) -> list[str]:
        """查询表的主键列名列表，用于自动爬取时标记主键字段角色"""
        sql = f"show keys from {table_name} where key_name = 'PRIMARY'"
        result = await self.session.execute(text(sql))
        return [row["Column_name"] for row in result.mappings().fetchall()]

    async def get_db_info(self):
        """读取当前数仓数据库的方言和版本，供 SQL 生成提示词使用"""

        sql = "select version()"
        result = await self.session.execute(text(sql))
        version = result.scalar()

        # dialect 来自 SQLAlchemy 当前绑定的数据库方言，例如 mysql
        dialect = self.session.bind.dialect.name
        return {"dialect": dialect, "version": version}

    async def list_tables(self) -> list[str]:
        """列出当前数仓库的全部真实数据表，作为表级权限的可授权清单"""
        sql = (
            "select table_name from information_schema.tables "
            "where table_schema = database() order by table_name"
        )
        result = await self.session.execute(text(sql))
        return [row[0] for row in result.fetchall()]

    async def drop_tables_by_prefix(self, prefix: str) -> int:
        """删除指定前缀的镜像表（删除数据源时清理），返回删除数量"""
        sql = (
            "select table_name from information_schema.tables "
            "where table_schema = database() and table_name regexp :prefix"
        )
        result = await self.session.execute(text(sql), {"prefix": f"^{prefix}_"})
        names = [row[0] for row in result.fetchall()]
        for name in names:
            await self.session.execute(text(f"DROP TABLE IF EXISTS `{name}`"))
        await self.session.commit()
        return len(names)

    async def validate(self, sql: str, allowed_tables: set[str] | None = None):
        """用 EXPLAIN 让数据库提前解析 SQL，发现语法 表名 字段名等错误"""
        assert_read_only_sql(sql)
        assert_allowed_tables(sql, allowed_tables)
        sql = f"explain {sql}"
        await self.session.execute(text(sql))

    async def run(self, sql: str, allowed_tables: set[str] | None = None) -> dict:
        """执行最终 SQL，返回结构化结果 {columns, rows}"""
        assert_read_only_sql(sql)
        assert_allowed_tables(sql, allowed_tables)
        result = await self.session.execute(text(sql))
        columns = list(result.keys())
        rows = [dict(row) for row in result.mappings().fetchall()]
        return {"columns": columns, "rows": rows}
