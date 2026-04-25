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
    """Manage Postgres connection pool for the application lifetime.

    If ``POSTGRES_URL`` is set, swaps the module-level ``_graph`` in
    routes.py from InMemorySaver to AsyncPostgresSaver.  If not set,
    InMemorySaver stays (dev / test mode — no Postgres required).
    """
    postgres_url = os.environ.get("POSTGRES_URL")
    if postgres_url:
        from saas_lead_agent.memory.checkpointer import postgres_checkpointer

        async with postgres_checkpointer(postgres_url) as checkpointer:
            _routes._graph = build_graph(checkpointer)
            yield
        # Pool closes here; _graph is now pointing at a closed connection.
        # In production the process exits after yield anyway.
    else:
        yield


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
