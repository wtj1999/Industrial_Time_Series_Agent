"""Auto-pipeline tools driven by PyOD's :class:`ADEngine`.

These tools hand control to the ADEngine, which itself:

- profiles the data,
- consults the knowledge base + routing rules,
- selects candidate detectors,
- runs them in parallel,
- computes consensus / quality metrics.

This is the highest-level entry point; use it when the user wants
``"just detect anomalies"`` without committing to a specific algorithm.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from langchain.tools import ToolRuntime, tool

from agent_app.tools._tool_guard import tool_guard
from agent_app.tools.anomaly_detection_tools._common import (
    format_notes,
    prepare_feature_matrix,
    scores_summary,
    top_anomaly_rows,
)
from agent_app.tools.outlier_detection_scripts.pyod.utils.ad_engine import ADEngine
from agent_app.tools.outlier_detection_scripts.pyod.utils._quality_metrics import (
    compute_quality,
)

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------

def _quality_block(state) -> Dict[str, Any]:
    """Best-effort extraction of a quality-metrics block from an
    :class:`InvestigationState`. Falls back to an empty dict on errors
    so callers don't crash when the engine shape changes."""
    try:
        consensus = getattr(state, "consensus", None) or {}
        results = getattr(state, "results", None) or []
        analysis = getattr(state, "analysis", None) or {}

        scores = (
            consensus.get("scores")
            or analysis.get("scores")
            or (results[0].get("scores_train") if results else None)
        )
        labels = (
            consensus.get("labels")
            or analysis.get("labels")
            or (results[0].get("labels_train") if results else None)
        )
        if scores is None or labels is None:
            return {}
        return dict(compute_quality(
            np.asarray(scores, dtype=float),
            np.asarray(labels, dtype=int),
            results,
            consensus,
        ))
    except Exception as exc:
        logger.debug("compute_quality failed: %s", exc)
        return {}


def _top_anomalies_from_state(state, df: pd.DataFrame, top_n: int) -> List[Dict[str, Any]]:
    """Pull consensus scores off ``state`` and return Top-N rows."""
    consensus = getattr(state, "consensus", None) or {}
    scores = consensus.get("scores")
    threshold = consensus.get("threshold")
    if scores is None:
        # Fall back to the first detector's scores.
        results = getattr(state, "results", None) or []
        if results:
            scores = results[0].get("scores_train")
            threshold = threshold or results[0].get("threshold")
    if scores is None:
        return []
    scores = np.asarray(scores, dtype=float).ravel()
    return top_anomaly_rows(df, scores, threshold, top_n)


# ----------------------------------------------------------------------
# Tools
# ----------------------------------------------------------------------

@tool("auto_detect_anomalies")
@tool_guard("auto_detect_anomalies")
def auto_detect_anomalies(
    runtime: ToolRuntime,
    data_type: str = "tabular",
    priority: str = "balanced",
    return_top_n: int = 10,
) -> Dict[str, Any]:
    """自动异常检测：让 ADEngine 自己选算法并跑完整流程。

    流程：数据画像 -> 候选检测器选择 -> 并行执行 -> 共识分析 ->
    质量评估 -> 报告生成。当用户没有明确指定算法、或想看「数据上
    哪些检测器表现最好」时调用本工具。

    Parameters
    ----------
    data_type : str, default ``"tabular"``
        数据模态提示：``"tabular"`` / ``"time_series"`` / ``"graph"`` /
        ``"text"`` / ``"image"`` / ``"audio"`` / ``"multimodal"``。
    priority : str, default ``"balanced"``
        算法选择偏好：``"balanced"`` / ``"accuracy"`` / ``"speed"`` /
        ``"explainability"``。
    return_top_n : int, default 10
        返回共识分数最高的 Top-N 行（含原始值）。

    Returns
    -------
    Dict[str, Any]
        ``report`` 是 ADEngine 生成的可读报告；``analysis`` /
        ``consensus`` / ``plans`` / ``results`` 是 InvestigationState 的
        原始结构化字段；``quality`` 是 quality-metrics 块；
        ``top_anomalies`` 是共识 Top-N 行。
    """
    ctx = runtime.context
    df: pd.DataFrame = ctx.df
    X, info = prepare_feature_matrix(runtime)

    engine = ADEngine()
    try:
        state = engine.investigate(X, data_type=data_type, priority=priority)
    except TypeError:
        # Older ADEngine signature may not accept ``priority``.
        state = engine.investigate(X, data_type=data_type)

    report = ""
    try:
        report = engine.report(state)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("engine.report failed: %s", exc)

    quality = _quality_block(state)
    top_rows = _top_anomalies_from_state(state, df, return_top_n)

    # Surface score distribution when available.
    consensus = getattr(state, "consensus", None) or {}
    consensus_scores = consensus.get("scores")
    summary_stats = (
        scores_summary(np.asarray(consensus_scores, dtype=float).ravel(),
                       threshold=consensus.get("threshold"),
                       top_n=return_top_n)
        if consensus_scores is not None else {}
    )

    return {
        "task_type": "anomaly_detection",
        "tool_name": "auto_detect_anomalies",
        "summary": (
            "ADEngine 自动检测完成（data_type=%s, priority=%s）。"
            % (data_type, priority)
        ),
        "report": report,
        "analysis": getattr(state, "analysis", None),
        "consensus": consensus,
        "plans": getattr(state, "plans", None),
        "results": getattr(state, "results", None),
        "quality": quality,
        "scores_summary": summary_stats,
        "top_anomalies": top_rows,
        "n_samples": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "notes": format_notes(info, [
            "data_type=%s, priority=%s；可用 priority 切换 accuracy/speed/"
            "explainability 重新跑。" % (data_type, priority)
        ]),
    }


@tool("recommend_detectors")
@tool_guard("recommend_detectors")
def recommend_detectors(
    runtime: ToolRuntime,
    data_type: str = "tabular",
    priority: str = "balanced",
    top_k: int = 5,
) -> Dict[str, Any]:
    """基于当前数据画像，给出 ADEngine 推荐的检测器与理由（不执行）。

    相比 :func:`auto_detect_anomalies`，本工具不真正训练，只返回
    ADEngine 的「候选清单 + 理由 + 默认参数」，便于大模型与用户确认
    算法选择后再调用 :func:`detect_with_model`（训练 + 持久化 + 打分）。

    Parameters
    ----------
    data_type : str, default ``"tabular"``
        数据模态提示。
    priority : str, default ``"balanced"``
        偏好（accuracy / speed / balanced / explainability）。
    top_k : int, default 5
        最多返回多少个候选。

    Returns
    -------
    Dict[str, Any]
        ``candidates`` 是每个候选检测器的 ``{name, params, reason}``。
    """
    X, info = prepare_feature_matrix(runtime)
    engine = ADEngine()

    try:
        profile = engine.profile_data(X, data_type=data_type)
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "task_type": "anomaly_detection",
            "tool_name": "recommend_detectors",
            "summary": "数据画像失败：%s" % exc,
            "candidates": [],
            "notes": format_notes(info, []),
        }

    try:
        plans = engine.plan_detection(
            profile, priority=priority, top_k=int(top_k))
    except Exception as exc:
        logger.debug("plan_detection failed: %s", exc)
        plans = []

    candidates: List[Dict[str, Any]] = []
    if isinstance(plans, list):
        for plan in plans:
            if isinstance(plan, dict):
                candidates.append({
                    "name": plan.get("detector_name") or plan.get("name"),
                    "params": plan.get("params", {}),
                    "reason": plan.get("reason") or plan.get("justification"),
                    "complexity": plan.get("complexity"),
                })
    elif isinstance(plans, dict):
        # Some engines return {"plans": [...]} or single plan.
        nested = plans.get("plans")
        if isinstance(nested, list):
            for plan in nested:
                candidates.append({
                    "name": plan.get("detector_name") or plan.get("name"),
                    "params": plan.get("params", {}),
                    "reason": plan.get("reason") or plan.get("justification"),
                    "complexity": plan.get("complexity"),
                })
        else:
            candidates.append({
                "name": plans.get("detector_name"),
                "params": plans.get("params", {}),
                "reason": plans.get("reason"),
                "complexity": plans.get("complexity"),
            })

    return {
        "task_type": "anomaly_detection",
        "tool_name": "recommend_detectors",
        "summary": (
            "基于当前数据画像，ADEngine 推荐 %d 个候选检测器。"
            % len(candidates)
        ),
        "data_type": data_type,
        "priority": priority,
        "profile": profile if isinstance(profile, (dict, list)) else None,
        "candidates": candidates,
        "notes": format_notes(info, [
            "本工具只做推荐不训练；选定后用 detect_with_model 执行"
            "（自动 train + 持久化 + 打分）。"]),
    }


TOOLS = [
    auto_detect_anomalies,
    recommend_detectors,
]
