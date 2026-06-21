"""Clerk JWT authentication for protected FastAPI endpoints."""

import asyncio
import os
from functools import lru_cache
from typing import Any

import jwt
from fastapi import HTTPException, Request, status
from jwt import PyJWKClient

from saas_lead_agent.schemas import AuthContext

_USER_ID_HEADER = "X-OLA-User-ID"
_USER_EMAIL_HEADER = "X-OLA-User-Email"


async def resolve_auth_context(request: Request) -> AuthContext:
    """Verify a Clerk bearer token or use an explicit non-production bypass."""

    token = _bearer_token(request)
    if token:
        try:
            claims = await asyncio.to_thread(_decode_clerk_token, token)
        except (jwt.PyJWTError, RuntimeError, ValueError) as exc:
            raise _unauthorized("Invalid or expired authentication token") from exc
        user_id = claims.get("sub")
        if not isinstance(user_id, str) or not user_id.strip():
            raise _unauthorized("Authentication token is missing a subject")
        email = claims.get("email") if isinstance(claims.get("email"), str) else None
        return AuthContext(
            mode="authenticated",
            user_id=user_id,
            email=email,
            roles=["user"],
        )

    if _dev_bypass_enabled():
        user_id = _clean_header(request.headers.get(_USER_ID_HEADER))
        email = _clean_header(request.headers.get(_USER_EMAIL_HEADER))
        if user_id:
            return AuthContext(mode="authenticated", user_id=user_id, email=email, roles=["user"])
        return AuthContext()

    raise _unauthorized("Bearer authentication is required")


def public_auth_metadata(auth: AuthContext) -> dict[str, object]:
    """Return metadata safe for responses, logs, and run events."""

    return {
        "auth_mode": auth.mode,
        "auth_user_present": bool(auth.user_id),
    }


def validate_auth_configuration() -> None:
    """Fail production startup when Clerk authentication is unsafe or incomplete."""

    if not _is_production():
        return
    if _truthy(os.environ.get("AUTH_DEV_BYPASS_ENABLED")):
        raise RuntimeError("AUTH_DEV_BYPASS_ENABLED must be false in production")
    if not _clean_header(os.environ.get("CLERK_ISSUER")):
        raise RuntimeError("CLERK_ISSUER is required in production")


def _decode_clerk_token(token: str) -> dict[str, Any]:
    issuer = _clean_header(os.environ.get("CLERK_ISSUER"))
    if not issuer:
        raise RuntimeError("CLERK_ISSUER is not configured")
    issuer = issuer.rstrip("/")
    jwks_url = _clean_header(os.environ.get("CLERK_JWKS_URL")) or (
        f"{issuer}/.well-known/jwks.json"
    )
    audience = _clean_header(os.environ.get("CLERK_AUDIENCE"))
    signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=issuer,
        audience=audience,
        options={"require": ["exp", "iat", "sub"], "verify_aud": audience is not None},
        leeway=30,
    )
    _validate_authorized_party(claims)
    return dict(claims)


@lru_cache(maxsize=4)
def _jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url, cache_keys=True)


def _validate_authorized_party(claims: dict[str, Any]) -> None:
    configured = _clean_header(os.environ.get("CLERK_AUTHORIZED_PARTIES"))
    if not configured:
        return
    allowed = {item.strip() for item in configured.split(",") if item.strip()}
    if claims.get("azp") not in allowed:
        raise ValueError("token authorized party is not allowed")


def _bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("Authorization", "").strip()
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _dev_bypass_enabled() -> bool:
    return not _is_production() and _truthy(os.environ.get("AUTH_DEV_BYPASS_ENABLED"))


def _is_production() -> bool:
    return os.environ.get("APP_ENV", "development").strip().lower() == "production"


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes"}


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _clean_header(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    return clean or None
