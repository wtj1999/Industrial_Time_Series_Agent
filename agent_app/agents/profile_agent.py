import os
import logging
from dataclasses import dataclass
import pandas as pd

from agents.base_agent import BaseAgent
from utils.prompt_loader import load_prompt
from models.schemas import CSVProfile
from tools.profile_tools import TOOLS as _PROFILE_TOOLS

@dataclass
class ProfileContext:
    """Context for CSV profiling."""
    df: pd.DataFrame


logger = logging.getLogger(__name__)



class ProfileAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            system_prompt=load_prompt("profile.md"),
            response_model=CSVProfile,
            tools=_PROFILE_TOOLS,
            context_schema=ProfileContext,
        )

    async def profile_csv_file(
            self,
            file_path: str,
            thread_id: str,
    ):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"upload file not found: {file_path}")

        df = pd.read_csv(file_path)
        logger.info(f"Loaded CSV file: {file_path} ({len(df)} rows × {len(df.columns)} columns)")

        ctx = ProfileContext(df=df)

        user_prompt = f"""
        请为该 CSV 文件生成完整的数据画像（CSVProfile）。

        请执行以下流程：

        1. 调用 get_basic_info 获取数据整体信息；
        2. 将全部列名作为列表传入 analyze_column，一次性分析所有字段；
        3. 综合分析结果生成完整的 CSVProfile。

        最终仅返回符合 CSVProfile Schema 的结构化对象。
        """

        result = await self.invoke_structured(
            prompt=user_prompt,
            thread_id=thread_id,
            response_type=CSVProfile,
            context=ctx,
        )

        return result
