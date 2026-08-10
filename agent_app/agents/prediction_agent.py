import logging
from typing import Any, Dict, List, Optional
import pandas as pd
from dataclasses import dataclass

from models.schemas import TaskSpec, TechPath, CSVProfile, Message

from agents.base_agent import BaseAgent, extract_tool_calls
from charts import extract_evaluation_chart, extract_prediction_chart
from utils.prompt_loader import load_prompt
from tools.prediction_tools import TOOLS as _PREDICTION_TOOLS

logger = logging.getLogger(__name__)


@dataclass
class PredictionContext:
    """Context injected into every prediction tool via ``runtime.context``.

    Mirrors :class:`AnalysisContext` / :class:`AnomalyDetectionContext`:
    tools read ONLY these data-access fields directly.

        ctx.df                # pandas.DataFrame
        ctx.target_columns    # List[str]  (CSV column names)
        ctx.feature_columns   # List[str]  (CSV column names)

    ``user_id``, ``thread_id`` and ``file_path`` are framework-managed
    metadata kept here for future per-(user, thread, file) caching of
    upstream HTTP calls; they are **not** surfaced to the LLM as
    data-access fields, and the prediction tools do not currently
    persist artifacts (unlike the anomaly-detection family) so the path
    layout is not used yet.
    """
    df: pd.DataFrame
    target_columns: List[str]
    feature_columns: List[str]
    user_id: Optional[str] = None
    thread_id: Optional[str] = None
    file_path: Optional[str] = None


class PredictionAgent(BaseAgent):
    """Sub-agent that drives the upstream time-series foundation-model
    prediction service (sundial / toto-2 / chronos-2 / timer-s1 /
    timesfm-2.5 / moirai-2.0-R-small / tirex-1.1-gifteval).

    The agent exposes the canonical prediction tool list (knowledge →
    forecast → evaluation) and is wired with the ``prediction.md``
    system prompt. Like the analysis / anomaly-detection agents it
    returns ``{"text", "chart", "tool_calls"}``; ``chart`` is currently
    always ``None`` because no prediction-chart extractor is implemented
    yet — the orchestrator should treat it as optional and skip the
    chart event when ``None``, exactly as it does for the analysis agent
    when no chartable tool result was captured.
    """

    def __init__(self):
        super().__init__(
            system_prompt=load_prompt("prediction.md"),
            tools=_PREDICTION_TOOLS,
            context_schema=PredictionContext,
        )

    async def execute_prediction(
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
        """Run the prediction sub-agent.

        Returns
        -------
        dict
            ``{"text": <LLM natural-language summary>, "chart": <chart
            payload dict or None>, "tool_calls": [...]}``. Mirrors the
            analysis / anomaly-detection agents' return shape so the
            orchestrator can treat all three uniformly. ``chart`` is
            ``None`` until a prediction-chart extractor is added.
        """
        df = pd.read_csv(file_path)

        ctx = PredictionContext(
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
            thread_id=thread_id,
            file_path=file_path,
        )

        recent_history = (dialogue_history or [])[-10:]
        history_block = "\n".join(
            f"[{getattr(m, 'role', '?')}] {getattr(m, 'content', '')}"
            for m in recent_history
        ) or "(无)"

        user_prompt = f"""
            你现在要执行工业时序预测任务。

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
        logger.info("prediction: captured %d tool_call(s)", len(tool_calls))

        # Build the forecast chart payload from the last chartable
        # prediction-tool result. Returns None when no suitable tool ran
        # (e.g. ``forecast_ensemble`` is not visualisable in this view),
        # in which case we fall back to the evaluation extractor — that
        # one handles ``backtest_forecast`` / ``compare_forecast_models_backtest``
        # and emits a ``chart_type == "backtest"`` payload instead. If
        # neither extractor produces a chart, the orchestrator simply
        # skips the chart event.
        chart: Optional[Dict[str, Any]] = extract_prediction_chart(tool_calls)
        if chart is None:
            chart = extract_evaluation_chart(tool_calls)

        if chart is not None:
            logger.info(
                "prediction chart extracted: tool=%s chart_type=%s",
                chart.get("tool_name"),
                chart.get("chart_type"),
            )
        else:
            logger.info(
                "prediction: no chartable tool result in %d tool_calls",
                len(tool_calls),
            )

        return {"text": text, "chart": chart, "tool_calls": tool_calls}
