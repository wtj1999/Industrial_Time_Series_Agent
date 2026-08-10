"""Forecast tools that drive the upstream HTTP prediction service.

Three tools, layered from most granular to most aggregate:

- :func:`forecast_time_series` — single-model forecast on one or more
  target columns. The workhorse.
- :func:`forecast_multi_models` — run several models on the same series
  and return side-by-side forecasts (no accuracy evaluation). Useful for
  cross-model sanity checks.
- :func:`forecast_ensemble` — combine forecasts from multiple models
  into a single point forecast (simple mean or inverse-MAPE weighting
  computed on a rolling holdout).

All three share the same column-resolution and NaN-imputation logic
from :mod:`prediction_tools._common`, so behaviour is consistent across
the family.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from langchain.tools import ToolRuntime, tool

from agent_app.tools._tool_guard import tool_guard
from agent_app.tools.prediction_tools._common import (
    AVAILABLE_MODELS,
    DEFAULT_TIMEOUT,
    MODEL_REGISTRY,
    call_predict_api,
    downsample_history,
    format_notes,
    get_df,
    make_envelope,
    normalize_forecast,
    prepare_series,
    resolve_columns,
    resolve_model,
    round_float,
    select_numeric_columns,
)

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Chart-history helper
# ----------------------------------------------------------------------

# Public re-export kept for backwards-compat with any callers that
# imported the underscore-prefixed name before the helper moved to
# ``_common``. New code should import ``downsample_history`` directly
# from ``_common``.
_downsample_history = downsample_history


# ----------------------------------------------------------------------
# Single-model forecast
# ----------------------------------------------------------------------

@tool("forecast_time_series")
@tool_guard("forecast_time_series")
def forecast_time_series(
    model: str,
    runtime: ToolRuntime,
    prediction_length: int = 8,
    history_tail: Optional[int] = None,
    impute: str = "ffill",
    endpoint: Optional[str] = None,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    """调用远端预测服务，对每个目标列输出未来 ``prediction_length`` 步预测。

    自动处理 7 个基础模型的输出张量差异，统一归一化为
    ``point_forecast`` + 9 个分位水平（p10..p90）+ 可选 ``samples``。

    仅预测 ``runtime.context.target_columns`` 中的列。

    Parameters
    ----------
    model : str
        模型名（大小写不敏感）。完整列表见 :func:`list_prediction_models`。
    prediction_length : int, default 8
        预测步数（>0）。
    history_tail : int, optional
        仅取最近 ``history_tail`` 步历史送入模型，避免超长输入。
        未提供时使用全部历史。
    impute : {"ffill","bfill","median","zero","drop"}, default "ffill"
        NaN 填充策略。时序默认前向填充。
    endpoint : str, optional
        自定义端点 URL；默认走模型注册表中的 preferred endpoint。
    timeout : int, optional
        单次 HTTP 调用超时秒数（默认 120）。

    Returns
    -------
    Dict[str, Any]
        ``metrics.per_column`` 含每列的 ``point_forecast`` / ``quantiles``
        / ``shape`` / ``n_input``；samples 类模型额外含 ``samples``。
    """
    if prediction_length <= 0:
        raise ValueError(
            "prediction_length 必须 > 0，当前=%r" % prediction_length)

    canonical, entry = resolve_model(model)

    df = get_df(runtime)
    cols = resolve_columns(runtime)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="forecast_time_series",
            summary="无可用数值列。",
            key_findings=["无法执行预测。"],
            metrics={
                "model": canonical,
                "skipped": {"non_numeric": non_numeric},
            },
        )

    if history_tail is not None and history_tail < prediction_length:
        logger.warning(
            "history_tail(%d) < prediction_length(%d)，"
            "可能不足以支撑预测。",
            history_tail, prediction_length)

    per_column: Dict[str, Any] = {}
    findings: List[str] = []
    errors: List[str] = []
    common_info: Dict[str, Any] = {}
    # Per-column chart history (downsampled 1-D array). One entry per
    # column since this tool runs a single model on every column.
    chart_history: Dict[str, Any] = {}

    for col in numeric_cols:
        arr, info = prepare_series(df, col, impute=impute, history_tail=history_tail)
        common_info = info
        # Capture history BEFORE the API call so we always ship it,
        # even when the call later fails. This keeps the chart payload
        # lossless on partial-failure turns.
        hist_list, hist_n, hist_ds = _downsample_history(arr)
        chart_history[col] = {
            "history": hist_list,
            "n_full": hist_n,
            "downsampled": hist_ds,
        }
        if arr.size < 2:
            per_column[col] = {
                "n_input": int(arr.size),
                "note": "样本不足（需 >= 2）",
            }
            continue

        try:
            body = call_predict_api(
                model=canonical,
                data_list=arr.tolist(),
                prediction_length=prediction_length,
                endpoint=endpoint,
                timeout=timeout,
            )
        except Exception as exc:
            logger.exception(
                "forecast_time_series: API 调用失败 col=%s model=%s",
                col, canonical)
            err = "%s: %s" % (type(exc).__name__, exc)
            per_column[col] = {"error": err, "n_input": int(arr.size)}
            errors.append("%s: %s" % (col, err))
            continue

        if body.get("code") != "success":
            msg = body.get("message", body)
            per_column[col] = {
                "error": "API 返回非成功: %s" % msg,
                "n_input": int(arr.size),
            }
            errors.append("%s: API code=%s" % (col, body.get("code")))
            continue

        raw = body.get("predict_data_result")
        if raw is None:
            per_column[col] = {
                "error": "predict_data_result 为空",
                "n_input": int(arr.size),
            }
            errors.append("%s: predict_data_result 为空" % col)
            continue

        try:
            norm = normalize_forecast(raw, canonical, prediction_length)
        except Exception as exc:
            logger.exception(
                "forecast_time_series: 归一化失败 col=%s model=%s",
                col, canonical)
            per_column[col] = {
                "error": "归一化失败: %s: %s" % (type(exc).__name__, exc),
                "n_input": int(arr.size),
                "raw_shape": str(np.asarray(raw).shape),
            }
            continue

        norm["n_input"] = int(arr.size)
        norm["input_first"] = round_float(float(arr[0]))
        norm["input_last"] = round_float(float(arr[-1]))
        per_column[col] = norm

        point = norm["point_forecast"]
        findings.append(
            "%s：未来 %d 步中位数预测首末 = %+.4g → %+.4g。"
            % (col, prediction_length, point[0], point[-1]))

    notes_extra: List[str] = []
    if non_numeric:
        notes_extra.append("非数值列已跳过：%s" % ", ".join(non_numeric))
    if errors:
        notes_extra.append(
            "共 %d 列预测失败：%s"
            % (len(errors), "; ".join(errors[:5])))
    if common_info.get("history_tail"):
        notes_extra.append(
            "已截取最近 %d 步历史送入模型。" % common_info["history_tail"])

    return make_envelope(
        tool_name="forecast_time_series",
        summary="完成 %d/%d 列的预测（模型=%s，horizon=%d）。"
                % (len([c for c in per_column.values() if "error" not in c]),
                   len(numeric_cols), canonical, prediction_length),
        key_findings=findings or ["无成功预测结果。"],
        metrics={
            "model": canonical,
            "endpoint": entry["preferred_endpoint"],
            "prediction_length": int(prediction_length),
            "history_tail": history_tail,
            "impute": impute,
            "per_column": per_column,
            "chart_history": chart_history,
        },
        recommendations=[
            "需要历史回测时改用 backtest_forecast；多模型对比时改用 "
            "forecast_multi_models。",
            "samples 类模型（如 sundial）的样本路径默认截断为 100 条，"
            "分位带始终基于完整样本计算。",
        ],
        notes=format_notes(
            {"skipped_non_numeric": non_numeric,
             "n_nan": common_info.get("n_nan", 0),
             "impute": impute},
            notes_extra),
    )


# ----------------------------------------------------------------------
# Multi-model side-by-side forecast
# ----------------------------------------------------------------------

@tool("forecast_multi_models")
@tool_guard("forecast_multi_models")
def forecast_multi_models(
    models: List[str],
    runtime: ToolRuntime,
    prediction_length: int = 8,
    history_tail: Optional[int] = None,
    impute: str = "ffill",
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    """在相同序列上并行调用多个模型，输出并排预测结果。

    与 :func:`compare_forecast_models_backtest` 的区别：本工具**不做
    历史回测**，只输出每个模型对未来的预测，便于"多模型交叉确认
    未来走势"。如果需要精度对比，请使用回测工具。

    仅预测 ``runtime.context.target_columns`` 中的列。

    Parameters
    ----------
    models : List[str]
        至少 2 个模型名（大小写不敏感）。
    prediction_length : int, default 8
        预测步数。
    history_tail / impute / timeout : 同 ``forecast_time_series``。
    """
    if not models or len(models) < 2:
        return make_envelope(
            tool_name="forecast_multi_models",
            summary="models 至少需要 2 个，已跳过。",
            key_findings=["未执行多模型预测。"],
            metrics={"models": list(models or [])},
            notes=["如只需单个模型，请改用 forecast_time_series。"],
        )
    if prediction_length <= 0:
        raise ValueError(
            "prediction_length 必须 > 0，当前=%r" % prediction_length)

    canonical_models: List[str] = []
    for m in models:
        canonical, _ = resolve_model(m)
        if canonical not in canonical_models:
            canonical_models.append(canonical)

    df = get_df(runtime)
    cols = resolve_columns(runtime)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="forecast_multi_models",
            summary="无可用数值列。",
            key_findings=["无法执行多模型预测。"],
            metrics={"models": canonical_models,
                     "skipped": {"non_numeric": non_numeric}},
        )

    # results[model][column] = normalized_forecast | {error}
    results: Dict[str, Dict[str, Any]] = {m: {} for m in canonical_models}
    findings: List[str] = []
    errors: List[str] = []
    # All models share the same per-column history (they all see the
    # same input series), so we capture it ONCE per column rather than
    # duplicating across models.
    chart_history: Dict[str, Any] = {}

    for col in numeric_cols:
        arr, _ = prepare_series(df, col, impute=impute, history_tail=history_tail)
        hist_list, hist_n, hist_ds = _downsample_history(arr)
        chart_history[col] = {
            "history": hist_list,
            "n_full": hist_n,
            "downsampled": hist_ds,
        }
        if arr.size < 2:
            for m in canonical_models:
                results[m][col] = {"note": "样本不足"}
            continue

        for m in canonical_models:
            entry = MODEL_REGISTRY[m]
            try:
                body = call_predict_api(
                    model=m,
                    data_list=arr.tolist(),
                    prediction_length=prediction_length,
                    timeout=timeout,
                )
            except Exception as exc:
                logger.exception(
                    "forecast_multi_models: API 失败 model=%s col=%s", m, col)
                err = "%s: %s" % (type(exc).__name__, exc)
                results[m][col] = {"error": err, "n_input": int(arr.size)}
                errors.append("%s/%s: %s" % (m, col, err))
                continue

            if body.get("code") != "success":
                results[m][col] = {
                    "error": "API code=%s msg=%s" % (body.get("code"), body.get("message")),
                    "n_input": int(arr.size),
                }
                errors.append("%s/%s: API code=%s" % (m, col, body.get("code")))
                continue

            raw = body.get("predict_data_result")
            if raw is None:
                results[m][col] = {"error": "predict_data_result 为空"}
                errors.append("%s/%s: empty result" % (m, col))
                continue

            try:
                norm = normalize_forecast(raw, m, prediction_length)
                norm["endpoint"] = entry["preferred_endpoint"]
                results[m][col] = norm
            except Exception as exc:
                results[m][col] = {
                    "error": "归一化失败: %s" % exc,
                    "raw_shape": str(np.asarray(raw).shape),
                }

        # Per-column cross-model median-of-medians summary.
        medians = []
        for m in canonical_models:
            r = results[m].get(col) or {}
            pf = r.get("point_forecast")
            if isinstance(pf, list) and pf:
                medians.append(pf[-1])
        if medians:
            findings.append(
                "%s：各模型末步预测 = %s。"
                % (col,
                   ", ".join("%+.4g" % float(v) for v in medians)))

    notes_extra: List[str] = []
    if non_numeric:
        notes_extra.append("非数值列已跳过：%s" % ", ".join(non_numeric))
    if errors:
        notes_extra.append(
            "共 %d 次 (model, col) 调用失败。" % len(errors))

    return make_envelope(
        tool_name="forecast_multi_models",
        summary="完成 %d 模型 × %d 列的并排预测（horizon=%d）。"
                % (len(canonical_models), len(numeric_cols), prediction_length),
        key_findings=findings or ["无成功预测结果。"],
        metrics={
            "models": canonical_models,
            "prediction_length": int(prediction_length),
            "history_tail": history_tail,
            "per_model": results,
            "chart_history": chart_history,
        },
        recommendations=[
            "如需评估哪个模型更准，改用 compare_forecast_models_backtest。",
            "若多模型结果一致，可调用 forecast_ensemble 合成单一预测。",
        ],
        notes=format_notes(
            {"skipped_non_numeric": non_numeric, "impute": impute},
            notes_extra),
    )


# ----------------------------------------------------------------------
# Ensemble of model forecasts
# ----------------------------------------------------------------------

@tool("forecast_ensemble")
@tool_guard("forecast_ensemble")
def forecast_ensemble(
    models: List[str],
    runtime: ToolRuntime,
    prediction_length: int = 8,
    history_tail: Optional[int] = None,
    impute: str = "ffill",
    weighting: str = "mean",
    holdout_steps: int = 0,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    """融合多个模型的预测为单一预测。

    仅预测 ``runtime.context.target_columns`` 中的列。

    Parameters
    ----------
    models : List[str]
        至少 2 个模型名。
    prediction_length : int, default 8
        预测步数。
    weighting : {"mean","median"}, default "mean"
        融合策略：

        - ``"mean"`` — 对每个模型的 ``point_forecast`` 取算术平均。
        - ``"median"`` — 取中位数，更抗离群模型。
    holdout_steps : int, default 0
        若 > 0，先用末尾 ``holdout_steps`` 步作为内部 holdout 计算每个
        模型的 MAPE，再做 inverse-MAPE 加权平均（覆盖 ``weighting``）。

    其他参数同 ``forecast_time_series``。
    """
    if not models or len(models) < 2:
        return make_envelope(
            tool_name="forecast_ensemble",
            summary="models 至少需要 2 个，已跳过。",
            key_findings=["未执行融合预测。"],
            metrics={"models": list(models or [])},
        )
    if prediction_length <= 0:
        raise ValueError(
            "prediction_length 必须 > 0，当前=%r" % prediction_length)
    if weighting not in ("mean", "median"):
        weighting = "mean"

    canonical_models: List[str] = []
    for m in models:
        canonical, _ = resolve_model(m)
        if canonical not in canonical_models:
            canonical_models.append(canonical)

    df = get_df(runtime)
    cols = resolve_columns(runtime)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="forecast_ensemble",
            summary="无可用数值列。",
            key_findings=["无法执行融合预测。"],
            metrics={"models": canonical_models,
                     "skipped": {"non_numeric": non_numeric}},
        )

    per_column: Dict[str, Any] = {}
    findings: List[str] = []
    errors: List[str] = []

    for col in numeric_cols:
        arr, _ = prepare_series(df, col, impute=impute, history_tail=history_tail)
        if arr.size < 2 + max(holdout_steps, 0):
            per_column[col] = {"note": "样本不足以做 holdout 与预测。"}
            continue

        # Split for optional holdout-weighting.
        if holdout_steps > 0 and arr.size > holdout_steps:
            train_arr = arr[:-holdout_steps]
            holdout_actual = arr[-holdout_steps:]
        else:
            train_arr = arr
            holdout_actual = None

        per_model_forecast: Dict[str, Any] = {}
        per_model_holdout_mape: Dict[str, Optional[float]] = {}

        for m in canonical_models:
            # 1) Holdout MAPE (if requested).
            if holdout_actual is not None:
                try:
                    hb = call_predict_api(
                        model=m,
                        data_list=train_arr.tolist(),
                        prediction_length=holdout_steps,
                        timeout=timeout,
                    )
                    if hb.get("code") != "success":
                        raise ValueError(
                            "API code=%s msg=%s" % (hb.get("code"), hb.get("message")))
                    hraw = hb.get("predict_data_result")
                    hnorm = normalize_forecast(hraw, m, holdout_steps)
                    hpoint = np.asarray(hnorm["point_forecast"], dtype=float)
                    from agent_app.tools.prediction_tools._common import (
                        forecast_metrics,
                    )
                    m_metrics = forecast_metrics(holdout_actual, hpoint)
                    per_model_holdout_mape[m] = m_metrics.get("mape")
                except Exception as exc:
                    logger.exception(
                        "forecast_ensemble: holdout 失败 model=%s col=%s", m, col)
                    per_model_holdout_mape[m] = None
                    errors.append("%s/%s holdout: %s" % (m, col, exc))

            # 2) Full-length forecast.
            try:
                body = call_predict_api(
                    model=m,
                    data_list=arr.tolist(),
                    prediction_length=prediction_length,
                    timeout=timeout,
                )
                if body.get("code") != "success":
                    raise ValueError(
                        "API code=%s msg=%s" % (body.get("code"), body.get("message")))
                raw = body.get("predict_data_result")
                norm = normalize_forecast(raw, m, prediction_length)
                per_model_forecast[m] = norm
            except Exception as exc:
                logger.exception(
                    "forecast_ensemble: forecast 失败 model=%s col=%s", m, col)
                per_model_forecast[m] = {"error": "%s: %s" % (type(exc).__name__, exc)}
                errors.append("%s/%s forecast: %s" % (m, col, exc))

        # 3) Combine.
        valid = {
            m: np.asarray(f["point_forecast"], dtype=float)
            for m, f in per_model_forecast.items()
            if isinstance(f, dict) and isinstance(f.get("point_forecast"), list)
        }
        # Drop arrays whose length disagrees with the majority. A
        # residual orientation bug in normalize_forecast would otherwise
        # crash np.vstack; we surface the dropped models in notes
        # instead of aborting the whole tool.
        if valid:
            lengths = {m: int(v.size) for m, v in valid.items()}
            # Prefer the requested prediction_length when present; else
            # fall back to the most common length.
            target_len = prediction_length if prediction_length in lengths.values() else \
                max(set(lengths.values()), key=list(lengths.values()).count)
            mismatched = [m for m, n in lengths.items() if n != target_len]
            if mismatched:
                logger.warning(
                    "forecast_ensemble: dropping models %s whose "
                    "point_forecast length != %d (got %s).",
                    mismatched, target_len,
                    {m: lengths[m] for m in mismatched})
                errors.append(
                    "%s: 点预测长度与目标 %d 不一致，已从融合中剔除。"
                    % (",".join(mismatched), target_len))
                for m in mismatched:
                    valid.pop(m, None)
        if not valid:
            per_column[col] = {
                "note": "无可用单模型预测，无法融合。",
                "per_model": per_model_forecast,
            }
            continue

        # All surviving arrays share the same length now.
        stacked = np.vstack(list(valid.values()))  # (n_models, horizon)

        used_weighting = weighting
        if holdout_actual is not None and per_model_holdout_mape:
            mapes = {m: per_model_holdout_mape.get(m) for m in valid.keys()}
            finite = {m: v for m, v in mapes.items()
                      if v is not None and np.isfinite(v) and v > 1e-9}
            if len(finite) >= 2:
                inv = np.array([1.0 / finite[m] for m in valid.keys()])
                weights = inv / inv.sum()
                ensemble = (stacked * weights[:, None]).sum(axis=0)
                used_weighting = "inverse_mape"
            else:
                if weighting == "median":
                    ensemble = np.median(stacked, axis=0)
                else:
                    ensemble = stacked.mean(axis=0)
        else:
            if weighting == "median":
                ensemble = np.median(stacked, axis=0)
            else:
                ensemble = stacked.mean(axis=0)

        per_column[col] = {
            "point_forecast": ensemble.tolist(),
            "n_models_used": int(len(valid)),
            "used_weighting": used_weighting,
            "per_model": per_model_forecast,
            "per_model_holdout_mape": per_model_holdout_mape,
        }
        findings.append(
            "%s：融合预测（%s，%d 模型）首末 = %+.4g → %+.4g。"
            % (col, used_weighting, len(valid),
               float(ensemble[0]), float(ensemble[-1])))

    notes_extra: List[str] = []
    if non_numeric:
        notes_extra.append("非数值列已跳过：%s" % ", ".join(non_numeric))
    if errors:
        notes_extra.append("共 %d 次内部调用失败。" % len(errors))

    return make_envelope(
        tool_name="forecast_ensemble",
        summary="完成 %d 列的多模型融合预测（%d 模型，horizon=%d）。"
                % (len(per_column), len(canonical_models), prediction_length),
        key_findings=findings or ["无成功融合结果。"],
        metrics={
            "models": canonical_models,
            "prediction_length": int(prediction_length),
            "weighting": weighting,
            "holdout_steps": int(holdout_steps),
            "per_column": per_column,
        },
        recommendations=[
            "如需对比融合前后的精度，先在 holdout 上比较 per_model_holdout_mape。",
            "样本路径模型（sundial）在融合时仅贡献 point_forecast，丢失密度信息。",
        ],
        notes=format_notes(
            {"skipped_non_numeric": non_numeric, "impute": impute},
            notes_extra),
    )


TOOLS = [
    forecast_time_series,
    forecast_multi_models,
    forecast_ensemble,
]
