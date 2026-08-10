import logging
from typing import Any, Dict, List, Optional
import pandas as pd
from dataclasses import dataclass, field

from agents.base_agent import BaseAgent, extract_tool_calls
from charts import extract_anomaly_chart
from utils.prompt_loader import load_prompt
from tools.anomaly_detection_tools import TOOLS as _ANOMALY_DETECTION_TOOLS
from models.schemas import ModelRef, TaskSpec, TechPath, CSVProfile, Message

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

    ``model_save_name`` / ``model_thread_id`` / ``model_source_file``
    carry an optional user-selected cross-scope model reference (set by
    the orchestrator from the CSV-upload breakpoint's model picker).
    When ``model_save_name`` is set, ``resolve_model_path`` will look
    the model up under its *original* ``(thread_id, file_stem)`` scope
    instead of the current one. ``user_id`` is always rebound to the
    current runtime so cross-user access is impossible.
    """
    df: pd.DataFrame
    target_columns: List[str]
    feature_columns: List[str]
    user_id: Optional[str] = None
    thread_id: Optional[str] = None
    file_path: Optional[str] = None
    model_save_name: Optional[str] = None
    model_thread_id: Optional[str] = None
    model_source_file: Optional[str] = None


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
            selected_model_ref: Optional[ModelRef] = None,
    ) -> Dict[str, Any]:
        """Run the anomaly-detection sub-agent.

        Returns
        -------
        dict
            ``{"text": <LLM natural-language summary>, "chart": <chart
            payload dict or None>}``. The chart payload is extracted from
            the most recent ``detect_with_model`` / ``detect_ts_anomalies``
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
            model_save_name=selected_model_ref.save_name if selected_model_ref else None,
            model_thread_id=selected_model_ref.thread_id if selected_model_ref else None,
            model_source_file=selected_model_ref.source_file if selected_model_ref else None,
        )

        # 历史对话由 orchestrator 的 SessionState(checkpointer 落盘)传
        # 入,作为多轮上下文。截取最近若干条避免 token 膨胀;dialogue_history
        # 已包含本轮用户消息,因此和 user_query 会有少量重复,不影响效果。
        recent_history = (dialogue_history or [])[-10:]
        history_block = "\n".join(
            f"[{getattr(m, 'role', '?')}] {getattr(m, 'content', '')}"
            for m in recent_history
        ) or "(无)"

        # 软引导：用户在前端显式选择了复用模型时，提示 LLM 调
        # detect_with_model——工具内部会检测到 runtime 携带的 model_save_name
        # 并自动走加载分支（路径解析见 _common.resolve_model_path）。
        # LLM 不需要传 save_name，框架会忽略它并使用前端选择的引用。
        # 没选模型时也走同一个 tool，会自动训练+持久化；没有"不保存"的旁路。
        if selected_model_ref and selected_model_ref.save_name:
            ref_desc_parts = [f"save_name=`{selected_model_ref.save_name}`"]
            if selected_model_ref.detector_name:
                ref_desc_parts.append(f"detector={selected_model_ref.detector_name}")
            if selected_model_ref.source_file:
                ref_desc_parts.append(f"基于数据集={selected_model_ref.source_file}")
            if selected_model_ref.thread_id:
                ref_desc_parts.append(f"来自会话={selected_model_ref.thread_id}")
            model_hint = (
                "【用户指定复用模型】用户已在前端显式选择复用已训练模型："
                + " · ".join(ref_desc_parts)
                + "。请直接调用 detect_with_model(detector_name='"
                + (selected_model_ref.detector_name or "IForest")
                + "') 对当前数据打分；框架会从 runtime context 中读取模型引用并"
                "自动定位到模型原始作用域的 .joblib 文件（即使跨会话/跨数据集），"
                "走加载分支不会重复训练。detector_name 在加载模式下会被忽略，"
                "但仍需传入以满足签名约束。"
            )
        else:
            model_hint = (
                "（用户未指定复用模型；请调 detect_with_model 训练并持久化新模型后打分。"
                "所有训练都会落盘——若事后想清理临时实验产物，提示用户去"
                "「我的模型」页面删除。）"
            )

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

               {model_hint}

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

