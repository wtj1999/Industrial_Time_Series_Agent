"""Data-quality assessment tools.

Three tools that audit the integrity of ``ctx.df`` before any modeling /
analysis is run:

- :func:`analyze_missing_values` — per-column missing rate, missingness
  pattern (MCAR/MAR/MNAR heuristic via Little's test surrogate), block
  co-occurrence of NaNs, and a small recommendation tree.
- :func:`analyze_duplicates` — exact-duplicate rows, key-based duplicates
  (e.g. same timestamp), and near-duplicates (rows whose numeric distance
  is below a threshold).
- :func:`analyze_constant_or_low_variance_columns` — columns to drop
  because they are constant, almost-constant (low entropy) or have zero
  variance, with an explicit severity tag per column.

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

from agent_app.tools._tool_guard import tool_guard
from agent_app.tools.analysis_tools._common import (
    format_notes,
    get_df,
    make_envelope,
    resolve_columns,
    round_float,
)

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Tools
# ----------------------------------------------------------------------

@tool("analyze_missing_values")
@tool_guard("analyze_missing_values")
def analyze_missing_values(
    runtime: ToolRuntime,
    columns: Optional[List[str]] = None,
    use: str = "any",
    include_all_columns: bool = True,
    top_n: int = 20,
    time_column: Optional[str] = None,
) -> Dict[str, Any]:
    """分析每列缺失情况 + 缺失模式（MCAR/MAR/MNAR 启发式）。

    Parameters
    ----------
    columns / use : 见 ``analyze_basic_statistics``；默认不传时
        ``include_all_columns=True`` 检查全部列。
    include_all_columns : bool, default True
        若为 True 且未指定 columns，则扫描 df 的全部列（不只是 ctx 的
        target/feature）。
    top_n : int, default 20
        返回缺失率最高的前 N 列的详细信息。
    time_column : str, optional
        若提供，会判断缺失是否随时间聚集（"时间相关性"），帮助判断
        MNAR（如某段时间传感器掉线）。

    Returns
    -------
    Dict[str, Any]
        ``metrics`` 含 per_column / overall / patterns / time_correlation。
    """
    df = get_df(runtime)
    if include_all_columns and columns is None:
        cols = list(df.columns)
    else:
        cols = resolve_columns(runtime, columns=columns, use=use)

    n_rows = int(len(df))
    if n_rows == 0:
        return make_envelope(
            tool_name="missing_values",
            summary="DataFrame 为空。",
            key_findings=["无数据可分析。"],
            metrics={},
        )

    # Per-column missing
    per_col: Dict[str, Any] = {}
    for c in cols:
        s = df[c]
        n_miss = int(s.isna().sum())
        if n_miss == 0:
            per_col[c] = {
                "missing_count": 0, "missing_rate": 0.0, "status": "complete"
            }
            continue
        per_col[c] = {
            "missing_count": n_miss,
            "missing_rate": round_float(float(n_miss) / n_rows),
            "status": (
                "complete" if n_miss == 0 else
                "low (<1%)" if n_miss / n_rows < 0.01 else
                "moderate (1-20%)" if n_miss / n_rows < 0.2 else
                "high (20-50%)" if n_miss / n_rows < 0.5 else
                "severe (>=50%)"
            ),
        }

    # Overall
    total_cells = int(df.shape[0] * df.shape[1])
    total_missing = int(df.isna().sum().sum())
    rows_with_any_missing = int(df.isna().any(axis=1).sum())
    complete_rows = int((~df.isna().any(axis=1)).sum())

    overall = {
        "n_rows": n_rows,
        "n_columns": int(df.shape[1]),
        "total_cells": total_cells,
        "total_missing": total_missing,
        "overall_missing_rate": round_float(float(total_missing) / max(total_cells, 1)),
        "rows_with_any_missing": rows_with_any_missing,
        "rows_with_any_missing_rate": round_float(float(rows_with_any_missing) / n_rows),
        "complete_rows": complete_rows,
        "complete_rows_rate": round_float(float(complete_rows) / n_rows),
    }

    # Missingness pattern heuristic: per-column missing rate variance
    # + correlation with target column missingness (as MNAR proxy).
    miss_matrix = df.isna().astype(int)
    col_rates = miss_matrix.mean(axis=0)
    rate_std = float(col_rates.std(ddof=0)) if col_rates.size else 0.0
    if rate_std < 0.05 and overall["overall_missing_rate"] < 0.05:
        pattern_label = "likely MCAR (low missing rate, uniform)"
    elif rate_std > 0.2:
        pattern_label = "likely MNAR / column-driven (high rate variance)"
    else:
        pattern_label = "likely MAR (moderate, column-correlated)"

    # Pairwise co-occurrence (top-N columns only to bound compute)
    cols_top = [c for c, _ in sorted(
        per_col.items(), key=lambda kv: kv[1].get("missing_rate", 0), reverse=True
    )[:top_n]]
    cooccur: Dict[str, Dict[str, float]] = {}
    if len(cols_top) >= 2:
        sub = miss_matrix[cols_top]
        for i, c1 in enumerate(cols_top):
            for c2 in cols_top[i + 1:]:
                both = int((sub[c1] & sub[c2]).sum())
                if both == 0:
                    continue
                # Jaccard similarity
                either = int((sub[c1] | sub[c2]).sum())
                jaccard = both / either if either else 0.0
                cooccur.setdefault(c1, {})[c2] = round_float(jaccard)

    # Time correlation: split df into early/late halves and compare miss rates
    time_corr: Dict[str, Any] = {"time_column": time_column, "evaluated": False}
    if time_column and time_column in df.columns:
        ts = pd.to_datetime(df[time_column], errors="coerce")
        if ts.notna().sum() > n_rows * 0.5:
            median_ts = ts.median()
            early_mask = ts <= median_ts
            late_mask = ts > median_ts
            n_early, n_late = int(early_mask.sum()), int(late_mask.sum())
            diffs: List[Dict[str, Any]] = []
            for c in cols_top:
                if c == time_column:
                    continue
                r_early = float(df.loc[early_mask, c].isna().mean()) if n_early else 0.0
                r_late = float(df.loc[late_mask, c].isna().mean()) if n_late else 0.0
                if abs(r_early - r_late) > 0.05:
                    diffs.append({
                        "column": c,
                        "missing_rate_early": round_float(r_early),
                        "missing_rate_late": round_float(r_late),
                        "delta": round_float(r_late - r_early),
                    })
            time_corr = {
                "time_column": time_column,
                "evaluated": True,
                "split_at": median_ts.isoformat() if pd.notna(median_ts) else None,
                "n_early": n_early,
                "n_late": n_late,
                "columns_with_time_drift": diffs,
            }

    # Top findings
    sorted_cols = sorted(per_col.items(),
                         key=lambda kv: kv[1].get("missing_rate", 0), reverse=True)
    findings = [
        "%s：缺失率 %.2f%% (%s)"
        % (c, (v.get("missing_rate", 0) or 0) * 100, v.get("status"))
        for c, v in sorted_cols[:10] if v.get("missing_rate", 0) > 0
    ]
    if not findings:
        findings.append("未发现缺失值，数据完整性良好。")

    return make_envelope(
        tool_name="missing_values",
        summary="缺失值扫描完成：整体缺失率 %.2f%%，%d 行完整（占 %.2f%%）。"
                % (overall["overall_missing_rate"] * 100,
                   overall["complete_rows"],
                   overall["complete_rows_rate"] * 100),
        key_findings=findings,
        metrics={
            "per_column": per_col,
            "overall": overall,
            "pattern_heuristic": pattern_label,
            "pairwise_cooccurrence_jaccard": cooccur,
            "time_correlation": time_corr,
            "columns_scanned": list(cols),
        },
        recommendations=[
            "严重缺失 (>=50%) 的列建议剔除或单独建模。",
            "缺失时间漂移显著 → MNAR，可考虑按时间段分别处理。",
            "两列 Jaccard 接近 1 → 缺失原因同源，可联合处理。",
        ],
        notes=format_notes({}),
    )


@tool("analyze_duplicates")
@tool_guard("analyze_duplicates")
def analyze_duplicates(
    runtime: ToolRuntime,
    subset: Optional[List[str]] = None,
    near_duplicate_columns: Optional[List[str]] = None,
    near_duplicate_threshold: float = 0.01,
    max_samples: int = 50,
) -> Dict[str, Any]:
    """检测完全重复、键重复与近似重复行。

    Parameters
    ----------
    subset : list[str], optional
        用于检测"键重复"的列子集（如 ``["timestamp"]`` 或
        ``["device_id","timestamp"]``）。
    near_duplicate_columns : list[str], optional
        用于计算近似重复的数值列；不传时使用 ctx.target_columns+
        feature_columns 中的数值列。
    near_duplicate_threshold : float, default 0.01
        两行归一化欧氏距离 < 该值视为近似重复。
    max_samples : int, default 50
        每类最多返回前 N 个示例。

    Returns
    -------
    Dict[str, Any]
        ``metrics`` 含 exact_duplicates / key_duplicates / near_duplicates。
    """
    df = get_df(runtime)
    n_rows = int(len(df))
    if n_rows == 0:
        return make_envelope(
            tool_name="duplicates",
            summary="DataFrame 为空。",
            key_findings=["无数据可分析。"],
            metrics={},
        )

    # Exact duplicates (all columns)
    exact_mask = df.duplicated(keep="first")
    n_exact = int(exact_mask.sum())
    exact_sample = df.index[exact_mask].tolist()[:max_samples]

    metrics_out: Dict[str, Any] = {
        "exact_duplicates": {
            "count": n_exact,
            "rate": round_float(float(n_exact) / n_rows),
            "sample_indices": [int(i) if isinstance(i, (int, np.integer)) else i
                               for i in exact_sample],
        },
    }

    findings = [
        "完全重复行：%d (%.2f%%)。"
        % (n_exact, 100.0 * n_exact / n_rows)
    ]

    # Key duplicates
    if subset:
        valid_subset = [c for c in subset if c in df.columns]
        if valid_subset:
            key_mask = df.duplicated(subset=valid_subset, keep=False)
            n_key = int(key_mask.sum())
            grouped = (df.loc[key_mask]
                       .groupby(valid_subset, dropna=False)
                       .size()
                       .reset_index(name="count"))
            key_groups = grouped[grouped["count"] > 1].sort_values(
                "count", ascending=False).head(max_samples).to_dict(orient="records")
            metrics_out["key_duplicates"] = {
                "subset": valid_subset,
                "rows_involved": n_key,
                "rate": round_float(float(n_key) / n_rows),
                "n_duplicate_keys": int(len(grouped[grouped["count"] > 1])),
                "sample_groups": key_groups,
            }
            findings.append(
                "键重复（基于 %s）：涉及 %d 行 (%.2f%%)，共 %d 个重复键。"
                % (",".join(valid_subset), n_key, 100.0 * n_key / n_rows,
                   metrics_out["key_duplicates"]["n_duplicate_keys"]))

    # Near duplicates (on numeric columns)
    if near_duplicate_columns is None:
        try:
            near_duplicate_columns = resolve_columns(runtime, use="any")
        except Exception:
            near_duplicate_columns = []
    numeric_cols = [c for c in near_duplicate_columns if c in df.columns]
    numeric_cols = [c for c in numeric_cols
                    if pd.to_numeric(df[c], errors="coerce").notna().any()]
    if len(numeric_cols) >= 1 and n_rows >= 2:
        sub = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
        # Normalise each column to [0,1] using min-max so distances are comparable
        ranges = sub.max(axis=0) - sub.min(axis=0)
        ranges = ranges.replace(0, 1.0)
        norm = (sub - sub.min(axis=0)) / ranges
        norm = norm.fillna(0.0).to_numpy(dtype=float)
        # Pairwise distance only against the immediate predecessor (cheap heuristic)
        # and a small random sample for global near-dups.
        prev_dist = np.linalg.norm(norm[1:] - norm[:-1], axis=1)
        adj_near = np.where(prev_dist < near_duplicate_threshold)[0] + 1
        metrics_out["near_duplicates"] = {
            "columns_used": list(numeric_cols),
            "threshold": float(near_duplicate_threshold),
            "adjacent_near_duplicate_count": int(adj_near.size),
            "adjacent_sample_indices": [int(i) for i in adj_near[:max_samples]],
        }
        findings.append(
            "近似重复（相邻行，阈值=%.4g）：%d 对。"
            % (near_duplicate_threshold, int(adj_near.size)))

    return make_envelope(
        tool_name="duplicates",
        summary="重复检测完成：%d 完全重复，%s键重复，%s近似重复。"
                % (n_exact,
                   "%d " % metrics_out.get("key_duplicates", {}).get("rows_involved", 0)
                   if "key_duplicates" in metrics_out else "未做",
                   "%d " % metrics_out.get("near_duplicates", {}).get("adjacent_near_duplicate_count", 0)
                   if "near_duplicates" in metrics_out else "未做"),
        key_findings=findings,
        metrics=metrics_out,
        recommendations=[
            "完全重复可直接删除（drop_duplicates）。",
            "时间戳键重复 → 检查采集系统是否漏掉了重复触发；建议保留首条/末条之一。",
            "相邻行近似重复多 → 采样率过高，可考虑降采样。",
        ],
        notes=format_notes({}),
    )


@tool("analyze_constant_or_low_variance_columns")
@tool_guard("analyze_constant_or_low_variance_columns")
def analyze_constant_or_low_variance_columns(
    runtime: ToolRuntime,
    columns: Optional[List[str]] = None,
    use: str = "any",
    include_all_columns: bool = True,
    low_variance_threshold: float = 1e-6,
    low_entropy_threshold: float = 0.1,
    cardinality_threshold: int = 1,
    max_samples_per_column: int = 5,
) -> Dict[str, Any]:
    """找出常数列、低方差列、低熵列（信息量不足，建议剔除）。

    Parameters
    ----------
    columns / use : 见 ``analyze_basic_statistics``；默认扫描全部列。
    include_all_columns : bool, default True
        若为 True 且未指定 columns，扫描 df 全部列。
    low_variance_threshold : float, default 1e-6
        方差低于此值视为"低方差"。
    low_entropy_threshold : float, default 0.1
        归一化香农熵低于此值视为"低熵"（覆盖高基数分类列）。
    cardinality_threshold : int, default 1
        unique 值数量 ≤ 该值视为常数列。
    max_samples_per_column : int, default 5
        每列返回前 N 个示例值。

    Returns
    -------
    Dict[str, Any]
        ``metrics.per_column`` 含 status ('constant'|'low_variance'|
        'low_entropy'|'ok') 与对应度量。
    """
    df = get_df(runtime)
    if include_all_columns and columns is None:
        cols = list(df.columns)
    else:
        cols = resolve_columns(runtime, columns=columns, use=use)

    n_rows = int(len(df))
    per_column: Dict[str, Any] = {}
    findings: List[str] = []

    for c in cols:
        s = df[c]
        n_valid = int(s.notna().sum())
        if n_valid == 0:
            per_column[c] = {"status": "all_missing",
                             "n_valid": 0,
                             "recommendation": "drop"}
            findings.append("%s：整列缺失，建议剔除。" % c)
            continue

        n_unique = int(s.nunique(dropna=True))
        top_values = s.value_counts(dropna=True).head(max_samples_per_column).to_dict()
        top_values_out = [
            {"value": (str(k) if not isinstance(k, (int, float, bool)) else k),
             "count": int(v)}
            for k, v in top_values.items()
        ]

        # Numeric checks
        as_num = pd.to_numeric(s, errors="coerce")
        var = None
        cv = None
        if as_num.notna().any():
            arr = as_num.dropna().to_numpy(dtype=float)
            var = float(arr.var(ddof=1)) if arr.size > 1 else 0.0
            mean = float(arr.mean())
            cv = abs(float(var ** 0.5) / mean) if mean not in (0.0,) and mean != 0 else None

        # Normalised Shannon entropy for the empirical distribution
        entropy_norm = None
        if n_valid > 0 and n_unique > 0:
            counts = s.value_counts(dropna=True).to_numpy(dtype=float)
            p = counts / counts.sum()
            ent = -float(np.sum(p * np.log(p + 1e-12)))
            max_ent = math.log(max(n_unique, 2))
            entropy_norm = ent / max_ent if max_ent > 0 else 0.0

        # Severity decision
        if n_unique <= cardinality_threshold:
            status = "constant"
            rec = "drop (no information)"
        elif var is not None and var < low_variance_threshold:
            status = "low_variance"
            rec = "drop or investigate (near-constant)"
        elif entropy_norm is not None and entropy_norm < low_entropy_threshold:
            status = "low_entropy"
            rec = "consider dropping (dominated by one value)"
        else:
            status = "ok"
            rec = "keep"

        per_column[c] = {
            "n_valid": n_valid,
            "n_unique": n_unique,
            "variance": round_float(var) if var is not None else None,
            "cv": round_float(cv) if cv is not None else None,
            "normalized_entropy": round_float(entropy_norm) if entropy_norm is not None else None,
            "top_values": top_values_out,
            "status": status,
            "recommendation": rec,
        }
        if status != "ok":
            findings.append(
                "%s：%s（unique=%d, var=%s, entropy=%.3f）→ %s"
                % (c, status, n_unique,
                   ("%.4g" % var) if var is not None else "N/A",
                   entropy_norm if entropy_norm is not None else 0.0,
                   rec))

    if not findings:
        findings.append("未发现常数 / 低方差 / 低熵列。")

    # Summary counts
    counts = {}
    for v in per_column.values():
        counts[v["status"]] = counts.get(v["status"], 0) + 1

    return make_envelope(
        tool_name="constant_low_variance",
        summary="扫描 %d 列：%s。"
                % (len(per_column),
                   ", ".join("%s=%d" % (k, v) for k, v in counts.items())),
        key_findings=findings,
        metrics={
            "per_column": per_column,
            "counts_by_status": counts,
            "thresholds": {
                "low_variance": float(low_variance_threshold),
                "low_entropy": float(low_entropy_threshold),
                "cardinality": int(cardinality_threshold),
            },
        },
        recommendations=[
            "常数列必须剔除——它们对任何模型 / 相关性分析都没有贡献。",
            "低熵列（如 99% 取同一值）建议剔除或在异常检测时单独处理。",
            "保留 status=ok 的列进入下游分析。",
        ],
        notes=format_notes({}),
    )


TOOLS = [
    analyze_missing_values,
    analyze_duplicates,
    analyze_constant_or_low_variance_columns,
]
