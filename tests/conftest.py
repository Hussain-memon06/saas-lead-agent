import os
from pathlib import Path

from dotenv import load_dotenv


def pytest_configure() -> None:
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    # Ensure tests never hit real APIs unless keys are explicitly set
    os.environ.setdefault("TAVILY_API_KEY", "test-stub")
    os.environ.setdefault("GOOGLE_API_KEY", "test-stub")
    os.environ.setdefault("OPENAI_API_KEY", "test-stub")
    os.environ.setdefault("HUNTER_API_KEY", "test-stub")
