"""Read-only knowledge-base query tools for the PyOD detector family.

These tools never touch ``ctx.df``; they only consult the vendored
PyOD :class:`KnowledgeBase` (algorithms.json, benchmarks.json,
routing_rules.json, papers.json) plus the static ``thresholds`` /
``combination`` registries. They are useful for the LLM to discover which
detectors exist, how they differ, which hyperparameters matter, and
which post-processing methods are available — all before committing to
a training/detection call.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from langchain.tools import ToolRuntime, tool

from agent_app.tools._tool_guard import tool_guard
from agent_app.tools.anomaly_detection_tools._common import (
    get_knowledge_base,
    is_transductive,
)

logger = logging.getLogger(__name__)


# Canonical modality order used when no filter is supplied so the LLM
# gets a stable, human-readable grouping. Built dynamically from the KB.
_ALL_DATA_TYPES = ["tabular", "time_series", "graph", "image", "audio",
                   "text", "multimodal"]


# Registry of advanced threshold methods exposed by
# ``pyod.models.thresholds`` (delegating to the ``pythresh`` package).
# Each entry: name -> short description. The list is hand-curated to the
# methods we expect the LLM to reason about; the threshold tool itself
# imports them lazily.
_THRESHOLD_METHODS: Dict[str, str] = {
    "ZSCORE": "Z-score based thresholding",
    "MAD": "Median Absolute Deviation",
    "IQR": "Inter-Quartile Range",
    "CHAU": "Chauvenon's criterion",
    "HIST": "Histogram-based thresholding",
    "BOOT": "Bootstrapping confidence intervals",
    "GESD": "Generalized Extreme Studentized Deviate",
    "MTT": "Modified Thompson Tau test",
    "MAD": "Median Absolute Deviation",
    "MCST": "Monte Carlo Shapiro Tests",
    "EB": "Elliptical Boundary",
    "MOLL": "Friedrichs' mollifier",
    "KARCH": "Riemannian Center of Mass",
    "OCSVM": "One-Class SVM thresholding",
    "VAE": "Variational AutoEncoder thresholding",
    "CLUST": "Clustering-based (kmeans, dbscan, optics, ...)",
    "CPD": "Change Point Detection",
    "DECOMP": "Decomposition (NMF, PCA, GRP, SRP)",
    "DSN": "Distance Shift from Normal",
    "FILTER": "Filtering methods",
    "FWFM": "Fractional Weighted Fractional Maximization",
    "GAMGMM": "Bayesian contamination estimation",
    "META": "Meta-modelling",
    "MIXMOD": "Mixture Models (normal & non-normal)",
    "QMCD": "Quasi-Monte Carlo Discrepancy",
    "REGR": "Regression (siegel/theil)",
    "AUCP": "Area Under Curve Percentage",
    "WIND": "Topological winding number",
    "YJ": "Yeo-Johnson transformation",
    "CLF": "Trained linear Classifier",
    "FGD": "Fixed Gradient Descent",
}

# Combination strategies from ``pyod.models.combination``.
_COMBINATION_METHODS: Dict[str, str] = {
    "average": "Simple arithmetic mean of detector scores",
    "maximization": "Take the maximum score across detectors",
    "median": "Median of detector scores (robust to outliers)",
    "majority_vote": "Binary majority vote on per-detector labels",
    "aom": "Average of Maximum — group detectors into buckets, take max in each, then average",
    "moa": "Maximization of Average — group detectors into buckets, take average in each, then max",
}


def _algo_summary(name: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten one KB entry into the compact summary returned by listing tools."""
    return {
        "name": name,
        "type": entry.get("category"),
        "class_path": entry.get("class_path"),
        "data_types": list(entry.get("data_types", [])),
        "status": entry.get("status"),
        "full_name": entry.get("full_name"),
        "best_for": entry.get("best_for"),
        "complexity": entry.get("complexity"),
        "default_params": dict(entry.get("default_params", {})),
        "transductive": is_transductive(name),
    }


# ----------------------------------------------------------------------
# Tools
# ----------------------------------------------------------------------

@tool("list_pyod_detectors")
@tool_guard("list_pyod_detectors")
def list_pyod_detectors(
    runtime: ToolRuntime,
    data_type: Optional[str] = None,
    status: str = "shipped",
) -> Dict[str, Any]:
    """列出 PyOD 内置的异常检测器，可按数据模态和状态过滤。

    用于回答「PyOD 有哪些检测器」「时序场景有哪些可用算法」「实验性
    检测器有哪些」等问题。返回每个检测器的精简元数据（名称、类型、
    模态、状态、默认参数、是否 transductive）。

    Parameters
    ----------
    data_type : str, optional
        数据模态过滤。常见取值：``"tabular"``、``"time_series"``、
        ``"graph"``、``"audio"``、``"image"``、``"text"``、
        ``"multimodal"``。``None`` 表示不过滤。
    status : str, default ``"shipped"``
        状态过滤：``"shipped"``（默认，推荐使用）、``"experimental"``、
        ``"planned"`` 或 ``"all"``（返回所有状态）。

    Returns
    -------
    Dict[str, Any]
        ``detectors`` 为精简条目列表；``counts`` 给出按模态和状态的
        分组计数，便于在回复中做一句话总结。
    """
    kb = get_knowledge_base()
    algorithms = kb.algorithms

    entries: List[Dict[str, Any]] = []
    for name, entry in algorithms.items():
        if data_type is not None and data_type not in entry.get("data_types", []):
            continue
        if status != "all" and entry.get("status") != status:
            continue
        entries.append(_algo_summary(name, entry))

    entries.sort(key=lambda e: (",".join(e["data_types"]), e["name"]))

    by_modality: Dict[str, int] = {dt: 0 for dt in _ALL_DATA_TYPES}
    by_status: Dict[str, int] = {}
    for e in entries:
        for dt in e["data_types"]:
            by_modality[dt] = by_modality.get(dt, 0) + 1
        st = e["status"] or "unknown"
        by_status[st] = by_status.get(st, 0) + 1

    return {
        "task_type": "anomaly_detection",
        "tool_name": "list_pyod_detectors",
        "summary": (
            "共 %d 个检测器（filter: data_type=%s, status=%s）。"
            % (len(entries), data_type, status)
        ),
        "detectors": entries,
        "counts": {"by_modality": by_modality, "by_status": by_status},
        "notes": [],
    }


@tool("explain_pyod_detector")
@tool_guard("explain_pyod_detector")
def explain_pyod_detector(
    detector_name: str,
    runtime: ToolRuntime,
) -> Dict[str, Any]:
    """返回单个 PyOD 检测器的完整元数据，辅助参数选择与原理理解。

    包括类别、原理（strengths/weaknesses/best_for/avoid_when）、复杂度、
    默认参数、数据类型、benchmark 排名、论文引用、示例用法。当用户问
    「IForest 是什么」「LOF 的关键超参数是什么」时调用本工具。

    Parameters
    ----------
    detector_name : str
        检测器名称（大小写敏感），例如 ``"IForest"``、``"LOF"``、
        ``"MatrixProfile"``。

    Returns
    -------
    Dict[str, Any]
        ``metadata`` 为 KB 中该检测器的完整条目；``example_usage`` 是
        可直接复制运行的 Python 片段。
    """
    kb = get_knowledge_base()
    entry = kb.get_algorithm(detector_name)
    if entry is None:
        return {
            "task_type": "anomaly_detection",
            "tool_name": "explain_pyod_detector",
            "summary": "未找到检测器 '%s'。" % detector_name,
            "metadata": None,
            "notes": [
                "可用 list_pyod_detectors 查看全部检测器名称。"
            ],
        }

    class_path = entry.get("class_path", "")
    module_path = class_path.rsplit(".", 1)[0] if "." in class_path else ""
    class_name = class_path.rsplit(".", 1)[1] if "." in class_path else detector_name

    example = (
        "from %s import %s\n"
        "clf = %s(%s)\n"
        "clf.fit(X)\n"
        "scores = clf.decision_scores_   # 训练集分数\n"
        "labels = clf.labels_            # 0/1 二值标签\n"
        "threshold = clf.threshold_      # 由 contamination 推导的阈值"
        % (
            module_path,
            class_name,
            class_name,
            ", ".join(
                "%s=%r" % (k, v)
                for k, v in (entry.get("default_params") or {}).items()
            ),
        )
    )

    paper_ref = entry.get("paper") or {}
    notes: List[str] = []
    if is_transductive(detector_name):
        notes.append(
            "%s 是 transductive 检测器：只对训练数据打分，不支持对新样本 "
            "predict/decision_function。" % detector_name)

    summary = "%s (%s) — %s" % (
        detector_name,
        entry.get("full_name", ""),
        entry.get("best_for", ""),
    )

    return {
        "task_type": "anomaly_detection",
        "tool_name": "explain_pyod_detector",
        "detector_name": detector_name,
        "summary": summary,
        "metadata": {
            "name": detector_name,
            **entry,
            "transductive": is_transductive(detector_name),
        },
        "paper": paper_ref,
        "example_usage": example,
        "notes": notes,
    }


@tool("compare_pyod_detectors")
@tool_guard("compare_pyod_detectors")
def compare_pyod_detectors(
    detector_names: List[str],
    runtime: ToolRuntime,
) -> Dict[str, Any]:
    """横向对比多个 PyOD 检测器，输出对比表与差异提示。

    适合回答「IForest 和 LOF 哪个更适合」「KShape 与 MatrixProfile 的
    区别」这类问题。对比维度包括类别、时间/空间复杂度、数据类型、
    benchmark 排名、是否 transductive、是否需要标签、关键超参数、
    训练成本。

    Parameters
    ----------
    detector_names : List[str]
        待对比的检测器名称列表（至少 2 个）。

    Returns
    -------
    Dict[str, Any]
        ``table`` 为逐检测器对比条目列表；``shared_data_types`` 给出
        所有检测器共同支持的模态；``notes`` 包含差异提示。
    """
    if not detector_names or len(detector_names) < 2:
        return {
            "task_type": "anomaly_detection",
            "tool_name": "compare_pyod_detectors",
            "summary": "compare_pyod_detectors 至少需要 2 个检测器名称。",
            "table": [],
            "notes": ["请提供至少 2 个 detector_name，例如 ['IForest','LOF']。"],
        }

    kb = get_knowledge_base()
    rows: List[Dict[str, Any]] = []
    missing: List[str] = []
    for name in detector_names:
        entry = kb.get_algorithm(name)
        if entry is None:
            missing.append(name)
            continue
        rows.append({
            "name": name,
            "type": entry.get("category"),
            "complexity": entry.get("complexity"),
            "data_types": entry.get("data_types", []),
            "best_for": entry.get("best_for"),
            "avoid_when": entry.get("avoid_when"),
            "benchmark_rank": entry.get("benchmark_rank", {}),
            "default_params": entry.get("default_params", {}),
            "transductive": is_transductive(name),
            "needs_labels": name in {"XGBOD", "DevNet"},  # supervised-aware
            "training_cost": _training_cost_hint(entry),
        })

    shared = None
    if rows:
        sets = [set(r["data_types"]) for r in rows]
        shared = sorted(set.intersection(*sets))

    notes: List[str] = []
    if missing:
        notes.append("KB 中找不到以下检测器：%s" % ", ".join(missing))
    if shared is not None and not shared:
        notes.append("这些检测器没有共同的数据模态，输入数据类型需分别准备。")
    transductive = [r["name"] for r in rows if r["transductive"]]
    if transductive:
        notes.append(
            "transductive 检测器（%s）不支持对新样本预测，"
            "只能对训练数据打分。" % ", ".join(transductive))

    return {
        "task_type": "anomaly_detection",
        "tool_name": "compare_pyod_detectors",
        "summary": "已对比 %d 个检测器。" % len(rows),
        "table": rows,
        "shared_data_types": shared,
        "notes": notes,
    }


@tool("list_threshold_methods")
@tool_guard("list_threshold_methods")
def list_threshold_methods(runtime: ToolRuntime) -> Dict[str, Any]:
    """列出 PyOD/``pythresh`` 暴露的高级阈值方法。

    当默认的 ``contamination`` 百分位切分不够好时，可以用这些方法
    重新对检测器分数做阈值化。返回方法名、简介。

    Returns
    -------
    Dict[str, Any]
        ``methods`` 是 ``{name: description}`` 字典。
    """
    return {
        "task_type": "anomaly_detection",
        "tool_name": "list_threshold_methods",
        "summary": "共 %d 个阈值方法。" % len(_THRESHOLD_METHODS),
        "methods": dict(sorted(_THRESHOLD_METHODS.items())),
        "notes": [
            "在 apply_threshold_method 中通过 ``method`` 参数指定名称。"
        ],
    }


@tool("list_combination_methods")
@tool_guard("list_combination_methods")
def list_combination_methods(runtime: ToolRuntime) -> Dict[str, Any]:
    """列出多检测器分数组合（ensemble combination）策略。

    用于回答「多个检测器的分数如何融合」「AOM/MOA 是什么」等问题。
    与 :func:`combine_detector_scores` 工具一一对应。

    Returns
    -------
    Dict[str, Any]
        ``methods`` 是 ``{name: description}`` 字典。
    """
    return {
        "task_type": "anomaly_detection",
        "tool_name": "list_combination_methods",
        "summary": "共 %d 个组合策略。" % len(_COMBINATION_METHODS),
        "methods": dict(sorted(_COMBINATION_METHODS.items())),
        "notes": [
            "average / maximization / median / majority_vote 适合任意数量检测器；",
            "aom / moa 适合 >=5 个检测器（n_buckets 默认 5）。",
        ],
    }


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _training_cost_hint(entry: Dict[str, Any]) -> str:
    """Coarse human-readable hint at training cost."""
    name = (entry.get("class_path") or "").rsplit(".", 1)[-1].lower()
    complexity = (entry.get("complexity") or {})
    time_c = str(complexity.get("time", "")).lower()
    if any(k in name for k in ("lstm", "anomalytransformer", "devnet",
                               "autoencoder", "vae", "alad", "anogan",
                               "deepsvdd", "ae1svm", "dif", "lunar")):
        return "high (deep learning; CPU slow, GPU recommended)"
    if "n^2" in time_c or "n^3" in time_c:
        return "medium-high (quadratic or worse)"
    if "n *" in time_c or "n log" in time_c or "n)" in time_c:
        return "low (near-linear)"
    return "unknown"


TOOLS = [
    list_pyod_detectors,
    explain_pyod_detector,
    compare_pyod_detectors,
    list_threshold_methods,
    list_combination_methods,
]
