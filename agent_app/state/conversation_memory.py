"""
Conversation memory for maintaining context across multi-turn conversations.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from langchain_core.memory import ConversationBufferMemory, ConversationSummaryMemory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from models.schemas import Message, SessionState


class ConversationMemory:
    """
    Manages conversation memory for LangChain agents.

    This class bridges between the unified session state and LangChain's memory system,
    allowing agents to maintain context across conversations.
    """

    def __init__(self, session_state: SessionState, max_history: int = 50):
        """
        Initialize conversation memory.

        Args:
            session_state: The session state to base memory on
            max_history: Maximum number of messages to keep in memory
        """
        self.session_state = session_state
        self.max_history = max_history

        # Initialize LangChain memory
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            input_key="input",
            output_key="output"
        )

        # Load existing conversation history
        self._load_history_from_session()

    def _load_history_from_session(self):
        """Load conversation history from session state into LangChain memory."""
        for msg in self.session_state.dialogue_history[-self.max_history:]:
            if msg.role == "user":
                self.memory.chat_memory.add_user_message(msg.content)
            elif msg.role == "assistant":
                self.memory.chat_memory.add_ai_message(msg.content)
            elif msg.role == "system":
                self.memory.chat_memory.add_message(SystemMessage(content=msg.content))

    def add_user_message(self, message: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Add a user message to memory.

        Args:
            message: The message content
            metadata: Optional metadata
        """
        self.memory.chat_memory.add_user_message(message)
        self.session_state.add_message(role="user", content=message, metadata=metadata)

    def add_ai_message(self, message: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Add an AI message to memory.

        Args:
            message: The message content
            metadata: Optional metadata
        """
        self.memory.chat_memory.add_ai_message(message)
        self.session_state.add_message(role="assistant", content=message, metadata=metadata)

    def add_system_message(self, message: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Add a system message to memory.

        Args:
            message: The message content
            metadata: Optional metadata
        """
        self.memory.chat_memory.add_message(SystemMessage(content=message))
        self.session_state.add_message(role="system", content=message, metadata=metadata)

    def get_memory_variables(self) -> Dict[str, Any]:
        """
        Get memory variables for LangChain.

        Returns:
            Dictionary of memory variables
        """
        return self.memory.load_memory_variables({})

    def get_chat_history(self) -> List[BaseMessage]:
        """
        Get chat history as LangChain messages.

        Returns:
            List of BaseMessage objects
        """
        return self.memory.chat_memory.messages

    def get_recent_history(self, n: int = 10) -> List[Message]:
        """
        Get recent conversation history.

        Args:
            n: Number of recent messages to retrieve

        Returns:
            List of Message objects
        """
        return self.session_state.get_recent_messages(n)

    def get_context_summary(self) -> str:
        """
        Get a summary of conversation context.

        Returns:
            Context summary string
        """
        if not self.session_state.dialogue_history:
            return "No conversation history."

        summary_parts = []

        # Add current task context
        if self.session_state.current_task:
            summary_parts.append(f"Current Task: {self.session_state.current_task.value}")

        # Add CSV profile context
        if self.session_state.csv_profile:
            summary_parts.append(
                f"Dataset: {self.session_state.csv_profile.file_name} "
                f"({self.session_state.csv_profile.total_rows} rows, "
                f"{self.session_state.csv_profile.total_columns} columns)"
            )

        # Add confirmed spec context
        if self.session_state.confirmed_spec:
            spec = self.session_state.confirmed_spec
            summary_parts.append(f"Task Type: {spec.task_type.value}")
            if spec.target_column:
                summary_parts.append(f"Target Column: {spec.target_column}")
            if spec.prediction_steps:
                summary_parts.append(f"Prediction Steps: {spec.prediction_steps}")

        # Add recent conversation context
        recent_messages = self.get_recent_history(3)
        if recent_messages:
            summary_parts.append("\nRecent conversation:")
            for msg in recent_messages:
                summary_parts.append(f"  {msg.role}: {msg.content[:100]}...")

        return "\n".join(summary_parts)

    def clear_memory(self):
        """Clear all memory."""
        self.memory.clear()
        # Keep session state but clear dialogue history
        self.session_state.dialogue_history = []

    def should_continue_previous_task(self, current_query: str) -> bool:
        """
        Determine if the current query is a continuation of the previous task.

        Args:
            current_query: The current user query

        Returns:
            True if continuing previous task, False otherwise
        """
        continuation_keywords = [
            "继续", "再", "还", "继续分析", "进一步", "深入",
            "continue", "further", "more", "deeper", "additional",
            "扩展", "展开", "详细", "补充"
        ]

        query_lower = current_query.lower()
        return any(keyword in query_lower for keyword in continuation_keywords)

    def extract_reference_to_previous_result(self, current_query: str) -> Optional[str]:
        """
        Extract references to previous results in the current query.

        Args:
            current_query: The current user query

        Returns:
            Reference key if found, None otherwise
        """
        reference_patterns = [
            "前面的", "上面的", "刚才的", "之前的", "那个结果",
            "previous", "above", "earlier", "that result"
        ]

        query_lower = current_query.lower()
        for pattern in reference_patterns:
            if pattern in query_lower:
                return pattern

        return None

    def get_memory_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about memory usage.

        Returns:
            Dictionary of memory statistics
        """
        history = self.session_state.dialogue_history
        user_messages = [m for m in history if m.role == "user"]
        assistant_messages = [m for m in history if m.role == "assistant"]

        return {
            "total_messages": len(history),
            "user_messages": len(user_messages),
            "assistant_messages": len(assistant_messages),
            "session_age_minutes": (
                datetime.utcnow() - self.session_state.created_at
            ).total_seconds() / 60,
            "last_activity_minutes": (
                datetime.utcnow() - self.session_state.updated_at
            ).total_seconds() / 60,
            "has_csv_profile": self.session_state.csv_profile is not None,
            "has_confirmed_spec": self.session_state.confirmed_spec is not None,
            "current_task": self.session_state.current_task.value if self.session_state.current_task else None,
            "current_stage": self.session_state.current_stage.value
        }


class SummaryConversationMemory(ConversationMemory):
    """
    Conversation memory that summarizes older messages to manage token usage.
    """

    def __init__(self, session_state: SessionState, max_history: int = 50):
        """
        Initialize summary conversation memory.

        Args:
            session_state: The session state to base memory on
            max_history: Maximum number of messages before summarization
        """
        super().__init__(session_state, max_history)
        self.summary_memory = ConversationSummaryMemory(
            memory_key="chat_history",
            return_messages=True,
            input_key="input",
            output_key="output"
        )

    def get_memory_variables(self) -> Dict[str, Any]:
        """
        Get memory variables with summary.

        Returns:
            Dictionary of memory variables including summary
        """
        return self.summary_memory.load_memory_variables({})

    def summarize_older_messages(self, keep_recent: int = 10):
        """
        Summarize messages older than the recent ones.

        Args:
            keep_recent: Number of recent messages to keep without summarizing
        """
        recent_messages = self.get_recent_history(keep_recent)
        self.clear_memory()

        # Re-add only recent messages
        for msg in recent_messages:
            if msg.role == "user":
                self.add_user_message(msg.content, msg.metadata)
            elif msg.role == "assistant":
                self.add_ai_message(msg.content, msg.metadata)
            elif msg.role == "system":
                self.add_system_message(msg.content, msg.metadata)
