"""Evaluation-chart payload extraction for the prediction tool family.

Consumes the ``tool_calls`` list produced by
:func:`agents.base_agent.extract_tool_calls` and turns the **last**
``backtest_forecast`` / ``compare_forecast_models_backtest`` result into
a frontend-ready backtest-chart payload tagged with
``chart_type == "backtest"``.

Visually a backtest chart sits somewhere between the forecast chart and
an accuracy report:

- the **train tail** renders as the history line (same role as in the
  forecast chart)
- the **forecast** renders either as a quantile band (single-model mode,
  ``backtest_forecast``) or as one dashed point-forecast line per model
  (multi-model mode, ``compare_forecast_models_backtest``)
- the **actual holdout** overlays as a solid green line so the user can
  eyeball the error directly
- a small per-column metrics readout (MAE / RMSE / MAPE / sMAPE) is
  attached so the card can surface the numbers alongside the chart

The frontend dispatches on ``chart_type == "backtest"`` (see
``frontend/src/components/forecast_chart/BacktestChartCard.tsx``).
``is_multi_model`` discriminates single-model vs multi-model mode.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ._common import json_safe

logger = logging.getLogger(__name__)


# Tools whose structured output we know how to visualise.
_CHARTABLE_TOOLS = {"backtest_forecast", "compare_forecast_models_backtest"}

# Nine quantile levels the upstream normaliser always emits (see
# ``prediction_tools._common.normalize_forecast``). The single-model
# backtest tool stores the full normalised forecast in ``per_column``,
# so we mirror the forecast-chart convention to keep the band rendering
# logic identical on the frontend side.
_QUANTILE_KEYS: List[str] = [
    "p10", "p20", "p30", "p40", "p50", "p60", "p70", "p80", "p90",
]

# Metric keys surfaced in the per-(column[, model]) readout. Order
# matters for the frontend display.
_METRIC_KEYS: List[str] = ["mae", "rmse", "mape", "smape", "mase"]


# ---------------------------------------------------------------------- #
# Public entry point
# ---------------------------------------------------------------------- #

def extract_evaluation_chart(
    tool_calls: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Walk ``tool_calls`` newest-first and build a chart payload from
    the most recent backtest-tool result that exposes ``chart_history``.

    Returns ``None`` when no suitable record is found, when its
    ``result`` cannot be parsed into the expected dict shape, or when
    neither of the two backtest tools produced a chartable envelope.
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
            chart = _build_backtest_chart(payload)
        except Exception as exc:
            logger.warning(
                "evaluation chart builder %s failed: %s", tool_name, exc,
                exc_info=True,
            )
            continue
        if chart is not None:
            return chart
    return None


# ---------------------------------------------------------------------- #
# Builder
# ---------------------------------------------------------------------- #

def _build_backtest_chart(
    envelope: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Convert a raw ``backtest_forecast`` /
    ``compare_forecast_models_backtest`` envelope into the frontend-friendly
    backtest-chart payload.

    The unified shape::

        {
          chart_type: "backtest",
          tool_name,
          title,
          summary,
          model_names: [...],          # length 1 (single) or N (multi)
          is_multi_model: bool,
          test_steps: int,
          rank_by: str | null,         # multi-model only
          per_column: {
            "<col>": {
              history: [float, ...],     # train tail (downsampled)
              n_history_full: int,
              history_downsampled: bool,
              horizon: int,              # = test_steps
              actual: [float, ...],      # holdout ground truth
              models: {
                "<model>": {
                  point_forecast: [...],
                  quantiles: {p10..p90},   # single-model only
                  metrics: {mae, rmse, ...},
                }, ...
              },
              # Multi-model mode only: mean metric values across all
              # models on this column, handy for the card header.
              best_model: str | null,
              best_metric_value: float | null,
            }, ...
          },
          all_columns: [...],
          ranking: [{model, mae, rmse, ...}, ...] | [],  # multi-model only
        }
    """
    metrics = envelope.get("metrics") or {}
    tool_name = envelope.get("tool_name")
    chart_history = metrics.get("chart_history")
    if not isinstance(chart_history, dict) or not chart_history:
        return None

    test_steps = int(metrics.get("test_steps") or 0)
    if test_steps <= 0:
        return None

    if tool_name == "backtest_forecast":
        model_name = metrics.get("model") or "model"
        model_names: List[str] = [str(model_name)]
        per_model_per_col = _expand_single_model(metrics)
        rank_by: Optional[str] = None
        ranking: List[Dict[str, Any]] = []
    elif tool_name == "compare_forecast_models_backtest":
        model_names = [str(m) for m in (metrics.get("models") or [])]
        per_model_per_col = _expand_multi_model(metrics)
        rank_by = metrics.get("rank_by") or "mae"
        ranking = _build_ranking(metrics.get("summary"), rank_by)
    else:
        return None

    if not model_names:
        return None

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
        actual_ref: Optional[List[float]] = None
        for m in model_names:
            entry = per_model_per_col.get(m, {}).get(col)
            actual_ref, model_entry = _project_model_entry(
                entry, test_steps, actual_ref,
            )
            if model_entry is None:
                continue
            models_out[m] = model_entry

        if not models_out:
            # A column whose every model failed should still surface its
            # history for context, but with an empty models dict and no
            # actual so the card can show the "no usable forecast"
            # state cleanly.
            per_column_out[col] = {
                "history": history,
                "n_history_full": n_full,
                "history_downsampled": downsampled,
                "horizon": test_steps,
                "actual": [],
                "models": {},
                "best_model": None,
                "best_metric_value": None,
            }
            all_columns.append(col)
            continue

        # Pick the "best" model on this column by rank_by (multi-model)
        # or the single model (single-model mode). Used by the card
        # header to surface a one-line summary per column.
        best_model, best_value = _pick_best_model(
            models_out, rank_by, is_multi=len(model_names) > 1,
        )

        per_column_out[col] = {
            "history": history,
            "n_history_full": n_full,
            "history_downsampled": downsampled,
            "horizon": test_steps,
            "actual": actual_ref or [],
            "models": models_out,
            "best_model": best_model,
            "best_metric_value": best_value,
        }
        all_columns.append(col)

    if not per_column_out:
        return None

    is_multi_model = len(model_names) > 1
    title = _make_title(model_names, is_multi_model, test_steps, rank_by)

    return {
        "chart_type": "backtest",
        "tool_name": tool_name,
        "title": title,
        "summary": envelope.get("summary"),
        "model_names": model_names,
        "is_multi_model": is_multi_model,
        "test_steps": test_steps,
        "rank_by": rank_by,
        "per_column": per_column_out,
        "all_columns": all_columns,
        "ranking": ranking,
    }


# ---------------------------------------------------------------------- #
# Per-tool tensor expansion helpers
# ---------------------------------------------------------------------- #

def _expand_single_model(
    metrics: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Reshape ``backtest_forecast`` metrics into the unified
    ``{model: {col: per_col_entry}}`` layout so the rest of the builder
    can treat single-model and multi-model envelopes identically.

    For ``backtest_forecast`` each per-column entry already carries the
    full normalised forecast (``point_forecast`` + ``quantiles``), the
    holdout ``actual`` and the error ``metrics``.
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
    """``compare_forecast_models_backtest`` stores results as
    ``metrics.per_model[model][col]`` — pass it through with light
    validation.

    Note: the compare tool only retains ``point_forecast`` (no
    quantiles) per model. That's fine — the multi-model card renders
    dashed point-forecast lines rather than a quantile band.
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


def _project_model_entry(
    norm: Any,
    test_steps: int,
    actual_ref: Optional[List[float]],
) -> tuple:
    """Project a raw per-(model, column) entry onto the subset the
    backtest chart needs: ``point_forecast`` + optional ``quantiles`` +
    ``metrics``. Also returns the holdout ``actual`` array (read from
    whichever entry first exposes it).

    Returns ``(actual_ref, model_entry)`` where ``actual_ref`` may have
    been refreshed from this entry, and ``model_entry`` is ``None`` when
    the entry is malformed / errored / length-mismatched — in any of
    those cases we'd rather drop the model than render a broken line.

    The second return value is deliberately a tuple so the caller can
    unpack without building a temporary.
    """
    if not isinstance(norm, dict):
        return actual_ref, None
    if norm.get("error") or norm.get("note"):
        return actual_ref, None

    point = norm.get("point_forecast")
    if not isinstance(point, list) or len(point) != test_steps:
        return actual_ref, None

    # In multi-model mode every entry stores the same `actual` array
    # (it's the shared holdout). The first model to expose it wins and
    # subsequent models reuse the reference.
    actual = actual_ref
    if actual is None:
        a = norm.get("actual")
        if isinstance(a, list) and len(a) == test_steps:
            actual = [json_safe(v) for v in a]

    out_entry: Dict[str, Any] = {
        "point_forecast": [json_safe(v) for v in point],
    }

    # Single-model mode carries full quantile bands.
    quants = norm.get("quantiles")
    if isinstance(quants, dict):
        quantile_out: Dict[str, List[float]] = {}
        ok = True
        for qk in _QUANTILE_KEYS:
            qv = quants.get(qk)
            if not isinstance(qv, list) or len(qv) != test_steps:
                ok = False
                break
            quantile_out[qk] = [json_safe(v) for v in qv]
        if ok:
            out_entry["quantiles"] = quantile_out

    mtr = norm.get("metrics")
    if isinstance(mtr, dict):
        out_entry["metrics"] = {
            k: json_safe(mtr[k]) for k in _METRIC_KEYS
            if k in mtr and mtr[k] is not None
        }
        n = mtr.get("n")
        if n is not None:
            out_entry["metrics"]["n"] = int(n)

    return actual, out_entry


def _build_ranking(
    summary: Any,
    rank_by: str,
) -> List[Dict[str, Any]]:
    """Project the compare tool's ``summary`` rows into the slim ranking
    list the card shows next to its model chip row.

    Each row carries the model name plus the 5 metric values plus the
    ``n_columns_ok`` count. ``rank_by`` is preserved as
    ``rank_metric`` so the card can highlight the sort key.
    """
    if not isinstance(summary, list):
        return []
    out: List[Dict[str, Any]] = []
    for row in summary:
        if not isinstance(row, dict):
            continue
        model = row.get("model")
        if not model:
            continue
        slim: Dict[str, Any] = {
            "model": str(model),
            "rank_metric": rank_by,
            "n_columns_ok": row.get("n_columns_ok"),
        }
        for k in _METRIC_KEYS:
            v = row.get(k)
            if v is not None:
                slim[k] = json_safe(v)
        out.append(slim)
    return out


def _pick_best_model(
    models_out: Dict[str, Any],
    rank_by: Optional[str],
    is_multi: bool,
) -> tuple:
    """Return ``(best_model_name, best_metric_value)`` for the card
    header. In single-model mode the only model wins; in multi-model
    mode we sort by ``rank_by`` (default mae) and pick the smallest.
    """
    if not models_out:
        return None, None
    if not is_multi:
        name = next(iter(models_out))
        mtr = models_out[name].get("metrics") or {}
        key = rank_by or "mae"
        return name, mtr.get(key)

    key = rank_by or "mae"
    if key not in _METRIC_KEYS:
        key = "mae"

    best_name: Optional[str] = None
    best_val: Optional[float] = None
    for name, entry in models_out.items():
        mtr = entry.get("metrics") or {}
        v = mtr.get(key)
        if v is None:
            continue
        try:
            v_f = float(v)
        except (TypeError, ValueError):
            continue
        if best_val is None or v_f < best_val:
            best_val = v_f
            best_name = name
    return best_name, best_val


def _make_title(
    model_names: List[str],
    is_multi_model: bool,
    test_steps: int,
    rank_by: Optional[str],
) -> str:
    if is_multi_model:
        names = ", ".join(model_names[:3])
        suffix = " 等" if len(model_names) > 3 else ""
        rank_part = "，按 %s 排名" % rank_by if rank_by else ""
        return "多模型回测对比（%s%s，holdout=%d%s）" % (
            names, suffix, test_steps, rank_part,
        )
    name = model_names[0] if model_names else "模型"
    return "%s holdout 回测（test_steps=%d）" % (name, test_steps)
