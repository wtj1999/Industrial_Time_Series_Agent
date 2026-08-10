"""Time-series-specific anomaly detection tools.

These tools shape ``ctx.df[ctx.target_columns]`` into the layout expected
by PyOD's ``ts_*`` detectors (1-D ``(n_timestamps,)`` or 2-D
``(n_timestamps, n_channels)``), fit a time-series detector (or the
:class:`TimeSeriesOD` sliding-window bridge over any tabular detector),
and return per-timestamp scores plus the Top-N anomalous intervals.

Two tools live here:

- :func:`detect_ts_anomalies` — one-shot time-series detection with
  optional persistence.
- :func:`detect_ts_with_forecast` — sliding-window residual detection
  that wraps any tabular detector inside ``TimeSeriesOD`` explicitly,
  exposing the forecast-vs-actual interpretation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from langchain.tools import ToolRuntime, tool

from agent_app.tools._tool_guard import tool_guard
from agent_app.tools.anomaly_detection_tools._common import (
    auto_save_name,
    build_detector_by_name,
    decision_scores_,
    ensure_dir,
    format_notes,
    is_transductive,
    labels_,
    resolve_model_path,
    score_with_detector,
    scores_summary,
    threshold_,
)
from agent_app.tools.outlier_detection_scripts.pyod.utils import persistence

logger = logging.getLogger(__name__)


# Detectors that ship as native PyOD time-series implementations.
_TS_NATIVE = {
    "KShape", "MatrixProfile", "SpectralResidual", "SAND",
    "LSTMAD", "AnomalyTransformer", "TimeSeriesOD",
}


# Detectors whose PyTorch network is defined as a local class inside
# __init__ (e.g., LSTMAD's _Net in ts_lstm.py). pickle cannot serialize
# local classes by qualified name, so persistence.save would raise
# PicklingError. List them here to skip persistence with a clear note
# rather than crashing the whole tool call. The persistence layer also
# has a defensive fallback that catches any we miss.
_UNPERSISTABLE_TS_DETECTORS = {"LSTMAD"}


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------

def _prepare_ts_matrix(runtime, time_column: Optional[str]):
    """Extract a time-series matrix from context.

    Returns ``(X, time_index, info)`` where ``X`` has shape
    ``(n_timestamps,)`` when there is a single channel, or
    ``(n_timestamps, n_channels)`` for multi-channel data. ``time_index``
    is the per-row timestamp/position used to label Top-N anomaly windows
    in the result.
    """
    ctx = runtime.context
    df: pd.DataFrame = ctx.df
    targets: List[str] = list(ctx.target_columns or [])
    features: List[str] = list(getattr(ctx, "feature_columns", None) or [])
    if not targets and not features:
        raise ValueError(
            "No target_columns or feature_columns available in context; "
            "cannot build a time series matrix.")
    candidates = targets if targets else features

    present = [c for c in candidates if c in df.columns]
    skipped_missing = [c for c in candidates if c not in df.columns]
    numeric_cols: List[str] = []
    skipped_non_numeric: List[str] = []
    for c in present:
        as_num = pd.to_numeric(df[c], errors="coerce")
        if as_num.notna().any():
            numeric_cols.append(c)
        else:
            skipped_non_numeric.append(c)
    if not numeric_cols:
        raise ValueError(
            "No numeric columns available in candidates=%r." % (candidates,))

    sub = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
    nan_count = int(sub.isna().sum().sum())
    if nan_count > 0:
        # Forward-fill then back-fill for time series (preserves temporal locality).
        sub = sub.ffill().bfill().fillna(0.0)

    arr = sub.to_numpy(dtype=np.float64)
    if arr.shape[1] == 1:
        ts_array = arr[:, 0]
    else:
        ts_array = arr

    time_index = None
    time_column_used: Optional[str] = None
    if time_column and time_column in df.columns:
        time_index = df[time_column].tolist()
        time_column_used = time_column
    else:
        time_index = list(range(arr.shape[0]))

    info = {
        "used_columns": numeric_cols,
        "source": "target" if targets else "feature",
        "skipped_missing": skipped_missing,
        "skipped_non_numeric": skipped_non_numeric,
        "imputed_nan_count": nan_count,
        "n_timestamps": int(arr.shape[0]),
        "n_channels": int(arr.shape[1]),
        "time_column": time_column_used,
    }
    return ts_array, time_index, info


def _build_ts_detector(
    detector_name: str,
    window_size: Optional[int],
    params: Optional[Dict[str, Any]],
    contamination: float,
    random_state: Optional[int] = None,
):
    """Build a time-series detector.

    Falls back to wrapping an arbitrary tabular detector with
    :class:`TimeSeriesOD` when ``detector_name`` is not a native ts_*
    detector.
    """
    name = detector_name
    merged: Dict[str, Any] = dict(params or {})

    if name not in _TS_NATIVE:
        bridge_params: Dict[str, Any] = {"contamination": contamination}
        if window_size is not None:
            bridge_params["window_size"] = window_size
        if merged:
            bridge_params["params"] = merged
        return build_detector_by_name(
            "TimeSeriesOD",
            params={"detector": name, **bridge_params},
            contamination=contamination,
            random_state=random_state,
        )

    if window_size is not None and "window_size" not in merged:
        if name != "SpectralResidual":  # uses score_window instead
            merged["window_size"] = window_size
    return build_detector_by_name(
        name,
        params=merged,
        contamination=contamination,
        random_state=random_state,
    )


def _anomaly_intervals(
    labels: np.ndarray,
    time_index: Optional[List[Any]],
    threshold: Optional[float],
    max_intervals: int = 20,
) -> List[Dict[str, Any]]:
    """Collapse binary per-timestamp labels into contiguous intervals."""
    labels = np.asarray(labels, dtype=int)
    if labels.size == 0:
        return []
    flag = labels > 0
    if not flag.any():
        return []
    diff = np.diff(flag.astype(int), prepend=0, append=0)
    starts = np.nonzero(diff == 1)[0]
    ends = np.nonzero(diff == -1)[0]
    intervals: List[Dict[str, Any]] = []
    for s, e in zip(starts, ends):
        if time_index is not None:
            t_start = time_index[s]
            t_end = time_index[e - 1]
        else:
            t_start = int(s)
            t_end = int(e - 1)
        intervals.append({
            "start_index": int(s),
            "end_index": int(e - 1),
            "length": int(e - s),
            "time_start": t_start,
            "time_end": t_end,
        })
        if len(intervals) >= max_intervals:
            break
    return intervals


def _top_ts_anomalies(
    scores: np.ndarray,
    time_index: Optional[List[Any]],
    threshold: Optional[float],
    top_n: int,
) -> List[Dict[str, Any]]:
    """Return the top-N highest-scoring timestamps with context."""
    scores = np.asarray(scores, dtype=float).ravel()
    n = min(int(top_n), len(scores)) if top_n else 0
    if n <= 0:
        return []
    finite = np.isfinite(scores)
    valid_positions = np.nonzero(finite)[0]
    valid_scores = scores[finite]
    if valid_scores.size == 0:
        return []
    order = np.argsort(valid_scores)[::-1][:n]
    picked = valid_positions[order]
    rows: List[Dict[str, Any]] = []
    for pos in picked:
        item: Dict[str, Any] = {
            "timestamp_index": int(pos),
            "score": float(scores[pos]),
            "time": time_index[pos] if time_index is not None else int(pos),
        }
        if threshold is not None:
            item["is_anomaly"] = bool(scores[pos] > threshold)
        rows.append(item)
    return rows


def _format_ts_notes(info: Dict[str, Any], extra: Optional[List[str]] = None) -> List[str]:
    notes: List[str] = []
    if info.get("skipped_missing"):
        notes.append(
            "target_columns 中缺失的列：%s"
            % ", ".join(info["skipped_missing"]))
    if info.get("skipped_non_numeric"):
        notes.append(
            "跳过 %d 个非数值列：%s"
            % (len(info["skipped_non_numeric"]),
               ", ".join(map(str, info["skipped_non_numeric"]))))
    if info.get("imputed_nan_count"):
        notes.append(
            "用 ffill/bfill 填充了 %d 个 NaN 值（时序优先保留时序连续性）。"
            % info["imputed_nan_count"])
    if info.get("source") == "feature":
        notes.append("target_columns 为空，退回到 feature_columns 作为时序输入。")
    if extra:
        notes.extend(extra)
    return notes


# ----------------------------------------------------------------------
# Tools
# ----------------------------------------------------------------------

@tool("detect_ts_anomalies")
@tool_guard("detect_ts_anomalies")
def detect_ts_anomalies(
    runtime: ToolRuntime,
    detector_name: str = "KShape",
    window_size: Optional[int] = None,
    contamination: float = 0.1,
    time_column: Optional[str] = None,
    return_top_n: int = 10,
    save_name: Optional[str] = None,
    random_state: Optional[int] = None,
) -> Dict[str, Any]:
    """时序异常检测专用工具。

    将 ``ctx.df[ctx.target_columns]`` 整形为 ``(n_timestamps,)`` 或
    ``(n_timestamps, n_channels)``，调用 PyOD 的 ``ts_*`` 原生检测器
    （如 ``KShape``、``MatrixProfile``、``SpectralResidual``、``SAND``、
    ``LSTMAD``、``AnomalyTransformer``）或 :class:`TimeSeriesOD` 滑窗
    桥接（可包裹任意表格检测器，如 ``"IForest"``）。

    返回逐时间戳的异常分数、Top-N 异常时间点，以及将连续异常合并后
    的「异常区间」列表（便于在仪表盘上高亮显示）。当提供 ``save_name``
    时，模型会持久化到当前作用域。

    Parameters
    ----------
    detector_name : str, default ``"KShape"``
        时序检测器名称，或任意表格检测器名称（自动通过 TimeSeriesOD 桥接）。
    window_size : int, optional
        滑窗/子序列长度。未提供时使用检测器默认值。
    contamination : float, default 0.1
        异常比例，影响 ``threshold_``。
    time_column : str, optional
        用作时间轴的列名（仅用于在结果中标注异常发生时间，不参与建模）。
    return_top_n : int, default 10
        返回分数最高的前 N 个时间点。
    save_name : str, optional
        提供时把模型保存到当前 ``(thread_id, file_path)`` 作用域。
    random_state : int, optional
        随机种子。

    Returns
    -------
    Dict[str, Any]
        ``scores`` 为逐时间戳分数列表；``labels`` 为 0/1 列表；
        ``anomaly_intervals`` 为连续异常区间；``top_anomalies`` 为 Top-N。
    """
    X, time_index, info = _prepare_ts_matrix(runtime, time_column)

    detector = _build_ts_detector(
        detector_name, window_size, None, contamination,
        random_state=random_state)
    detector.fit(X)

    scores, lbls, th, supports_ = score_with_detector(
        detector, X, detector_name)
    summary_stats = scores_summary(scores, threshold=th, top_n=return_top_n)
    intervals = _anomaly_intervals(lbls, time_index, th)
    top_rows = _top_ts_anomalies(scores, time_index, th, return_top_n)

    notes: List[str] = []
    if detector_name not in _TS_NATIVE:
        notes.append(
            "%s 不是原生时序检测器，已用 TimeSeriesOD 滑窗桥接（window=%r）。"
            % (detector_name,
               getattr(detector, "window_size", window_size)))
    if is_transductive(detector_name):
        notes.append(
            "%s 是 transductive 检测器：supports_out_of_sample=false。"
            % detector_name)
    elif not supports_:
        notes.append("supports_out_of_sample: false")

    model_path = None
    skip_save_reason: Optional[str] = None
    if save_name:
        if detector_name in _UNPERSISTABLE_TS_DETECTORS:
            # 前置拦截:已知不可 pickle 的检测器(如 LSTMAD,其 _Net 类
            # 定义在 _LSTMModel.__init__ 作用域内),直接跳过 save,
            # 避免触发 PicklingError 让整个 tool 调用失败。
            skip_save_reason = (
                "%s 的神经网络类定义在 __init__ 作用域内,pickle 无法"
                "序列化,已跳过持久化。如需复用,请在推理时重新 fit。"
                % detector_name
            )
            logger.warning(skip_save_reason)
        else:
            if save_name is None:
                save_name = auto_save_name(detector_name)
            model_path = resolve_model_path(save_name, runtime)
            ensure_dir(model_path.parent)
            metadata = {
                "detector_name": detector_name,
                "params": {},
                "contamination": contamination,
                "random_state": random_state,
                "window_size": getattr(detector, "window_size", window_size),
                "n_timestamps": info["n_timestamps"],
                "n_channels": info["n_channels"],
                "feature_columns": info["used_columns"],
                "threshold": th,
                "transductive": is_transductive(detector_name),
                "mode": "time_series",
            }
            persistence.save(detector, model_path, metadata=metadata)

    if skip_save_reason:
        notes.append(skip_save_reason)

    n_anom = int((lbls > 0).sum()) if lbls.size else 0
    return {
        "task_type": "anomaly_detection",
        "tool_name": "detect_ts_anomalies",
        "detector_name": detector_name,
        "summary": (
            "%s 时序检测完成：%d 个时间戳，%d 个被判为异常，"
            "形成 %d 个连续异常区间。"
            % (detector_name, info["n_timestamps"], n_anom, len(intervals))
        ),
        "n_timestamps": info["n_timestamps"],
        "n_channels": info["n_channels"],
        "window_size": getattr(detector, "window_size", window_size),
        "threshold": th,
        "supports_out_of_sample": supports_,
        "scores": scores.tolist(),
        "labels": lbls.tolist() if lbls.size else [],
        "scores_summary": summary_stats,
        "anomaly_intervals": intervals,
        "top_anomalies": top_rows,
        "time_column": info["time_column"],
        "feature_columns": info["used_columns"],
        "model_path": str(model_path) if model_path else None,
        "save_name": save_name if model_path else None,
        "notes": _format_ts_notes(info, notes),
    }


@tool("detect_ts_with_forecast")
@tool_guard("detect_ts_with_forecast")
def detect_ts_with_forecast(
    runtime: ToolRuntime,
    base_detector: str = "IForest",
    window_size: int = 24,
    step: int = 1,
    score_aggregation: str = "max",
    contamination: float = 0.1,
    time_column: Optional[str] = None,
    return_top_n: int = 10,
) -> Dict[str, Any]:
    """以「预测窗口 vs 真实窗口」的视角做滑窗异常检测。

    本工具显式调用 ``TimeSeriesOD`` 把任意表格检测器（如 ``IForest``、
    ``LOF``、``OCSVM``）包裹为时序检测器，重点暴露 ``window_size`` /
    ``step`` / ``score_aggregation`` 三个滑窗超参，便于工业场景下
    「以 N 分钟窗口为一个样本」的检测。

    Parameters
    ----------
    base_detector : str, default ``"IForest"``
        被桥接的表格检测器名称。
    window_size : int, default 24
        滑窗长度（时间步数）。
    step : int, default 1
        滑窗步长。
    score_aggregation : str, default ``"max"``
        窗口内分数聚合方式，常见取值：``"max"``、``"mean"``、
        ``"p95"`` 等（具体可选项取决于 ``TimeSeriesOD`` 实现）。
    contamination : float, default 0.1
        异常比例。
    time_column : str, optional
        用于在结果中标注时间戳的列名。
    return_top_n : int, default 10
        返回分数最高的前 N 个时间点。

    Returns
    -------
    Dict[str, Any]
        与 :func:`detect_ts_anomalies` 类似，额外携带滑窗参数与
        ``base_detector`` 字段。
    """
    if window_size <= 0:
        raise ValueError("window_size 必须为正整数。")
    if step <= 0:
        raise ValueError("step 必须为正整数。")

    X, time_index, info = _prepare_ts_matrix(runtime, time_column)

    bridge_params: Dict[str, Any] = {
        "contamination": contamination,
        "window_size": window_size,
        "step": step,
        "score_aggregation": score_aggregation,
    }

    detector = build_detector_by_name(
        "TimeSeriesOD",
        params={"detector": base_detector, **bridge_params},
        contamination=contamination,
    )
    detector.fit(X)

    scores, lbls, th, supports_ = score_with_detector(
        detector, X, "TimeSeriesOD")
    intervals = _anomaly_intervals(lbls, time_index, th)
    top_rows = _top_ts_anomalies(scores, time_index, th, return_top_n)
    summary_stats = scores_summary(scores, threshold=th, top_n=return_top_n)

    notes: List[str] = [
        "base_detector=%s，滑窗窗口=%d，步长=%d，聚合=%s。"
        % (base_detector, window_size, step, score_aggregation),
    ]
    if not supports_:
        notes.append("supports_out_of_sample: false")

    n_anom = int((lbls > 0).sum()) if lbls.size else 0
    return {
        "task_type": "anomaly_detection",
        "tool_name": "detect_ts_with_forecast",
        "detector_name": "TimeSeriesOD(%s)" % base_detector,
        "summary": (
            "滑窗检测完成：%d 个时间戳，%d 个异常，%d 个连续区间。"
            % (info["n_timestamps"], n_anom, len(intervals))
        ),
        "base_detector": base_detector,
        "window_size": window_size,
        "step": step,
        "score_aggregation": score_aggregation,
        "threshold": th,
        "supports_out_of_sample": supports_,
        "scores": scores.tolist(),
        "labels": lbls.tolist() if lbls.size else [],
        "scores_summary": summary_stats,
        "anomaly_intervals": intervals,
        "top_anomalies": top_rows,
        "time_column": info["time_column"],
        "feature_columns": info["used_columns"],
        "notes": _format_ts_notes(info, notes),
    }


TOOLS = [
    detect_ts_anomalies,
    detect_ts_with_forecast,
]
