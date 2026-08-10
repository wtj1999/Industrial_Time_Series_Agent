import logging
from typing import Any, Dict, List, Optional
import pandas as pd
from dataclasses import dataclass, field

from agents.base_agent import BaseAgent, extract_tool_calls
from charts import extract_anomaly_chart
from utils.prompt_loader import load_prompt
from tools.anomaly_detection_tools import TOOLS as _ANOMALY_DETECTION_TOOLS
from models.schemas import TaskSpec, TechPath, CSVProfile, Message

logger = logging.getLogger(__name__)


@dataclass
class AnomalyDetectionContext:
    """Context for anomaly detection.

    Note
    ----
    Only ``df`` / ``target_columns`` / ``feature_columns`` are visible to
    the LLM as data-access fields. ``user_id``, ``thread_id`` and
    ``file_path`` are framework-managed metadata used solely to derive a
    deterministic persistence path (``artifacts/anomaly_detection/
    <user_id>/<thread_id>/<file_stem>_anomaly_detection/
    <save_name>.joblib``); the LLM does not control or see them.
    """
    df: pd.DataFrame
    target_columns: List[str]
    feature_columns: List[str]
    user_id: Optional[str] = None
    thread_id: Optional[str] = None
    file_path: Optional[str] = None


class AnomalyDetectionAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            system_prompt=load_prompt("anomaly_detection.md"),
            tools=_ANOMALY_DETECTION_TOOLS,
            context_schema=AnomalyDetectionContext,
        )

    async def execute_anomaly_detection(
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
        """Run the anomaly-detection sub-agent.

        Returns
        -------
        dict
            ``{"text": <LLM natural-language summary>, "chart": <chart
            payload dict or None>}``. The chart payload is extracted from
            the most recent ``detect_anomalies`` / ``detect_ts_anomalies``
            tool result captured during this turn — if no such tool ran
            (e.g. the LLM only called ``list_pyod_detectors``), ``chart``
            is ``None`` and the orchestrator simply skips the chart event.
        """
        df = pd.read_csv(file_path)

        ctx = AnomalyDetectionContext(
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

        # 历史对话由 orchestrator 的 SessionState(checkpointer 落盘)传
        # 入,作为多轮上下文。截取最近若干条避免 token 膨胀;dialogue_history
        # 已包含本轮用户消息,因此和 user_query 会有少量重复,不影响效果。
        recent_history = (dialogue_history or [])[-10:]
        history_block = "\n".join(
            f"[{getattr(m, 'role', '?')}] {getattr(m, 'content', '')}"
            for m in recent_history
        ) or "(无)"

        user_prompt = f"""
               你现在要执行工业数据异常检测任务。

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
        logger.info("anomaly_detection: captured %d tool_call(s)", len(tool_calls))

        chart = extract_anomaly_chart(tool_calls)
        if chart is not None:
            logger.info(
                "anomaly_detection chart extracted: tool=%s detector=%s "
                "n_samples=%d n_anomalies=%d",
                chart.get("tool_name"),
                chart.get("detector_name"),
                chart.get("n_samples"),
                chart.get("n_anomalies"),
            )
        else:
            logger.info(
                "anomaly_detection: no chartable tool result in %d tool_calls",
                len(tool_calls),
            )

        return {"text": text, "chart": chart, "tool_calls": tool_calls}

