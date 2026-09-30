"""Read a small, JSON-safe table sample from an uploaded dataset."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from math import isfinite
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq


PREVIEW_ROWS = 50


def _cell(value: Any) -> str | int | float | bool | None:
    if value is None:
        return None
    if isinstance(value, (datetime, date, time, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (TypeError, ValueError):
            return str(value)
    if isinstance(value, (list, dict, tuple)):
        return str(value)
    if pd.isna(value):
        return None
    if isinstance(value, float) and not isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def read_dataset_table_preview(file_path: Path) -> dict[str, Any]:
    """Return the first 50 rows without reading an entire data file into memory."""
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        try:
            frame = pd.read_csv(file_path, nrows=PREVIEW_ROWS + 1, encoding="utf-8-sig")
        except UnicodeDecodeError:
            frame = pd.read_csv(file_path, nrows=PREVIEW_ROWS + 1, encoding="gb18030")
        total_rows = None
    elif suffix == ".xlsx":
        frame = pd.read_excel(file_path, nrows=PREVIEW_ROWS + 1)
        total_rows = None
    elif suffix == ".parquet":
        parquet = pq.ParquetFile(file_path)
        total_rows = parquet.metadata.num_rows
        first_batch = next(parquet.iter_batches(batch_size=PREVIEW_ROWS + 1), None)
        frame = first_batch.to_pandas() if first_batch is not None else pd.DataFrame(columns=parquet.schema_arrow.names)
    else:
        raise ValueError("不支持的文件格式")

    has_more = len(frame) > PREVIEW_ROWS
    sample = frame.head(PREVIEW_ROWS)
    return {
        "file_name": file_path.name,
        "columns": [str(column) for column in sample.columns],
        "rows": [[_cell(value) for value in row] for row in sample.itertuples(index=False, name=None)],
        "preview_rows": len(sample),
        "has_more": has_more,
        "total_rows": total_rows,
    }
