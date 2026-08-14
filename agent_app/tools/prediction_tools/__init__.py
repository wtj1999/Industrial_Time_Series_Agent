"""Prediction tool family.

Drives the upstream time-series foundation-model HTTP service
(``http://10.2.128.43:19053`` and ``http://10.2.128.43:19054``). Seven
models are supported through a uniform call surface::

    sundial              # samples → (batch, horizon, n_samples)
    toto-2               # quantiles → (9, batch, n_variates, horizon)
    timer-s1             # quantiles → (batch, 9, horizon)
    chronos-2            # quantiles → (9, horizon)
    timesfm-2.5          # quantiles → (9, horizon)
    moirai-2.0-R-small   # quantiles → (9, horizon)
    tirex-1.1-gifteval   # quantiles → (9, horizon)

Every model's raw tensor is normalised to a single schema
``{point_forecast, quantiles, samples, shape, model}`` so the agent and
downstream consumers never branch on tensor layout.

Usage::

    from agent_app.tools.prediction_tools import (
        forecast_time_series,
        backtest_forecast,
        list_prediction_models,
        ...
    )

Design principles (mirroring the analysis / anomaly-detection families):

1. **Single source of context.** Tools read only ``ctx.df``,
   ``ctx.target_columns`` and ``ctx.feature_columns``. Everything else
   (model name, ``prediction_length``, ``history_tail``, ``impute``,
   ``endpoint``, ``timeout`` …) is an explicit LLM-supplied argument.
2. **Uniform return shape.** Every tool returns the canonical
   ``prediction`` envelope (see :func:`make_envelope`).
3. **Failure isolation.** HTTP errors, non-success codes and
   shape-mismatched raw payloads are captured per (model, column) and
   surfaced as ``error`` entries rather than aborting the whole call.
"""

from __future__ import annotations

# Shared internal helpers (re-exported for tests / ad-hoc consumers).
from agent_app.tools.prediction_tools._common import (  # noqa: F401
    API_ENDPOINT_1,
    API_ENDPOINT_2,
    AVAILABLE_MODELS,
    DEFAULT_TIMEOUT,
    MAX_SAMPLE_PATHS,
    MODEL_REGISTRY,
    QUANTILE_LEVELS,
    call_predict_api,
    forecast_metrics,
    format_notes,
    get_df,
    get_feature_columns,
    get_target_columns,
    json_safe,
    make_envelope,
    normalize_forecast,
    prepare_series,
    resolve_columns,
    resolve_model,
    round_float,
    select_numeric_columns,
)

# Knowledge / discovery tools.
from agent_app.tools.prediction_tools.knowledge_tools import (  # noqa: F401
    TOOLS as _knowledge_tools,
    explain_prediction_model,
    list_prediction_models,
    recommend_prediction_model,
)

# Forecast tools.
from agent_app.tools.prediction_tools.forecast_tools import (  # noqa: F401
    TOOLS as _forecast_tools,
    forecast_ensemble,
    forecast_multi_models,
    forecast_time_series,
)

# Evaluation / backtest tools.
from agent_app.tools.prediction_tools.evaluation_tools import (  # noqa: F401
    TOOLS as _evaluation_tools,
    backtest_forecast,
    compare_forecast_models_backtest,
)
from agent_app.tools.prediction_tools.finetuning_tools import (  # noqa: F401
    finetune_prediction_model,
)


# Canonical tool list, in the suggested registration order:
#   1) Knowledge (read-only, always cheap)
#   2) Single-model forecast (the workhorse)
#   3) Multi-model / ensemble forecasts
#   4) Evaluation / backtest
TOOLS = [
    # Knowledge
    list_prediction_models,
    explain_prediction_model,
    recommend_prediction_model,
    finetune_prediction_model,

    # Forecast
    forecast_time_series,
    forecast_multi_models,
    forecast_ensemble,

    # Evaluation
    backtest_forecast,
    compare_forecast_models_backtest,
]


__all__ = [
    # Common helpers
    "API_ENDPOINT_1",
    "API_ENDPOINT_2",
    "AVAILABLE_MODELS",
    "DEFAULT_TIMEOUT",
    "MAX_SAMPLE_PATHS",
    "MODEL_REGISTRY",
    "QUANTILE_LEVELS",
    "call_predict_api",
    "forecast_metrics",
    "format_notes",
    "get_df",
    "get_feature_columns",
    "get_target_columns",
    "json_safe",
    "make_envelope",
    "normalize_forecast",
    "prepare_series",
    "resolve_columns",
    "resolve_model",
    "round_float",
    "select_numeric_columns",

    # Canonical list
    "TOOLS",

    # Knowledge
    "list_prediction_models",
    "explain_prediction_model",
    "recommend_prediction_model",
    "finetune_prediction_model",

    # Forecast
    "forecast_time_series",
    "forecast_multi_models",
    "forecast_ensemble",

    # Evaluation
    "backtest_forecast",
    "compare_forecast_models_backtest",
]
