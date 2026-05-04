"""FastAPI application factory for the lead-research API."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import saas_lead_agent.api.routes as _routes
from saas_lead_agent.api.routes import router
from saas_lead_agent.graph import build_graph


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Manage Postgres + Langfuse lifecycles for the application.

    - ``POSTGRES_URL`` set → swap ``_routes._graph`` from InMemorySaver to
      AsyncPostgresSaver.  Connection pool is closed on shutdown.
    - ``LANGFUSE_PUBLIC_KEY`` set → flush buffered traces on shutdown so no
      events are lost when the worker exits.
    - Either / both unset → no-op fallback (dev / test mode).
    """
    from saas_lead_agent.memory.langfuse_handler import flush_langfuse

    postgres_url = os.environ.get("POSTGRES_URL")
    try:
        if postgres_url:
            from saas_lead_agent.memory.checkpointer import postgres_checkpointer

            async with postgres_checkpointer(postgres_url) as checkpointer:
                _routes._graph = build_graph(checkpointer)
                yield
        else:
            yield
    finally:
        flush_langfuse()


def _should_mount_chainlit() -> bool:
    """Disable Chainlit mounting when DISABLE_CHAINLIT is truthy.

    Tests set this in conftest so the FastAPI fixture stays cheap and free
    of Chainlit's global socketio / file-server side-effects.
    """
    flag = os.environ.get("DISABLE_CHAINLIT", "").lower()
    return flag not in ("1", "true", "yes")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Mounts the qualify router first, then the Chainlit UI at ``/chainlit``.
    The order is mandatory — mounting Chainlit before the router would
    cause every ``/api/*`` route to 404 (CLAUDE.md).
    """
    app = FastAPI(
        title="SaaS Lead Research Agent",
        description="Research and qualify B2B SaaS companies.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # 1. API router FIRST.
    app.include_router(router)

    # 2. Chainlit UI LAST. Mounting before the router 404s every /api/* route.
    if _should_mount_chainlit():
        from chainlit.utils import mount_chainlit

        target = str(Path(__file__).parent.parent / "ui" / "chainlit_app.py")
        mount_chainlit(app=app, target=target, path="/chainlit")

    return app


app = create_app()
