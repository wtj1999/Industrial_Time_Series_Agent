"""Statistical outlier detection tools (univariate & multivariate).

Three complementary tools that don't depend on PyOD (for the lightweight
"just want to know which rows look weird" use case the agent often hits
before deciding to train a full detector):

- :func:`detect_univariate_outliers` — IQR / Z-score / MAD rules applied
  per column, with per-column outlier counts, rates, threshold values
  and a sample of the actual outlier row indices.
- :func:`detect_multivariate_outliers` — Mahalanobis distance (with a
  robust covariance option via sklearn's ``MinCovDet``) plus a χ²
  cut-off; surfaces the top-N most extreme multivariate rows.
- :func:`analyze_extreme_values` — return-period / exceedance analysis:
  per-column p95 / p99 thresholds, count above configurable limits, and
  empirical return levels for 100 / 1000 step horizons.

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
    make_envelope,
    numeric_frame,
    numeric_series,
    resolve_columns,
    round_float,
    select_numeric_columns,
    truncate_list,
)

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Tools
# ----------------------------------------------------------------------

@tool("detect_univariate_outliers")
@tool_guard("detect_univariate_outliers")
def detect_univariate_outliers(
    runtime: ToolRuntime,
    columns: Optional[List[str]] = None,
    use: str = "target",
    method: str = "iqr",
    threshold: Optional[float] = None,
    z_cap: float = 5.0,
    top_n: int = 10,
) -> Dict[str, Any]:
    """对每列做单变量异常值检测（IQR / Z-score / MAD 任选其一）。

    Parameters
    ----------
    columns / use : 见 ``analyze_basic_statistics``。
    method : {"iqr","zscore","mad"}, default "iqr"
        - ``iqr``：< Q1 - 1.5*IQR 或 > Q3 + 1.5*IQR。
        - ``zscore``：|z|>``threshold``（默认 3）。
        - ``mad``：modified z-score = 0.6745*(x-median)/MAD，|z|>``threshold``。
    threshold : float, optional
        zscore/mad 阈值（默认分别为 3.0 和 3.5）。
    z_cap : float, default 5.0
        报告的最大 z-score（截断极值，避免数值爆炸）。
    top_n : int, default 10
        每列返回的最异常前 N 个行索引。

    Returns
    -------
    Dict[str, Any]
        ``metrics.per_column`` 含 count/rate/lower_bound/upper_bound/
        sample_indices。
    """
    if method not in {"iqr", "zscore", "mad"}:
        method = "iqr"
    if method == "iqr":
        k = float(threshold) if threshold is not None else 1.5
    elif method == "zscore":
        k = float(threshold) if threshold is not None else 3.0
    else:
        k = float(threshold) if threshold is not None else 3.5
    if top_n < 0:
        top_n = 0

    df = get_df(runtime)
    cols = resolve_columns(runtime, columns=columns, use=use)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="univariate_outlier",
            summary="无可用数值列。",
            key_findings=["无法做单变量异常值检测。"],
            metrics={"skipped": {"non_numeric": non_numeric}},
        )

    findings: List[str] = []
    per_column: Dict[str, Any] = {}

    for col in numeric_cols:
        s_full, _ = numeric_series(df, col, dropna=False)
        s = s_full.dropna()
        if s.size < 4:
            per_column[col] = {"n_valid": int(s.size), "note": "样本不足"}
            continue
        arr = s.to_numpy(dtype=float)
        n_total = int(arr.size)

        if method == "iqr":
            q1, q3 = np.percentile(arr, [25, 75])
            iqr = q3 - q1
            lower = float(q1 - k * iqr)
            upper = float(q3 + k * iqr)
            mask = (arr < lower) | (arr > upper)
            stat_info = {
                "q1": round_float(float(q1)),
                "q3": round_float(float(q3)),
                "iqr": round_float(float(iqr)),
                "lower_bound": round_float(lower),
                "upper_bound": round_float(upper),
                "k": float(k),
            }
        elif method == "zscore":
            mu = float(arr.mean())
            sd = float(arr.std(ddof=0))
            if sd <= 0:
                per_column[col] = {"n_valid": n_total, "note": "std=0 无法计算 z"}
                continue
            z = np.clip(np.abs((arr - mu) / sd), 0, z_cap)
            mask = z > k
            lower = float(mu - k * sd)
            upper = float(mu + k * sd)
            stat_info = {
                "mean": round_float(mu),
                "std": round_float(sd),
                "lower_bound": round_float(lower),
                "upper_bound": round_float(upper),
                "k": float(k),
            }
        else:  # mad
            median = float(np.median(arr))
            mad = float(np.median(np.abs(arr - median)))
            if mad <= 0:
                per_column[col] = {"n_valid": n_total, "note": "MAD=0 无法计算"}
                continue
            mod_z = np.clip(0.6745 * (arr - median) / mad, -z_cap, z_cap)
            mask = np.abs(mod_z) > k
            stat_info = {
                "median": round_float(median),
                "mad": round_float(mad),
                "k": float(k),
            }

        outlier_idx = np.where(mask)[0]
        # Map back to original df positions (relative to s.dropna())
        outlier_positions = (
            s.index[outlier_idx].tolist() if hasattr(s.index, "tolist") else outlier_idx.tolist()
        )
        # Top-N by extremity
        if method == "iqr":
            score = np.maximum(arr - upper, lower - arr)
        elif method == "zscore":
            score = np.abs((arr - mu) / sd)
        else:
            score = np.abs(mod_z)
        top_order = np.argsort(score)[::-1][:top_n]
        top_samples = []
        for kth in top_order:
            if not mask[kth]:
                continue
            top_samples.append({
                "row_index": int(s.index[kth]) if hasattr(s.index, "__getitem__") else int(kth),
                "value": round_float(float(arr[kth])),
                "score": round_float(float(score[kth])),
            })

        per_column[col] = {
            "n_valid": n_total,
            "method": method,
            **stat_info,
            "outlier_count": int(mask.sum()),
            "outlier_rate": round_float(float(mask.sum()) / n_total),
            "sample_indices": [int(i) for i in outlier_positions[:top_n]],
            "top_outliers": top_samples,
        }
        findings.append(
            "%s：检出 %d 个异常 (%.2f%%, method=%s)。"
            % (col, int(mask.sum()), 100.0 * mask.sum() / n_total, method))

    notes_extras: List[str] = []
    if non_numeric:
        notes_extras.append("非数值列已跳过：%s" % ", ".join(non_numeric))

    return make_envelope(
        tool_name="univariate_outlier",
        summary="完成 %d 列的 %s 单变量异常检测。"
                % (len(numeric_cols), method.upper()),
        key_findings=findings,
        metrics={
            "per_column": per_column,
            "method": method,
        },
        recommendations=[
            "IQR 适合一般场景；MAD 对极端值更稳健；Z-score 仅适用于近似正态分布。",
            "outlier_rate>5% 时检查是否为正常工况（如换班、批次切换）而非真异常。",
            "需多变量联合异常检测时使用 detect_multivariate_outliers。",
        ],
        notes=format_notes({"skipped_non_numeric": non_numeric}, notes_extras),
    )


@tool("detect_multivariate_outliers")
@tool_guard("detect_multivariate_outliers")
def detect_multivariate_outliers(
    runtime: ToolRuntime,
    columns: Optional[List[str]] = None,
    use: str = "any",
    robust: bool = True,
    chi2_alpha: float = 0.01,
    top_n: int = 20,
) -> Dict[str, Any]:
    """基于 Mahalanobis 距离的多变量异常检测。

    使用 sklearn 的 ``EmpiricalCovariance``（MLE）或
    ``MinCovDet``（稳健估计）来估计协方差，计算每个样本到分布中心的
    Mahalanobis 距离，按 χ² 分位数判定异常。

    Parameters
    ----------
    columns / use : 见 ``analyze_basic_statistics``；默认 ``use="any"``。
    robust : bool, default True
        是否使用 MinCovDet 稳健估计（推荐，但开销大）。
    chi2_alpha : float, default 0.01
        χ² 检验显著性水平；α=0.01 对应较严格的异常判定。
    top_n : int, default 20
        返回距离最大的前 N 行。

    Returns
    -------
    Dict[str, Any]
        ``metrics`` 含 ``threshold_distance``、``outlier_indices``、
        ``top_outliers``。
    """
    from sklearn.covariance import EmpiricalCovariance, MinCovDet

    if chi2_alpha <= 0 or chi2_alpha >= 1:
        chi2_alpha = 0.01

    df = get_df(runtime)
    cols = resolve_columns(runtime, columns=columns, use=use)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if len(numeric_cols) < 2:
        return make_envelope(
            tool_name="multivariate_outlier",
            summary="数值列不足 2 个，无法做 Mahalanobis 检测。",
            key_findings=["至少需要 2 个数值列。"],
            metrics={"skipped": {"non_numeric": non_numeric}},
        )

    sub, info = numeric_frame(df, numeric_cols, impute="median")
    X = sub.to_numpy(dtype=float)
    n, p = X.shape
    if n < max(10, 5 * p):
        return make_envelope(
            tool_name="multivariate_outlier",
            summary="样本量不足（建议 n >= 5*p）。",
            key_findings=["当前 n=%d, p=%d。" % (n, p)],
            metrics={"n_samples": n, "n_features": p},
        )

    try:
        if robust:
            est = MinCovDet(random_state=0, support_fraction=None)
        else:
            est = EmpiricalCovariance()
        est.fit(X)
        dist = est.mahalanobis(X)
    except Exception as exc:
        logger.warning("Mahalanobis fit failed: %s", exc)
        # Fallback: classic estimator via numpy
        mu = X.mean(axis=0)
        cov = np.cov(X, rowvar=False)
        try:
            inv = np.linalg.pinv(cov)
        except Exception:
            return make_envelope(
                tool_name="multivariate_outlier",
                summary="协方差矩阵不可逆。",
                key_findings=["无法计算 Mahalanobis 距离。"],
                metrics={"error": str(exc)},
            )
        diff = X - mu
        dist = np.einsum("ij,jk,ik->i", diff, inv, diff)

    # χ² threshold with p degrees of freedom
    chi2_threshold = float(sp_stats.chi2.ppf(1.0 - chi2_alpha, df=p))
    is_outlier = dist > chi2_threshold

    order = np.argsort(dist)[::-1][:top_n]
    top_outliers = []
    for k in order:
        row = {
            "row_index": int(sub.index[k]),
            "mahalanobis_distance": round_float(float(dist[k])),
            "is_outlier": bool(is_outlier[k]),
            "values": {str(c): round_float(float(sub.iloc[k][c])) for c in numeric_cols[:10]},
        }
        top_outliers.append(row)

    findings = [
        "Mahalanobis 异常：%d 个样本（χ² 门槛=%.3f, p=%d, α=%.3f）。"
        % (int(is_outlier.sum()), chi2_threshold, p, chi2_alpha)
    ]
    if top_outliers:
        findings.append(
            "最异常样本 row_index=%d，距离=%.3f。"
            % (top_outliers[0]["row_index"], top_outliers[0]["mahalanobis_distance"]))

    notes_extras: List[str] = []
    if non_numeric:
        notes_extras.append("非数值列已跳过：%s" % ", ".join(non_numeric))
    if robust:
        notes_extras.append("已使用 MinCovDet 稳健估计，抗异常值污染。")

    return make_envelope(
        tool_name="multivariate_outlier",
        summary="完成 %d 样本 × %d 列的 Mahalanobis 异常检测（robust=%s）。"
                % (n, p, robust),
        key_findings=findings,
        metrics={
            "n_samples": int(n),
            "n_features": int(p),
            "robust": bool(robust),
            "chi2_alpha": float(chi2_alpha),
            "threshold_distance": round_float(chi2_threshold),
            "outlier_indices": [int(i) for i in np.where(is_outlier)[0]][:200],
            "outlier_count": int(is_outlier.sum()),
            "top_outliers": top_outliers,
            "used_columns": list(numeric_cols),
        },
        recommendations=[
            "Mahalanobis 异常样本同时检查其在 anomaly_detection_tools 中是否被多个检测器一致标记。",
            "robust=True 与 False 结论差异大 → 数据中存在大量异常污染了协方差估计。",
            "高维 (p>20) 时 Mahalanobis 估计不稳定，建议先做 PCA 降维。",
        ],
        notes=format_notes(info, notes_extras),
    )


@tool("analyze_extreme_values")
@tool_guard("analyze_extreme_values")
def analyze_extreme_values(
    runtime: ToolRuntime,
    columns: Optional[List[str]] = None,
    use: str = "target",
    upper_limit: Optional[float] = None,
    lower_limit: Optional[float] = None,
    return_periods: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """极值 / 超越分析：阈值计数 + 重现水平估计。

    Parameters
    ----------
    columns / use : 见 ``analyze_basic_statistics``。
    upper_limit / lower_limit : float, optional
        工艺上下限（如规格上下界），用于统计超界次数与时长。
    return_periods : list[int], optional
        需要估计重现水平的步数（默认 [100, 1000, 10000]）。

    Returns
    -------
    Dict[str, Any]
        ``metrics.per_column`` 含 thresholds_exceed / return_levels。
    """
    if return_periods is None:
        return_periods = [100, 1000, 10000]

    df = get_df(runtime)
    cols = resolve_columns(runtime, columns=columns, use=use)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="extreme_values",
            summary="无可用数值列。",
            key_findings=["无法做极值分析。"],
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
        n = int(arr.size)

        # Standard thresholds
        p95 = float(np.percentile(arr, 95))
        p99 = float(np.percentile(arr, 99))
        max_val = float(arr.max())
        min_val = float(arr.min())

        entry: Dict[str, Any] = {
            "n_valid": n,
            "min": round_float(min_val),
            "max": round_float(max_val),
            "p95": round_float(p95),
            "p99": round_float(p99),
        }

        # Limit exceedances
        exceed: Dict[str, Any] = {}
        if upper_limit is not None:
            mask = arr > float(upper_limit)
            exceed["upper_limit"] = round_float(float(upper_limit))
            exceed["upper_exceed_count"] = int(mask.sum())
            exceed["upper_exceed_rate"] = round_float(float(mask.sum()) / n)
        if lower_limit is not None:
            mask = arr < float(lower_limit)
            exceed["lower_limit"] = round_float(float(lower_limit))
            exceed["lower_exceed_count"] = int(mask.sum())
            exceed["lower_exceed_rate"] = round_float(float(mask.sum()) / n)
        if exceed:
            entry["spec_exceedance"] = exceed

        # Return levels via block maxima Gumbel fit (simple method-of-moments)
        rp_results: List[Dict[str, Any]] = []
        for rp in return_periods:
            if rp <= 0 or n < 30:
                continue
            try:
                level = gumbel_return_level(arr, rp, n)
                rp_results.append({
                    "return_period_steps": int(rp),
                    "return_level": round_float(level),
                })
            except Exception as exc:
                logger.debug("gumbel failed: %s", exc)
        entry["return_levels"] = rp_results

        per_column[col] = entry
        # Build finding
        bits = ["p99=%.4g" % p99]
        if upper_limit is not None:
            bits.append("超上限 %d 次" % int((arr > float(upper_limit)).sum()))
        if lower_limit is not None:
            bits.append("超下限 %d 次" % int((arr < float(lower_limit)).sum()))
        if rp_results:
            bits.append("%d 步重现水平=%.4g"
                        % (rp_results[0]["return_period_steps"],
                           rp_results[0]["return_level"]))
        findings.append("%s：%s。" % (col, "，".join(bits)))

    notes_extras: List[str] = []
    if non_numeric:
        notes_extras.append("非数值列已跳过：%s" % ", ".join(non_numeric))

    return make_envelope(
        tool_name="extreme_values",
        summary="完成 %d 列的极值 / 超越分析。" % len(numeric_cols),
        key_findings=findings,
        metrics={
            "per_column": per_column,
            "upper_limit": upper_limit,
            "lower_limit": lower_limit,
            "return_periods": list(return_periods),
        },
        recommendations=[
            "重现水平用于工艺裕度评估；超过 p99 的样本应触发质量复核。",
            "超界率 > 1% 时建议先排查规格是否合理，而非全数判定异常。",
            "极值统计在小样本下不稳定，n<200 时谨慎引用 return_levels。",
        ],
        notes=format_notes({"skipped_non_numeric": non_numeric}, notes_extras),
    )


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------

def gumbel_return_level(x: np.ndarray, return_period: int, n: int) -> float:
    """Block-maxima Gumbel method-of-moments return level.

    Fits a Gumbel distribution to the array's maxima (treating the full
    series as one block for simplicity) and returns the level that is
    expected to be exceeded once every ``return_period`` observations.
    """
    arr = np.asarray(x, dtype=float)
    if arr.size < 2:
        return float("nan")
    mu = float(arr.mean())
    sigma = float(arr.std(ddof=1))
    if sigma <= 0:
        return float(arr.max())
    # Reduce the return period to per-observation probability
    # P(exceed in one step) ≈ 1/return_period
    prob = 1.0 / float(return_period)
    # Gumbel quantile: x = mu - sigma * ln(-ln(1-p))
    # but with sigma scaled to Gumbel scale (sigma_gumbel = sigma * sqrt(6)/pi).
    beta = sigma * math.sqrt(6) / math.pi
    mu_g = mu - 0.5772156649 * beta  # Euler-Mascheroni
    level = mu_g - beta * math.log(-math.log(1 - prob))
    return float(level)


TOOLS = [
    detect_univariate_outliers,
    detect_multivariate_outliers,
    analyze_extreme_values,
]
