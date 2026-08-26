"""CatBoost-based root-cause analysis for target/feature relationships."""

from __future__ import annotations

import math
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from langchain.tools import ToolRuntime, tool
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from agent_app.tools._tool_guard import tool_guard
from agent_app.tools.analysis_tools._common import make_envelope


ANALYSIS_MODEL_VERSION = 1
ANALYSIS_MODEL_ROOT = (
    Path(__file__).resolve().parents[2] / "artifacts" / "analysis_models"
)


def _safe_segment(value: Any, fallback: str) -> str:
    text = str(value or fallback).strip()
    text = re.sub(r"[^0-9A-Za-z._-]+", "_", text).strip("._")
    return text[:120] or fallback


def _artifact_path(runtime: ToolRuntime, save_name: Optional[str]) -> Path:
    ctx = runtime.context
    user = _safe_segment(getattr(ctx, "user_id", None), "anonymous")
    thread = _safe_segment(getattr(ctx, "thread_id", None), "default")
    source = Path(str(getattr(ctx, "file_path", "dataset"))).stem
    source = _safe_segment(source, "dataset")
    name = _safe_segment(save_name, f"catboost_root_cause_{uuid.uuid4().hex[:8]}")
    folder = ANALYSIS_MODEL_ROOT / user / thread / f"{source}_analysis"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{name}.joblib"


def _selected_artifact_path(runtime: ToolRuntime) -> Optional[Path]:
    """Resolve a selected model from trusted runtime coordinates."""
    ctx = runtime.context
    save_name = getattr(ctx, "model_save_name", None)
    if not save_name:
        return None
    category = getattr(ctx, "model_category", None)
    if category and category != "data_analysis":
        raise ValueError("所选模型不是数据分析模型")
    user = _safe_segment(getattr(ctx, "user_id", None), "anonymous")
    thread = _safe_segment(getattr(ctx, "model_thread_id", None), "default")
    source = _safe_segment(getattr(ctx, "model_source_file", None), "dataset")
    name = _safe_segment(save_name, "analysis_model")
    return ANALYSIS_MODEL_ROOT / user / thread / f"{source}_analysis" / f"{name}.joblib"


def _progress_emitter(injected_writer=None):
    operation_id = uuid.uuid4().hex
    writer = injected_writer
    if writer is None:
        try:
            from langgraph.config import get_stream_writer
            writer = get_stream_writer()
        except Exception:
            writer = None

    def emit(stage: str, **payload: Any) -> None:
        if writer is None:
            return
        try:
            writer({
                "event": "analysis_training_progress",
                "operation_id": operation_id,
                "model_name": "CatBoost 根因分析",
                "stage": stage,
                **payload,
            })
        except Exception:
            pass

    return emit


class _CatBoostProgressCallback:
    def __init__(self, emit, target: str, target_index: int, target_count: int, iterations: int):
        self.emit = emit
        self.target = target
        self.target_index = target_index
        self.target_count = target_count
        self.iterations = max(1, iterations)
        self.history: List[Dict[str, Any]] = []

    def after_iteration(self, info) -> bool:
        iteration = int(getattr(info, "iteration", 0) or 0)
        emit_every = max(1, self.iterations // 100)
        if iteration != 1 and iteration % emit_every != 0 and iteration != self.iterations:
            return True
        metrics = getattr(info, "metrics", {}) or {}
        learn = metrics.get("learn", {}) or {}
        validation = metrics.get("validation", {}) or metrics.get("validation_0", {}) or {}
        train_rmse = _last_metric(learn.get("RMSE"))
        val_rmse = _last_metric(validation.get("RMSE"))
        self.history.append({
            "iteration": iteration,
            "train_rmse": train_rmse,
            "validation_rmse": val_rmse,
        })
        overall = (
            (self.target_index + 0.85 * min(iteration / self.iterations, 1.0))
            / self.target_count
        ) * 90.0
        event_metrics = {}
        if train_rmse is not None:
            event_metrics["train_rmse"] = train_rmse
        if val_rmse is not None:
            event_metrics["validation_rmse"] = val_rmse
        self.emit(
            "training",
            current=iteration,
            total=self.iterations,
            percent=overall,
            message=f"正在训练目标列 {self.target}",
            metrics=event_metrics,
        )
        return True


def _last_metric(value: Any) -> Optional[float]:
    if isinstance(value, (list, tuple)) and value:
        value = value[-1]
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _metric_block(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, Optional[float]]:
    mse = float(mean_squared_error(y_true, y_pred))
    nonzero = np.abs(y_true) > 1e-12
    mape = (
        float(np.mean(np.abs((y_true[nonzero] - y_pred[nonzero]) / y_true[nonzero])) * 100.0)
        if nonzero.any() else None
    )
    denom = np.abs(y_true) + np.abs(y_pred)
    valid_smape = denom > 1e-12
    smape = (
        float(np.mean(2.0 * np.abs(y_pred[valid_smape] - y_true[valid_smape]) / denom[valid_smape]) * 100.0)
        if valid_smape.any() else None
    )
    return {
        "mse": mse,
        "rmse": math.sqrt(mse),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)) if len(y_true) >= 2 else None,
        "mape": mape,
        "smape": smape,
    }


def _prepare_features(
    frame: pd.DataFrame,
    feature_columns: List[str],
    categorical_columns: Optional[List[str]] = None,
) -> Tuple[pd.DataFrame, List[int]]:
    X = frame[feature_columns].copy()
    categorical_indices: List[int] = []
    forced_categorical = set(categorical_columns or [])
    for idx, column in enumerate(feature_columns):
        series = X[column]
        if column not in forced_categorical and pd.api.types.is_numeric_dtype(series):
            numeric = pd.to_numeric(series, errors="coerce")
            median = numeric.median()
            X[column] = numeric.fillna(float(median) if pd.notna(median) else 0.0)
        else:
            categorical_indices.append(idx)
            X[column] = series.astype("string").fillna("<MISSING>").astype(str)
    return X, categorical_indices


def _model_explanations(
    model: Any,
    X: pd.DataFrame,
    features: List[str],
    cat_indices: List[int],
    Pool: Any,
    top_n_features: int,
    shap_sample_size: int,
    rng: np.random.RandomState,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    feature_importance = np.asarray(model.get_feature_importance(type="FeatureImportance"), dtype=float)
    order = np.argsort(np.abs(feature_importance))[::-1][: min(top_n_features, len(features))]
    shap_source = X.reset_index(drop=True)
    effective_samples = min(int(shap_sample_size), 300)
    if len(shap_source) > effective_samples:
        positions = np.sort(rng.choice(len(shap_source), effective_samples, replace=False))
        shap_source = shap_source.iloc[positions].reset_index(drop=True)
    shap_values = np.asarray(
        model.get_feature_importance(Pool(shap_source, cat_features=cat_indices), type="ShapValues"),
        dtype=float,
    )[:, : len(features)]
    mean_abs_shap = np.mean(np.abs(shap_values), axis=0)
    shap_summary: List[Dict[str, Any]] = []
    for feature_index in order[: min(10, len(order))]:
        column = features[int(feature_index)]
        raw_values = shap_source[column].tolist()
        labels = [str(value) for value in raw_values]
        if int(feature_index) in cat_indices:
            mapping = {label: idx for idx, label in enumerate(sorted(set(labels)))}
            color_values = [float(mapping[label]) for label in labels]
        else:
            color_values = [float(value) for value in raw_values]
        shap_summary.append({
            "feature": column,
            "importance": float(feature_importance[feature_index]),
            "mean_abs_shap": float(mean_abs_shap[feature_index]),
            "points": [{
                "shap_value": float(shap_values[row_index, feature_index]),
                "feature_value": color_values[row_index],
                "display_value": labels[row_index],
            } for row_index in range(len(shap_source))],
        })
    importance = [
        {"feature": features[int(i)], "importance": float(feature_importance[i])}
        for i in order
    ]
    return importance, shap_summary


def _split_positions(n: int, train_ratio: float, validation_ratio: float) -> Tuple[slice, slice, slice]:
    n_train = max(2, int(n * train_ratio))
    n_validation = max(2, int(n * validation_ratio))
    if n_train + n_validation > n - 2:
        raise ValueError("有效样本过少，无法保证训练集、验证集和测试集各至少 2 行")
    return slice(0, n_train), slice(n_train, n_train + n_validation), slice(n_train + n_validation, n)


@tool("analyze_root_causes_catboost")
@tool_guard("analyze_root_causes_catboost")
def analyze_root_causes_catboost(
    runtime: ToolRuntime,
    train_ratio: float = 0.7,
    validation_ratio: float = 0.1,
    test_ratio: float = 0.2,
    split_strategy: str = "chronological",
    iterations: int = 5000,
    learning_rate: float = 0.05,
    depth: int = 6,
    early_stopping_rounds: int = 50,
    random_seed: int = 42,
    top_n_features: int = 15,
    shap_sample_size: int = 300,
    thread_count: int = -1,
    save_name: Optional[str] = None,
) -> Dict[str, Any]:
    """训练 CatBoost 回归模型并用 TreeSHAP 分析目标列的关键驱动因素。

    使用 ``AnalysisContext.feature_columns`` 预测 ``target_columns``；当目标列
    多于一个时逐列训练独立模型。默认按原始行顺序切分 70%/10%/20%，避免
    工业时序数据发生未来信息泄漏。模型训练后自动持久化到“我的模型/数据分析”。

    Parameters
    ----------
    train_ratio, validation_ratio, test_ratio:
        三个集合的比例，必须都大于 0 且总和为 1。
    split_strategy:
        ``chronological``（默认，保持时序顺序）或 ``random``。
    iterations, learning_rate, depth, early_stopping_rounds:
        CatBoost 常用训练参数。
    top_n_features:
        返回并展示的重要特征数量。
    shap_sample_size:
        每个目标最多用于 TreeSHAP 可视化的验证/测试样本数。
    save_name:
        可选模型资产名称；未提供时自动生成。
    """
    try:
        from catboost import CatBoostRegressor, Pool
    except ImportError as exc:
        raise ImportError("根因分析需要 catboost，请先安装项目 requirements.txt 中的 catboost 依赖") from exc

    ctx = runtime.context
    df: pd.DataFrame = ctx.df
    selected_path = _selected_artifact_path(runtime)
    if selected_path is not None:
        if not selected_path.is_file():
            raise FileNotFoundError(f"所选数据分析模型不存在：{selected_path.name}")
        emit = _progress_emitter(getattr(ctx, "stream_writer", None))
        emit("preparing", percent=5.0, message="正在加载已训练的数据分析模型")
        try:
            bundle = joblib.load(selected_path)
        except Exception as exc:
            emit("failed", message=f"数据分析模型加载失败：{exc}")
            raise ValueError(f"无法加载所选数据分析模型：{exc}") from exc
        if (
            not isinstance(bundle, dict)
            or bundle.get("_analysis_model_version") != ANALYSIS_MODEL_VERSION
            or not isinstance(bundle.get("models"), dict)
            or not isinstance(bundle.get("metadata"), dict)
        ):
            raise ValueError("所选文件不是兼容的数据分析模型")
        metadata = bundle["metadata"]
        models = bundle["models"]
        features = list(metadata.get("feature_columns") or [])
        missing = [column for column in features if column not in df.columns]
        if not features or missing:
            detail = f"，缺少：{', '.join(missing)}" if missing else ""
            raise ValueError(f"当前数据不满足模型所需特征列{detail}")
        categorical_columns = list(metadata.get("categorical_columns") or [])
        X, cat_indices = _prepare_features(df, features, categorical_columns)
        rng = np.random.RandomState(int(random_seed))
        per_target: Dict[str, Any] = {}
        strongest: List[str] = []
        emit("evaluating", percent=30.0, message="正在预测并计算当前数据的 TreeSHAP")
        for target, model in models.items():
            predictions = np.asarray(model.predict(X), dtype=float)
            importance, shap_summary = _model_explanations(
                model, X, features, cat_indices, Pool,
                top_n_features, shap_sample_size, rng,
            )
            current_metrics = None
            if target in df.columns:
                actual = pd.to_numeric(df[target], errors="coerce").to_numpy(dtype=float)
                valid = np.isfinite(actual) & np.isfinite(predictions)
                if valid.any():
                    current_metrics = _metric_block(actual[valid], predictions[valid])
            saved_target = (metadata.get("targets") or {}).get(target, {})
            per_target[target] = {
                "title": f"{target} 根因分析预测",
                "mode": "load",
                "validation_metrics": saved_target.get("validation_metrics"),
                "test_metrics": saved_target.get("test_metrics"),
                "current_metrics": current_metrics,
                "feature_importance": importance,
                "shap_summary": shap_summary,
                "training_history": [],
                "best_iteration": saved_target.get("best_iteration"),
                "n_train": saved_target.get("n_train", 0),
                "n_validation": saved_target.get("n_validation", 0),
                "n_test": saved_target.get("n_test", 0),
                "n_predictions": len(predictions),
                "prediction_summary": {
                    "count": len(predictions),
                    "min": float(np.min(predictions)),
                    "max": float(np.max(predictions)),
                    "mean": float(np.mean(predictions)),
                    "std": float(np.std(predictions)),
                },
                "prediction_preview": [
                    {"row": int(i) + 1, "prediction": float(value)}
                    for i, value in enumerate(predictions[:20])
                ],
            }
            if importance:
                strongest.append(f"{target} 的首要影响特征为 {importance[0]['feature']}")
        if not per_target:
            raise ValueError("所选数据分析模型中没有可用于预测的目标模型")
        targets = list(per_target)
        emit("completed", percent=100.0, message="已完成模型加载、预测与解释")
        return make_envelope(
            tool_name="catboost_root_cause",
            summary=f"已加载训练模型并完成 {len(df)} 行数据、{len(targets)} 个目标的预测。",
            key_findings=strongest,
            metrics={
                "mode": "load",
                "active_column": targets[0],
                "per_target": per_target,
                "feature_columns": features,
            },
            recommendations=["结合 SHAP 方向与工艺机理复核关键参数，不将模型关联性直接解释为确定因果关系。"],
            notes=["当前数据包含目标列时会同时计算预测指标；不包含目标列时仅输出预测与解释结果。"],
            extra={
                "mode": "load",
                "model_path": str(selected_path),
                "save_name": selected_path.stem,
                "model_metadata": metadata,
            },
        )

    ratios = [float(train_ratio), float(validation_ratio), float(test_ratio)]
    if any(value <= 0 for value in ratios) or not math.isclose(sum(ratios), 1.0, abs_tol=1e-8):
        raise ValueError("train_ratio、validation_ratio、test_ratio 必须均大于 0 且总和为 1")
    if split_strategy not in {"chronological", "random"}:
        raise ValueError("split_strategy 只支持 chronological 或 random")
    if iterations < 10 or learning_rate <= 0 or not 2 <= depth <= 16:
        raise ValueError("iterations 必须 >= 10，learning_rate > 0，depth 必须在 2 到 16 之间")
    if top_n_features < 1 or shap_sample_size < 1:
        raise ValueError("top_n_features 和 shap_sample_size 必须为正整数")

    targets = [column for column in (ctx.target_columns or []) if column in df.columns]
    features = [
        column for column in (ctx.feature_columns or [])
        if column in df.columns and column not in targets
    ]
    if not targets:
        raise ValueError("AnalysisContext.target_columns 中没有可用目标列")
    if not features:
        raise ValueError("AnalysisContext.feature_columns 中没有可用特征列")

    emit = _progress_emitter(getattr(ctx, "stream_writer", None))
    emit("preparing", percent=0.0, message="正在准备 CatBoost 根因分析数据")
    per_target: Dict[str, Any] = {}
    models: Dict[str, Any] = {}
    metadata_targets: Dict[str, Any] = {}
    categorical_columns: List[str] = []
    rng = np.random.RandomState(random_seed)

    for target_index, target in enumerate(targets):
        y = pd.to_numeric(df[target], errors="coerce")
        valid = y.notna()
        frame = df.loc[valid, features].copy()
        target_values = y.loc[valid].astype(float).reset_index(drop=True)
        frame = frame.reset_index(drop=True)
        if len(frame) < 10:
            raise ValueError(f"目标列 {target} 的有效样本少于 10，无法可靠划分训练/验证/测试集")
        if split_strategy == "random":
            order = rng.permutation(len(frame))
            frame = frame.iloc[order].reset_index(drop=True)
            target_values = target_values.iloc[order].reset_index(drop=True)

        X, cat_indices = _prepare_features(frame, features)
        categorical_columns = [features[index] for index in cat_indices]
        train_slice, val_slice, test_slice = _split_positions(len(X), train_ratio, validation_ratio)
        X_train, y_train = X.iloc[train_slice], target_values.iloc[train_slice]
        X_val, y_val = X.iloc[val_slice], target_values.iloc[val_slice]
        X_test, y_test = X.iloc[test_slice], target_values.iloc[test_slice]
        train_pool = Pool(X_train, y_train, cat_features=cat_indices)
        val_pool = Pool(X_val, y_val, cat_features=cat_indices)

        callback = _CatBoostProgressCallback(
            emit, target, target_index, len(targets), int(iterations),
        )
        model = CatBoostRegressor(
            iterations=int(iterations),
            learning_rate=float(learning_rate),
            depth=int(depth),
            loss_function="RMSE",
            eval_metric="RMSE",
            random_seed=int(random_seed),
            thread_count=int(thread_count),
            allow_writing_files=False,
            verbose=False,
        )
        try:
            model.fit(
                train_pool,
                eval_set=val_pool,
                early_stopping_rounds=int(early_stopping_rounds),
                use_best_model=True,
                callbacks=[callback],
            )
        except Exception as exc:
            emit("failed", message=f"目标列 {target} 训练失败：{exc}")
            raise
        evaluation_percent = ((target_index + 0.9) / len(targets)) * 90.0
        emit("evaluating", percent=evaluation_percent, message=f"正在评估并计算 {target} 的 TreeSHAP")

        val_pred = np.asarray(model.predict(X_val), dtype=float)
        test_pred = np.asarray(model.predict(X_test), dtype=float)
        feature_importance = np.asarray(model.get_feature_importance(type="FeatureImportance"), dtype=float)
        order = np.argsort(np.abs(feature_importance))[::-1][: min(top_n_features, len(features))]

        shap_source = pd.concat([X_val, X_test], ignore_index=True)
        effective_shap_samples = min(int(shap_sample_size), 300)
        if len(shap_source) > effective_shap_samples:
            sample_positions = np.sort(rng.choice(len(shap_source), effective_shap_samples, replace=False))
            shap_source = shap_source.iloc[sample_positions].reset_index(drop=True)
        try:
            shap_values = np.asarray(
                model.get_feature_importance(
                    Pool(shap_source, cat_features=cat_indices),
                    type="ShapValues",
                ),
                dtype=float,
            )[:, : len(features)]
        except Exception as exc:
            emit("failed", message=f"目标列 {target} 的 TreeSHAP 计算失败：{exc}")
            raise
        mean_abs_shap = np.mean(np.abs(shap_values), axis=0)

        shap_summary = []
        for feature_index in order[: min(10, len(order))]:
            column = features[int(feature_index)]
            raw_values = shap_source[column].tolist()
            if int(feature_index) in cat_indices:
                labels = [str(value) for value in raw_values]
                mapping = {label: idx for idx, label in enumerate(sorted(set(labels)))}
                color_values = [float(mapping[label]) for label in labels]
            else:
                labels = [str(value) for value in raw_values]
                color_values = [float(value) for value in raw_values]
            shap_summary.append({
                "feature": column,
                "importance": float(feature_importance[feature_index]),
                "mean_abs_shap": float(mean_abs_shap[feature_index]),
                "points": [
                    {
                        "shap_value": float(shap_values[row_index, feature_index]),
                        "feature_value": color_values[row_index],
                        "display_value": labels[row_index],
                    }
                    for row_index in range(len(shap_source))
                ],
            })

        best_iteration = int(model.get_best_iteration()) if model.get_best_iteration() is not None else None
        per_target[target] = {
            "title": f"{target} 根因分析",
            "mode": "train",
            "validation_metrics": _metric_block(y_val.to_numpy(), val_pred),
            "test_metrics": _metric_block(y_test.to_numpy(), test_pred),
            "feature_importance": [
                {"feature": features[int(i)], "importance": float(feature_importance[i])}
                for i in order
            ],
            "shap_summary": shap_summary,
            "training_history": callback.history,
            "best_iteration": best_iteration,
            "n_train": len(X_train),
            "n_validation": len(X_val),
            "n_test": len(X_test),
        }
        models[target] = model
        metadata_targets[target] = {
            "best_iteration": best_iteration,
            "validation_metrics": per_target[target]["validation_metrics"],
            "test_metrics": per_target[target]["test_metrics"],
            "n_train": len(X_train),
            "n_validation": len(X_val),
            "n_test": len(X_test),
        }

    emit("saving", percent=96.0, message="正在持久化 CatBoost 分析模型")
    artifact_path = _artifact_path(runtime, save_name)
    now = datetime.now(timezone.utc).isoformat()
    metadata = {
        "category": "data_analysis",
        "task_type": "analysis",
        "model_type": "CatBoostRegressor",
        "save_name": artifact_path.stem,
        "target_columns": targets,
        "feature_columns": features,
        "categorical_columns": categorical_columns,
        "n_targets": len(targets),
        "n_features": len(features),
        "n_samples": len(df),
        "source_file": Path(str(getattr(ctx, "file_path", "dataset"))).stem,
        "thread_id": getattr(ctx, "thread_id", None),
        "trained_at": now,
        "saved_at": now,
        "split": {
            "strategy": split_strategy,
            "train_ratio": train_ratio,
            "validation_ratio": validation_ratio,
            "test_ratio": test_ratio,
        },
        "training": {
            "iterations": iterations,
            "learning_rate": learning_rate,
            "depth": depth,
            "early_stopping_rounds": early_stopping_rounds,
            "random_seed": random_seed,
        },
        "targets": metadata_targets,
    }
    try:
        joblib.dump({
            "_analysis_model_version": ANALYSIS_MODEL_VERSION,
            "models": models,
            "metadata": metadata,
        }, artifact_path)
    except Exception as exc:
        emit("failed", message=f"分析模型保存失败：{exc}")
        raise
    emit("completed", percent=100.0, message="CatBoost 根因分析模型训练并保存完成")

    strongest = []
    for target, result in per_target.items():
        if result["feature_importance"]:
            first = result["feature_importance"][0]
            strongest.append(f"{target} 的首要驱动特征为 {first['feature']}")
    return make_envelope(
        tool_name="catboost_root_cause",
        summary=f"已针对 {len(targets)} 个目标列分别训练 CatBoost 根因分析模型。",
        key_findings=strongest,
        metrics={
            "mode": "train",
            "active_column": targets[0],
            "per_target": per_target,
            "feature_columns": features,
            "split_strategy": split_strategy,
            "split_ratios": ratios,
        },
        recommendations=["结合 SHAP 方向与工艺机理复核关键参数，不将模型关联性直接解释为确定因果关系。"],
        notes=["默认按原始行顺序切分以避免时序数据未来信息泄漏。"],
        extra={
            "mode": "train",
            "model_path": str(artifact_path),
            "save_name": artifact_path.stem,
            "model_metadata": metadata,
        },
    )


TOOLS = [analyze_root_causes_catboost]
