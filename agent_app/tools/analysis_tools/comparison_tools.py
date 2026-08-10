"""Group-comparison analysis tools.

Three tools for comparing distributions / means across categorical groups:

- :func:`compare_group_statistics` — per-group descriptive statistics
  (count/mean/std/min/max/quantiles) for the chosen target columns,
  plus a "spread across groups" summary.
- :func:`compare_group_distributions` — one-way ANOVA + Kruskal-Wallis
  (non-parametric) per target column, plus Tukey HSD post-hoc pairs when
  ANOVA rejects the null.
- :func:`compare_two_groups` — two-sample t-test (equal / Welch) + Mann-
  Whitney U + effect size (Cohen's d / rank-biserial), for the special
  case of comparing exactly two groups.

All tools take ``runtime: ToolRuntime`` for context access; every other
parameter (group_column, group values to compare, ...) is supplied
directly by the LLM.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from langchain.tools import ToolRuntime, tool
from scipy import stats as sp_stats

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

@tool("compare_group_statistics")
@tool_guard("compare_group_statistics")
def compare_group_statistics(
    runtime: ToolRuntime,
    group_column: str,
    columns: Optional[List[str]] = None,
    use: str = "target",
    agg: List[str] = None,
    max_groups: int = 50,
) -> Dict[str, Any]:
    """按 ``group_column`` 分组，输出每组的描述性统计。

    Parameters
    ----------
    group_column : str
        必填，分组列名（设备 ID / 班次 / 批次 / 工艺配方等）。
    columns / use : 见 ``analyze_basic_statistics``。
    agg : list[str], default ["count","mean","std","min","median","max"]
        每组计算的统计函数。
    max_groups : int, default 50
        分组数上限（过多的分组会被截断并告警）。

    Returns
    -------
    Dict[str, Any]
        ``metrics.per_column`` 含 group_stats 列表与 across_groups_spread。
    """
    if not group_column:
        return make_envelope(
            tool_name="group_statistics",
            summary="必须提供 group_column。",
            key_findings=["无法做分组对比。"],
            metrics={},
        )
    if agg is None:
        agg = ["count", "mean", "std", "min", "median", "max"]

    df = get_df(runtime)
    if group_column not in df.columns:
        return make_envelope(
            tool_name="group_statistics",
            summary="group_column=%r 不在 df 中。" % group_column,
            key_findings=["请检查分组列名。"],
            metrics={},
        )

    cols = resolve_columns(runtime, columns=columns, use=use)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="group_statistics",
            summary="无可用数值列。",
            key_findings=["无法做分组对比。"],
            metrics={"skipped": {"non_numeric": non_numeric}},
        )

    n_groups_total = int(df[group_column].nunique(dropna=True))
    top_groups = df[group_column].value_counts(dropna=True).head(max_groups).index.tolist()

    findings: List[str] = []
    per_column: Dict[str, Any] = {}

    for col in numeric_cols:
        sub = df[[group_column, col]].dropna(subset=[col]).copy()
        sub[col] = pd.to_numeric(sub[col], errors="coerce")
        sub = sub.dropna(subset=[col])
        if sub.empty:
            continue
        grouped = sub.groupby(group_column)[col]
        group_stats: List[Dict[str, Any]] = []
        for g in top_groups:
            series = grouped.get_group(g) if g in grouped.groups else pd.Series(dtype=float)
            if series.empty:
                continue
            arr = series.to_numpy(dtype=float)
            entry: Dict[str, Any] = {"group": g, "n": int(arr.size)}
            if "count" in agg:
                entry["count"] = int(arr.size)
            if "mean" in agg:
                entry["mean"] = round_float(float(arr.mean()))
            if "std" in agg:
                entry["std"] = round_float(float(arr.std(ddof=1)) if arr.size > 1 else 0.0)
            if "min" in agg:
                entry["min"] = round_float(float(arr.min()))
            if "median" in agg:
                entry["median"] = round_float(float(np.median(arr)))
            if "max" in agg:
                entry["max"] = round_float(float(arr.max()))
            if "q1" in agg:
                entry["q1"] = round_float(float(np.percentile(arr, 25)))
            if "q3" in agg:
                entry["q3"] = round_float(float(np.percentile(arr, 75)))
            group_stats.append(entry)

        # Spread across groups
        means = [g["mean"] for g in group_stats if g.get("mean") is not None]
        if len(means) >= 2:
            overall_mean = float(np.mean(means))
            spread_cv = float(np.std(means, ddof=1) / abs(overall_mean)) if overall_mean != 0 else None
            best_group = max(group_stats, key=lambda g: g.get("mean", float("-inf")))
            worst_group = min(group_stats, key=lambda g: g.get("mean", float("inf")))
            spread = {
                "mean_of_group_means": round_float(overall_mean),
                "std_of_group_means": round_float(float(np.std(means, ddof=1))),
                "cv_across_groups": round_float(spread_cv) if spread_cv is not None else None,
                "best_group": best_group["group"],
                "worst_group": worst_group["group"],
                "best_minus_worst": round_float(best_group["mean"] - worst_group["mean"]),
            }
        else:
            spread = {"note": "组数不足"}

        per_column[col] = {
            "n_groups_total": n_groups_total,
            "n_groups_returned": len(group_stats),
            "group_stats": group_stats,
            "across_groups_spread": spread,
        }
        if len(means) >= 2:
            findings.append(
                "%s：%d 组均值范围 [%.4g, %.4g]，跨组 CV=%.3f。"
                % (col, len(means), min(means), max(means),
                   spread.get("cv_across_groups") or 0.0))

    notes_extras: List[str] = []
    if non_numeric:
        notes_extras.append("非数值列已跳过：%s" % ", ".join(non_numeric))
    if n_groups_total > max_groups:
        notes_extras.append(
            "实际分组数 %d 超过 max_groups=%d，仅返回最大的 %d 组。"
            % (n_groups_total, max_groups, max_groups))

    return make_envelope(
        tool_name="group_statistics",
        summary="完成按 %s 分组的 %d 列统计（共 %d 组）。"
                % (group_column, len(numeric_cols), n_groups_total),
        key_findings=findings,
        metrics={
            "per_column": per_column,
            "group_column": group_column,
            "agg": list(agg),
        },
        recommendations=[
            "跨组 CV>0.2 → 组间差异显著，建议进一步 compare_group_distributions 做显著性检验。",
            "样本极少的组（n<5）统计不可靠，建议剔除或合并。",
            "对比同一物理量在不同班次/设备下的均值差，可定位工艺一致性瓶颈。",
        ],
        notes=format_notes({}, notes_extras),
    )


@tool("compare_group_distributions")
@tool_guard("compare_group_distributions")
def compare_group_distributions(
    runtime: ToolRuntime,
    group_column: str,
    columns: Optional[List[str]] = None,
    use: str = "target",
    alpha: float = 0.05,
    min_group_size: int = 5,
    max_groups: int = 10,
    tukey_hsd: bool = True,
) -> Dict[str, Any]:
    """对多组做 ANOVA + Kruskal-Wallis + Tukey HSD 事后比较。

    Parameters
    ----------
    group_column : str
        分组列名。
    columns / use : 见 ``analyze_basic_statistics``。
    alpha : float, default 0.05
        显著性水平。
    min_group_size : int, default 5
        样本数低于此值的组会被剔除（避免单点拉偏结果）。
    max_groups : int, default 10
        最多分析的组数（过多的组会让 Tukey HSD 失去统计力）。
    tukey_hsd : bool, default True
        是否在 ANOVA 拒绝原假设后做 Tukey HSD 两两比较。

    Returns
    -------
    Dict[str, Any]
        ``metrics.per_column`` 含 anova / kruskal / tukey_hsd / verdict。
    """
    if not group_column:
        return make_envelope(
            tool_name="group_distribution_test",
            summary="必须提供 group_column。",
            key_findings=["无法做多组分布检验。"],
            metrics={},
        )

    df = get_df(runtime)
    if group_column not in df.columns:
        return make_envelope(
            tool_name="group_distribution_test",
            summary="group_column=%r 不在 df 中。" % group_column,
            key_findings=["请检查分组列名。"],
            metrics={},
        )

    cols = resolve_columns(runtime, columns=columns, use=use)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="group_distribution_test",
            summary="无可用数值列。",
            key_findings=["无法做多组分布检验。"],
            metrics={"skipped": {"non_numeric": non_numeric}},
        )

    # Pick top groups by size with sufficient samples
    counts = df[group_column].value_counts(dropna=True)
    eligible = counts[counts >= min_group_size].head(max_groups)
    selected_groups = eligible.index.tolist()
    if len(selected_groups) < 2:
        return make_envelope(
            tool_name="group_distribution_test",
            summary="满足 min_group_size=%d 的组数不足 2。"
                    % min_group_size,
            key_findings=["请降低 min_group_size 或更换 group_column。"],
            metrics={"selected_groups": selected_groups,
                     "group_counts": counts.head(20).to_dict()},
        )

    findings: List[str] = []
    per_column: Dict[str, Any] = {}

    for col in numeric_cols:
        sub = df[[group_column, col]].dropna(subset=[col]).copy()
        sub[col] = pd.to_numeric(sub[col], errors="coerce")
        sub = sub.dropna(subset=[col])
        groups_data: List[np.ndarray] = []
        for g in selected_groups:
            arr = sub.loc[sub[group_column] == g, col].to_numpy(dtype=float)
            if arr.size >= min_group_size:
                groups_data.append(arr)

        if len(groups_data) < 2:
            per_column[col] = {"note": "样本不足"}
            continue

        result: Dict[str, Any] = {
            "n_groups": len(groups_data),
            "groups": selected_groups[:len(groups_data)],
            "group_sizes": [int(a.size) for a in groups_data],
        }

        # One-way ANOVA
        try:
            f_stat, p_anova = sp_stats.f_oneway(*groups_data)
            result["anova"] = {
                "f_statistic": round_float(float(f_stat)),
                "p_value": round_float(float(p_anova)),
                "reject_equal_means": bool(p_anova < alpha),
            }
        except Exception as exc:
            result["anova"] = {"error": str(exc)}

        # Kruskal-Wallis (non-parametric)
        try:
            h_stat, p_kw = sp_stats.kruskal(*groups_data)
            result["kruskal_wallis"] = {
                "h_statistic": round_float(float(h_stat)),
                "p_value": round_float(float(p_kw)),
                "reject_equal_medians": bool(p_kw < alpha),
            }
        except Exception as exc:
            result["kruskal_wallis"] = {"error": str(exc)}

        # Verdict reconciliation
        anova_reject = result.get("anova", {}).get("reject_equal_means", False)
        kw_reject = result.get("kruskal_wallis", {}).get("reject_equal_medians", False)
        if anova_reject and kw_reject:
            verdict = "groups differ (robust)"
        elif anova_reject or kw_reject:
            verdict = "groups differ (single test only, inspect distribution)"
        else:
            verdict = "no significant group difference"
        result["verdict"] = verdict

        # Tukey HSD post-hoc
        if tukey_hsd and (anova_reject or kw_reject):
            try:
                from scipy.stats import tukey_hsd as _scipy_tukey  # scipy >=1.11
                res = _scipy_tukey(*groups_data)
                pair_results: List[Dict[str, Any]] = []
                n_g = len(groups_data)
                for i in range(n_g):
                    for j in range(i + 1, n_g):
                        pair_results.append({
                            "group_a": selected_groups[i],
                            "group_b": selected_groups[j],
                            "mean_diff": round_float(float(res.statistic[i, j])),
                            "p_value": round_float(float(res.pvalue[i, j])),
                            "significant": bool(res.pvalue[i, j] < alpha),
                        })
                pair_results.sort(key=lambda x: x["p_value"])
                result["tukey_hsd"] = pair_results[:50]
            except ImportError:
                # Fallback to statsmodels
                try:
                    from statsmodels.stats.multicomp import pairwise_tukeyhsd
                    all_vals = np.concatenate(groups_data)
                    labels = np.concatenate(
                        [[selected_groups[i]] * groups_data[i].size
                         for i in range(len(groups_data))]
                    )
                    tk = pairwise_tukeyhsd(all_vals, labels, alpha=alpha)
                    pair_results = []
                    for row in tk.summary().data[1:]:
                        pair_results.append({
                            "group_a": row[0],
                            "group_b": row[1],
                            "mean_diff": round_float(float(row[2])),
                            "p_value": round_float(float(row[3])),
                            "reject": bool(row[5]),
                        })
                    result["tukey_hsd"] = pair_results[:50]
                except Exception as exc:
                    result["tukey_hsd"] = {"note": "Tukey HSD 不可用：%s" % exc}

        per_column[col] = result
        findings.append(
            "%s：%s（anova p=%.4g, KW p=%.4g）。"
            % (col, verdict,
               result.get("anova", {}).get("p_value") or 1.0,
               result.get("kruskal_wallis", {}).get("p_value") or 1.0))

    notes_extras: List[str] = []
    if non_numeric:
        notes_extras.append("非数值列已跳过：%s" % ", ".join(non_numeric))

    return make_envelope(
        tool_name="group_distribution_test",
        summary="完成按 %s 分组的 %d 列 ANOVA + Kruskal-Wallis 检验。"
                % (group_column, len(numeric_cols)),
        key_findings=findings,
        metrics={
            "per_column": per_column,
            "group_column": group_column,
            "alpha": float(alpha),
            "min_group_size": int(min_group_size),
            "selected_groups": selected_groups,
        },
        recommendations=[
            "ANOVA 与 KW 同时拒绝 → 组间差异稳健；只一个拒绝 → 检查组内是否非正态或方差不齐。",
            "Tukey HSD 列出哪两组差异显著，可定位具体差异来源。",
            "组数过多（>10）时 Bonferroni 校正更保守，可适当收紧 α。",
        ],
        notes=format_notes({"skipped_non_numeric": non_numeric}, notes_extras),
    )


@tool("compare_two_groups")
@tool_guard("compare_two_groups")
def compare_two_groups(
    runtime: ToolRuntime,
    group_column: str,
    group_a: str,
    group_b: str,
    columns: Optional[List[str]] = None,
    use: str = "target",
    equal_var: bool = False,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """两组对比：Welch/t 检验 + Mann-Whitney U + 效应量。

    专用于"两个组谁更好/更差"这类典型工艺问题（如班次 A vs 班次 B、
    设备 1 vs 设备 2）。

    Parameters
    ----------
    group_column : str
        分组列名。
    group_a / group_b : str
        要比较的两个组值（必须）。
    columns / use : 见 ``analyze_basic_statistics``。
    equal_var : bool, default False
        t 检验是否假设方差齐（False 用 Welch）。
    alpha : float, default 0.05
        显著性水平。

    Returns
    Dict[str, Any]
        ``metrics.per_column`` 含 t_test / mann_whitney / effect_size /
        verdict。
    """
    if not group_column or not group_a or not group_b:
        return make_envelope(
            tool_name="two_group_test",
            summary="必须提供 group_column / group_a / group_b。",
            key_findings=["缺少必要参数。"],
            metrics={},
        )

    df = get_df(runtime)
    if group_column not in df.columns:
        return make_envelope(
            tool_name="two_group_test",
            summary="group_column=%r 不在 df 中。" % group_column,
            key_findings=["请检查分组列名。"],
            metrics={},
        )

    cols = resolve_columns(runtime, columns=columns, use=use)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="two_group_test",
            summary="无可用数值列。",
            key_findings=["无法做两组对比。"],
            metrics={"skipped": {"non_numeric": non_numeric}},
        )

    findings: List[str] = []
    per_column: Dict[str, Any] = {}

    for col in numeric_cols:
        a_full = pd.to_numeric(df.loc[df[group_column] == group_a, col], errors="coerce").dropna()
        b_full = pd.to_numeric(df.loc[df[group_column] == group_b, col], errors="coerce").dropna()
        if a_full.size < 2 or b_full.size < 2:
            per_column[col] = {"n_a": int(a_full.size),
                               "n_b": int(b_full.size),
                               "note": "样本不足（每组需>=2）"}
            continue
        a = a_full.to_numpy(dtype=float)
        b = b_full.to_numpy(dtype=float)

        result: Dict[str, Any] = {
            "n_a": int(a.size), "n_b": int(b.size),
            "mean_a": round_float(float(a.mean())),
            "mean_b": round_float(float(b.mean())),
            "std_a": round_float(float(a.std(ddof=1))),
            "std_b": round_float(float(b.std(ddof=1))),
        }

        # t-test (Welch by default)
        try:
            t_stat, p_t = sp_stats.ttest_ind(a, b, equal_var=equal_var)
            result["t_test"] = {
                "statistic": round_float(float(t_stat)),
                "p_value": round_float(float(p_t)),
                "equal_var_assumed": bool(equal_var),
                "reject_equal_means": bool(p_t < alpha),
            }
        except Exception as exc:
            result["t_test"] = {"error": str(exc)}

        # Mann-Whitney U
        try:
            u_stat, p_u = sp_stats.mannwhitneyu(a, b, alternative="two-sided")
            result["mann_whitney"] = {
                "statistic": round_float(float(u_stat)),
                "p_value": round_float(float(p_u)),
                "reject_equal_distributions": bool(p_u < alpha),
            }
        except Exception as exc:
            result["mann_whitney"] = {"error": str(exc)}

        # Effect sizes
        pooled_std = math.sqrt(
            ((a.size - 1) * a.var(ddof=1) + (b.size - 1) * b.var(ddof=1))
            / max(a.size + b.size - 2, 1)
        )
        cohen_d = (a.mean() - b.mean()) / pooled_std if pooled_std > 0 else 0.0
        result["effect_size"] = {
            "cohen_d": round_float(float(cohen_d)),
            "interpretation": (
                "negligible" if abs(cohen_d) < 0.2 else
                "small" if abs(cohen_d) < 0.5 else
                "medium" if abs(cohen_d) < 0.8 else "large"
            ),
        }

        # Verdict
        t_reject = result.get("t_test", {}).get("reject_equal_means", False)
        u_reject = result.get("mann_whitney", {}).get("reject_equal_distributions", False)
        if t_reject and u_reject:
            verdict = "groups differ significantly"
        elif t_reject or u_reject:
            verdict = "groups differ (one test only)"
        else:
            verdict = "no significant difference"
        result["verdict"] = verdict
        per_column[col] = result

        sign = "↑" if a.mean() > b.mean() else "↓"
        findings.append(
            "%s：%s vs %s → %s（%s: %.4g vs %.4g，d=%.2f）。"
            % (col, group_a, group_b, verdict,
               sign, float(a.mean()), float(b.mean()), cohen_d))

    notes_extras: List[str] = []
    if non_numeric:
        notes_extras.append("非数值列已跳过：%s" % ", ".join(non_numeric))

    return make_envelope(
        tool_name="two_group_test",
        summary="完成 %s 与 %s 的两组对比（%d 列）。"
                % (group_a, group_b, len(numeric_cols)),
        key_findings=findings,
        metrics={
            "per_column": per_column,
            "group_column": group_column,
            "group_a": group_a,
            "group_b": group_b,
            "alpha": float(alpha),
        },
        recommendations=[
            "Cohen's d 解读：|d|<0.2 微弱、0.5 中等、0.8+ 显著。",
            "Welch (equal_var=False) 在方差不相等时更稳健，是默认推荐。",
            "t 检验与 Mann-Whitney 结论冲突 → 分布严重非正态，建议看 MW。",
        ],
        notes=format_notes({"skipped_non_numeric": non_numeric}, notes_extras),
    )


TOOLS = [
    compare_group_statistics,
    compare_group_distributions,
    compare_two_groups,
]
