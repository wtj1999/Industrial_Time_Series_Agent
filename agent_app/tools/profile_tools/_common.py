"""Shared helpers for the profile_tools family.

Every tool in this family reads only ``ctx.df`` from the injected
``ProfileContext``. Results returned to the LLM fall into two buckets:

1. **Schema fields** — populated on :class:`ColumnInfo` and consumed by
   the final CSVProfile. These are the only values that may appear in
   the structured output.
2. **Auxiliary hints** — sample values, candidate-role flags, anomaly
   indicators. These are surfaced in the tool's free-text response to
   help the LLM reason about ``time_column_candidates`` /
   ``target_column_candidates`` / ``grouping_columns``, but they MUST
   NOT appear in the CSVProfile itself.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from models.schemas import ColumnInfo, ColumnType


# ---------------------------------------------------------------------------
# Column-type detection
# ---------------------------------------------------------------------------

def detect_column_type(series: pd.Series) -> ColumnType:
    """Classify a pandas Series into a :class:`ColumnType`."""
    dtype = series.dtype

    # Numeric (with boolean special-case)
    if pd.api.types.is_numeric_dtype(series):
        if series.dropna().isin([0, 1]).all() and series.nunique() <= 2:
            return ColumnType.BOOLEAN
        return ColumnType.NUMERIC

    # Native datetime
    if pd.api.types.is_datetime64_any_dtype(series):
        return ColumnType.TEMPORAL

    # Object / string — try to be smarter
    if dtype == 'object':
        # Can it be parsed as datetime?
        try:
            parsed = pd.to_datetime(series, errors='coerce')
            valid_ratio = parsed.notna().sum() / len(series) if len(series) else 0
            if valid_ratio > 0.8:
                return ColumnType.TEMPORAL
        except Exception:
            pass

        # Boolean-like?
        unique_values = series.dropna().unique()
        if len(unique_values) <= 10 and all(
            str(v).lower() in {'true', 'false', 'yes', 'no', '1', '0'}
            for v in unique_values
        ):
            return ColumnType.BOOLEAN

        # Low cardinality → categorical, otherwise text
        if len(series) == 0 or series.nunique() < len(series) * 0.5:
            return ColumnType.CATEGORICAL
        return ColumnType.TEXT

    return ColumnType.UNKNOWN


# ---------------------------------------------------------------------------
# Distribution stats (ColumnInfo.distribution_stats)
# ---------------------------------------------------------------------------

def compute_distribution_stats(series: pd.Series) -> Optional[Dict[str, float]]:
    """Return distribution stats for a numeric series; ``None`` otherwise.

    Keys are aligned with the schema description:
    ``mean / std / min / max / median / q25 / q75``.
    """
    cleaned = series.dropna()
    if cleaned.empty:
        return None

    try:
        return {
            'mean':   float(cleaned.mean()),
            'std':    float(cleaned.std()),
            'min':    float(cleaned.min()),
            'max':    float(cleaned.max()),
            'median': float(cleaned.median()),
            'q25':    float(cleaned.quantile(0.25)),
            'q75':    float(cleaned.quantile(0.75)),
        }
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Auxiliary hints (NOT part of CSVProfile schema; for LLM reasoning only)
# ---------------------------------------------------------------------------

def is_time_column_candidate(series: pd.Series, column_type: ColumnType) -> bool:
    """Heuristic: is this column likely a time axis?"""
    if column_type == ColumnType.TEMPORAL:
        return True

    if column_type in {ColumnType.TEXT, ColumnType.CATEGORICAL}:
        try:
            parsed = pd.to_datetime(series, errors='coerce')
            valid_ratio = parsed.notna().sum() / len(series) if len(series) else 0
            return valid_ratio > 0.8
        except Exception:
            pass

    return False


def is_target_column_candidate(series: pd.Series, column_type: ColumnType) -> bool:
    """Heuristic: is this column likely a prediction / monitoring target?"""
    if column_type != ColumnType.NUMERIC:
        return False
    if len(series) == 0:
        return False
    unique_ratio = series.nunique() / len(series)
    return 0.01 < unique_ratio <= 1.0


def is_grouping_column_candidate(series: pd.Series, column_type: ColumnType) -> bool:
    """Heuristic: is this column likely a grouping / dimension column?"""
    if column_type == ColumnType.CATEGORICAL:
        return series.nunique() < len(series) * 0.5 if len(series) else False
    if column_type == ColumnType.NUMERIC:
        return series.nunique() < 50
    return False


def detect_column_anomalies(series: pd.Series, column_type: ColumnType) -> List[str]:
    """Heuristic anomaly indicators. Returned to the LLM as a hint only."""
    anomalies: List[str] = []
    if len(series) == 0:
        return anomalies

    missing_rate = series.isna().sum() / len(series)
    if missing_rate > 0.5:
        anomalies.append(f"High missing rate: {missing_rate:.1%}")

    if series.nunique() == 1:
        anomalies.append("Constant column (only one unique value)")

    if column_type == ColumnType.CATEGORICAL:
        unique_ratio = series.nunique() / len(series)
        if unique_ratio > 0.9:
            anomalies.append("High cardinality for categorical column")

    if column_type == ColumnType.NUMERIC:
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        if iqr > 0:
            outliers = ((series < q1 - 3 * iqr) | (series > q3 + 3 * iqr)).sum()
            if outliers > len(series) * 0.05:
                anomalies.append(f"High number of outliers: {int(outliers)}")

    return anomalies


def get_sample_values(series: pd.Series, n: int = 10) -> List[Any]:
    """Return up to ``n`` non-null sample values from the series."""
    return series.dropna().head(n).tolist()


# ---------------------------------------------------------------------------
# Building a ColumnInfo
# ---------------------------------------------------------------------------

def analyze_column_info(df: pd.DataFrame, column_name: str) -> ColumnInfo:
    """Construct a :class:`ColumnInfo` for ``column_name``.

    Only schema-valid fields are populated. Auxiliary hints (sample
    values, candidate flags, anomaly indicators) are exposed separately
    through :func:`get_column_hints`.
    """
    series = df[column_name]
    total = len(series)
    missing_rate = series.isna().sum() / total if total else 0.0
    column_type = detect_column_type(series)

    distribution_stats = (
        compute_distribution_stats(series)
        if column_type == ColumnType.NUMERIC
        else None
    )

    return ColumnInfo(
        name=column_name,
        type=column_type,
        missing_rate=missing_rate,
        unique_count=int(series.nunique()),
        distribution_stats=distribution_stats,
    )


def get_column_hints(df: pd.DataFrame, column_name: str) -> Dict[str, Any]:
    """Return auxiliary info to help the LLM categorize the column.

    These values are intentionally NOT part of the CSVProfile schema —
    they exist only to inform the LLM's reasoning when filling
    ``time_column_candidates`` / ``target_column_candidates`` /
    ``grouping_columns``.
    """
    series = df[column_name]
    column_type = detect_column_type(series)
    return {
        "sample_values":         get_sample_values(series),
        "is_time_candidate":     is_time_column_candidate(series, column_type),
        "is_target_candidate":   is_target_column_candidate(series, column_type),
        "is_grouping_candidate": is_grouping_column_candidate(series, column_type),
        "anomaly_indicators":    detect_column_anomalies(series, column_type),
    }


# ---------------------------------------------------------------------------
# Runtime accessor
# ---------------------------------------------------------------------------

def get_df(runtime) -> pd.DataFrame:
    """Pull the DataFrame out of the injected ProfileContext."""
    return runtime.context.df