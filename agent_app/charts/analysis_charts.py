"""Analysis-chart payload extraction.

Consumes the ``tool_calls`` list produced by
:func:`agents.base_agent.extract_tool_calls` (one record per tool
invocation, with the parsed tool ``result`` already attached), finds the
**last** analysis-tool result, and converts it into a frontend-ready
chart payload tagged with ``chart_type``.

The frontend dispatches on ``chart_type`` via a registry (see
``frontend/src/components/analysis_chart/``), so adding a new chart is:

1. add a ``_build_*`` function here
2. register it in :data:`_CHART_BUILDERS`
3. add a TS type + a React component on the frontend

Currently covers Tier-1 charts plus model-based root-cause analysis:

- ``correlation_heatmap``  ← analyze_correlation_matrix
- ``histogram``            ← analyze_histogram
- ``decomposition``        ← decompose_time_series
- ``control_chart``        ← analyze_control_chart
- ``changepoint``          ← detect_mean_change_points
- ``acf``                  ← analyze_autocorrelation
- ``catboost_root_cause``  ← analyze_root_causes_catboost

Multi-column contract
---------------------
Analysis tools compute metrics for EVERY column in ``target_columns``
(laid out in ``metrics.per_column``). The chart payload preserves that
multi-column data: each builder emits an ``active_column`` (the first
chartable column, used as the initial selection) plus a ``columns`` dict
keyed by column name whose values carry the SAME render fields the old
single-column payload used to put at the top level. The frontend card
component owns a small ``useState`` for the active column and renders
``columns[active]``; a chip row lets the user switch columns locally
without re-calling the backend.

Per the user-facing contract we only return ONE chart *card* per turn
(the most recent analysis-tool result). Multi-chart-per-turn support
can be added later by walking ``tool_calls`` in order instead of
reversed.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ._common import json_safe

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------- #
# Public entry point
# ---------------------------------------------------------------------- #

def extract_analysis_chart(
    tool_calls: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Return the chart payload for the **last** analysis tool call in
    ``tool_calls``, or ``None`` when no chartable tool ran this turn.

    ``tool_calls`` is the output of
    :func:`agents.base_agent.extract_tool_calls`: each entry has the
    shape ``{"tool", "args", "result", "tool_call_id"}`` where ``result``
    is the already-parsed tool output dict (the analysis envelope with
    ``task_type`` / ``tool_name`` / ``metrics`` / ``summary``).
    """
    for call in reversed(tool_calls):
        payload = call.get("result") if isinstance(call, dict) else None
        if not isinstance(payload, dict):
            continue
        if payload.get("task_type") != "analysis":
            continue
        tool_name = payload.get("tool_name")
        builder = _CHART_BUILDERS.get(tool_name)
        if builder is None:
            continue
        try:
            chart = builder(payload)
        except Exception as exc:
            logger.warning(
                "analysis chart builder %s failed: %s", tool_name, exc,
                exc_info=True,
            )
            continue
        if chart is not None:
            return chart
    return None


# ---------------------------------------------------------------------- #
# Tier-1 builders
# ---------------------------------------------------------------------- #

def _build_correlation_heatmap(envelope: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """analyze_correlation_matrix → correlation_heatmap.

    Inherently multi-column: the matrix already covers every column, so
    this builder doesn't follow the ``active_column`` + ``columns``
    pattern — it returns the full matrix at the top level.

    Source shape (``metrics``):
        matrix: {col_a: {col_a: 1.0, col_b: -0.3, ...}, ...}
        top_pairs: [{a, b, r}, ...]
        method: "pearson" | "spearman" | "kendall"
    """
    metrics = envelope.get("metrics") or {}
    matrix = metrics.get("matrix")
    if not isinstance(matrix, dict) or not matrix:
        return None

    columns = list(matrix.keys())
    # Normalise: matrix[a][b] is the correlation. Each row must be a dict.
    norm_rows: List[Dict[str, Any]] = []
    for c1 in columns:
        row = matrix.get(c1) or {}
        if not isinstance(row, dict):
            row = {}
        norm_rows.append({
            "column": c1,
            "values": [json_safe(row.get(c2)) for c2 in columns],
        })

    return {
        "chart_type": "correlation_heatmap",
        "tool_name": "analyze_correlation_matrix",
        "title": "%s 相关性矩阵" % (metrics.get("method", "pearson")).title(),
        "summary": envelope.get("summary"),
        "columns": columns,
        "rows": norm_rows,
        "method": metrics.get("method", "pearson"),
        "n_columns": int(metrics.get("n_columns") or len(columns)),
        "top_pairs": [
            {
                "a": p.get("a"),
                "b": p.get("b"),
                "r": json_safe(p.get("r")),
            }
            for p in (metrics.get("top_pairs") or [])[:15]
        ],
        "n_high_multicollinearity": int(metrics.get("n_high_multicollinearity") or 0),
    }


def _build_histogram(envelope: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """analyze_histogram → histogram chart, one entry per column.

    Source shape (``metrics.per_column[col]``):
        bin_edges, counts, density, cumulative, top_bins,
        concentration_ratio_top1, bin_strategy
    """
    per_column = (envelope.get("metrics") or {}).get("per_column") or {}
    columns: Dict[str, Dict[str, Any]] = {}
    active_column: Optional[str] = None

    for col, entry in per_column.items():
        if not isinstance(entry, dict):
            continue
        bin_edges = entry.get("bin_edges") or []
        counts = entry.get("counts") or []
        if len(bin_edges) < 2 or not counts:
            continue

        bins = []
        for i, cnt in enumerate(counts):
            lo = bin_edges[i] if i < len(bin_edges) else None
            hi = bin_edges[i + 1] if i + 1 < len(bin_edges) else None
            bins.append({
                "index": i,
                "range": [json_safe(lo), json_safe(hi)],
                "center": json_safe((float(lo) + float(hi)) / 2.0)
                          if lo is not None and hi is not None else None,
                "count": int(cnt) if cnt is not None else 0,
                "density": json_safe(entry.get("density", [None])[i])
                           if i < len(entry.get("density") or []) else None,
            })

        columns[col] = {
            "title": "%s 直方图" % col,
            "bins": bins,
            "bin_count": int(entry.get("bin_count") or len(counts)),
            "bin_strategy": entry.get("bin_strategy", "equal_width"),
            "cumulative": [json_safe(v) for v in (entry.get("cumulative") or [])],
            "concentration_ratio_top1": json_safe(entry.get("concentration_ratio_top1")),
            "n_valid": int(entry.get("n_valid") or 0),
        }
        if active_column is None:
            active_column = col

    if not columns or active_column is None:
        return None

    return {
        "chart_type": "histogram",
        "tool_name": "analyze_histogram",
        "summary": envelope.get("summary"),
        "active_column": active_column,
        "columns": columns,
    }


def _build_decomposition(envelope: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """decompose_time_series → 4-panel decomposition chart, one entry per column.

    Source shape (``metrics.per_column[col]``):
        chart_series: {observed, trend, seasonal, residual, downsampled, original_n}
        strength_trend, strength_seasonal, period, method, model
    """
    per_column = (envelope.get("metrics") or {}).get("per_column") or {}
    columns: Dict[str, Dict[str, Any]] = {}
    active_column: Optional[str] = None

    for col, entry in per_column.items():
        if not isinstance(entry, dict):
            continue
        chart_series = entry.get("chart_series") or {}
        obs = chart_series.get("observed")
        if not isinstance(obs, list) or not obs:
            continue

        columns[col] = {
            "title": "%s 时序分解" % col,
            "observed": obs,
            "trend": chart_series.get("trend") or [],
            "seasonal": chart_series.get("seasonal") or [],
            "residual": chart_series.get("residual") or [],
            "n_points": len(obs),
            "downsampled": bool(chart_series.get("downsampled")),
            "original_n": int(chart_series.get("original_n") or len(obs)),
            "period": json_safe(entry.get("period")),
            "method": entry.get("method", "stl"),
            "model": entry.get("model", "additive"),
            "strength_trend": json_safe(entry.get("strength_trend")),
            "strength_seasonal": json_safe(entry.get("strength_seasonal")),
        }
        if active_column is None:
            active_column = col

    if not columns or active_column is None:
        return None

    return {
        "chart_type": "decomposition",
        "tool_name": "decompose_time_series",
        "summary": envelope.get("summary"),
        "active_column": active_column,
        "columns": columns,
    }


def _build_control_chart(envelope: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """analyze_control_chart → Shewhart control chart, one entry per column.

    Source shape (``metrics.per_column[col]``):
        chart_series: {values, violation_indices, downsampled, original_n}
        center_line, ucl, lcl, sigma, sigma_width, agg
        rule_violation_counts, n_total_violations
    """
    per_column = (envelope.get("metrics") or {}).get("per_column") or {}
    columns: Dict[str, Dict[str, Any]] = {}
    active_column: Optional[str] = None

    for col, entry in per_column.items():
        if not isinstance(entry, dict):
            continue
        chart_series = entry.get("chart_series") or {}
        values = chart_series.get("values")
        if not isinstance(values, list) or not values:
            continue

        sigma_width = json_safe(entry.get("sigma_width")) or 3.0
        columns[col] = {
            "title": "%s 控制图 (σ=%.1f)" % (col, float(sigma_width)),
            "values": values,
            "violation_indices": list(chart_series.get("violation_indices") or []),
            "n_points": len(values),
            "downsampled": bool(chart_series.get("downsampled")),
            "original_n": int(chart_series.get("original_n") or len(values)),
            "center_line": json_safe(entry.get("center_line")),
            "ucl": json_safe(entry.get("ucl")),
            "lcl": json_safe(entry.get("lcl")),
            "sigma": json_safe(entry.get("sigma")),
            "sigma_width": json_safe(entry.get("sigma_width")),
            "agg": entry.get("agg", "individuals"),
            "rule_violation_counts": dict(entry.get("rule_violation_counts") or {}),
            "n_total_violations": int(entry.get("n_total_violations") or 0),
        }
        if active_column is None:
            active_column = col

    if not columns or active_column is None:
        return None

    return {
        "chart_type": "control_chart",
        "tool_name": "analyze_control_chart",
        "summary": envelope.get("summary"),
        "active_column": active_column,
        "columns": columns,
    }


def _build_changepoint(envelope: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """detect_mean_change_points → step chart of segment means + change-point
    reference lines, one entry per column.

    Source shape (``metrics.per_column[col]``):
        segments: [{start, end, length, mean, std}, ...]
        change_points: [{index, delta_mean, p_value, confidence, ...}, ...]
        n_change_points

    Note: this tool does NOT expose the raw series. We render the segment
    means as a step line + vertical lines at each change point — a
    faithful summary of what the algorithm actually found.
    """
    per_column = (envelope.get("metrics") or {}).get("per_column") or {}
    columns: Dict[str, Dict[str, Any]] = {}
    active_column: Optional[str] = None

    for col, entry in per_column.items():
        if not isinstance(entry, dict):
            continue
        segments = entry.get("segments") or []
        change_points = entry.get("change_points") or []
        if not segments:
            continue

        # Build a step-line series: at each segment's [start, end] the
        # value is that segment's mean. This gives a flat-topped
        # staircase that visualises the segmentation even without the
        # raw data.
        step_points: List[Dict[str, Any]] = []
        for seg in segments:
            start = int(seg.get("start", 0))
            end = int(seg.get("end", start))
            mean = json_safe(seg.get("mean"))
            step_points.append({"x": start, "y": mean, "kind": "start"})
            step_points.append({"x": end, "y": mean, "kind": "end"})

        columns[col] = {
            "title": "%s 均值变点（发现 %d 个）" % (col, len(change_points)),
            "segments": [
                {
                    "start": int(s.get("start", 0)),
                    "end": int(s.get("end", 0)),
                    "length": int(s.get("length") or 0),
                    "mean": json_safe(s.get("mean")),
                    "std": json_safe(s.get("std")),
                }
                for s in segments
            ],
            "step_points": step_points,
            "change_points": [
                {
                    "index": int(cp.get("index", 0)),
                    "delta_mean": json_safe(cp.get("delta_mean")),
                    "left_mean": json_safe(cp.get("left_mean")),
                    "right_mean": json_safe(cp.get("right_mean")),
                    "p_value": json_safe(cp.get("p_value")),
                    "confidence": cp.get("confidence"),
                }
                for cp in change_points
            ],
            "n_valid": int(entry.get("n_valid") or 0),
            "n_change_points": int(entry.get("n_change_points") or 0),
        }
        if active_column is None:
            active_column = col

    if not columns or active_column is None:
        return None

    return {
        "chart_type": "changepoint",
        "tool_name": "detect_mean_change_points",
        "summary": envelope.get("summary"),
        "active_column": active_column,
        "columns": columns,
    }


def _build_acf(envelope: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """analyze_autocorrelation → ACF bar chart with confidence bands,
    one entry per column.

    Source shape (``metrics.per_column[col]``):
        acf: [...], pacf: [...], confidence_band, max_lag, ci_level,
        significant_acf_lags, significant_pacf_lags
    """
    per_column = (envelope.get("metrics") or {}).get("per_column") or {}
    columns: Dict[str, Dict[str, Any]] = {}
    active_column: Optional[str] = None

    for col, entry in per_column.items():
        if not isinstance(entry, dict):
            continue
        acf = entry.get("acf") or []
        if not acf:
            continue

        pacf = entry.get("pacf") or []
        has_pacf = bool(pacf)
        ci = json_safe(entry.get("confidence_band"))

        columns[col] = {
            "title": "%s ACF/PACF（max_lag=%d）" % (
                col, int(entry.get("max_lag") or len(acf) - 1),
            ),
            "acf": [json_safe(v) for v in acf],
            "pacf": [json_safe(v) for v in pacf] if has_pacf else [],
            "confidence_band": ci,
            "ci_level": json_safe(entry.get("ci_level")),
            "max_lag": int(entry.get("max_lag") or len(acf) - 1),
            "significant_acf_lags": list(entry.get("significant_acf_lags") or []),
            "significant_pacf_lags": list(entry.get("significant_pacf_lags") or []),
            "lag_1_autocorr": json_safe(entry.get("lag_1_autocorr")),
            "n_valid": int(entry.get("n_valid") or 0),
        }
        if active_column is None:
            active_column = col

    if not columns or active_column is None:
        return None

    return {
        "chart_type": "acf",
        "tool_name": "analyze_autocorrelation",
        "summary": envelope.get("summary"),
        "active_column": active_column,
        "columns": columns,
    }


def _build_catboost_root_cause(envelope: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """CatBoost root-cause result → metrics + importance + SHAP card."""
    metrics = envelope.get("metrics") or {}
    per_target = metrics.get("per_target") or {}
    columns: Dict[str, Dict[str, Any]] = {}
    for target, entry in per_target.items():
        if not isinstance(entry, dict):
            continue
        importance = entry.get("feature_importance") or []
        shap_summary = entry.get("shap_summary") or []
        columns[str(target)] = {
            "title": entry.get("title") or f"{target} 根因分析",
            "mode": entry.get("mode") or metrics.get("mode") or "train",
            "validation_metrics": json_safe(entry.get("validation_metrics") or {}),
            "test_metrics": json_safe(entry.get("test_metrics") or {}),
            "current_metrics": json_safe(entry.get("current_metrics")),
            "feature_importance": json_safe(importance),
            "shap_summary": json_safe(shap_summary),
            "training_history": json_safe(entry.get("training_history") or []),
            "best_iteration": json_safe(entry.get("best_iteration")),
            "n_train": int(entry.get("n_train") or 0),
            "n_validation": int(entry.get("n_validation") or 0),
            "n_test": int(entry.get("n_test") or 0),
            "n_predictions": int(entry.get("n_predictions") or 0),
            "prediction_summary": json_safe(entry.get("prediction_summary")),
        }
    if not columns:
        return None
    requested_active = metrics.get("active_column")
    active_column = requested_active if requested_active in columns else next(iter(columns))
    return {
        "chart_type": "catboost_root_cause",
        "tool_name": "analyze_root_causes_catboost",
        "summary": envelope.get("summary"),
        "mode": metrics.get("mode") or envelope.get("mode") or "train",
        "active_column": active_column,
        "columns": columns,
        "save_name": envelope.get("save_name"),
        "split_strategy": metrics.get("split_strategy"),
        "split_ratios": json_safe(metrics.get("split_ratios") or []),
    }


# ---------------------------------------------------------------------- #
# Builder registry — placed AFTER the builders so we can reference the
# functions directly instead of going through ``globals()[name]``.
# Maps the analysis envelope's ``tool_name`` to its builder.
# ---------------------------------------------------------------------- #
_CHART_BUILDERS = {
    "correlation_matrix": _build_correlation_heatmap,
    "histogram": _build_histogram,
    "decomposition": _build_decomposition,
    "control_chart": _build_control_chart,
    "mean_change_point": _build_changepoint,
    "autocorrelation": _build_acf,
    "catboost_root_cause": _build_catboost_root_cause,
}
