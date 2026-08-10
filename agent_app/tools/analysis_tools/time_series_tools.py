"""Time-series specific analysis tools.

Four tools that exploit temporal ordering of the rows:

- :func:`analyze_autocorrelation` — ACF + PACF for a configurable max lag,
  with confidence bands so the LLM can spot significant lags (e.g.
  AR(p) order candidates).
- :func:`analyze_seasonality` — Lomb-Scargle-style periodogram (via scipy)
  to surface dominant periodicities in seconds, minutes or row-steps.
- :func:`decompose_time_series` — classical additive/multiplicative
  trend + seasonal + residual decomposition (statsmodels STL / classical).
- :func:`analyze_stationarity` — ADF + KPSS tests with verdicts on whether
  differencing / detrending is needed.

All tools take ``runtime: ToolRuntime`` for context access; every other
parameter (time column, period, lag, model) is supplied directly by the LLM.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from langchain.tools import ToolRuntime, tool
from scipy import signal as sp_signal
from scipy import stats as sp_stats

from agent_app.tools._tool_guard import tool_guard
from agent_app.tools.analysis_tools._common import (
    format_notes,
    get_df,
    json_safe,
    make_envelope,
    numeric_series,
    resolve_columns,
    resolve_time_column,
    round_float,
    select_numeric_columns,
)

logger = logging.getLogger(__name__)


# Cap for chart-only arrays emitted by tools that internally compute long
# series (decomposition, control chart, ...). 1500 matches the anomaly-chart
# budget so all charts have a consistent per-tool payload size.
_CHART_MAX_POINTS = 1500


def _downsample_aligned(arrays, max_points):
    """Stride-downsample a list of equal-length 1-D arrays **in lockstep**.

    Returns a list of lists with the same length ordering as ``arrays``.
    Every input array must share its length with the first one. When the
    inputs already fit within ``max_points`` they are returned unchanged
    (as plain Python lists, NaNs coerced to None for JSON safety).

    Used by tools that want to expose their internal series for the
    frontend chart extractor without bloating the ToolMessage payload on
    long inputs.
    """
    if not arrays:
        return []
    n = int(arrays[0].shape[0]) if hasattr(arrays[0], "shape") else len(arrays[0])
    if n == 0:
        return [[] for _ in arrays]
    if n <= max_points:
        return [_to_json_list(a) for a in arrays]
    stride = int(math.ceil(n / max_points))
    out = []
    for a in arrays:
        arr = a[::stride] if hasattr(a, "__getitem__") else a
        out.append(_to_json_list(arr))
    return out


def _to_json_list(arr) -> list:
    """Coerce a numpy / list scalar sequence into a JSON-safe Python list.

    NaN / ±Inf become None so the frontend can render gaps via
    ``connectNulls={false}`` instead of corrupting the chart domain.
    """
    out = []
    for v in arr:
        try:
            f = float(v)
        except (TypeError, ValueError):
            out.append(None)
            continue
        if not math.isfinite(f):
            out.append(None)
        else:
            out.append(f)
    return out


# ----------------------------------------------------------------------
# Tools
# ----------------------------------------------------------------------

@tool("analyze_autocorrelation")
@tool_guard("analyze_autocorrelation")
def analyze_autocorrelation(
    runtime: ToolRuntime,
    columns: Optional[List[str]] = None,
    use: str = "target",
    max_lag: int = 40,
    ci_level: float = 0.95,
) -> Dict[str, Any]:
    """计算 ACF / PACF 与置信带，找出显著滞后期。

    Parameters
    ----------
    columns / use : 见 ``analyze_basic_statistics``。
    max_lag : int, default 40
        最大滞后期（步数）。建议不超过 N/4。
    ci_level : float, default 0.95
        置信带水平（用于标记显著滞后）。

    Returns
    -------
    Dict[str, Any]
        ``metrics.per_column`` 含 acf / pacf / conf_bands /
        significant_lags。
    """
    if max_lag < 1:
        max_lag = 1
    if ci_level <= 0 or ci_level >= 1:
        ci_level = 0.95

    from statsmodels.tsa.stattools import acf, pacf

    df = get_df(runtime)
    cols = resolve_columns(runtime, columns=columns, use=use)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="autocorrelation",
            summary="无可用数值列。",
            key_findings=["无法计算 ACF/PACF。"],
            metrics={"skipped": {"non_numeric": non_numeric}},
        )

    alpha = 1.0 - ci_level
    findings: List[str] = []
    per_column: Dict[str, Any] = {}

    for col in numeric_cols:
        s, _ = numeric_series(df, col, dropna=True)
        if s.size < max_lag * 3:
            per_column[col] = {"n_valid": int(s.size),
                               "note": "样本不足（需>=3*max_lag）"}
            continue
        arr = s.to_numpy(dtype=float)
        effective_lag = min(max_lag, arr.size // 2)

        try:
            acf_vals, acf_ci = acf(arr, nlags=effective_lag, fft=True,
                                   alpha=alpha, missing="drop")
        except Exception as exc:
            logger.debug("acf failed for %s: %s", col, exc)
            acf_vals, acf_ci = np.zeros(effective_lag + 1), None

        try:
            pacf_vals, pacf_ci = pacf(arr, nlags=effective_lag, alpha=alpha,
                                      method="ywm")
        except Exception as exc:
            logger.debug("pacf failed for %s: %s", col, exc)
            pacf_vals, pacf_ci = np.zeros(effective_lag + 1), None

        # Bartlett bands ~ ±1.96/sqrt(N) for acf
        bartlett = sp_stats.norm.ppf(1 - alpha / 2) / math.sqrt(arr.size)

        sig_acf_lags = [int(k) for k in range(1, effective_lag + 1)
                        if abs(float(acf_vals[k])) > bartlett]
        sig_pacf_lags = []
        if pacf_ci is not None:
            sig_pacf_lags = [int(k) for k in range(1, effective_lag + 1)
                             if abs(float(pacf_vals[k])) > bartlett]

        per_column[col] = {
            "n_valid": int(arr.size),
            "max_lag": int(effective_lag),
            "ci_level": float(ci_level),
            "acf": [round_float(float(v)) for v in acf_vals],
            "pacf": [round_float(float(v)) for v in pacf_vals],
            "confidence_band": round_float(float(bartlett)),
            "significant_acf_lags": sig_acf_lags[:50],
            "significant_pacf_lags": sig_pacf_lags[:50],
            "lag_1_autocorr": round_float(float(acf_vals[1] if len(acf_vals) > 1 else 0.0)),
        }
        findings.append(
            "%s：lag-1 自相关=%+.3f，显著 ACF 滞后=%s，显著 PACF 滞后=%s。"
            % (col, float(acf_vals[1] if len(acf_vals) > 1 else 0.0),
               sig_acf_lags[:5], sig_pacf_lags[:5]))

    notes_extras: List[str] = []
    if non_numeric:
        notes_extras.append("非数值列已跳过：%s" % ", ".join(non_numeric))

    return make_envelope(
        tool_name="autocorrelation",
        summary="完成 %d 列的 ACF/PACF 分析（max_lag=%d，CI=%.0f%%）。"
                % (len(numeric_cols), max_lag, ci_level * 100),
        key_findings=findings,
        metrics={
            "per_column": per_column,
            "max_lag": int(max_lag),
            "ci_level": float(ci_level),
        },
        recommendations=[
            "PACF 在 p 阶截断、ACF 拖尾 → AR(p)；反之 → MA(q)。",
            "ACF 缓慢衰减 → 序列非平稳，先做差分 (analyze_stationarity)。",
            "季节性滞后（如 lag=24 小时数据）显著 → 用 decompose_time_series 拆分。",
        ],
        notes=format_notes({"skipped_non_numeric": non_numeric}, notes_extras),
    )


@tool("analyze_seasonality")
@tool_guard("analyze_seasonality")
def analyze_seasonality(
    runtime: ToolRuntime,
    columns: Optional[List[str]] = None,
    use: str = "target",
    time_column: Optional[str] = None,
    sampling_period_hz: Optional[float] = None,
    max_periods: int = 5,
    min_period_length: int = 2,
    detrend: bool = True,
) -> Dict[str, Any]:
    """基于周期图识别数据中的主导周期。

    使用 ``scipy.signal.periodogram``（ Welch 法的简化版）估计功率谱，
    输出 Top-N 主导周期及其相对能量占比。

    Parameters
    ----------
    columns / use : 见 ``analyze_basic_statistics``。
    time_column : str, optional
        若提供且可解析为 datetime，则以采样间隔作为 fs，输出周期单位为秒；
        否则按行序输出"步"。
    sampling_period_hz : float, optional
        显式指定采样频率（Hz）。优先级高于 time_column 推断。
    max_periods : int, default 5
        返回前 N 个最强周期。
    min_period_length : int, default 2
        最小周期长度（步）。小于此值的高频成分忽略。
    detrend : bool, default True
        周期图前是否对序列去线性趋势。

    Returns
    -------
    Dict[str, Any]
        ``metrics.per_column`` 含 dominant_periods、period_powers、
        spectral_entropy。
    """
    df = get_df(runtime)
    cols = resolve_columns(runtime, columns=columns, use=use)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="seasonality",
            summary="无可用数值列。",
            key_findings=["无法做周期性分析。"],
            metrics={"skipped": {"non_numeric": non_numeric}},
        )

    # Resolve fs (sampling frequency)
    fs: Optional[float] = None
    ts, ts_info = resolve_time_column(df, time_column)
    if sampling_period_hz is not None and sampling_period_hz > 0:
        fs = float(sampling_period_hz)
    elif ts is not None and ts.notna().sum() >= 3:
        deltas = (ts - ts.shift(1)).dt.total_seconds().dropna()
        median_dt = deltas.median()
        if median_dt and median_dt > 0:
            fs = 1.0 / float(median_dt)
    period_unit = "seconds" if fs else "steps"

    findings: List[str] = []
    per_column: Dict[str, Any] = {}

    for col in numeric_cols:
        s, _ = numeric_series(df, col, dropna=True)
        if s.size < max(20, min_period_length * 4):
            per_column[col] = {"n_valid": int(s.size), "note": "样本不足"}
            continue
        arr = s.to_numpy(dtype=float)

        if detrend:
            try:
                arr = sp_signal.detrend(arr, type="linear")
            except Exception:
                pass

        n = arr.size
        try:
            freqs, power = sp_signal.periodogram(
                arr, fs=fs if fs else 1.0,
                window="hann", scaling="spectrum")
        except Exception as exc:
            logger.debug("periodogram failed for %s: %s", col, exc)
            per_column[col] = {"note": "周期图计算失败：%s" % exc}
            continue

        # Drop DC component
        if freqs.size:
            mask_dc = freqs > 0
            freqs = freqs[mask_dc]
            power = power[mask_dc]

        if not freqs.size:
            per_column[col] = {"note": "无有效频率成分"}
            continue

        # Convert frequency to period
        periods = 1.0 / freqs
        # Filter out too-short periods
        keep = periods >= min_period_length
        periods = periods[keep]
        power = power[keep]
        if not periods.size:
            per_column[col] = {"note": "未发现满足 min_period_length 的周期"}
            continue

        # Top-N strongest
        order = np.argsort(power)[::-1][:max_periods]
        total_power = float(power.sum()) or 1.0
        dom_periods = []
        for k in order:
            dom_periods.append({
                "period": round_float(float(periods[k])),
                "frequency": round_float(float(freqs[k])),
                "power": round_float(float(power[k])),
                "power_ratio": round_float(float(power[k] / total_power)),
            })

        # Spectral entropy (normalized to [0,1])
        p = power / total_power
        ent = -float(np.sum(p * np.log(p + 1e-12)))
        ent_norm = ent / math.log(p.size) if p.size > 1 else 0.0

        per_column[col] = {
            "n_valid": int(s.size),
            "fs": round_float(fs) if fs else None,
            "period_unit": period_unit,
            "dominant_periods": dom_periods,
            "spectral_entropy": round_float(ent),
            "spectral_entropy_normalized": round_float(ent_norm),
            "detrended": bool(detrend),
        }
        if dom_periods:
            top = dom_periods[0]
            findings.append(
                "%s：最强周期=%.4g %s（占比 %.1f%%），谱熵=%.3f。"
                % (col, top["period"], period_unit,
                   top["power_ratio"] * 100, ent_norm))

    notes_extras: List[str] = []
    if non_numeric:
        notes_extras.append("非数值列已跳过：%s" % ", ".join(non_numeric))
    notes_extras.append("时间轴：%s" % (ts_info.get("note") or "已使用 time_column/采样频率。"))

    return make_envelope(
        tool_name="seasonality",
        summary="完成 %d 列的周期性分析（unit=%s）。"
                % (len(numeric_cols), period_unit),
        key_findings=findings,
        metrics={
            "per_column": per_column,
            "period_unit": period_unit,
            "fs": round_float(fs) if fs else None,
            "max_periods": int(max_periods),
            "time_axis": ts_info,
        },
        recommendations=[
            "spectral_entropy_normalized 接近 1 → 接近白噪声，无明显周期。",
            "强周期（power_ratio>0.2）建议作为 STL/seasonal_decompose 的周期输入。",
            "周期长度对不上工艺常识时检查采样频率（fs）是否正确推断。",
        ],
        notes=format_notes({"skipped_non_numeric": non_numeric}, notes_extras),
    )


@tool("decompose_time_series")
@tool_guard("decompose_time_series")
def decompose_time_series(
    runtime: ToolRuntime,
    columns: Optional[List[str]] = None,
    use: str = "target",
    period: Optional[int] = None,
    model: str = "additive",
    method: str = "stl",
    robust: bool = True,
) -> Dict[str, Any]:
    """时序分解为趋势 / 季节 / 残差三成分。

    Parameters
    ----------
    columns / use : 见 ``analyze_basic_statistics``。
    period : int, optional
        季节周期（步数）。建议来自 ``analyze_seasonality``。必填时
        需 ≥2；若未提供，尝试用 STL 内部估计或抛错。
    model : {"additive","multiplicative"}, default "additive"
        经典分解时使用加法 / 乘法模型（STL 始终是加法）。
    method : {"stl","classical"}, default "stl"
        STL（推荐，更稳健）或 statsmodels 的 seasonal_decompose。
    robust : bool, default True
        STL 是否启用稳健迭代（抗异常值）。

    Returns
    -------
    Dict[str, Any]
        ``metrics.per_column`` 含 trend/seasonal/residual 的首尾片段
        与统计量；``strength_seasonal`` / ``strength_trend``。
    """
    from statsmodels.tsa.seasonal import STL, seasonal_decompose

    if model not in {"additive", "multiplicative"}:
        model = "additive"
    if method not in {"stl", "classical"}:
        method = "stl"

    df = get_df(runtime)
    cols = resolve_columns(runtime, columns=columns, use=use)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="decomposition",
            summary="无可用数值列。",
            key_findings=["无法做时序分解。"],
            metrics={"skipped": {"non_numeric": non_numeric}},
        )

    findings: List[str] = []
    per_column: Dict[str, Any] = {}

    for col in numeric_cols:
        s_full, _ = numeric_series(df, col, dropna=False)
        s = s_full.dropna()
        if s.size < (period or 0) * 2 + 4 if period else s.size < 20:
            per_column[col] = {"n_valid": int(s.size), "note": "样本不足"}
            continue

        # Reindex to a positional index so statsmodels can handle gaps
        s_idx = pd.Series(s.to_numpy(dtype=float),
                          index=np.arange(s.size))
        try:
            if method == "stl":
                if not period:
                    per_column[col] = {
                        "note": "STL 必须提供 period，请通过 analyze_seasonality 推断。",
                    }
                    continue
                decomp = STL(s_idx, period=int(period), robust=robust).fit()
                trend = np.asarray(decomp.trend)
                seasonal = np.asarray(decomp.seasonal)
                resid = np.asarray(decomp.resid)
            else:
                # classical seasonal_decompose needs an explicit period
                if not period:
                    per_column[col] = {
                        "note": "classical 必须提供 period。",
                    }
                    continue
                if model == "multiplicative" and (s_idx.to_numpy() <= 0).any():
                    per_column[col] = {
                        "note": "multiplicative 模型不允许 ≤0 的值，已跳过。",
                    }
                    continue
                decomp = seasonal_decompose(
                    s_idx, period=int(period), model=model,
                    extrapolate_trend="freq")
                trend = np.asarray(decomp.trend)
                seasonal = np.asarray(decomp.seasonal)
                resid = np.asarray(decomp.resid)
        except Exception as exc:
            logger.warning("decompose failed for %s: %s", col, exc)
            per_column[col] = {"note": "分解失败：%s" % exc}
            continue

        var_total = float(np.nanvar(s.to_numpy(dtype=float))) or 1e-12
        var_resid = float(np.nanvar(np.nan_to_num(resid))) or 1e-12
        var_trend = float(np.nanvar(np.nan_to_num(trend))) or 0.0
        strength_trend = max(0.0, 1.0 - var_resid / max(var_trend + var_resid, 1e-12))
        strength_seasonal = max(0.0, 1.0 - var_resid / max(var_total, 1e-12))

        # Downsample the full observed/trend/seasonal/residual arrays for
        # the frontend 4-panel chart. Capped at _CHART_MAX_POINTS per series
        # so the ToolMessage payload stays bounded even on 10k+ rows; the
        # chart extractor reads these verbatim with no further downsampling.
        obs_full = s.to_numpy(dtype=float)
        chart_series = _downsample_aligned(
            [obs_full, trend, seasonal, resid], _CHART_MAX_POINTS)

        per_column[col] = {
            "n_valid": int(s.size),
            "period": int(period) if period else None,
            "model": model,
            "method": method,
            "trend": {
                "first_5": [round_float(float(v)) for v in trend[:5]],
                "last_5": [round_float(float(v)) for v in trend[-5:]],
                "mean": round_float(float(np.nanmean(trend))),
                "std": round_float(float(np.nanstd(trend))),
            },
            "seasonal": {
                "first_period": [round_float(float(v)) for v in seasonal[:int(period)]]
                if period else [],
                "amplitude": round_float(float(np.nanmax(seasonal) - np.nanmin(seasonal))),
            },
            "residual": {
                "mean": round_float(float(np.nanmean(resid))),
                "std": round_float(float(np.nanstd(resid))),
                "max_abs": round_float(float(np.nanmax(np.abs(resid)))),
            },
            "strength_trend": round_float(float(strength_trend)),
            "strength_seasonal": round_float(float(strength_seasonal)),
            # Visualisation-only fields. The LLM can ignore these; the
            # chart extractor in analysis_agent reads them to render the
            # 4-panel decomposition chart.
            "chart_series": {
                "observed": chart_series[0],
                "trend": chart_series[1],
                "seasonal": chart_series[2],
                "residual": chart_series[3],
                "downsampled": len(obs_full) > _CHART_MAX_POINTS,
                "original_n": int(len(obs_full)),
            },
        }
        findings.append(
            "%s：趋势强度=%.3f，季节强度=%.3f，残差 std=%.4g。"
            % (col, strength_trend, strength_seasonal, float(np.nanstd(resid))))

    notes_extras: List[str] = []
    if non_numeric:
        notes_extras.append("非数值列已跳过：%s" % ", ".join(non_numeric))

    return make_envelope(
        tool_name="decomposition",
        summary="完成 %d 列的时序分解（method=%s, period=%s）。"
                % (len(numeric_cols), method, period),
        key_findings=findings,
        metrics={
            "per_column": per_column,
            "period": period,
            "method": method,
            "model": model,
        },
        recommendations=[
            "strength_trend>0.8 → 序列主要由趋势驱动；<0.2 → 适合平稳化处理。",
            "残差 max_abs 异常大的位置对应原数据中的异常点，可与 outlier_tools 交叉验证。",
            "multiplicative 适合季节幅度随水平增加的情况（如产能翻倍后波动也翻倍）。",
        ],
        notes=format_notes({"skipped_non_numeric": non_numeric}, notes_extras),
    )


@tool("analyze_stationarity")
@tool_guard("analyze_stationarity")
def analyze_stationarity(
    runtime: ToolRuntime,
    columns: Optional[List[str]] = None,
    use: str = "target",
    adf_max_lag: Optional[int] = None,
    kpss_regression: str = "c",
    alpha: float = 0.05,
    difference_order: int = 0,
) -> Dict[str, Any]:
    """平稳性检验：ADF + KPSS（互证）。

    ADF H0=有单位根（非平稳）；KPSS H0=平稳。两检验一致判定时最可信。

    Parameters
    ----------
    columns / use : 见 ``analyze_basic_statistics``。
    adf_max_lag : int, optional
        ADF 检验的最大滞后期，None 时由 statsmodels 自动选择。
    kpss_regression : {"c","ct"}, default "c"
        KPSS 模型：常数 / 常数+趋势。
    alpha : float, default 0.05
        显著性水平。
    difference_order : int, default 0
        检验前做的差分阶数（0=原始序列，1=一阶差分，2=二阶）。

    Returns
    -------
    Dict[str, Any]
        ``metrics.per_column`` 含 adf / kpss / verdict。
    """
    from statsmodels.tsa.stattools import adfuller, kpss

    if alpha <= 0 or alpha >= 1:
        alpha = 0.05
    if difference_order < 0:
        difference_order = 0
    if kpss_regression not in {"c", "ct"}:
        kpss_regression = "c"

    df = get_df(runtime)
    cols = resolve_columns(runtime, columns=columns, use=use)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="stationarity",
            summary="无可用数值列。",
            key_findings=["无法做平稳性检验。"],
            metrics={"skipped": {"non_numeric": non_numeric}},
        )

    findings: List[str] = []
    per_column: Dict[str, Any] = {}

    for col in numeric_cols:
        s, _ = numeric_series(df, col, dropna=True)
        if s.size < 20:
            per_column[col] = {"n_valid": int(s.size), "note": "样本不足"}
            continue
        arr = s.to_numpy(dtype=float)
        for _ in range(difference_order):
            arr = np.diff(arr)
        arr = arr[np.isfinite(arr)]
        if arr.size < 20:
            per_column[col] = {"n_valid": int(arr.size),
                               "note": "差分后样本不足"}
            continue

        adf_block: Dict[str, Any] = {}
        try:
            adf_stat, adf_p, adf_lag, adf_n, adf_crit, _ = adfuller(
                arr, maxlag=adf_max_lag, autolag="AIC" if adf_max_lag is None else None)
            adf_block = {
                "statistic": round_float(float(adf_stat)),
                "p_value": round_float(float(adf_p)),
                "used_lag": int(adf_lag),
                "n_obs": int(adf_n),
                "critical_values": {k: round_float(float(v))
                                    for k, v in adf_crit.items()},
                "reject_unit_root": bool(adf_p < alpha),
            }
        except Exception as exc:
            adf_block = {"error": str(exc)}

        kpss_block: Dict[str, Any] = {}
        try:
            kpss_stat, kpss_p, kpss_lag, kpss_crit = kpss(
                arr, regression=kpss_regression, nlags="auto")
            kpss_block = {
                "statistic": round_float(float(kpss_stat)),
                "p_value": round_float(float(kpss_p)),
                "used_lag": int(kpss_lag),
                "critical_values": {k: round_float(float(v))
                                    for k, v in kpss_crit.items()},
                "reject_stationarity": bool(kpss_p < alpha),
            }
        except Exception as exc:
            kpss_block = {"error": str(exc)}

        # Verdict reconciliation
        adf_stationary = adf_block.get("reject_unit_root", False) if "error" not in adf_block else None
        kpss_stationary = (not kpss_block.get("reject_stationarity", True)) if "error" not in kpss_block else None
        if adf_stationary and kpss_stationary:
            verdict = "stationary"
        elif adf_stationary is False and kpss_stationary is False:
            verdict = "non-stationary (differencing needed)"
        elif adf_stationary is False:
            verdict = "likely non-stationary (ADF rejects stationarity)"
        elif kpss_stationary is False:
            verdict = "likely non-stationary (KPSS rejects stationarity)"
        elif adf_stationary and kpss_stationary is False:
            verdict = "difference-stationary (trend may be present)"
        else:
            verdict = "inconclusive"

        per_column[col] = {
            "n_valid": int(arr.size),
            "difference_order": int(difference_order),
            "adf": adf_block,
            "kpss": kpss_block,
            "verdict": verdict,
        }
        findings.append("%s：%s（d=%d）。" % (col, verdict, difference_order))

    notes_extras: List[str] = []
    if non_numeric:
        notes_extras.append("非数值列已跳过：%s" % ", ".join(non_numeric))

    return make_envelope(
        tool_name="stationarity",
        summary="完成 %d 列的平稳性检验（d=%d，α=%.2f）。"
                % (len(numeric_cols), difference_order, alpha),
        key_findings=findings,
        metrics={
            "per_column": per_column,
            "alpha": alpha,
            "difference_order": difference_order,
        },
        recommendations=[
            "判定为非平稳 → 至少 d=1 差分后再做 ARIMA / 回归。",
            "ADF 与 KPSS 结论冲突 → 多为差分平稳序列，先做一阶差分再检验。",
            "原始序列平稳且季节性强 → 考虑 SARIMA 或先做季节差分。",
        ],
        notes=format_notes({"skipped_non_numeric": non_numeric}, notes_extras),
    )


TOOLS = [
    analyze_autocorrelation,
    analyze_seasonality,
    decompose_time_series,
    analyze_stationarity,
]
