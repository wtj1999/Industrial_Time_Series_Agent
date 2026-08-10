import logging
from typing import Any, Dict, List, Optional
import pandas as pd
from dataclasses import dataclass

from models.schemas import TaskSpec, TechPath, CSVProfile, Message

from agents.base_agent import BaseAgent, extract_tool_calls
from charts import extract_analysis_chart
from utils.prompt_loader import load_prompt
from tools.analysis_tools import TOOLS as _ANALYSIS_TOOLS

logger = logging.getLogger(__name__)


@dataclass
class AnalysisContext:
    """Context injected into every analysis tool via ``runtime.context``.

    Tools read ONLY these three fields directly from the context:

        ctx.df                # pandas.DataFrame
        ctx.target_columns    # List[str]  (CSV column names)
        ctx.feature_columns   # List[str]  (CSV column names)

    Note: the upstream ``TaskSpec`` schema carries only ``target_columns``
    and ``feature_columns`` (each a list of ``ColumnMapping``). There is
    no ``time_column`` / ``group_column`` / spec-limit / sampling-rate
    field in ``TaskSpec`` — every other parameter the tool needs must be
    passed as an explicit tool-call argument, inferred by the LLM from
    the column metadata (semantic_name, dtypes, value preview) that the
    agent embeds in the user prompt.
    """
    df: pd.DataFrame
    target_columns: List[str]
    feature_columns: List[str]
    user_id: Optional[str] = None


class AnalysisAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            system_prompt=load_prompt("analysis.md"),
            tools=_ANALYSIS_TOOLS,
            context_schema=AnalysisContext,
        )

    async def execute_analysis(
            self,
            thread_id: str,
            file_path: str,
            task_spec: TaskSpec,
            user_query: str,
            tech_proposal: Optional[TechPath],
            csv_profile: Optional[CSVProfile],
            user_id: Optional[str] = None,
            dialogue_history: Optional[List[Message]] = None,
    ) -> Dict[str, Any]:
        """Run the analysis sub-agent.

        Returns
        -------
        dict
            ``{"text": <LLM natural-language summary>, "chart": <chart
            payload dict or None>}``. Mirrors the anomaly-detection agent's
            return shape so the orchestrator can treat both uniformly.
            Only the **last** analysis-tool result is converted into a
            chart (per the "one tool per turn" guidance in analysis.md).
        """
        df = pd.read_csv(file_path)

        ctx = AnalysisContext(
            df=df,
            target_columns=[
                c.csv_column
                for c in task_spec.target_columns
                if c.csv_column
            ],
            feature_columns=[
                c.csv_column
                for c in task_spec.feature_columns
                if c.csv_column
            ],
            user_id=user_id,
        )

        # 历史对话由 orchestrator 的 SessionState(checkpointer 落盘)传
        # 入,作为多轮上下文。截取最近若干条避免 token 膨胀;dialogue_history
        # 已包含本轮用户消息,因此和 user_query 会有少量重复,不影响效果。
        recent_history = (dialogue_history or [])[-10:]
        history_block = "\n".join(
            f"[{getattr(m, 'role', '?')}] {getattr(m, 'content', '')}"
            for m in recent_history
        ) or "(无)"

        user_prompt = f"""
            你现在要执行工业数据分析任务。

            用户原始问题：
               {user_query or "(未提供)"}

               历史对话（仅作上下文，不要被旧结论误导）：
               {history_block}

               深度检索给出的技术路线：
               {tech_proposal.model_dump_json(indent=2, ensure_ascii=False) if tech_proposal else "None"}

               工具注入参数：
               {task_spec.model_dump_json(indent=2, ensure_ascii=False)}

               CSV画像：
               {csv_profile.model_dump_json(indent=2, ensure_ascii=False) if csv_profile else "None"}

               请据此选择工具并输出结构化结果。
        """

        text, messages = await self.invoke_chat_full(
            prompt=user_prompt,
            thread_id=thread_id,
            context=ctx,
        )

        tool_calls = extract_tool_calls(messages)
        logger.info("analysis: captured %d tool_call(s)", len(tool_calls))

        chart = extract_analysis_chart(tool_calls)
        if chart is not None:
            logger.info(
                "analysis chart extracted: tool=%s chart_type=%s",
                chart.get("tool_name"),
                chart.get("chart_type"),
            )
        else:
            logger.info(
                "analysis: no chartable tool result in %d tool_calls",
                len(tool_calls),
            )

        return {"text": text, "chart": chart, "tool_calls": tool_calls}
