"""Smoke tests for the deployment artifacts.

Two layers:

1. **File-presence + content sanity** — runs everywhere.  Verifies the
   Dockerfile, compose file, and .dockerignore exist and contain the
   contracts other tests rely on (EXPOSE 8080, multi-stage, secrets
   excluded, etc.).

2. **Actual `docker build`** — only runs when ``docker`` is on PATH.
   Catches Dockerfile breakage that file-content checks can't see (bad
   base image tag, broken uv install, syntax errors, etc.).  Run this
   manually before each release:

       uv run pytest tests/test_docker.py -v
"""

import shutil
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# File presence + content
# ---------------------------------------------------------------------------


def test_dockerfile_exists() -> None:
    assert (_ROOT / "Dockerfile").exists(), "Dockerfile must live at repo root"


def test_docker_compose_yml_exists() -> None:
    assert (_ROOT / "docker-compose.yml").exists()


def test_dockerignore_exists() -> None:
    assert (_ROOT / ".dockerignore").exists()


def test_dockerfile_uses_python_3_11() -> None:
    """Project pins Python 3.11 (per pyproject.toml requires-python)."""
    content = (_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "python:3.11" in content, "base image must be python:3.11-slim"


def test_dockerfile_exposes_8080() -> None:
    """Cloud Run + docker-compose both rely on port 8080."""
    content = (_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "EXPOSE 8080" in content


def test_dockerfile_runs_as_non_root() -> None:
    """Cloud Run requires non-root containers."""
    content = (_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "USER app" in content, "container must drop to non-root user"


def test_dockerfile_is_multi_stage() -> None:
    """Final image must not carry build-essential / compilers."""
    content = (_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert content.count("FROM ") >= 2, "must use multi-stage build"
    assert "AS builder" in content
    assert "AS runtime" in content


def test_dockerfile_uses_uv() -> None:
    """Project mandates uv (CLAUDE.md)."""
    content = (_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "uv sync" in content
    assert "--no-dev" in content, "production image must not ship dev deps"


def test_dockerfile_command_respects_port_env() -> None:
    """Cloud Run injects $PORT; the CMD must honour it."""
    content = (_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "${PORT" in content or "$PORT" in content, (
        "CMD must expand ${PORT} so Cloud Run can override the listen port"
    )


def test_dockerignore_excludes_secrets() -> None:
    content = (_ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert ".env" in content, ".env must be excluded from the image"


def test_dockerignore_excludes_venv() -> None:
    content = (_ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert ".venv" in content, "host .venv must not pollute the image"


def test_dockerignore_excludes_git() -> None:
    content = (_ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert ".git" in content


def test_compose_has_postgres_service() -> None:
    content = (_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "postgres:" in content
    assert "POSTGRES_DB" in content


def test_compose_has_migrate_service() -> None:
    """User-requested: separate migrations step in compose."""
    content = (_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "migrate:" in content
    assert "postgres_checkpointer" in content, "migrate service must run AsyncPostgresSaver.setup()"


def test_compose_app_depends_on_migrate_completion() -> None:
    """App must wait for migrations to finish before starting."""
    content = (_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "service_completed_successfully" in content


def test_deployment_md_exists() -> None:
    assert (_ROOT / "DEPLOYMENT.md").exists()


def test_deployment_md_documents_secrets() -> None:
    content = (_ROOT / "DEPLOYMENT.md").read_text(encoding="utf-8")
    # Each secret used in production must be documented in the runbook.
    for secret in (
        "OPENAI_API_KEY",
        "TAVILY_API_KEY",
        "HUNTER_API_KEY",
        "SENDGRID_API_KEY",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "POSTGRES_URL",
    ):
        assert secret in content, f"DEPLOYMENT.md must document {secret}"


# ---------------------------------------------------------------------------
# Real Docker build (skipped when docker is not on PATH)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    shutil.which("docker") is None,
    reason="docker not on PATH; run before release where docker is available",
)
def test_docker_image_builds() -> None:
    """`docker build` succeeds end-to-end.

    Surface stdout + stderr on failure so CI logs show the exact step that
    broke (uv resolve / package install / COPY).
    """
    result = subprocess.run(  # noqa: S603 — controlled subprocess
        ["docker", "build", "-t", "saas-lead-agent:test", "."],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, (
        f"docker build failed (exit {result.returncode})\n"
        f"--- stdout (last 2k) ---\n{result.stdout[-2000:]}\n"
        f"--- stderr (last 2k) ---\n{result.stderr[-2000:]}"
    )
