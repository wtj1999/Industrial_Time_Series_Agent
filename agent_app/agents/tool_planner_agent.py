from typing import Optional

from agents.base_agent import BaseAgent
from models.schemas import (
    ToolPlan,
    TaskType,
    CSVProfile,
)
from utils.prompt_loader import load_prompt
from tools.registry import ToolRegistry

class ToolPlannerAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            system_prompt=load_prompt("tool_planner.md"),
            response_model=ToolPlan,
        )

        self.registry = ToolRegistry()

    def _build_planner_prompt(
        self,
        *,
        user_query: str,
        tech_proposal: Optional[str],
        csv_profile: Optional[CSVProfile],
        task_type_hint: TaskType,
    ) -> str:

        csv_text = (
            csv_profile.model_dump_json(
                indent=2,
                ensure_ascii=False,
            )
            if csv_profile
            else "None"
        )

        proposal_text = tech_proposal or "None"

        task_type = (
            task_type_hint.value
            if isinstance(task_type_hint, TaskType)
            else str(task_type_hint)
        )

        #
        # 根据任务类型读取 Tool
        #
        tools = self.registry.get_tools(task_type_hint)

        tool_prompt = []

        for tool in tools:

            schema = (
                tool.args_schema.model_json_schema()
                if getattr(tool, "args_schema", None)
                else {}
            )

            tool_prompt.append(
                f"""
                    Tool Name:
                    {tool.name}
                    
                    Description:
                    {tool.description}
                    
                    Arguments(JSON Schema):
                    {schema}
                """
            )

        tool_text = "\n\n".join(tool_prompt)

        return f"""
            ============================
            用户问题
            ============================
            
            {user_query}
            
            ============================
            任务类型
            ============================
            
            {task_type}
            
            ============================
            技术方案
            ============================
            
            {proposal_text}
            
            ============================
            CSV画像
            ============================
            
            {csv_text}
            
            ============================
            可调用工具
            ============================
            
            {tool_text}
            
            ============================
            请输出 ToolPlan
            ============================
            
            请根据用户问题规划需要调用的工具。
            
            要求：
            
            1. 只能使用上面提供的工具。
            
            2. 一个任务可以调用多个工具。
            
            3. 不允许编造工具名称。
            
            4. 参数必须符合工具 Schema。
            
            5. CSV 中不存在的字段不能编造。
            
            6. 如果字段无法确定，参数填 null。
            
            7. 不要真正执行工具。
            
            8. 只负责生成 ToolPlan。
            
            9. 输出必须符合 ToolPlan Schema。
        """

    async def generate_tool_plan(
            self,
            user_query: str,
            thread_id: str,
            tech_proposal: str = None,
            csv_profile: CSVProfile = None,
            task_type_hint: TaskType = None,
    ) -> ToolPlan:
        prompt = self._build_planner_prompt(
            user_query=user_query,
            tech_proposal=tech_proposal,
            csv_profile=csv_profile,
            task_type_hint=task_type_hint,
        )

        plan = await self.invoke_structured(
            prompt=prompt,
            thread_id=thread_id,
            response_type=ToolPlan,
        )

        if plan is None:
            raise RuntimeError("ToolPlannerAgent returned None")

        return plan