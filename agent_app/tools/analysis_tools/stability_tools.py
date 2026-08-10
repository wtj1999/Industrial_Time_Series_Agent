"""Process-stability and SPC (statistical process control) tools.

Three tools focused on how stable an industrial process is over the
observed window:

- :func:`analyze_stability` — overall + rolling CV / std / spread, with
  a qualitative stability grade. Good "first pass" answer to "is this
  process stable?".
- :func:`analyze_process_capability` — Cp / Cpk / Pp / Ppk against user-
  supplied spec limits, plus defect-rate (PPM) extrapolation. The
  standard Six-Sigma / quality-engineering capability indices.
- :func:`analyze_control_chart` — Shewhart X̄ / individuals control
  limits (3σ) and Western Electric rule violations. Surfaces which
  specific rule fired and where, so the LLM can root-cause.

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


# Cap for chart-only arrays emitted by tools with long internal series
# (control chart line, ...). Matches the anomaly-chart budget.
_CHART_MAX_POINTS = 1500


def _downsample_with_indices(values, highlight_indices, max_points):
    """Stride-downsample ``values`` and remap ``highlight_indices`` onto the
    sampled grid. Returns ``(sampled_values, sampled_highlight_positions)``
    where ``sampled_values`` is a JSON-safe list (NaN/Inf→None) and
    ``sampled_highlight_positions`` are 0-based indices into it.

    Used by ``analyze_control_chart`` to ship the data line + the violation
    positions in one compact payload for the frontend chart extractor.
    """
    import math

    n = int(len(values))
    if n == 0:
        return [], []
    if n <= max_points:
        out_vals = []
        for v in values:
            try:
                f = float(v)
            except (TypeError, ValueError):
                out_vals.append(None)
                continue
            out_vals.append(f if math.isfinite(f) else None)
        return out_vals, [int(i) for i in highlight_indices
                          if 0 <= i < n]

    stride = int(math.ceil(n / max_points))
    sampled_vals = []
    for v in values[::stride]:
        try:
            f = float(v)
        except (TypeError, ValueError):
            sampled_vals.append(None)
            continue
        sampled_vals.append(f if math.isfinite(f) else None)

    highlight_set = set()
    for i in highlight_indices:
        if not (0 <= i < n):
            continue
        highlight_set.add(min(int(i) // stride, len(sampled_vals) - 1))
    return sampled_vals, sorted(highlight_set)


# ----------------------------------------------------------------------
# Tools
# ----------------------------------------------------------------------

@tool("analyze_stability")
@tool_guard("analyze_stability")
def analyze_stability(
    runtime: ToolRuntime,
    columns: Optional[List[str]] = None,
    use: str = "target",
    window: int = 30,
    drift_threshold: float = 0.1,
) -> Dict[str, Any]:
    """评估过程稳定性：CV、滚动 std、滚动均值漂移、稳定性等级。

    Parameters
    ----------
    columns / use : 见 ``analyze_basic_statistics``。
    window : int, default 30
        滚动窗口长度（行数）。
    drift_threshold : float, default 0.1
        滚动均值首末相对差值超过该阈值时判为"漂移"。

    Returns
    -------
    Dict[str, Any]
        ``metrics.per_column`` 含 cv / rolling_std_mean / drift_ratio /
        stability_grade ('stable'|'acceptable'|'unstable')。
    """
    if window < 2:
        window = 2

    df = get_df(runtime)
    cols = resolve_columns(runtime, columns=columns, use=use)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="stability",
            summary="无可用数值列。",
            key_findings=["无法做稳定性分析。"],
            metrics={"skipped": {"non_numeric": non_numeric}},
        )

    findings: List[str] = []
    per_column: Dict[str, Any] = {}

    for col in numeric_cols:
        s, _ = numeric_series(df, col, dropna=True)
        if s.size < window:
            per_column[col] = {"n_valid": int(s.size), "note": "样本不足"}
            continue
        arr = s.to_numpy(dtype=float)
        mean = float(arr.mean())
        std = float(arr.std(ddof=1)) if arr.size > 1 else 0.0
        cv = float(std / mean) if mean not in (0.0,) and mean != 0 else None

        rolling = pd.Series(arr).rolling(window=window, min_periods=window)
        roll_mean = rolling.mean().to_numpy()
        roll_std = rolling.std().to_numpy()
        valid_rm = roll_mean[np.isfinite(roll_mean)]
        valid_rs = roll_std[np.isfinite(roll_std)]

        drift_ratio = None
        if valid_rm.size >= 2 and mean != 0:
            drift_ratio = float((valid_rm[-1] - valid_rm[0]) / abs(mean))

        rolling_std_mean = float(np.nanmean(roll_std)) if valid_rs.size else None
        rolling_std_max = float(np.nanmax(roll_std)) if valid_rs.size else None

        # Stability grade
        cv_val = abs(cv) if cv is not None else float("inf")
        drift_val = abs(drift_ratio) if drift_ratio is not None else 0.0
        if cv_val < 0.1 and drift_val < drift_threshold:
            grade = "stable"
        elif cv_val < 0.3 and drift_val < 2 * drift_threshold:
            grade = "acceptable"
        else:
            grade = "unstable"

        per_column[col] = {
            "n_valid": int(arr.size),
            "window": int(window),
            "mean": round_float(mean),
            "std": round_float(std),
            "cv": round_float(cv) if cv is not None else None,
            "rolling_std_mean": round_float(rolling_std_mean) if rolling_std_mean is not None else None,
            "rolling_std_max": round_float(rolling_std_max) if rolling_std_max is not None else None,
            "rolling_mean_first": round_float(float(valid_rm[0])) if valid_rm.size else None,
            "rolling_mean_last": round_float(float(valid_rm[-1])) if valid_rm.size else None,
            "drift_ratio": round_float(drift_ratio) if drift_ratio is not None else None,
            "stability_grade": grade,
        }
        findings.append(
            "%s：CV=%.3f，漂移=%.3f → %s。"
            % (col, cv_val, drift_val, grade))

    notes_extras: List[str] = []
    if non_numeric:
        notes_extras.append("非数值列已跳过：%s" % ", ".join(non_numeric))

    return make_envelope(
        tool_name="stability",
        summary="完成 %d 列的稳定性评估（window=%d）。"
                % (len(numeric_cols), window),
        key_findings=findings,
        metrics={
            "per_column": per_column,
            "window": int(window),
            "drift_threshold": float(drift_threshold),
        },
        recommendations=[
            "稳定性等级 unstable 时优先排查工艺参数变化或设备劣化。",
            "drift_ratio 大但 CV 小 → 缓慢漂移；建议结合 change_point 工具找漂移起点。",
            "rolling_std_max 远大于 rolling_std_mean → 突发波动；与 variance_change 工具交叉。",
        ],
        notes=format_notes({"skipped_non_numeric": non_numeric}, notes_extras),
    )


@tool("analyze_process_capability")
@tool_guard("analyze_process_capability")
def analyze_process_capability(
    runtime: ToolRuntime,
    usl: Optional[float] = None,
    lsl: Optional[float] = None,
    target: Optional[float] = None,
    columns: Optional[List[str]] = None,
    use: str = "target",
) -> Dict[str, Any]:
    """计算过程能力指数 Cp / Cpk / Pp / Ppk 与缺陷率估计。

    必须提供至少一个规格限 (USL / LSL)。

    Parameters
    ----------
    usl / lsl / target : float, optional
        规格上 / 下限与目标值。三者至少有一个非空。
    columns / use : 见 ``analyze_basic_statistics``。

    Returns
    -------
    Dict[str, Any]
        ``metrics.per_column`` 含 cp/cpk/pp/ppk、sigma_level、
        expected_ppm_defects。
    """
    if usl is None and lsl is None:
        return make_envelope(
            tool_name="process_capability",
            summary="必须提供至少一个规格限 (usl 或 lsl)。",
            key_findings=["无法计算过程能力指数。"],
            metrics={},
        )

    df = get_df(runtime)
    cols = resolve_columns(runtime, columns=columns, use=use)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="process_capability",
            summary="无可用数值列。",
            key_findings=["无法计算能力指数。"],
            metrics={"skipped": {"non_numeric": non_numeric}},
        )

    findings: List[str] = []
    per_column: Dict[str, Any] = {}

    for col in numeric_cols:
        s, _ = numeric_series(df, col, dropna=True)
        if s.size < 10:
            per_column[col] = {"n_valid": int(s.size), "note": "样本不足"}
            continue
        arr = s.to_numpy(dtype=float)
        mu = float(arr.mean())
        # Within-subgroup std via moving range (for Cp/Cpk) — common in SPC.
        # Treat the whole series as a single subgroup when no subgroup info given:
        # use sample std for both indices (Pp/Ppk definition), then inflate by
        # the moving-range estimate to obtain Cp/Cpk.
        sigma_overall = float(arr.std(ddof=1))
        diffs = np.abs(np.diff(arr))
        mr_bar = float(diffs.mean()) if diffs.size else sigma_overall
        sigma_within = mr_bar / 1.128 if mr_bar > 0 else sigma_overall

        result: Dict[str, Any] = {
            "n_valid": int(arr.size),
            "mean": round_float(mu),
            "sigma_overall": round_float(sigma_overall),
            "sigma_within": round_float(sigma_within),
            "usl": round_float(usl) if usl is not None else None,
            "lsl": round_float(lsl) if lsl is not None else None,
            "target": round_float(target) if target is not None else None,
        }

        # Cp / Cpk (within-subgroup)
        if usl is not None and lsl is not None and sigma_within > 0:
            cp = (usl - lsl) / (6.0 * sigma_within)
            cpu = (usl - mu) / (3.0 * sigma_within)
            cpl = (mu - lsl) / (3.0 * sigma_within)
            cpk = min(cpu, cpl)
            result["cp"] = round_float(cp)
            result["cpk"] = round_float(cpk)
            result["cpu"] = round_float(cpu)
            result["cpl"] = round_float(cpl)
        # Pp / Ppk (overall)
        if usl is not None and lsl is not None and sigma_overall > 0:
            pp = (usl - lsl) / (6.0 * sigma_overall)
            ppu = (usl - mu) / (3.0 * sigma_overall)
            ppl = (mu - lsl) / (3.0 * sigma_overall)
            ppk = min(ppu, ppl)
            result["pp"] = round_float(pp)
            result["ppk"] = round_float(ppk)
        # One-sided indices
        if usl is not None and lsl is None and sigma_within > 0:
            result["cpu"] = round_float((usl - mu) / (3.0 * sigma_within))
        if lsl is not None and usl is None and sigma_within > 0:
            result["cpl"] = round_float((mu - lsl) / (3.0 * sigma_within))

        # Sigma level (use Cpk or Ppk)
        capability_index = result.get("cpk") or result.get("cpu") or result.get("cpl")
        if capability_index is not None:
            result["sigma_level"] = round_float(float(capability_index) * 3.0)

        # Expected PPM defective under normality assumption
        if sigma_overall > 0:
            from scipy import stats as sp_stats
            p_above = (1.0 - sp_stats.norm.cdf((usl - mu) / sigma_overall)) if usl is not None else 0.0
            p_below = sp_stats.norm.cdf((lsl - mu) / sigma_overall) if lsl is not None else 0.0
            result["expected_ppm_defects"] = round_float(float((p_above + p_below) * 1e6))

        per_column[col] = result
        findings.append(
            "%s：Cpk=%s，σ=%s → %s。"
            % (col,
               ("%.3f" % result["cpk"]) if "cpk" in result else "N/A",
               ("%.2f" % result["sigma_level"]) if "sigma_level" in result else "N/A",
               "capable" if (result.get("cpk") is not None and result["cpk"] >= 1.33) else
               "marginal" if (result.get("cpk") is not None and result["cpk"] >= 1.0) else "not capable"))

    notes_extras: List[str] = []
    if non_numeric:
        notes_extras.append("非数值列已跳过：%s" % ", ".join(non_numeric))

    return make_envelope(
        tool_name="process_capability",
        summary="完成 %d 列的过程能力分析（usl=%s, lsl=%s）。"
                % (len(numeric_cols), usl, lsl),
        key_findings=findings,
        metrics={
            "per_column": per_column,
            "usl": usl, "lsl": lsl, "target": target,
        },
        recommendations=[
            "Cpk≥1.33 通常被视为 capable（4σ 水平），Cpk≥1.67 为高质量（5σ）。",
            "Cpk 与 Ppk 差距大 → 过程不稳定（短期可控但长期偏移），结合 stability 评估。",
            "PPM 缺陷率假设正态，非正态时需用百分位法或 Box-Cox 变换。",
        ],
        notes=format_notes({"skipped_non_numeric": non_numeric}, notes_extras),
    )


@tool("analyze_control_chart")
@tool_guard("analyze_control_chart")
def analyze_control_chart(
    runtime: ToolRuntime,
    columns: Optional[List[str]] = None,
    use: str = "target",
    sigma_width: float = 3.0,
    subgroup_size: int = 1,
    apply_rules: Optional[List[str]] = None,
    window: int = 30,
) -> Dict[str, Any]:
    """Shewhart 控制图分析 + Western Electric 规则违例。

    支持单值图（``subgroup_size=1``）与子组均值图（>1 时按子组聚合）。
    默认应用 Western Electric Rules 1/2/3/4，输出每条规则的违例位置。

    Parameters
    ----------
    columns / use : 见 ``analyze_basic_statistics``。
    sigma_width : float, default 3.0
        控制限宽度（3σ 标准控制限；可改 2σ 用于预警）。
    subgroup_size : int, default 1
        子组大小。>1 时按非重叠子组聚合为均值。
    apply_rules : list[str], optional
        启用的 Western Electric 规则，默认 ['rule1','rule2','rule3','rule4']。
    window : int, default 30
        规则 3/4 所需的连续点数（默认 6/8/14/15）。

    Returns
    -------
    Dict[str, Any]
        ``metrics.per_column`` 含 center_line/ucl/lcl 与每条规则的
        violations（行索引列表）。
    """
    if apply_rules is None:
        apply_rules = ["rule1", "rule2", "rule3", "rule4"]
    if sigma_width <= 0:
        sigma_width = 3.0
    if subgroup_size < 1:
        subgroup_size = 1

    df = get_df(runtime)
    cols = resolve_columns(runtime, columns=columns, use=use)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="control_chart",
            summary="无可用数值列。",
            key_findings=["无法做控制图分析。"],
            metrics={"skipped": {"non_numeric": non_numeric}},
        )

    findings: List[str] = []
    per_column: Dict[str, Any] = {}

    for col in numeric_cols:
        s, _ = numeric_series(df, col, dropna=True)
        if s.size < 10:
            per_column[col] = {"n_valid": int(s.size), "note": "样本不足"}
            continue

        # Subgroup aggregation
        if subgroup_size > 1:
            arr = s.to_numpy(dtype=float)
            n_groups = arr.size // subgroup_size
            arr = arr[:n_groups * subgroup_size].reshape(n_groups, subgroup_size).mean(axis=1)
            agg_label = "subgroup_mean(n=%d)" % subgroup_size
            indices = (s.index[:n_groups * subgroup_size]
                       .to_numpy().reshape(n_groups, subgroup_size)[:, 0])
        else:
            arr = s.to_numpy(dtype=float)
            indices = s.index.to_numpy()
            agg_label = "individuals"

        # Control limits: estimate sigma via moving range (industry standard)
        if subgroup_size == 1:
            mr = np.abs(np.diff(arr))
            sigma = mr.mean() / 1.128 if mr.size else float(arr.std(ddof=1))
        else:
            sigma = float(arr.std(ddof=1))
        center = float(arr.mean())
        ucl = center + sigma_width * sigma
        lcl = center - sigma_width * sigma
        if sigma <= 0:
            per_column[col] = {"note": "sigma=0，所有点相同"}
            continue

        violations = western_electric_rules(
            arr, center, sigma, sigma_width=sigma_width,
            rules=apply_rules, window=window)

        # Map back to original df indices
        rule_violation_indices: Dict[str, List[int]] = {}
        for rule, positions in violations.items():
            mapped = [int(indices[p]) for p in positions if 0 <= p < indices.size]
            rule_violation_indices[rule] = mapped[:200]

        any_violation_idx = sorted({i for lst in rule_violation_indices.values() for i in lst})

        # Downsample the (possibly subgroup-aggregated) series for the
        # frontend control chart. Stride-sampled with NaN→None coercion;
        # violation positions are recomputed on the sampled grid so the
        # red dots stay aligned with the rendered line.
        chart_values, chart_violation_idx = _downsample_with_indices(
            arr, any_violation_idx, _CHART_MAX_POINTS)

        per_column[col] = {
            "n_points": int(arr.size),
            "agg": agg_label,
            "sigma_width": float(sigma_width),
            "center_line": round_float(center),
            "ucl": round_float(ucl),
            "lcl": round_float(lcl),
            "sigma": round_float(sigma),
            "rule_violation_counts": {r: len(v) for r, v in rule_violation_indices.items()},
            "rule_violation_indices": rule_violation_indices,
            "all_violation_indices": any_violation_idx[:500],
            "n_total_violations": len(any_violation_idx),
            # Visualisation-only: the actual data line + sampled violation
            # positions on that grid. LLM can ignore; chart extractor in
            # analysis_agent reads these to render the Shewhart chart.
            "chart_series": {
                "values": chart_values,
                "violation_indices": chart_violation_idx,
                "downsampled": len(arr) > _CHART_MAX_POINTS,
                "original_n": int(len(arr)),
            },
        }
        findings.append(
            "%s：控制限=[%.4g, %.4g]，违例 %d 个点（rule1=%d, rule2=%d, rule3=%d, rule4=%d）。"
            % (col, lcl, ucl, len(any_violation_idx),
               len(rule_violation_indices.get("rule1", [])),
               len(rule_violation_indices.get("rule2", [])),
               len(rule_violation_indices.get("rule3", [])),
               len(rule_violation_indices.get("rule4", []))))

    notes_extras: List[str] = []
    if non_numeric:
        notes_extras.append("非数值列已跳过：%s" % ", ".join(non_numeric))

    return make_envelope(
        tool_name="control_chart",
        summary="完成 %d 列的 Shewhart 控制图分析（σ=%.1f, rules=%s）。"
                % (len(numeric_cols), sigma_width, ",".join(apply_rules)),
        key_findings=findings,
        metrics={
            "per_column": per_column,
            "sigma_width": float(sigma_width),
            "subgroup_size": int(subgroup_size),
            "rules_applied": list(apply_rules),
        },
        recommendations=[
            "Rule 1（单点 3σ 外）=强信号，立即排查；Rule 2/3/4=模式信号，提示系统性偏移。",
            "违例聚集在某个时间段 → 与 change_point / variance_change 工具交叉验证。",
            "持续 Rule 4（连续 8 点同侧）说明过程已偏移，控制限需要重新计算。",
        ],
        notes=format_notes({"skipped_non_numeric": non_numeric}, notes_extras),
    )


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------

def western_electric_rules(
    arr: np.ndarray,
    center: float,
    sigma: float,
    sigma_width: float = 3.0,
    rules: Optional[List[str]] = None,
    window: int = 30,
) -> Dict[str, List[int]]:
    """Apply Western Electric rules; return positions flagged per rule."""
    if sigma <= 0 or arr.size == 0:
        return {}
    if rules is None:
        rules = ["rule1", "rule2", "rule3", "rule4"]

    deviations = (arr - center) / sigma
    out: Dict[str, List[int]] = {}

    if "rule1" in rules:
        out["rule1"] = [int(i) for i in np.where(np.abs(deviations) > sigma_width)[0]]

    if "rule2" in rules:
        # 9 (or window-driven: 8) consecutive points on the same side
        run_len = 9 if window >= 30 else 8
        out["rule2"] = _find_runs(deviations > 0, run_len) + _find_runs(deviations < 0, run_len)
        out["rule2"].sort()

    if "rule3" in rules:
        # 6 consecutive points steadily increasing or decreasing
        out["rule3"] = _find_trend(arr, 6)

    if "rule4" in rules:
        # 14 consecutive points alternating up/down (no obvious pattern)
        out["rule4"] = _find_alternating(arr, 14)

    return out


def _find_runs(boolean: np.ndarray, run_len: int) -> List[int]:
    """Return the position of the *last* point of each qualifying run."""
    out: List[int] = []
    count = 0
    prev = False
    for i, v in enumerate(boolean):
        if v == prev:
            count += 1
        else:
            count = 1
            prev = bool(v)
        if v and count >= run_len:
            out.append(i)
    return out


def _find_trend(arr: np.ndarray, n: int) -> List[int]:
    """Return indices ending a run of ``n`` consecutive increasing/decreasing steps."""
    out: List[int] = []
    if arr.size < n:
        return out
    diffs = np.sign(np.diff(arr))
    i = 0
    while i <= diffs.size - n + 1:
        window = diffs[i:i + n - 1]
        if np.all(window == 1) or np.all(window == -1):
            out.append(i + n - 1)
            i += n  # skip to avoid overlap
        else:
            i += 1
    return out


def _find_alternating(arr: np.ndarray, n: int) -> List[int]:
    """Return indices ending a run of ``n`` consecutive alternating signs."""
    out: List[int] = []
    if arr.size < n:
        return out
    diffs = np.sign(np.diff(arr))
    i = 0
    while i <= diffs.size - n + 2:
        window = diffs[i:i + n - 1]
        if np.all(window != 0) and (
            np.all(window[::2] == window[0]) and np.all(window[1::2] == window[1])
            and window[0] != window[1]
        ):
            out.append(i + n - 2)
            i += n - 1
        else:
            i += 1
    return out


TOOLS = [
    analyze_stability,
    analyze_process_capability,
    analyze_control_chart,
]
