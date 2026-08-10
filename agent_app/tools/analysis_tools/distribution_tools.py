"""Distribution-shape analysis tools.

Three complementary tools for characterising the marginal distribution
of one or more target / feature columns:

- :func:`analyze_basic_statistics` — count/mean/std/min/max/quantiles/
  IQR/CV plus a 95% bootstrap CI on the mean. The first thing you call
  when you want a "quick statistical summary".
- :func:`analyze_distribution_shape` — skewness, kurtosis, normality
  tests (Shapiro-Wilk / D'Agostino-Pearson / Anderson-Darling / Jarque
  -Bera) and a qualitative shape label (symmetric / right-skew / left
  -skew / heavy-tailed / bimodal-suspected).
- :func:`analyze_histogram` — equi-width bin counts, densities, cumulative
  proportions and dominant-bin concentration; the building block for
  distribution / spread questions.

All tools take ``runtime: ToolRuntime`` for context access; every other
parameter is supplied directly by the LLM.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Sequence

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

@tool("analyze_basic_statistics")
@tool_guard("analyze_basic_statistics")
def analyze_basic_statistics(
    runtime: ToolRuntime,
    columns: Optional[List[str]] = None,
    use: str = "target",
    quantiles: Optional[List[float]] = None,
    bootstrap_ci: bool = True,
    random_state: Optional[int] = 0,
) -> Dict[str, Any]:
    """计算目标/特征列的基础统计描述。

    覆盖：count / mean / std / min / max / 分位数 / IQR / 变异系数 CV，
    并可选对均值做 95% 自助置信区间。当需要"快速看一眼这列大致什么样"
    时优先使用。

    Parameters
    ----------
    columns : list[str], optional
        显式指定要分析的列名；不填时按 ``use`` 取上下文中的列。
    use : {"target","feature","any"}, default "target"
        没有显式 ``columns`` 时，从 ctx 的 target/feature 列中选择。
    quantiles : list[float], optional
        需要计算的分位点（0~1）。默认 [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]。
    bootstrap_ci : bool, default True
        是否对均值做 500 次自助采样，输出 95% 置信区间。
    random_state : int, optional
        自助采样的随机种子（默认 0 保证可复现）。

    Returns
    -------
    Dict[str, Any]
        ``metrics.per_column`` 为每列的统计字典；``metrics.skipped``
        列出非数值或缺失列。
    """
    df = get_df(runtime)
    cols = resolve_columns(runtime, columns=columns, use=use)
    numeric_cols, non_numeric, missing = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="basic_statistics",
            summary="没有任何可分析的数值列。",
            key_findings=["输入列中没有数值类型，无法计算描述性统计。"],
            metrics={"skipped": {"non_numeric": non_numeric, "missing": missing}},
            recommendations=["请检查列名或更换 use 参数（target/feature/any）。"],
        )

    qs = list(quantiles) if quantiles else [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]
    qs = sorted(set(float(q) for q in qs if 0.0 <= float(q) <= 1.0))
    findings: List[str] = []
    per_column: Dict[str, Any] = {}

    for col in numeric_cols:
        s, _ = numeric_series(df, col, dropna=True)
        if s.empty:
            per_column[col] = {"n_valid": 0}
            continue
        arr = s.to_numpy(dtype=float)
        mean = float(arr.mean())
        std = float(arr.std(ddof=1)) if arr.size > 1 else 0.0
        cv = float(std / mean) if mean not in (0.0,) and mean != 0 else None
        q_values = {("p%.2f" % (q * 100)).replace(".", "_"): float(np.percentile(arr, q * 100))
                    for q in qs}
        q_values["p50"] = float(np.percentile(arr, 50))
        iqr = q_values.get("p75", 0.0) - q_values.get("p25", 0.0)

        entry: Dict[str, Any] = {
            "n_valid": int(arr.size),
            "n_missing": int(df[col].isna().sum()),
            "mean": round_float(mean),
            "std": round_float(std),
            "min": round_float(float(arr.min())),
            "max": round_float(float(arr.max())),
            "range": round_float(float(arr.max() - arr.min())),
            "iqr": round_float(float(iqr)),
            "cv": round_float(cv) if cv is not None else None,
            "quantiles": {k: round_float(v) for k, v in q_values.items()},
        }

        if bootstrap_ci and arr.size >= 3:
            from agent_app.tools.analysis_tools._common import bootstrap_ci as _bs
            lo, hi = _bs(arr, np.mean, n_boot=500, alpha=0.05,
                         random_state=random_state if random_state is not None else 0)
            entry["mean_ci_95"] = [round_float(lo), round_float(hi)] if lo is not None else None

        per_column[col] = entry
        findings.append(
            "%s：均值=%.4g，标准差=%.4g，CV=%.3f，范围=[%.4g, %.4g]，IQR=%.4g"
            % (col, mean, std, cv if cv is not None else float("nan"),
               arr.min(), arr.max(), iqr))

    notes_extras: List[str] = []
    if non_numeric:
        notes_extras.append("非数值列已跳过：%s" % ", ".join(non_numeric))

    return make_envelope(
        tool_name="basic_statistics",
        summary="完成 %d 列的基础描述性统计。" % len(numeric_cols),
        key_findings=findings,
        metrics={
            "per_column": per_column,
            "skipped": {"non_numeric": non_numeric, "missing": missing},
            "quantiles_requested": qs,
            "bootstrap_ci": bool(bootstrap_ci),
        },
        recommendations=[
            "关注 CV（变异系数）较高的列——通常 CV>0.3 表示过程波动明显。",
            "对比 p1/p99 与 min/max，判断是否需要剔除极端值。",
            "若 mean_ci_95 较宽，说明样本量不足以稳健估计均值。",
        ],
        notes=format_notes({"skipped_non_numeric": non_numeric}, notes_extras),
    )


@tool("analyze_distribution_shape")
@tool_guard("analyze_distribution_shape")
def analyze_distribution_shape(
    runtime: ToolRuntime,
    columns: Optional[List[str]] = None,
    use: str = "target",
    normality_alpha: float = 0.05,
) -> Dict[str, Any]:
    """分析分布形态：偏度、峰度与正态性检验。

    输出 scipy 实现的偏度（含偏差校正）、峰度（超额峰度）、
    Shapiro-Wilk（<=5000 样本）、D'Agostino-Pearson 正态性检验、
    Anderson-Darling（含 5%/1% 临界值）、Jarque-Bera，并据此给出
    分布形态标签。

    Parameters
    ----------
    columns / use : 见 ``analyze_basic_statistics``。
    normality_alpha : float, default 0.05
        判定正态性检验是否拒绝 H0 的显著性水平。

    Returns
    -------
    Dict[str, Any]
        ``metrics.per_column`` 含 skew/kurtosis/normality_tests/shape_label。
    """
    df = get_df(runtime)
    cols = resolve_columns(runtime, columns=columns, use=use)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="distribution_shape",
            summary="无可用数值列。",
            key_findings=["无法计算偏度/峰度。"],
            metrics={"skipped": {"non_numeric": non_numeric}},
        )

    findings: List[str] = []
    per_column: Dict[str, Any] = {}

    for col in numeric_cols:
        s, _ = numeric_series(df, col, dropna=True)
        if s.size < 3:
            per_column[col] = {"n_valid": int(s.size), "note": "样本不足"}
            continue
        arr = s.to_numpy(dtype=float)

        skew = float(sp_stats.skew(arr, bias=False)) if arr.size > 2 else 0.0
        kurt = float(sp_stats.kurtosis(arr, fisher=True, bias=False)) if arr.size > 3 else 0.0

        normality: Dict[str, Any] = {}
        # Shapiro-Wilk (cap at 5000 samples to avoid known slow-down / warning).
        if arr.size <= 5000:
            try:
                w, p = sp_stats.shapiro(arr)
                normality["shapiro_wilk"] = {
                    "statistic": round_float(float(w)),
                    "p_value": round_float(float(p)),
                    "reject_normality": bool(p < normality_alpha),
                }
            except Exception as exc:
                logger.debug("shapiro failed: %s", exc)

        # D'Agostino-Pearson (needs >=8 samples)
        if arr.size >= 8:
            try:
                k2, p = sp_stats.normaltest(arr)
                normality["dagostino_pearson"] = {
                    "statistic": round_float(float(k2)),
                    "p_value": round_float(float(p)),
                    "reject_normality": bool(p < normality_alpha),
                }
            except Exception as exc:
                logger.debug("normaltest failed: %s", exc)

        # Jarque-Bera
        try:
            jb, p = sp_stats.jarque_bera(arr)
            normality["jarque_bera"] = {
                "statistic": round_float(float(jb)),
                "p_value": round_float(float(p)),
                "reject_normality": bool(p < normality_alpha),
            }
        except Exception as exc:
            logger.debug("jarque_bera failed: %s", exc)

        # Anderson-Darling
        try:
            ad = sp_stats.anderson(arr, dist="norm")
            normality["anderson_darling"] = {
                "statistic": round_float(float(ad.statistic)),
                "critical_values": [round_float(float(c)) for c in ad.critical_values],
                "significance_levels": [float(s) for s in ad.significance_level],
            }
        except Exception as exc:
            logger.debug("anderson failed: %s", exc)

        # Shape label
        shape_label = _shape_label(skew, kurt)
        per_column[col] = {
            "n_valid": int(arr.size),
            "skewness": round_float(skew),
            "kurtosis_excess": round_float(kurt),
            "normality_tests": normality,
            "shape_label": shape_label,
        }
        findings.append(
            "%s：偏度=%+.3f，超额峰度=%+.3f → %s"
            % (col, skew, kurt, shape_label))

    notes_extras: List[str] = []
    if non_numeric:
        notes_extras.append("非数值列已跳过：%s" % ", ".join(non_numeric))

    return make_envelope(
        tool_name="distribution_shape",
        summary="完成 %d 列的分布形态分析（偏度/峰度/正态性）。" % len(numeric_cols),
        key_findings=findings,
        metrics={"per_column": per_column},
        recommendations=[
            "拒绝正态性的列应避免直接使用基于正态假设的方法（如 3σ 准则）。",
            "重尾（kurtosis_excess>3）的列容易出现极端值，建议使用 MAD 或 IQR 准则。",
            "强偏态分布可考虑对数/Box-Cox 变换后再建模。",
        ],
        notes=format_notes({"skipped_non_numeric": non_numeric}, notes_extras),
    )


@tool("analyze_histogram")
@tool_guard("analyze_histogram")
def analyze_histogram(
    runtime: ToolRuntime,
    columns: Optional[List[str]] = None,
    use: str = "target",
    bins: int = 20,
    bin_strategy: str = "equal_width",
    cumulative: bool = True,
    top_n: int = 5,
) -> Dict[str, Any]:
    """构建直方图，输出每列的频次/密度/累计占比以及主峰集中度。

    Parameters
    ----------
    columns / use : 见 ``analyze_basic_statistics``。
    bins : int, default 20
        等宽分箱时的桶数（建议 10~50）。
    bin_strategy : {"equal_width","quantile"}, default "equal_width"
        等宽 vs. 等频分箱。等频更适合强偏态分布。
    cumulative : bool, default True
        是否输出累计占比。
    top_n : int, default 5
        每列返回频次最高的前 N 个桶。

    Returns
    -------
    Dict[str, Any]
        ``metrics.per_column`` 含 ``bin_edges``、``counts``、``density``、
        ``cumulative``、``top_bins`` 和 ``concentration_ratio_top1``。
    """
    if bins < 2:
        bins = 2
    if bins > 200:
        bins = 200

    df = get_df(runtime)
    cols = resolve_columns(runtime, columns=columns, use=use)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="histogram",
            summary="无可用数值列。",
            key_findings=["无法构建直方图。"],
            metrics={"skipped": {"non_numeric": non_numeric}},
        )

    findings: List[str] = []
    per_column: Dict[str, Any] = {}

    for col in numeric_cols:
        s, _ = numeric_series(df, col, dropna=True)
        if s.size < 2:
            per_column[col] = {"n_valid": int(s.size)}
            continue
        arr = s.to_numpy(dtype=float)

        if bin_strategy == "quantile":
            qs = np.linspace(0, 100, bins + 1)
            edges = np.percentile(arr, qs)
            edges = np.unique(edges)  # collapse duplicate quantile edges
            if edges.size < 3:
                # Fall back to equal-width when quantile edges collapse.
                edges = np.linspace(arr.min(), arr.max(), bins + 1)
        else:
            edges = np.linspace(arr.min(), arr.max(), bins + 1)

        counts, edge_arr = np.histogram(arr, bins=edges)
        total = int(counts.sum()) or 1
        density = counts / total
        cum = np.cumsum(density) if cumulative else None

        # Top-N most frequent bins
        order = np.argsort(counts)[::-1][:top_n]
        top_bins = []
        for k in order:
            top_bins.append({
                "bin_index": int(k),
                "range": [round_float(float(edge_arr[k])),
                          round_float(float(edge_arr[k + 1]))],
                "count": int(counts[k]),
                "density": round_float(float(density[k])),
            })

        # Concentration: ratio of samples in the single largest bin
        concentration_top1 = float(counts.max() / total) if total else 0.0

        per_column[col] = {
            "n_valid": int(arr.size),
            "bin_strategy": bin_strategy,
            "bin_count": int(len(edge_arr) - 1),
            "bin_edges": [round_float(float(e)) for e in edge_arr],
            "counts": counts.tolist(),
            "density": [round_float(float(d)) for d in density],
            "cumulative": ([round_float(float(c)) for c in cum]
                           if cum is not None else None),
            "top_bins": top_bins,
            "concentration_ratio_top1": round_float(concentration_top1),
        }
        findings.append(
            "%s：%d 个分箱，最大桶集中度=%.2f，主峰范围=[%.4g, %.4g]。"
            % (col, len(edge_arr) - 1, concentration_top1,
               edge_arr[top_bins[0]["bin_index"]] if top_bins else float("nan"),
               edge_arr[(top_bins[0]["bin_index"] + 1) if top_bins else 0]
               if top_bins else float("nan")))

    notes_extras: List[str] = []
    if non_numeric:
        notes_extras.append("非数值列已跳过：%s" % ", ".join(non_numeric))

    return make_envelope(
        tool_name="histogram",
        summary="完成 %d 列的直方图构建（%s，bins=%d）。"
                % (len(numeric_cols), bin_strategy, bins),
        key_findings=findings,
        metrics={
            "per_column": per_column,
            "bins_requested": bins,
            "bin_strategy": bin_strategy,
        },
        recommendations=[
            "concentration_ratio_top1 > 0.5 说明数据过度集中在单一桶，警惕「质量门槛」或传感器死区。",
            "等频分箱后桶宽差距大说明强偏态，可结合 analyze_distribution_shape 一起看。",
            "双峰分布（两个高桶相邻有 trough）建议考虑聚类或子群分析。",
        ],
        notes=format_notes({"skipped_non_numeric": non_numeric}, notes_extras),
    )


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------

def _shape_label(skew: float, kurt: float) -> str:
    """Coarse qualitative label from (skew, excess-kurtosis)."""
    abs_skew = abs(skew)
    parts: List[str] = []
    if skew > 0.5:
        parts.append("右偏")
    elif skew < -0.5:
        parts.append("左偏")
    else:
        parts.append("近似对称")
    if kurt > 3.0:
        parts.append("重尾")
    elif kurt < -1.0:
        parts.append("轻尾/平坦")
    return "+".join(parts)


TOOLS = [
    analyze_basic_statistics,
    analyze_distribution_shape,
    analyze_histogram,
]
