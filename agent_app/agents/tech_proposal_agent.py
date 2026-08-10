import logging

from models.schemas import TechProposalEnvelope

from agents.base_agent import BaseAgent
from utils.prompt_loader import load_prompt, load_skill

logger = logging.getLogger(__name__)


class ProposalAgent:

    def __init__(self):

        self.text_agent = BaseAgent(
            system_prompt=load_prompt(
                "proposal_text.md",
                analysis_skill=load_skill("analysis_skill.md"),
                prediction_skill=load_skill("prediction_skill.md"),
                anomaly_skill=load_skill("anomaly_detection_skill.md"),
        ))

        self.path_agent = BaseAgent(
            system_prompt=load_prompt("proposal_path.md"),
            response_model=TechProposalEnvelope,
        )

        logger.info("ProposalAgent initialized")


    def _build_user_prompt(
            self,
            user_query: str,
    ) -> str:

        return f"""
                    用户问题：
                    {user_query}
                    请基于以上信息输出一份详细的端到端技术方案。
        """

    def _build_proposal_prompt(
            self,
            proposal_text: str,
    ) -> str:

        return f"""
                    技术方案：
                    {proposal_text}
                    请基于以上信息提取结构化的技术路线，严格输出符合 schema 的 JSON。
        """

    async def _generate_proposal_text(
            self,
            user_query: str,
            thread_id: str,
    ):
        return await self.text_agent.invoke_chat(
            prompt=self._build_user_prompt(user_query),
            thread_id=thread_id,
        )

    async def _generate_proposal_paths(
            self,
            proposal_text: str,
            thread_id: str,
    ):
        return await self.path_agent.invoke_structured(
            prompt=self._build_proposal_prompt(proposal_text),
            thread_id=thread_id,
            response_type=TechProposalEnvelope
        )

    async def generate_tech_proposal(
            self,
            user_query: str,
            thread_id: str = None,
    ):
        try:
            proposal_text = await self._generate_proposal_text(
                user_query=user_query,
                thread_id=thread_id,
            )

            if not proposal_text:
                raise RuntimeError("Failed to generate proposal text")

            proposal_paths = await self._generate_proposal_paths(
                proposal_text=proposal_text,
                thread_id=thread_id,
            )

            if proposal_paths is None:
                raise RuntimeError("Failed to generate structured tech paths")

            return {
                "proposal_text": proposal_text,
                "proposal_paths": proposal_paths.paths,
            }

        except Exception as e:
            logger.error(f"Failed to generate tech proposal: {str(e)}", exc_info=True)
            return None


