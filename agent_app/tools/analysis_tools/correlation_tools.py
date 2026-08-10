"""Correlation / relationship-analysis tools.

Three tools that quantify pairwise relationships between numeric columns:

- :func:`analyze_correlation_matrix` — pairwise correlation matrix using
  Pearson / Spearman / Kendall, with a top-N strongest pairs ranking.
- :func:`analyze_cross_correlation` — lagged cross-correlation between a
  target column and one or more feature columns; surfaces lead/lag
  relationships (e.g. furnace temperature vs. downstream product
  quality 30 minutes later).
- :func:`analyze_mutual_information` — non-linear dependency via mutual
  information (sklearn's ``mutual_info_regression`` / ``mutual_info_classif``),
  complementing correlation when relationships are non-monotone.

All tools take ``runtime: ToolRuntime`` for context access; every other
parameter is supplied directly by the LLM.
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
    json_safe,
    make_envelope,
    numeric_frame,
    resolve_columns,
    round_float,
    select_numeric_columns,
    truncate_list,
)

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Tools
# ----------------------------------------------------------------------

@tool("analyze_correlation_matrix")
@tool_guard("analyze_correlation_matrix")
def analyze_correlation_matrix(
    runtime: ToolRuntime,
    columns: Optional[List[str]] = None,
    use: str = "any",
    method: str = "pearson",
    min_abs: float = 0.0,
    top_n: int = 15,
) -> Dict[str, Any]:
    """计算数值列两两相关系数矩阵，并按绝对值排序输出 Top-N 强相关对。

    Parameters
    ----------
    columns / use : 见 ``analyze_basic_statistics``；默认 ``use="any"`` 合并
        target+feature 列。
    method : {"pearson","spearman","kendall"}, default "pearson"
        相关系数类型。Pearson 线性、Spearman 单调、Kendall 秩相关。
    min_abs : float, default 0.0
        输出 Top-N 前的过滤阈值，过滤掉 |r|<min_abs 的弱相关对。
    top_n : int, default 15
        返回前 N 个最强相关对。

    Returns
    -------
    Dict[str, Any]
        ``metrics.matrix`` 为相关系数矩阵（dict-of-dict）；
        ``metrics.top_pairs`` 为 [(col1, col2, r), ...] 列表。
    """
    if method not in {"pearson", "spearman", "kendall"}:
        method = "pearson"

    df = get_df(runtime)
    cols = resolve_columns(runtime, columns=columns, use=use)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if len(numeric_cols) < 2:
        return make_envelope(
            tool_name="correlation_matrix",
            summary="数值列不足 2 个，无法计算相关性。",
            key_findings=["至少需要 2 个数值列。"],
            metrics={"skipped": {"non_numeric": non_numeric}},
        )

    sub, frame_info = numeric_frame(df, numeric_cols, impute="median")
    corr = sub.corr(method=method)
    corr_filled = corr.fillna(0.0)

    pairs: List[Tuple[str, str, float]] = []
    for i, c1 in enumerate(corr.columns):
        for c2 in corr.columns[i + 1:]:
            v = corr.loc[c1, c2]
            if pd.notna(v) and abs(float(v)) >= min_abs:
                pairs.append((c1, c2, float(v)))
    pairs.sort(key=lambda t: abs(t[2]), reverse=True)
    top_pairs = pairs[:top_n]

    findings = [
        "%s ⟷ %s：r=%+.4f" % (a, b, v) for a, b, v in top_pairs[:10]
    ]
    if not findings:
        findings.append("没有满足 |r|≥%.2f 的相关对。" % min_abs)

    # Build a JSON-friendly matrix dict.
    matrix_dict = {
        str(c): {str(c2): round_float(float(corr_filled.loc[c, c2]))
                 for c2 in corr.columns}
        for c in corr.columns
    }

    # Multi-collinearity warning: any pair with |r|>0.9
    high_multicol = [(a, b, v) for a, b, v in pairs if abs(v) > 0.9]

    notes_extras: List[str] = []
    if non_numeric:
        notes_extras.append("非数值列已跳过：%s" % ", ".join(non_numeric))
    if high_multicol:
        notes_extras.append(
            "%d 对 |r|>0.9，存在严重多重共线性：%s"
            % (len(high_multicol),
               ", ".join("%s-%s" % (a, b) for a, b, _ in high_multicol[:5])))

    return make_envelope(
        tool_name="correlation_matrix",
        summary="完成 %d 列 × %d 列的 %s 相关分析（共 %d 对，|r|≥%.2f 的 %d 对）。"
                % (len(numeric_cols), len(numeric_cols), method,
                   len(pairs) + sum(1 for _ in filter(lambda _: False, pairs)),
                   min_abs, len(pairs)),
        key_findings=findings,
        metrics={
            "method": method,
            "n_columns": len(numeric_cols),
            "matrix": matrix_dict,
            "top_pairs": [
                {"a": a, "b": b, "r": round_float(v)} for a, b, v in top_pairs
            ],
            "n_high_multicollinearity": len(high_multicol),
            "min_abs_filter": float(min_abs),
        },
        recommendations=[
            "r>0.9 的变量对建模时只保留其一（PCA 或人工剔除）。",
            "Pearson 与 Spearman 差异显著 → 非线性关系，考虑 mutual_information。",
            "强负相关同样重要，注意观察 r 的符号而非仅绝对值。",
        ],
        notes=format_notes(frame_info, notes_extras),
    )


@tool("analyze_cross_correlation")
@tool_guard("analyze_cross_correlation")
def analyze_cross_correlation(
    runtime: ToolRuntime,
    target_column: str,
    feature_columns: Optional[List[str]] = None,
    max_lag: int = 24,
    direction: str = "both",
) -> Dict[str, Any]:
    """计算目标列与各特征列之间的时滞互相关 (CCF)。

    用于回答"上游变量 X 多少步之后会影响下游 Y"这类工艺问题。

    Parameters
    ----------
    target_column : str
        目标列（响应变量），必填。
    feature_columns : list[str], optional
        要比较的特征列；为空时取 ctx.feature_columns。
    max_lag : int, default 24
        最大滞后步数（含），扫描范围 ``[-max_lag, +max_lag]``。
    direction : {"both","positive","negative"}, default "both"
        ``positive`` 只看 X 滞后 Y（X 领先 Y）；``negative`` 反向。

    Returns
    -------
    Dict[str, Any]
        ``metrics.per_feature`` 含 ``best_lag``、``best_corr``、
        ``lag_corr_curve``（截断到 ±max_lag）。
    """
    if not target_column:
        return make_envelope(
            tool_name="cross_correlation",
            summary="缺少 target_column。",
            key_findings=["必须提供目标列。"],
            metrics={},
        )
    if max_lag < 1:
        max_lag = 1
    if max_lag > 500:
        max_lag = 500
    if direction not in {"both", "positive", "negative"}:
        direction = "both"

    df = get_df(runtime)
    if target_column not in df.columns:
        return make_envelope(
            tool_name="cross_correlation",
            summary="target_column=%r 不在 df 中。" % target_column,
            key_findings=["请检查目标列名。"],
            metrics={},
        )

    if feature_columns is None:
        feature_columns = [c for c in resolve_columns(runtime, use="feature")
                           if c != target_column]
    feature_columns = [c for c in feature_columns
                       if c in df.columns and c != target_column]
    if not feature_columns:
        return make_envelope(
            tool_name="cross_correlation",
            summary="没有可用于互相关的特征列。",
            key_findings=["请显式提供 feature_columns 或检查 ctx.feature_columns。"],
            metrics={},
        )

    y = pd.to_numeric(df[target_column], errors="coerce")
    n = int(len(df))
    if y.notna().sum() < max_lag * 2:
        return make_envelope(
            tool_name="cross_correlation",
            summary="样本量过小（建议 >= 2*max_lag）。",
            key_findings=["请减小 max_lag 或增加数据量。"],
            metrics={"n_samples": n},
        )

    lag_range: List[int]
    if direction == "positive":
        lag_range = list(range(0, max_lag + 1))
    elif direction == "negative":
        lag_range = list(range(-max_lag, 1))
    else:
        lag_range = list(range(-max_lag, max_lag + 1))

    findings: List[str] = []
    per_feature: Dict[str, Any] = {}

    for feat in feature_columns:
        x = pd.to_numeric(df[feat], errors="coerce")
        valid = x.notna() & y.notna()
        if valid.sum() < max_lag * 2:
            per_feature[feat] = {"n_valid": int(valid.sum()),
                                 "note": "样本不足"}
            continue
        xx = x[valid].to_numpy(dtype=float)
        yy = y[valid].to_numpy(dtype=float)
        xx = (xx - xx.mean()) / (xx.std() + 1e-12)
        yy = (yy - yy.mean()) / (yy.std() + 1e-12)

        curve: List[Tuple[int, float]] = []
        for lag in lag_range:
            r = _lagcorr(xx, yy, lag)
            curve.append((lag, r))
        best = max(curve, key=lambda kv: abs(kv[1]))
        per_feature[feat] = {
            "n_valid": int(valid.sum()),
            "best_lag": int(best[0]),
            "best_corr": round_float(best[1]),
            "lag_corr_curve": [
                {"lag": int(l), "corr": round_float(c)} for l, c in curve[:201]
            ],
            "direction": ("X leads Y" if best[0] > 0 else
                          "Y leads X" if best[0] < 0 else "synchronous"),
        }
        findings.append(
            "%s ⟷ %s：最佳滞后=%+d 步，r=%+.4f"
            % (target_column, feat, best[0], best[1]))

    return make_envelope(
        tool_name="cross_correlation",
        summary="完成 %s 与 %d 个特征列的互相关分析（max_lag=%d）。"
                % (target_column, len(per_feature), max_lag),
        key_findings=findings,
        metrics={
            "target_column": target_column,
            "feature_columns": list(per_feature.keys()),
            "max_lag": int(max_lag),
            "direction": direction,
            "per_feature": per_feature,
        },
        recommendations=[
            "best_lag>0 说明 feature 领先 target——可用作预警特征。",
            "整条 lag_corr_curve 接近 0 → 该 feature 与 target 几乎独立。",
            "若互相关在多个滞后上都强，考虑变量本身的周期性。",
        ],
    )


@tool("analyze_mutual_information")
@tool_guard("analyze_mutual_information")
def analyze_mutual_information(
    runtime: ToolRuntime,
    target_column: Optional[str] = None,
    feature_columns: Optional[List[str]] = None,
    n_neighbors: int = 3,
    task_type: str = "auto",
    top_n: int = 15,
) -> Dict[str, Any]:
    """使用 sklearn 估计目标列与各特征列之间的互信息 (MI)。

    用于发现 Pearson/Spearman 难以捕捉的非线性依赖关系。

    Parameters
    ----------
    target_column : str, optional
        目标列；不填时取 ctx.target_columns[0]。
    feature_columns : list[str], optional
        特征列；不填时取 ctx.feature_columns。
    n_neighbors : int, default 3
        KSG 估计器的邻居数（sklearn 默认 3）。
    task_type : {"auto","regression","classification"}, default "auto"
        target 为连续值时用 regression 离散时用 classification。
    top_n : int, default 15
        返回 MI 最高的前 N 个特征。

    Returns
    -------
    Dict[str, Any]
        ``metrics.per_feature`` 为 {feature: mi_score}，``top_features``
        为排序后的前 N 个。
    """
    from sklearn.feature_selection import (
        mutual_info_regression, mutual_info_classif,
    )

    df = get_df(runtime)
    if target_column is None:
        tgts = resolve_columns(runtime, use="target")
        if not tgts:
            return make_envelope(
                tool_name="mutual_information",
                summary="未提供 target_column 且 ctx.target_columns 为空。",
                key_findings=["无法确定目标列。"],
                metrics={},
            )
        target_column = tgts[0]
    if target_column not in df.columns:
        return make_envelope(
            tool_name="mutual_information",
            summary="target_column=%r 不在 df 中。" % target_column,
            key_findings=["请检查目标列名。"],
            metrics={},
        )

    if feature_columns is None:
        feature_columns = [c for c in resolve_columns(runtime, use="feature")
                           if c != target_column]
    feature_columns = [c for c in feature_columns
                       if c in df.columns and c != target_column]
    if not feature_columns:
        return make_envelope(
            tool_name="mutual_information",
            summary="没有可用的特征列。",
            key_findings=["请显式提供 feature_columns。"],
            metrics={},
        )

    sub_y, _ = numeric_frame(df, [target_column], impute="median")
    sub_x, info = numeric_frame(df, feature_columns, impute="median")
    y = sub_y[target_column].to_numpy(dtype=float)
    X = sub_x.to_numpy(dtype=float)

    # Decide task type
    if task_type == "auto":
        n_unique = pd.Series(y).nunique()
        task_type = "classification" if n_unique <= 5 and n_unique / len(y) < 0.05 else "regression"

    try:
        if task_type == "classification":
            mi = mutual_info_classif(X, y, n_neighbors=n_neighbors, random_state=0)
        else:
            mi = mutual_info_regression(X, y, n_neighbors=n_neighbors, random_state=0)
    except Exception as exc:
        logger.warning("mutual_info failed: %s", exc)
        return make_envelope(
            tool_name="mutual_information",
            summary="互信息估计失败：%s: %s" % (type(exc).__name__, exc),
            key_findings=["请尝试更换 n_neighbors 或检查输入。"],
            metrics={"error": str(exc)},
        )

    pairs = list(zip(feature_columns, [float(v) for v in mi]))
    pairs.sort(key=lambda kv: kv[1], reverse=True)
    top = pairs[:top_n]

    findings = [
        "%s：MI=%.4f" % (f, v) for f, v in top[:10]
    ]

    return make_envelope(
        tool_name="mutual_information",
        summary="完成 target=%s 与 %d 个特征列的互信息估计（task=%s）。"
                % (target_column, len(feature_columns), task_type),
        key_findings=findings,
        metrics={
            "target_column": target_column,
            "task_type": task_type,
            "n_neighbors": int(n_neighbors),
            "per_feature": {f: round_float(v) for f, v in pairs},
            "top_features": [{"feature": f, "mi": round_float(v)} for f, v in top],
        },
        recommendations=[
            "MI 高但 Pearson 低 → 非线性关系，适合树模型 / 神经网络。",
            "MI 与 Pearson 都高 → 线性特征已足够，可用线性模型。",
            "MI 接近 0 的特征可在建模前剔除。",
        ],
        notes=format_notes(info),
    )


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------

def _lagcorr(x: np.ndarray, y: np.ndarray, lag: int) -> float:
    """Pearson correlation between X[t] and Y[t+lag], NaN-safe."""
    n = min(x.size, y.size)
    if lag >= 0:
        a = x[:n - lag] if lag > 0 else x[:n]
        b = y[lag:n] if lag > 0 else y[:n]
    else:
        lag_abs = -lag
        a = x[lag_abs:n]
        b = y[:n - lag_abs]
    if a.size < 3:
        return 0.0
    try:
        r, _ = sp_stats.pearsonr(a, b)
        if not math.isfinite(float(r)):
            return 0.0
        return float(r)
    except Exception:
        return 0.0


TOOLS = [
    analyze_correlation_matrix,
    analyze_cross_correlation,
    analyze_mutual_information,
]
