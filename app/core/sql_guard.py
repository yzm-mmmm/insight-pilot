"""
SQL 只读安全守卫

这是防止 LLM 生成的 SQL 对数据仓库造成写入/删除/提权的最后一道代码级防线，
统一挂在 DW 仓储的 run() / validate() 两个真实执行出口上，避免任何节点绕过。
只允许单条以 SELECT / WITH 开头的只读查询。
"""

import re

# 明确表示写操作或结构变更的关键字，词边界匹配避免误伤 update_time 这类字段名
FORBIDDEN_KEYWORDS = (
    "insert",
    "update",
    "delete",
    "drop",
    "truncate",
    "alter",
    "create",
    "rename",
    "grant",
    "revoke",
    "merge",
)


def _strip_comments(sql: str) -> str:
    """移除 SQL 注释，防止通过注释夹带写语句"""
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)  # /* ... */
    sql = re.sub(r"--[^\n]*", " ", sql)  # -- 行注释
    sql = re.sub(r"#[^\n]*", " ", sql)  # MySQL # 行注释
    return sql


def _strip_string_literals(sql: str) -> str:
    """移除字符串字面量，避免 where 条件里的值（如 'delete'）触发误判"""
    sql = re.sub(r"'(?:[^'\\]|\\.)*'", "''", sql)
    sql = re.sub(r'"(?:[^"\\]|\\.)*"', '""', sql)
    return sql


def _first_keyword(sql: str) -> str:
    """返回 SQL 的第一个关键字（小写），用于判断语句类型"""
    match = re.match(r"\s*([a-zA-Z]+)", sql)
    return match.group(1).lower() if match else ""


def normalize_sql(raw: str) -> str:
    """从 LLM 原始输出中提取干净的 SQL 语句

    模型即便被提示词约束，仍可能输出 Markdown 代码块围栏（```sql / ```）
    或语句前的解释性文字，导致校验把首字符识别成非字母而报
    「语句类型：未知」。这里做纯文本层提取：去围栏、去首尾空白，
    并从首个以 SELECT / WITH 开头的行开始截取，保证进入校验的 SQL 干净。
    """

    if not raw:
        return ""

    text = raw.strip()

    # 去掉 Markdown 代码块围栏，例如 ```sql ... ``` 或 ``` ... ```
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text).strip()

    # 若仍有前导说明文字（如“以下是 SQL：”），从首个 SELECT / WITH 行截取
    match = re.search(r"(?im)^\s*(select|with)\b", text)
    if match and match.start() > 0:
        text = text[match.start() :].strip()

    return text


def assert_read_only_sql(sql: str) -> None:
    """断言 SQL 是单条只读查询，否则抛出 ValueError

    在 dw_mysql_repository.run / validate 执行前调用，校验失败会中断执行。
    """

    if not sql or not sql.strip():
        raise ValueError("SQL 不能为空")

    cleaned = _strip_string_literals(_strip_comments(sql)).strip()
    if not cleaned:
        raise ValueError("SQL 不能为空")

    # 拒绝多语句：按分号拆分后，除末尾空段外不允许出现第二个语句
    statements = [segment.strip() for segment in cleaned.split(";") if segment.strip()]
    if len(statements) != 1:
        raise ValueError("禁止执行多语句 SQL")

    statement = statements[0]
    first = _first_keyword(statement)
    if first not in ("select", "with"):
        raise ValueError(f"只允许执行 SELECT/WITH 查询，收到语句类型：{first or '未知'}")

    lowered = statement.lower()
    # SELECT ... INTO OUTFILE / DUMPFILE 是把查询结果写文件的通道，必须拦截
    if re.search(r"\binto\s+(outfile|dumpfile)\b", lowered):
        raise ValueError("禁止 INTO OUTFILE / DUMPFILE")

    # 词边界拒绝写/结构关键字，防止 SELECT 中夹带写操作
    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", lowered):
            raise ValueError(f"检测到禁止的关键字：{keyword}")


def enforce_scope(sql: str, scope: dict | None) -> str:
    """按数据权限范围改写 SQL

    本次仅做占位实现，直接返回原 SQL；行级权限后续在此接入 scope 过滤条件。
    """

    return sql


def _extract_tables(sql: str) -> set[str]:
    """提取 SQL 引用的表名（FROM/JOIN 后紧跟的标识符），用于表级白名单校验

    会剔除 WITH ... AS (...) 声明的 CTE 名，避免把 CTE 误判成物理表。
    这是执行期兜底校验，主要防线仍是检索期对元数据的过滤，因此只做
    正则级提取，覆盖 agent 生成的常规 FROM/JOIN 语句即可。
    """

    cleaned = _strip_string_literals(_strip_comments(sql)).lower()
    cte_names = set(
        re.findall(r"\bwith\b\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+as\s*\(", cleaned)
    )
    tables: set[str] = set()
    for token in re.findall(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", cleaned):
        if token not in cte_names:
            tables.add(token)
    return tables


def assert_allowed_tables(sql: str, allowed_tables: set[str] | None) -> None:
    """断言 SQL 只引用了允许的表

    allowed_tables 为 None 表示不限制（管理员）；否则引用了白名单之外的
    表名时抛出 ValueError，拦截越权查询。
    """

    if allowed_tables is None:
        return

    referenced = _extract_tables(sql)
    denied = referenced - allowed_tables
    if denied:
        raise ValueError(
            f"无权访问表：{', '.join(sorted(denied))}，请在数据权限面板申请这些表的查询权限"
        )
