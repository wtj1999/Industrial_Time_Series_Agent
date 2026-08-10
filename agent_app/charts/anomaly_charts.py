"""Anomaly-detection chart-payload extraction.

Consumes the ``tool_calls`` list produced by
:func:`agents.base_agent.extract_tool_calls` and turns the **last**
``detect_with_model`` / ``detect_ts_anomalies`` result into a frontend-
ready anomaly-score chart payload.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from ._common import json_safe

logger = logging.getLogger(__name__)


# Tools whose structured output we know how to visualise. Keep this list
# in sync with :func:`_build_anomaly_scores_chart` — adding a new tool
# name here without a matching branch in the builder will just fall
# through to ``None`` (no chart emitted).
#
# ``detect_with_model`` is the unified entry point (train+load merged);
# it emits the same ``scores`` / ``labels`` / ``threshold`` /
# ``scores_summary`` / ``top_anomalies`` shape regardless of whether it
# ended up training a new detector or loading a saved one, so the same
# builder handles both modes.
_CHARTABLE_TOOLS = {
    "detect_with_model",
    "detect_ts_anomalies",
}

# Cap the per-chart score array so we never ship a 100k-point JSON
# payload to the browser. When the series is longer than this we
# downsample by strided sampling; ``anomaly_indices`` and ``top_anomalies``
# are always preserved in full so no anomalies are silently dropped.
_MAX_CHART_POINTS = 1500


# ---------------------------------------------------------------------- #
# Public entry point
# ---------------------------------------------------------------------- #

def extract_anomaly_chart(
    tool_calls: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Walk ``tool_calls`` newest-first and build a chart payload from the
    most recent anomaly-detection tool result.

    Returns ``None`` when no suitable record is found, or when its
    ``result`` cannot be parsed into the expected dict shape.
    """
    for call in reversed(tool_calls):
        payload = call.get("result") if isinstance(call, dict) else None
        if not isinstance(payload, dict):
            continue
        if payload.get("task_type") != "anomaly_detection":
            continue
        tool_name = payload.get("tool_name")
        if tool_name not in _CHARTABLE_TOOLS:
            continue
        chart = _build_anomaly_scores_chart(payload)
        if chart is not None:
            return chart
    return None


# ---------------------------------------------------------------------- #
# Builder
# ---------------------------------------------------------------------- #

def _build_anomaly_scores_chart(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Convert a raw ``detect_with_model`` / ``detect_ts_anomalies`` result
    dict into the frontend-friendly chart payload.

    The shape is intentionally a strict subset that both tools satisfy so
    the React component can treat them uniformly::

        {
          chart_type, tool_name, detector_name, title, summary,
          n_samples, n_anomalies,
          x_label, x_values,           # index axis by default
          scores,                      # downsampled if huge
          threshold,                   # horizontal reference line
          anomaly_indices,             # red dot positions (downsampled grid)
          anomaly_intervals,           # ts only; null otherwise
          top_anomalies,               # up to 20 rows for the side table
          feature_columns,
        }
    """
    tool_name = result.get("tool_name")
    scores_raw = result.get("scores") or []
    labels_raw = result.get("labels") or []
    threshold = result.get("threshold")

    # Build the anomaly index list from labels (preferred) or fall back
    # to the scores_summary.top_indices the tool also exposes.
    anomaly_indices_orig = [i for i, lbl in enumerate(labels_raw) if lbl]
    if not anomaly_indices_orig:
        summary = result.get("scores_summary") or {}
        anomaly_indices_orig = list(summary.get("top_indices") or [])

    # Downsample scores + anomaly_indices together when the series is
    # huge; top_anomalies / intervals are always kept intact.
    scores, anomaly_indices, _sampled_positions = _maybe_downsample(
        scores_raw, anomaly_indices_orig, _MAX_CHART_POINTS,
    )
    n_samples = len(scores_raw)

    n_anomalies = (
        len(anomaly_indices_orig)
        or ((result.get("scores_summary") or {}).get("n_above_threshold"))
        or 0
    )

    detector_name = result.get("detector_name") or ""
    title = f"{detector_name} 异常检测分数".strip()

    chart: Dict[str, Any] = {
        "chart_type": "anomaly_scores",
        "tool_name": tool_name,
        "detector_name": detector_name,
        "title": title,
        "summary": result.get("summary"),
        "n_samples": int(result.get("n_samples") or result.get("n_timestamps") or n_samples),
        "n_anomalies": int(n_anomalies),
        "x_label": "样本序号",
        "x_values": None,
        "scores": scores,
        "threshold": threshold,
        "anomaly_indices": anomaly_indices,
        "anomaly_intervals": None,
        "top_anomalies": _sanitise_top_anomalies(result.get("top_anomalies")),
        "feature_columns": list(result.get("feature_columns") or []),
        "downsampled": len(scores_raw) > _MAX_CHART_POINTS,
        "original_n_samples": n_samples,
    }

    if tool_name == "detect_ts_anomalies":
        intervals = result.get("anomaly_intervals") or []
        chart["anomaly_intervals"] = [
            {
                "start_index": int(iv.get("start_index", 0)),
                "end_index": int(iv.get("end_index", 0)),
                "length": int(iv.get("length", 0)),
                "time_start": iv.get("time_start"),
                "time_end": iv.get("time_end"),
            }
            for iv in intervals
            if isinstance(iv, dict)
        ]
        time_col = result.get("time_column")
        if time_col:
            chart["x_label"] = time_col

    return chart


# ---------------------------------------------------------------------- #
# Downsampling / sanitisation helpers
# ---------------------------------------------------------------------- #

def _maybe_downsample(
    scores: List[float],
    anomaly_indices: List[int],
    max_points: int,
) -> Tuple[List[float], List[int], List[int]]:
    """Stride-downsample ``scores`` to at most ``max_points`` items.

    Returns ``(sampled_scores, sampled_anomaly_positions, original_positions)``
    where ``sampled_anomaly_positions`` are indices into ``sampled_scores``
    and ``original_positions`` is the mapping ``sampled_scores[i]`` ←
    ``scores[original_positions[i]]`` (also used as the x-axis values).

    When the input already fits, returns it unchanged with
    ``original_positions = [0, 1, ..., n-1]``.
    """
    n = len(scores)
    if n <= max_points:
        return list(scores), list(anomaly_indices), list(range(n))

    stride = math.ceil(n / max_points)
    sampled_scores = [scores[i] for i in range(0, n, stride)]
    original_positions = list(range(0, n, stride))

    # Bucket each anomaly into the nearest sampled position. Multiple
    # anomalies in the same bucket collapse to one red dot so the visual
    # signal is preserved without per-pixel noise.
    sampled_set = set()
    for a_idx in anomaly_indices:
        sampled_set.add(min(a_idx // stride, len(sampled_scores) - 1))
    sampled_anomaly = sorted(sampled_set)
    return sampled_scores, sampled_anomaly, original_positions


def _sanitise_top_anomalies(rows: Any, limit: int = 20) -> List[Dict[str, Any]]:
    """Trim and JSON-safe the ``top_anomalies`` list for the frontend."""
    if not isinstance(rows, list):
        return []
    out: List[Dict[str, Any]] = []
    for r in rows[:limit]:
        if not isinstance(r, dict):
            continue
        item: Dict[str, Any] = {
            "row_index": r.get("row_index", r.get("timestamp_index")),
            "score": r.get("score"),
            "is_anomaly": r.get("is_anomaly"),
        }
        # Keep ``values`` only when it's a small dict; big nested objects
        # blow up the SSE payload size.
        values = r.get("values")
        if isinstance(values, dict) and len(values) <= 30:
            item["values"] = {str(k): json_safe(v) for k, v in values.items()}
        if r.get("time") is not None:
            item["time"] = json_safe(r.get("time"))
        out.append(item)
    return out
