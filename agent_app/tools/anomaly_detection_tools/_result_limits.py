"""Bound row-aligned anomaly-tool results before they reach the LLM."""

from __future__ import annotations

import math
from typing import Any, Dict


MAX_RETURN_POINTS = 1500

# These fields contain one value per input row (or a sparse list of input-row
# indices). They must never be returned to LangChain without a hard bound.
_ROW_SERIES_KEYS = frozenset({
    "scores",
    "labels",
    "scores_train",
    "labels_train",
    "scores_test",
    "labels_test",
    "consensus_scores",
    "consensus_labels",
    "consensus_anomalies",
})


def limit_anomaly_result(
    payload: Dict[str, Any],
    max_points: int = MAX_RETURN_POINTS,
) -> Dict[str, Any]:
    """Recursively retain only the last ``max_points`` of row series.

    A ``series_windows`` entry is added beside every truncated field so
    downstream consumers can map the returned window back to original row
    positions. NumPy arrays are converted through ``tolist`` even when they
    already fit, ensuring nested auto-detection results remain JSON-safe.
    """
    if max_points <= 0:
        raise ValueError("max_points must be > 0")
    return _limit_mapping(payload, int(max_points))


def _limit_mapping(payload: Dict[str, Any], max_points: int) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    windows: Dict[str, Dict[str, Any]] = {}

    for key, value in payload.items():
        if key in _ROW_SERIES_KEYS:
            sequence = _as_list(value)
            if sequence is None:
                out[key] = value
                continue
            total = len(sequence)
            start = max(0, total - max_points)
            # NumPy arrays are commonly used for detector scores.  Their
            # ``tolist()`` output may still contain NaN/Infinity, which
            # Python's json encoder emits as non-standard JSON tokens that
            # browsers reject.  Normalise every retained value here so the
            # final ``completed`` NDJSON event remains strictly parseable.
            out[key] = [_json_safe_value(item) for item in sequence[start:]]
            if start:
                windows[key] = {
                    "total_points": total,
                    "returned_points": total - start,
                    "start_index": start,
                    "end_index": total - 1,
                    "truncated": True,
                }
            continue

        if isinstance(value, dict):
            out[key] = _limit_mapping(value, max_points)
        elif isinstance(value, (list, tuple)):
            out[key] = [
                _limit_mapping(item, max_points)
                if isinstance(item, dict)
                else _json_safe_value(item)
                for item in value
            ]
        else:
            out[key] = _json_safe_value(value)

    if windows:
        existing = out.get("series_windows")
        out["series_windows"] = {
            **(existing if isinstance(existing, dict) else {}),
            **windows,
        }
    return out


def _as_list(value: Any):
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        converted = tolist()
        return converted if isinstance(converted, list) else [converted]
    return None


def _json_safe_value(value: Any) -> Any:
    """Return a strictly JSON-compatible representation of ``value``."""
    if isinstance(value, dict):
        return {key: _json_safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_value(item) for item in value]

    # NumPy scalar values expose ``tolist`` and should be converted before
    # checking Python numeric types.  Array values can occur in nested result
    # metadata, so handle those recursively as well.
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        converted = tolist()
        if converted is not value:
            return _json_safe_value(converted)

    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value
