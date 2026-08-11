"""Shared internal helpers for the anomaly-detection tool family.

This module centralises the boilerplate the new ``anomaly_detection_tools``
modules need:

- **Deterministic persistence paths** derived from ``thread_id`` and
  ``file_path`` (the LLM never invents paths; the framework builds them).
- KnowledgeBase singleton access (cached process-wide).
- Detector construction through the vendored ``_detector_factory``.
- Feature-matrix preparation from ``ctx.df[ctx.target_columns]``.
- Time-series matrix preparation / detection helpers (shaping, sliding-window
  bridge construction, anomaly intervals, Top-N timestamps) used by
  ``detect_with_model``'s time-series branch.
- Transductive-detector detection (no ``predict`` / ``decision_function``).
- Score summarisation (min/max/mean/std + Top-N anomaly indices).
- Score scaling helpers shared across train/predict/evaluate/ensemble tools.

Importing this module has no side effects beyond defining the helpers.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from agent_app.tools.outlier_detection_scripts.pyod.utils._detector_factory import (
    build_detector_from_plan,
)
from agent_app.tools.outlier_detection_scripts.pyod.utils.knowledge import KnowledgeBase

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Persistence paths  (thread_id + file_path + anomaly_detection prefix)
# ----------------------------------------------------------------------

# Root directory for every persisted anomaly detector.
#   agent_app/tools/anomaly_detection_tools/_common.py
#   -> agent_app/artifacts/anomaly_detection/
ARTIFACTS_ROOT: Path = (
    Path(__file__).resolve().parent.parent.parent / "artifacts" / "anomaly_detection"
)

# Sub-directory name suffix appended after the file stem. Kept constant so
# every detector for a given (thread_id, file_path) lands in the same place
# and can be enumerated without scanning the whole tree.
_FILE_SUBDIR_SUFFIX = "_anomaly_detection"


def _sanitize_path_segment(value: str, max_len: int = 64) -> str:
    """Collapse ``value`` into a filesystem-safe path segment.

    Strips directory traversals, replaces non [A-Za-z0-9_.-] characters
    with ``_``, collapses runs of underscores and trims to ``max_len``.
    Empty input becomes ``"na"`` so we never produce an empty segment.
    """
    if value is None:
        return "na"
    # Take only the basename to avoid path separators escaping the root.
    base = str(Path(str(value)).name)
    # Drop file extensions like .csv / .parquet.
    base = re.sub(r"\.[A-Za-z0-9]+$", "", base)
    base = re.sub(r"[^A-Za-z0-9_.\-]", "_", base)
    base = re.sub(r"_+", "_", base).strip("._")
    if not base:
        base = "na"
    if len(base) > max_len:
        base = base[:max_len].rstrip("._")
    return base or "na"


def get_user_id(runtime) -> str:
    """Read the owner ``user_id`` off the runtime context.

    Falls back to ``"user_default"`` when the context doesn't carry one
    (e.g. legacy callers that haven't been updated yet), so old code
    paths keep working without raising.
    """
    ctx = getattr(runtime, "context", None)
    uid = getattr(ctx, "user_id", None) if ctx is not None else None
    if not uid:
        return "user_default"
    # The API layer already sanitises user_id with a ``user_`` prefix,
    # but defensively re-sanitise so an unexpected caller can't escape
    # the artifacts root.
    seg = _sanitize_path_segment(uid)
    return "user_" + seg if not seg.startswith("user_") else seg


def get_thread_id(runtime) -> str:
    """Read ``thread_id`` off the runtime context, falling back to ``default``."""
    ctx = getattr(runtime, "context", None)
    tid = getattr(ctx, "thread_id", None) if ctx is not None else None
    return _sanitize_path_segment(tid) if tid else "default"


def get_file_stem(runtime) -> str:
    """Read ``file_path`` off the runtime context and reduce it to its stem."""
    ctx = getattr(runtime, "context", None)
    fp = getattr(ctx, "file_path", None) if ctx is not None else None
    return _sanitize_path_segment(fp) if fp else "default"


def artifacts_dir_for(runtime) -> Path:
    """Return the per-(user_id, thread_id, file_path) directory for
    persisted detectors.

    Layout::

        ARTIFACTS_ROOT/<user_id_safe>/<thread_id_safe>/
                      <file_stem_safe>_anomaly_detection/

    The user_id layer enforces per-user isolation: user A's models
    cannot be loaded, listed or deleted by user B.

    The directory is *not* created here; callers use :func:`ensure_dir`
    when they actually write.
    """
    return (
        ARTIFACTS_ROOT
        / get_user_id(runtime)
        / get_thread_id(runtime)
        / (get_file_stem(runtime) + _FILE_SUBDIR_SUFFIX)
    )


def ensure_dir(path: Path) -> Path:
    """Create ``path`` (and parents) if missing; return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_model_path(save_name: str, runtime) -> Path:
    """Build the full ``.joblib`` path for ``save_name`` under the runtime scope.

    Resolution order:

    1. **Cross-scope** — when the runtime context carries an explicit
       ``(model_save_name, model_thread_id, model_source_file)`` triple
       (set by the orchestrator from the user's front-end model picker)
       AND the requested ``save_name`` matches ``model_save_name``, the
       path is rebuilt under the model's *original*
       ``(user_id, thread_id, file_stem)`` scope. ``user_id`` is always
       taken from the current runtime so users cannot cross boundaries.
    2. **Same-scope** — otherwise the bare ``save_name`` is resolved
       under the current ``(thread_id, file_path)`` scope.
    3. **Escape hatch** — absolute paths or any string containing a path
       separator are returned verbatim, so manual absolute paths still
       work for power users.

    The LLM normally only supplies a bare ``save_name`` (e.g.
    ``"iforest_v1"``); cross-scope kicks in transparently when the user
    picked the model up-front.
    """
    if not save_name:
        raise ValueError("save_name must be a non-empty string.")

    # 1. Cross-scope: user-selected model from the front-end picker.
    ctx = getattr(runtime, "context", None)
    msn = getattr(ctx, "model_save_name", None) if ctx is not None else None
    mtid = getattr(ctx, "model_thread_id", None) if ctx is not None else None
    msrc = getattr(ctx, "model_source_file", None) if ctx is not None else None
    if msn and msn == save_name and (mtid or msrc):
        # user_id is ALWAYS rebound to the current runtime — isolation
        # between users cannot be broken by a forged picker payload.
        thread_seg = _sanitize_path_segment(mtid) if mtid else "default"
        if msrc:
            file_seg = _sanitize_path_segment(msrc) + _FILE_SUBDIR_SUFFIX
        else:
            file_seg = "default" + _FILE_SUBDIR_SUFFIX
        folder = (
            ARTIFACTS_ROOT
            / get_user_id(runtime)
            / thread_seg
            / file_seg
        )
        name = save_name if save_name.endswith(".joblib") else save_name + ".joblib"
        return folder / name

    # 3. Escape hatch (checked before same-scope so explicit absolute
    #    paths still short-circuit).
    p = Path(save_name)
    if p.is_absolute():
        return p
    if "/" in save_name or "\\" in save_name:
        return p

    # 2. Same-scope fallback.
    name = save_name
    if not name.endswith(".joblib"):
        name = name + ".joblib"
    return artifacts_dir_for(runtime) / name


def auto_save_name(detector_name: str) -> str:
    """Generate a timestamped ``save_name`` when the LLM doesn't provide one."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return "%s_%s" % (detector_name, ts)


# ----------------------------------------------------------------------
# Knowledge base
# ----------------------------------------------------------------------

_KB_CACHE: Optional[KnowledgeBase] = None


def get_knowledge_base() -> KnowledgeBase:
    """Return a process-wide cached :class:`KnowledgeBase` singleton."""
    global _KB_CACHE
    if _KB_CACHE is None:
        _KB_CACHE = KnowledgeBase()
    return _KB_CACHE


# ----------------------------------------------------------------------
# Detector construction
# ----------------------------------------------------------------------

# Detectors that ship without an out-of-sample ``predict`` / ``decision_function``.
# They only expose ``decision_scores_`` and ``labels_`` after ``fit``.
_TRANSDUCTIVE_NAMES = {"MatrixProfile"}


def is_transductive(detector_name: str) -> bool:
    """Return True for detectors that cannot score new samples.

    Currently this covers ``MatrixProfile``. The check is name-based so
    callers can branch before attempting ``predict``/``decision_function``.
    """
    return detector_name in _TRANSDUCTIVE_NAMES


def build_detector_by_name(
    detector_name: str,
    params: Optional[Dict[str, Any]] = None,
    contamination: float = 0.1,
    random_state: Optional[int] = None,
):
    """Build an unfitted detector by name using the vendored factory.

    Wraps :func:`build_detector_from_plan` and additionally makes sure
    ``contamination`` lands on the resulting instance: the factory does
    not inject it on its own, so detectors that accept it as a constructor
    argument need it merged into ``params`` here.

    Parameters
    ----------
    detector_name : str
        Registered algorithm name (e.g. ``"IForest"``, ``"MatrixProfile"``).
    params : dict, optional
        Extra constructor kwargs forwarded to the detector class.
    contamination : float, default 0.1
        Expected outlier proportion. Merged into ``params`` when the
        detector's ``__init__`` declares a ``contamination`` parameter and
        the caller did not already supply one.
    random_state : int, optional
        Seed forwarded when the detector ``__init__`` declares
        ``random_state`` explicitly.

    Returns
    -------
    detector : BaseDetector
        Unfitted detector instance.

    Raises
    ------
    ValueError
        If ``detector_name`` is unknown or not in a buildable status.
    """
    kb = get_knowledge_base()
    merged_params: Dict[str, Any] = dict(params or {})

    algo = kb.get_algorithm(detector_name)
    if algo is None:
        raise ValueError(
            "Unknown detector '%s'. Use list_pyod_detectors to enumerate "
            "available algorithms." % detector_name)

    if "contamination" not in merged_params:
        merged_params["contamination"] = contamination

    plan = {
        "detector_name": detector_name,
        "params": merged_params,
    }
    detector = build_detector_from_plan(plan, kb, random_state=random_state)

    try:
        detector.contamination = contamination
    except Exception:  # pragma: no cover - defensive
        pass
    return detector


# ----------------------------------------------------------------------
# Fitted-attribute extraction
# ----------------------------------------------------------------------

def decision_scores_(detector) -> np.ndarray:
    """Pull ``decision_scores_`` off a fitted detector as float ndarray."""
    scores = getattr(detector, "decision_scores_", None)
    if scores is None:
        raise RuntimeError(
            "Detector %r has no decision_scores_ after fit()."
            % type(detector).__name__)
    return np.asarray(scores, dtype=float).ravel()


def labels_(detector) -> np.ndarray:
    labels = getattr(detector, "labels_", None)
    if labels is None:
        return np.zeros(0, dtype=int)
    return np.asarray(labels, dtype=int).ravel()


def threshold_(detector) -> Optional[float]:
    th = getattr(detector, "threshold_", None)
    return None if th is None else float(th)


def score_with_detector(
    detector,
    X: np.ndarray,
    detector_name: str,
) -> Tuple[np.ndarray, np.ndarray, Optional[float], bool]:
    """Return ``(scores, labels, threshold, supports_out_of_sample)``.

    For transductive detectors (``MatrixProfile``) only the scores
    computed during ``fit`` are available, so we read them off the
    fitted object directly and never call ``predict``/``decision_function``.
    """
    if is_transductive(detector_name):
        scores = decision_scores_(detector)
        labels_arr = labels_(detector)
        th = threshold_(detector)
        return scores, labels_arr, th, False

    try:
        scores = np.asarray(detector.decision_function(X), dtype=float).ravel()
    except NotImplementedError:
        scores = decision_scores_(detector)
        labels_arr = labels_(detector)
        th = threshold_(detector)
        return scores, labels_arr, th, False

    th = threshold_(detector)
    if th is None:
        contamination = float(getattr(detector, "contamination", 0.1)) or 0.1
        th = float(np.percentile(
            scores, 100.0 * (1.0 - min(max(contamination, 1e-4), 0.5))))
    labels_arr = (scores > th).astype(int)
    return scores, labels_arr, th, True


# ----------------------------------------------------------------------
# Feature matrix preparation
# ----------------------------------------------------------------------

def prepare_feature_matrix(runtime) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Extract a numeric feature matrix from the tool runtime context.

    Selects ``ctx.target_columns`` from ``ctx.df`` (falling back to
    ``ctx.feature_columns`` when the targets list is empty), keeps only
    numeric columns, fills NaNs with per-column medians, and returns the
    matrix plus a diagnostics dict describing what was skipped or imputed.

    Parameters
    ----------
    runtime : ToolRuntime
        LangChain tool runtime exposing ``runtime.context.df`` and
        ``runtime.context.target_columns``.

    Returns
    -------
    X : np.ndarray of shape (n_samples, n_features)
        Float64 feature matrix ready for PyOD detectors.
    info : dict
        Diagnostics with keys ``used_columns``, ``source`` (``"target"``
        or ``"feature"``), ``skipped_non_numeric``, ``imputed_nan_count``,
        ``n_samples``, ``n_features``.
    """
    ctx = runtime.context
    df: pd.DataFrame = ctx.df
    targets: List[str] = list(getattr(ctx, "target_columns", None) or [])
    features: List[str] = list(getattr(ctx, "feature_columns", None) or [])

    info: Dict[str, Any] = {
        "used_columns": [],
        "source": "target",
        "skipped_non_numeric": [],
        "imputed_nan_count": 0,
        "n_samples": int(len(df)),
        "n_features": 0,
    }

    if not targets and not features:
        raise ValueError(
            "No target_columns or feature_columns available in context. "
            "Cannot build a feature matrix for anomaly detection.")

    # Prefer target_columns; fall back to feature_columns when targets are empty.
    if targets:
        candidates = targets
        info["source"] = "target"
    else:
        candidates = features
        info["source"] = "feature"

    present = [c for c in candidates if c in df.columns]
    missing = [c for c in candidates if c not in df.columns]
    if missing:
        logger.warning(
            "prepare_feature_matrix: columns missing from df: %s", missing)

    numeric_cols: List[str] = []
    skipped_non_numeric: List[str] = []
    for c in present:
        col = df[c]
        as_num = pd.to_numeric(col, errors="coerce")
        if as_num.notna().any():
            numeric_cols.append(c)
        else:
            skipped_non_numeric.append(c)

    if not numeric_cols:
        raise ValueError(
            "No numeric columns available in candidates=%r. "
            "All candidate columns were non-numeric or all-NaN."
            % (candidates,))

    sub = df[numeric_cols].apply(pd.to_numeric, errors="coerce")

    nan_count = int(sub.isna().sum().sum())
    if nan_count > 0:
        medians = sub.median(axis=0, skipna=True)
        sub = sub.fillna(medians).fillna(0.0)

    X = sub.to_numpy(dtype=np.float64)

    info["used_columns"] = numeric_cols
    info["skipped_non_numeric"] = skipped_non_numeric
    info["imputed_nan_count"] = nan_count
    info["n_features"] = int(X.shape[1])
    return X, info


# ----------------------------------------------------------------------
# Time-series matrix preparation / detection
#
# Shared by ``detect_with_model``'s time-series branch. These mirror the
# tabular helpers above but preserve temporal order (1-D ``(n_timestamps,)``
# or 2-D ``(n_timestamps, n_channels)``) and impute NaNs with ffill/bfill
# instead of the column median, which suits ordered series better.
# ----------------------------------------------------------------------

# Detectors that ship as native PyOD time-series implementations. Any other
# name is bridged through :class:`TimeSeriesOD` (sliding windows) by
# :func:`build_ts_detector`.
TS_NATIVE_DETECTORS = {
    "KShape", "MatrixProfile", "SpectralResidual", "SAND",
    "LSTMAD", "AnomalyTransformer", "TimeSeriesOD",
}

def prepare_ts_matrix(runtime, time_column: Optional[str]):
    """Extract a time-series matrix from context.

    Returns ``(X, time_index, info)`` where ``X`` has shape
    ``(n_timestamps,)`` when there is a single channel, or
    ``(n_timestamps, n_channels)`` for multi-channel data. ``time_index``
    is the per-row timestamp/position used to label Top-N anomaly windows
    in the result.
    """
    ctx = runtime.context
    df: pd.DataFrame = ctx.df
    targets: List[str] = list(getattr(ctx, "target_columns", None) or [])
    features: List[str] = list(getattr(ctx, "feature_columns", None) or [])
    if not targets and not features:
        raise ValueError(
            "No target_columns or feature_columns available in context; "
            "cannot build a time series matrix.")
    candidates = targets if targets else features

    present = [c for c in candidates if c in df.columns]
    skipped_missing = [c for c in candidates if c not in df.columns]
    numeric_cols: List[str] = []
    skipped_non_numeric: List[str] = []
    for c in present:
        as_num = pd.to_numeric(df[c], errors="coerce")
        if as_num.notna().any():
            numeric_cols.append(c)
        else:
            skipped_non_numeric.append(c)
    if not numeric_cols:
        raise ValueError(
            "No numeric columns available in candidates=%r." % (candidates,))

    sub = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
    nan_count = int(sub.isna().sum().sum())
    if nan_count > 0:
        # Forward-fill then back-fill for time series (preserves temporal locality).
        sub = sub.ffill().bfill().fillna(0.0)

    arr = sub.to_numpy(dtype=np.float64)
    if arr.shape[1] == 1:
        ts_array = arr[:, 0]
    else:
        ts_array = arr

    if time_column and time_column in df.columns:
        time_index = df[time_column].tolist()
        time_column_used: Optional[str] = time_column
    else:
        time_index = list(range(arr.shape[0]))
        time_column_used = None

    info = {
        "used_columns": numeric_cols,
        "source": "target" if targets else "feature",
        "skipped_missing": skipped_missing,
        "skipped_non_numeric": skipped_non_numeric,
        "imputed_nan_count": nan_count,
        "n_timestamps": int(arr.shape[0]),
        "n_channels": int(arr.shape[1]),
        "time_column": time_column_used,
    }
    return ts_array, time_index, info


def build_ts_detector(
    detector_name: str,
    window_size: Optional[int],
    params: Optional[Dict[str, Any]],
    contamination: float,
    random_state: Optional[int] = None,
):
    """Build a time-series detector.

    Falls back to wrapping an arbitrary tabular detector with
    :class:`TimeSeriesOD` (sliding windows) when ``detector_name`` is not
    a native ``ts_*`` detector.
    """
    name = detector_name
    merged: Dict[str, Any] = dict(params or {})

    if name not in TS_NATIVE_DETECTORS:
        bridge_params: Dict[str, Any] = {"contamination": contamination}
        if window_size is not None:
            bridge_params["window_size"] = window_size
        if merged:
            bridge_params["params"] = merged
        return build_detector_by_name(
            "TimeSeriesOD",
            params={"detector": name, **bridge_params},
            contamination=contamination,
            random_state=random_state,
        )

    if window_size is not None and "window_size" not in merged:
        if name != "SpectralResidual":  # uses score_window instead
            merged["window_size"] = window_size
    return build_detector_by_name(
        name,
        params=merged,
        contamination=contamination,
        random_state=random_state,
    )


def anomaly_intervals(
    labels: np.ndarray,
    time_index: Optional[List[Any]],
    threshold: Optional[float],
    max_intervals: int = 20,
) -> List[Dict[str, Any]]:
    """Collapse binary per-timestamp labels into contiguous intervals."""
    labels = np.asarray(labels, dtype=int)
    if labels.size == 0:
        return []
    flag = labels > 0
    if not flag.any():
        return []
    diff = np.diff(flag.astype(int), prepend=0, append=0)
    starts = np.nonzero(diff == 1)[0]
    ends = np.nonzero(diff == -1)[0]
    intervals: List[Dict[str, Any]] = []
    for s, e in zip(starts, ends):
        if time_index is not None:
            t_start = time_index[s]
            t_end = time_index[e - 1]
        else:
            t_start = int(s)
            t_end = int(e - 1)
        intervals.append({
            "start_index": int(s),
            "end_index": int(e - 1),
            "length": int(e - s),
            "time_start": t_start,
            "time_end": t_end,
        })
        if len(intervals) >= max_intervals:
            break
    return intervals


def top_ts_anomalies(
    scores: np.ndarray,
    time_index: Optional[List[Any]],
    threshold: Optional[float],
    top_n: int,
) -> List[Dict[str, Any]]:
    """Return the top-N highest-scoring timestamps with context."""
    scores = np.asarray(scores, dtype=float).ravel()
    n = min(int(top_n), len(scores)) if top_n else 0
    if n <= 0:
        return []
    finite = np.isfinite(scores)
    valid_positions = np.nonzero(finite)[0]
    valid_scores = scores[finite]
    if valid_scores.size == 0:
        return []
    order = np.argsort(valid_scores)[::-1][:n]
    picked = valid_positions[order]
    rows: List[Dict[str, Any]] = []
    for pos in picked:
        item: Dict[str, Any] = {
            "timestamp_index": int(pos),
            "score": float(scores[pos]),
            "time": time_index[pos] if time_index is not None else int(pos),
        }
        if threshold is not None:
            item["is_anomaly"] = bool(scores[pos] > threshold)
        rows.append(item)
    return rows


def format_ts_notes(info: Dict[str, Any], extra: Optional[List[str]] = None) -> List[str]:
    """Format time-series diagnostics + extra hints into a ``notes`` list."""
    notes: List[str] = []
    if info.get("skipped_missing"):
        notes.append(
            "target_columns 中缺失的列：%s"
            % ", ".join(info["skipped_missing"]))
    if info.get("skipped_non_numeric"):
        notes.append(
            "跳过 %d 个非数值列：%s"
            % (len(info["skipped_non_numeric"]),
               ", ".join(map(str, info["skipped_non_numeric"]))))
    if info.get("imputed_nan_count"):
        notes.append(
            "用 ffill/bfill 填充了 %d 个 NaN 值（时序优先保留时序连续性）。"
            % info["imputed_nan_count"])
    if info.get("source") == "feature":
        notes.append("target_columns 为空，退回到 feature_columns 作为时序输入。")
    if extra:
        notes.extend(extra)
    return notes


# ----------------------------------------------------------------------
# Score scaling / summarisation
# ----------------------------------------------------------------------

def scores_summary(
    scores: np.ndarray,
    threshold: Optional[float] = None,
    top_n: int = 10,
) -> Dict[str, Any]:
    """Summarise a 1-D score array.

    Returns min/max/mean/std, optional threshold-driven anomaly count,
    and the indices of the ``top_n`` highest-scoring samples.

    NaNs in ``scores`` are ignored for the statistical aggregates; the
    returned ``top_indices`` refer to positions in the original array.
    """
    scores = np.asarray(scores, dtype=float).ravel()
    valid_mask = np.isfinite(scores)
    valid = scores[valid_mask]

    summary: Dict[str, Any] = {
        "n_total": int(scores.shape[0]),
        "n_valid": int(valid_mask.sum()),
    }

    if valid.size == 0:
        summary.update({
            "min": None, "max": None, "mean": None, "std": None,
        })
    else:
        summary.update({
            "min": float(np.min(valid)),
            "max": float(np.max(valid)),
            "mean": float(np.mean(valid)),
            "std": float(np.std(valid)),
        })

    if threshold is not None and valid.size > 0:
        above = scores > threshold
        summary["threshold"] = float(threshold)
        summary["n_above_threshold"] = int(above.sum())

    if valid.size > 0 and top_n and top_n > 0:
        k = min(int(top_n), valid.size)
        valid_positions = np.nonzero(valid_mask)[0]
        order = np.argsort(valid)[::-1][:k]
        top_positions = valid_positions[order].tolist()
        summary["top_indices"] = top_positions
        summary["top_scores"] = [float(scores[i]) for i in top_positions]

    return summary


def top_anomaly_rows(
    df: pd.DataFrame,
    scores: np.ndarray,
    threshold: Optional[float],
    top_n: int,
    columns: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Return the ``top_n`` highest-scoring rows with their original values.

    ``columns`` controls which DataFrame columns are inlined into each
    result entry; defaults to all columns. Values are passed through
    :func:`json_safe` so the output is JSON-serialisable.
    """
    scores = np.asarray(scores, dtype=float).ravel()
    n = min(int(top_n), len(scores)) if top_n else 0
    if n <= 0:
        return []
    finite = np.isfinite(scores)
    valid_positions = np.nonzero(finite)[0]
    valid_scores = scores[finite]
    if valid_scores.size == 0:
        return []
    order = np.argsort(valid_scores)[::-1][:n]
    picked = valid_positions[order]

    cols = list(columns) if columns else list(df.columns)
    rows: List[Dict[str, Any]] = []
    for pos in picked:
        item: Dict[str, Any] = {
            "row_index": int(pos),
            "score": float(scores[pos]),
        }
        if threshold is not None:
            item["is_anomaly"] = bool(scores[pos] > threshold)
        try:
            item["values"] = {
                str(c): json_safe(df.iloc[pos][c])
                for c in cols
            }
        except Exception:  # pragma: no cover - defensive on weird indexes
            item["values"] = {}
        rows.append(item)
    return rows


def json_safe(v: Any) -> Any:
    """Best-effort conversion of a scalar DataFrame cell to JSON-safe value."""
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def format_notes(info: Dict[str, Any], extra: Optional[List[str]] = None) -> List[str]:
    """Format diagnostics + extra hints into a flat ``notes`` list."""
    notes: List[str] = []
    if info.get("skipped_non_numeric"):
        notes.append(
            "跳过 %d 个非数值列：%s"
            % (len(info["skipped_non_numeric"]),
               ", ".join(map(str, info["skipped_non_numeric"]))))
    if info.get("imputed_nan_count"):
        notes.append("用列中位数填充了 %d 个 NaN 值。" % info["imputed_nan_count"])
    if info.get("source") == "feature":
        notes.append("target_columns 为空，已退回到 feature_columns 作为检测输入。")
    if extra:
        notes.extend(extra)
    return notes


def minmax_scale(scores: np.ndarray) -> np.ndarray:
    """Min-max scale to ``[0, 1]``; returns zeros if range is degenerate."""
    s = np.asarray(scores, dtype=float).ravel()
    lo = float(np.min(s)) if s.size else 0.0
    hi = float(np.max(s)) if s.size else 0.0
    rng = hi - lo
    if not np.isfinite(rng) or rng <= 0:
        return np.zeros_like(s)
    return (s - lo) / rng
