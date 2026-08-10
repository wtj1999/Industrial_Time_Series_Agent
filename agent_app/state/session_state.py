"""
Session state management for multi-turn conversations.
"""

import json
import uuid
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta

from models.schemas import SessionState, TaskType, TaskStage, TaskSpec, CSVProfile, Message
from config.settings import settings


class SessionManager:
    """
    Manages session state for multi-turn conversations.

    This class provides methods to create, retrieve, update, and delete sessions.
    It maintains unified session state across all agents.
    """

    def __init__(self):
        """Initialize session manager."""
        self.sessions: Dict[str, SessionState] = {}
        self.session_timeout = timedelta(minutes=settings.session_timeout_minutes)

    def create_session(self, initial_query: Optional[str] = None, session_id: Optional[str] = None) -> SessionState:
        """
        Create a new session.

        Args:
            initial_query: Optional initial user query
            session_id: Optional session ID (if not provided, generates UUID)

        Returns:
            SessionState: The created session state
        """
        if session_id is None:
            session_id = str(uuid.uuid4())

        session_state = SessionState(
            session_id=session_id,
            last_user_query=initial_query,
            current_stage=TaskStage.PROFILING
        )

        if initial_query:
            session_state.add_message(role="user", content=initial_query)

        self.sessions[session_id] = session_state
        return session_state

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """
        Retrieve a session by ID.

        Args:
            session_id: The session ID to retrieve

        Returns:
            SessionState if found and active, None otherwise
        """
        session = self.sessions.get(session_id)
        if session and session.is_active:
            # Check if session has timed out
            if datetime.utcnow() - session.updated_at < self.session_timeout:
                return session
            else:
                session.is_active = False
        return None

    def update_session(self, session_id: str, **updates: Any) -> Optional[SessionState]:
        """
        Update session fields.

        Args:
            session_id: The session ID to update
            **updates: Fields to update

        Returns:
            Updated SessionState if found, None otherwise
        """
        session = self.get_session(session_id)
        if not session:
            return None

        for field, value in updates.items():
            if hasattr(session, field):
                setattr(session, field, value)
            else:
                raise ValueError(f"Invalid field: {field}")

        session.update_timestamp()
        return session

    def add_dialogue_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[SessionState]:
        """
        Add a message to the dialogue history.

        Args:
            session_id: The session ID
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata

        Returns:
            Updated SessionState if found, None otherwise
        """
        session = self.get_session(session_id)
        if not session:
            return None

        session.add_message(role=role, content=content, metadata=metadata)
        return session

    def set_last_user_query(self, session_id: str, query: str) -> Optional[SessionState]:
        return self.update_session(session_id, last_user_query=query)

    def set_csv_profile(self, session_id: str, csv_profile: CSVProfile) -> Optional[SessionState]:
        return self.update_session(session_id, csv_profile=csv_profile)

    def set_current_task(self, session_id: str, task_type: TaskType) -> Optional[SessionState]:
        return self.update_session(session_id, current_task=task_type)

    def set_task_stage(self, session_id: str, stage: TaskStage) -> Optional[SessionState]:
        return self.update_session(session_id, current_stage=stage)

    def set_task_spec(self, session_id: str, spec: TaskSpec) -> Optional[SessionState]:
        """
        Set the task specification.

        Args:
            session_id: The session ID
            spec: The task specification

        Returns:
            Updated SessionState if found, None otherwise
        """
        return self.update_session(
            session_id,
            confirmed_spec=spec,
            clarification_pending=False,
            clarification_message=None
        )

    def set_tech_proposal(
            self,
            session_id: str,
            tech_proposal: str
    ) -> Optional[SessionState]:
        return self.update_session(session_id, tech_proposal=tech_proposal)


    def store_analysis_result(
        self,
        session_id: str,
        analysis_results: str,
    ) -> Optional[SessionState]:
        return self.update_session(session_id, analysis_results=analysis_results)

    def set_clarification_pending(
        self,
        session_id: str,
        message: str
    ) -> Optional[SessionState]:
        """
        Set clarification as pending with a message.

        Args:
            session_id: The session ID
            message: Clarification message (contains all questions)

        Returns:
            Updated SessionState if found, None otherwise
        """
        return self.update_session(
            session_id,
            clarification_pending=True,
            clarification_message=message
        )


    def get_analysis_result(
        self,
        session_id: str,
        result_key: str
    ) -> Optional[Any]:
        """
        Retrieve analysis result from artifacts.

        Args:
            session_id: The session ID
            result_key: Key for the result

        Returns:
            Result data if found, None otherwise
        """
        session = self.get_session(session_id)
        if not session:
            return None

        return session.analysis_artifacts.get(result_key)

    def get_recent_history(
        self,
        session_id: str,
        n: int = 10
    ) -> List[Message]:
        """
        Get recent dialogue history.

        Args:
            session_id: The session ID
            n: Number of recent messages to retrieve

        Returns:
            List of recent messages
        """
        session = self.get_session(session_id)
        if not session:
            return []

        return session.get_recent_messages(n)

    def clear_session(self, session_id: str) -> bool:
        """
        Deactivate a session.

        Args:
            session_id: The session ID to deactivate

        Returns:
            True if session was deactivated, False otherwise
        """
        session = self.get_session(session_id)
        if session:
            session.is_active = False
            return True
        return False

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session permanently.

        Args:
            session_id: The session ID to delete

        Returns:
            True if session was deleted, False otherwise
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        expired_count = 0
        current_time = datetime.utcnow()

        for session_id, session in list(self.sessions.items()):
            if current_time - session.updated_at >= self.session_timeout:
                session.is_active = False
                expired_count += 1

        return expired_count

    def get_all_active_sessions(self) -> List[SessionState]:
        """
        Get all active sessions.

        Returns:
            List of active sessions
        """
        return [
            session for session in self.sessions.values()
            if session.is_active
        ]

    def export_session(self, session_id: str) -> Optional[str]:
        """
        Export session state to JSON string.

        Args:
            session_id: The session ID to export

        Returns:
            JSON string if session found, None otherwise
        """
        session = self.get_session(session_id)
        if not session:
            return None

        return session.json(indent=2)

    def import_session(self, json_str: str) -> Optional[SessionState]:
        """
        Import session state from JSON string.

        Args:
            json_str: JSON string to import

        Returns:
            Imported SessionState
        """
        try:
            data = json.loads(json_str)
            session = SessionState(**data)
            self.sessions[session.session_id] = session
            return session
        except Exception as e:
            raise ValueError(f"Failed to import session: {e}")
