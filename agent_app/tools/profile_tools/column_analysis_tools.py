"""Per-column analysis tool."""

from __future__ import annotations

from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from agent_app.tools._tool_guard import tool_guard
from agent_app.tools.profile_tools._common import (
    analyze_column_info,
    get_column_hints,
    get_df,
)


@tool("analyze_column")
@tool_guard("analyze_column", return_type="str")
def analyze_column_tool(
    column_name: str,
    runtime: ToolRuntime,
) -> str:
    """分析指定列的详细信息。

    输入：
    - column_name：需要分析的列名

    返回的 schema 字段（这些会进入最终 CSVProfile）：
    - 字段类型（ColumnType 枚举值）
    - 缺失率
    - 唯一值数量
    - 数值列的分布统计（mean / std / min / max / median / q25 / q75）

    返回的辅助判断信息（仅供你做归类判断，**不要**写入 CSVProfile）：
    - 是否可能为时间列
    - 是否可能为目标列
    - 是否可能为分组列
    - 示例值
    - 异常指标

    在生成 CSV 画像时，应对每一个列都调用该工具，确保 ``columns`` 字典覆盖完整。
    """

    df = get_df(runtime)

    if column_name not in df.columns:
        return (
            f"字段【{column_name}】不存在。\n"
            f"可用字段：{', '.join(df.columns)}"
        )

    info = analyze_column_info(df, column_name)
    hints = get_column_hints(df, column_name)

    sample_str = ", ".join(repr(v) for v in hints["sample_values"][:5])
    anomalies_str = (
        "; ".join(hints["anomaly_indicators"])
        if hints["anomaly_indicators"]
        else "无"
    )
    if info.distribution_stats:
        stats_str = "\n".join(
            f"  {k}: {v:.4f}" for k, v in info.distribution_stats.items()
        )
    else:
        stats_str = "  （非数值列，无分布统计）"

    return f"""
字段分析结果

字段名称：{info.name}

字段类型：{info.type.value}

缺失率：{info.missing_rate:.2%}

唯一值数量：{info.unique_count}

时间列候选：{hints['is_time_candidate']}

目标列候选：{hints['is_target_candidate']}

分组列候选：{hints['is_grouping_candidate']}

示例值（最多5个）：{sample_str}

分布统计：
{stats_str}

异常指标：{anomalies_str}
"""
