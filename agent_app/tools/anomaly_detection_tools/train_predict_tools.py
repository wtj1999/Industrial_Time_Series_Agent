"""Detect / train / persist tools for PyOD detectors.

These tools operate on ``ctx.df`` and ``ctx.target_columns`` (falling
back to ``ctx.feature_columns`` when targets are empty):

- :func:`detect_with_model` — **统一入口**：自动判断加载已有模型还是
  训练新模型并对当前 DataFrame 打分，同时覆盖**表格与时序**两类数据
  （``as_time_series`` 三态控制；原生时序检测器自动走时序分支）。当
  用户在前端选择了复用模型时，走跨作用域加载分支；否则按
  ``detector_name`` 训练 + 持久化 + 打分。**所有打分都会持久化模型**
  ——没有"不保存"的探索分支；不想落盘请显式调
  :func:`delete_saved_detector` 清理。
- :func:`list_saved_detectors` — 枚举当前 (thread_id, file_path) 作用域
  下的已保存检测器（只读信封，代价低）。
- :func:`delete_saved_detector` — 删除当前作用域下的某个检测器 artifact。
- :func:`fit_predict_with_split` — 在 train/test 切分上做归纳式评估。
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from langchain.tools import ToolRuntime, tool

from agent_app.tools._tool_guard import tool_guard
from agent_app.tools.anomaly_detection_tools._result_limits import limit_anomaly_result
from agent_app.tools.anomaly_detection_tools._common import (
    TS_NATIVE_DETECTORS,
    anomaly_intervals,
    artifacts_dir_for,
    auto_save_name,
    build_detector_by_name,
    build_ts_detector,
    decision_scores_,
    ensure_dir,
    format_notes,
    format_ts_notes,
    is_transductive,
    labels_,
    prepare_feature_matrix,
    prepare_ts_matrix,
    resolve_model_path,
    score_with_detector,
    scores_summary,
    threshold_,
    top_anomaly_rows,
    top_ts_anomalies,
)
from agent_app.tools.outlier_detection_scripts.pyod.utils import persistence

logger = logging.getLogger(__name__)


def _training_progress_emitter(detector_name: str, injected_writer=None):
    """Return a best-effort LangGraph custom-stream emitter.

    Tools are also invoked directly by tests and scripts, where no LangGraph
    stream writer exists.  In that case progress reporting is intentionally a
    no-op and must never affect model training.
    """
    operation_id = uuid.uuid4().hex
    writer = injected_writer
    if writer is None:
        try:
            from langgraph.config import get_stream_writer
            writer = get_stream_writer()
        except Exception:
            writer = None

    def emit(stage: str, **data: Any) -> None:
        if writer is None:
            return
        payload = {
            "event": "anomaly_training_progress",
            "operation_id": operation_id,
            "detector_name": detector_name,
            "stage": stage,
            **data,
        }
        try:
            writer(payload)
        except Exception:
            logger.debug("Unable to emit training progress", exc_info=True)

    return emit


# ----------------------------------------------------------------------
# Tools
# ----------------------------------------------------------------------

@tool("detect_with_model")
@tool_guard("detect_with_model")
def detect_with_model(
    detector_name: str,
    runtime: ToolRuntime,
    contamination: float = 0.1,
    save_name: Optional[str] = None,
    return_top_n: int = 10,
    random_state: Optional[int] = None,
    as_time_series: Optional[bool] = None,
    time_column: Optional[str] = None,
    window_size: Optional[int] = None,
) -> Dict[str, Any]:
    """对当前 DataFrame 做异常检测并打分，**自动判断是加载已有模型还是训练新模型**，
    并**同时支持表格数据与时序数据**（统一入口）。

    决策规则（工具内部自动分派，LLM 无需也不应当干预）：

    - **加载模式**（``mode == "load"``）：当 ``runtime.context`` 携带
      ``model_save_name``（用户在前端 CSV 上传断点的模型选择器中选了
      某个模型）时触发。跨作用域加载该模型（路径解析见
      :func:`_common.resolve_model_path`）并对当前数据打分。
      ``detector_name`` / ``contamination`` / ``save_name`` /
      ``random_state`` 在此模式下被忽略，以模型信封里记录的为准。
      时序 / 表格的整形方式也以模型 metadata 的 ``mode`` 字段为准。

    - **训练模式**（``mode == "train"``）：否则用 ``detector_name`` 训练
      新检测器，持久化到当前 ``(thread_id, file_path)`` 作用域
     （``save_name`` 控制文件名，未指定则自动生成
      ``{detector_name}_{timestamp}``），然后对当前数据打分。

    **时序 / 表格的选择**（仅训练模式生效，加载模式以 metadata 为准）：

    - ``as_time_series=True`` → 强制时序分支；``False`` → 强制表格分支。
    - ``as_time_series=None``（默认）→ 自动判断：``detector_name`` 属于原生
      时序检测器（``MatrixProfile`` / ``KShape`` / ``SpectralResidual`` 等）
      时走时序分支，否则走表格分支。
    - 时序分支把 ``ctx.df[ctx.target_columns]`` 整形为 ``(n_timestamps,)``
      或 ``(n_timestamps, n_channels)``（NaN 用 ffill/bfill 填充），非原生
      时序检测器会自动用 ``TimeSeriesOD`` 滑窗桥接。返回 ``anomaly_intervals``
      （连续异常区间）、``n_timestamps`` / ``n_channels`` / ``time_column``。
    - 表格分支保持原有行为（每行一个 iid 样本，NaN 用列中位数填充）。

    所有训练分支都会落盘——没有"不保存"的旁路。若只是临时试一下、不
    想保留产物，请事后用 :func:`delete_saved_detector` 清理。

    Parameters
    ----------
    detector_name : str
        PyOD 检测器类名，**大小写敏感**（如 ``"IForest"``、``"LOF"``、
        ``"HBOS"``、``"MatrixProfile"``）。训练模式必填；加载模式下被忽略。
    contamination : float, default 0.1
        期望异常比例（仅训练模式有效）。影响 ``threshold_`` 与 ``labels_``。
    save_name : str, optional
        训练模式下的保存文件名（裸名称，不带 ``.joblib`` 后缀，不带路径
        分隔符）。未指定时自动生成 ``{detector_name}_{timestamp}``。
        加载模式下被忽略。
    return_top_n : int, default 10
        返回分数最高的前 N 行（表格）/ 前 N 个时间点（时序）。
    random_state : int, optional
        训练模式下的随机种子。
    as_time_series : bool, optional
        三态开关：``True`` 强制时序、``False`` 强制表格、``None``（默认）
        按 ``detector_name`` 是否为原生时序检测器自动判断。加载模式下被忽略。
    time_column : str, optional
        时序时间轴列名，仅用于在结果中标注异常发生时间，**不参与建模**。
        未提供时用行号当时间轴。加载模式下以模型 metadata 记录的为准。
    window_size : int, optional
        时序分支的滑窗 / 子序列长度。仅时序分支有效；未提供时用检测器默认值。

    Returns
    -------
    Dict[str, Any]
        ``mode`` 字段标识实际走了哪条分支（``"load"`` 或 ``"train"``），
        ``is_time_series`` 标识是否走了时序分支。``scores`` / ``labels`` /
        ``threshold`` / ``scores_summary`` / ``top_anomalies`` /
        ``feature_columns`` 在两种模式下结构一致，前端 chart 提取逻辑统一
        处理。时序分支额外返回 ``anomaly_intervals`` / ``time_column`` /
        ``n_timestamps`` / ``n_channels`` / ``window_size``（表格时为 None）。
        加载模式额外返回 ``model_metadata`` / ``envelope``；训练模式额外返回
        ``training_scores`` / ``metadata`` / ``n_anomalies``。
    """
    ctx = runtime.context
    # The anomaly agent is an independently invoked inner graph. Its own
    # custom stream is not automatically forwarded by the orchestrator's
    # outer graph, so the outer writer is explicitly carried in context.
    progress = _training_progress_emitter(
        detector_name or "saved detector",
        getattr(ctx, "stream_writer", None),
    )
    df: pd.DataFrame = ctx.df

    # 用户在前端选择的复用模型引用（跨作用域坐标）。None 表示走训练模式。
    msn = getattr(ctx, "model_save_name", None)

    extra_notes: List[str] = []

    # 跨分支共享的局部变量（按 load/train × 时序/表格 分派后填充）。
    info: Optional[Dict[str, Any]] = None       # 表格整形诊断
    ts_info: Optional[Dict[str, Any]] = None    # 时序整形诊断
    time_index: Optional[List[Any]] = None      # 时序时间轴（表格为 None）
    is_ts = False
    window_size_used: Optional[int] = None

    # ==================================================================
    # 模式分派
    # ==================================================================
    if msn:
        # ---------------------- 加载模式 ----------------------
        mode = "load"
        effective_save_name = msn
        # detector_name 从信封里读，忽略 LLM 传入的值
        detector_name_resolved: Optional[str] = None

        model_path = resolve_model_path(msn, runtime)
        if not Path(model_path).exists():
            return {
                "task_type": "anomaly_detection",
                "tool_name": "detect_with_model",
                "mode": mode,
                "is_time_series": False,
                "detector_name": None,
                "summary": "未找到模型文件 %s" % model_path,
                "model_path": str(model_path),
                "save_name": msn,
                "n_samples": 0,
                "n_features": 0,
                "threshold": None,
                "scores": [],
                "labels": [],
                "scores_summary": {"n_total": 0, "n_valid": 0},
                "top_anomalies": [],
                "feature_columns": [],
                "anomaly_intervals": None,
                "time_column": None,
                "n_timestamps": None,
                "n_channels": None,
                "window_size": None,
                "notes": [
                    "请确认前端选择的模型仍然存在；可在「我的模型」中确认。",
                    "该模型可能来自其它会话，若原始文件已被清理，需要重新训练。",
                ],
            }

        model, envelope = persistence.load(
            model_path, strict=False, return_metadata=True)
        saved_meta = (envelope or {}).get("metadata") or {}
        detector_name_resolved = (
            saved_meta.get("detector_name") or type(model).__name__
        )
        supports_ = not is_transductive(detector_name_resolved)

        # 时序 / 表格的整形方式以模型 metadata 的 ``mode`` 为准（加载模式
        # 下忽略 LLM 传入的 as_time_series / window_size）。旧模型没有
        # ``mode`` 字段，一律视为表格。
        saved_mode = saved_meta.get("mode") or "tabular"
        is_ts = (saved_mode == "time_series")
        if is_ts:
            ts_time_column = saved_meta.get("time_column") or time_column
            X, time_index, ts_info = prepare_ts_matrix(runtime, ts_time_column)
            window_size_used = (
                saved_meta.get("window_size")
                if saved_meta.get("window_size") is not None
                else getattr(model, "window_size", None)
            )
        else:
            X, info = prepare_feature_matrix(runtime)

        # 跨作用域来源说明：路径不在当前 artifacts_dir_for 下即跨域。
        try:
            current_scope_dir = artifacts_dir_for(runtime)
            if current_scope_dir != Path(model_path).parent:
                src_dataset = (
                    saved_meta.get("dataset_name")
                    or saved_meta.get("source_file")
                    or None
                )
                try:
                    mtid_seg = Path(model_path).parent.parent.name
                except Exception:
                    mtid_seg = None
                parts = ["已跨会话加载模型"]
                if mtid_seg:
                    parts.append("来自会话 %s" % mtid_seg)
                if src_dataset:
                    parts.append("基于数据集 %s" % src_dataset)
                extra_notes.append("·".join(parts))
        except Exception:
            pass

        # transductive 检测器（如 MatrixProfile）没有对新样本打分的能力，
        # 其 ``decision_scores_`` 只反映训练数据。加载后必须先在当前数据上
        # 重新 fit，否则读到的是原训练集的旧分数（长度都对不上）。
        if is_transductive(detector_name_resolved):
            extra_notes.append(
                "%s 是 transductive 检测器，加载的模型已在当前数据上重新 fit "
                "后打分。" % detector_name_resolved)
            model.fit(X)

        try:
            scores, lbls, th, supports_ = score_with_detector(
                model, X, detector_name_resolved)
        except NotImplementedError:
            extra_notes.append(
                "模型不支持新样本 decision_function，已在当前数据上重新 fit "
                "并读取 decision_scores_。")
            model.fit(X)
            scores = decision_scores_(model)
            th = threshold_(model)
            lbls = labels_(model)
            supports_ = False

        # 列漂移检测：训练时记录的列 vs 当前 DataFrame 实际使用的列。
        used_cols = (ts_info or info or {}).get("used_columns") or []
        saved_cols = list(saved_meta.get("feature_columns") or [])
        if saved_cols and saved_cols != used_cols:
            extra_notes.append(
                "当前输入列与训练时记录的列不一致（训练：%s；当前：%s）。"
                "结果可能不可靠。"
                % (saved_cols, used_cols))

        envelope_summary = {
            k: v for k, v in (envelope or {}).items() if k != "model"
        } if envelope else {}

        result_extra: Dict[str, Any] = {
            "model_metadata": saved_meta,
            "envelope": envelope_summary,
        }

        effective_save_name_for_return = msn
        model_path_for_return = str(model_path)

    else:
        # ---------------------- 训练模式 ----------------------
        mode = "train"
        if not detector_name:
            raise ValueError(
                "训练模式必须提供 detector_name；若想加载已有模型，"
                "请在 CSV 上传卡片的模型选择器中指定。")
        detector_name_resolved = detector_name
        progress("preparing", message="正在准备训练数据与模型参数")

        # 时序 / 表格分流：as_time_series 三态（None=按检测器自动判断）。
        if as_time_series is None:
            is_ts = detector_name in TS_NATIVE_DETECTORS
        else:
            is_ts = bool(as_time_series)
            if (not is_ts) and detector_name in TS_NATIVE_DETECTORS:
                extra_notes.append(
                    "%s 是原生时序检测器，但 as_time_series=False，"
                    "已按表格矩阵运行。" % detector_name)

        # 记录数据集来源（前端模型卡片/选择器展示「基于数据集 X 训练」）
        raw_file_path = getattr(ctx, "file_path", None)
        dataset_name = (
            str(Path(str(raw_file_path)).name) if raw_file_path else None
        )

        effective_save_name = save_name or auto_save_name(detector_name)

        if is_ts:
            # ---------------- 时序分支 ----------------
            X, time_index, ts_info = prepare_ts_matrix(runtime, time_column)
            detector = build_ts_detector(
                detector_name, window_size, None, contamination,
                random_state=random_state)
            setattr(detector, "_progress_callback", progress)
            progress(
                "training",
                current=0,
                total=int(getattr(detector, "epochs", 0) or 0),
                percent=0.0,
                message=f"开始训练 {detector_name}",
            )
            detector.fit(X)
            progress("scoring", message="训练完成，正在计算异常分数")
            scores, lbls, th, supports_ = score_with_detector(
                detector, X, detector_name)
            window_size_used = getattr(detector, "window_size", window_size)

            if detector_name not in TS_NATIVE_DETECTORS:
                extra_notes.append(
                    "%s 不是原生时序检测器，已用 TimeSeriesOD 滑窗桥接"
                    "（window=%r）。" % (detector_name, window_size_used))

            metadata = {
                "detector_name": detector_name,
                "params": {},
                "contamination": contamination,
                "random_state": random_state,
                "window_size": window_size_used,
                "n_timestamps": ts_info["n_timestamps"],
                "n_channels": ts_info["n_channels"],
                "n_samples": ts_info["n_timestamps"],
                "n_features": ts_info["n_channels"],
                "feature_columns": ts_info["used_columns"],
                "source": ts_info["source"],
                "threshold": th,
                "transductive": is_transductive(detector_name),
                "trained_at": datetime.now(timezone.utc).isoformat(),
                "dataset_name": dataset_name,
                "time_column": ts_info["time_column"],
                "mode": "time_series",
            }
        else:
            # ---------------- 表格分支 ----------------
            X, info = prepare_feature_matrix(runtime)
            detector = build_detector_by_name(
                detector_name,
                contamination=contamination,
                random_state=random_state,
            )
            setattr(detector, "_progress_callback", progress)
            progress(
                "training",
                current=0,
                total=int(getattr(detector, "epochs", getattr(detector, "epoch_num", 0)) or 0),
                percent=0.0,
                message=f"开始训练 {detector_name}",
            )
            detector.fit(X)
            progress("scoring", message="训练完成，正在计算异常分数")
            scores = decision_scores_(detector)
            th = threshold_(detector)
            lbls = labels_(detector)
            supports_ = not is_transductive(detector_name)

            metadata = {
                "detector_name": detector_name,
                "params": {},
                "contamination": contamination,
                "random_state": random_state,
                "n_samples": int(X.shape[0]),
                "n_features": int(X.shape[1]),
                "feature_columns": info["used_columns"],
                "source": info["source"],
                "threshold": th,
                "transductive": is_transductive(detector_name),
                "trained_at": datetime.now(timezone.utc).isoformat(),
                "dataset_name": dataset_name,
                "mode": "tabular",
            }

        n_anomalies_train = int((lbls > 0).sum()) if lbls.size else 0
        metadata["n_anomalies"] = n_anomalies_train

        if is_transductive(detector_name):
            extra_notes.append(
                "%s 是 transductive 检测器，加载后不能对新样本 predict。"
                % detector_name)

        model_path = resolve_model_path(effective_save_name, runtime)
        ensure_dir(model_path.parent)
        progress("saving", message="正在保存模型与训练元数据")
        persistence.save(detector, model_path, metadata=metadata)
        model_path_for_return = str(model_path)
        effective_save_name_for_return = effective_save_name

        result_extra = {
            "training_scores": scores_summary(scores, threshold=th, top_n=10),
            "metadata": metadata,
            "n_anomalies": n_anomalies_train,
        }
        progress("completed", percent=100.0, message="模型训练与保存已完成")

    # ==================================================================
    # 通用收尾：top rows / intervals / summary / notes
    # ==================================================================
    if not supports_:
        extra_notes.append("supports_out_of_sample: false")

    summary_stats = scores_summary(scores, threshold=th, top_n=return_top_n)
    n_anomalies_total = int((lbls > 0).sum()) if lbls.size else 0

    if is_ts:
        top_rows = top_ts_anomalies(scores, time_index, th, return_top_n)
        intervals_out = anomaly_intervals(lbls, time_index, th)
        notes_out = format_ts_notes(ts_info, extra_notes)
        n_samples_out = int(ts_info["n_timestamps"])
        n_features_out = int(ts_info["n_channels"])
        feature_columns_out = ts_info["used_columns"]
        summary_text = (
            "[%s模式] %s 时序检测完成：%d 个时间戳，%d 个异常，"
            "%d 个连续异常区间。"
            % (mode, detector_name_resolved, n_samples_out,
               n_anomalies_total, len(intervals_out))
        )
    else:
        top_rows = top_anomaly_rows(
            df, scores, th, return_top_n, columns=info["used_columns"])
        intervals_out = None
        notes_out = format_notes(info, extra_notes)
        n_samples_out = int(X.shape[0])
        n_features_out = int(X.shape[1])
        feature_columns_out = info["used_columns"]
        summary_text = (
            "[%s模式] %s 完成打分：%d 个样本，%d 个异常。"
            % (mode, detector_name_resolved, n_samples_out, n_anomalies_total)
        )

    return limit_anomaly_result({
        "task_type": "anomaly_detection",
        "tool_name": "detect_with_model",
        "mode": mode,
        "is_time_series": is_ts,
        "detector_name": detector_name_resolved,
        "summary": summary_text,
        "model_path": model_path_for_return,
        "save_name": effective_save_name_for_return,
        "n_samples": n_samples_out,
        "n_features": n_features_out,
        "threshold": th,
        "supports_out_of_sample": supports_,
        "scores_summary": summary_stats,
        "labels": lbls.tolist() if lbls.size else [],
        "scores": scores.tolist(),
        "top_anomalies": top_rows,
        "feature_columns": feature_columns_out,
        "notes": notes_out,
        # 时序专属字段（表格模式下均为 None），前端 chart 依此渲染区间高亮。
        "anomaly_intervals": intervals_out,
        "time_column": ts_info["time_column"] if is_ts else None,
        "n_timestamps": int(ts_info["n_timestamps"]) if is_ts else None,
        "n_channels": int(ts_info["n_channels"]) if is_ts else None,
        "window_size": window_size_used if is_ts else None,
        **result_extra,
    })


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
                    # tabular / time_series；旧模型无此字段时为 None。
                    "mode": meta.get("mode"),
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
    # 统一入口：自动判断加载已有模型 / 训练新模型（持久化）+ 打分。
    detect_with_model,
    # 已保存模型的管理（只读枚举 / 删除）。
    list_saved_detectors,
    delete_saved_detector,
    # 归纳式评估（train/test 切分）。
    fit_predict_with_split,
]
