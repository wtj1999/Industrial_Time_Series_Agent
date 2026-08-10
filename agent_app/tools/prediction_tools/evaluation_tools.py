"""Evaluation / backtest tools for the prediction tool family.

Two tools that put the forecasting service to a quantitative test:

- :func:`backtest_forecast` — single-model holdout backtest. Trains on
  ``series[:-test_steps]`` and scores the forecast against the held-out
  tail with MAE / RMSE / MAPE / sMAPE / MASE.
- :func:`compare_forecast_models_backtest` — runs the same backtest for
  every requested model on the same series and ranks them by a chosen
  metric (default MAE). The right tool to answer "which model fits my
  data best".

Both tools are network-bound (one HTTP call per model per column on the
*training* slice) and therefore can be slow when given many models or
columns; the prompt steers the LLM to default to a single model unless
the user explicitly asks for a comparison.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from langchain.tools import ToolRuntime, tool

from agent_app.tools._tool_guard import tool_guard
from agent_app.tools.prediction_tools._common import (
    MODEL_REGISTRY,
    call_predict_api,
    downsample_history,
    forecast_metrics,
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


# Metrics the LLM can ask the compare tool to rank by.
_SUPPORTED_RANK_BY = {"mae", "rmse", "mape", "smape", "mase"}


def _backtest_single(
    model: str,
    train: np.ndarray,
    test: np.ndarray,
    timeout: Optional[int],
) -> Dict[str, Any]:
    """Run one (train -> forecast -> score) cycle.

    Returns a dict with ``forecast`` (normalized), ``actual`` and the
    metrics dict, or ``error`` on failure.
    """
    test_steps = int(test.size)
    try:
        body = call_predict_api(
            model=model,
            data_list=train.tolist(),
            prediction_length=test_steps,
            timeout=timeout,
        )
    except Exception as exc:
        return {"error": "API: %s: %s" % (type(exc).__name__, exc)}

    if body.get("code") != "success":
        return {"error": "API code=%s msg=%s"
                % (body.get("code"), body.get("message"))}

    raw = body.get("predict_data_result")
    if raw is None:
        return {"error": "predict_data_result 为空"}

    try:
        norm = normalize_forecast(raw, model, test_steps)
    except Exception as exc:
        return {"error": "归一化失败: %s: %s" % (type(exc).__name__, exc)}

    point = np.asarray(norm["point_forecast"], dtype=float)
    metrics = forecast_metrics(test, point)
    return {
        "forecast": norm,
        "actual": test.tolist(),
        "metrics": metrics,
    }


# ----------------------------------------------------------------------
# Tools
# ----------------------------------------------------------------------

@tool("backtest_forecast")
@tool_guard("backtest_forecast")
def backtest_forecast(
    model: str,
    runtime: ToolRuntime,
    test_steps: int = 8,
    impute: str = "ffill",
    history_tail: Optional[int] = None,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    """对单个模型在历史数据末尾做 holdout 回测。

    流程：把每列切成 ``train = series[:-test_steps]`` 与
    ``test = series[-test_steps:]``，调用 API 用 train 预测 test_steps
    步，再与 test 对比计算 MAE/RMSE/MAPE/sMAPE/MASE。

    仅对 ``runtime.context.target_columns`` 中的列做回测。

    Parameters
    ----------
    model : str
        模型名（大小写不敏感）。
    test_steps : int, default 8
        保留多少步作为 holdout（必须 >= 2 且 < 序列长度的 50%）。
    impute / history_tail / timeout : 同 ``forecast_time_series``。
    """
    if test_steps < 2:
        raise ValueError("test_steps 必须 >= 2，当前=%r" % test_steps)

    canonical, entry = resolve_model(model)

    df = get_df(runtime)
    cols = resolve_columns(runtime)
    numeric_cols, non_numeric, _ = select_numeric_columns(df, cols)
    if not numeric_cols:
        return make_envelope(
            tool_name="backtest_forecast",
            summary="无可用数值列。",
            key_findings=["无法执行回测。"],
            metrics={"model": canonical,
                     "skipped": {"non_numeric": non_numeric}},
        )

    per_column: Dict[str, Any] = {}
    findings: List[str] = []
    errors: List[str] = []
    # Per-column downsampled train tail — the "history" portion of the
    # backtest chart. Captured for every column even when the API call
    # later fails so the chart can still render the partial result.
    chart_history: Dict[str, Any] = {}

    for col in numeric_cols:
        full, _ = prepare_series(df, col, impute=impute)
        if full.size < 2 * test_steps:
            per_column[col] = {
                "note": "样本不足（需 >= 2*test_steps=%d，实际 %d）"
                        % (2 * test_steps, full.size),
            }
            continue

        train_full = full[:-test_steps]
        test = full[-test_steps:]

        if history_tail is not None and train_full.size > history_tail:
            train_input = train_full[-history_tail:]
        else:
            train_input = train_full

        # Downsample the actual train slice we fed the model — this is
        # what the chart renders as the "history" line. Preserves the
        # final sample so the history→forecast junction stays exact.
        hist_list, hist_n, hist_ds = downsample_history(train_input)
        chart_history[col] = {
            "history": hist_list,
            "n_full": hist_n,
            "downsampled": hist_ds,
        }

        result = _backtest_single(canonical, train_input, test, timeout)
        if "error" in result:
            per_column[col] = {"error": result["error"],
                               "n_train": int(train_input.size),
                               "n_test": int(test.size)}
            errors.append("%s: %s" % (col, result["error"]))
            continue

        # Attach train tail for context.
        forecast_payload = result["forecast"]
        forecast_payload["n_train"] = int(train_input.size)
        forecast_payload["train_last"] = round_float(float(train_input[-1]))
        forecast_payload["actual"] = result["actual"]
        forecast_payload["metrics"] = result["metrics"]
        per_column[col] = forecast_payload

        m = result["metrics"]
        findings.append(
            "%s：MAE=%.4g，RMSE=%.4g，MAPE=%s，sMAPE=%s。"
            % (col,
               m.get("mae", float("nan")),
               m.get("rmse", float("nan")),
               "%.2f%%" % m["mape"] if m.get("mape") is not None else "N/A",
               "%.2f%%" % m["smape"] if m.get("smape") is not None else "N/A"))

    notes_extra: List[str] = []
    if non_numeric:
        notes_extra.append("非数值列已跳过：%s" % ", ".join(non_numeric))
    if errors:
        notes_extra.append("共 %d 列回测失败。" % len(errors))

    # Aggregate metrics across columns (mean of per-column metrics).
    valid_metrics = [v["metrics"] for v in per_column.values()
                     if isinstance(v, dict) and v.get("metrics")]
    overall: Dict[str, Any] = {}
    if valid_metrics:
        for key in ("mae", "rmse", "mape", "smape"):
            vals = [m[key] for m in valid_metrics
                    if m.get(key) is not None and np.isfinite(m[key])]
            if vals:
                overall[key] = round_float(float(np.mean(vals)))
        mase_vals = [m["mase"] for m in valid_metrics
                     if m.get("mase") is not None and np.isfinite(m["mase"])]
        if mase_vals:
            overall["mase"] = round_float(float(np.mean(mase_vals)))
        overall["n_columns"] = len(valid_metrics)

    return make_envelope(
        tool_name="backtest_forecast",
        summary="完成 %s 的 holdout 回测（test_steps=%d，%d 列成功）。"
                % (canonical, test_steps,
                   len(valid_metrics)),
        key_findings=findings or ["无成功回测结果。"],
        metrics={
            "model": canonical,
            "endpoint": entry["preferred_endpoint"],
            "test_steps": int(test_steps),
            "history_tail": history_tail,
            "per_column": per_column,
            "overall": overall,
            "chart_history": chart_history,
        },
        recommendations=[
            "如需多模型精度对比，改用 compare_forecast_models_backtest。",
            "MAPE/sMAPE 在序列接近 0 时不可靠，请参考 MAE/RMSE/MASE。",
        ],
        notes=format_notes(
            {"skipped_non_numeric": non_numeric, "impute": impute},
            notes_extra),
    )


@tool("compare_forecast_models_backtest")
@tool_guard("compare_forecast_models_backtest")
def compare_forecast_models_backtest(
    models: List[str],
    runtime: ToolRuntime,
    test_steps: int = 8,
    impute: str = "ffill",
    history_tail: Optional[int] = None,
    rank_by: str = "mae",
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    """在相同 holdout 上对比多个模型的精度并按指标排名。

    仅对 ``runtime.context.target_columns`` 中的列做对比。

    Parameters
    ----------
    models : List[str]
        至少 2 个模型名（大小写不敏感）。
    test_steps : int, default 8
        holdout 步数（>= 2）。
    rank_by : {"mae","rmse","mape","smape","mase"}, default "mae"
        用于排名的指标（越小越好）。
    其他参数同 ``backtest_forecast``。
    """
    if not models or len(models) < 2:
        return make_envelope(
            tool_name="compare_forecast_models_backtest",
            summary="models 至少需要 2 个。",
            key_findings=["未执行对比。"],
            metrics={"models": list(models or [])},
            notes=["单模型场景请用 backtest_forecast。"],
        )
    if test_steps < 2:
        raise ValueError("test_steps 必须 >= 2，当前=%r" % test_steps)
    if rank_by not in _SUPPORTED_RANK_BY:
        raise ValueError(
            "rank_by 必须是 %s，当前=%r"
            % (sorted(_SUPPORTED_RANK_BY), rank_by))

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
            tool_name="compare_forecast_models_backtest",
            summary="无可用数值列。",
            key_findings=["无法执行对比。"],
            metrics={"models": canonical_models,
                     "skipped": {"non_numeric": non_numeric}},
        )

    # results[model][column] = {forecast, metrics, ...} | {error}
    results: Dict[str, Dict[str, Any]] = {m: {} for m in canonical_models}
    findings: List[str] = []
    errors: List[str] = []
    # All models share the same per-column train history (they all see
    # the same input series), so capture it ONCE per column.
    chart_history: Dict[str, Any] = {}

    for col in numeric_cols:
        full, _ = prepare_series(df, col, impute=impute)
        if full.size < 2 * test_steps:
            for m in canonical_models:
                results[m][col] = {"note": "样本不足"}
            continue

        train_full = full[:-test_steps]
        test = full[-test_steps:]
        if history_tail is not None and train_full.size > history_tail:
            train_input = train_full[-history_tail:]
        else:
            train_input = train_full

        # Downsample the train slice once per column — every model saw
        # the same input so the chart's history line is shared.
        hist_list, hist_n, hist_ds = downsample_history(train_input)
        chart_history[col] = {
            "history": hist_list,
            "n_full": hist_n,
            "downsampled": hist_ds,
        }

        for m in canonical_models:
            r = _backtest_single(m, train_input, test, timeout)
            if "error" in r:
                results[m][col] = {"error": r["error"]}
                errors.append("%s/%s: %s" % (m, col, r["error"]))
                continue
            results[m][col] = {
                "metrics": r["metrics"],
                "point_forecast": r["forecast"]["point_forecast"],
                "actual": r["actual"],
                "n_train": int(train_input.size),
            }

    # Aggregate per model: mean of rank_by across successful columns.
    summary_rows: List[Dict[str, Any]] = []
    for m in canonical_models:
        metric_vals: Dict[str, List[float]] = {k: [] for k in _SUPPORTED_RANK_BY}
        n_cols_ok = 0
        for col, r in results[m].items():
            mtr = r.get("metrics") if isinstance(r, dict) else None
            if not mtr:
                continue
            n_cols_ok += 1
            for k in _SUPPORTED_RANK_BY:
                v = mtr.get(k)
                if v is not None and np.isfinite(v):
                    metric_vals[k].append(v)
        agg = {
            k: round_float(float(np.mean(vs))) if vs else None
            for k, vs in metric_vals.items()
        }
        agg["model"] = m
        agg["n_columns_ok"] = n_cols_ok
        summary_rows.append(agg)

    # Sort by rank_by ascending (smaller is better). Models with None
    # rank to the end.
    def _rank_key(row: Dict[str, Any]):
        v = row.get(rank_by)
        if v is None or not np.isfinite(v):
            return (1, float("inf"))
        return (0, float(v))

    summary_rows.sort(key=_rank_key)

    if summary_rows and summary_rows[0].get(rank_by) is not None:
        winner = summary_rows[0]
        findings.append(
            "按 %s 排名，最优模型 = %s（值 = %s）。"
            % (rank_by, winner["model"], winner[rank_by]))
        if len(summary_rows) > 1:
            second = summary_rows[1]
            findings.append(
                "次优 = %s（%s = %s）。"
                % (second["model"], rank_by, second.get(rank_by)))

    notes_extra: List[str] = []
    if non_numeric:
        notes_extra.append("非数值列已跳过：%s" % ", ".join(non_numeric))
    if errors:
        notes_extra.append("共 %d 次 (model, col) 调用失败。" % len(errors))

    return make_envelope(
        tool_name="compare_forecast_models_backtest",
        summary="完成 %d 模型 × %d 列的 holdout 对比（按 %s 排名）。"
                % (len(canonical_models), len(numeric_cols), rank_by),
        key_findings=findings or ["无有效对比结果。"],
        metrics={
            "models": canonical_models,
            "test_steps": int(test_steps),
            "rank_by": rank_by,
            "summary": summary_rows,
            "per_model": results,
            "chart_history": chart_history,
        },
        recommendations=[
            "winner 即为当前数据上的推荐模型；可调用 "
            "forecast_time_series(model=winner) 预测未来。",
            "MAPE/sMAPE 在序列接近 0 时不可靠；建议同时参考 MASE。",
        ],
        notes=format_notes(
            {"skipped_non_numeric": non_numeric, "impute": impute},
            notes_extra),
    )


TOOLS = [
    backtest_forecast,
    compare_forecast_models_backtest,
]
