"""Advanced thresholding tools built on ``pyod.models.thresholds``.

The default ``contamination``-percentile cut can be replaced by any of
the ~30 methods exposed by the ``pythresh`` package (ZSCORE, MAD, IQR,
CLUST, OCSVM, ...). :func:`apply_threshold_method` runs a detector (or
reuses a saved one) and re-thresholds its decision scores with the
chosen method, returning a new label/threshold pair without retraining.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
from langchain.tools import ToolRuntime, tool

from agent_app.tools._tool_guard import tool_guard
from agent_app.tools.anomaly_detection_tools._common import (
    build_detector_by_name,
    format_notes,
    prepare_feature_matrix,
    resolve_model_path,
    scores_summary,
    top_anomaly_rows,
)
from agent_app.tools.outlier_detection_scripts.pyod.models import thresholds as th_module
from agent_app.tools.outlier_detection_scripts.pyod.utils import persistence

logger = logging.getLogger(__name__)


# Subset of threshold method names we expose to the LLM. The full list
# is dynamically queryable via list_threshold_methods; we restrict to
# those that are well-tested and don't need extra dependencies beyond
# what the vendored pythresh package already pulls in.
_SUPPORTED_METHODS = {
    "ZSCORE", "MAD", "IQR", "CHAU", "HIST", "BOOT", "GESD", "MTT",
    "MCST", "EB", "MOLL", "KARCH", "OCSVM", "VAE", "CLUST", "CPD",
    "DECOMP", "DSN", "FILTER", "FWFM", "GAMGMM", "META", "MIXMOD",
    "QMCD", "REGR", "AUCP", "WIND", "YJ", "CLF", "FGD",
}


def _resolve_labels_from_method(method_name: str, scores: np.ndarray) -> np.ndarray:
    """Build a thresholder and ask it for binary labels on ``scores``.

    All ``pythresh`` thresholders expose ``.eval(scores)`` returning a
    0/1 ndarray (1 = anomaly). The factory functions in
    ``pyod.models.thresholds`` take arbitrary kwargs and forward them.
    """
    if method_name not in _SUPPORTED_METHODS:
        raise ValueError(
            "Unsupported threshold method %r. Call list_threshold_methods "
            "to enumerate available names." % method_name)
    factory = getattr(th_module, method_name, None)
    if factory is None:
        raise ValueError(
            "Method %r is registered but not importable from pyod.models."
            "thresholds." % method_name)
    thresholder = factory()
    # pythresh thresholders expose ``eval`` (newer) or ``__call__``.
    if hasattr(thresholder, "eval"):
        labels = thresholder.eval(scores)
    else:  # pragma: no cover - legacy fallback
        labels = thresholder(scores)
    labels = np.asarray(labels, dtype=int).ravel()
    # Defensive: force to {0, 1}.
    labels = (labels != 0).astype(int)
    return labels


def _derive_threshold_from_labels(scores: np.ndarray, labels: np.ndarray) -> Optional[float]:
    """Pick the smallest score flagged anomalous as the new threshold."""
    scores = np.asarray(scores, dtype=float).ravel()
    labels = np.asarray(labels, dtype=int).ravel()
    if labels.size == 0 or labels.sum() == 0:
        return None
    flagged = scores[labels > 0]
    if flagged.size == 0:
        return None
    return float(np.min(flagged))


# ----------------------------------------------------------------------
# Tools
# ----------------------------------------------------------------------

@tool("apply_threshold_method")
@tool_guard("apply_threshold_method")
def apply_threshold_method(
    detector_name: str,
    method: str,
    runtime: ToolRuntime,
    contamination: float = 0.1,
    save_name: Optional[str] = None,
    return_top_n: int = 10,
    random_state: Optional[int] = None,
) -> Dict[str, Any]:
    """用一个检测器生成分数，再用高级阈值方法重新二值化。

    与默认的 ``contamination`` 百分位不同，这里用 ``pythresh`` 的阈值
    方法（``ZSCORE`` / ``MAD`` / ``IQR`` / ``CLUST`` / ``OCSVM`` ...）
    去推断分数分布的「自然断点」，常用于：

    - 无标签但想得到更稳健的二值切分；
    - 默认阈值偏敏感或偏保守时尝试不同假设；
    - 给已有检测器做「阈值敏感性」分析。

    Parameters
    ----------
    detector_name : str
        任意 PyOD 检测器名称。
    method : str
        阈值方法名称（大小写敏感），可通过 ``list_threshold_methods``
        查看完整清单。
    contamination : float, default 0.1
        仅用于检测器 fit；阈值方法自身通常忽略该值。
    save_name : str, optional
        如提供，把「检测器分数 + 阈值方法标签」缓存到当前作用域，
        方便后续对比。模型体仍是检测器本身。
    return_top_n : int, default 10
        返回 Top-N 异常行（含原始值）。
    random_state : int, optional
        随机种子。

    Returns
    -------
    Dict[str, Any]
        ``labels`` 是按阈值方法重算的二值标签；``threshold`` 是从标签
        反推的最小异常分数；``scores_summary`` 为原始分数统计。
    """
    ctx = runtime.context
    df = ctx.df
    X, info = prepare_feature_matrix(runtime)

    detector = build_detector_by_name(
        detector_name,
        contamination=contamination, random_state=random_state)
    detector.fit(X)

    scores = getattr(detector, "decision_scores_", None)
    if scores is None:
        raise RuntimeError(
            "Detector %r has no decision_scores_ after fit."
            % type(detector).__name__)
    scores = np.asarray(scores, dtype=float).ravel()

    try:
        labels = _resolve_labels_from_method(method, scores)
        notes_extra: List[str] = []
    except Exception as exc:
        return {
            "task_type": "anomaly_detection",
            "tool_name": "apply_threshold_method",
            "summary": "阈值方法 %s 执行失败：%s" % (method, exc),
            "detector_name": detector_name,
            "method": method,
            "notes": format_notes(info, [
                "可改用 list_threshold_methods 中的其他方法。"]),
        }

    derived_th = _derive_threshold_from_labels(scores, labels)
    top_rows = top_anomaly_rows(
        df, scores, derived_th, return_top_n, columns=info["used_columns"])
    summary_stats = scores_summary(scores, threshold=derived_th, top_n=return_top_n)

    model_path = None
    if save_name:
        from agent_app.tools.anomaly_detection_tools._common import (
            auto_save_name, ensure_dir,
        )
        if save_name is None:
            save_name = auto_save_name(detector_name)
        model_path = resolve_model_path(save_name, runtime)
        ensure_dir(model_path.parent)
        metadata = {
            "detector_name": detector_name,
            "method": method,
            "params": {},
            "contamination": contamination,
            "n_samples": int(X.shape[0]),
            "n_features": int(X.shape[1]),
            "feature_columns": info["used_columns"],
            "threshold": derived_th,
            "n_anomalies": int(labels.sum()),
            "threshold_mode": method,
        }
        persistence.save(detector, model_path, metadata=metadata)

    return {
        "task_type": "anomaly_detection",
        "tool_name": "apply_threshold_method",
        "detector_name": detector_name,
        "method": method,
        "summary": (
            "%s + %s 完成：%d 个样本，%d 个被判为异常。"
            % (detector_name, method, X.shape[0], int(labels.sum()))
        ),
        "n_samples": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "threshold": derived_th,
        "labels": labels.tolist(),
        "scores": scores.tolist(),
        "scores_summary": summary_stats,
        "top_anomalies": top_rows,
        "model_path": str(model_path) if model_path else None,
        "save_name": save_name if model_path else None,
        "notes": format_notes(info, notes_extra),
    }


TOOLS = [
    apply_threshold_method,
]
