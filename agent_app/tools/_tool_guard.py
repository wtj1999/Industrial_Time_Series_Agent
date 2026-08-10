"""Cross-cutting guard for LangChain tool functions.

Applied as the innermost decorator (just above the ``def``), right under
``@tool("...")``. It provides two things every tool call needs:

1. **Input-parameter logging at INFO level** — every LLM-supplied
   argument (everything except the framework-injected ``runtime``) is
   logged via the module logger so the operator can see exactly what the
   LLM passed in. This is invaluable when debugging misbehaving calls
   (e.g. the LLM picked ``window_size=300`` for a 100-row series).

2. **Exception safety** — any unhandled exception raised from the tool
   body is caught, logged with full traceback, and converted into a
   structured error envelope that the LLM can read and recover from.
   Without this, a single failing tool call aborts the whole LangGraph
   ``astream`` loop (see the ``LSTMAD`` window_size=300 incident).

Usage::

    from agent_app.tools._tool_guard import tool_guard

    @tool("detect_ts_anomalies")
    @tool_guard("detect_ts_anomalies")
    def detect_ts_anomalies(runtime: ToolRuntime, detector_name: str = "KShape", ...):
        ...

The decorator uses :func:`functools.wraps`, so LangChain's ``@tool``
still sees the original signature / docstring / type hints (including
the ``ToolRuntime`` annotation it uses to inject the runtime).

``return_type`` selects the shape of the error envelope:

- ``"dict"`` (default) returns ``{task_type, tool_name, summary,
  error_type, error_message}`` — matches the canonical analysis /
  anomaly-detection envelope.
- ``"str"`` returns a plain string for the two profiling tools that
  return ``str`` on the happy path.
"""

from __future__ import annotations

import functools
import inspect
import logging
from typing import Any, Callable, Dict

logger = logging.getLogger(__name__)


# Parameters that are framework-injected (not LLM-supplied) and should
# be excluded from the input-logging line. We always exclude ``runtime``
# (ToolRuntime) and ``config`` (RunnableConfig) since those are passed
# in by LangChain/LangGraph, not by the model.
_INJECTED_PARAMS = frozenset({"runtime", "config"})


def _format_param_value(v: Any) -> Any:
    """Reduce a parameter value to something safe to log.

    LLM tool-call arguments are always JSON-compatible scalars / lists /
    dicts, but we add a defensive cap so a huge list or a weird object
    can't blow up the log line.
    """
    # Common JSON-compatible types — pass through.
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float, str)):
        return v
    if isinstance(v, (list, tuple)):
        try:
            if len(v) > 20:
                return list(v[:20]) + ["...(%d items total)" % len(v)]
            return list(v)
        except Exception:  # pragma: no cover - defensive
            return repr(v)[:200]
    if isinstance(v, dict):
        try:
            return dict(v)
        except Exception:  # pragma: no cover - defensive
            return repr(v)[:200]
    return repr(v)[:200]


def _extract_llm_params(func: Callable, args: tuple, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Bind ``args``/``kwargs`` to ``func``'s signature and drop injected ones.

    Falls back to ``kwargs`` (also filtered) when signature binding fails
    — e.g. for callables that don't expose a regular signature.
    """
    try:
        sig = inspect.signature(func)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        return {
            k: _format_param_value(v)
            for k, v in bound.arguments.items()
            if k not in _INJECTED_PARAMS
        }
    except Exception:  # pragma: no cover - defensive
        return {
            k: _format_param_value(v)
            for k, v in kwargs.items()
            if k not in _INJECTED_PARAMS
        }


def tool_guard(tool_name: str, *, return_type: str = "dict"):
    """Decorator factory that wraps a tool function.

    Parameters
    ----------
    tool_name : str
        Name shown in the log line and the error envelope. Should match
        the name passed to ``@tool(...)``.
    return_type : {"dict", "str"}, default "dict"
        Shape of the value returned when the wrapped function raises.
        Use ``"str"`` only for tools whose normal return type is ``str``
        (currently :func:`get_basic_info` and :func:`analyze_column_tool`).
    """
    if return_type not in ("dict", "str"):
        raise ValueError("return_type must be 'dict' or 'str', got %r" % return_type)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # ----- 1. log LLM-supplied params -----
            params = _extract_llm_params(func, args, kwargs)
            try:
                logger.info("[%s] 调用入参: %s", tool_name, params)
            except Exception:  # pragma: no cover - logging must never crash the call
                pass

            # ----- 2. execute with exception safety -----
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                logger.exception("[%s] 执行失败: %s: %s",
                                 tool_name, type(exc).__name__, exc)
                if return_type == "str":
                    return ("工具 %s 执行失败：%s: %s"
                            % (tool_name, type(exc).__name__, exc))
                return {
                    "task_type": "tool_error",
                    "tool_name": tool_name,
                    "summary": "工具执行失败：%s: %s"
                               % (type(exc).__name__, exc),
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "llm_params": params,
                }

        return wrapper

    return decorator
