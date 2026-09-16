"""
电商问数 Agent 状态定义

State 是 LangGraph 各节点之间传递和更新的共享数据。
在单轮检索链路之上，扩展了自主分析循环所需的规划、反思、执行结果与迭代控制字段。
其中在循环里需要累积的列表字段使用 Annotated + operator.add reducer，
否则每次节点返回都会互相覆盖，这是改造后最容易踩的隐性坑。
"""

from operator import add
from typing import Annotated, TypedDict

from app.entities.column_info import ColumnInfo
from app.entities.metric_info import MetricInfo
from app.entities.value_info import ValueInfo


class MetricInfoState(TypedDict):
    """面向 SQL 生成提示词的指标信息"""

    name: str
    description: str
    # 指标依赖的字段 id，用来提示模型不要脱离业务口径随意计算
    relevant_columns: list[str]
    alias: list[str]


class ColumnInfoState(TypedDict):
    """表上下文中的字段信息"""

    name: str
    type: str
    role: str
    # 字段真实样例值，尤其用于辅助 where 条件里的枚举值选择
    examples: list
    description: str
    alias: list[str]


class TableInfoState(TypedDict):
    """SQL 生成阶段真正传给模型的表结构上下文"""

    name: str
    role: str
    description: str
    columns: list[ColumnInfoState]


class DateInfoState(TypedDict):
    """SQL 生成阶段使用的当前日期上下文"""

    date: str
    weekday: str
    quarter: str


class DBInfoState(TypedDict):
    """SQL 生成阶段使用的数据库环境信息"""

    dialect: str
    version: str


class PlanItemState(TypedDict):
    """规划阶段拆出的一个分析子问题"""

    id: int
    question: str
    intent: str


class ReflectionState(TypedDict):
    """反思节点对当前执行结果的判断与下一步动作"""

    next_action: str  # done / retry_sql / new_sub_question / ask_user
    finding: str  # 本轮分析发现
    reason: str  # 决策依据


class ExecutionResultState(TypedDict):
    """一次 SQL 执行的富结果，供反思、画图和报告节点复用"""

    question: str
    sql: str
    columns: list[str]
    rows: list[dict]


class DataAgentState(TypedDict):
    """一次问数链路中的核心状态"""

    query: str  # 用户原始问题
    user_id: int  # 当前登录用户编号
    role: str  # 用户角色
    scope: dict | None  # 数据权限范围（预留，行级权限扩展点）
    granted_tables: set[str]  # 已授权的表名集合（管理员为空集且执行期不限制）
    intent: str  # 整体分析意图的一句话概括

    # 自主分析循环：规划与游标
    plan: list[PlanItemState]  # 拆解出的子问题清单
    plan_cursor: int  # 当前处理到第几个子问题
    current_question: str  # 当前正在回答的子问题
    iteration_count: int  # 反思轮数计数，防止无限循环
    sql_retry_count: int  # 单条 SQL 校验修正次数
    reflection: ReflectionState  # 最近一次反思结论

    # 检索结果
    keywords: list[str]
    retrieved_column_infos: list[ColumnInfo]
    retrieved_metric_infos: list[MetricInfo]
    retrieved_value_infos: list[ValueInfo]

    table_infos: list[TableInfoState]  # 合并和补齐后的表结构上下文
    metric_infos: list[MetricInfoState]  # 合并后的指标上下文
    date_info: DateInfoState  # 当前日期 星期和季度信息
    db_info: DBInfoState  # 数据库方言和版本信息
    feedback_examples: list[dict]  # 用户历史纠错的 few-shot 示例（question/wrong_sql/corrected_sql）

    sql: str  # 生成或校正后的 SQL
    error: str  # 校验 SQL 时出现的错误信息

    # 循环中累积的字段，必须用 operator.add reducer 追加而非覆盖
    sql_history: Annotated[list[str], add]  # 已尝试过的 SQL
    executed_results: Annotated[list[ExecutionResultState], add]  # 每次执行的富结果
    insights: Annotated[list[str], add]  # 反思沉淀的分析结论
    chart_specs: Annotated[list[dict], add]  # 图表意图 spec（阶段③写入）
    conversation_history: Annotated[list[dict], add]  # 多轮对话历史（阶段④写入）
    report_markdown: str  # 最终分析报告（阶段③写入）
