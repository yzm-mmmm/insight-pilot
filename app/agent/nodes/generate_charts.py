"""
图表生成节点

在自主分析循环结束后，审视全部执行结果，挑选适合可视化的数据，
让大模型输出「图表意图 spec」而非完整 ECharts option（避免复杂 option 生成坏 JSON）。
spec 只包含前端拼装 option 所需的最小信息：图表类型、标题、X/Y 字段和真实数据行。

本节点输出的 chart_specs 通过 operator.add reducer 累积到 state，供报告节点
和前端 ChartRenderer 复用。
"""

import json

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt

# 前端 ChartRenderer 只认识这四类图表，其他类型一律丢弃
CHART_TYPES = ("bar", "line", "pie", "scatter")


async def generate_charts(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """根据执行结果生成图表意图 spec"""

    writer = runtime.stream_writer
    step = "生成图表"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        executed_results = state["executed_results"]
        # 没有任何执行结果时无需生成图表，直接返回空更新
        if not executed_results:
            writer({"type": "progress", "step": step, "status": "success"})
            return {}

        prompt = PromptTemplate(
            template=load_prompt("generate_charts"),
            input_variables=["query", "intent", "results"],
        )
        chain = prompt | llm | JsonOutputParser()

        result = await chain.ainvoke(
            {
                "query": state["query"],
                "intent": state["intent"],
                "results": json.dumps(executed_results, ensure_ascii=False, default=str),
            }
        )

        # 兼容模型输出 {"charts": [...]} 或直接输出数组两种情况
        raw = result.get("charts", []) if isinstance(result, dict) else result
        if not isinstance(raw, list):
            raw = []

        # 逐项清洗模型输出，只保留结构合法且类型在白名单内的图表
        charts = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                continue

            chart_type = item.get("type")
            if chart_type not in CHART_TYPES:
                continue

            rows = [r for r in (item.get("rows") or []) if isinstance(r, dict)]
            if not rows:
                continue

            charts.append(
                {
                    "id": str(item.get("id") or f"chart_{index + 1}"),
                    "type": chart_type,
                    "title": str(item.get("title") or "").strip() or f"图表 {index + 1}",
                    "xField": item.get("xField"),
                    "yFields": item.get("yFields") or item.get("series") or [],
                    "series": item.get("series") or [],
                    "rows": rows,
                }
            )

        for chart in charts:
            writer({"type": "chart", "data": chart})

        logger.info(f"生成图表 {len(charts)} 张")
        writer({"type": "progress", "step": step, "status": "success"})

        # 没有合法图表时返回空更新，避免 reducer 收到 None
        return {"chart_specs": charts} if charts else {}

    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
