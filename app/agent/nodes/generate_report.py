"""
报告生成节点

作为自主分析链路的收尾，把执行结果、反思沉淀的分析发现和图表规格
综合成一份中文 Markdown 分析报告。图表在报告里用 chart://<id> 占位符引用，
由前端 MarkdownReport 拦截后渲染成真实 ECharts 图。
"""

import json

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import get_llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt


async def generate_report(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """综合结果与发现生成 Markdown 报告"""

    writer = runtime.stream_writer
    step = "生成报告"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        prompt = PromptTemplate(
            template=load_prompt("generate_report"),
            input_variables=["query", "intent", "results", "insights", "charts"],
        )
        chain = prompt | get_llm() | StrOutputParser()

        markdown = await chain.ainvoke(
            {
                "query": state["query"],
                "intent": state["intent"],
                "results": json.dumps(state["executed_results"], ensure_ascii=False, default=str),
                "insights": json.dumps(state["insights"], ensure_ascii=False)
                if state["insights"]
                else "（暂无）",
                "charts": json.dumps(state["chart_specs"], ensure_ascii=False, default=str)
                if state["chart_specs"]
                else "（暂无）",
            }
        )

        markdown = markdown.strip()
        writer({"type": "report", "markdown": markdown})
        writer({"type": "progress", "step": step, "status": "success"})
        logger.info("生成报告完成")
        return {"report_markdown": markdown}

    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
