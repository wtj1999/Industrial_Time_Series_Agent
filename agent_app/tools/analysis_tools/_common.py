"""Shared internal helpers for the analysis tool family.

This module centralises the boilerplate every ``analysis_tools`` submodule
needs:

- **Numeric-column extraction** from the injected :class:`AnalysisContext`
  (``ctx.df``, ``ctx.target_columns``, ``ctx.feature_columns``). All other
  parameters (window sizes, method names, threshold ratios, time column
  name, group column name, ...) are supplied by the LLM as direct tool
  arguments — the context never carries them.
- **JSON-safe conversion** of pandas/numpy scalars so tool outputs are
  always serialisable.
- **Note formatting** used to surface skipped columns, imputed NaNs,
  short-series fallbacks, etc.
- **Small statistical primitives** reused across trend / correlation /
  outlier / change-point tools (rank, linear slope, safe percentiles,
  bootstrap CI, sliding-window reducer).

Importing this module has no side effects beyond defining the helpers.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# AnalysisContext accessors
# ----------------------------------------------------------------------

def _ctx_attr(runtime, name: str, default: Any = None) -> Any:
    """Read ``name`` off ``runtime.context`` defensively."""
    ctx = getattr(runtime, "context", None)
    if ctx is None:
        return default
    return getattr(ctx, name, default)


def get_df(runtime) -> pd.DataFrame:
    """Return ``ctx.df`` (raises if missing)."""
    df = _ctx_attr(runtime, "df", None)
    if not isinstance(df, pd.DataFrame):
        raise ValueError(
            "runtime.context.df 必须是 pandas.DataFrame，当前类型=%r"
            % type(df).__name__)
    return df


def get_target_columns(runtime) -> List[str]:
    """Return ``ctx.target_columns`` as a list (may be empty)."""
    cols = _ctx_attr(runtime, "target_columns", None) or []
    return [str(c) for c in cols if c is not None]


def get_feature_columns(runtime) -> List[str]:
    """Return ``ctx.feature_columns`` as a list (may be empty)."""
    cols = _ctx_attr(runtime, "feature_columns", None) or []
    return [str(c) for c in cols if c is not None]


def resolve_columns(
    runtime,
    columns: Optional[Sequence[str]] = None,
    use: str = "target",
) -> List[str]:
    """Resolve which columns the tool should operate on.

    Priority order:

    1. ``columns`` — explicit per-call override supplied by the LLM.
    2. ``ctx.target_columns`` when ``use="target"`` (default).
    3. ``ctx.feature_columns`` when ``use="feature"``.
    4. ``ctx.target_columns + ctx.feature_columns`` when ``use="any"``.

    Only columns actually present in ``ctx.df`` are returned; missing
    names are logged and dropped.
    """
    df = get_df(runtime)
    if columns:
        candidates = list(columns)
        source = "explicit"
    elif use == "target":
        candidates = get_target_columns(runtime)
        source = "target"
    elif use == "feature":
        candidates = get_feature_columns(runtime)
        source = "feature"
    elif use == "any":
        candidates = list(dict.fromkeys(
            get_target_columns(runtime) + get_feature_columns(runtime)))
        source = "any"
    else:
        raise ValueError("use 必须是 'target' / 'feature' / 'any'，当前=%r" % use)

    present = [c for c in candidates if c in df.columns]
    missing = [c for c in candidates if c not in df.columns]
    if missing:
        logger.warning("resolve_columns: 不在 df 中的列被跳过: %s", missing)
    if not present:
        raise ValueError(
            "无法定位任何可用列（source=%s, candidates=%r）。"
            "请通过 columns 参数显式指定列名。" % (source, candidates))
    return present


def select_numeric_columns(
    df: pd.DataFrame,
    columns: Sequence[str],
) -> Tuple[List[str], List[str], List[str]]:
    """Partition ``columns`` into (numeric, non_numeric, missing).

    A column is considered numeric when at least one value parses as a
    finite number under :func:`pd.to_numeric`. Pure-constant numeric
    columns are still returned as numeric — callers can decide whether
    to skip them.
    """
    numeric: List[str] = []
    non_numeric: List[str] = []
    missing: List[str] = []
    for c in columns:
        if c not in df.columns:
            missing.append(c)
            continue
        as_num = pd.to_numeric(df[c], errors="coerce")
        if as_num.notna().any():
            numeric.append(c)
        else:
            non_numeric.append(c)
    return numeric, non_numeric, missing


def numeric_frame(
    df: pd.DataFrame,
    columns: Sequence[str],
    impute: str = "median",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Return a clean numeric ``DataFrame[columns]`` plus diagnostics.

    Non-finite values are imputed per-column. Supported strategies:
    ``"median"`` (default), ``"mean"``, ``"ffill"``, ``"zero"`` and
    ``"drop"`` (rows with any NaN are removed).

    The returned diagnostics dict carries ``used_columns``,
    ``imputed_nan_count``, ``impute`` and ``n_samples``.
    """
    info: Dict[str, Any] = {
        "used_columns": list(columns),
        "impute": impute,
        "imputed_nan_count": 0,
        "n_samples": int(len(df)),
    }
    if not columns:
        return pd.DataFrame(index=df.index), info

    sub = df[list(columns)].apply(pd.to_numeric, errors="coerce")
    nan_count = int(sub.isna().sum().sum())
    info["imputed_nan_count"] = nan_count

    if nan_count == 0:
        return sub, info

    if impute == "drop":
        sub = sub.dropna(how="any")
        info["n_samples"] = int(len(sub))
    elif impute == "ffill":
        sub = sub.ffill().bfill().fillna(0.0)
    elif impute == "zero":
        sub = sub.fillna(0.0)
    elif impute == "mean":
        sub = sub.fillna(sub.mean(axis=0, skipna=True)).fillna(0.0)
    else:  # "median"
        sub = sub.fillna(sub.median(axis=0, skipna=True)).fillna(0.0)
    return sub, info


def numeric_series(
    df: pd.DataFrame,
    column: str,
    dropna: bool = True,
) -> Tuple[pd.Series, Dict[str, Any]]:
    """Return a clean numeric :class:`pandas.Series` for ``column``."""
    if column not in df.columns:
        raise ValueError("列 %r 不在 df.columns 中。" % column)
    raw = pd.to_numeric(df[column], errors="coerce")
    n_nan = int(raw.isna().sum())
    if dropna:
        s = raw.dropna()
    else:
        s = raw
    info = {
        "column": column,
        "n_total": int(len(raw)),
        "n_nan": n_nan,
        "n_valid": int(s.size),
    }
    return s, info


# ----------------------------------------------------------------------
# Time / group column resolution (LLM-supplied)
# ----------------------------------------------------------------------

def resolve_time_column(
    df: pd.DataFrame,
    time_column: Optional[str],
) -> Tuple[Optional[pd.Series], Dict[str, Any]]:
    """Parse ``time_column`` into a datetime series (or None on failure)."""
    info: Dict[str, Any] = {"time_column": time_column, "parsed": False}
    if not time_column:
        info["note"] = "未提供 time_column，时序类工具将以行序作为隐式时间轴。"
        return None, info
    if time_column not in df.columns:
        info["note"] = "time_column=%r 不在 df 中。" % time_column
        return None, info

    parsed = pd.to_datetime(df[time_column], errors="coerce")
    valid = parsed.notna().sum()
    info["n_valid"] = int(valid)
    if valid == 0:
        info["note"] = "time_column=%r 无法解析为时间，已退化为行序索引。" % time_column
        return None, info
    info["parsed"] = True
    info["start"] = (
        parsed.min().isoformat() if valid else None
    )
    info["end"] = (
        parsed.max().isoformat() if valid else None
    )
    return parsed, info


def resolve_group_column(
    df: pd.DataFrame,
    group_column: Optional[str],
) -> Tuple[Optional[pd.Series], Dict[str, Any]]:
    """Return ``df[group_column]`` as a Series (or None)."""
    info: Dict[str, Any] = {"group_column": group_column, "parsed": False}
    if not group_column:
        info["note"] = "未提供 group_column，分组对比类工具将不可用。"
        return None, info
    if group_column not in df.columns:
        info["note"] = "group_column=%r 不在 df 中。" % group_column
        return None, info
    info["parsed"] = True
    info["n_groups"] = int(df[group_column].nunique(dropna=True))
    return df[group_column], info


# ----------------------------------------------------------------------
# JSON-safe conversion & note formatting
# ----------------------------------------------------------------------

def json_safe(v: Any) -> Any:
    """Best-effort conversion of a scalar/array cell to a JSON-safe value."""
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        f = float(v)
        if not math.isfinite(f):
            return None
        return f
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (pd.Timestamp,)):
        return v.isoformat()
    return v


def round_float(v: Any, ndigits: int = 6) -> Any:
    """Round floats for human-readable output; pass other values through."""
    if isinstance(v, float) and math.isfinite(v):
        return round(v, ndigits)
    if isinstance(v, (np.floating,)) and math.isfinite(float(v)):
        return round(float(v), ndigits)
    return v


def format_notes(info: Dict[str, Any], extra: Optional[List[str]] = None) -> List[str]:
    """Flatten diagnostics + extra hints into a ``notes`` list."""
    notes: List[str] = []
    if info.get("skipped_non_numeric"):
        notes.append(
            "跳过 %d 个非数值列：%s"
            % (len(info["skipped_non_numeric"]),
               ", ".join(map(str, info["skipped_non_numeric"]))))
    if info.get("imputed_nan_count"):
        notes.append(
            "使用策略 %s 填充了 %d 个 NaN 值。"
            % (info.get("impute", "median"), info["imputed_nan_count"]))
    if info.get("source") == "any":
        notes.append("未显式指定列，已合并 target_columns + feature_columns 作为分析对象。")
    if info.get("source") == "feature":
        notes.append("target_columns 为空，已退回到 feature_columns。")
    if info.get("note"):
        notes.append(str(info["note"]))
    if extra:
        notes.extend(extra)
    return notes


def truncate_list(items: List[Any], limit: int = 50) -> List[Any]:
    """Return at most ``limit`` items, with a trailing ``"..."`` marker."""
    if limit <= 0 or len(items) <= limit:
        return list(items)
    out = list(items[:limit])
    out.append("...（共 %d 项，已截断展示前 %d 项）" % (len(items), limit))
    return out


# ----------------------------------------------------------------------
# Small statistical primitives
# ----------------------------------------------------------------------

def safe_mean(x: Sequence[float]) -> Optional[float]:
    arr = np.asarray(x, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return None
    return float(arr.mean())


def safe_std(x: Sequence[float], ddof: int = 1) -> Optional[float]:
    arr = np.asarray(x, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size <= ddof:
        return None
    return float(arr.std(ddof=ddof))


def safe_percentile(
    x: Sequence[float],
    q: Union[float, Sequence[float]],
) -> Any:
    arr = np.asarray(x, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return None if np.isscalar(q) else [None] * len(list(q))
    return np.percentile(arr, q)


def linear_slope(y: Sequence[float]) -> Optional[Tuple[float, float]]:
    """Ordinary-least-squares slope against an integer index.

    Returns ``(slope, r_squared)`` or ``None`` when there is not enough
    finite data.
    """
    arr = np.asarray(y, dtype=float)
    mask = np.isfinite(arr)
    if mask.sum() < 2:
        return None
    x = np.flatnonzero(mask).astype(float)
    yy = arr[mask]
    n = float(x.size)
    xm = x.mean()
    ym = yy.mean()
    denom = float(((x - xm) ** 2).sum())
    if denom == 0:
        return 0.0, 0.0
    slope = float(((x - xm) * (yy - ym)).sum() / denom)
    # R²
    pred = slope * (x - xm) + ym
    ss_res = float(((yy - pred) ** 2).sum())
    ss_tot = float(((yy - ym) ** 2).sum())
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    return slope, r2


def rolling_apply(
    s: pd.Series,
    window: int,
    fn: str,
    min_periods: Optional[int] = None,
) -> pd.Series:
    """Uniform rolling aggregator; ``fn`` ∈ {mean, std, var, min, max, median}."""
    if window < 2:
        window = 2
    if min_periods is None:
        min_periods = 1
    roll = s.rolling(window=window, min_periods=min_periods)
    return getattr(roll, fn)()


def rankdata(a: Sequence[float]) -> np.ndarray:
    """Average-rank, NaN-safe."""
    arr = np.asarray(a, dtype=float)
    finite = np.isfinite(arr)
    out = np.full(arr.shape, np.nan)
    if finite.any():
        order = arr[finite].argsort()
        ranks = np.empty(order.size, dtype=float)
        ranks[order] = np.arange(1, order.size + 1)
        # Tie correction via average ranks.
        # (Simple implementation that matches scipy.stats.rankdata for average method.)
        sorted_vals = arr[finite][order]
        i = 0
        n = order.size
        while i < n:
            j = i + 1
            while j < n and sorted_vals[j] == sorted_vals[i]:
                j += 1
            if j > i + 1:
                avg = (i + 1 + j) / 2.0  # average of ranks i+1..j
                ranks[order[i:j]] = avg
            i = j
        out[finite] = ranks
    return out


def bootstrap_ci(
    x: Sequence[float],
    stat_fn=np.mean,
    n_boot: int = 500,
    alpha: float = 0.05,
    random_state: Optional[int] = None,
) -> Tuple[Optional[float], Optional[float]]:
    """Percentile bootstrap confidence interval for ``stat_fn(x)``."""
    arr = np.asarray(x, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size < 2:
        return None, None
    rng = np.random.RandomState(random_state) if random_state is not None else np.random
    idx = rng.randint(0, arr.size, size=(n_boot, arr.size))
    samples = arr[idx]
    stats = np.apply_along_axis(stat_fn, 1, samples)
    lo = float(np.percentile(stats, 100.0 * alpha / 2.0))
    hi = float(np.percentile(stats, 100.0 * (1.0 - alpha / 2.0)))
    return lo, hi


# ----------------------------------------------------------------------
# Output envelope
# ----------------------------------------------------------------------

def make_envelope(
    tool_name: str,
    summary: str,
    key_findings: List[str],
    metrics: Dict[str, Any],
    recommendations: Optional[List[str]] = None,
    notes: Optional[List[str]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the canonical analysis-tool return dict.

    All analysis tools return this shape so the LLM can parse them
    uniformly::

        {
            "task_type": "analysis",
            "tool_name": ...,
            "summary": ...,
            "key_findings": [...],
            "metrics": {...},
            "recommendations": [...],
            "notes": [...],
        }
    """
    out: Dict[str, Any] = {
        "task_type": "analysis",
        "tool_name": tool_name,
        "summary": summary,
        "key_findings": list(key_findings or []),
        "metrics": metrics or {},
        "recommendations": list(recommendations or []),
        "notes": list(notes or []),
    }
    if extra:
        for k, v in extra.items():
            out.setdefault(k, v)
    return out
