import os
from pathlib import Path

from dotenv import load_dotenv

# Set BEFORE any test module imports saas_lead_agent.api.main — the app
# factory checks this flag at create_app() time.  Without it Chainlit would
# load its global socket.io / static-file routes for every test session.
os.environ.setdefault("DISABLE_CHAINLIT", "1")


def pytest_configure() -> None:
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    # Ensure tests never hit real APIs unless keys are explicitly set
    os.environ.setdefault("TAVILY_API_KEY", "test-stub")
    os.environ.setdefault("GOOGLE_API_KEY", "test-stub")
    os.environ.setdefault("OPENAI_API_KEY", "test-stub")
    os.environ.setdefault("HUNTER_API_KEY", "test-stub")
    # Do NOT set POSTGRES_URL — absence causes persistence tests to skip and
    # the lifespan to stay on InMemorySaver, so all existing tests run unchanged.
    # Do NOT set SENDGRID_API_KEY — absence keeps send_email in stub mode so
    # tests don't accidentally hit the real SendGrid API.
    # Do NOT set LANGFUSE_PUBLIC_KEY — absence keeps the callback handler at
    # None so no traces are emitted from test runs.
