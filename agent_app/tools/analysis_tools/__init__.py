"""Analysis tool family.

A modular re-design of the original monolithic ``analysis_tools.py``.
Each category of analysis lives in its own module so imports stay
clean::

    from agent_app.tools.analysis_tools import (
        analyze_basic_statistics,
        analyze_linear_trend,
        analyze_correlation_matrix,
        detect_mean_change_points,
        ...
    )

Design principles
-----------------
1. **Single source of context.** Every tool reads only three fields from
   the injected :class:`AnalysisContext`::

       ctx.df                # pandas.DataFrame
       ctx.target_columns    # List[str]
       ctx.feature_columns   # List[str]

2. **LLM-driven parameters.** Anything that isn't one of those three
   (window sizes, method names, thresholds, ``time_column``,
   ``group_column``, spec limits, …) is passed as a direct tool
   argument that the LLM fills in after reasoning about ``task_spec``.

3. **Uniform return shape.** Every tool returns::

       {
         "task_type": "analysis",
         "tool_name": <short tag>,
         "summary": str,
         "key_findings": List[str],
         "metrics": Dict[str, Any],
         "recommendations": List[str],
         "notes": List[str],
       }

4. **Granular, composable tools.** Each tool answers one well-scoped
   question. The agent is encouraged to call several in sequence to
   cover a multi-faceted analytical question.
"""

from __future__ import annotations

# Shared internal helpers (re-exported for tests / ad-hoc consumers).
from agent_app.tools.analysis_tools._common import (  # noqa: F401
    bootstrap_ci,
    format_notes,
    get_df,
    get_feature_columns,
    get_target_columns,
    json_safe,
    linear_slope,
    make_envelope,
    numeric_frame,
    numeric_series,
    resolve_columns,
    resolve_group_column,
    resolve_time_column,
    round_float,
    select_numeric_columns,
    truncate_list,
)

# ----------------------------------------------------------------------
# Distribution / shape
# ----------------------------------------------------------------------
from agent_app.tools.analysis_tools.distribution_tools import (  # noqa: F401
    TOOLS as _distribution_tools,
    analyze_basic_statistics,
    analyze_distribution_shape,
    analyze_histogram,
)

# ----------------------------------------------------------------------
# Trend
# ----------------------------------------------------------------------
from agent_app.tools.analysis_tools.trend_tools import (  # noqa: F401
    TOOLS as _trend_tools,
    analyze_linear_trend,
    analyze_mann_kendall_trend,
    analyze_rolling_trend,
)

# ----------------------------------------------------------------------
# Correlation / relationships
# ----------------------------------------------------------------------
from agent_app.tools.analysis_tools.correlation_tools import (  # noqa: F401
    TOOLS as _correlation_tools,
    analyze_correlation_matrix,
    analyze_cross_correlation,
    analyze_mutual_information,
)

# ----------------------------------------------------------------------
# Time-series specific
# ----------------------------------------------------------------------
from agent_app.tools.analysis_tools.time_series_tools import (  # noqa: F401
    TOOLS as _ts_tools,
    analyze_autocorrelation,
    analyze_seasonality,
    analyze_stationarity,
    decompose_time_series,
)

# ----------------------------------------------------------------------
# Change-point detection
# ----------------------------------------------------------------------
from agent_app.tools.analysis_tools.change_point_tools import (  # noqa: F401
    TOOLS as _change_point_tools,
    detect_cusum_change,
    detect_mean_change_points,
    detect_variance_change,
)

# ----------------------------------------------------------------------
# Outliers
# ----------------------------------------------------------------------
from agent_app.tools.analysis_tools.outlier_tools import (  # noqa: F401
    TOOLS as _outlier_tools,
    analyze_extreme_values,
    detect_multivariate_outliers,
    detect_univariate_outliers,
)

# ----------------------------------------------------------------------
# Stability / SPC
# ----------------------------------------------------------------------
from agent_app.tools.analysis_tools.stability_tools import (  # noqa: F401
    TOOLS as _stability_tools,
    analyze_control_chart,
    analyze_process_capability,
    analyze_stability,
)

# ----------------------------------------------------------------------
# Group comparison
# ----------------------------------------------------------------------
from agent_app.tools.analysis_tools.comparison_tools import (  # noqa: F401
    TOOLS as _comparison_tools,
    compare_group_distributions,
    compare_group_statistics,
    compare_two_groups,
)

# ----------------------------------------------------------------------
# Data quality
# ----------------------------------------------------------------------
from agent_app.tools.analysis_tools.quality_tools import (  # noqa: F401
    TOOLS as _quality_tools,
    analyze_constant_or_low_variance_columns,
    analyze_duplicates,
    analyze_missing_values,
)


# Canonical tool list, in the suggested registration order:
#   1) Quality (always run first to know what's usable)
#   2) Distribution (basic description)
#   3) Trend
#   4) Correlation / relationships
#   5) Time-series (ACF / seasonality / decomposition / stationarity)
#   6) Change-point
#   7) Outliers
#   8) Stability / SPC
#   9) Group comparison
TOOLS = [
    # Quality
    analyze_missing_values,
    analyze_duplicates,
    analyze_constant_or_low_variance_columns,

    # Distribution
    analyze_basic_statistics,
    analyze_distribution_shape,
    analyze_histogram,

    # Trend
    analyze_linear_trend,
    analyze_mann_kendall_trend,
    analyze_rolling_trend,

    # Correlation / relationships
    analyze_correlation_matrix,
    analyze_cross_correlation,
    analyze_mutual_information,

    # Time-series
    analyze_autocorrelation,
    analyze_seasonality,
    decompose_time_series,
    analyze_stationarity,

    # Change-point
    detect_mean_change_points,
    detect_variance_change,
    detect_cusum_change,

    # Outliers
    detect_univariate_outliers,
    detect_multivariate_outliers,
    analyze_extreme_values,

    # Stability / SPC
    analyze_stability,
    analyze_process_capability,
    analyze_control_chart,

    # Group comparison
    compare_group_statistics,
    compare_group_distributions,
    compare_two_groups,
]


__all__ = [
    # Common helpers
    "bootstrap_ci",
    "format_notes",
    "get_df",
    "get_feature_columns",
    "get_target_columns",
    "json_safe",
    "linear_slope",
    "make_envelope",
    "numeric_frame",
    "numeric_series",
    "resolve_columns",
    "resolve_group_column",
    "resolve_time_column",
    "round_float",
    "select_numeric_columns",
    "truncate_list",

    # Canonical list
    "TOOLS",

    # Distribution
    "analyze_basic_statistics",
    "analyze_distribution_shape",
    "analyze_histogram",

    # Trend
    "analyze_linear_trend",
    "analyze_mann_kendall_trend",
    "analyze_rolling_trend",

    # Correlation
    "analyze_correlation_matrix",
    "analyze_cross_correlation",
    "analyze_mutual_information",

    # Time-series
    "analyze_autocorrelation",
    "analyze_seasonality",
    "decompose_time_series",
    "analyze_stationarity",

    # Change-point
    "detect_mean_change_points",
    "detect_variance_change",
    "detect_cusum_change",

    # Outliers
    "detect_univariate_outliers",
    "detect_multivariate_outliers",
    "analyze_extreme_values",

    # Stability / SPC
    "analyze_stability",
    "analyze_process_capability",
    "analyze_control_chart",

    # Group comparison
    "compare_group_statistics",
    "compare_group_distributions",
    "compare_two_groups",

    # Quality
    "analyze_missing_values",
    "analyze_duplicates",
    "analyze_constant_or_low_variance_columns",
]
