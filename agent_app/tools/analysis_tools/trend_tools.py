"""Trend-analysis tools.

Three tools that quantify how a numeric column evolves along the row
order (or a supplied time column):

- :func:`analyze_linear_trend` — OLS slope per unit step + R² and a
  monotonic-direction verdict.
- :func:`analyze_mann_kendall_trend` — non-parametric Mann-Kendall trend
  test (robust to outliers and non-normal residuals). Reports S statistic,
  Kendall's tau, z-score and two-sided p-value, plus a Sen's slope.
- :func:`analyze_rolling_trend` — sliding-window slopes to surface
  acceleration / deceleration in the trend.

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
from scipy import stats as sp_stats

from agent_app.tools._tool_guard import tool_guard
from agent_app.tools.analysis_tools._common import (
    format_notes,
    get_df,
    json_safe,
    linear_slope,
    make_envelope,
    numeric_series,
    resolve_columns,
    resolve_time_column,
    round_float,
    select_numeric_columns,
)

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Tools
# ----------------------------------------------------------------------

@tool("analyze_linear_trend")
@tool_guard("analyze_linear_trend")
def analyze_linear_trend(
    runtime: ToolRuntime,
    columns: Optional[List[str]] = None,
    use: str = "target",
    time_column: Optional[str] = None,
    robust: bool = False,
) -> Dict[str, Any]:
    """对每列按行序（或 time_column）做线性回归，给出斜率与方向判定。

    当 ``time_column`` 可解析为 datetime 时，斜率单位为"每秒"，方便
    对齐到真实物理时间；否则以行序为自变量，单位为"每步"。

    Parameters
    ----------
    columns / use : 见 ``analyze_basic_statistics``。
    time_column : str, optional
        时间列名。可解析时以"自起点起的秒数"作为 x 轴。
    robust : bool, default False
        是否使用 Theil-Sen 稳健回归（抗异常值，但开销更大）。

    Returns
    -------
    Dict[str, Any]
        ``metrics.per_column`` 含 slope/intercept/r_squared/n、
        direction ('upward'/'downward'/'stable') 与 slope_unit。
    """
    df = get_df(runtime)
    cols = resolve_columns(runtime, columns=columns, use=use)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="linear_trend",
            summary="无可用数值列。",
            key_findings=["无法计算线性趋势。"],
            metrics={"skipped": {"non_numeric": non_numeric}},
        )

    ts, ts_info = resolve_time_column(df, time_column)
    if ts is not None:
        x = (ts - ts.min()).dt.total_seconds().to_numpy(dtype=float)
        slope_unit = "value/second"
        time_info = ts_info
    else:
        x = np.arange(len(df), dtype=float)
        slope_unit = "value/step"
        time_info = ts_info

    findings: List[str] = []
    per_column: Dict[str, Any] = {}

    for col in numeric_cols:
        s, _ = numeric_series(df, col, dropna=False)
        arr = pd.to_numeric(s, errors="coerce").to_numpy(dtype=float)
        mask = np.isfinite(arr) & np.isfinite(x)
        if mask.sum() < 2:
            per_column[col] = {"n_valid": int(mask.sum()), "note": "样本不足"}
            continue
        xx = x[mask]
        yy = arr[mask]

        if robust:
            try:
                slope, intercept, lo, hi = sp_stats.theilslopes(yy, xx)
                slope = float(slope)
                intercept = float(intercept)
                # R² for the Theil-Sen fit (informational)
                pred = slope * xx + intercept
                ss_res = float(((yy - pred) ** 2).sum())
                ss_tot = float(((yy - yy.mean()) ** 2).sum())
                r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
                extra = {
                    "theilslopes_ci": [round_float(lo), round_float(hi)],
                }
            except Exception as exc:
                logger.debug("theilslopes failed: %s", exc)
                slope_intercept = linear_slope(yy)
                slope, r2 = slope_intercept if slope_intercept else (0.0, 0.0)
                intercept = float(yy.mean() - slope * xx.mean())
                extra = {"note": "Theil-Sen 失败，回退为 OLS。"}
        else:
            slope_intercept = linear_slope_with_intercept(xx, yy)
            slope, intercept, r2 = slope_intercept
            extra = {}

        # Direction verdict: use a tiny relative threshold based on the
        # robust scale of y to avoid flagging noise as trend.
        y_scale = float(np.std(yy)) or 1.0
        rel_slope = abs(slope) * max(xx.max() - xx.min(), 1.0) / max(y_scale, 1e-12)
        if rel_slope < 0.05:
            direction = "stable"
        elif slope > 0:
            direction = "upward"
        else:
            direction = "downward"

        per_column[col] = {
            "n_valid": int(mask.sum()),
            "slope": round_float(slope),
            "intercept": round_float(intercept),
            "r_squared": round_float(r2),
            "direction": direction,
            "slope_unit": slope_unit,
            "total_change": round_float(float(slope * (xx.max() - xx.min()))),
            "robust": bool(robust),
            **extra,
        }
        findings.append(
            "%s：斜率=%+.4g %s，R²=%.3f → %s。"
            % (col, slope, slope_unit, r2, direction))

    notes_extras: List[str] = []
    if non_numeric:
        notes_extras.append("非数值列已跳过：%s" % ", ".join(non_numeric))
    notes_extras.append("时间轴：%s" % (time_info.get("note") or "已使用 time_column。"))

    return make_envelope(
        tool_name="linear_trend",
        summary="完成 %d 列的线性趋势分析（%s）。"
                % (len(numeric_cols), "Theil-Sen 稳健" if robust else "OLS"),
        key_findings=findings,
        metrics={
            "per_column": per_column,
            "time_axis": time_info,
            "slope_unit": slope_unit,
        },
        recommendations=[
            "R² 较低（<0.3）时说明线性模型解释力差，配合 rolling_trend 或 change_point。",
            "稳健回归 (robust=True) 适用于已知存在异常值的场景。",
            "斜率方向与工艺预期不符时，结合 change_point 看是否分段趋势相反。",
        ],
        notes=format_notes({"skipped_non_numeric": non_numeric}, notes_extras),
    )


@tool("analyze_mann_kendall_trend")
@tool_guard("analyze_mann_kendall_trend")
def analyze_mann_kendall_trend(
    runtime: ToolRuntime,
    columns: Optional[List[str]] = None,
    use: str = "target",
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """非参数 Mann-Kendall 趋势检验 + Sen's slope。

    适用于非正态、含异常值的工业时序。基于符号检验判断单调趋势方向。

    Parameters
    ----------
    columns / use : 见 ``analyze_basic_statistics``。
    alpha : float, default 0.05
        拒绝"无趋势"H0 的显著性水平。

    Returns
    -------
    Dict[str, Any]
        ``metrics.per_column`` 含 S、tau、z、p_value、sens_slope、
        sens_intercept、trend_significance。
    """
    df = get_df(runtime)
    cols = resolve_columns(runtime, columns=columns, use=use)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="mann_kendall_trend",
            summary="无可用数值列。",
            key_findings=["无法执行 Mann-Kendall 检验。"],
            metrics={"skipped": {"non_numeric": non_numeric}},
        )

    findings: List[str] = []
    per_column: Dict[str, Any] = {}

    for col in numeric_cols:
        s, _ = numeric_series(df, col, dropna=True)
        if s.size < 4:
            per_column[col] = {"n_valid": int(s.size), "note": "样本不足（需>=4）"}
            continue
        arr = s.to_numpy(dtype=float)
        result = mann_kendall(arr, alpha=alpha)
        per_column[col] = {
            "n_valid": int(arr.size),
            "S": int(result["S"]),
            "tau": round_float(result["tau"]),
            "z": round_float(result["z"]),
            "p_value": round_float(result["p_value"]),
            "sens_slope": round_float(result["sens_slope"]),
            "sens_intercept": round_float(result["sens_intercept"]),
            "trend_significance": result["verdict"],
        }
        findings.append(
            "%s：tau=%+.3f，p=%.4g → %s，Sen 斜率=%+.4g。"
            % (col, result["tau"], result["p_value"],
               result["verdict"], result["sens_slope"]))

    notes_extras: List[str] = []
    if non_numeric:
        notes_extras.append("非数值列已跳过：%s" % ", ".join(non_numeric))

    return make_envelope(
        tool_name="mann_kendall_trend",
        summary="完成 %d 列的 Mann-Kendall 趋势检验（α=%.2f）。"
                % (len(numeric_cols), alpha),
        key_findings=findings,
        metrics={"per_column": per_column, "alpha": alpha},
        recommendations=[
            "p_value<α 且 |tau|>0.3 时趋势可信；仅 p_value 小但 tau 接近 0 时趋势效应微弱。",
            "Sen 斜率抗异常值，可作为线性_trend 的稳健替代。",
            "强季节性数据 MK 检验可能误判，先做季节性分解 (decompose_time_series)。",
        ],
        notes=format_notes({"skipped_non_numeric": non_numeric}, notes_extras),
    )


@tool("analyze_rolling_trend")
@tool_guard("analyze_rolling_trend")
def analyze_rolling_trend(
    runtime: ToolRuntime,
    columns: Optional[List[str]] = None,
    use: str = "target",
    window: int = 30,
    step: int = 1,
    agg: str = "mean",
    detect_acceleration: bool = True,
) -> Dict[str, Any]:
    """滚动窗口统计，刻画趋势的"加速 / 减速"变化。

    对每列：按窗口大小切分时序，每个窗口计算 ``agg``（默认均值），
    输出序列 + 该序列的斜率（即"二阶趋势"，表示加速/减速）。

    Parameters
    ----------
    columns / use : 见 ``analyze_basic_statistics``。
    window : int, default 30
        滚动窗口长度（行数）。
    step : int, default 1
        窗口步长，>1 时做稀疏采样以减小输出体积。
    agg : {"mean","median","std","min","max"}, default "mean"
        每个窗口的聚合函数。
    detect_acceleration : bool, default True
        是否对窗口序列再做一次线性回归以输出趋势的"加速"指标。

    Returns
    -------
    Dict[str, Any]
        ``metrics.per_column`` 含 rolling_values（截断到前 200 个）、
        window_slope、acceleration_label。
    """
    if window < 2:
        window = 2
    if step < 1:
        step = 1
    if agg not in {"mean", "median", "std", "min", "max"}:
        agg = "mean"

    df = get_df(runtime)
    cols = resolve_columns(runtime, columns=columns, use=use)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="rolling_trend",
            summary="无可用数值列。",
            key_findings=["无法计算滚动趋势。"],
            metrics={"skipped": {"non_numeric": non_numeric}},
        )

    findings: List[str] = []
    per_column: Dict[str, Any] = {}

    for col in numeric_cols:
        s, _ = numeric_series(df, col, dropna=True)
        if s.size < window * 2:
            per_column[col] = {"n_valid": int(s.size),
                               "note": "样本不足（需>=2*window=%d）" % (window * 2)}
            continue
        arr = s.to_numpy(dtype=float)

        # Stepwise window aggregation
        starts = np.arange(0, arr.size - window + 1, step)
        windows = np.asarray([arr[i:i + window] for i in starts])
        if agg == "mean":
            rolled = windows.mean(axis=1)
        elif agg == "median":
            rolled = np.median(windows, axis=1)
        elif agg == "std":
            rolled = windows.std(axis=1, ddof=1)
        elif agg == "min":
            rolled = windows.min(axis=1)
        else:
            rolled = windows.max(axis=1)

        result: Dict[str, Any] = {
            "n_valid": int(arr.size),
            "window": int(window),
            "step": int(step),
            "agg": agg,
            "n_windows": int(rolled.size),
            "rolling_first": round_float(float(rolled[0])),
            "rolling_last": round_float(float(rolled[-1])),
            "rolling_min": round_float(float(rolled.min())),
            "rolling_max": round_float(float(rolled.max())),
            "rolling_values": [round_float(float(v)) for v in rolled[:200]],
        }

        if detect_acceleration and rolled.size >= 3:
            sl = linear_slope(rolled)
            if sl is not None:
                slope, r2 = sl
                rel = abs(slope) * (rolled.size - 1) / max(
                    float(np.std(rolled)) or 1.0, 1e-12)
                if rel < 0.05:
                    label = "stable"
                elif slope > 0:
                    label = "increasing"
                else:
                    label = "decreasing"
                result["window_slope"] = round_float(slope)
                result["window_r_squared"] = round_float(r2)
                result["acceleration_label"] = label

        per_column[col] = result
        findings.append(
            "%s：%d 个窗口（%s），首窗口=%.4g → 末窗口=%.4g。"
            % (col, rolled.size, agg, rolled[0], rolled[-1]))

    notes_extras: List[str] = []
    if non_numeric:
        notes_extras.append("非数值列已跳过：%s" % ", ".join(non_numeric))

    return make_envelope(
        tool_name="rolling_trend",
        summary="完成 %d 列的滚动窗口趋势（window=%d, step=%d, agg=%s）。"
                % (len(numeric_cols), window, step, agg),
        key_findings=findings,
        metrics={
            "per_column": per_column,
            "window": int(window),
            "step": int(step),
            "agg": agg,
        },
        recommendations=[
            "rolling_values 起末差异显著但窗口斜率小：说明趋势稳定但水平跳变，配合 change_point。",
            "rolling_std 上升说明波动加剧，可能预示设备劣化或工况切换。",
            "rolling_values 出现周期性 → 与 seasonality 工具交叉验证。",
        ],
        notes=format_notes({"skipped_non_numeric": non_numeric}, notes_extras),
    )


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------

def linear_slope_with_intercept(
    x: np.ndarray,
    y: np.ndarray,
) -> tuple:
    """OLS slope/intercept/R² for aligned finite arrays."""
    n = float(x.size)
    xm = float(x.mean())
    ym = float(y.mean())
    denom = float(((x - xm) ** 2).sum())
    if denom == 0:
        return 0.0, ym, 0.0
    slope = float(((x - xm) * (y - ym)).sum() / denom)
    intercept = ym - slope * xm
    pred = slope * x + intercept
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - ym) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return slope, intercept, r2


def mann_kendall(x: np.ndarray, alpha: float = 0.05) -> Dict[str, Any]:
    """Mann-Kendall trend test + Sen's slope.

    Parameters
    ----------
    x : 1-D finite numeric array.
    alpha : two-sided significance level.

    Returns
    -------
    Dict with S, tau, z, p_value, sens_slope, sens_intercept, verdict.
    """
    n = int(x.size)
    x = np.asarray(x, dtype=float)
    # S statistic
    S = 0
    for i in range(n - 1):
        S += int(np.sign(x[i + 1:] - x[i]).sum())
    # Tie correction
    unique, counts = np.unique(x, return_counts=True)
    tie_term = float((counts * (counts - 1) * (2 * counts + 5)).sum())
    var_S = (n * (n - 1) * (2 * n + 5) - tie_term) / 18.0
    if S > 0:
        z = (S - 1) / math.sqrt(var_S) if var_S > 0 else 0.0
    elif S < 0:
        z = (S + 1) / math.sqrt(var_S) if var_S > 0 else 0.0
    else:
        z = 0.0
    # Two-sided p
    p = 2 * (1 - sp_stats.norm.cdf(abs(z)))
    # Kendall's tau
    nc = n * (n - 1) / 2.0
    tau = S / nc if nc > 0 else 0.0
    # Sen's slope (median of all pairwise slopes)
    slopes = []
    for i in range(n - 1):
        diffs = (x[i + 1:] - x[i]) / (np.arange(i + 2, n + 1) - (i + 1))
        slopes.extend(diffs.tolist())
    sens_slope = float(np.median(slopes)) if slopes else 0.0
    sens_intercept = float(np.median(x) - sens_slope * (n / 2.0))

    if p < alpha and S > 0:
        verdict = "increasing (significant)"
    elif p < alpha and S < 0:
        verdict = "decreasing (significant)"
    else:
        verdict = "no significant trend"
    return {
        "S": S,
        "tau": float(tau),
        "z": float(z),
        "p_value": float(p),
        "sens_slope": sens_slope,
        "sens_intercept": sens_intercept,
        "verdict": verdict,
    }


TOOLS = [
    analyze_linear_trend,
    analyze_mann_kendall_trend,
    analyze_rolling_trend,
]
