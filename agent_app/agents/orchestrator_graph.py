# orchestrator_graph.py
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, TypedDict, Union
from datetime import datetime
from pathlib import Path

import logging
import sqlite3
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_core.messages import ToolMessage

from models.schemas import (
    TaskType, SessionState, TaskStage, IntentType, Message, ModelRef
)
from state.session_state import SessionManager
from agents.profile_agent import ProfileAgent
from agents.parser_agent import ParserAgent
from agents.prediction_agent import PredictionAgent
from agents.anomaly_detection_agent import AnomalyDetectionAgent
# from agents.explanation_agent import ExplanationAgent
# from agents.report_agent import ReportAgent
from agents.analysis_agent import AnalysisAgent
from agents.tech_proposal_agent import ProposalAgent
from agents.intent_router_agent import IntentRouterAgent
from agents.chat_agent import ChatAgent
from utils.csv_preview import build_csv_preview

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Path to the persistent SQLite checkpoint DB. Resolved relative to this
# file so it doesn't depend on uvicorn's CWD.
#
# NOTE: the saver is opened LAZILY inside the FastAPI event loop (see
# ``_ensure_graph``) because ``AsyncSqliteSaver`` wraps an ``aiosqlite``
# connection whose worker thread captures the *running* loop at connect
# time. Constructing it eagerly in ``__init__`` would bind it to no loop
# (or a throwaway one) and every later ``await`` would fail.
_CHECKPOINT_DB_PATH: Path = Path(__file__).resolve().parent.parent / "orchestrator.db"

_NODE_WORKFLOW_PLAN: Dict[str, List[str]] = {
    "chat": ["闲聊响应"],
    "execute_task": ["技术方案执行"],
    "profiling": ["数据画像", "文件参数解析", "文件字段澄清", "技术方案执行"],
    "parse_intent": ["文件参数解析", "文件字段澄清", "技术方案执行"],
    "await_clarification": ["文件字段澄清", "技术方案执行"],
    "tech_proposal": ["技术方案生成", "技术方案选择", "文件参数解析", "文件字段澄清", "技术方案执行"],
}

_INTERNAL_NODES = {"intent_router", "parse_intent", "await_clarification", "profiling"}


class OrchestratorAgent:
    def __init__(self):
        self.session_manager = SessionManager()

        self.intent_router_agent = IntentRouterAgent()
        self.chat_agent = ChatAgent()
        self.proposal_agent = ProposalAgent()
        self.profile_agent = ProfileAgent()
        # self.tool_planner_agent = ToolPlannerAgent()
        self.parser_agent = ParserAgent()
        self.analysis_agent = AnalysisAgent()
        self.prediction_agent = PredictionAgent()
        self.anomaly_agent = AnomalyDetectionAgent()
        self.explanation_agent = None
        self.report_agent = None

        # The LangGraph checkpointer + compiled graph are built LAZILY on
        # the first ``process_query`` / ``aget_session_info`` call. See
        # the note on ``_CHECKPOINT_DB_PATH``: AsyncSqliteSaver must be
        # constructed inside the running event loop.
        self._checkpoint_conn: Any = None  # aiosqlite.Connection | None
        self._checkpointer: Any = None
        self._graph: Any = None
        self._init_lock = asyncio.Lock()

        logger.info(
            "Orchestrator Agent initialized (graph + checkpointer will be "
            "built lazily inside the event loop on first use, db=%s)",
            _CHECKPOINT_DB_PATH,
        )

    async def _ensure_graph(self):
        """Return the compiled graph, building it on first call.

        Double-checked behind ``_init_lock`` so concurrent first-time
        requests don't race to open two DB connections.
        """
        if self._graph is None:
            async with self._init_lock:
                if self._graph is None:
                    self._checkpointer = await self._build_persistent_checkpointer()
                    self._graph = self._build_graph(self._checkpointer)
                    logger.info(
                        "Orchestrator graph built (checkpointer=%s)",
                        type(self._checkpointer).__name__,
                    )
        return self._graph

    async def _build_persistent_checkpointer(self):
        """Open an :class:`AsyncSqliteSaver` against ``_CHECKPOINT_DB_PATH``.

        Any failure (missing ``aiosqlite`` package, read-only filesystem,
        corrupt DB, ...) falls back to :class:`InMemorySaver` so a
        misconfigured environment doesn't make the whole agent unusable
        — only persistence is lost.
        """
        try:
            import aiosqlite
            _CHECKPOINT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            conn = await aiosqlite.connect(str(_CHECKPOINT_DB_PATH))
            saver = AsyncSqliteSaver(conn)
            # Older langgraph-checkpoint-sqlite versions expose an
            # async ``setup()``; newer ones create the tables lazily.
            setup = getattr(saver, "setup", None)
            if callable(setup):
                await setup()
            self._checkpoint_conn = conn
            logger.info("Opened AsyncSqliteSaver at %s", _CHECKPOINT_DB_PATH)
            return saver
        except Exception as exc:
            logger.error(
                "Failed to open AsyncSqliteSaver at %s: %s — falling back "
                "to InMemorySaver. Conversations will NOT survive a restart.",
                _CHECKPOINT_DB_PATH, exc,
            )
            self._checkpoint_conn = None
            return InMemorySaver()

    def _build_graph(self, checkpointer):
        """
            START
               │
               ▼
            resume_router
               │
               ├──────────── interrupted ───────────────┐
               │                                        │
               ▼                                        │
            intent_router                               │
               │                                        │
               ├────► chat ───────────────► END         │
               │                                        │
               ▼                                        │
            tech_proposal                               │
               │                                        │
            choose_path                                 │
               │                                        │
            parse_intent                                │
               │                                        │
            route_before_execute                        │
               ├──── upload_csv ─────► await_csv_upload │
               │                          │             │
               │                          ▼             │
               │                     profiling          │
               │                          │             │
               │                          ▼             │
               │                     parse_intent       │
               │                                        │
               ├──── clarification ─► await_clarification
               │                          │
               │                          ▼
               └────────────────────► execute_task
                                          │
                                          ▼
                                         END
        """
        builder = StateGraph(SessionState)

        builder.add_node("intent_router",self._node_intent_router)
        builder.add_node("chat",self._node_chat)
        builder.add_node("tech_proposal", self._node_tech_proposal)
        builder.add_node("choose_path", self._node_choose_path)
        builder.add_node("profiling", self._node_profiling)
        builder.add_node("parse_intent", self._node_parse_intent)
        builder.add_node("await_csv_upload", self._node_await_csv_upload)
        builder.add_node("await_clarification", self._node_await_clarification)
        builder.add_node("execute_task", self._node_execute_task)

        builder.add_edge(START, "intent_router")
        return builder.compile(checkpointer=checkpointer)

    async def process_query(
            self,
            query: str,
            session_id: str,
            resume_value: Optional[Any] = None,
            user_id: Optional[str] = None,
    ):
        try:
            graph = await self._ensure_graph()
            config = {"configurable": {"thread_id": session_id}}

            snapshot = await graph.aget_state(config)
            current_values = snapshot.values or {}

            dialogue_history = list(current_values.get("dialogue_history") or [])
            last_user_query = current_values.get("last_user_query")

            # event_log is the chronological source-of-truth for UI
            # replay (see SessionState.event_log docstring). The user's
            # message is appended HERE (as part of the graph's input
            # update) so it lands in event_log before any node runs.
            # Speaking nodes (_node_chat / _node_execute_task) and
            # _node_profiling append their own events atomically inside
            # their update dicts — see those nodes.
            event_log = list(current_values.get("event_log") or [])

            if query:
                dialogue_history.append(
                    Message(role="user", content=query)
                )
                last_user_query = query
                event_log.append({
                    "kind": "message",
                    "role": "user",
                    "content": query,
                    "ts": datetime.utcnow().isoformat(),
                })

            file_path = resume_value.get('file_path') if resume_value and resume_value.get(
                "file_path") else current_values.get("file_path")

            # Inherit user_id from the existing session when the caller
            # doesn't re-supply it (e.g. resume after interrupt). A
            # non-None caller value always wins so the API can refresh
            # it on every request.
            effective_user_id = user_id or current_values.get("user_id")

            update: Dict[str, Any] = {
                "session_id": session_id,
                "user_id": effective_user_id,
                "dialogue_history": dialogue_history,
                "event_log": event_log,
                "last_user_query": last_user_query,
                "file_path": file_path,
            }

            interrupted = bool(snapshot.next)

            # 断点回传
            if interrupted:
                input_state = Command(
                update=update if update else None,
                resume=resume_value
            )
            # initial state
            else:
                initial_state = dict(current_values)
                initial_state["session_id"] = session_id
                initial_state["user_id"] = effective_user_id
                initial_state["last_user_query"] = update.get("last_user_query")
                initial_state["dialogue_history"] = update.get("dialogue_history")
                initial_state["event_log"] = update.get("event_log")
                initial_state["file_path"] = update.get("file_path")

                input_state = initial_state

            logger.info("======== BEFORE INVOKE ========")
            logger.info("snapshot.next = %s", snapshot.next)
            # logger.debug("snapshot.values = %s", snapshot.values)
            logger.info("input_state = %s", input_state)

            # result = await self.graph.ainvoke(input_state, config=config)

            # Stream tokens + artifact diffs to the UI.
            #
            # NOTE: we NO LONGER buffer assistant text or persist event_log
            # from here. Persisting state via ``aupdate_state`` AFTER the
            # stream ends breaks the suspended-task info on an interrupted
            # graph — the new checkpoint looks completed, so the user's
            # next "resume" actually restarts the graph from scratch and
            # the interrupt fires a second time (duplicate clarification
            # panel, etc.).
            #
            # Instead, each "speaking" node (chat / execute_task) and
            # ``_node_profiling`` append to ``event_log`` /
            # ``dialogue_history`` ATOMICALLY inside their own update
            # dict — see those nodes for the writes. ``process_query``
            # is now purely a stream forwarder + the final yield.
            async for mode, chunk in graph.astream(
                    input_state,
                    config=config,
                    stream_mode=["messages", "updates", "custom"],
            ):

                if mode == "custom":
                    if isinstance(chunk, dict) and chunk.get("event") == "anomaly_training_progress":
                        yield {
                            "type": "anomaly_training_progress",
                            "data": chunk,
                        }

                elif mode == "messages":
                    message, metadata = chunk

                    md = metadata or {}

                    # 0) Drop ToolMessage instances entirely.
                    # Sub-agents (ProfileAgent / analysis agents / ...) are
                    # built with langchain's `create_agent`, which is itself a
                    # LangGraph sub-graph with internal nodes named "agent"
                    # and "tools". When such a sub-agent is invoked from a
                    # parent node (e.g. _node_profiling), the tool results
                    # bubble up to this stream as ToolMessages whose
                    # `langgraph_node` metadata points at the sub-graph's
                    # "tools" node — NOT at "profiling" — so the
                    # `_INTERNAL_NODES` check below does not catch them.
                    # Tool results are internal scratchpad data and must
                    # never reach the chat UI.
                    if isinstance(message, ToolMessage):
                        continue

                    # 1) Blacklist internal classifier / parser nodes whose
                    #    structured-output preambles should never reach the UI.
                    node_name = md.get("langgraph_node")
                    if node_name in _INTERNAL_NODES:
                        continue

                    # 2) Drop any LLM call tagged "structured_output" (set by
                    #    BaseAgent.invoke_structured via RunnableConfig.tags).
                    #    These calls stream a "Returning structured response:"
                    #    preamble plus the JSON/repr body across many chunks;
                    #    tag-based filtering catches ALL of them reliably.
                    tags = md.get("tags") or []
                    if isinstance(tags, (list, tuple)) and "structured_output" in tags:
                        continue

                    # 3) Skip empty chunks and tool-call-only messages.
                    content = getattr(message, "content", None)
                    if not content:
                        continue

                    # 4) Defensive substring guard: catches chunks whose tag
                    #    was lost (e.g. when an older sub-agent didn't set it).
                    if isinstance(content, str) and "Returning structured response" in content:
                        continue

                    yield {
                        "type": "token",
                        "content": content,
                    }

                # elif mode == "updates":
                #     yield {
                #         "type": "update",
                #         "data": chunk,
                #     }
                elif mode == "updates":
                    # The updates stream yields state diffs per node:
                    #   {node_name: {field: value, ...}}
                    # We only forward the csv_preview / anomaly_chart diffs
                    # so the frontend charts appear the instant profiling /
                    # anomaly-detection finishes — without leaking the rest
                    # of the state noise (intermediate enums,
                    # planned_workflow, ...).
                    #
                    # event_log updates emitted by nodes are deliberately
                    # ignored here: the node already atomically updated
                    # event_log in its own state write, and the frontend
                    # doesn't need a live stream of event_log entries
                    # (it's a replay-only structure read on demand via
                    # /api/sessions/{id}/messages).
                    if not isinstance(chunk, dict):
                        continue
                    for _node_name, state_diff in chunk.items():
                        if not isinstance(state_diff, dict):
                            continue
                        preview = state_diff.get("csv_preview")
                        if preview:
                            yield {
                                "type": "csv_preview",
                                "data": preview,
                            }
                        chart = state_diff.get("anomaly_chart")
                        if chart:
                            yield {
                                "type": "anomaly_chart",
                                "data": chart,
                            }
                        analysis_chart = state_diff.get("analysis_chart")
                        if analysis_chart:
                            yield {
                                "type": "analysis_chart",
                                "data": analysis_chart,
                            }
                        prediction_chart = state_diff.get("prediction_chart")
                        if prediction_chart:
                            yield {
                                "type": "prediction_chart",
                                "data": prediction_chart,
                            }

            snapshot = await graph.aget_state(config)

            # Refresh the per-user session index so the sidebar history
            # list picks this thread up. Reads dialogue_history straight
            # from the post-stream snapshot — the speaking nodes have
            # already appended their assistant messages.
            try:
                from session_store import upsert_session
                upsert_session(
                    user_id=effective_user_id or "user_anonymous",
                    session_id=session_id,
                    dialogue_history=snapshot.values.get("dialogue_history") if snapshot else None,
                )
            except Exception as exc:
                logger.warning("session_index upsert failed: %s", exc)

            if snapshot.next:
                yield {
                    "type": "interrupt",
                    "data": snapshot.tasks[0].interrupts[0].value
                }
            else:
                state = snapshot.values
                yield {
                    "type": "completed",
                    "data": state
                }

        except Exception as e:
            logger.error(f"Error processing query: {str(e)}", exc_info=True)

    # ------------------------------------------------------------------ #
    # Session-level helpers (used by /api/session/{id} & /reset endpoints)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _enum_value(value: Any) -> Any:
        """Return .value for Enum instances, otherwise the value itself."""
        if value is None:
            return None
        if hasattr(value, "value") and hasattr(value, "name"):
            return value.value
        return value

    def _build_session_info(
        self,
        session_id: str,
        snapshot: Any,
    ) -> Optional[Dict[str, Any]]:
        """
        Convert a LangGraph StateSnapshot into the SessionInfo dict shape
        expected by the frontend (`frontend/src/types/index.ts`).

        Returns None when there is no checkpoint for the thread.
        """
        if snapshot is None:
            return None

        values = snapshot.values or {}
        if not values:
            # No state has been written yet for this thread.
            return None

        current_stage = self._enum_value(values.get("current_stage")) or ""
        task_type = self._enum_value(values.get("task_type"))
        csv_profile = values.get("csv_profile")
        confirmed_spec = values.get("confirmed_spec")
        dialogue_history = values.get("dialogue_history") or []
        execution_results = values.get("execution_results")

        # clarification_pending: True when the graph is paused inside the
        # await_clarification node (snapshot.next is non-empty) OR the
        # current stage is the clarification stage.
        next_nodes = list(snapshot.next or [])
        clarification_pending = (
            "await_clarification" in next_nodes
            or current_stage == TaskStage.CLARIFICATION.value
        )

        # analysis_artifacts_count: the current schema only stores a single
        # serialized `execution_results` blob, so expose 1 when present.
        analysis_artifacts_count = 1 if execution_results else 0

        created_at = values.get("created_at")
        updated_at = values.get("updated_at")
        now = datetime.utcnow().isoformat()

        return {
            "session_id": session_id,
            "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else (created_at or now),
            "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else (updated_at or now),
            "is_active": bool(values.get("is_active", True)),
            "current_task": task_type,
            "current_stage": current_stage,
            "has_csv_profile": csv_profile is not None,
            "has_confirmed_spec": confirmed_spec is not None,
            "dialogue_turns": len(dialogue_history),
            "clarification_pending": clarification_pending,
            "analysis_artifacts_count": analysis_artifacts_count,
        }

    async def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Read the latest checkpointed state for ``session_id`` and
        return a SessionInfo dict (or None if the thread is unknown).

        Now async because the underlying ``AsyncSqliteSaver`` only
        implements ``aget_state`` — the sync ``get_state`` raises
        ``NotImplementedError``.
        """
        config = {"configurable": {"thread_id": session_id}}
        try:
            graph = await self._ensure_graph()
            snapshot = await graph.aget_state(config)
        except Exception as e:
            logger.error(f"get_session_info: failed to read state for %s: %s", session_id, e)
            return None
        return self._build_session_info(session_id, snapshot)

    async def get_session_messages(
        self, session_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Return the stored transcript + visual artifacts for
        ``session_id``.

        Shape::

            {
              "messages": [{"role": ..., "content": ...}, ...],   # text-only
              "artifacts": {csv_preview, anomaly_chart, ...},     # latest-of-each
              "events":   [{kind, role?, content?, data?, ts?}, ...],
            }

        ``events`` is the chronological source-of-truth for UI replay:
        user messages, assistant responses, csv_preview cards and chart
        cards in the exact order they originally appeared. The frontend
        prefers this field when non-empty; ``messages`` + ``artifacts``
        are kept as a fallback for older sessions that pre-date
        ``event_log``.

        Returns ``None`` when no checkpoint exists for the thread.
        """
        config = {"configurable": {"thread_id": session_id}}
        try:
            graph = await self._ensure_graph()
            snapshot = await graph.aget_state(config)
        except Exception as e:
            logger.error(
                "get_session_messages: failed to read state for %s: %s",
                session_id, e,
            )
            return None

        if snapshot is None or not snapshot.values:
            return None

        values = snapshot.values
        history = values.get("dialogue_history") or []
        out: List[Dict[str, Any]] = []
        for m in history:
            role = self._msg_field(m, "role")
            content = self._msg_field(m, "content")
            if role is None and content is None:
                continue
            out.append({"role": role, "content": content})

        # Coerce artifact values to plain JSON-friendly dicts. Pydantic
        # models are dumped via model_dump so FastAPI's JSON encoder
        # doesn't have to guess.
        def _to_jsonable(v: Any) -> Any:
            if v is None:
                return None
            if hasattr(v, "model_dump") and callable(v.model_dump):
                try:
                    return v.model_dump(mode="json")
                except Exception:
                    pass
            if hasattr(v, "dict") and callable(v.dict) and not isinstance(v, type):
                try:
                    return v.dict()
                except Exception:
                    pass
            return v

        # event_log entries already have the right shape, just coerce
        # any pydantic values inside.
        raw_events = values.get("event_log") or []
        events: List[Dict[str, Any]] = []
        for e in raw_events:
            if not isinstance(e, dict):
                continue
            events.append({
                "kind": e.get("kind"),
                "role": e.get("role"),
                "content": e.get("content"),
                "data": _to_jsonable(e.get("data")),
                "ts": e.get("ts"),
            })

        return {
            "messages": out,
            "artifacts": {
                "csv_preview":      _to_jsonable(values.get("csv_preview")),
                "anomaly_chart":    _to_jsonable(values.get("anomaly_chart")),
                "analysis_chart":   _to_jsonable(values.get("analysis_chart")),
                "prediction_chart": _to_jsonable(values.get("prediction_chart")),
            },
            "events": events,
        }

    async def delete_session_state(self, session_id: str) -> int:
        """Delete all checkpoint rows for ``session_id`` from the
        underlying saver. Returns the number of rows removed (best
        effort). Used by the ``DELETE /api/sessions/{id}`` endpoint
        after the session_index row has been removed.

        Uses the same code path as :meth:`reset_session_task` so both
        InMemorySaver and AsyncSqliteSaver are handled uniformly.
        """
        return await self._clear_thread(session_id)

    async def reset_session_task(self, session_id: str) -> Dict[str, Any]:
        """
        Clear the LangGraph checkpoint state for a thread so the next
        /api/query starts a fresh workflow.

        Works against both ``InMemorySaver`` (in-process dict) and
        ``AsyncSqliteSaver`` (on-disk tables). For the SQLite case we
        DELETE the thread's rows from both the ``checkpoints`` and
        ``writes`` tables via async ``aiosqlite`` calls.
        """
        removed = await self._clear_thread(session_id)
        logger.info(
            "reset_session_task: session=%s removed_checkpoints=%d",
            session_id, removed,
        )
        return {
            "success": True,
            "session_id": session_id,
            "message": "会话状态已重置" if removed else "无可重置的会话状态",
            "cleared_checkpoints": removed,
        }

    async def _clear_thread(self, session_id: str) -> int:
        """Shared helper: drop every checkpoint row for ``session_id``
        from whichever saver is active. Returns the number of rows /
        entries removed (best effort)."""
        checkpointer = self._checkpointer
        removed = 0
        if checkpointer is None:
            # Graph not built yet → nothing to clear.
            return 0

        # InMemorySaver path: drop every key belonging to this thread.
        storage = getattr(checkpointer, "storage", None)
        if isinstance(storage, dict):
            keys_to_remove = [
                k for k in list(storage.keys())
                if self._key_thread_id(k) == session_id
            ]
            for k in keys_to_remove:
                del storage[k]
                removed += 1

        writes = getattr(checkpointer, "writes", None)
        if isinstance(writes, dict):
            keys_to_remove = [
                k for k in list(writes.keys())
                if self._key_thread_id(k) == session_id
            ]
            for k in keys_to_remove:
                del writes[k]

        # AsyncSqliteSaver path: async DELETE on the checkpoint tables.
        # ``self._checkpoint_conn`` is an ``aiosqlite.Connection`` when
        # the saver opened successfully, else ``None``.
        conn = self._checkpoint_conn
        if conn is not None and not isinstance(checkpointer, InMemorySaver):
            removed = await self._asql_clear_thread(conn, session_id, removed)

        return removed

    @staticmethod
    async def _asql_clear_thread(
        conn: Any, session_id: str, removed: int,
    ) -> int:
        """Async best-effort DELETE of a thread's checkpoint rows.

        ``conn`` is the long-lived ``aiosqlite.Connection`` shared with
        ``AsyncSqliteSaver``. We must NOT wrap it in ``async with conn:``
        — that pattern calls ``Connection.__await__`` which tries to
        start the worker thread, and aiosqlite refuses with "threads can
        only be started once" because the saver already started it at
        construction time. Just call ``execute`` / ``commit`` directly.
        """
        try:
            for table in ("checkpoints", "writes"):
                try:
                    cur = await conn.execute(
                        f"DELETE FROM {table} WHERE thread_id = ?",
                        (session_id,),
                    )
                    removed += cur.rowcount or 0
                    # Close cursor defensively — aiosqlite keeps
                    # statement state in its worker thread.
                    try:
                        await cur.close()
                    except Exception:
                        pass
                except sqlite3.Error as e:
                    logger.debug(
                        "_asql_clear_thread: %s delete skipped: %s", table, e,
                    )
            # aiosqlite defaults to autocommit=OFF (inherits sqlite3's
            # deferred transaction semantics), so commit explicitly to
            # actually persist the DELETEs.
            await conn.commit()
        except sqlite3.Error as e:
            logger.warning("_asql_clear_thread: sqlite clear failed: %s", e)
        return removed

    @staticmethod
    def _key_thread_id(key: Any) -> Optional[str]:
        """Best-effort extraction of thread_id from a checkpointer storage key."""
        if isinstance(key, tuple) and key:
            return key[0]
        if isinstance(key, dict):
            return key.get("thread_id")
        return None

    @staticmethod
    def _msg_field(msg: Any, field: str) -> Any:
        """Read ``role`` / ``content`` from a dialogue_history entry that
        may be a pydantic ``Message``, a plain dict, or anything else
        exposing those attributes. Returns ``None`` when not available."""
        if msg is None:
            return None
        if isinstance(msg, dict):
            return msg.get(field)
        return getattr(msg, field, None)

    async def _node_intent_router(
            self,
            state: SessionState
    ):
        logger.info("intent_router start")

        result = await self.intent_router_agent.classify(
            user_query=state.last_user_query,
            thread_id=state.session_id,
            current_stage=state.current_stage,
            task_type=state.task_type,
            dialogue_history=state.dialogue_history,

        )

        logger.info(
            "intent_router result: intent=%s skip_proposal=%s task_type_hint=%s",
            result.intent, result.skip_proposal, result.task_type_hint,
        )

        update = {
            "current_stage": TaskStage.Router,
            "intent_type": result.intent,
            "task_type": result.task_type_hint or state.task_type,
        }

        target = None

        # 普通聊天（任何时候命中都直接走 chat）
        if result.intent == IntentType.CHAT:
            target = "chat"
        # 执行完成后的后续跟进快速通道：仅当上一轮已经到 EXECUTION 时启用
        elif state.current_stage == TaskStage.EXECUTION:
            followup_routing = {
                IntentType.SWITCH_TOOL: "execute_task",
                IntentType.NEW_FILE: "profiling",
                IntentType.CHANGE_TASK: "choose_path" if state.proposal_paths else "execute_task",
                IntentType.CHANGE_MAPPING: "await_clarification",
            }
            target = followup_routing.get(result.intent)
            if target is not None:
                logger.info("followup fast-path: %s -> %s", result.intent, target)

        # 首轮新任务 / 兜底：跳过 / 不跳过技术方案
        if target is None:
            if result.skip_proposal:
                target = "parse_intent"
            else:
                target = "tech_proposal"

        planned_workflow = list(_NODE_WORKFLOW_PLAN.get(target, []))
        update["planned_workflow"] = planned_workflow
        logger.info("planned workflow (todo): %s", " -> ".join(planned_workflow))

        return Command(update=update, goto=target)

    def _advance_workflow(self, state: SessionState, stage: str) -> List[str]:
        """
        planned_workflow 中的指定阶段标记为已完成（前缀 ✓），返回新列表。
        """
        workflow = list(state.planned_workflow)
        for i, item in enumerate(workflow):
            if item == stage:
                workflow[i] = f"✓ {stage}"
                pending = [x for x in workflow if not x.startswith("✓ ")]
                logger.info(
                    "workflow progress: %s | pending: %s",
                    " -> ".join(workflow),
                    " -> ".join(pending) if pending else "(none)",
                )
                break
        return workflow

    async def _node_chat(
            self,
            state: SessionState
    ):
        logger.info("chat start")
        answer = await self.chat_agent.chat(
            user_query=state.last_user_query,
            thread_id=state.session_id,
        )

        # Persist the assistant's reply into BOTH dialogue_history (LLM
        # context for future turns) AND event_log (UI replay log) right
        # here, atomically as part of this node's state update. Doing
        # this inside the node — instead of in process_query after the
        # stream — avoids the "aupdate_state on an interrupted graph
        # breaks the suspended task" trap that was causing duplicate
        # clarification panels.
        ts = datetime.utcnow().isoformat()
        new_dialogue = list(state.dialogue_history or [])
        new_dialogue.append(Message(role="assistant", content=answer))

        new_event_log = list(state.event_log or [])
        new_event_log.append({
            "kind": "message",
            "role": "assistant",
            "content": answer,
            "ts": ts,
        })

        update = {
            "current_stage": TaskStage.CHAT,
            "chat_response": answer,
            "dialogue_history": new_dialogue,
            "event_log": new_event_log,
            "planned_workflow": self._advance_workflow(state, "闲聊响应"),
        }

        return Command(
            update=update,
            goto=END,
        )

    async def _node_tech_proposal(
            self,
            state: SessionState
    ):
        logger.info("tech_proposal node start")
        session_id = state.session_id
        query = state.last_user_query

        proposal = await self.proposal_agent.generate_tech_proposal(
            user_query=query,
            thread_id=session_id,
        )
        if proposal is None:
            raise RuntimeError("Failed to generate tech proposal")

        update = {
            "current_stage": TaskStage.Proposal,
            "proposal_text": proposal.get("proposal_text"),
            "proposal_paths": proposal.get("proposal_paths"),
            "planned_workflow": self._advance_workflow(state, "技术方案生成"),
        }

        return Command(
            update=update,
            goto="choose_path",
        )

    async def _node_choose_path(
            self,
            state: SessionState
    ):
        logger.info("choose_path node start")
        selected = interrupt({
            "type": "choose_tech_path",
            "message": "请选择一个技术路径继续执行",
            "paths": state.proposal_paths,
        })

        selected_path_id = selected.get("path_id")
        selected_path = next(
            (p for p in state.proposal_paths if p.path_id == selected_path_id),
            None
        )

        if selected_path is None:
            raise ValueError(f"Invalid selected path_id: {selected_path_id}")

        update = {
            "task_type": selected_path.model_type,
            "selected_path": selected_path,  # .model_dump(),
            "planned_workflow": self._advance_workflow(state, "技术方案选择"),
        }

        return Command(
            update=update,
            goto="parse_intent",
        )

    async def _node_profiling(
            self,
            state: SessionState
    ):
        logger.info("profiling node start")
        if state.file_path:
            result = await self.profile_agent.profile_csv_file(
                file_path=state.file_path,
                thread_id=state.session_id,
            )

            try:
                preview = build_csv_preview(state.file_path, csv_profile=result)
            except Exception as e:
                logger.warning("csv_preview build failed: %s", e, exc_info=True)
                preview = None

            # Append the csv_preview event to event_log atomically so
            # history replay shows the preview card in its original
            # chronological position (right after profiling ran).
            new_event_log = list(state.event_log or [])
            if preview:
                new_event_log.append({
                    "kind": "csv_preview",
                    "data": preview,
                    "ts": datetime.utcnow().isoformat(),
                })

            update = {
                "current_stage": TaskStage.PROFILING,
                "csv_profile": result,
                "csv_preview": preview,
                "event_log": new_event_log,
                "planned_workflow": self._advance_workflow(state, "数据画像"),
            }

            return Command(
                update=update,
                goto="parse_intent",
            )

    async def _node_parse_intent(
            self,
            state: SessionState
    ):
        logger.info("parse_intent node start")
        spec = await self.parser_agent.generate_task_spec(
            user_query=state.last_user_query,
            thread_id=state.session_id,
            tech_proposal=state.selected_path,
            csv_profile=state.csv_profile,
            task_type=state.task_type,
        )

        if spec is None:
            raise RuntimeError("ParserAgent returned None")

        update = {
            "current_stage": TaskStage.Parse,
            "confirmed_spec": spec,
            "planned_workflow": self._advance_workflow(state, "文件参数解析"),
        }

        if not state.file_path:
            return Command(
                update=update,
                goto="await_csv_upload",
            )

            # ② 已上传文件但还没有画像
        if state.csv_profile is None:
            return Command(
                update=update,
                goto="profiling",
            )

        # ③ 参数默认需要澄清
        return Command(
            update=update,
            goto="await_clarification",
        )

    async def _node_await_csv_upload(self, state: SessionState):
        # 仅在异常检测任务下暴露模型选择器；其它任务（预测/分析）保持
        # 原有行为，前端凭 allow_model 决定是否渲染 ModelPicker。
        allow_model = state.task_type == TaskType.ANOMALY_DETECTION

        uploaded = interrupt({
            "type": "upload_csv",
            "message": "当前任务执行前必须上传 CSV 文件，请先上传数据文件后继续。",
            "hint": "上传完成后，请将 file_path 回传，或由后端更新会话状态后继续。",
            "allow_model": allow_model,
            "current_task_type": (
                state.task_type.value if state.task_type is not None else None
            ),
        })

        update: Dict[str, Any] = {
            "file_path": uploaded["file_path"],
        }

        # 用户在前端选择了复用模型时，把跨作用域坐标打包进 ModelRef
        # 持久化到 SessionState，供执行节点透传给 anomaly_agent。
        # user_id 不在此处携带——resolve_model_path 永远从当前 runtime
        # 取，保证用户隔离不被击穿。
        save_name = uploaded.get("save_name")
        if save_name:
            update["selected_model_ref"] = ModelRef(
                save_name=save_name,
                thread_id=uploaded.get("model_thread_id"),
                source_file=uploaded.get("model_source_file"),
                detector_name=uploaded.get("detector_name"),
            )
        else:
            # 显式清空：上一轮可能选过模型，本轮没选就要重置。
            update["selected_model_ref"] = None

        return Command(
            update=update,
            goto="profiling",
        )

    async def _node_await_clarification(self, state: SessionState):
        """
           Ask user for confirm information.
           interrupt return
           {
              "target_columns": [
                {
                  "semantic_name": "温度",
                  "csv_column": "Temp"
                }
              ],
              "feature_columns": [
                {
                  "semantic_name": "压力",
                  "csv_column": "Press"
                }
              ]
            }
        """
        logger.info("await_clarification node start")

        payload = {
            "type": "clarification",
            "feature_columns": getattr(state.confirmed_spec, "feature_columns", None),
            "target_columns": getattr(state.confirmed_spec, "target_columns", None),
            "candidate_columns": state.csv_profile.numeric_columns,
            "hint": "请补全/确认映射关系，并将已确认项的 status 置为 mapped 后再返回",
        }

        updated_spec = interrupt(payload)

        if updated_spec is None:
            raise RuntimeError(
                "clarification_answer is empty"
            )

        if not isinstance(updated_spec, dict):
            raise RuntimeError(
                f"Invalid clarification result: {type(updated_spec)}"
            )

        new_confirmed_spec = state.confirmed_spec.apply_mapping(updated_spec)

        update = {
            "current_stage": TaskStage.CLARIFICATION,
            "confirmed_spec": new_confirmed_spec,
            "planned_workflow": self._advance_workflow(state, "文件字段澄清"),
        }

        return Command(
            update=update,
            goto="execute_task",
        )

    async def _node_execute_task(self, state: SessionState):
        """
            Execute task based on confirmed spec.
        """
        logger.info("execute_task node start")
        task_spec = state.confirmed_spec
        if task_spec is None:
            raise ValueError("confirmed_spec is missing")

        if state.csv_profile is None:
            raise ValueError("csv_profile is missing")

        file_path = state.file_path
        if not file_path:
            raise ValueError("csv_profile.file_path is missing")

        session_id = state.session_id
        user_id = state.user_id
        task_type = state.task_type

        # 任务路由
        new_tool_calls: List[Dict[str, Any]] = []
        if task_type == TaskType.ANALYSIS:
            result = await self.analysis_agent.execute_analysis(
                file_path=file_path,
                thread_id=session_id,
                task_spec=task_spec,
                user_query=state.last_user_query,
                tech_proposal=state.selected_path,
                csv_profile=state.csv_profile,
                user_id=user_id,
                dialogue_history=state.dialogue_history,
            )

            if isinstance(result, dict):
                analysis_chart = result.get("chart")
                result_text = result.get("text") or ""
                new_tool_calls = list(result.get("tool_calls") or [])
            else:
                analysis_chart = None
                result_text = result

        elif task_type == TaskType.PREDICTION:
            result = await self.prediction_agent.execute_prediction(
                file_path=file_path,
                thread_id=session_id,
                task_spec=task_spec,
                user_query=state.last_user_query,
                tech_proposal=state.selected_path,
                csv_profile=state.csv_profile,
                user_id=user_id,
                dialogue_history=state.dialogue_history,
            )

            if isinstance(result, dict):
                prediction_chart = result.get("chart")
                result_text = result.get("text") or ""
                new_tool_calls = list(result.get("tool_calls") or [])
            else:
                prediction_chart = None
                result_text = result

        elif task_type == TaskType.ANOMALY_DETECTION:
            # This node owns the outer graph stream. The anomaly agent below
            # runs a separate create_agent graph via invoke(), so LangGraph
            # cannot automatically bubble its custom events to this stream.
            # Pass the outer writer through the framework context explicitly.
            from langgraph.config import get_stream_writer
            stream_writer = get_stream_writer()
            result = await self.anomaly_agent.execute_anomaly_detection(
                file_path=file_path,
                thread_id=session_id,
                task_spec=task_spec,
                user_query=state.last_user_query,
                tech_proposal=state.selected_path,
                csv_profile=state.csv_profile,
                user_id=user_id,
                dialogue_history=state.dialogue_history,
                selected_model_ref=state.selected_model_ref,
                stream_writer=stream_writer,
            )

            if isinstance(result, dict):
                anomaly_chart = result.get("chart")
                result_text = result.get("text") or ""
                new_tool_calls = list(result.get("tool_calls") or [])
            else:
                anomaly_chart = None
                result_text = result

        # elif task_type == TaskType.MONITORING:
        #     result = await self.monitoring_agent.execute_monitoring(
        #         file_path=file_path,
        #         task_spec=task_spec,
        #         thread_id=session_id,
        #     )
        else:
            raise ValueError(f"Unsupported task type: {task_type}")


        if task_type == TaskType.ANOMALY_DETECTION:
            execution_text = result_text
            anomaly_chart_payload = anomaly_chart
            analysis_chart_payload = None
            prediction_chart_payload = None
        elif task_type == TaskType.ANALYSIS:
            execution_text = result_text
            anomaly_chart_payload = None
            analysis_chart_payload = analysis_chart
            prediction_chart_payload = None
        elif task_type == TaskType.PREDICTION:
            execution_text = result_text
            anomaly_chart_payload = None
            analysis_chart_payload = None
            prediction_chart_payload = prediction_chart
        else:
            execution_text = result
            anomaly_chart_payload = None
            analysis_chart_payload = None
            prediction_chart_payload = None

        merged_tool_calls: List[Dict[str, Any]] = (
            list(state.tool_calls or []) + new_tool_calls
        )

        # Persist this node's outputs atomically:
        # - dialogue_history gets the assistant's text response (LLM
        #   context for future turns).
        # - event_log gets the assistant text FIRST, then any charts,
        #   so history replay shows the LLM's narration followed by the
        #   visualisation — matching the live UX.
        # Doing this inside the node (not via aupdate_state from
        # process_query) keeps it safe with respect to interrupts on
        # OTHER branches of the same graph.
        ts = datetime.utcnow().isoformat()
        new_dialogue = list(state.dialogue_history or [])
        if execution_text:
            new_dialogue.append(Message(role="assistant", content=execution_text))

        new_event_log = list(state.event_log or [])
        if execution_text:
            new_event_log.append({
                "kind": "message",
                "role": "assistant",
                "content": execution_text,
                "ts": ts,
            })
        if anomaly_chart_payload:
            new_event_log.append({
                "kind": "anomaly_chart",
                "data": anomaly_chart_payload,
                "ts": ts,
            })
        if analysis_chart_payload:
            new_event_log.append({
                "kind": "analysis_chart",
                "data": analysis_chart_payload,
                "ts": ts,
            })
        if prediction_chart_payload:
            new_event_log.append({
                "kind": "prediction_chart",
                "data": prediction_chart_payload,
                "ts": ts,
            })

        update = {
            "execution_results": execution_text,
            "anomaly_chart": anomaly_chart_payload,
            "analysis_chart": analysis_chart_payload,
            "prediction_chart": prediction_chart_payload,
            "tool_calls": merged_tool_calls,
            "current_stage": TaskStage.EXECUTION,
            "dialogue_history": new_dialogue,
            "event_log": new_event_log,
            "planned_workflow": self._advance_workflow(state, "技术方案执行"),
        }

        return Command(
            update=update,
            goto=END
        )
