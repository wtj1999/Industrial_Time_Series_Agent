"""Shared internal helpers for the prediction tool family.

Centralises the boilerplate every ``prediction_tools`` submodule needs:

- **Two upstream HTTP endpoints** for the time-series foundation-model
  service, plus a per-model registry that maps each of the seven model
  names (``sundial`` / ``toto-2`` / ``timer-s1`` / ``chronos-2`` /
  ``timesfm-2.5`` / ``moirai-2.0-R-small`` / ``tirex-1.1-gifteval``) to
  its endpoint, output tensor shape and output type
  (``"samples"`` vs ``"quantiles"``).
- **Series preparation** from ``ctx.df[ctx.target_columns]``: NaN-safe
  coercion, optional trailing-window slicing and per-column diagnostics.
- **HTTP call** to the forecasting service (``requests.post`` with a
  generous timeout), returning the parsed JSON body.
- **Output normalisation**: every model's raw ``predict_data_result``
  tensor is collapsed to a uniform schema
  ``{point_forecast, quantiles, samples, shape, model}`` so the agent
  and downstream tooling never need to branch on tensor layout.
- **Forecast-error metrics** (MAE / RMSE / MAPE / sMAPE / MASE) reused
  by the backtest tool.
- **JSON-safe / note formatting / envelope** helpers matching the
  analysis-family conventions.

Importing this module has no side effects beyond defining the helpers.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# Cap on the per-column history length we ship to the frontend for any
# prediction-family chart. Beyond this we strided-downsample (always
# preserving the final sample so the history→forecast join point stays
# exact). Mirrors the anomaly chart's downsampling philosophy but for
# a plain 1-D array. Used by both forecast and backtest tools.
CHART_HISTORY_MAX_POINTS = 400


def downsample_history(
    arr: np.ndarray,
    max_points: int = CHART_HISTORY_MAX_POINTS,
) -> Tuple[List[float], int, bool]:
    """Stride-downsample a 1-D history array for a chart payload.

    Returns ``(history_list, n_full, downsampled)`` where:

    - ``history_list`` is the (possibly subsampled) JSON-safe list of
      floats, always ending at the same final sample as ``arr`` so the
      history→forecast junction renders cleanly.
    - ``n_full`` is the original length ``len(arr)``.
    - ``downsampled`` is ``True`` iff subsampling was applied.
    """
    if arr is None:
        return [], 0, False
    n_full = int(arr.size)
    if n_full == 0:
        return [], 0, False
    if n_full <= max_points:
        return [round_float(float(v)) for v in arr.tolist()], n_full, False

    stride = math.ceil(n_full / max_points)
    idx = list(range(0, n_full, stride))
    # Guarantee the last point is included so the forecast "blooms"
    # from the exact same value the chart shows as the final history
    # sample.
    if idx[-1] != n_full - 1:
        idx.append(n_full - 1)
    return [round_float(float(arr[i])) for i in idx], n_full, True


# ----------------------------------------------------------------------
# Upstream HTTP endpoints
# ----------------------------------------------------------------------

# Endpoint #1 — serves ``sundial`` and ``toto-2``.
API_ENDPOINT_1: str = "http://10.2.128.43:19053/time/seriesPredict"

# Endpoint #2 — serves ``sundial``, ``chronos-2``, ``timesfm-2.5``,
# ``moirai-2.0-R-small``, ``timer-s1`` and ``tirex-1.1-gifteval``.
API_ENDPOINT_2: str = "http://10.2.128.43:19054/time/seriesPredict"

# Default per-request timeout in seconds. Foundation-model inference on
# long series can take a while, so keep this generous but bounded.
DEFAULT_TIMEOUT: int = 120

# Soft cap on the number of sample paths we ship back to the LLM. Sundial
# can emit hundreds of paths; truncating keeps the tool result inside a
# sane JSON payload size without losing the density information (the
# quantile bands are always computed from the *full* sample set first).
MAX_SAMPLE_PATHS: int = 100


# ----------------------------------------------------------------------
# Quantile levels & model registry
# ----------------------------------------------------------------------

# Standard 9 quantile levels emitted by every quantile-type model. The
# order matches the leading axis of their output tensors (ascending).
QUANTILE_LEVELS: List[float] = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


# Each model's static descriptor.
#
# The API protocol has been unified across all seven foundation models:
#
#   - Request ``dataList``:  2-D ``[n_variables, input_history_length]``
#   - Response ``predict_data_result``: 3-D ``[n_variables, prediction_length, 9]``
#     where the trailing 9 is the fixed set of quantile levels (p10..p90).
#
# ``output_type`` is kept for backwards compatibility with callers that
# still read it (e.g. knowledge tools) but is now ``"quantiles"`` for
# every model — there is no longer a ``"samples"`` branch.
#
# ``output_shape`` documents the unified response tensor layout.
MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "sundial": {
        "endpoints": [API_ENDPOINT_1, API_ENDPOINT_2],
        "preferred_endpoint": API_ENDPOINT_1,
        "output_type": "quantiles",
        "output_shape": "[n_variables, prediction_length, 9]",
        "multivariate": False,
        "description": "Sundial 基础模型，输出 9 分位数密度预测。",
        "tags": ["general", "probabilistic", "robust"],
    },
    "toto-2": {
        "endpoints": [API_ENDPOINT_1],
        "preferred_endpoint": API_ENDPOINT_1,
        "output_type": "quantiles",
        "output_shape": "[n_variables, prediction_length, 9]",
        "multivariate": True,
        "description": "ToTo-2.0-2.5B 多变量分位数预测模型。",
        "tags": ["multivariate"],
    },
    "timer-s1": {
        "endpoints": [API_ENDPOINT_2],
        "preferred_endpoint": API_ENDPOINT_2,
        "output_type": "quantiles",
        "output_shape": "[n_variables, prediction_length, 9]",
        "multivariate": False,
        "description": "Timer-XL S1 单变量分位数预测。",
        "tags": [],
    },
    "chronos-2": {
        "endpoints": [API_ENDPOINT_2],
        "preferred_endpoint": API_ENDPOINT_2,
        "output_type": "quantiles",
        "output_shape": "[n_variables, prediction_length, 9]",
        "multivariate": False,
        "description": "Chronos-2 语言类时序基础模型。",
        "tags": [],
    },
    "timesfm-2.5": {
        "endpoints": [API_ENDPOINT_2],
        "preferred_endpoint": API_ENDPOINT_2,
        "output_type": "quantiles",
        "output_shape": "[n_variables, prediction_length, 9]",
        "multivariate": False,
        "description": "TimesFM-2.5 解码器类时序预测模型。",
        "tags": [],
    },
    "moirai-2.0-R-small": {
        "endpoints": [API_ENDPOINT_2],
        "preferred_endpoint": API_ENDPOINT_2,
        "output_type": "quantiles",
        "output_shape": "[n_variables, prediction_length, 9]",
        "multivariate": False,
        "description": "Moirai-2.0-R-small，Salesforce 基础模型。",
        "tags": [],
    },
    "tirex-1.1-gifteval": {
        "endpoints": [API_ENDPOINT_2],
        "preferred_endpoint": API_ENDPOINT_2,
        "output_type": "quantiles",
        "output_shape": "[n_variables, prediction_length, 9]",
        "multivariate": False,
        "description": "TI-Rex-1.1 gifteval 分位数预测模型。",
        "tags": [],
    },
}

AVAILABLE_MODELS: List[str] = sorted(MODEL_REGISTRY.keys())


def resolve_model(model_name: str) -> Tuple[str, Dict[str, Any]]:
    """Return ``(canonical_name, registry_entry)`` for ``model_name``.

    Match is case-insensitive on the canonical key. Raises ``ValueError``
    when the name is unknown so the LLM is steered back to
    :func:`list_prediction_models`.
    """
    if not model_name or not isinstance(model_name, str):
        raise ValueError("model_name 不能为空。")

    if model_name in MODEL_REGISTRY:
        return model_name, MODEL_REGISTRY[model_name]

    lower = model_name.lower()
    for key, entry in MODEL_REGISTRY.items():
        if key.lower() == lower:
            return key, entry

    raise ValueError(
        "未知预测模型 %r。可用模型：%s。可调用 list_prediction_models 查询。"
        % (model_name, ", ".join(AVAILABLE_MODELS)))


# ----------------------------------------------------------------------
# Context accessors
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
    cols = _ctx_attr(runtime, "target_columns", None) or []
    return [str(c) for c in cols if c is not None]


def get_feature_columns(runtime) -> List[str]:
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
    """Partition ``columns`` into (numeric, non_numeric, missing)."""
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


def prepare_series(
    df: pd.DataFrame,
    column: str,
    impute: str = "ffill",
    history_tail: Optional[int] = None,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Return ``(values, info)`` for a single column.

    The returned array is float64 and NaN-safe. ``impute`` supports
    ``"ffill"`` (default, natural for time series), ``"bfill"``,
    ``"median"``, ``"zero"`` and ``"drop"``. When ``history_tail`` is
    given, only the last ``history_tail`` values (post-impute) are
    returned.
    """
    if column not in df.columns:
        raise ValueError("列 %r 不在 df.columns 中。" % column)
    raw = pd.to_numeric(df[column], errors="coerce")
    n_nan = int(raw.isna().sum())
    info: Dict[str, Any] = {
        "column": column,
        "n_total": int(len(raw)),
        "n_nan": n_nan,
        "impute": impute,
        "history_tail": history_tail,
    }

    s = raw
    if n_nan > 0:
        if impute == "ffill":
            s = s.ffill().bfill().fillna(0.0)
        elif impute == "bfill":
            s = s.bfill().ffill().fillna(0.0)
        elif impute == "median":
            med = s.median(skipna=True)
            s = s.fillna(med if pd.notna(med) else 0.0)
        elif impute == "zero":
            s = s.fillna(0.0)
        elif impute == "drop":
            s = s.dropna()
        else:
            med = s.median(skipna=True)
            s = s.fillna(med if pd.notna(med) else 0.0)

    arr = s.to_numpy(dtype=float)
    finite = arr[np.isfinite(arr)]
    info["n_valid_full"] = int(finite.size)

    if history_tail is not None and arr.size > history_tail:
        arr = arr[-int(history_tail):]
    info["n_input"] = int(arr.size)
    return arr, info


# ----------------------------------------------------------------------
# HTTP call to the upstream prediction service
# ----------------------------------------------------------------------

def call_predict_api(
    model: str,
    data_list: Sequence[float],
    prediction_length: int,
    endpoint: Optional[str] = None,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    """POST to the forecasting service. Returns the parsed JSON body.

    The endpoint is resolved automatically from :func:`resolve_model`
    when ``endpoint`` is ``None``. ``model`` is matched case-insensitively
    and the canonical name is sent in the payload.

    The unified API protocol expects ``dataList`` as a 2-D array of shape
    ``[n_variables, input_history_length]``. The prediction tools call
    the service one variable at a time, so this function wraps the
    caller's flat 1-D ``data_list`` into ``[1, len(data_list)]`` before
    sending. The response is correspondingly ``[1, prediction_length, 9]``.
    """
    import requests  # local import keeps module import side-effect free

    canonical, entry = resolve_model(model)
    if endpoint is None:
        endpoint = entry["preferred_endpoint"]
    if timeout is None:
        timeout = DEFAULT_TIMEOUT
    if prediction_length <= 0:
        raise ValueError("prediction_length 必须 > 0，当前=%r" % prediction_length)

    # Unified protocol: dataList is 2-D [n_variables, history_length].
    # All prediction-family tools operate per-column (single variable),
    # so we wrap the caller's 1-D array into one outer row.
    data_2d = [[float(x) for x in data_list]]
    payload = {
        "model": canonical,
        "dataList": data_2d,
        "predictionLength": int(prediction_length),
    }
    logger.info(
        "call_predict_api: endpoint=%s model=%s n_input=%d horizon=%d",
        endpoint, canonical, len(payload["dataList"][0]), prediction_length)
    resp = requests.post(endpoint, json=payload, timeout=timeout)
    resp.raise_for_status()
    body = resp.json()
    return body if isinstance(body, dict) else {"raw": body}


# ----------------------------------------------------------------------
# Output normalisation
# ----------------------------------------------------------------------

def normalize_forecast(
    raw: Any,
    model: str,
    prediction_length: int,
    max_sample_paths: int = MAX_SAMPLE_PATHS,  # retained for API compat, unused
) -> Dict[str, Any]:
    """Convert the API's raw ``predict_data_result`` into a uniform schema.

    The unified API protocol returns ``predict_data_result`` as a 3-D
    array of shape ``[n_variables, prediction_length, 9]`` where the
    trailing 9 is the fixed set of quantile levels (p10..p90, ascending).
    All seven foundation models now share this single output format, so
    the per-model tensor-orientation helpers that previously lived here
    (``_squeeze_singleton_axes`` / ``_orient_samples_matrix`` /
    ``_orient_quantile_matrix``) have been retired.

    The prediction tools always call the service one variable at a time
    (see :func:`call_predict_api`), so the response we receive is
    ``[1, prediction_length, 9]`` and we extract variable 0.

    Returns::

        {
            "point_forecast": List[float],            # length = horizon (= p50)
            "quantiles": { "p10": [...], ..., "p90": [...] },  # 9 levels
            "samples": None,                          # reserved, always None
            "shape": str,                             # original tensor shape
            "model": str,
        }
    """
    canonical, _ = resolve_model(model)
    arr = np.asarray(raw, dtype=float)
    shape_str = str(arr.shape)
    horizon = int(prediction_length)

    if arr.ndim != 3:
        raise ValueError(
            "predict_data_result 维度不符合统一协议，期望 3-D "
            "[变量数, 预测长度, 9]，实际 %dD (shape=%s)"
            % (arr.ndim, shape_str))

    n_vars, n_steps, n_quantiles = arr.shape
    if n_vars == 0:
        raise ValueError("predict_data_result 变量数为 0")
    if n_quantiles != len(QUANTILE_LEVELS):
        raise ValueError(
            "分位数维度 != %d，实际 %d (shape=%s)"
            % (len(QUANTILE_LEVELS), n_quantiles, shape_str))

    # Take variable 0 (callers always invoke with a single variable).
    qs = arr[0]  # shape: [prediction_length, 9]

    if qs.shape[0] == 0:
        raise ValueError("predict_data_result 预测长度为 0")

    # Align the horizon axis to the requested prediction_length. The
    # upstream service should already match, but we guard anyway — pad
    # by repeating the last step or truncate from the end.
    cur = qs.shape[0]
    if cur < horizon:
        pad = np.tile(qs[-1:], (horizon - cur, 1))
        qs = np.vstack([qs, pad])
    elif cur > horizon:
        qs = qs[:horizon]

    point = qs[:, 4]  # median (p50) — 5th of the 9 ascending levels

    quantile_dict = {
        "p%d" % int(lvl * 100): qs[:, i].tolist()
        for i, lvl in enumerate(QUANTILE_LEVELS)
    }
    return {
        "point_forecast": point.tolist(),
        "quantiles": quantile_dict,
        "samples": None,
        "shape": shape_str,
        "model": canonical,
    }


# ----------------------------------------------------------------------
# Forecast-error metrics
# ----------------------------------------------------------------------

def forecast_metrics(
    actual: Sequence[float],
    forecast: Sequence[float],
) -> Dict[str, Any]:
    """Common point-forecast error metrics.

    Inputs are 1-D arrays of equal length; NaNs are dropped pairwise.
    Returns ``mae`` / ``rmse`` / ``mape`` / ``smape`` / ``mase``.
    """
    a = np.asarray(actual, dtype=float).ravel()
    f = np.asarray(forecast, dtype=float).ravel()
    n = min(a.size, f.size)
    if n == 0:
        return {"n": 0, "note": "no overlapping samples"}
    a, f = a[:n], f[:n]
    mask = np.isfinite(a) & np.isfinite(f)
    a, f = a[mask], f[mask]
    if a.size == 0:
        return {"n": 0, "note": "no finite samples"}

    err = f - a
    abs_err = np.abs(err)
    mae = float(abs_err.mean())
    rmse = float(np.sqrt((err ** 2).mean()))

    denom_mape = np.abs(a)
    valid_mape = denom_mape > 1e-9
    mape = (
        float((abs_err[valid_mape] / denom_mape[valid_mape]).mean() * 100.0)
        if valid_mape.any() else None
    )

    denom_smape = (np.abs(a) + np.abs(f)) / 2.0
    valid_smape = denom_smape > 1e-9
    smape = (
        float((abs_err[valid_smape] / denom_smape[valid_smape]).mean() * 100.0)
        if valid_smape.any() else None
    )

    # MASE with naive lag-1 seasonal-1 denominator.
    if a.size > 1:
        naive_err = float(np.mean(np.abs(np.diff(a))))
    else:
        naive_err = 0.0
    mase = (
        float(mae / naive_err) if naive_err and naive_err > 1e-9 else None
    )

    return {
        "n": int(a.size),
        "mae": mae,
        "rmse": rmse,
        "mape": mape,
        "smape": smape,
        "mase": mase,
    }


# ----------------------------------------------------------------------
# JSON helpers / envelope / notes
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
    if isinstance(v, float) and math.isfinite(v):
        return round(v, ndigits)
    if isinstance(v, (np.floating,)) and math.isfinite(float(v)):
        return round(float(v), ndigits)
    return v


def format_notes(info: Dict[str, Any], extra: Optional[List[str]] = None) -> List[str]:
    notes: List[str] = []
    if info.get("skipped_non_numeric"):
        notes.append(
            "跳过 %d 个非数值列：%s"
            % (len(info["skipped_non_numeric"]),
               ", ".join(map(str, info["skipped_non_numeric"]))))
    if info.get("n_nan"):
        notes.append(
            "使用策略 %s 填充了 %d 个 NaN 值。"
            % (info.get("impute", "ffill"), info["n_nan"]))
    if info.get("source") == "feature":
        notes.append("target_columns 为空，已退回到 feature_columns。")
    if info.get("note"):
        notes.append(str(info["note"]))
    if extra:
        notes.extend(extra)
    return notes


def make_envelope(
    tool_name: str,
    summary: str,
    key_findings: List[str],
    metrics: Dict[str, Any],
    recommendations: Optional[List[str]] = None,
    notes: Optional[List[str]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the canonical prediction-tool return dict.

    Mirrors the analysis-family envelope shape so the orchestrator and
    downstream tooling can treat analysis / anomaly / prediction tool
    results uniformly::

        {
            "task_type": "prediction",
            "tool_name": ...,
            "summary": ...,
            "key_findings": [...],
            "metrics": {...},
            "recommendations": [...],
            "notes": [...],
        }
    """
    out: Dict[str, Any] = {
        "task_type": "prediction",
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
