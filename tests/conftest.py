import os
from pathlib import Path

from dotenv import load_dotenv

# Set BEFORE any test module imports saas_lead_agent.api.main — the app
# factory checks this flag at create_app() time.  Without it Chainlit would
# load its global socket.io / static-file routes for every test session.
os.environ.setdefault("DISABLE_CHAINLIT", "1")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("AUTH_DEV_BYPASS_ENABLED", "true")


def pytest_configure() -> None:
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    # Ensure tests never hit real APIs unless keys are explicitly set
    os.environ.setdefault("TAVILY_API_KEY", "test-stub")
    os.environ.setdefault("OPENAI_API_KEY", "test-stub")
    os.environ.setdefault("HUNTER_API_KEY", "test-stub")
    # Do NOT set POSTGRES_URL — absence causes persistence tests to skip and
    # the lifespan to stay on InMemorySaver, so all existing tests run unchanged.
    # Do NOT set SENDGRID_API_KEY — tests enable SENDGRID_STUB_ENABLED only
    # when they are intentionally exercising explicit stub mode.
    # Do NOT set LANGFUSE_PUBLIC_KEY — absence keeps the callback handler at
    # None so no traces are emitted from test runs.
