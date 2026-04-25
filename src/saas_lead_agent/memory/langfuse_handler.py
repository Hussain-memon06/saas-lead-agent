"""Langfuse v3 callback-handler factory + lifespan hook.

Reads ``LANGFUSE_PUBLIC_KEY`` / ``LANGFUSE_SECRET_KEY`` / ``LANGFUSE_HOST``
from the environment.  Returns ``None`` whenever credentials are absent or
SDK initialisation fails so missing keys never break the graph — tracing
degrades silently in dev / CI / test.

Wiring pattern (one place, ``api/routes.py::_config``):

    handler = get_langfuse_handler()
    cfg: dict[str, Any] = {"configurable": {"thread_id": tid}}
    if handler is not None:
        cfg["callbacks"] = [handler]

LangChain propagates ``callbacks`` through the runnable tree, so every LLM
call inside the compiled graph emits a Langfuse trace under the same
top-level run id.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langfuse.langchain import CallbackHandler

# Module-level singleton.  ``_initialised`` separates "never tried" from
# "tried and got None" so we don't re-import langfuse on every request.
_handler: "CallbackHandler | None" = None
_initialised: bool = False


def get_langfuse_handler() -> "CallbackHandler | None":
    """Return a singleton CallbackHandler, or None if Langfuse is unconfigured.

    Idempotent: caches the result of the first call.  Use
    :func:`reset_langfuse_handler` in tests when env-var state changes
    between cases.
    """
    global _handler, _initialised
    if _initialised:
        return _handler
    _initialised = True

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    if not public_key:
        return None

    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler

        # Initialise the global Langfuse client.  Reads env vars
        # (LANGFUSE_PUBLIC_KEY / SECRET_KEY / HOST) by default.
        Langfuse(
            public_key=public_key,
            secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
            host=os.environ.get("LANGFUSE_HOST"),
        )
        _handler = CallbackHandler()
    except Exception:
        # Misconfiguration must never crash the graph.  Tracing simply
        # stays disabled for this process lifetime.
        _handler = None

    return _handler


def reset_langfuse_handler() -> None:
    """Reset the singleton.  For tests only — never call from production code."""
    global _handler, _initialised
    _handler = None
    _initialised = False


def flush_langfuse() -> None:
    """Flush any buffered Langfuse events.  Safe to call when unconfigured."""
    if _handler is None:
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception:
        # Flush failures must not block shutdown.
        pass


@asynccontextmanager
async def langfuse_lifespan() -> AsyncIterator["CallbackHandler | None"]:
    """Async context manager: yield the handler, flush on exit.

    Use inside the FastAPI lifespan so buffered events reach Langfuse before
    the worker process terminates.
    """
    handler = get_langfuse_handler()
    try:
        yield handler
    finally:
        flush_langfuse()
