from typing import List, Optional

from models.schemas import (
    IntentRouterResult,
    Message,
    TaskStage,
    TaskType
)
from agents.base_agent import BaseAgent
from utils.prompt_loader import load_prompt, load_skill


class IntentRouterAgent(BaseAgent):

    _HISTORY_WINDOW = 6

    def __init__(self):
        self.system_prompt = load_prompt(
            "intent_router.md",
            analysis_skill=load_skill("analysis_skill.md"),
            prediction_skill=load_skill("prediction_skill.md"),
            anomaly_skill=load_skill("anomaly_detection_skill.md"),
        )

        super().__init__(
            system_prompt=self.system_prompt,
            response_model=IntentRouterResult,
        )

    def _build_prompt(
        self,
        user_query: str,
        current_stage: Optional[TaskStage],
        dialogue_history: Optional[List[Message]],
        task_type: Optional[TaskType]
    ) -> str:

        parts: List[str] = []

        if current_stage is not None:
            parts.append(f"[CURRENT_STAGE={current_stage.value}]")

        if task_type is not None:
            parts.append(f"[LAST_ROUND_TASK={task_type.value}]")

        if dialogue_history:
            recent = dialogue_history[-self._HISTORY_WINDOW:]
            if recent:
                history_lines = [
                    f"[{m.role}] {m.content}" for m in recent
                ]
                parts.append(
                    "[DIALOGUE_HISTORY]\n"
                    + "\n".join(history_lines)
                    + "\n[/DIALOGUE_HISTORY]"
                )

        parts.append(
            "[LAST_USER_QUERY]\n"
            + "\n".join(user_query)
            + "\n[/LAST_USER_QUERY]"
        )
        return "\n\n".join(parts)

    async def classify(
        self,
        user_query: str,
        thread_id: str,
        current_stage: Optional[TaskStage] = None,
        task_type: Optional[TaskType] = None,
        dialogue_history: Optional[List[Message]] = None,
    ):
        prompt = self._build_prompt(
            user_query=user_query,
            current_stage=current_stage,
            dialogue_history=dialogue_history,
            task_type=task_type
        )

        return await self.invoke_structured(
            prompt=prompt,
            thread_id=thread_id,
            response_type=IntentRouterResult,
        )

