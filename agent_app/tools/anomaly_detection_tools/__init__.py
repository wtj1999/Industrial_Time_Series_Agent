"""Anomaly-detection tool family.

A refactored superset of the original ``detector_*_tools`` modules.
Everything is grouped under this package so imports stay clean::

    from agent_app.tools.anomaly_detection_tools import (
        detect_with_model,
        list_pyod_detectors,
        ...
    )

The persistence layout is deterministic: every saved model lives under

    artifacts/anomaly_detection/<user_id>/<thread_id>/<file_stem>_anomaly_detection/

so the LLM never needs to (and cannot) invent a path — it only supplies
a bare ``save_name`` (e.g. ``"iforest_v1"``).
"""

from __future__ import annotations

# Shared internal helpers (re-exported for tests and ad-hoc consumers).
from agent_app.tools.anomaly_detection_tools._common import (  # noqa: F401
    ARTIFACTS_ROOT,
    artifacts_dir_for,
    build_detector_by_name,
    ensure_dir,
    get_knowledge_base,
    is_transductive,
    prepare_feature_matrix,
    resolve_model_path,
    scores_summary,
)

# Knowledge / discovery tools.
from agent_app.tools.anomaly_detection_tools.knowledge_tools import (  # noqa: F401
    TOOLS as _knowledge_tools,
    compare_pyod_detectors,
    explain_pyod_detector,
    list_combination_methods,
    list_pyod_detectors,
    list_threshold_methods,
)

# Detect / train / persist tools.
from agent_app.tools.anomaly_detection_tools.train_predict_tools import (  # noqa: F401
    TOOLS as _train_predict_tools,
    delete_saved_detector,
    detect_with_model,
    fit_predict_with_split,
    list_saved_detectors,
)

# Evaluation tools.
from agent_app.tools.anomaly_detection_tools.evaluation_tools import (  # noqa: F401
    TOOLS as _evaluation_tools,
    compare_detection_results,
    evaluate_detection,
)

# Ensemble / score-combination tools.
from agent_app.tools.anomaly_detection_tools.ensemble_tools import (  # noqa: F401
    TOOLS as _ensemble_tools,
    combine_detector_scores,
    train_ensemble_detector,
)

# Threshold tools.
from agent_app.tools.anomaly_detection_tools.threshold_tools import (  # noqa: F401
    TOOLS as _threshold_tools,
    apply_threshold_method,
)

# Explainability tools.
from agent_app.tools.anomaly_detection_tools.explainability_tools import (  # noqa: F401
    TOOLS as _explainability_tools,
    compute_feature_importance,
    explain_anomalies,
)

# Auto-pipeline tools.
from agent_app.tools.anomaly_detection_tools.auto_detection_tools import (  # noqa: F401
    TOOLS as _auto_tools,
    auto_detect_anomalies,
    recommend_detectors,
)


# The canonical tool list, in the order the agent should register them.
TOOLS = [
    # Knowledge / discovery (read-only).
    list_pyod_detectors,
    explain_pyod_detector,
    compare_pyod_detectors,
    list_threshold_methods,
    list_combination_methods,
    recommend_detectors,

    # Detect / train / persist.
    detect_with_model,
    list_saved_detectors,
    delete_saved_detector,
    fit_predict_with_split,

    # Evaluation.
    evaluate_detection,
    compare_detection_results,

    # Ensemble.
    combine_detector_scores,
    train_ensemble_detector,

    # Threshold.
    apply_threshold_method,

    # Explainability.
    explain_anomalies,
    compute_feature_importance,

    # Auto pipeline (highest-level entry point).
    auto_detect_anomalies,
]


__all__ = [
    # Common helpers
    "ARTIFACTS_ROOT",
    "artifacts_dir_for",
    "build_detector_by_name",
    "ensure_dir",
    "get_knowledge_base",
    "is_transductive",
    "prepare_feature_matrix",
    "resolve_model_path",
    "scores_summary",

    # Tools
    "TOOLS",
    # Knowledge
    "list_pyod_detectors",
    "explain_pyod_detector",
    "compare_pyod_detectors",
    "list_threshold_methods",
    "list_combination_methods",
    "recommend_detectors",
    # Detect / train / persist
    "detect_with_model",
    "list_saved_detectors",
    "delete_saved_detector",
    "fit_predict_with_split",
    # Evaluation
    "evaluate_detection",
    "compare_detection_results",
    # Ensemble
    "combine_detector_scores",
    "train_ensemble_detector",
    # Threshold
    "apply_threshold_method",
    # Explainability
    "explain_anomalies",
    "compute_feature_importance",
    # Auto
    "auto_detect_anomalies",
]
