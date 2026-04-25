"""FastAPI application factory for the lead-research API."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

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


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Mounts the qualify router.  Chainlit UI will be mounted here in Phase 3
    (after this router) per CLAUDE.md — do not mount it until then.

    # TODO(phase-3): mount Chainlit at /chainlit AFTER all other routes
    """
    app = FastAPI(
        title="SaaS Lead Research Agent",
        description="Research and qualify B2B SaaS companies.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


app = create_app()
