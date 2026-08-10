"""Evaluation and comparison tools for PyOD detection results.

Two tools live here:

- :func:`evaluate_detection` — fit a single detector on the current
  DataFrame and report score distribution, threshold, anomaly count, and
  (optionally) ROC-AUC / Precision@n / Precision-Recall-F1 when a
  ground-truth label column is supplied.
- :func:`compare_detection_results` — fit multiple detectors, then
  emit per-detector statistics, pairwise Spearman rank correlation of
  scores, and a "consensus anomaly" set (samples flagged by the majority).

The label-aware metrics come from the vendored PyOD utility
``precision_n_scores`` plus ``sklearn.metrics`` for ROC-AUC / AP / F1.
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
    format_notes,
    is_transductive,
    prepare_feature_matrix,
    score_with_detector,
    scores_summary,
)
from agent_app.tools.outlier_detection_scripts.pyod.utils._quality_metrics import (
    label_metrics as _label_metrics,
)
from agent_app.tools.outlier_detection_scripts.pyod.utils.data import evaluate_print
from agent_app.tools.outlier_detection_scripts.pyod.utils.utility import (
    precision_n_scores,
)

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------

def _extract_labels(
    df: pd.DataFrame,
    label_column: Optional[str],
) -> Optional[np.ndarray]:
    """Return a 1-D int ndarray of ground-truth labels, or None."""
    if not label_column:
        return None
    if label_column not in df.columns:
        raise ValueError(
            "label_column %r not found in df.columns=%r"
            % (label_column, list(df.columns)))
    raw = pd.to_numeric(df[label_column], errors="coerce")
    valid = raw.dropna()
    if valid.empty:
        return None
    # Coerce to {0, 1}: anything truthy/non-zero becomes 1.
    y = (raw.fillna(0) != 0).astype(int).to_numpy()
    return y


def _safe_roc_auc(y_true: np.ndarray, scores: np.ndarray) -> Optional[float]:
    if y_true is None or len(y_true) == 0:
        return None
    if np.unique(y_true).size < 2:
        return None
    if np.unique(scores).size < 2:
        return None
    try:
        from sklearn.metrics import roc_auc_score
        return float(roc_auc_score(y_true, scores))
    except Exception as exc:
        logger.debug("roc_auc_score failed: %s", exc)
        return None


def _safe_precision_at_n(y_true: np.ndarray, scores: np.ndarray) -> Optional[float]:
    if y_true is None or len(y_true) == 0:
        return None
    if np.unique(y_true).size < 2:
        return None
    try:
        return float(precision_n_scores(y_true, scores))
    except Exception as exc:
        logger.debug("precision_n_scores failed: %s", exc)
        return None


def _spearman(a: np.ndarray, b: np.ndarray) -> Optional[float]:
    """Spearman rank correlation, NaN-safe."""
    if len(a) != len(b) or len(a) < 2:
        return None
    ra = _rankdata(a)
    rb = _rankdata(b)
    ra = ra - ra.mean()
    rb = rb - rb.mean()
    denom = np.sqrt((ra * ra).sum() * (rb * rb).sum())
    if denom == 0:
        return None
    return float((ra * rb).sum() / denom)


def _rankdata(x: np.ndarray) -> np.ndarray:
    """Average-rank implementation (no scipy dependency)."""
    x = np.asarray(x, dtype=float)
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), dtype=float)
    sx = x[order]
    i = 0
    while i < len(x):
        j = i + 1
        while j < len(x) and sx[j] == sx[i]:
            j += 1
        avg_rank = 0.5 * (i + j - 1) + 1.0  # 1-indexed average rank
        ranks[order[i:j]] = avg_rank
        i = j
    return ranks


# ----------------------------------------------------------------------
# Tools
# ----------------------------------------------------------------------

@tool("evaluate_detection")
@tool_guard("evaluate_detection")
def evaluate_detection(
    detector_name: str,
    runtime: ToolRuntime,
    label_column: Optional[str] = None,
    contamination: float = 0.1,
) -> Dict[str, Any]:
    """运行单个检测器并评估结果，可选地与 ground-truth 标签对比。

    总是返回：分数分布、阈值、异常数量。当 ``label_column`` 提供且
    该列包含至少两类时，额外计算 ROC-AUC、Precision@n、Precision/Recall/
    F1、Average Precision（通过 vendored PyOD ``evaluate_print`` 同时打印
    日志）。

    Parameters
    ----------
    detector_name : str
        检测器名称。
    label_column : str, optional
        DataFrame 中存储 0/1 ground-truth 标签的列名。任何非零值视为
        异常（=1）。
    contamination : float, default 0.1
        异常比例。

    Returns
    -------
    Dict[str, Any]
        ``metrics`` 中包含 ``roc_auc``、``precision_at_n``、
        ``precision``/``recall``/``f1``/``average_precision``
        （仅当有有效标签时）；``scores_summary`` 为分数统计。
    """
    ctx = runtime.context
    df: pd.DataFrame = ctx.df
    X, info = prepare_feature_matrix(runtime)

    detector = build_detector_by_name(
        detector_name,
        contamination=contamination,
    )
    detector.fit(X)

    scores, lbls, th, supports_ = score_with_detector(
        detector, X, detector_name)
    summary_stats = scores_summary(scores, threshold=th, top_n=10)

    y = _extract_labels(df, label_column)
    metrics: Dict[str, Any] = {}
    notes: List[str] = []
    if y is None:
        notes.append(
            "未提供有效 label_column（=%r）：跳过 ROC-AUC / Precision@n / F1。"
            % label_column)
    else:
        try:
            evaluate_print(detector_name, y, scores)
        except Exception as exc:  # pragma: no cover - logging only
            logger.debug("evaluate_print failed: %s", exc)
        metrics["roc_auc"] = _safe_roc_auc(y, scores)
        metrics["precision_at_n"] = _safe_precision_at_n(y, scores)
        try:
            metrics.update(_label_metrics(y, lbls, scores))
        except Exception as exc:
            logger.debug("label_metrics failed: %s", exc)
        metrics["n_labeled_anomalies"] = int((y > 0).sum())
        metrics["n_labeled_inliers"] = int((y == 0).sum())

    if not supports_:
        notes.append(
            "%s 是 transductive 检测器：supports_out_of_sample=false。"
            % detector_name)

    return {
        "task_type": "anomaly_detection",
        "tool_name": "evaluate_detection",
        "detector_name": detector_name,
        "summary": (
            "%s 评估完成：%d 个样本，%d 个被判为异常。%s"
            % (detector_name, X.shape[0],
               int((lbls > 0).sum()) if lbls.size else 0,
               ("ROC-AUC=%.4f" % metrics["roc_auc"]) if metrics.get("roc_auc") is not None else "")
        ),
        "n_samples": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "threshold": th,
        "supports_out_of_sample": supports_,
        "scores_summary": summary_stats,
        "metrics": metrics,
        "label_column": label_column,
        "notes": format_notes(info, notes),
    }


@tool("compare_detection_results")
@tool_guard("compare_detection_results")
def compare_detection_results(
    detector_names: List[str],
    runtime: ToolRuntime,
    contamination: float = 0.1,
    label_column: Optional[str] = None,
) -> Dict[str, Any]:
    """横向对比多个检测器在**同一份数据**上的表现。

    返回每个检测器的分数统计、两两 Spearman rank 相关，以及「共识异常」
    集合（被多数检测器判为异常的样本）。当提供 ``label_column`` 时，
    额外给出每个检测器的 ROC-AUC / Precision@n / Precision-Recall-F1。

    Parameters
    ----------
    detector_names : List[str]
        参与对比的检测器名称，至少 2 个。
    contamination : float, default 0.1
        异常比例（所有检测器共用，保证 threshold 口径一致）。
    label_column : str, optional
        ground-truth 标签列名。

    Returns
    -------
    Dict[str, Any]
        ``per_detector`` 为逐检测器统计；``pairwise_spearman`` 为方阵；
        ``consensus_anomalies`` 为多数投票命中的样本索引列表。
    """
    if not detector_names or len(detector_names) < 2:
        return {
            "task_type": "anomaly_detection",
            "tool_name": "compare_detection_results",
            "summary": "compare_detection_results 至少需要 2 个检测器。",
            "per_detector": [],
            "notes": ["请提供至少 2 个 detector_name。"],
        }

    ctx = runtime.context
    df: pd.DataFrame = ctx.df
    X, info = prepare_feature_matrix(runtime)

    y = _extract_labels(df, label_column)

    per_detector: List[Dict[str, Any]] = []
    score_matrix: Dict[str, np.ndarray] = {}
    label_matrix: Dict[str, np.ndarray] = {}
    notes: List[str] = []

    for name in detector_names:
        try:
            detector = build_detector_by_name(
                name, contamination=contamination)
            detector.fit(X)
            scores, lbls, th, supports_ = score_with_detector(
                detector, X, name)
        except Exception as exc:
            per_detector.append({
                "detector_name": name,
                "error": "%s: %s" % (type(exc).__name__, exc),
            })
            notes.append("%s 构建或拟合失败：%s" % (name, exc))
            continue

        score_matrix[name] = scores
        label_matrix[name] = lbls

        entry: Dict[str, Any] = {
            "detector_name": name,
            "threshold": th,
            "supports_out_of_sample": supports_,
            "transductive": is_transductive(name),
            "scores_summary": scores_summary(scores, threshold=th, top_n=10),
            "n_anomalies": int((lbls > 0).sum()) if lbls.size else 0,
        }
        if y is not None:
            entry["roc_auc"] = _safe_roc_auc(y, scores)
            entry["precision_at_n"] = _safe_precision_at_n(y, scores)
            try:
                entry.update(_label_metrics(y, lbls, scores))
            except Exception as exc:
                logger.debug("label_metrics failed for %s: %s", name, exc)
        per_detector.append(entry)
        if not supports_:
            notes.append(
                "%s 是 transductive 检测器：分数取自 decision_scores_。"
                % name)

    # Pairwise Spearman on score vectors.
    pairwise: Dict[str, Dict[str, Optional[float]]] = {}
    common_index = None
    for sc in score_matrix.values():
        mask = np.isfinite(sc)
        common_index = mask if common_index is None else (common_index & mask)
    if common_index is None:
        common_index = np.ones(X.shape[0], dtype=bool)

    successful = [n for n in detector_names if n in score_matrix]
    for a in successful:
        pairwise[a] = {}
        for b in successful:
            if a == b:
                pairwise[a][b] = 1.0
                continue
            sa = score_matrix[a][common_index]
            sb = score_matrix[b][common_index]
            pairwise[a][b] = _spearman(sa, sb)

    # Consensus anomalies: majority vote on labels among successful detectors.
    consensus: List[int] = []
    if successful:
        stacked = np.vstack([
            (label_matrix[n] > 0).astype(int) for n in successful
        ])
        votes = stacked.sum(axis=0)
        majority = max(1, len(successful) // 2 + 1)
        consensus = [int(i) for i in np.nonzero(votes >= majority)[0]]

    return {
        "task_type": "anomaly_detection",
        "tool_name": "compare_detection_results",
        "summary": (
            "对比了 %d 个检测器，共识异常 %d 个（多数投票阈值 %d/%d）。"
            % (len(successful), len(consensus),
               max(1, len(successful) // 2 + 1), len(successful))
        ),
        "n_samples": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "contamination": contamination,
        "label_column": label_column,
        "per_detector": per_detector,
        "pairwise_spearman": pairwise,
        "consensus_anomalies": consensus,
        "n_consensus": len(consensus),
        "notes": format_notes(info, notes),
    }


TOOLS = [
    evaluate_detection,
    compare_detection_results,
]
