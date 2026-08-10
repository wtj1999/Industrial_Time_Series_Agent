"""Shared helpers for chart-payload builders.

These were previously duplicated between ``analysis_chart_extractors.py``
and ``anomaly_detection_agent.py``; centralising them here keeps the
two builder modules thin and ensures numpy / pandas coercion stays
consistent across chart families.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional


def json_safe(v: Any) -> Any:
    """Coerce numpy / pandas scalars to JSON-safe Python values.

    - ``np.integer`` → ``int``
    - ``np.floating`` → ``float`` (``NaN`` / ``Inf`` become ``None`` so
      ``json.dumps`` does not blow up downstream)
    - ``np.bool_`` → ``bool``
    - plain Python ``float`` that is non-finite → ``None``
    - everything else passes through unchanged
    """
    try:
        import numpy as np
    except Exception:
        np = None  # type: ignore

    if np is not None and isinstance(v, (np.integer,)):
        return int(v)
    if np is not None and isinstance(v, (np.floating,)):
        f = float(v)
        return f if math.isfinite(f) else None
    if np is not None and isinstance(v, (np.bool_,)):
        return bool(v)
    if v is None:
        return None
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    return v


def first_column(
    per_column: Dict[str, Any],
    prefer: Optional[str] = None,
) -> Optional[str]:
    """Pick the column to visualise when a tool returned per-column data.

    Charts render one column at a time. Selection order:

    1. ``prefer`` if it exists in ``per_column``
    2. the first key whose entry looks chartable (has ``chart_series``)
    3. the first key overall

    Returns ``None`` when ``per_column`` is empty.
    """
    if not per_column:
        return None
    if prefer and prefer in per_column:
        return prefer
    for col, entry in per_column.items():
        if isinstance(entry, dict) and entry.get("chart_series"):
            return col
    return next(iter(per_column))
