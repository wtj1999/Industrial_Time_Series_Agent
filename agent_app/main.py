"""
Main entry point for Industrial Time Series Agent System.

This module provides the main interface for interacting with the multi-agent system.
"""

import os
import sys
import logging
import time
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.orchestrator_graph import OrchestratorAgent
from state.session_state import SessionManager
from config.settings import settings
from utils.helpers import (
    format_response,
    validate_file_path,
    handle_errors,
    log_execution_time
)

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IndustrialTimeSeriesAgent:
    """
    Main interface for Time Series Agent System.
    """

    def __init__(self):
        """Initialize the agent system."""
        self.orchestrator = OrchestratorAgent()
        self.session_manager = SessionManager()
        logger.info("Industrial Time Series Agent System initialized")

    async def process_query(
        self,
        query: str,
        session_id: str,
        resume_value: Any = None,
        user_id: Optional[str] = None,
    ):
        """
        Process a user query (async).

        Returns:
            Response dictionary with results and session information

        """
        started_at = time.monotonic()
        logger.info("Processing query [%s]: %s...", session_id, query[:50])

        try:
            async for chunk in self.orchestrator.process_query(
                    query=query,
                    session_id=session_id,
                    resume_value=resume_value,
                    user_id=user_id,
            ):
                yield chunk
        except Exception:
            logger.exception("process_query failed [%s]", session_id)
            raise
        finally:
            logger.info(
                "process_query stream finished [%s] in %.2f seconds",
                session_id,
                time.monotonic() - started_at,
            )

        # result = await self.orchestrator.process_query(
        #     query=query,
        #     session_id=session_id,
        #     resume_value=resume_value,
        # )
        #
        # return result

    @log_execution_time
    async def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """
        Get information about a session.

        Args:
            session_id: Session ID

        Returns:
            Session information dictionary
        """
        # NOTE: ``@handle_errors`` is intentionally dropped here — it
        # only wraps sync functions. The API layer already has its own
        # try/except → HTTPException mapping, and the orchestrator
        # returns None on internal failure rather than raising.
        return await self.orchestrator.get_session_info(session_id)

    @log_execution_time
    @handle_errors(default_return={'success': False, 'error': 'Failed to get history'})
    def get_session_history(self, session_id: str, limit: int = 20) -> Dict[str, Any]:
        """
        Get conversation history for a session.

        Args:
            session_id: Session ID
            limit: Maximum number of messages to retrieve

        Returns:
            Dictionary with conversation history
        """
        history = self.orchestrator.get_session_history(session_id, limit)

        if history is None:
            return {
                'success': False,
                'error': 'Session not found'
            }

        return {
            'success': True,
            'history': history,
            'total_messages': len(history)
        }

    @log_execution_time
    @handle_errors(default_return={'success': False, 'error': 'Failed to continue session'})
    def continue_session(self, session_id: str, query: str) -> Dict[str, Any]:
        """
        Continue an existing session with a new query.

        Args:
            session_id: Existing session ID
            query: New user query

        Returns:
            Response dictionary
        """
        return self.orchestrator.continue_session(session_id, query)

    @log_execution_time
    async def reset_session_task(self, session_id: str) -> Dict[str, Any]:
        """
        Reset the current task in a session.

        Args:
            session_id: Session ID

        Returns:
            Status response dictionary
        """
        # NOTE: ``@handle_errors`` dropped — sync-only decorator. The
        # API layer's try/except handles errors; the orchestrator
        # returns ``{success: True, ...}`` even when nothing was cleared.
        return await self.orchestrator.reset_session_task(session_id)

    @log_execution_time
    @handle_errors(default_return={'success': False, 'error': 'Failed to get available tasks'})
    def get_available_tasks(self, session_id: str) -> Dict[str, Any]:
        """
        Get available analysis tasks for a session.

        Args:
            session_id: Session ID

        Returns:
            Dictionary with available tasks
        """
        tasks = self.orchestrator.get_available_tasks(session_id)

        if tasks is None:
            return {
                'success': False,
                'error': 'Session not found'
            }

        return {
            'success': True,
            'available_tasks': tasks,
            'total_tasks': len(tasks)
        }

    def create_new_session(self, session_id: Optional[str] = None, initial_query: Optional[str] = None) -> str:
        """
        Create a new session with specified or generated session_id.

        Args:
            session_id: Optional session ID (if not provided, generates UUID)
            initial_query: Optional initial query

        Returns:
            Session ID
        """
        session = self.session_manager.create_session(initial_query, session_id)
        logger.info(f"Created session: {session.session_id}")
        return session.session_id

    def cleanup_expired_sessions(self) -> Dict[str, Any]:
        """
        Clean up expired sessions.

        Returns:
            Dictionary with cleanup results
        """
        cleaned_count = self.session_manager.cleanup_expired_sessions()

        return {
            'success': True,
            'cleaned_sessions': cleaned_count,
            'message': f'Cleaned up {cleaned_count} expired sessions'
        }

    def get_system_status(self) -> Dict[str, Any]:
        """
        Get system status information.

        Returns:
            Dictionary with system status
        """
        active_sessions = self.session_manager.get_all_active_sessions()

        return {
            'success': True,
            'system': {
                'name': settings.app_name,
                'version': settings.version,
                'debug_mode': settings.debug
            },
            'sessions': {
                'active_count': len(active_sessions),
                'timeout_minutes': settings.session_timeout_minutes
            },
            'configuration': {
                'llm_provider': settings.llm.provider,
                'llm_model': settings.llm.model_name,
                'max_prediction_steps': settings.max_prediction_steps,
                'supported_tasks': settings.supported_tasks
            }
        }


def main():
    """
    Main function for command-line interface.

    Provides an interactive command-line interface for the agent system.
    """
    print("=" * 60)
    print(f"工业时间序列多智能体系统 - {settings.version}")
    print("=" * 60)
    print("")

    # Initialize agent system
    agent = IndustrialTimeSeriesAgent()
    session_id = None
    file_path = None

    print("系统已初始化。输入 'help' 查看可用命令，'exit' 退出。")
    print("注意：session_id 现在是必传参数，使用 'new' 命令创建新会话。")
    print("")

    while True:
        try:
            # Get user input
            if file_path:
                prompt = f"[Session: {session_id[:8] if session_id else 'None'}] [File: {os.path.basename(file_path)}] > "
            else:
                prompt = f"[Session: {session_id[:8] if session_id else 'None'}] > "

            user_input = input(prompt).strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.lower() == 'exit':
                print("感谢使用工业时间序列多智能体系统！")
                break

            elif user_input.lower() == 'help':
                print_available_commands()
                continue

            elif user_input.lower() == 'status':
                status = agent.get_system_status()
                print_system_status(status)
                continue

            elif user_input.lower() == 'new':
                import uuid
                session_id = str(uuid.uuid4())
                file_path = None
                print(f"已生成新会话ID: {session_id}")
                print("现在可以使用此 session_id 进行查询")
                continue

            elif user_input.lower() == 'info':
                if session_id:
                    info = agent.get_session_info(session_id)
                    print_session_info(info)
                else:
                    print("没有活动的会话。使用 'new' 命令创建新会话。")
                continue

            elif user_input.lower().startswith('file '):
                file_path = user_input[5:].strip()
                is_valid, error = validate_file_path(file_path)
                if is_valid:
                    print(f"文件已设置: {file_path}")
                    if not session_id:
                        print("注意：需要先使用 'new' 命令创建 session_id")
                else:
                    print(f"错误: {error}")
                continue

            # Process query
            if not session_id:
                print("错误：session_id 是必传参数")
                print("请先使用 'new' 命令创建新会话，或输入现有 session_id")
                print("提示: 使用 'new' 命令生成新的 session_id")
                continue

            result = agent.process_query(
                query=user_input,
                session_id=session_id,
                file_path=file_path
            )

            # Display result
            print_query_result(result)

        except KeyboardInterrupt:
            print("\n\n操作已取消。输入 'exit' 退出。")
        except Exception as e:
            print(f"错误: {str(e)}")
            logger.error(f"Error in main loop: {str(e)}", exc_info=True)


def print_available_commands():
    """Print available commands."""
    print("可用命令:")
    print("  new          - 生成新的 session_id")
    print("  file <path>  - 设置CSV文件路径")
    print("  info         - 显示当前会话信息")
    print("  status       - 显示系统状态")
    print("  help         - 显示此帮助信息")
    print("  exit         - 退出系统")
    print("")
    print("注意：")
    print("  • session_id 是必传参数")
    print("  • 使用 'new' 命令生成新的 session_id")
    print("  • 所有查询都需要提供 session_id")
    print("")


def print_system_status(status: Dict[str, Any]):
    """Print system status."""
    if not status.get('success'):
        print("错误: 无法获取系统状态")
        return

    system = status['system']
    sessions = status['sessions']
    config = status['configuration']

    print(f"系统: {system['name']} v{system['version']}")
    print(f"调试模式: {system['debug_mode']}")
    print(f"活动会话: {sessions['active_count']}")
    print(f"LLM提供商: {config['llm_provider']}")
    print(f"LLM模型: {config['llm_model']}")
    print(f"支持的任务: {', '.join(config['supported_tasks'])}")
    print("")


def print_session_info(info: Optional[Dict[str, Any]]):
    """Print session information."""
    if not info:
        print("错误: 无法获取会话信息")
        return

    print(f"会话 ID: {info.get('session_id', 'Unknown')}")
    print(f"创建时间: {info.get('created_at', 'Unknown')}")
    print(f"更新时间: {info.get('updated_at', 'Unknown')}")
    print(f"活动状态: {info.get('is_active', False)}")
    print(f"当前任务: {info.get('current_task', 'None')}")
    print(f"当前阶段: {info.get('current_stage', 'Unknown')}")
    print(f"对话轮数: {info.get('dialogue_turns', 0)}")
    print(f"有CSV档案: {info.get('has_csv_profile', False)}")
    print(f"有确认规格: {info.get('has_confirmed_spec', False)}")
    print(f"待澄清: {info.get('clarification_pending', False)}")
    print(f"分析结果数: {info.get('analysis_artifacts_count', 0)}")
    print("")


def print_query_result(result: Dict[str, Any]):
    """Print query result."""
    if result.get('success'):
        print(result.get('response', '处理完成'))

        if result.get('followup_suggestions'):
            print("\n建议的后续操作:")
            for suggestion in result['followup_suggestions'][:3]:
                print(f"  • {suggestion}")
    else:
        print(f"处理失败: {result.get('error', 'Unknown error')}")

        if result.get('needs_clarification'):
            print("\n需要补充信息:")
            for i, question in enumerate(result.get('questions', []), 1):
                print(f"  {i}. {question}")

    print("")


if __name__ == '__main__':
    main()
