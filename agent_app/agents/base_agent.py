import time
import logging
import sqlite3
from functools import partial
from typing import Any, Dict, List, Optional, Tuple, Type

from fastapi.concurrency import run_in_threadpool
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from config.settings import settings

logger = logging.getLogger(__name__)


def _parse_tool_content(content: Any) -> Any:
    """Best-effort parse of a ``ToolMessage.content`` into a Python object.

    Our ``@tool``-decorated functions return dicts that langchain serialises
    to JSON strings before stuffing them into ``ToolMessage.content``; some
    versions keep them as dicts directly. Handle both transparently so each
    caller does not have to re-implement the JSON / ast fallback dance.
    """
    if isinstance(content, (dict, list)):
        return content
    if not isinstance(content, str):
        return None
    text = content.strip()
    if not text:
        return None
    try:
        import json
        return json.loads(text)
    except Exception:
        pass
    try:
        import ast
        return ast.literal_eval(text)
    except Exception:
        return None


def extract_tool_calls(messages: List[Any]) -> List[Dict[str, Any]]:
    """Walk an agent's langchain message list and return one record per
    tool call, paired with its tool result.

    Each ``AIMessage.tool_calls`` entry is joined with the matching
    ``ToolMessage`` on ``tool_call_id`` so the caller sees both the
    invocation (tool name + args) and the structured result the tool
    returned. Records that have no matching ``ToolMessage`` (e.g. the
    tool errored out before producing output) are still emitted with
    ``result=None`` so the call history stays complete.

    Returns a list of dicts with the shape::

        {
            "tool": <name>,
            "args": <args dict>,
            "result": <parsed ToolMessage content or None>,
            "tool_call_id": <id>,
        }
    """
    try:
        from langchain_core.messages import AIMessage, ToolMessage
    except Exception:  # pragma: no cover - langchain_core always available
        return []

    result_by_id: Dict[str, Any] = {}
    for msg in messages:
        if not isinstance(msg, ToolMessage):
            continue
        call_id = getattr(msg, "tool_call_id", None)
        if call_id:
            result_by_id[call_id] = _parse_tool_content(msg.content)

    records: List[Dict[str, Any]] = []
    for msg in messages:
        if not isinstance(msg, AIMessage):
            continue
        calls = getattr(msg, "tool_calls", None) or []
        for call in calls:
            # LangChain's ToolCall is a TypedDict in some versions and a
            # pydantic model in others — normalise to a plain dict.
            if hasattr(call, "model_dump"):
                call = call.model_dump()
            call_id = call.get("id")
            records.append({
                "tool": call.get("name"),
                "args": call.get("args") or {},
                "result": result_by_id.get(call_id),
                "tool_call_id": call_id,
            })
    return records


class BaseAgent:

    def __init__(
        self,
        *,
        system_prompt: str,
        response_model: Optional[Type] = None,
        tools: Optional[list] = None,
        context_schema: Optional[Type] = None,
    ):

        self.model = ChatOpenAI(
            model=settings.MODEL_NAME,
            base_url=settings.BASE_URL,
            api_key=settings.API_KEY,
            temperature=settings.TEMPERATURE,
            timeout=settings.TIMEOUT,
        )

        self.system_prompt = system_prompt

        kwargs = dict(
            model=self.model,
            tools=tools or [],
            system_prompt=system_prompt,
        )

        if response_model is not None:
            kwargs["response_format"] = response_model

        if context_schema is not None:
            kwargs["context_schema"] = context_schema

        self.agent = create_agent(**kwargs)

        logger.info("%s initialized", self.__class__.__name__)

    async def invoke_structured(
            self,
            *,
            prompt: str,
            thread_id: str,
            response_type: Type,
            context: Any = None,
            max_retries: int = 3,
            retry_sleep: float = 0.5,
    ):

        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ]
        }

        config = {
            "configurable": {
                "thread_id": f"{self.__class__.__name__}:{thread_id}"
            },
            # Tag this call so the orchestrator's message-stream filter can
            # drop the "Returning structured response: ..." preamble that
            # LangChain emits for response_format / structured-output calls.
            # The tag propagates into each streamed message chunk's metadata.
            "tags": ["structured_output"],
        }

        kwargs = dict(config=config)

        if context is not None:
            kwargs["context"] = context

        last_error = None

        for attempt in range(max_retries):

            try:
                invoke_fn = partial(
                    self.agent.invoke,
                    payload,
                    **kwargs,
                )

                result = await run_in_threadpool(invoke_fn)

                structured = result.get("structured_response")

                if isinstance(structured, response_type):
                    return structured

                last_error = RuntimeError(
                    f"invalid structured_response: {type(structured)}"
                )

            except Exception as e:
                last_error = e
                logger.exception(e)

            if attempt < max_retries - 1:
                time.sleep(retry_sleep)

        raise RuntimeError(last_error)

    async def invoke_chat(
        self,
        *,
        prompt: str,
        thread_id: str,
        context: Any = None,
    ) -> str:

        content, _ = await self.invoke_chat_full(
            prompt=prompt,
            thread_id=thread_id,
            context=context,
        )
        return content

    async def invoke_chat_full(
        self,
        *,
        prompt: str,
        thread_id: str,
        context: Any = None,
    ) -> Tuple[str, List[Any]]:
        """Same as :meth:`invoke_chat` but also returns the full message
        list so callers can inspect intermediate messages — most notably
        ``ToolMessage`` instances whose content carries the structured
        result of the last tool call (e.g. anomaly-detection scores,
        thresholds, top anomalies).

        Returns
        -------
        (content, messages) : tuple
            ``content`` is the final assistant message text (identical to
            what :meth:`invoke_chat` returns). ``messages`` is the raw
            langchain message list from ``agent.invoke``.
        """

        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ]
        }

        config = {
            "configurable": {
                "thread_id": f"{self.__class__.__name__}:{thread_id}"
            }
        }

        kwargs = dict(config=config)

        if context is not None:
            kwargs["context"] = context

        invoke_fn = partial(
            self.agent.invoke,
            payload,
            **kwargs,
        )

        result = await run_in_threadpool(invoke_fn)

        messages = result["messages"]

        return messages[-1].content, messages

    async def stream_chat(
            self,
            *,
            prompt: str,
            thread_id: str,
            context: Any = None,
    ):
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ]
        }

        config = {
            "configurable": {
                "thread_id": f"{self.__class__.__name__}:{thread_id}"
            }
        }

        kwargs = dict(config=config)

        if context is not None:
            kwargs["context"] = context

        async for chunk in self.agent.astream(
                payload,
                **kwargs,
                stream_mode="updates",
        ):
            yield chunk

