"""Build a compact CSV preview payload for the frontend.

The frontend renders the payload as an interactive line chart that shows
the last ``N`` rows of the uploaded CSV. Only numeric columns are
eligible for line charts; non-numeric columns are surfaced as chips so
the user can see the full column roster but only click into numeric
ones.

Payload shape (kept intentionally small)::

    {
        "file_name":    "session_xxx_data.csv",
        "total_rows":   12345,
        "preview_rows": 100,
        "columns": [
            {"name": "temperature", "kind": "numeric",    "chartable": true},
            {"name": "device_id",   "kind": "categorical", "chartable": false},
            ...
        ],
        "index":  [0, 1, 2, ..., 99],
        "series": {
            "temperature": [12.3, 12.4, ...],   # last 100 values, NaN → null
            ...
        }
    }
"""

from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Optional

import pandas as pd

from models.schemas import CSVProfile, ColumnType


# How many trailing rows to send to the frontend. Keeping this bounded
# keeps the NDJSON line small and the chart snappy.
DEFAULT_PREVIEW_ROWS = 100


def _kind_from_column_type(t: ColumnType) -> str:
    """Map schema ColumnType to a frontend-friendly kind tag."""
    return t.value if isinstance(t, ColumnType) else str(t)


def _is_chartable(kind: str) -> bool:
    """Only numeric (and boolean-as-0/1) columns can be line-charted."""
    return kind in {ColumnType.NUMERIC.value, ColumnType.BOOLEAN.value}


def _to_jsonable(v: Any) -> Optional[float]:
    """Convert numpy scalars / NaN to a JSON-friendly value."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def build_csv_preview(
    file_path: str,
    csv_profile: Optional[CSVProfile] = None,
    preview_rows: int = DEFAULT_PREVIEW_ROWS,
) -> Dict[str, Any]:
    """Read the tail of a CSV file and assemble a preview payload.

    Args:
        file_path: Absolute path to the uploaded CSV.
        csv_profile: The profile produced by ``ProfileAgent``. When
            supplied, its per-column ``type`` is used to decide which
            columns are chartable; otherwise we fall back to pandas
            dtype inference.
        preview_rows: Number of trailing rows to include. Capped to
            ``DEFAULT_PREVIEW_ROWS`` to keep payload size sane.

    Returns:
        A JSON-serialisable dict matching the payload shape above.
    """
    n = max(1, min(preview_rows, DEFAULT_PREVIEW_ROWS))

    # Read just the tail to avoid loading a potentially huge file twice.
    # ``pd.read_csv`` doesn't have a native "tail" mode, so we read in
    # chunks and keep the last ``n`` rows. For very large files this is
    # still O(file_size); a production-grade version would use the byte
    # offset trick. Good enough for typical industrial CSVs (<100 MB).
    try:
        df = pd.read_csv(file_path)
    except Exception:
        # If parsing fails, surface an empty payload rather than crashing
        # the whole profiling node — the CSVProfile itself may still be
        # valid via the LLM-driven path.
        return {
            "file_name": os.path.basename(file_path),
            "total_rows": 0,
            "preview_rows": 0,
            "columns": [],
            "index": [],
            "series": {},
            "error": "failed to read CSV for preview",
        }

    total_rows = len(df)
    tail = df.tail(n).reset_index(drop=True) if total_rows else df

    # Build the per-column descriptor list, preserving the CSV's column
    # order so the chip strip on the frontend mirrors the file.
    profile_columns = csv_profile.columns if csv_profile else {}
    columns_meta: List[Dict[str, Any]] = []
    chartable_names: List[str] = []
    for name in df.columns:
        info = profile_columns.get(name)
        if info is not None:
            kind = _kind_from_column_type(info.type)
        else:
            # Fallback: infer from pandas dtype.
            col_type = pd.api.types.is_numeric_dtype(df[name])
            kind = ColumnType.NUMERIC.value if col_type else ColumnType.UNKNOWN.value
        chartable = _is_chartable(kind)
        columns_meta.append({"name": name, "kind": kind, "chartable": chartable})
        if chartable:
            chartable_names.append(name)

    # Numeric series — only send data for chartable columns.
    series: Dict[str, List[Optional[float]]] = {}
    for name in chartable_names:
        col = tail[name]
        # Coerce to float, NaN/Inf → null so recharts renders gaps.
        series[name] = [_to_jsonable(v) for v in col.tolist()]

    return {
        "file_name": os.path.basename(file_path),
        "total_rows": total_rows,
        "preview_rows": len(tail),
        "columns": columns_meta,
        "index": list(range(len(tail))),
        "series": series,
    }
