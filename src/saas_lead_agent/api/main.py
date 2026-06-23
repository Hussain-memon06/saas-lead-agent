"""FastAPI application factory for the lead-research API."""

import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import saas_lead_agent.api.routes as _routes
from saas_lead_agent.api.auth import validate_auth_configuration
from saas_lead_agent.api.logging_redaction import configure_http_logging_redaction
from saas_lead_agent.api.routes import router
from saas_lead_agent.api.security import (
    request_body_limit_bytes,
    validate_compliance_configuration,
)
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
    from saas_lead_agent.persistence import create_lead_run_repository

    validate_auth_configuration()
    validate_compliance_configuration()
    postgres_url = os.environ.get("POSTGRES_URL")
    lead_store = create_lead_run_repository(postgres_url)
    await lead_store.setup()
    _routes._lead_store = lead_store
    try:
        if postgres_url:
            from saas_lead_agent.memory.checkpointer import postgres_checkpointer

            async with postgres_checkpointer(postgres_url) as checkpointer:
                _routes._graph = build_graph(checkpointer)
                yield
        else:
            yield
    finally:
        await lead_store.close()
        flush_langfuse()


def _should_mount_chainlit() -> bool:
    """Disable Chainlit mounting when DISABLE_CHAINLIT is truthy.

    Tests set this in conftest so the FastAPI fixture stays cheap and free
    of Chainlit's global socketio / file-server side-effects.
    """
    flag = os.environ.get("DISABLE_CHAINLIT", "").lower()
    if os.environ.get("APP_ENV", "development").lower() == "production":
        return False
    return flag not in ("1", "true", "yes")


def _cors_origins() -> list[str]:
    configured = [
        origin.strip()
        for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    ]
    if configured:
        return configured
    if os.environ.get("APP_ENV", "development").lower() == "production":
        raise RuntimeError("CORS_ALLOWED_ORIGINS is required in production")
    return ["*"]


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Mounts the qualify router first, then the Chainlit UI at ``/chainlit``.
    The order is mandatory — mounting Chainlit before the router would
    cause every ``/api/*`` route to 404 (CLAUDE.md).
    """
    configure_http_logging_redaction()
    app = FastAPI(
        title="Outbound Lead Agent",
        description="Research and qualify B2B SaaS companies.",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def add_request_id(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        max_body_bytes = request_body_limit_bytes()
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > max_body_bytes:
                    error_response = JSONResponse(
                        status_code=413,
                        content={"detail": "Request body exceeds the configured limit"},
                    )
                    error_response.headers["X-Request-ID"] = request_id
                    return error_response
            except ValueError:
                error_response = JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header"},
                )
                error_response.headers["X-Request-ID"] = request_id
                return error_response
        body = await request.body()
        if len(body) > max_body_bytes:
            error_response = JSONResponse(
                status_code=413,
                content={"detail": "Request body exceeds the configured limit"},
            )
            error_response.headers["X-Request-ID"] = request_id
            return error_response
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
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
