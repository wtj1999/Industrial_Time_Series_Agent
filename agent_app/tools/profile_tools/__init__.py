"""Profile tool family.

A modular re-design of the original monolithic ``profile_tools.py``.
Mirrors the layout of :mod:`agent_app.tools.analysis_tools`::

    from tools.profile_tools import (
        get_basic_info,
        analyze_column_tool,
        TOOLS,
    )

Design principles
-----------------
1. **Single source of context.** Every tool reads only ``ctx.df`` from
   the injected ``ProfileContext``.

2. **Schema-only structured output.** Anything returned in the final
   CSVProfile must be a field of :class:`ColumnInfo` /
   :class:`CSVProfile`. Auxiliary hints (sample values, candidate
   flags, anomaly indicators) are surfaced in the tool's free-text
   response to help the LLM reason, but they MUST NOT appear in the
   structured output.

3. **Granular tools.** Each tool answers one well-scoped question:
   - :func:`get_basic_info` — overall structure
   - :func:`analyze_column_tool` — per-column detail
"""

from __future__ import annotations

# Tools
from agent_app.tools.profile_tools.basic_info_tools import get_basic_info  # noqa: F401
from agent_app.tools.profile_tools.column_analysis_tools import analyze_column_tool  # noqa: F401

# Internal helpers (re-exported for tests / ad-hoc consumers).
from agent_app.tools.profile_tools._common import (  # noqa: F401
    analyze_column_info,
    compute_distribution_stats,
    detect_column_anomalies,
    detect_column_type,
    get_column_hints,
    get_df,
    get_sample_values,
    is_grouping_column_candidate,
    is_target_column_candidate,
    is_time_column_candidate,
)


# Canonical tool list, in the suggested call order:
#   1) get_basic_info    — overall structure
#   2) analyze_column    — one call per column
TOOLS = [
    get_basic_info,
    analyze_column_tool,
]


__all__ = [
    # Tools
    "get_basic_info",
    "analyze_column_tool",
    "TOOLS",

    # Internal helpers
    "analyze_column_info",
    "compute_distribution_stats",
    "detect_column_anomalies",
    "detect_column_type",
    "get_column_hints",
    "get_df",
    "get_sample_values",
    "is_grouping_column_candidate",
    "is_target_column_candidate",
    "is_time_column_candidate",
]
