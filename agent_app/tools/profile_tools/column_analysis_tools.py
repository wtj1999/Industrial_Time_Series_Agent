"""Per-column analysis tool."""

from __future__ import annotations

from typing import List

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
    column_names: List[str],
    runtime: ToolRuntime,
) -> str:
    """批量分析指定列的详细信息。

    输入：
    - column_names：需要分析的列名列表。生成画像时应一次传入全部列名

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

    每个字段都会独立返回一组结果；不存在的字段会集中列出，不影响其他字段。
    """

    df = get_df(runtime)

    if not column_names:
        return "未提供需要分析的字段。请在 column_names 中传入至少一个列名。"

    # 保持调用方给定的顺序，同时避免重复分析同一列。
    unique_column_names = list(dict.fromkeys(column_names))
    missing_columns = [name for name in unique_column_names if name not in df.columns]
    valid_columns = [name for name in unique_column_names if name in df.columns]

    results = []
    for column_name in valid_columns:
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
                f"  {key}: {value:.4f}"
                for key, value in info.distribution_stats.items()
            )
        else:
            stats_str = "  （非数值列，无分布统计）"

        results.append(
            f"""字段名称：{info.name}

字段类型：{info.type.value}

缺失率：{info.missing_rate:.2%}

唯一值数量：{info.unique_count}

时间列候选：{hints['is_time_candidate']}

目标列候选：{hints['is_target_candidate']}

分组列候选：{hints['is_grouping_candidate']}

示例值（最多5个）：{sample_str}

分布统计：
{stats_str}

异常指标：{anomalies_str}"""
        )

    sections = [
        f"字段批量分析结果（成功 {len(valid_columns)} 个，未找到 {len(missing_columns)} 个）"
    ]
    sections.extend(results)
    if missing_columns:
        sections.append(
            "未找到字段："
            + ", ".join(map(str, missing_columns))
            + "\n可用字段："
            + ", ".join(map(str, df.columns))
        )

    return "\n\n---\n\n".join(sections)
