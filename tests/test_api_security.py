"""Focused tests for Phase 6 runtime API security controls."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException, Request
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from saas_lead_agent.api.main import app
from saas_lead_agent.api.schemas import QualifyRequest
from saas_lead_agent.api.security import (
    InMemoryRateLimiter,
    enforce_write_rate_limit,
    validate_compliance_configuration,
)
from saas_lead_agent.schemas import AuthContext


@pytest.mark.asyncio
async def test_rate_limiter_returns_retry_after_when_limit_is_exhausted() -> None:
    limiter = InMemoryRateLimiter(clock=lambda: 100.0)

    assert await limiter.check("qualify:user-1", limit=1, window_seconds=60) is None
    assert await limiter.check("qualify:user-1", limit=1, window_seconds=60) == 60


@pytest.mark.asyncio
async def test_write_rate_limit_raises_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("QUALIFY_RATE_LIMIT_PER_MINUTE", "1")
    limiter = InMemoryRateLimiter(clock=lambda: 100.0)
    request = Request({"type": "http", "headers": [], "client": ("127.0.0.1", 5000)})
    auth = AuthContext(mode="authenticated", user_id="user-1")

    with patch("saas_lead_agent.api.security._WRITE_LIMITER", limiter):
        await enforce_write_rate_limit(action="qualify", auth=auth, request=request)
        with pytest.raises(HTTPException) as exc_info:
            await enforce_write_rate_limit(action="qualify", auth=auth, request=request)

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers == {"Retry-After": "60"}


@pytest.mark.asyncio
async def test_request_body_limit_returns_413_with_request_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_REQUEST_BODY_BYTES", "32")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/qualify",
            content=b"x" * 33,
            headers={"Content-Type": "application/json", "X-Request-ID": "req-large"},
        )

    assert response.status_code == 413
    assert response.headers["X-Request-ID"] == "req-large"
    assert response.json()["detail"] == "Request body exceeds the configured limit"


def test_production_requires_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        validate_compliance_configuration()


def test_qualify_request_rejects_oversized_icp_context() -> None:
    with pytest.raises(ValidationError, match="icp_context must be 32000 bytes or fewer"):
        QualifyRequest(
            url="https://acme.example.com",
            icp_context={"target_industries": ["x" * 32_000]},
        )
