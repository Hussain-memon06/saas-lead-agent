"""Tests for dependency-free API auth context plumbing."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers

from saas_lead_agent.api.auth import public_auth_metadata, resolve_auth_context


class _Request:
    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.headers = Headers(headers or {})


@pytest.mark.asyncio
async def test_explicit_dev_bypass_defaults_to_anonymous_demo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_DEV_BYPASS_ENABLED", "true")
    context = await resolve_auth_context(_Request())  # type: ignore[arg-type]

    assert context.mode == "anonymous_demo"
    assert context.user_id is None
    assert public_auth_metadata(context) == {
        "auth_mode": "anonymous_demo",
        "auth_user_present": False,
    }


@pytest.mark.asyncio
async def test_explicit_dev_bypass_accepts_internal_user_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_DEV_BYPASS_ENABLED", "true")
    context = await resolve_auth_context(
        _Request({"X-OLA-User-ID": " user-1 ", "X-OLA-User-Email": "user@example.com"})
    )  # type: ignore[arg-type]

    assert context.mode == "authenticated"
    assert context.user_id == "user-1"
    assert context.email == "user@example.com"
    assert public_auth_metadata(context) == {
        "auth_mode": "authenticated",
        "auth_user_present": True,
    }


@pytest.mark.asyncio
async def test_production_does_not_trust_plain_identity_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_DEV_BYPASS_ENABLED", "true")

    with pytest.raises(HTTPException) as exc_info:
        await resolve_auth_context(
            _Request({"X-OLA-User-ID": "user-1"})  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verified_bearer_claims_resolve_authenticated_context() -> None:
    request = _Request({"Authorization": "Bearer clerk-token"})
    with patch(
        "saas_lead_agent.api.auth._decode_clerk_token",
        return_value={"sub": "user-1", "email": "user@example.com"},
    ):
        context = await resolve_auth_context(request)  # type: ignore[arg-type]

    assert context.mode == "authenticated"
    assert context.user_id == "user-1"
    assert context.email == "user@example.com"
