from typing import Annotated, Any, Dict, List, Literal, Optional, Union, TypedDict
from agents.base_agent import BaseAgent
from models.schemas import TaskSpec, TaskType, CSVProfile, TechPath
from utils.prompt_loader import load_prompt


class ParserAgent(BaseAgent):
    """
    Main Parser Agent that coordinates task identification and parameter extraction.
    """

    def __init__(self):

        super().__init__(
            system_prompt=load_prompt("parser.md"),
            response_model=TaskSpec,
        )

    def _build_user_prompt(
            self,
            user_query: str,
            tech_proposal: Optional[TechPath] = None,
            csv_profile: Optional[CSVProfile] = None,
            task_type: TaskType = None,
    ) -> str:

        return f"""
                    用户问题：
                    {user_query}

                    技术方案：
                    {tech_proposal.model_dump_json(indent=2, ensure_ascii=False) if tech_proposal else "None"}

                    CSV画像：
                    {csv_profile.model_dump_json(indent=2, ensure_ascii=False) if csv_profile else "None"}
                    
                    任务类型：

                    {(task_type.value if isinstance(task_type, TaskType) else task_type) if task_type else "None"}

                    请基于以上信息输出 TaskSpec。
                """

    async def generate_task_spec(
            self,
            user_query: str,
            thread_id: str,
            tech_proposal: Optional[Dict[str, Any]]  = None,
            csv_profile: Optional[CSVProfile] = None,
            task_type: TaskType = None,
    ) -> TaskSpec:
        prompt = self._build_user_prompt(
            user_query=user_query,
            tech_proposal=tech_proposal,
            csv_profile=csv_profile,
            task_type=task_type,
        )

        return await self.invoke_structured(
            prompt=prompt,
            thread_id=thread_id,
            response_type=TaskSpec,
        )
