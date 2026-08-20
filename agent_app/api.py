"""
API interface for Industrial Time Series Agent System.

This module provides a REST API for interacting with the multi-agent system
using FastAPI framework.
"""

import asyncio
import contextlib
import os
import re
import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Header, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from models.schemas import QueryResponse
import uvicorn

from main import IndustrialTimeSeriesAgent
from config.settings import settings
from utils.helpers import validate_existing_file_name, validate_file_path

import warnings
warnings.filterwarnings("ignore", category=UserWarning)


def _json_default(obj):
    """JSON serializer for objects not serializable by the default encoder.

    The agent's graph state and interrupt payloads frequently contain
    Pydantic models (TechPath, TaskSpec, CSVProfile, ...), Enums, and
    datetimes. Using `default=str` turns each Pydantic object into its
    Python repr string (e.g. "TechPath(path_id='...', title='...')"),
    which the frontend cannot parse back into structured fields.

    This serializer instead recursively dumps Pydantic models to plain
    dicts/lists so the NDJSON stream carries real structured data.
    """
    # Pydantic v2
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        try:
            return obj.model_dump(mode="json")
        except Exception:
            pass
    # Pydantic v1
    if hasattr(obj, "dict") and callable(obj.dict) and not isinstance(obj, type):
        try:
            return obj.dict()
        except Exception:
            pass
    # Enum
    if hasattr(obj, "value") and hasattr(obj, "name"):
        return obj.value
    # datetime / date / time / timedelta
    if hasattr(obj, "isoformat") and callable(obj.isoformat):
        return obj.isoformat()
    # UUID
    if hasattr(obj, "hex") and hasattr(obj, "int"):
        return str(obj)
    # Last resort
    return str(obj)


# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="工业时间序列多智能体系统 API",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the agent system
agent = IndustrialTimeSeriesAgent()

# Keep graph executions alive when the HTTP consumer disappears (browser
# refresh, Stop button, laptop network transition, ...).  Cancelling a
# LangGraph ``astream`` between checkpoint writes can leave a thread with
# pending tasks but no real ``interrupt()`` payload.  The next turn then sees
# an incomplete run and either resumes the wrong node or closes without a
# terminal event.  A running asyncio task is cheap to retain here, and the
# done callback removes it as soon as the graph reaches a durable terminal or
# business-interrupt checkpoint.
_detached_query_tasks: set[asyncio.Task[Any]] = set()
_detached_query_tasks_by_session: dict[str, set[asyncio.Task[Any]]] = {}


def _retain_detached_query_task(task: asyncio.Task[Any], session_id: str) -> None:
    """Retain and observe a query task after its client disconnects."""
    _detached_query_tasks.add(task)
    _detached_query_tasks_by_session.setdefault(session_id, set()).add(task)

    def _finished(done: asyncio.Task[Any]) -> None:
        _detached_query_tasks.discard(done)
        session_tasks = _detached_query_tasks_by_session.get(session_id)
        if session_tasks is not None:
            session_tasks.discard(done)
            if not session_tasks:
                _detached_query_tasks_by_session.pop(session_id, None)
        try:
            done.result()
        except asyncio.CancelledError:
            logger.warning("Detached query task was cancelled [%s]", session_id)
        except Exception:
            logger.exception("Detached query task failed [%s]", session_id)

    task.add_done_callback(_finished)


async def _wait_for_detached_query_tasks(session_id: str) -> None:
    """Serialize a new turn behind a disconnected turn for one session."""
    pending = tuple(_detached_query_tasks_by_session.get(session_id, ()))
    if not pending:
        return
    logger.info(
        "Waiting for %d detached query task(s) before next turn [%s]",
        len(pending),
        session_id,
    )
    await asyncio.gather(*pending, return_exceptions=True)


class StandardResponse(BaseModel):
    """Standard response model."""
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
    timestamp: float
    data: Optional[Dict[str, Any]] = None


class SessionInfoResponse(BaseModel):
    """Session information response model."""
    session_id: str
    created_at: str
    updated_at: str
    is_active: bool
    current_task: Optional[str]
    current_stage: str
    has_csv_profile: bool
    has_confirmed_spec: bool
    dialogue_turns: int
    clarification_pending: bool
    analysis_artifacts_count: int


# Root endpoint
@app.get("/", response_model=Dict[str, Any])
async def index():
    """
    Root endpoint with API information.

    Returns:
        API information including available endpoints
    """
    return {
        'name': settings.app_name,
        'version': settings.version,
        'status': 'running',
        'endpoints': {
            'POST /api/query': 'Process a user query (streaming, supports file upload, existing_file_name reuse & resume_value)',
            'GET /api/session/{session_id}': 'Get session information (stage / task / profile flags)',
            'DELETE /api/session/{session_id}/reset': 'Reset the session state so the next query starts fresh',
            'GET /api/sessions': 'List all conversation threads owned by the current user',
            'GET /api/sessions/{session_id}/messages': 'Get the stored dialogue history for a session',
            'DELETE /api/sessions/{session_id}': 'Delete a conversation thread (index + checkpoint state)',
            'GET /api/datasets': 'List all uploaded data files',
            'GET /api/models': 'List anomaly-detection and fine-tuned prediction models',
            'GET /health': 'Health check endpoint',
        },
        'documentation': {
            'swagger': '/docs',
            'redoc': '/redoc'
        }
    }


# Query processing endpoint
@app.post("/api/query")
async def process_query(
    query: Optional[str] = Form(None, description="User's query in natural language"),
    application_id: Optional[str] = Form(
        None, description="Optional structured agent-application identifier",
    ),
    application_params: Optional[str] = Form(
        None, description="JSON parameters for the selected agent application",
    ),
    file: UploadFile | None = File(None, description="CSV file to upload for analysis"),
    existing_file_name: Optional[str] = Form(
        None,
        description="Re-use a previously uploaded file. "
                    "Must be the on-disk filename within uploads/<user_id>/.",
    ),
    session_id: str = Form(..., description="Session ID (required)"),
    resume_value: Optional[str] = Form(None, description="JSON string used to resume from graph interrupt"),
    x_user_id: Optional[str] = Header(
        None, alias="X-User-Id",
        description="Owner identity. Namespaces uploads + model artifacts.",
    ),
):
    """
    Process a user query.
    """
    try:
        file_path = None
        parsed_resume_value: Any = None
        user_id = _sanitize_user_id(x_user_id)

        if application_id:
            try:
                from applications import build_application_query

                raw_application_params = (
                    json.loads(application_params) if application_params else {}
                )
                if not isinstance(raw_application_params, dict):
                    raise ValueError("application_params must be a JSON object")
                query = build_application_query(application_id, raw_application_params)
            except (json.JSONDecodeError, ValueError) as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid agent application request: {exc}",
                ) from exc

        if resume_value:
            try:
                parsed_resume_value = json.loads(resume_value)
            except json.JSONDecodeError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid resume_value JSON: {str(e)}"
                )

        if file is not None and file.filename:
            uploads_dir = "uploads"
            user_uploads_dir = os.path.join(uploads_dir, user_id)
            os.makedirs(user_uploads_dir, exist_ok=True)

            file_ext = os.path.splitext(file.filename)[1].lower()
            allowed_extensions = [".csv", ".xlsx", ".parquet"]

            if file_ext not in allowed_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file format. Allowed formats: {', '.join(allowed_extensions)}"
                )

            safe_filename = f"{session_id}_{file.filename}"
            file_path = os.path.join(user_uploads_dir, safe_filename)

            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)

            is_valid, error = validate_file_path(file_path)
            if not is_valid:
                if os.path.exists(file_path):
                    os.remove(file_path)
                raise HTTPException(
                    status_code=400,
                    detail=f"File validation failed: {error}"
                )

            logger.info(f"File uploaded successfully: {file_path}")

            if parsed_resume_value is None:
                parsed_resume_value = {}

            parsed_resume_value["file_path"] = file_path

        elif existing_file_name:
            # Re-use a previously uploaded file from this user's uploads
            # directory. ``file`` always wins when both are supplied, so
            # this branch only fires for "select from history" requests.
            #
            # Three layers of defence against path traversal / cross-user
            # access:
            #   1. reject path syntax while allowing Unicode filenames
            #   2. ``basename`` is retained as defence in depth
            #   3. ``realpath`` boundary check ensures the resolved path
            #      stays inside ``uploads/<user_id>/`` (blocks symlinks
            #      and any residual ``..`` tricks).
            raw_name = existing_file_name.strip()
            if not raw_name:
                raise HTTPException(
                    status_code=400,
                    detail="existing_file_name must not be empty",
                )

            is_valid_name, name_error = validate_existing_file_name(raw_name)
            if not is_valid_name:
                raise HTTPException(
                    status_code=400,
                    detail=name_error,
                )
            base_name = os.path.basename(raw_name)

            uploads_dir = "uploads"
            user_uploads_dir = os.path.join(uploads_dir, user_id)
            os.makedirs(user_uploads_dir, exist_ok=True)
            candidate_path = os.path.join(user_uploads_dir, base_name)

            real_user_dir = os.path.realpath(user_uploads_dir)
            real_candidate = os.path.realpath(candidate_path)
            if not (real_candidate == real_user_dir or
                    real_candidate.startswith(real_user_dir + os.sep)):
                raise HTTPException(
                    status_code=400,
                    detail="existing_file_name escapes the user uploads directory",
                )

            is_valid, error = validate_file_path(candidate_path)
            if not is_valid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Existing file validation failed: {error}"
                )

            logger.info(f"Reusing existing file: {candidate_path}")
            file_path = candidate_path
            if parsed_resume_value is None:
                parsed_resume_value = {}
            parsed_resume_value["file_path"] = file_path

        if not query and parsed_resume_value is None and not file_path:
            raise HTTPException(
                status_code=400,
                detail="query is required for the initial request"
            )

        # result = await agent.process_query(
        #     query=query or "",
        #     session_id=session_id,
        #     resume_value=parsed_resume_value,
        # )
        #
        # return result

        async def event_generator():
            """Forward agent events without leaving the HTTP stream idle.

            Internal graph events are intentionally filtered by the
            orchestrator, so the first user-visible event may take a while.
            Sending an immediate handshake and periodic heartbeats prevents
            Vite/ngrok and other reverse proxies from treating the response as
            an empty or stalled stream.  Exceptions raised while iterating an
            async generator happen after response headers have been sent, so
            they must be converted to an in-stream error event here.
            """
            queue: asyncio.Queue[Any] = asyncio.Queue()
            stream_finished = object()

            async def produce_events() -> None:
                try:
                    # A user can press Stop and immediately submit another
                    # message.  Let the disconnected turn reach its durable
                    # checkpoint before opening a second writer for the same
                    # LangGraph thread.
                    await _wait_for_detached_query_tasks(session_id)
                    async for event in agent.process_query(
                            query=query or "",
                            session_id=session_id,
                            resume_value=parsed_resume_value,
                            user_id=user_id,
                    ):
                        await queue.put(event)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.error("Query event stream failed: %s", exc, exc_info=True)
                    await queue.put({
                        "type": "error",
                        "error": str(exc) or "Query event stream failed",
                    })
                finally:
                    await queue.put(stream_finished)

            def encode(event: Any) -> str:
                return json.dumps(
                    event,
                    ensure_ascii=False,
                    default=_json_default,
                ) + "\n"

            # Flush bytes immediately so remote clients know that the stream
            # is established before the first LLM/graph operation completes.
            logger.info("Query stream connected [%s]", session_id)
            yield encode({"type": "update", "data": {"stream": "connected"}})

            producer = asyncio.create_task(produce_events())
            try:
                while True:
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=15.0)
                    except asyncio.TimeoutError:
                        logger.debug("Query stream heartbeat [%s]", session_id)
                        yield encode({"type": "update", "data": {"stream": "heartbeat"}})
                        continue
                    if item is stream_finished:
                        break
                    logger.info(
                        "Query stream event [%s]: %s",
                        session_id,
                        item.get("type", "unknown") if isinstance(item, dict) else type(item).__name__,
                    )
                    yield encode(item)
            finally:
                if not producer.done():
                    logger.warning(
                        "Query stream client disconnected; graph will finish in background [%s]",
                        session_id,
                    )
                    _retain_detached_query_task(producer, session_id)
                else:
                    # Retrieve a completed task's result here so asyncio never
                    # reports an unobserved exception. ``produce_events``
                    # converts ordinary failures to an in-stream error event.
                    with contextlib.suppress(asyncio.CancelledError):
                        producer.result()
                logger.info("Query stream closed [%s]", session_id)

        return StreamingResponse(
            event_generator(),
            # The body is newline-delimited JSON, not wire-format SSE
            # (which would require ``data: ...\n\n`` frames).  Declaring the
            # real media type prevents reverse proxies such as ngrok from
            # applying SSE-specific buffering/parsing to otherwise valid
            # NDJSON bytes.
            media_type="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


# Get session info endpoint
@app.get("/api/session/{session_id}", response_model=Dict[str, Any])
async def get_session_info(session_id: str):
    """
    Get information about a session.

    Args:
        session_id: Session ID

    Returns:
        JSON response with session information

    Raises:
        HTTPException: If session not found
    """
    try:
        info = await agent.get_session_info(session_id)

        if info is None:
            raise HTTPException(
                status_code=404,
                detail='Session not found'
            )

        return info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session info: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get session info: {str(e)}")


# Reset session task endpoint
@app.delete("/api/session/{session_id}/reset", response_model=Dict[str, Any])
async def reset_session_task(session_id: str):
    """
    Reset the current task in a session.

    Args:
        session_id: Session ID

    Returns:
        JSON response with reset status

    Raises:
        HTTPException: If reset operation fails
    """
    try:
        result = await agent.reset_session_task(session_id)

        if not result.get('success'):
            raise HTTPException(
                status_code=404,
                detail=result.get('error', 'Reset operation failed')
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting session task: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reset task: {str(e)}")


# ----------------------------------------------------------------------
# Conversation history endpoints (sidebar "历史对话" list + message replay)
#
# These read from the lightweight ``session_index`` table maintained by
# ``agent_app/session_store.py`` (one row per (user_id, session_id)) and
# from the LangGraph checkpoint DB for the actual dialogue transcript.
# ----------------------------------------------------------------------

@app.get("/api/sessions", response_model=Dict[str, Any])
async def list_user_sessions(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
):
    """List every conversation thread owned by the requesting user.

    Returns the lightweight index rows (title, timestamps, message
    count) — the full transcript is fetched on demand via
    :http:get:`/api/sessions/{session_id}/messages`. Sessions from
    other users are never visible.
    """
    from session_store import list_sessions

    try:
        user_id = _sanitize_user_id(x_user_id)
        sessions = list_sessions(user_id)
        return {"sessions": sessions, "total": len(sessions), "user_id": user_id}
    except Exception as e:
        logger.error(f"Error listing sessions: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")


@app.get("/api/sessions/{session_id}/messages", response_model=Dict[str, Any])
async def get_session_messages(
    session_id: str,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
):
    """Return the stored ``dialogue_history`` for a session as a list of
    ``{role, content}`` dicts.

    Ownership check: the session_index row's ``user_id`` MUST match the
    requesting user. Missing-from-index but present-in-checkpointer
    threads (e.g. created before this feature shipped) are denied too —
    the index is the source of truth for "what belongs to whom".
    """
    from session_store import get_session_owner

    try:
        user_id = _sanitize_user_id(x_user_id)
        owner = get_session_owner(session_id)
        if owner is None or owner != user_id:
            raise HTTPException(
                status_code=404,
                detail="Session not found or not owned by the current user",
            )

        replay = await agent.orchestrator.get_session_messages(session_id)
        if replay is None:
            # Index row exists but checkpoint has nothing yet — return
            # an empty payload rather than 404 so the UI can still open it.
            replay = {"messages": [], "artifacts": {}, "events": []}
        messages = replay.get("messages") or []
        artifacts = replay.get("artifacts") or {}
        events = replay.get("events") or []
        return {
            "session_id": session_id,
            "messages": messages,
            "artifacts": artifacts,
            # Chronological event_log — frontend prefers this for replay
            # when non-empty so csv_preview / charts land in their
            # original positions instead of all at the end.
            "events": events,
            "total": len(messages),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session messages: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get messages: {str(e)}")


@app.delete("/api/sessions/{session_id}", response_model=Dict[str, Any])
async def delete_user_session(
    session_id: str,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
):
    """Delete a conversation thread.

    Removes both the index row (so it disappears from the sidebar) and
    the underlying checkpoint state (so the next /api/query with the
    same session_id starts a brand-new graph run). Ownership is
    enforced against the index row before any deletion happens.
    """
    from session_store import delete_session, get_session_owner

    try:
        user_id = _sanitize_user_id(x_user_id)
        owner = get_session_owner(session_id)
        if owner is None or owner != user_id:
            raise HTTPException(
                status_code=404,
                detail="Session not found or not owned by the current user",
            )

        index_removed = delete_session(session_id)
        checkpoint_rows = await agent.orchestrator.delete_session_state(session_id)
        logger.info(
            "delete_session: session=%s index_removed=%s checkpoint_rows=%d",
            session_id, index_removed, checkpoint_rows,
        )
        return {
            "success": True,
            "session_id": session_id,
            "index_removed": index_removed,
            "checkpoint_rows_removed": checkpoint_rows,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")


# Health check endpoint
@app.get("/health", response_model=Dict[str, str])
async def health_check():
    """
    Health check endpoint.

    Returns:
        Health status
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


# ----------------------------------------------------------------------
# Authentication endpoints (register / login / me)
# ----------------------------------------------------------------------

class AuthRequest(BaseModel):
    """JSON body for register / login."""
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)


class AuthResponse(BaseModel):
    """Response for all auth endpoints. ``user_id`` is the stable identity
    the client stores and sends back as ``X-User-Id`` on every subsequent
    request."""
    success: bool
    user_id: Optional[str] = None
    username: Optional[str] = None
    error: Optional[str] = None


@app.post("/api/auth/register", response_model=AuthResponse)
async def auth_register(req: AuthRequest):
    """Create a new user account.

    On success returns the stable ``user_id`` that the client stores and
    uses as the ``X-User-Id`` header for all future requests. The same
    account (username + password) always maps to the same user_id, so a
    user's uploads + trained models are reachable from any browser.
    """
    from auth.user_store import register as _register

    try:
        result = _register(req.username, req.password)
        if result is None:
            return AuthResponse(
                success=False,
                error="用户名已存在，或用户名/密码不符合要求",
            )
        logger.info("auth: registered user=%s", result.get("username"))
        return AuthResponse(
            success=True,
            user_id=result["user_id"],
            username=result["username"],
        )
    except Exception as e:
        logger.error(f"auth register error: {str(e)}", exc_info=True)
        return AuthResponse(success=False, error="注册失败，请稍后重试")


@app.post("/api/auth/login", response_model=AuthResponse)
async def auth_login(req: AuthRequest):
    """Validate credentials and return the account's stable user_id.

    The returned ``user_id`` is what the client stores in localStorage
    and sends as ``X-User-Id`` on subsequent requests — it never changes
    for a given account, so uploads/models persist across logins.
    """
    from auth.user_store import authenticate as _authenticate

    try:
        result = _authenticate(req.username, req.password)
        if result is None:
            return AuthResponse(success=False, error="用户名或密码错误")
        return AuthResponse(
            success=True,
            user_id=result["user_id"],
            username=result["username"],
        )
    except Exception as e:
        logger.error(f"auth login error: {str(e)}", exc_info=True)
        return AuthResponse(success=False, error="登录失败，请稍后重试")


@app.get("/api/auth/me", response_model=AuthResponse)
async def auth_me(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
):
    """Validate a stored session (page reload / re-open).

    The client calls this on mount with the user_id it has in
    localStorage; if the backend confirms the account still exists, the
    session is valid. Otherwise the client clears localStorage and shows
    the login page.
    """
    from auth.user_store import get_by_user_id

    try:
        user_id = _sanitize_user_id(x_user_id)
        result = get_by_user_id(user_id)
        if result is None:
            return AuthResponse(success=False, error="会话已失效，请重新登录")
        return AuthResponse(
            success=True,
            user_id=result["user_id"],
            username=result["username"],
        )
    except Exception as e:
        logger.error(f"auth me error: {str(e)}", exc_info=True)
        return AuthResponse(success=False, error="验证失败，请重新登录")


# ----------------------------------------------------------------------
# Asset listing endpoints (uploaded files + trained models)
# ----------------------------------------------------------------------

# Matches the ``{session_id}_{original_filename}`` pattern used by
# ``process_query`` when saving uploads. Session IDs are UUIDs.
_SESSION_FILENAME_RE = re.compile(
    r"^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})_(.+)$"
)


def _sanitize_user_id(raw: Optional[str]) -> str:
    """Collapse a raw ``X-User-Id`` header value into a filesystem-safe
    segment, falling back to ``"user_anonymous"`` when missing/blank.

    The user_id namespaces both ``uploads/`` and the model artifacts
    tree, so it MUST be path-safe (no separators, no traversal). The
    auth system already generates ids of the form ``user_<hex>``; we
    re-sanitise defensively but avoid double-prefixing so those ids
    survive a round-trip unchanged.
    """
    if not raw:
        return "user_anonymous"
    s = str(raw).strip()
    if not s:
        return "user_anonymous"
    # Drop any path separators / traversal attempts outright.
    s = re.sub(r"[^A-Za-z0-9_.\-]", "_", s)
    s = re.sub(r"_+", "_", s).strip("._")
    if not s:
        return "user_anonymous"
    if len(s) > 96:
        s = s[:96].rstrip("._")
    # Ensure the ``user_`` namespace prefix without double-prefixing
    # ids that already carry it (the auth system's ids all do).
    if not s.startswith("user_"):
        s = "user_" + s
    return s


def _uploads_dir() -> Path:
    """Resolve the uploads directory.

    ``process_query`` writes to ``"uploads"`` (CWD-relative). We resolve
    the same way, then fall back to ``agent_app/uploads`` so the listing
    works regardless of which directory uvicorn was launched from.
    """
    cwd_candidate = Path("uploads")
    if cwd_candidate.exists():
        return cwd_candidate
    return Path(__file__).resolve().parent / "uploads"


def _models_root() -> Path:
    """Return the canonical root for persisted anomaly-detection models."""
    try:
        from tools.anomaly_detection_tools._common import ARTIFACTS_ROOT
        return ARTIFACTS_ROOT
    except Exception:
        # Fallback: mirror the layout hardcoded in _common.py so the
        # endpoint still works if the import path ever changes.
        return Path(__file__).resolve().parent / "artifacts" / "anomaly_detection"


def _prediction_models_root() -> Path:
    try:
        from tools.prediction_tools.finetuning_tools import PREDICTION_MODEL_INDEX_ROOT
        return PREDICTION_MODEL_INDEX_ROOT
    except Exception:
        return Path(__file__).resolve().parent / "artifacts" / "prediction_models"


@app.get("/api/datasets", response_model=Dict[str, Any])
async def list_datasets(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
):
    """List every file the requesting user has ever uploaded.

    Scans ``uploads/<user_id>/`` and returns one entry per file with its
    parsed original filename, extension, size and upload time. Files
    from other users are never visible.
    """
    try:
        user_id = _sanitize_user_id(x_user_id)
        uploads = _uploads_dir() / user_id
        if not uploads.exists():
            return {"datasets": [], "total": 0, "user_id": user_id}

        entries: List[Dict[str, Any]] = []
        for fp in uploads.iterdir():
            if not fp.is_file():
                continue
            ext = fp.suffix.lower().lstrip(".")
            # Only surface the file types the upload endpoint accepts.
            if ext not in ("csv", "xlsx", "parquet"):
                continue
            name = fp.name
            match = _SESSION_FILENAME_RE.match(name)
            if match:
                session_id = match.group(1)
                original_name = match.group(2)
            else:
                session_id = None
                original_name = name
            stat = fp.stat()
            entries.append({
                "name": original_name,
                "file_name": name,
                "extension": ext,
                "size_bytes": int(stat.st_size),
                "modified_at": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc,
                ).isoformat(),
                "session_id": session_id,
            })

        entries.sort(key=lambda e: e.get("modified_at") or "", reverse=True)
        return {"datasets": entries, "total": len(entries), "user_id": user_id}

    except Exception as e:
        logger.error(f"Error listing datasets: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list datasets: {str(e)}")


@app.get("/api/models", response_model=Dict[str, Any])
async def list_models(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
):
    """List every anomaly and fine-tuned prediction model the user owns.

    Walks ``artifacts/anomaly_detection/<user_id>/`` and reads each
    ``.joblib`` envelope's metadata **without** unpickling the model
    body — we load with ``mmap_mode="r"`` and only touch the envelope
    dict keys, mirroring the pattern in ``list_saved_detectors``. Models
    Prediction weights remain remote; their local JSON indexes are merged
    into the same response. Models belonging to other users are never visible.
    """
    import joblib

    try:
        user_id = _sanitize_user_id(x_user_id)
        root = _models_root()
        user_root = root / user_id

        entries: List[Dict[str, Any]] = []
        failed: List[Dict[str, str]] = []
        for fp in user_root.glob("**/*.joblib"):
            if not fp.is_file():
                continue
            try:
                obj = joblib.load(fp, mmap_mode="r")
            except Exception as exc:
                failed.append({
                    "file_name": fp.name,
                    "error": "%s: %s" % (type(exc).__name__, exc),
                })
                continue

            # Parse the (thread_id, source_file) from the relative path
            # so the UI can group models by origin dataset.
            try:
                rel = fp.relative_to(user_root)
                parts = rel.parts
            except ValueError:
                parts = ()
            thread_id = parts[0] if len(parts) >= 1 else None
            subdir = parts[1] if len(parts) >= 2 else ""
            source_file = subdir
            if subdir.endswith("_anomaly_detection"):
                source_file = subdir[: -len("_anomaly_detection")]

            stat = fp.stat()
            if isinstance(obj, dict) and "_pyod_persistence_version" in obj:
                meta = obj.get("metadata") or {}
                entries.append({
                    "category": "anomaly_detection",
                    "task_type": "anomaly_detection",
                    "save_name": fp.stem,
                    "file_name": fp.name,
                    "detector_name": meta.get("detector_name"),
                    "model_class": obj.get("model_class"),
                    "contamination": meta.get("contamination"),
                    "n_samples": meta.get("n_samples"),
                    "n_features": meta.get("n_features"),
                    "feature_columns": meta.get("feature_columns", []),
                    "source": meta.get("source"),
                    "n_anomalies": meta.get("n_anomalies"),
                    "threshold": meta.get("threshold"),
                    "transductive": meta.get("transductive"),
                    "trained_at": meta.get("trained_at"),
                    "saved_at": obj.get("saved_at"),
                    "pyod_version": obj.get("pyod_version"),
                    "sklearn_version": obj.get("sklearn_version"),
                    "size_bytes": int(stat.st_size),
                    "thread_id": thread_id,
                    "source_file": source_file or None,
                })
            else:
                entries.append({
                    "category": "anomaly_detection",
                    "task_type": "anomaly_detection",
                    "save_name": fp.stem,
                    "file_name": fp.name,
                    "detector_name": None,
                    "model_class": type(obj).__name__ if obj is not None else None,
                    "saved_at": None,
                    "legacy": True,
                    "size_bytes": int(stat.st_size),
                    "thread_id": thread_id,
                    "source_file": source_file or None,
                })

        prediction_root = _prediction_models_root() / user_id
        if prediction_root.exists():
            for fp in prediction_root.glob("**/*.json"):
                try:
                    record = json.loads(fp.read_text(encoding="utf-8"))
                    if not isinstance(record, dict) or not record.get("model_path"):
                        raise ValueError("invalid prediction model index")
                    record.setdefault("category", "time_series_prediction")
                    record.setdefault("task_type", "prediction")
                    record.setdefault("file_name", fp.name)
                    record["size_bytes"] = int(fp.stat().st_size)
                    entries.append(record)
                except Exception as exc:
                    failed.append({
                        "file_name": fp.name,
                        "error": "%s: %s" % (type(exc).__name__, exc),
                    })

        entries.sort(
            key=lambda e: e.get("saved_at") or e.get("trained_at") or "",
            reverse=True,
        )
        return {
            "models": entries,
            "total": len(entries),
            "user_id": user_id,
            "root": str(root),
            "failed": failed,
        }

    except Exception as e:
        logger.error(f"Error listing models: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions.

    Must return a Starlette ``Response`` (not a plain ``dict``) so that
    Starlette can invoke it as ``response(scope, receive, sender)`` in the
    ASGI pipeline. Returning a bare dict causes
    ``TypeError: 'dict' object is not callable`` after the handler runs.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions.

    See :func:`http_exception_handler` for why a ``Response`` is required.
    """
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "status_code": 500,
        },
    )


def main():
    """Main function to run the API server."""
    print("=" * 60)
    print(f"工业时间序列多智能体系统 API - {settings.version}")
    print("=" * 60)
    print("")

    # Get configuration
    host = os.getenv('API_HOST', '0.0.0.0')
    port = int(os.getenv('API_PORT', '8000'))
    debug = settings.debug
    workers = int(os.getenv('API_WORKERS', '1'))

    print(f"启动 API 服务器...")
    print(f"地址: http://{host}:{port}")
    print(f"调试模式: {debug}")
    print(f"工作进程: {workers}")
    print(f"API 文档: http://{host}:{port}/docs")
    print(f"ReDoc 文档: http://{host}:{port}/redoc")
    print("")

    # Run the app with uvicorn
    uvicorn.run(
        "api:app",
        host=host,
        port=port,
        reload=debug,
        workers=workers if not debug else 1,
        log_level="info" if not debug else "debug"
    )


if __name__ == '__main__':
    main()
