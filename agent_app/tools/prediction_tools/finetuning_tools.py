"""Remote Chronos-2 / TimesFM 2.5 fine-tuning with SSE progress."""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

import numpy as np

from langchain.tools import ToolRuntime, tool

from agent_app.tools._tool_guard import tool_guard
from agent_app.tools.prediction_tools._common import (
    call_predict_api,
    downsample_history,
    forecast_metrics,
    get_df,
    normalize_forecast,
    prepare_series,
    round_float,
    resolve_columns,
    select_numeric_columns,
)

logger = logging.getLogger(__name__)

FINETUNING_ENDPOINT = os.getenv(
    "PREDICTION_FINETUNING_ENDPOINT",
    "http://10.2.128.43:19155/time/seriesFinetune/stream",
)
REMOTE_FINETUNED_ROOT = os.getenv(
    "PREDICTION_FINETUNED_ROOT", "/data/huggingface/finetuned"
).rstrip("/")
PREDICTION_MODEL_INDEX_ROOT = Path(
    os.getenv(
        "PREDICTION_MODEL_INDEX_ROOT",
        str(Path(__file__).resolve().parents[2] / "artifacts" / "prediction_models"),
    )
)
BASE_MODEL_PATHS = {
    "chronos-2": "/data/huggingface/chronos-2",
    "timesfm-2.5": "/data/huggingface/timesfm-2.5-200m-transformers",
}


def _safe_segment(value: Any, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "")).strip("._")
    return cleaned[:100] or fallback


def _iter_sse_events(chunks: Iterable[bytes]) -> Iterator[Tuple[str, Dict[str, Any]]]:
    """Parse POST-SSE frames across arbitrary HTTP chunk boundaries."""
    decoder_buffer = ""
    for chunk in chunks:
        decoder_buffer += chunk.decode("utf-8", errors="replace").replace("\r\n", "\n")
        while "\n\n" in decoder_buffer:
            frame, decoder_buffer = decoder_buffer.split("\n\n", 1)
            if not frame.strip() or frame.lstrip().startswith(":"):
                continue
            event = "message"
            data_parts = []
            for line in frame.split("\n"):
                if line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:"):
                    data_parts.append(line[5:].strip())
            if not data_parts:
                continue
            payload = json.loads("".join(data_parts))
            if isinstance(payload, dict):
                yield event, payload


def _prediction_payload(
    model: str,
    data_list: Iterable[float],
    prediction_length: int,
    model_path: Optional[str],
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "dataList": [[float(x) for x in data_list]],
        "predictionLength": int(prediction_length),
    }
    if model_path:
        payload["modelPath"] = model_path
    return payload


def _progress_emitter(model: str, writer=None):
    operation_id = uuid.uuid4().hex

    def emit(stage: str, **data: Any) -> None:
        if writer is None:
            return
        try:
            writer({
                "event": "prediction_finetuning_progress",
                "operation_id": operation_id,
                "model_name": model,
                "stage": stage,
                **data,
            })
        except Exception:
            logger.debug("Unable to emit fine-tuning progress", exc_info=True)

    return emit


def _save_index(ctx: Any, record: Dict[str, Any]) -> Path:
    user = _safe_segment(getattr(ctx, "user_id", None), "anonymous")
    thread = _safe_segment(getattr(ctx, "thread_id", None), "default")
    directory = PREDICTION_MODEL_INDEX_ROOT / user / thread
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (record["file_name"])
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def resolve_prediction_model_index(
    user_id: Optional[str], thread_id: Optional[str], save_name: str
) -> Dict[str, Any]:
    """Resolve a selected model from the current user's local index.

    The browser-supplied remote path is deliberately ignored: only a JSON
    record below ``prediction_models/<current-user>`` may authorize a path.
    """
    user_root = PREDICTION_MODEL_INDEX_ROOT / _safe_segment(user_id, "anonymous")
    search_root = user_root / _safe_segment(thread_id, "default") if thread_id else user_root
    matches = []
    if search_root.exists():
        for path in search_root.glob("**/*.json"):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                continue
            if record.get("save_name") == save_name and record.get("model_path"):
                matches.append(record)
    if not matches:
        raise ValueError("当前用户下未找到所选预测微调模型索引")
    matches.sort(key=lambda item: item.get("trained_at") or "", reverse=True)
    return matches[0]


def _holdout_model_result(
    model: str,
    train_data: List[List[float]],
    actual_data: List[List[float]],
    columns: List[str],
    holdout_steps: int,
    timeout: int,
    model_path: Optional[str],
) -> Dict[str, Dict[str, Any]]:
    """Run one batched holdout forecast and score every variate."""
    try:
        body = call_predict_api(
            model=model,
            data_list=train_data,
            prediction_length=holdout_steps,
            timeout=timeout,
            model_path=model_path,
        )
    except Exception as exc:
        error = "API: %s: %s" % (type(exc).__name__, exc)
        return {column: {"error": error} for column in columns}

    if body.get("code") != "success":
        error = "API code=%s msg=%s" % (body.get("code"), body.get("message"))
        return {column: {"error": error} for column in columns}
    raw = body.get("predict_data_result")
    raw_array = np.asarray(raw) if raw is not None else np.asarray([])
    if raw_array.ndim != 3 or raw_array.shape[0] != len(columns):
        error = "批量响应变量数不匹配，shape=%s" % (raw_array.shape,)
        return {column: {"error": error} for column in columns}

    results: Dict[str, Dict[str, Any]] = {}
    for index, column in enumerate(columns):
        try:
            norm = normalize_forecast(
                raw_array[index:index + 1], model, holdout_steps
            )
            point = np.asarray(norm["point_forecast"], dtype=float)
            actual = np.asarray(actual_data[index], dtype=float)
            results[column] = {
                "point_forecast": norm["point_forecast"],
                "quantiles": norm.get("quantiles"),
                "actual": actual.tolist(),
                "metrics": forecast_metrics(actual, point),
                "n_train": len(train_data[index]),
            }
        except Exception as exc:
            results[column] = {
                "error": "归一化/指标计算失败 %s: %s"
                % (type(exc).__name__, exc)
            }
    return results


def _aggregate_holdout_metrics(
    model_name: str, per_column: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    row: Dict[str, Any] = {"model": model_name, "n_columns_ok": 0}
    valid = [
        entry["metrics"] for entry in per_column.values()
        if isinstance(entry, dict) and entry.get("metrics")
    ]
    row["n_columns_ok"] = len(valid)
    for key in ("mae", "rmse", "mape", "smape", "mase"):
        values = [
            metrics[key] for metrics in valid
            if metrics.get(key) is not None and np.isfinite(metrics[key])
        ]
        row[key] = round_float(float(np.mean(values))) if values else None
    return row


def _evaluate_finetuned_holdout(
    model: str,
    train_data: List[List[float]],
    actual_data: List[List[float]],
    columns: List[str],
    holdout_steps: int,
    model_path: str,
    timeout: int,
) -> Dict[str, Any]:
    """Compare base and fine-tuned weights on one shared holdout."""
    base_label = "%s (base)" % model
    tuned_label = "%s (finetuned)" % model
    base = _holdout_model_result(
        model, train_data, actual_data, columns, holdout_steps, timeout, None
    )
    tuned = _holdout_model_result(
        model, train_data, actual_data, columns, holdout_steps, timeout, model_path
    )
    summary = [
        _aggregate_holdout_metrics(base_label, base),
        _aggregate_holdout_metrics(tuned_label, tuned),
    ]
    summary.sort(
        key=lambda row: (
            row.get("mae") is None,
            row.get("mae") if row.get("mae") is not None else float("inf"),
        )
    )
    chart_history = {}
    for column, train in zip(columns, train_data):
        history, n_full, downsampled = downsample_history(np.asarray(train))
        chart_history[column] = {
            "history": history,
            "n_full": n_full,
            "downsampled": downsampled,
        }
    return {
        "models": [base_label, tuned_label],
        "test_steps": holdout_steps,
        "rank_by": "mae",
        "summary": summary,
        "per_model": {base_label: base, tuned_label: tuned},
        "chart_history": chart_history,
    }


@tool("finetune_prediction_model")
@tool_guard("finetune_prediction_model")
def finetune_prediction_model(
    model: str,
    runtime: ToolRuntime,
    save_name: str,
    prediction_length: int,
    holdout_steps: Optional[int] = None,
    context_length: Optional[int] = None,
    num_steps: int = 1000,
    learning_rate: float = 1e-5,
    batch_size: int = 32,
    finetune_mode: str = "lora",
    logging_steps: int = 100,
    device: Optional[str] = None,
    output_dir: Optional[str] = None,
    base_model_path: Optional[str] = None,
    lora_r: int = 4,
    lora_alpha: int = 8,
    lora_dropout: float = 0.05,
    timeout: int = 7200,
) -> Dict[str, Any]:
    """在远程服务微调 Chronos-2 或 TimesFM 2.5，并实时转发训练进度。

    权重保存在远程 ``output_dir``；本地仅保存包含最终 ``modelPath`` 的
    JSON 索引，供“我的模型”和预测模型选择器使用。
    """
    canonical = str(model).lower()
    if canonical not in BASE_MODEL_PATHS:
        raise ValueError("model 只支持 chronos-2 或 timesfm-2.5")
    if prediction_length <= 0 or num_steps <= 0 or batch_size <= 0:
        raise ValueError("prediction_length、num_steps、batch_size 必须 > 0")
    mode = str(finetune_mode).lower()
    if mode not in {"full", "lora"}:
        raise ValueError("finetune_mode 只支持 full 或 lora")
    if canonical == "timesfm-2.5" and mode != "lora":
        raise ValueError("timesfm-2.5 只支持 lora 微调")

    ctx = runtime.context
    df = get_df(runtime)
    numeric, non_numeric, _ = select_numeric_columns(df, resolve_columns(runtime))
    if not numeric:
        raise ValueError("目标列中没有可用于微调的数值序列")
    full_data_list: List[List[float]] = []
    for column in numeric:
        values, _ = prepare_series(df, column, impute="ffill")
        full_data_list.append(values.astype(float).tolist())
    effective_holdout = int(holdout_steps or prediction_length)
    if effective_holdout < 2:
        raise ValueError("holdout_steps 必须 >= 2")
    if any(len(series) <= effective_holdout for series in full_data_list):
        raise ValueError("每条序列长度必须大于 holdout_steps")
    # Reserve the tail before fine-tuning to prevent holdout leakage.
    data_list = [series[:-effective_holdout] for series in full_data_list]
    holdout_data = [series[-effective_holdout:] for series in full_data_list]
    if canonical == "timesfm-2.5":
        effective_context = int(context_length or 64)
        minimum = effective_context + prediction_length
        if any(len(series) < minimum for series in data_list):
            raise ValueError(
                "扣除 holdout 后，每条训练序列必须至少达到 "
                "contextLength + predictionLength"
            )
    else:
        effective_context = context_length

    safe_name = _safe_segment(save_name, canonical + "-finetuned")
    user = _safe_segment(getattr(ctx, "user_id", None), "anonymous")
    thread = _safe_segment(getattr(ctx, "thread_id", None), "default")
    remote_output = output_dir or (
        f"{REMOTE_FINETUNED_ROOT}/{user}/{thread}/{safe_name}_{uuid.uuid4().hex[:8]}"
    )
    payload: Dict[str, Any] = {
        "model": canonical,
        "dataList": data_list,
        "outputDir": remote_output,
        "baseModelPath": base_model_path or BASE_MODEL_PATHS[canonical],
        "predictionLength": int(prediction_length),
        "numSteps": int(num_steps),
        "learningRate": float(learning_rate),
        "batchSize": int(batch_size),
        "finetuneMode": mode,
        "loggingSteps": int(logging_steps),
    }
    if effective_context is not None:
        payload["contextLength"] = int(effective_context)
    if device:
        payload["device"] = device
    else:
        payload["device"] = "cuda:0"
    if canonical == "timesfm-2.5":
        payload.update({
            "loraR": int(lora_r),
            "loraAlpha": int(lora_alpha),
            "loraDropout": float(lora_dropout),
        })

    emit = _progress_emitter(canonical, getattr(ctx, "stream_writer", None))
    emit("preparing", percent=0.0, message="正在提交远程微调任务")
    import requests
    with requests.post(
        FINETUNING_ENDPOINT,
        json=payload,
        headers={"Accept": "text/event-stream"},
        stream=True,
        timeout=(30, int(timeout)),
    ) as response:
        response.raise_for_status()
        completed = None
        for event, data in _iter_sse_events(response.iter_content(chunk_size=1024)):
            if event == "status":
                emit("training", percent=0.0, message=data.get("message", "Training started"))
            elif event == "progress":
                metrics = {
                    key: float(data[key])
                    for key in ("loss", "grad_norm", "learning_rate", "epoch")
                    if data.get(key) is not None
                }
                emit(
                    "training",
                    current=data.get("step"),
                    total=data.get("totalSteps"),
                    percent=data.get("progress"),
                    message="远程模型微调中",
                    metrics=metrics,
                )
            elif event == "failed":
                emit("failed", message=data.get("message", "远程微调失败"))
                raise RuntimeError(data.get("message", "远程微调失败"))
            elif event == "completed":
                completed = data

    if not completed or not completed.get("modelPath"):
        raise RuntimeError("微调流已结束，但未收到包含 modelPath 的 completed 事件")

    now = datetime.now(timezone.utc).isoformat()
    file_name = f"{safe_name}_{uuid.uuid4().hex[:8]}.json"
    record = {
        "category": "time_series_prediction",
        "task_type": "prediction",
        "model_type": canonical,
        "save_name": safe_name,
        "file_name": file_name,
        "model_path": completed["modelPath"],
        "output_dir": completed.get("outputDir", remote_output),
        "base_model_path": completed.get("baseModelPath", payload["baseModelPath"]),
        "trained_at": now,
        "saved_at": now,
        "thread_id": getattr(ctx, "thread_id", None),
        "source_file": Path(str(getattr(ctx, "file_path", "dataset"))).stem,
        "feature_columns": numeric,
        "n_features": len(numeric),
        "n_samples": min(len(series) for series in data_list),
        "size_bytes": 0,
        "training": {
            "prediction_length": prediction_length,
            "context_length": effective_context,
            "num_steps": num_steps,
            "finetune_mode": mode,
            "holdout_steps": effective_holdout,
        },
    }
    index_path = _save_index(ctx, record)
    record["size_bytes"] = index_path.stat().st_size
    index_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    emit("evaluating", percent=95.0, message="正在进行基础模型与微调模型 holdout 对比")
    evaluation = _evaluate_finetuned_holdout(
        canonical,
        data_list,
        holdout_data,
        numeric,
        effective_holdout,
        record["model_path"],
        timeout,
    )
    record["evaluation"] = {
        "test_steps": effective_holdout,
        "rank_by": "mae",
        "summary": evaluation["summary"],
    }
    index_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    emit("completed", percent=100.0, message="微调及 holdout 对比已完成")
    return {
        "task_type": "prediction",
        "tool_name": "finetune_prediction_model",
        "summary": f"{canonical} 微调完成，并已比较基础模型与微调模型的 holdout 指标。",
        **record,
        "metrics": evaluation,
        "skipped_non_numeric": non_numeric,
    }


TOOLS = [finetune_prediction_model]
