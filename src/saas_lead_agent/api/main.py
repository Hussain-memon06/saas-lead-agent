"""FastAPI application factory for the lead-research API."""

from fastapi import FastAPI

from saas_lead_agent.api.routes import router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Mounts the qualify router.  Chainlit UI will be mounted here in Phase 2
    (after this router) per CLAUDE.md — do not mount it until Phase 2.

    # TODO(phase-2): mount Chainlit at /chainlit AFTER all other routes
    """
    app = FastAPI(
        title="SaaS Lead Research Agent",
        description="Research and qualify B2B SaaS companies.",
        version="0.1.0",
    )
    app.include_router(router)
    return app


app = create_app()
