from agents.base_agent import BaseAgent
from utils.prompt_loader import load_prompt


class ChatAgent(BaseAgent):

    def __init__(self):
        self.system_prompt = load_prompt("chat.md")

        super().__init__(
            system_prompt=self.system_prompt,
        )

    async def chat(
        self,
        user_query: str,
        thread_id: str,
    ) -> str:

        return await self.invoke_chat(
            prompt=user_query,
            thread_id=thread_id,
        )

