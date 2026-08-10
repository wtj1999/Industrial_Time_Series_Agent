"""Train / predict / persist tools for PyOD detectors.

These tools operate on ``ctx.df`` and ``ctx.target_columns`` (falling
back to ``ctx.feature_columns`` when targets are empty):

- :func:`train_anomaly_detector` — fit a named detector on the current
  DataFrame and persist it under the deterministic
  ``artifacts/anomaly_detection/{thread_id}/{file_stem}_anomaly_detection/``
  layout. The LLM only provides ``save_name``.
- :func:`detect_anomalies` — one-shot fit + score (no persistence).
- :func:`load_detector_and_predict` — load a saved detector (by bare
  ``save_name``) and score the current DataFrame.
- :func:`list_saved_detectors` — enumerate persisted detectors in the
  current (thread_id, file_path) scope.
- :func:`delete_saved_detector` — remove a saved detector artifact.
- :func:`predict_with_detector` — score new samples on a freshly-fit
  detector with explicit inlier/outlier split for inductive evaluation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from langchain.tools import ToolRuntime, tool

from agent_app.tools._tool_guard import tool_guard
from agent_app.tools.anomaly_detection_tools._common import (
    artifacts_dir_for,
    auto_save_name,
    build_detector_by_name,
    decision_scores_,
    ensure_dir,
    format_notes,
    is_transductive,
    labels_,
    prepare_feature_matrix,
    resolve_model_path,
    score_with_detector,
    scores_summary,
    threshold_,
    top_anomaly_rows,
)
from agent_app.tools.outlier_detection_scripts.pyod.utils import persistence

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Tools
# ----------------------------------------------------------------------

@tool("train_anomaly_detector")
@tool_guard("train_anomaly_detector")
def train_anomaly_detector(
    detector_name: str,
    runtime: ToolRuntime,
    contamination: float = 0.1,
    save_name: Optional[str] = None,
    random_state: Optional[int] = None,
) -> Dict[str, Any]:
    """在当前 DataFrame 上训练指定 PyOD 检测器并持久化。

    存储路径由框架根据 ``(thread_id, file_path)`` 自动拼接为::

        artifacts/anomaly_detection/
          <thread_id>/<file_stem>_anomaly_detection/<save_name>.joblib

    大模型只需要提供 ``save_name``（如 ``"iforest_v1"``），无需也**不能**
    生成完整路径。同一对话同一文件下的同名模型会被覆盖。

    Parameters
    ----------
    detector_name : str
        PyOD 检测器名称，例如 ``"IForest"``、``"LOF"``、``"HBOS"``。
    contamination : float, default 0.1
        期望的异常比例，影响 ``threshold_`` 与 ``labels_``。
    save_name : str, optional
        保存文件名（不带后缀）。未提供时自动生成
        ``{detector_name}_{timestamp}``。
    random_state : int, optional
        随机种子。

    Returns
    -------
    Dict[str, Any]
        包含 ``model_path``、``threshold``、``n_anomalies``、
        ``training_scores`` 统计与 ``metadata``。
    """
    X, info = prepare_feature_matrix(runtime)

    detector = build_detector_by_name(
        detector_name,
        contamination=contamination,
        random_state=random_state,
    )
    detector.fit(X)

    scores = decision_scores_(detector)
    th = threshold_(detector)
    lbls = labels_(detector)
    n_anomalies = int((lbls > 0).sum()) if lbls.size else 0

    if save_name is None:
        save_name = auto_save_name(detector_name)
    model_path = resolve_model_path(save_name, runtime)
    ensure_dir(model_path.parent)

    metadata = {
        "detector_name": detector_name,
        "params": {},
        "contamination": contamination,
        "random_state": random_state,
        "n_samples": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "feature_columns": info["used_columns"],
        "source": info["source"],
        "n_anomalies": n_anomalies,
        "threshold": th,
        "transductive": is_transductive(detector_name),
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    persistence.save(detector, model_path, metadata=metadata)

    extra_notes: List[str] = []
    if is_transductive(detector_name):
        extra_notes.append(
            "%s 是 transductive 检测器，加载后不能对新样本 predict。"
            % detector_name)

    summary_stats = scores_summary(scores, threshold=th, top_n=10)
    return {
        "task_type": "anomaly_detection",
        "tool_name": "train_anomaly_detector",
        "detector_name": detector_name,
        "summary": (
            "已训练 %s，识别出 %d 个异常（contamination=%.3f），"
            "模型保存至 %s"
            % (detector_name, n_anomalies, contamination, model_path.name)
        ),
        "model_path": str(model_path),
        "save_name": Path(model_path).stem,
        "n_samples": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "threshold": th,
        "n_anomalies": n_anomalies,
        "training_scores": summary_stats,
        "metadata": metadata,
        "notes": format_notes(info, extra_notes),
    }


@tool("detect_anomalies")
@tool_guard("detect_anomalies")
def detect_anomalies(
    detector_name: str,
    runtime: ToolRuntime,
    contamination: float = 0.1,
    return_top_n: int = 10,
    random_state: Optional[int] = None,
) -> Dict[str, Any]:
    """一次性训练 + 打分：在当前 DataFrame 上用指定检测器输出异常分数。

    与 :func:`train_anomaly_detector` 的区别：本工具**不保存模型**，仅返回
    分数、二值标签与 Top-N 异常行（含原始数值）。适合「快速看一下这批
    数据用检测器能挑出哪些异常」之类的探索性需求。

    Parameters
    ----------
    detector_name : str
        检测器名称，例如 ``"IForest"``、``"MatrixProfile"``。
    contamination : float, default 0.1
        异常比例，影响 ``threshold_`` 与 ``labels_``。
    return_top_n : int, default 10
        返回分数最高的前 N 行及其原始值。设为 0 可关闭。
    random_state : int, optional
        随机种子。

    Returns
    -------
    Dict[str, Any]
        ``scores_summary`` 为分数统计；``top_anomalies`` 为 Top-N 行；
        ``labels`` 仅在内存中以列表形式返回（int 0/1）。
    """
    ctx = runtime.context
    df: pd.DataFrame = ctx.df
    X, info = prepare_feature_matrix(runtime)

    detector = build_detector_by_name(
        detector_name,
        contamination=contamination,
        random_state=random_state,
    )
    detector.fit(X)

    scores, lbls, th, supports_ = score_with_detector(
        detector, X, detector_name)

    top_rows = top_anomaly_rows(
        df, scores, th, return_top_n, columns=info["used_columns"])
    summary_stats = scores_summary(scores, threshold=th, top_n=return_top_n)

    extra_notes: List[str] = []
    if not supports_:
        extra_notes.append(
            "%s 是 transductive 检测器：未调用 predict，分数来自 "
            "decision_scores_。后续对新数据无法直接打分。" % detector_name)
        extra_notes.append("supports_out_of_sample: false")

    return {
        "task_type": "anomaly_detection",
        "tool_name": "detect_anomalies",
        "detector_name": detector_name,
        "summary": (
            "%s 完成：共 %d 个样本，%d 个被判为异常（contamination=%.3f）。"
            % (detector_name, X.shape[0],
               int((lbls > 0).sum()) if lbls.size else 0,
               contamination)
        ),
        "n_samples": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "threshold": th,
        "supports_out_of_sample": supports_,
        "scores_summary": summary_stats,
        "labels": lbls.tolist() if lbls.size else [],
        "scores": scores.tolist(),
        "top_anomalies": top_rows,
        "notes": format_notes(info, extra_notes),
    }


@tool("load_detector_and_predict")
@tool_guard("load_detector_and_predict")
def load_detector_and_predict(
    save_name: str,
    runtime: ToolRuntime,
    return_top_n: int = 10,
) -> Dict[str, Any]:
    """加载当前 ``(thread_id, file_path)`` 作用域下保存的检测器并打分。

    ``save_name`` 是训练时给定的裸名称（如 ``"iforest_v1"``）。框架会
    自动定位到::

        artifacts/anomaly_detection/
          <thread_id>/<file_stem>_anomaly_detection/<save_name>.joblib

    Parameters
    ----------
    save_name : str
        训练时使用的 save_name（不带 ``.joblib`` 后缀）。
    return_top_n : int, default 10
        返回分数最高的前 N 行。

    Returns
    -------
    Dict[str, Any]
        ``model_metadata`` 来自保存时写入的信封；``scores_summary``、
        ``top_anomalies`` 与 :func:`detect_anomalies` 一致。
    """
    ctx = runtime.context
    df: pd.DataFrame = ctx.df

    model_path = resolve_model_path(save_name, runtime)
    if not Path(model_path).exists():
        return {
            "task_type": "anomaly_detection",
            "tool_name": "load_detector_and_predict",
            "summary": "未找到模型文件 %s" % model_path,
            "model_path": str(model_path),
            "save_name": save_name,
            "notes": [
                "请确认 save_name 正确；可用 list_saved_detectors 查看当前 "
                "(thread_id, file_path) 作用域下已保存的模型。"
            ],
        }

    X, info = prepare_feature_matrix(runtime)

    model, envelope = persistence.load(
        model_path, strict=False, return_metadata=True)

    saved_meta = (envelope or {}).get("metadata") or {}
    detector_name = (
        saved_meta.get("detector_name")
        or type(model).__name__
    )

    supports_ = not is_transductive(detector_name)
    extra_notes: List[str] = []
    try:
        scores, lbls, th, supports_ = score_with_detector(
            model, X, detector_name)
    except NotImplementedError:
        extra_notes.append(
            "模型不支持新样本 decision_function，已在当前数据上重新 fit 并"
            "读取 decision_scores_。")
        model.fit(X)
        scores = decision_scores_(model)
        th = threshold_(model)
        lbls = labels_(model)
        supports_ = False

    top_rows = top_anomaly_rows(
        df, scores, th, return_top_n, columns=info["used_columns"])
    summary_stats = scores_summary(scores, threshold=th, top_n=return_top_n)

    if not supports_:
        extra_notes.append("supports_out_of_sample: false")

    # Surface column-drift between training and current DataFrame.
    saved_cols = list(saved_meta.get("feature_columns") or [])
    if saved_cols and saved_cols != info["used_columns"]:
        extra_notes.append(
            "当前输入列与训练时记录的列不一致（训练：%s；当前：%s）。"
            "结果可能不可靠。"
            % (saved_cols, info["used_columns"]))

    envelope_summary = {
        k: v for k, v in (envelope or {}).items() if k != "model"
    } if envelope else {}

    return {
        "task_type": "anomaly_detection",
        "tool_name": "load_detector_and_predict",
        "detector_name": detector_name,
        "summary": (
            "加载 %s 完成打分：%d 个样本，%d 个异常。"
            % (detector_name, X.shape[0],
               int((lbls > 0).sum()) if lbls.size else 0)
        ),
        "model_path": str(model_path),
        "save_name": save_name,
        "n_samples": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "threshold": th,
        "supports_out_of_sample": supports_,
        "scores_summary": summary_stats,
        "labels": lbls.tolist() if lbls.size else [],
        "scores": scores.tolist(),
        "top_anomalies": top_rows,
        "model_metadata": saved_meta,
        "envelope": envelope_summary,
        "notes": format_notes(info, extra_notes),
    }


@tool("list_saved_detectors")
@tool_guard("list_saved_detectors")
def list_saved_detectors(runtime: ToolRuntime) -> Dict[str, Any]:
    """列出**当前 ``(thread_id, file_path)`` 作用域**下保存的检测器。

    仅读取每个 ``.joblib`` 文件的**信封**（依赖版本、保存时间、用户
    写入的 metadata），**不加载模型体**，因此代价很低。当用户问
    「我们之前训练过哪些模型」「上次保存的 IForest 叫什么」时调用。

    Returns
    -------
    Dict[str, Any]
        ``detectors`` 为元数据列表，按 ``saved_at`` 倒序排列。
    """
    import joblib

    scope_dir = artifacts_dir_for(runtime)
    if not scope_dir.exists():
        return {
            "task_type": "anomaly_detection",
            "tool_name": "list_saved_detectors",
            "summary": "当前作用域下没有已保存的检测器。",
            "scope_dir": str(scope_dir),
            "detectors": [],
            "notes": [
                "当前 (thread_id, file_path) 作用域目录不存在，",
                "可能尚未在此上下文中训练过模型。"
            ],
        }

    files = sorted(scope_dir.glob("*.joblib"))
    entries: List[Dict[str, Any]] = []
    failed: List[Dict[str, str]] = []
    for fp in files:
        try:
            obj = joblib.load(fp, mmap_mode="r")
            if isinstance(obj, dict) and "_pyod_persistence_version" in obj:
                meta = obj.get("metadata") or {}
                entries.append({
                    "save_name": fp.stem,
                    "file_name": fp.name,
                    "path": str(fp),
                    "saved_at": obj.get("saved_at"),
                    "pyod_version": obj.get("pyod_version"),
                    "sklearn_version": obj.get("sklearn_version"),
                    "model_class": obj.get("model_class"),
                    "detector_name": meta.get("detector_name"),
                    "contamination": meta.get("contamination"),
                    "n_samples": meta.get("n_samples"),
                    "n_features": meta.get("n_features"),
                    "feature_columns": meta.get("feature_columns", []),
                    "source": meta.get("source"),
                    "n_anomalies": meta.get("n_anomalies"),
                    "threshold": meta.get("threshold"),
                    "transductive": meta.get("transductive"),
                    "trained_at": meta.get("trained_at"),
                    "size_bytes": fp.stat().st_size,
                })
            else:
                entries.append({
                    "save_name": fp.stem,
                    "file_name": fp.name,
                    "path": str(fp),
                    "saved_at": None,
                    "model_class": type(obj).__name__,
                    "detector_name": type(obj).__name__,
                    "legacy": True,
                    "size_bytes": fp.stat().st_size,
                    "notes": "无版本信封（旧格式），无法验证依赖漂移。",
                })
        except Exception as exc:  # pragma: no cover - defensive
            failed.append({
                "file_name": fp.name,
                "error": "%s: %s" % (type(exc).__name__, exc),
            })

    entries.sort(
        key=lambda e: e.get("saved_at") or e.get("trained_at") or "",
        reverse=True,
    )

    return {
        "task_type": "anomaly_detection",
        "tool_name": "list_saved_detectors",
        "summary": "当前作用域下共有 %d 个模型。" % len(entries),
        "scope_dir": str(scope_dir),
        "detectors": entries,
        "notes": (
            ["以下文件无法读取：%s" % ", ".join(f["file_name"] for f in failed)]
            if failed else []
        ),
    }


@tool("delete_saved_detector")
@tool_guard("delete_saved_detector")
def delete_saved_detector(
    save_name: str,
    runtime: ToolRuntime,
) -> Dict[str, Any]:
    """删除当前作用域下保存的某个检测器。

    出于安全考虑，只允许通过 ``save_name`` 删除当前 ``(thread_id,
    file_path)`` 作用域下的文件，**不接受**绝对路径。

    Parameters
    ----------
    save_name : str
        训练时使用的 save_name（不带 ``.joblib`` 后缀）。

    Returns
    -------
    Dict[str, Any]
        ``deleted`` 表示是否删除成功；``path`` 为被删除文件路径。
    """
    if not save_name:
        return {
            "task_type": "anomaly_detection",
            "tool_name": "delete_saved_detector",
            "summary": "save_name 为空，未执行删除。",
            "deleted": False,
        }
    if "/" in save_name or "\\" in save_name:
        return {
            "task_type": "anomaly_detection",
            "tool_name": "delete_saved_detector",
            "summary": "拒绝删除：save_name 不能包含路径分隔符。",
            "deleted": False,
            "notes": ["只允许删除当前作用域下的模型，请提供裸 save_name。"],
        }

    model_path = resolve_model_path(save_name, runtime)
    if not model_path.exists():
        return {
            "task_type": "anomaly_detection",
            "tool_name": "delete_saved_detector",
            "summary": "未找到 %s，未执行删除。" % model_path,
            "deleted": False,
            "path": str(model_path),
        }

    try:
        model_path.unlink()
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "task_type": "anomaly_detection",
            "tool_name": "delete_saved_detector",
            "summary": "删除失败：%s: %s" % (type(exc).__name__, exc),
            "deleted": False,
            "path": str(model_path),
        }

    return {
        "task_type": "anomaly_detection",
        "tool_name": "delete_saved_detector",
        "summary": "已删除 %s。" % model_path.name,
        "deleted": True,
        "path": str(model_path),
        "save_name": save_name,
    }


@tool("fit_predict_with_split")
@tool_guard("fit_predict_with_split")
def fit_predict_with_split(
    detector_name: str,
    runtime: ToolRuntime,
    test_fraction: float = 0.3,
    contamination: float = 0.1,
    random_state: Optional[int] = None,
) -> Dict[str, Any]:
    """在 train/test 切分上做归纳式（inductive）评估。

    适用于希望「先在一部分数据上训练，再在剩余数据上检测」的场景。
    transductive 检测器（如 MatrixProfile）会自动退化为在合并数据上
    fit + 读取 ``decision_scores_``。

    Parameters
    ----------
    detector_name : str
        检测器名称。
    test_fraction : float, default 0.3
        用作「新样本」打分的比例，范围 (0, 1)。
    contamination : float, default 0.1
        异常比例。
    random_state : int, optional
        控制切分与检测器内部随机性的种子。

    Returns
    -------
    Dict[str, Any]
        ``train_scores`` 与 ``test_scores`` 分别给出训练/测试集的分数
        统计与 Top-N 异常行（含原始值）。
    """
    from sklearn.model_selection import train_test_split

    if not (0.0 < test_fraction < 1.0):
        raise ValueError(
            "test_fraction 必须在 (0, 1) 区间内，当前=%r" % test_fraction)

    ctx = runtime.context
    df: pd.DataFrame = ctx.df
    X, info = prepare_feature_matrix(runtime)

    rng = np.random.RandomState(random_state) if random_state is not None else None
    idx = np.arange(X.shape[0])
    train_idx, test_idx = train_test_split(
        idx, test_size=test_fraction,
        random_state=random_state, shuffle=True,
    )
    X_train, X_test = X[train_idx], X[test_idx]

    detector = build_detector_by_name(
        detector_name,
        contamination=contamination, random_state=random_state)
    detector.fit(X_train)

    if is_transductive(detector_name):
        extra_notes: List[str] = [
            "%s 是 transductive 检测器：在合并数据上重新 fit 并读取 "
            "decision_scores_。" % detector_name]
        detector.fit(X)
        train_scores_all = decision_scores_(detector)
        th = threshold_(detector)
        train_lbls = labels_(detector)
        # Surface train-set scores aligned to train_idx
        train_scores = train_scores_all[train_idx]
        test_scores = train_scores_all[test_idx]
        train_labels = train_lbls[train_idx] if train_lbls.size == X.shape[0] else train_lbls
        test_labels = (test_scores > th).astype(int) if th is not None else np.zeros_like(test_scores, dtype=int)
        supports_ = False
    else:
        extra_notes = []
        train_scores = np.asarray(
            detector.decision_function(X_train), dtype=float).ravel()
        test_scores = np.asarray(
            detector.decision_function(X_test), dtype=float).ravel()
        th = threshold_(detector)
        if th is None:
            cont = float(getattr(detector, "contamination", contamination)) or contamination
            th = float(np.percentile(
                train_scores,
                100.0 * (1.0 - min(max(cont, 1e-4), 0.5))))
        train_labels = (train_scores > th).astype(int)
        test_labels = (test_scores > th).astype(int)
        supports_ = True

    train_top = _top_rows_by_index(
        df, train_scores, train_idx, th, limit=10, columns=info["used_columns"])
    test_top = _top_rows_by_index(
        df, test_scores, test_idx, th, limit=10, columns=info["used_columns"])

    return {
        "task_type": "anomaly_detection",
        "tool_name": "fit_predict_with_split",
        "detector_name": detector_name,
        "summary": (
            "%s 切分评估完成：训练 %d，测试 %d，测试集异常 %d。"
            % (detector_name, X_train.shape[0], X_test.shape[0],
               int((test_labels > 0).sum()))
        ),
        "threshold": th,
        "supports_out_of_sample": supports_,
        "train": {
            "n_samples": int(X_train.shape[0]),
            "scores_summary": scores_summary(train_scores, threshold=th, top_n=10),
            "top_anomalies": train_top,
        },
        "test": {
            "n_samples": int(X_test.shape[0]),
            "scores_summary": scores_summary(test_scores, threshold=th, top_n=10),
            "top_anomalies": test_top,
        },
        "split": {
            "test_fraction": float(test_fraction),
            "random_state": random_state,
            "n_train": int(X_train.shape[0]),
            "n_test": int(X_test.shape[0]),
        },
        "notes": format_notes(info, extra_notes),
    }


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------

def _top_rows_by_index(
    df: pd.DataFrame,
    scores: np.ndarray,
    indices: np.ndarray,
    threshold: Optional[float],
    limit: int,
    columns: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Like :func:`top_anomaly_rows` but scores refer to ``df.iloc[indices]``."""
    scores = np.asarray(scores, dtype=float).ravel()
    n = min(int(limit), len(scores)) if limit else 0
    if n <= 0 or scores.size == 0:
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
    for offset in picked:
        original_idx = int(indices[offset])
        item = {
            "row_index": original_idx,
            "subset_position": int(offset),
            "score": float(scores[offset]),
        }
        if threshold is not None:
            item["is_anomaly"] = bool(scores[offset] > threshold)
        try:
            item["values"] = {
                str(c): _json_safe(df.iloc[original_idx][c])
                for c in cols
            }
        except Exception:
            item["values"] = {}
        rows.append(item)
    return rows


def _json_safe(v: Any) -> Any:
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


TOOLS = [
    train_anomaly_detector,
    detect_anomalies,
    load_detector_and_predict,
    list_saved_detectors,
    delete_saved_detector,
    fit_predict_with_split,
]
