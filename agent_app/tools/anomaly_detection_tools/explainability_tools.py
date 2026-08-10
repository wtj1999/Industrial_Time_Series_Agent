"""Post-hoc explainability tools for anomaly detection results.

These tools surface *why* a detector thinks specific samples are
anomalous, in two complementary flavours:

- :func:`explain_anomalies` — per-sample feature contributions: top-5
  features by absolute z-score, with their raw value, column mean, and
  direction (high / low). Useful for surfacing a human-readable reason
  for a flagged row.
- :func:`compute_feature_importance` — per-feature contribution to the
  detector's overall score ranking: Pearson correlation between each
  column's |z-score| and the detector's anomaly scores.

Both helpers wrap the vendored ``pyod.utils._quality_metrics`` functions
so we don't re-implement the math.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from langchain.tools import ToolRuntime, tool

from agent_app.tools._tool_guard import tool_guard
from agent_app.tools.anomaly_detection_tools._common import (
    build_detector_by_name,
    decision_scores_,
    format_notes,
    labels_,
    prepare_feature_matrix,
    scores_summary,
    threshold_,
)
from agent_app.tools.outlier_detection_scripts.pyod.utils._quality_metrics import (
    compute_feature_importance as _compute_feature_importance,
    feature_contributions as _feature_contributions,
)

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Tools
# ----------------------------------------------------------------------

@tool("explain_anomalies")
@tool_guard("explain_anomalies")
def explain_anomalies(
    detector_name: str,
    runtime: ToolRuntime,
    top_k: int = 10,
    contamination: float = 0.1,
    random_state: Optional[int] = None,
) -> Dict[str, Any]:
    """解释指定检测器挑出的 Top-K 异常**为什么**异常。

    流程：在当前 DataFrame 上 fit 指定检测器 -> 取分数最高的 Top-K
    样本 -> 对每个样本计算其与训练集均值的特征级 z-score，返回 Top-5
    偏离方向最大的特征（含原始值、列均值、方向）。

    Parameters
    ----------
    detector_name : str
        任意 PyOD 检测器名称。
    top_k : int, default 10
        要解释的异常样本数量（按分数降序）。
    contamination : float, default 0.1
        异常比例。
    random_state : int, optional
        随机种子。

    Returns
    -------
    Dict[str, Any]
        ``explanations`` 为长度 ``top_k`` 的列表，每项含
        ``row_index``、``score``、``contributions``（Top-5 特征）。
    """
    if top_k <= 0:
        return {
            "task_type": "anomaly_detection",
            "tool_name": "explain_anomalies",
            "summary": "top_k 必须为正整数。",
            "explanations": [],
        }

    ctx = runtime.context
    df: pd.DataFrame = ctx.df
    X, info = prepare_feature_matrix(runtime)
    feature_names = info["used_columns"]

    detector = build_detector_by_name(
        detector_name,
        contamination=contamination, random_state=random_state)
    detector.fit(X)

    scores = decision_scores_(detector)
    th = threshold_(detector)
    lbls = labels_(detector)

    # Pick Top-K by score, finite only.
    finite = np.isfinite(scores)
    valid_pos = np.nonzero(finite)[0]
    valid_scores = scores[finite]
    if valid_scores.size == 0:
        return {
            "task_type": "anomaly_detection",
            "tool_name": "explain_anomalies",
            "detector_name": detector_name,
            "summary": "无有效分数可解释。",
            "explanations": [],
            "notes": format_notes(info, []),
        }
    k = min(int(top_k), valid_scores.size)
    order = np.argsort(valid_scores)[::-1][:k]
    picked = valid_pos[order]

    explanations: List[Dict[str, Any]] = []
    for pos in picked:
        contributions = _feature_contributions(
            X, int(pos), scores, feature_names=feature_names)
        row_values = {}
        try:
            row_values = {
                str(c): _json_safe(df.iloc[pos][c])
                for c in df.columns
            }
        except Exception:
            pass
        explanations.append({
            "row_index": int(pos),
            "score": float(scores[pos]),
            "is_anomaly": bool(th is not None and scores[pos] > th),
            "contributions": contributions,
            "row_values": row_values,
        })

    summary_stats = scores_summary(scores, threshold=th, top_n=k)
    return {
        "task_type": "anomaly_detection",
        "tool_name": "explain_anomalies",
        "detector_name": detector_name,
        "summary": (
            "已用 %s 解释 Top-%d 异常样本（threshold=%.4f）。"
            % (detector_name, k, th if th is not None else float("nan"))
        ),
        "threshold": th,
        "n_samples": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "feature_columns": feature_names,
        "scores_summary": summary_stats,
        "n_anomalies": int((lbls > 0).sum()) if lbls.size else 0,
        "explanations": explanations,
        "notes": format_notes(info, [
            "contributions 中 z_score 是基于当前 DataFrame 列均值/标准差"
            "计算的；direction='high' 表示该值高于均值，'low' 表示低于。"
        ]),
    }


@tool("compute_feature_importance")
@tool_guard("compute_feature_importance")
def compute_feature_importance(
    detector_name: str,
    runtime: ToolRuntime,
    contamination: float = 0.1,
    random_state: Optional[int] = None,
) -> Dict[str, Any]:
    """计算每个特征对检测器分数排序的「驱动力」（Pearson 相关）。

    对每一列，计算其绝对 z-score 与检测器分数之间的 Pearson 相关。
    绝对值越大，说明该列越能驱动检测器把样本判为异常。返回按绝对值
    排序的 (feature, importance) 列表。

    Parameters
    ----------
    detector_name : str
        任意 PyOD 检测器。
    contamination : float, default 0.1
        异常比例。
    random_state : int, optional
        随机种子。

    Returns
    -------
    Dict[str, Any]
        ``importances`` 是 ``[{feature, importance}, ...]``，按
        ``abs(importance)`` 降序。
    """
    ctx = runtime.context
    X, info = prepare_feature_matrix(runtime)
    feature_names = info["used_columns"]

    detector = build_detector_by_name(
        detector_name,
        contamination=contamination, random_state=random_state)
    detector.fit(X)
    scores = decision_scores_(detector)

    result = {
        "scores_train": scores,
    }
    importances = _compute_feature_importance(result, X)
    if importances is None:
        return {
            "task_type": "anomaly_detection",
            "tool_name": "compute_feature_importance",
            "detector_name": detector_name,
            "summary": "无法计算特征重要性（输入维度不匹配或全为零方差）。",
            "importances": [],
            "notes": format_notes(info, []),
        }

    pairs = list(zip(feature_names, importances))
    pairs.sort(key=lambda kv: abs(kv[1]), reverse=True)

    return {
        "task_type": "anomaly_detection",
        "tool_name": "compute_feature_importance",
        "detector_name": detector_name,
        "summary": (
            "%s 的特征重要性已计算（共 %d 个特征）。"
            % (detector_name, len(pairs))
        ),
        "importances": [
            {"feature": name, "importance": float(imp)}
            for name, imp in pairs
        ],
        "threshold": threshold_(detector),
        "n_samples": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "notes": format_notes(info, [
            "importance 是 |z-score| 与分数的 Pearson 相关，范围 [-1, 1]；",
            "正号表示该列偏高时分数偏高，负号表示该列偏低时分数偏高。"
        ]),
    }


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------

def _json_safe(v: Any) -> Any:
    """Best-effort conversion of a scalar DataFrame cell to JSON-safe value."""
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


TOOLS = [
    explain_anomalies,
    compute_feature_importance,
]
