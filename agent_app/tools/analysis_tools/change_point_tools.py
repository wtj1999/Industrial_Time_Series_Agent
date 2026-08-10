"""Change-point detection tools.

Three tools that locate structural breaks in a numeric series:

- :func:`detect_mean_change_points` — mean-shift detection via a dynamic-
  programming segmenter (a lightweight PELT-style algorithm in pure numpy,
  since ``ruptures`` may not be installed). Each detected point comes with
  a magnitude, left/right segment statistics and a confidence score.
- :func:`detect_variance_change` — variance-shift detection based on a
  rolling standard-deviation series plus mean-shift detection on it.
- :func:`detect_cusum_change` — classic CUSUM (cumulative sum) detection
  for small persistent shifts, configured via a sensitivity ``threshold``
  and a ``drift`` parameter.

All tools take ``runtime: ToolRuntime`` for context access; every other
parameter is supplied directly by the LLM.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from langchain.tools import ToolRuntime, tool

from agent_app.tools._tool_guard import tool_guard
from agent_app.tools.analysis_tools._common import (
    format_notes,
    get_df,
    make_envelope,
    numeric_series,
    resolve_columns,
    round_float,
    select_numeric_columns,
)

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Tools
# ----------------------------------------------------------------------

@tool("detect_mean_change_points")
@tool_guard("detect_mean_change_points")
def detect_mean_change_points(
    runtime: ToolRuntime,
    columns: Optional[List[str]] = None,
    use: str = "target",
    max_change_points: int = 5,
    min_segment_length: int = 10,
    penalty: str = "auto",
) -> Dict[str, Any]:
    """基于均值漂移的变点检测（动态规划 + 段内方差目标）。

    采用自底向上的二元分割 (binary segmentation)：每次找一个切分点
    使其前后两段均值之差 × 段长 最大，且统计显著。重复至达到
    ``max_change_points`` 或无显著切分。

    Parameters
    ----------
    columns / use : 见 ``analyze_basic_statistics``。
    max_change_points : int, default 5
        每列最多报告的变点数。
    min_segment_length : int, default 10
        最小段长度（过短段不稳定）。
    penalty : {"auto","aic","bic"}, default "auto"
        显著性惩罚策略，``auto`` 用 t-test p-value<0.001 判定。

    Returns
    -------
    Dict[str, Any]
        ``metrics.per_column`` 含 change_points 列表与 segment_stats。
    """
    if max_change_points < 1:
        max_change_points = 1
    if min_segment_length < 2:
        min_segment_length = 2

    df = get_df(runtime)
    cols = resolve_columns(runtime, columns=columns, use=use)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="mean_change_point",
            summary="无可用数值列。",
            key_findings=["无法做均值变点检测。"],
            metrics={"skipped": {"non_numeric": non_numeric}},
        )

    findings: List[str] = []
    per_column: Dict[str, Any] = {}

    for col in numeric_cols:
        s, _ = numeric_series(df, col, dropna=True)
        if s.size < min_segment_length * 3:
            per_column[col] = {"n_valid": int(s.size), "note": "样本不足"}
            continue
        arr = s.to_numpy(dtype=float)

        change_points, segments = binary_segmentation_mean(
            arr,
            max_cp=int(max_change_points),
            min_seg=int(min_segment_length),
            penalty=penalty,
        )

        per_column[col] = {
            "n_valid": int(arr.size),
            "n_change_points": len(change_points),
            "change_points": [
                {
                    "index": int(cp["index"]),
                    "relative_position": round_float(float(cp["index"]) / arr.size),
                    "left_mean": round_float(cp["left_mean"]),
                    "right_mean": round_float(cp["right_mean"]),
                    "delta_mean": round_float(cp["delta_mean"]),
                    "p_value": round_float(cp["p_value"]),
                    "confidence": cp["confidence"],
                }
                for cp in change_points
            ],
            "segments": [
                {
                    "start": int(seg["start"]),
                    "end": int(seg["end"]),
                    "length": int(seg["end"] - seg["start"] + 1),
                    "mean": round_float(seg["mean"]),
                    "std": round_float(seg["std"]),
                }
                for seg in segments
            ],
        }
        if change_points:
            top = change_points[0]
            findings.append(
                "%s：发现 %d 个均值变点，最强在 index=%d（Δ均值=%+.4g）。"
                % (col, len(change_points), top["index"], top["delta_mean"]))
        else:
            findings.append("%s：未发现显著均值变点。" % col)

    notes_extras: List[str] = []
    if non_numeric:
        notes_extras.append("非数值列已跳过：%s" % ", ".join(non_numeric))

    return make_envelope(
        tool_name="mean_change_point",
        summary="完成 %d 列的均值变点检测（max=%d, min_seg=%d）。"
                % (len(numeric_cols), max_change_points, min_segment_length),
        key_findings=findings,
        metrics={
            "per_column": per_column,
            "max_change_points": int(max_change_points),
            "min_segment_length": int(min_segment_length),
            "penalty": penalty,
        },
        recommendations=[
            "变点位置对得上工艺事件（停机、切换）时可信度高。",
            "min_segment_length 过小会引入噪声段，建议 ≥ 工艺最小批次长度。",
            "变点附近数据可单独建模，提升整体预测精度。",
        ],
        notes=format_notes({"skipped_non_numeric": non_numeric}, notes_extras),
    )


@tool("detect_variance_change")
@tool_guard("detect_variance_change")
def detect_variance_change(
    runtime: ToolRuntime,
    columns: Optional[List[str]] = None,
    use: str = "target",
    window: int = 30,
    max_change_points: int = 5,
    ratio_threshold: float = 1.5,
) -> Dict[str, Any]:
    """检测波动幅度（标准差）发生突变的点。

    先计算滚动 std（窗口 ``window``），再对其做均值变点检测，找出
    波动显著放大的区段。常用于"设备状态劣化""工况失稳"的早期预警。

    Parameters
    ----------
    columns / use : 见 ``analyze_basic_statistics``。
    window : int, default 30
        计算 rolling std 的窗口长度（行数）。
    max_change_points : int, default 5
        最多报告的方差变点数。
    ratio_threshold : float, default 1.5
        前后段 std 之比超过该值才视为显著变化。

    Returns
    -------
    Dict[str, Any]
        ``metrics.per_column`` 含 change_points 与 segment_volatilities。
    """
    if window < 5:
        window = 5
    if ratio_threshold < 1.0:
        ratio_threshold = 1.0

    df = get_df(runtime)
    cols = resolve_columns(runtime, columns=columns, use=use)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="variance_change",
            summary="无可用数值列。",
            key_findings=["无法做方差变点检测。"],
            metrics={"skipped": {"non_numeric": non_numeric}},
        )

    findings: List[str] = []
    per_column: Dict[str, Any] = {}

    for col in numeric_cols:
        s, _ = numeric_series(df, col, dropna=True)
        if s.size < window * 3:
            per_column[col] = {"n_valid": int(s.size), "note": "样本不足"}
            continue
        arr = s.to_numpy(dtype=float)

        roll_std = pd.Series(arr).rolling(window=window, min_periods=window).std().to_numpy()
        valid = np.isfinite(roll_std)
        if valid.sum() < window * 2:
            per_column[col] = {"n_valid": int(s.size), "note": "rolling std 全为 NaN"}
            continue
        rstd = roll_std[valid]

        cps, segments = binary_segmentation_mean(
            rstd, max_cp=int(max_change_points),
            min_seg=int(max(window // 2, 5)),
            penalty="auto")

        # Keep only change points whose ratio crosses ratio_threshold
        filtered_cps = []
        for cp in cps:
            ratio = cp["right_mean"] / cp["left_mean"] if cp["left_mean"] > 1e-12 else float("inf")
            if ratio >= ratio_threshold or ratio <= 1.0 / ratio_threshold:
                cp_out = dict(cp)
                cp_out["std_ratio"] = float(ratio)
                cp_out["index"] = int(cp["index"]) + int(window) - 1  # shift to original index
                filtered_cps.append(cp_out)

        per_column[col] = {
            "n_valid": int(arr.size),
            "window": int(window),
            "n_change_points": len(filtered_cps),
            "change_points": [
                {
                    "index": int(cp["index"]),
                    "left_rolling_std": round_float(cp["left_mean"]),
                    "right_rolling_std": round_float(cp["right_mean"]),
                    "std_ratio": round_float(cp["std_ratio"]),
                    "p_value": round_float(cp["p_value"]),
                }
                for cp in filtered_cps
            ],
            "overall_std_first_window": round_float(float(rstd[:window].mean())),
            "overall_std_last_window": round_float(float(rstd[-window:].mean())),
        }
        if filtered_cps:
            top = max(filtered_cps, key=lambda c: abs(math.log(c["std_ratio"])))
            findings.append(
                "%s：发现 %d 个方差变点，最大波动放大在 index=%d（std_ratio=%.2f）。"
                % (col, len(filtered_cps), top["index"], top["std_ratio"]))
        else:
            findings.append("%s：未发现显著方差变化。" % col)

    notes_extras: List[str] = []
    if non_numeric:
        notes_extras.append("非数值列已跳过：%s" % ", ".join(non_numeric))

    return make_envelope(
        tool_name="variance_change",
        summary="完成 %d 列的方差变点检测（window=%d, ratio≥%.2f）。"
                % (len(numeric_cols), window, ratio_threshold),
        key_findings=findings,
        metrics={
            "per_column": per_column,
            "window": int(window),
            "ratio_threshold": float(ratio_threshold),
        },
        recommendations=[
            "std_ratio>2 通常表示设备或工况进入不稳定阶段，建议触发预警。",
            "方差放大先于均值变化时，可作为「早期预警」信号。",
            "window 过大会平滑掉短时波动，建议 ~ 工艺最小批次长度。",
        ],
        notes=format_notes({"skipped_non_numeric": non_numeric}, notes_extras),
    )


@tool("detect_cusum_change")
@tool_guard("detect_cusum_change")
def detect_cusum_change(
    runtime: ToolRuntime,
    columns: Optional[List[str]] = None,
    use: str = "target",
    threshold: float = 5.0,
    drift: float = 0.5,
    min_segment_length: int = 10,
) -> Dict[str, Any]:
    """CUSUM 累积和变点检测，擅长捕捉小幅度持续漂移。

    算法：以全局均值减去 ``drift`` / 加上 ``drift`` 作为参考，累计
    正/负偏差，超过 ``threshold`` 时标记变点。比单点突变检测对小而
    持续的工艺漂移更敏感。

    Parameters
    ----------
    columns / use : 见 ``analyze_basic_statistics``。
    threshold : float, default 5.0
        触发变点的累积量阈值。值越小越敏感、误报越多。
    drift : float, default 0.5
        容忍的微小漂移（"slack"），单位与原序列相同。
    min_segment_length : int, default 10
        相邻变点之间最小间隔。

    Returns
    -------
    Dict[str, Any]
        ``metrics.per_column`` 含 cusum_positive、cusum_negative（截断）、
        change_points 与对应方向。
    """
    if threshold <= 0:
        threshold = 5.0
    if drift < 0:
        drift = 0.0
    if min_segment_length < 2:
        min_segment_length = 2

    df = get_df(runtime)
    cols = resolve_columns(runtime, columns=columns, use=use)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="cusum_change",
            summary="无可用数值列。",
            key_findings=["无法做 CUSUM 检测。"],
            metrics={"skipped": {"non_numeric": non_numeric}},
        )

    findings: List[str] = []
    per_column: Dict[str, Any] = {}

    for col in numeric_cols:
        s, _ = numeric_series(df, col, dropna=True)
        if s.size < min_segment_length * 3:
            per_column[col] = {"n_valid": int(s.size), "note": "样本不足"}
            continue
        arr = s.to_numpy(dtype=float)
        # Scale drift and threshold to the data's std
        scale = float(np.std(arr)) or 1.0
        k = drift * scale
        h = threshold * scale

        mean_target = float(arr.mean())
        sp = np.zeros(arr.size)  # positive cumulative sum
        sn = np.zeros(arr.size)  # negative cumulative sum
        change_points: List[Dict[str, Any]] = []
        last_cp = -min_segment_length

        for i in range(arr.size):
            sp[i] = max(0, sp[i - 1] + (arr[i] - mean_target) - k) if i > 0 else max(0, arr[i] - mean_target - k)
            sn[i] = max(0, sn[i - 1] - (arr[i] - mean_target) - k) if i > 0 else max(0, -arr[i] + mean_target - k)
            if sp[i] > h and (i - last_cp) >= min_segment_length:
                change_points.append({
                    "index": int(i),
                    "direction": "upward",
                    "cusum_value": round_float(float(sp[i])),
                    "local_mean_before": round_float(float(arr[max(0, i - min_segment_length):i].mean())),
                    "local_mean_after": round_float(float(arr[i:i + min_segment_length].mean())),
                })
                last_cp = i
                sp[i] = 0.0
            elif sn[i] > h and (i - last_cp) >= min_segment_length:
                change_points.append({
                    "index": int(i),
                    "direction": "downward",
                    "cusum_value": round_float(float(sn[i])),
                    "local_mean_before": round_float(float(arr[max(0, i - min_segment_length):i].mean())),
                    "local_mean_after": round_float(float(arr[i:i + min_segment_length].mean())),
                })
                last_cp = i
                sn[i] = 0.0

        per_column[col] = {
            "n_valid": int(arr.size),
            "threshold": round_float(float(h)),
            "drift": round_float(float(k)),
            "n_change_points": len(change_points),
            "change_points": change_points[:50],
            "cusum_positive_head": [round_float(float(v)) for v in sp[:200]],
            "cusum_negative_head": [round_float(float(v)) for v in sn[:200]],
        }
        if change_points:
            findings.append(
                "%s：CUSUM 标记 %d 个漂移点（threshold=%.4g, drift=%.4g）。"
                % (col, len(change_points), h, k))
        else:
            findings.append(
                "%s：未触发 CUSUM 变点（threshold=%.4g）。可尝试降低 threshold。" % (col, h))

    notes_extras: List[str] = []
    if non_numeric:
        notes_extras.append("非数值列已跳过：%s" % ", ".join(non_numeric))

    return make_envelope(
        tool_name="cusum_change",
        summary="完成 %d 列的 CUSUM 变点检测（threshold=%.2f, drift=%.2f）。"
                % (len(numeric_cols), threshold, drift),
        key_findings=findings,
        metrics={
            "per_column": per_column,
            "threshold": float(threshold),
            "drift": float(drift),
        },
        recommendations=[
            "CUSUM 适合检测小幅持续漂移；大幅突变用 detect_mean_change_points 更直观。",
            "误报多时增大 threshold 或 drift；漏检时减小 threshold。",
            "direction='upward' 通常表示磨损/劣化；'downward' 可能是冷却/恢复。",
        ],
        notes=format_notes({"skipped_non_numeric": non_numeric}, notes_extras),
    )


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------

def _welch_t_test(a: np.ndarray, b: np.ndarray) -> float:
    """Welch's t-test p-value (two-sided). NaN-safe."""
    from scipy import stats as sp_stats
    if a.size < 2 or b.size < 2:
        return 1.0
    try:
        _, p = sp_stats.ttest_ind(a, b, equal_var=False, nan_policy="omit")
        if not math.isfinite(float(p)):
            return 1.0
        return float(p)
    except Exception:
        return 1.0


def binary_segmentation_mean(
    x: np.ndarray,
    max_cp: int = 5,
    min_seg: int = 10,
    penalty: str = "auto",
    p_threshold: float = 1e-3,
) -> tuple:
    """Binary-segmentation mean-shift change point detection.

    Returns ``(change_points, segments)`` where ``change_points`` is a
    list of dicts with ``index``, ``left_mean``, ``right_mean``,
    ``delta_mean``, ``p_value`` and ``confidence``, sorted by index.
    ``segments`` lists the contiguous runs between change points with
    their start/end/mean/std.

    The candidate at each step is the split that maximises
    ``|mean_left - mean_right| * sqrt(n_left * n_right)`` (a proxy for
    the t-statistic without pooling variance). Significance is then
    re-checked with Welch's t-test.
    """
    x = np.asarray(x, dtype=float)
    n = int(x.size)

    def best_split(arr: np.ndarray, lo: int) -> Optional[Dict[str, Any]]:
        m = arr.size
        if m < 2 * min_seg:
            return None
        # Cumulative sums for O(n) scan
        cumsum = np.concatenate([[0.0], np.cumsum(arr)])
        best: Optional[Dict[str, Any]] = None
        best_score = -1.0
        # Search positions in [min_seg, m - min_seg]
        for k in range(min_seg, m - min_seg + 1):
            left_mean = cumsum[k] / k
            right_mean = (cumsum[m] - cumsum[k]) / (m - k)
            score = abs(left_mean - right_mean) * math.sqrt(k * (m - k))
            if score > best_score:
                best_score = score
                best = {
                    "index": lo + k,           # absolute index in original array
                    "left_start": lo,
                    "left_end": lo + k - 1,
                    "right_start": lo + k,
                    "right_end": lo + m - 1,
                    "left_mean": float(left_mean),
                    "right_mean": float(right_mean),
                    "delta_mean": float(right_mean - left_mean),
                    "score": float(best_score),
                }
        return best

    def evaluate_and_split(lo: int, hi: int, queue: List[Dict[str, Any]]):
        if hi - lo + 1 < 2 * min_seg:
            return
        arr = x[lo:hi + 1]
        candidate = best_split(arr, lo)
        if candidate is None:
            return
        a = arr[:candidate["index"] - lo]
        b = arr[candidate["index"] - lo:]
        p = _welch_t_test(a, b)
        candidate["p_value"] = p
        candidate["confidence"] = (
            "high" if p < 1e-4 else
            "medium" if p < 1e-2 else
            "low" if p < 5e-2 else "none"
        )

        if penalty == "aic":
            accept = (candidate["delta_mean"] != 0 and p < 0.05)
        elif penalty == "bic":
            accept = (p < 0.01)
        else:
            accept = (p < p_threshold)

        if accept:
            queue.append(candidate)
            evaluate_and_split(lo, candidate["index"] - 1, queue)
            evaluate_and_split(candidate["index"], hi, queue)

    raw: List[Dict[str, Any]] = []
    evaluate_and_split(0, n - 1, raw)
    raw.sort(key=lambda c: c["index"])

    # Keep at most max_cp (most significant by p_value)
    if len(raw) > max_cp:
        raw.sort(key=lambda c: c["p_value"])
        raw = raw[:max_cp]
        raw.sort(key=lambda c: c["index"])

    # Build segment summary
    bounds = [0] + [c["index"] for c in raw] + [n]
    segments: List[Dict[str, Any]] = []
    for i in range(len(bounds) - 1):
        s_idx, e_idx = bounds[i], bounds[i + 1] - 1
        seg = x[s_idx:e_idx + 1]
        if seg.size:
            segments.append({
                "start": int(s_idx),
                "end": int(e_idx),
                "mean": float(np.mean(seg)),
                "std": float(np.std(seg, ddof=1)) if seg.size > 1 else 0.0,
            })

    return raw, segments


TOOLS = [
    detect_mean_change_points,
    detect_variance_change,
    detect_cusum_change,
]
