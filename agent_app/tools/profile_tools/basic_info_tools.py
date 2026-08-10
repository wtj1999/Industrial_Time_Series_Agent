"""Dataset-level overview tool."""

from __future__ import annotations

from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from agent_app.tools._tool_guard import tool_guard
from agent_app.tools.profile_tools._common import get_df


@tool("get_basic_info")
@tool_guard("get_basic_info", return_type="str")
def get_basic_info(runtime: ToolRuntime) -> str:
    """获取CSV数据集的整体信息。

    返回内容包括：
    - 总行数
    - 总列数
    - 所有列名
    - 内存占用
    - 每列的数据类型

    该工具用于帮助理解数据集整体结构，应作为CSV画像分析的第一步。
    """

    df = get_df(runtime)

    return f"""
数据集基本信息：

- 总行数：{len(df)}
- 总列数：{len(df.columns)}

列名：

{", ".join(df.columns.tolist())}

内存占用：

{df.memory_usage(deep=True).sum() / 1024**2:.2f} MB

各列数据类型：

{df.dtypes.to_string()}
"""