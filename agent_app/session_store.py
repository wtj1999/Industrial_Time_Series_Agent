"""Per-user session index for the orchestrator.

The LangGraph ``SqliteSaver`` checkpointer is keyed by ``thread_id``
(= session_id) and knows nothing about user ownership, so we maintain a
small side index that maps ``(user_id, session_id)`` to display metadata
(title, timestamps, message count). The frontend uses this to render the
"历史对话" list in the sidebar.

Storage
-------
A dedicated SQLite file ``sessions.db`` next to the orchestrator's own
``orchestrator.db`` (kept separate so langgraph schema changes can never
clobber our data). All writes go through a process-wide
:class:`threading.Lock` and SQLite's own WAL journaling, which is enough
for a single uvicorn worker. If this ever needs to scale across workers,
swap the file for Postgres without touching the public surface.

The checkpointer state itself (including the full ``dialogue_history``)
lives in langgraph's DB; this module only stores the lightweight lookup
fields the UI needs to list sessions without re-reading every checkpoint.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Storage paths + concurrency
# ----------------------------------------------------------------------

# Resolve relative to this file so the DB location doesn't depend on
# uvicorn's CWD. Sits next to orchestrator.db (created by the
# SqliteSaver) — same directory, different file.
_DB_PATH: Path = Path(__file__).resolve().parent / "sessions.db"
_LOCK = threading.Lock()

_TITLE_MAX = 40


def _connect() -> sqlite3.Connection:
    """Open a check_same_thread=False connection. Callers serialize
    writes via ``_LOCK`` so a single shared connection is fine."""
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS session_index (
            session_id   TEXT PRIMARY KEY,
            user_id      TEXT NOT NULL,
            title        TEXT,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL,
            message_count INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_session_user
            ON session_index(user_id, updated_at DESC);
        """
    )
    conn.commit()


# Initialise on import so the first request works without a startup hook.
try:
    with _LOCK, _connect() as c:
        _ensure_schema(c)
except Exception as exc:  # pragma: no cover - startup diagnostic
    logger.error("session_store: failed to initialise schema: %s", exc)


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _derive_title(first_user_message: Optional[str]) -> str:
    """Compact a user message into a sidebar-friendly title.

    Strips excess whitespace and truncates to ``_TITLE_MAX`` chars with
    an ellipsis. Returns a generic fallback when the session has no
    usable text yet (e.g. started from a pure file upload).
    """
    if not first_user_message:
        return "新对话"
    s = " ".join(str(first_user_message).split())
    if not s:
        return "新对话"
    if len(s) <= _TITLE_MAX:
        return s
    return s[:_TITLE_MAX - 1] + "…"


def _row_to_summary(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "session_id": row["session_id"],
        "user_id": row["user_id"],
        "title": row["title"] or "新对话",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "message_count": int(row["message_count"] or 0),
    }


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def upsert_session(
    user_id: str,
    session_id: str,
    dialogue_history: Optional[List[Any]],
) -> None:
    """Create or refresh the index entry for ``session_id``.

    ``title`` is set on first creation from the first user message in
    ``dialogue_history`` and kept stable afterwards — a session shouldn't
    be renamed just because the latest message is shorter. ``updated_at``
    and ``message_count`` are refreshed on every call.

    ``dialogue_history`` entries may be pydantic ``Message`` models,
    plain dicts, or any object with ``role``/``content`` attributes; we
    coerce defensively.
    """
    if not user_id or not session_id:
        return

    first_user: Optional[str] = None
    msg_count = 0
    if dialogue_history:
        for m in dialogue_history:
            role = None
            content = None
            if hasattr(m, "role") and hasattr(m, "content"):
                role = getattr(m, "role", None)
                content = getattr(m, "content", None)
            elif isinstance(m, dict):
                role = m.get("role")
                content = m.get("content")
            if role == "user" and content and first_user is None:
                first_user = str(content)
            msg_count += 1

    now = _now_iso()
    title = _derive_title(first_user)

    with _LOCK, _connect() as c:
        cur = c.execute(
            "SELECT created_at, title FROM session_index WHERE session_id = ?",
            (session_id,),
        )
        existing = cur.fetchone()
        if existing:
            # Preserve original created_at + title (stable identity).
            c.execute(
                """
                UPDATE session_index
                   SET user_id = ?, updated_at = ?, message_count = ?
                 WHERE session_id = ?
                """,
                (user_id, now, msg_count, session_id),
            )
        else:
            c.execute(
                """
                INSERT INTO session_index
                    (session_id, user_id, title, created_at, updated_at, message_count)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, user_id, title, now, now, msg_count),
            )
        c.commit()


def list_sessions(user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Return all sessions owned by ``user_id``, newest first."""
    if not user_id:
        return []
    with _LOCK, _connect() as c:
        cur = c.execute(
            """
            SELECT session_id, user_id, title, created_at, updated_at, message_count
              FROM session_index
             WHERE user_id = ?
             ORDER BY updated_at DESC
             LIMIT ?
            """,
            (user_id, limit),
        )
        return [_row_to_summary(r) for r in cur.fetchall()]


def get_session_owner(session_id: str) -> Optional[str]:
    """Return the ``user_id`` that owns ``session_id``, or None."""
    if not session_id:
        return None
    with _LOCK, _connect() as c:
        cur = c.execute(
            "SELECT user_id FROM session_index WHERE session_id = ?",
            (session_id,),
        )
        row = cur.fetchone()
        return row["user_id"] if row else None


def delete_session(session_id: str) -> bool:
    """Remove ``session_id`` from the index. Returns True if a row was
    deleted. The langgraph checkpoint for the thread is *not* touched
    here — the caller decides whether to clear that too.
    """
    if not session_id:
        return False
    with _LOCK, _connect() as c:
        cur = c.execute(
            "DELETE FROM session_index WHERE session_id = ?",
            (session_id,),
        )
        c.commit()
        return cur.rowcount > 0
