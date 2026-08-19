"""Ensemble / score-combination tools for PyOD detection.

Two complementary capabilities live here:

- :func:`combine_detector_scores` — run N detectors on the same data,
  then fuse their score vectors using one of the strategies from
  ``pyod.models.combination`` (``average`` / ``maximization`` /
  ``median`` / ``majority_vote`` / ``aom`` / ``moa``). The output is a
  single consensus score per sample plus per-detector diagnostics.
- :func:`train_ensemble_detector` — fit a *single* ensemble estimator
  (``SUOD`` / ``FeatureBagging`` / ``LSCP`` / ``XGBOD``) and persist it
  under the same ``(thread_id, file_path)`` layout as the other tools.

The first tool favours flexibility (combine arbitrary pre-fit scores);
the second favours production use (one saved ensemble callable later).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from langchain.tools import ToolRuntime, tool

from agent_app.tools._tool_guard import tool_guard
from agent_app.tools.anomaly_detection_tools._result_limits import limit_anomaly_result
from agent_app.tools.anomaly_detection_tools._common import (
    auto_save_name,
    build_detector_by_name,
    decision_scores_,
    ensure_dir,
    format_notes,
    is_transductive,
    labels_,
    minmax_scale,
    prepare_feature_matrix,
    resolve_model_path,
    score_with_detector,
    scores_summary,
    threshold_,
    top_anomaly_rows,
)
from agent_app.tools.outlier_detection_scripts.pyod.models import combination as combo
from agent_app.tools.outlier_detection_scripts.pyod.utils import persistence

logger = logging.getLogger(__name__)


# Ensemble estimators that ship as single PyOD models. ``XGBOD`` is
# semi-supervised and will raise if no labels are provided.
_ENSEMBLE_DETECTORS = {"SUOD", "FeatureBagging", "LSCP", "XGBOD"}


# Valid combination strategies. ``majority_vote`` works on the label
# matrix (not scores) and is therefore handled inline in the tool body;
# the rest are dispatched through :func:`_combine_scores`.
_SCORE_COMBINATION_METHODS = ("average", "maximization", "median", "aom", "moa")
_ALL_COMBINATION_METHODS = _SCORE_COMBINATION_METHODS + ("majority_vote",)


def _clamp_n_buckets(requested: int, n_estimators: int) -> int:
    """Clamp ``n_buckets`` for AOM/MOA into the valid range ``[2, n_estimators]``.

    The ``combo`` library requires each bucket to contain at least one
    detector, so ``n_buckets`` can never exceed the number of detectors.
    A bucket count of 1 is degenerate (collapses to plain max/mean), so
    the lower bound is 2.
    """
    return max(2, min(int(requested), int(n_estimators)))


def _combine_scores(
    score_matrix: np.ndarray,
    method: str,
    estimator_weights: Optional[List[float]] = None,
    n_buckets: int = 5,
) -> np.ndarray:
    """Dispatch a ``(n_samples, n_detectors)`` score matrix through ``method``.

    For ``aom`` / ``moa`` the ``n_buckets`` argument is **auto-clamped** to
    ``[2, n_detectors]`` so the call never crashes when the caller supplies
    fewer than ``n_buckets`` detectors. Clamping is logged at WARNING level
    so downstream debugging can see when an explicit request was adjusted.
    """
    n_estimators = int(score_matrix.shape[1])

    if method == "average":
        return np.asarray(
            combo.average(score_matrix, estimator_weights=estimator_weights),
            dtype=float).ravel()
    if method == "maximization":
        return np.asarray(combo.maximization(score_matrix), dtype=float).ravel()
    if method == "median":
        return np.asarray(combo.median(score_matrix), dtype=float).ravel()

    if method in ("aom", "moa"):
        clamped = _clamp_n_buckets(n_buckets, n_estimators)
        if clamped != int(n_buckets):
            logger.warning(
                "combine %s: n_buckets=%d 钳位到 %d (n_estimators=%d)",
                method, int(n_buckets), clamped, n_estimators,
            )
        fn = combo.aom if method == "aom" else combo.moa
        return np.asarray(
            fn(score_matrix, n_buckets=clamped),
            dtype=float).ravel()

    raise ValueError(
        "Unknown combination method %r. Available: %s"
        % (method, list(_ALL_COMBINATION_METHODS)))


# ----------------------------------------------------------------------
# Tools
# ----------------------------------------------------------------------

@tool("combine_detector_scores")
@tool_guard("combine_detector_scores")
def combine_detector_scores(
    detector_names: List[str],
    runtime: ToolRuntime,
    method: str = "average",
    contamination: float = 0.1,
    estimator_weights: Optional[List[float]] = None,
    n_buckets: int = 5,
    return_top_n: int = 10,
) -> Dict[str, Any]:
    """运行多个检测器并融合其分数，得到单一共识分数。

    支持的融合策略（来自 ``pyod.models.combination``）：

    - ``"average"``（默认）：算术平均，可选 ``estimator_weights``。
    - ``"maximization"``：取最大值（任意检测器认定的异常即保留）。
    - ``"median"``：中位数，对离群检测器分数稳健。
    - ``"aom"``：Average of Maximum，``n_buckets`` 桶分组后组内取 max，
      再对桶间取平均。当检测器少于 ``n_buckets`` 时自动钳位到
      ``len(detector_names)``。
    - ``"moa"``：Maximization of Average，``n_buckets`` 桶分组后组内取
      mean，再对桶间取 max。同样自动钳位。
    - ``"majority_vote"``：基于每检测器二值标签的多数投票。

    Parameters
    ----------
    detector_names : List[str]
        至少 2 个检测器。
    method : str, default ``"average"``
        融合方法。
    contamination : float, default 0.1
        异常比例（用于推导 consensus 阈值）。
    estimator_weights : List[float], optional
        仅 ``average`` 使用；长度需与 ``detector_names`` 一致。
    n_buckets : int, default 5
        仅 ``aom`` / ``moa`` 使用。AOM/MOA 的桶数，会自动钳位到
        ``[2, len(detector_names)]``。当检测器少于 5 个时无需手调，
        会自动降到检测器数量。``n_buckets == n_estimators`` 时 AOM
        退化为 average、MOA 退化为 maximization，意义不大。
    return_top_n : int, default 10
        返回融合后分数最高的前 N 行。

    Returns
    -------
    Dict[str, Any]
        ``consensus_scores`` 为融合后的分数；``threshold`` 为由
        ``contamination`` 推导的共识阈值；``per_detector`` 含每检测器
        分数统计；``top_anomalies`` 为共识 Top-N 行；``n_buckets_used``
        报告 AOM/MOA 实际使用的桶数（钳位后）。
    """
    if not detector_names or len(detector_names) < 2:
        return {
            "task_type": "anomaly_detection",
            "tool_name": "combine_detector_scores",
            "summary": "combine_detector_scores 至少需要 2 个检测器。",
            "notes": ["请提供至少 2 个 detector_name。"],
        }
    if method not in _ALL_COMBINATION_METHODS:
        return {
            "task_type": "anomaly_detection",
            "tool_name": "combine_detector_scores",
            "summary": "不支持的 method=%r" % method,
            "notes": ["可用方法：%s" % list(_ALL_COMBINATION_METHODS)],
        }
    if estimator_weights is not None and len(estimator_weights) != len(detector_names):
        raise ValueError(
            "estimator_weights 长度 %d 与 detector_names 长度 %d 不一致。"
            % (len(estimator_weights), len(detector_names)))

    ctx = runtime.context
    df: pd.DataFrame = ctx.df
    X, info = prepare_feature_matrix(runtime)

    per_detector: List[Dict[str, Any]] = []
    score_cols: List[np.ndarray] = []
    label_cols: List[np.ndarray] = []
    successful_names: List[str] = []
    notes: List[str] = []

    for name in detector_names:
        try:
            detector = build_detector_by_name(
                name, contamination=contamination)
            detector.fit(X)
            scores, lbls, th, supports_ = score_with_detector(detector, X, name)
        except Exception as exc:
            per_detector.append({
                "detector_name": name,
                "error": "%s: %s" % (type(exc).__name__, exc),
            })
            notes.append("%s 失败：%s" % (name, exc))
            continue

        score_cols.append(minmax_scale(scores))
        label_cols.append(np.asarray(lbls, dtype=int).ravel())
        successful_names.append(name)
        per_detector.append({
            "detector_name": name,
            "threshold": th,
            "supports_out_of_sample": supports_,
            "scores_summary": scores_summary(scores, threshold=th, top_n=10),
            "n_anomalies": int((lbls > 0).sum()) if lbls.size else 0,
            "params": {},
        })
        if not supports_:
            notes.append(
                "%s 是 transductive 检测器：分数取自 decision_scores_。"
                % name)

    if len(successful_names) < 2:
        return {
            "task_type": "anomaly_detection",
            "tool_name": "combine_detector_scores",
            "summary": "成功执行的检测器不足 2 个，无法融合。",
            "per_detector": per_detector,
            "notes": format_notes(info, notes),
        }

    score_matrix = np.column_stack(score_cols)
    label_matrix = np.column_stack(label_cols)

    if method == "majority_vote":
        # Binary majority vote — output is fraction of detectors flagging anomaly.
        consensus = label_matrix.mean(axis=1)
        consensus_threshold = 0.5
        # n_buckets_used = None
    else:
        consensus = _combine_scores(
            score_matrix, method, estimator_weights, n_buckets)
        consensus_threshold = float(np.percentile(
            consensus,
            100.0 * (1.0 - min(max(contamination, 1e-4), 0.5))))
        # n_buckets_used = (
        #     _clamp_n_buckets(n_buckets, len(successful_names))
        #     if method in ("aom", "moa") else None
        # )
    consensus_labels = (consensus > consensus_threshold).astype(int)

    top_rows = top_anomaly_rows(
        df, consensus, consensus_threshold, return_top_n,
        columns=info["used_columns"])
    consensus_summary = scores_summary(
        consensus, threshold=consensus_threshold, top_n=return_top_n)

    return limit_anomaly_result({
        "task_type": "anomaly_detection",
        "tool_name": "combine_detector_scores",
        "summary": (
            "用 %s 融合 %d 个检测器，共识异常 %d 个（阈值=%.4f）。"
            % (method, len(successful_names),
               int((consensus_labels > 0).sum()), consensus_threshold)
        ),
        "method": method,
        "detectors_combined": successful_names,
        "contamination": contamination,
        "threshold": consensus_threshold,
        "consensus_scores": consensus.tolist(),
        "consensus_labels": consensus_labels.tolist(),
        "consensus_summary": consensus_summary,
        "top_anomalies": top_rows,
        "per_detector": per_detector,
        "estimator_weights": estimator_weights,
        # "n_buckets_requested": int(n_buckets) if method in ("aom", "moa") else None,
        # "n_buckets_used": n_buckets_used,
        "notes": format_notes(info, notes),
    })


@tool("train_ensemble_detector")
@tool_guard("train_ensemble_detector")
def train_ensemble_detector(
    detector_name: str,
    runtime: ToolRuntime,
    contamination: float = 0.1,
    label_column: Optional[str] = None,
    save_name: Optional[str] = None,
    random_state: Optional[int] = None,
) -> Dict[str, Any]:
    """训练单一 PyOD 集成检测器（``SUOD``/``FeatureBagging``/``LSCP``/``XGBOD``）。

    与 :func:`combine_detector_scores` 不同：这里只产生**一个**模型对象，
    内部自动并行/特征装袋/局部选择，适合保存后反复使用。

    Parameters
    ----------
    detector_name : str
        集成检测器名称，必须在
        ``{"SUOD", "FeatureBagging", "LSCP", "XGBOD"}`` 中。
        ``XGBOD`` 需要 ``label_column``（半监督）。
    contamination : float, default 0.1
        异常比例。
    label_column : str, optional
        仅 ``XGBOD`` 需要；提供 0/1 标签列。
    save_name : str, optional
        保存名称；不提供时自动生成。
    random_state : int, optional
        随机种子。

    Returns
    -------
    Dict[str, Any]
        与 :func:`detect_with_model` 一致，附带 ``detector_name``。
    """
    if detector_name not in _ENSEMBLE_DETECTORS:
        return {
            "task_type": "anomaly_detection",
            "tool_name": "train_ensemble_detector",
            "summary": "不支持的集成检测器 %r" % detector_name,
            "notes": ["可选：%s" % sorted(_ENSEMBLE_DETECTORS)],
        }

    ctx = runtime.context
    df: pd.DataFrame = ctx.df
    X, info = prepare_feature_matrix(runtime)

    fit_args: List[Any] = [X]
    fit_kwargs: Dict[str, Any] = {}
    if detector_name == "XGBOD":
        if not label_column or label_column not in df.columns:
            raise ValueError(
                "XGBOD 是半监督检测器，必须提供有效的 label_column。")
        raw = pd.to_numeric(df[label_column], errors="coerce").fillna(0)
        y = (raw != 0).astype(int).to_numpy()
        fit_args.append(y)
        notes_extra = ["使用 label_column=%s 提供的 %d 个正样本进行训练。"
                       % (label_column, int((y > 0).sum()))]
    else:
        notes_extra = []

    detector = build_detector_by_name(
        detector_name,
        contamination=contamination, random_state=random_state)
    detector.fit(*fit_args, **fit_kwargs)

    scores = decision_scores_(detector)
    th = threshold_(detector)
    lbls = labels_(detector)
    n_anomalies = int((lbls > 0).sum()) if lbls.size else 0

    if save_name is None:
        save_name = auto_save_name(detector_name)
    model_path = resolve_model_path(save_name, runtime)
    ensure_dir(model_path.parent)

    metadata = {
        "detector_name": detector_name,
        "params": {},
        "contamination": contamination,
        "random_state": random_state,
        "n_samples": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "feature_columns": info["used_columns"],
        "source": info["source"],
        "n_anomalies": n_anomalies,
        "threshold": th,
        "transductive": is_transductive(detector_name),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "label_column": label_column,
        "ensemble": True,
    }
    persistence.save(detector, model_path, metadata=metadata)

    summary_stats = scores_summary(scores, threshold=th, top_n=10)
    return {
        "task_type": "anomaly_detection",
        "tool_name": "train_ensemble_detector",
        "detector_name": detector_name,
        "summary": (
            "已训练集成检测器 %s，识别 %d 个异常，保存至 %s"
            % (detector_name, n_anomalies, model_path.name)
        ),
        "model_path": str(model_path),
        "save_name": Path(model_path).stem,
        "n_samples": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "threshold": th,
        "n_anomalies": n_anomalies,
        "training_scores": summary_stats,
        "metadata": metadata,
        "notes": format_notes(info, notes_extra),
    }


TOOLS = [
    combine_detector_scores,
    train_ensemble_detector,
]
