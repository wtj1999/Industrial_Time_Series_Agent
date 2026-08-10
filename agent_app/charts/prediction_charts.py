"""Prediction-chart payload extraction.

Consumes the ``tool_calls`` list produced by
:func:`agents.base_agent.extract_tool_calls` and turns the **last**
``forecast_time_series`` / ``forecast_multi_models`` result into a
frontend-ready forecast-chart payload tagged with
``chart_type == "forecast"``.

Both tools share a single ``chart_type`` and a single React component;
``model_names`` discriminates single-model vs multi-model mode (length 1
→ single; length >1 → multi). ``forecast_ensemble`` is intentionally
NOT covered here (its envelope lacks ``chart_history`` and its
post-blend output no longer carries per-model quantile bands).

The frontend dispatches on ``chart_type == "forecast"`` (see
``frontend/src/components/forecast_chart/ForecastChartCard.tsx``).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ._common import json_safe

logger = logging.getLogger(__name__)


# Tools whose structured output we know how to visualise.
_CHARTABLE_TOOLS = {"forecast_time_series", "forecast_multi_models"}

# Nine quantile levels the upstream normaliser always emits (see
# ``prediction_tools._common.normalize_forecast``). Keep the keys stable
# so the frontend's stacked-delta derivation can match them by name.
_QUANTILE_KEYS: List[str] = [
    "p10", "p20", "p30", "p40", "p50", "p60", "p70", "p80", "p90",
]


# ---------------------------------------------------------------------- #
# Public entry point
# ---------------------------------------------------------------------- #

def extract_prediction_chart(
    tool_calls: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Walk ``tool_calls`` newest-first and build a chart payload from the
    most recent prediction-tool result that exposes ``chart_history``.

    Returns ``None`` when no suitable record is found, when its ``result``
    cannot be parsed into the expected dict shape, or when the matched
    tool is ``forecast_ensemble`` (not visualisable in this view).
    """
    for call in reversed(tool_calls):
        payload = call.get("result") if isinstance(call, dict) else None
        if not isinstance(payload, dict):
            continue
        if payload.get("task_type") != "prediction":
            continue
        tool_name = payload.get("tool_name")
        if tool_name not in _CHARTABLE_TOOLS:
            continue
        try:
            chart = _build_forecast_chart(payload)
        except Exception as exc:
            logger.warning(
                "prediction chart builder %s failed: %s", tool_name, exc,
                exc_info=True,
            )
            continue
        if chart is not None:
            return chart
    return None


# ---------------------------------------------------------------------- #
# Builder
# ---------------------------------------------------------------------- #

def _build_forecast_chart(
    envelope: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Convert a raw ``forecast_time_series`` / ``forecast_multi_models``
    envelope into the frontend-friendly forecast-chart payload.

    The unified shape::

        {
          chart_type: "forecast",
          tool_name,
          title,
          summary,
          model_names: [...],          # length 1 (single) or N (multi)
          is_multi_model: bool,
          prediction_length: int,
          per_column: {
            "<col>": {
              history: [float, ...],     # already downsampled by the tool
              n_history_full: int,
              history_downsampled: bool,
              horizon: int,
              models: {
                "<model>": {
                  point_forecast: [...],   # = p50
                  quantiles: {p10: [...], ..., p90: [...]},
                }, ...
              },
            }, ...
          },
          all_columns: [...],
        }
    """
    metrics = envelope.get("metrics") or {}
    tool_name = envelope.get("tool_name")
    chart_history = metrics.get("chart_history")
    if not isinstance(chart_history, dict) or not chart_history:
        # ``forecast_ensemble`` and any older forecast envelope will land
        # here — we simply skip them.
        return None

    prediction_length = int(metrics.get("prediction_length") or 0)
    if prediction_length <= 0:
        return None

    # Resolve the per-(model, column) forecast tensors depending on
    # which tool produced the envelope.
    if tool_name == "forecast_time_series":
        model_name = metrics.get("model") or "model"
        model_names: List[str] = [str(model_name)]
        per_model_per_col = _expand_single_model(metrics)
    elif tool_name == "forecast_multi_models":
        model_names = [str(m) for m in (metrics.get("models") or [])]
        per_model_per_col = _expand_multi_model(metrics)
    else:
        return None

    if not model_names:
        return None

    # Build the per-column chart payload, keeping only columns that have
    # BOTH a chart_history entry AND at least one successful model
    # forecast. Columns with no successful model forecast are still
    # included if they have history, but with an empty models dict so
    # the user can at least see the history.
    per_column_out: Dict[str, Any] = {}
    all_columns: List[str] = []
    for col, hist in chart_history.items():
        if not isinstance(hist, dict):
            continue
        history_raw = hist.get("history")
        if not isinstance(history_raw, list):
            continue
        history = [json_safe(v) for v in history_raw]
        if not history:
            continue
        n_full = int(hist.get("n_full") or len(history))
        downsampled = bool(hist.get("downsampled"))

        models_out: Dict[str, Any] = {}
        for m in model_names:
            norm = per_model_per_col.get(m, {}).get(col)
            entry = _get_model_col_entry(norm, prediction_length)
            if entry is None:
                continue
            models_out[m] = entry

        per_column_out[col] = {
            "history": history,
            "n_history_full": n_full,
            "history_downsampled": downsampled,
            "horizon": prediction_length,
            "models": models_out,
        }
        all_columns.append(col)

    if not per_column_out:
        return None

    is_multi_model = len(model_names) > 1
    title = _make_title(model_names, is_multi_model)

    return {
        "chart_type": "forecast",
        "tool_name": tool_name,
        "title": title,
        "summary": envelope.get("summary"),
        "model_names": model_names,
        "is_multi_model": is_multi_model,
        "prediction_length": prediction_length,
        "per_column": per_column_out,
        "all_columns": all_columns,
    }


# ---------------------------------------------------------------------- #
# Per-tool tensor expansion helpers
# ---------------------------------------------------------------------- #

def _expand_single_model(
    metrics: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Reshape ``forecast_time_series`` metrics into the unified
    ``{model: {col: normalized_forecast}}`` layout so the rest of the
    builder can treat single-model and multi-model envelopes identically.
    """
    model_name = str(metrics.get("model") or "model")
    per_column = metrics.get("per_column") or {}
    out: Dict[str, Dict[str, Any]] = {model_name: {}}
    if not isinstance(per_column, dict):
        return out
    for col, entry in per_column.items():
        if isinstance(entry, dict):
            out[model_name][col] = entry
    return out


def _expand_multi_model(
    metrics: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """``forecast_multi_models`` already stores results as
    ``metrics.per_model[model][col]`` — pass it through with light
    validation.
    """
    per_model = metrics.get("per_model") or {}
    out: Dict[str, Dict[str, Any]] = {}
    if not isinstance(per_model, dict):
        return out
    for m, col_map in per_model.items():
        if not isinstance(col_map, dict):
            continue
        out[str(m)] = {
            str(col): entry
            for col, entry in col_map.items()
            if isinstance(entry, dict)
        }
    return out


def _get_model_col_entry(
    norm: Any,
    prediction_length: int,
) -> Optional[Dict[str, Any]]:
    """Project a normalised forecast dict onto the (point_forecast +
    quantiles) subset the chart needs.

    Returns ``None`` when the entry is malformed, carries an error, or
    its arrays' lengths disagree with ``prediction_length`` — in any of
    those cases we'd rather drop the model from the chart than render a
    broken band.
    """
    if not isinstance(norm, dict):
        return None
    if norm.get("error") or norm.get("note"):
        return None
    point = norm.get("point_forecast")
    quants = norm.get("quantiles")
    if not isinstance(point, list) or len(point) != prediction_length:
        return None
    if not isinstance(quants, dict):
        return None
    quantile_out: Dict[str, List[float]] = {}
    for qk in _QUANTILE_KEYS:
        qv = quants.get(qk)
        if not isinstance(qv, list) or len(qv) != prediction_length:
            return None
        quantile_out[qk] = [json_safe(v) for v in qv]
    return {
        "point_forecast": [json_safe(v) for v in point],
        "quantiles": quantile_out,
    }


def _collect_columns(per_column_out: Dict[str, Any]) -> List[str]:
    """Stable column ordering — currently insertion order from the dict
    we just built. Kept as a helper in case we later want a smarter
    sort (e.g. by history length or column name).
    """
    return list(per_column_out.keys())


def _make_title(model_names: List[str], is_multi_model: bool) -> str:
    if is_multi_model:
        names = ", ".join(model_names[:3])
        suffix = " 等" if len(model_names) > 3 else ""
        return "多模型预测对比（%s%s）" % (names, suffix)
    return "%s 时序预测" % (model_names[0] if model_names else "模型")


def _validate_quantiles(quantiles: Dict[str, Any]) -> bool:
    """Cheap sanity check that all 9 quantile keys are present. Kept as
    a helper so the title-builder and the entry builder can share one
    definition of "complete".
    """
    return all(k in quantiles for k in _QUANTILE_KEYS)
