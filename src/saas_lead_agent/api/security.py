"""Dependency-free Phase 6 API security controls."""

import asyncio
import os
from collections import defaultdict, deque
from collections.abc import Callable
from math import ceil
from time import monotonic

from fastapi import HTTPException, Request, status

from saas_lead_agent.schemas import AuthContext
from saas_lead_agent.schemas.compliance import COMPLIANCE_CONFIGURATION_PLAN


class InMemoryRateLimiter:
    """Sliding-window process-local limiter for authenticated write operations."""

    def __init__(self, clock: Callable[[], float] = monotonic) -> None:
        self._clock = clock
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, key: str, *, limit: int, window_seconds: int) -> int | None:
        """Return retry-after seconds when the key has exhausted its allowance."""
        now = self._clock()
        cutoff = now - window_seconds
        async with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                return max(1, ceil(window_seconds - (now - events[0])))
            events.append(now)
        return None


_WRITE_LIMITER = InMemoryRateLimiter()


async def enforce_write_rate_limit(
    *,
    action: str,
    auth: AuthContext,
    request: Request,
) -> None:
    """Apply a user limit, with a client-host fallback for explicit dev bypass."""
    if not _rate_limit_enabled():
        return
    if action == "qualify":
        limit = _positive_env_int("QUALIFY_RATE_LIMIT_PER_MINUTE", 10)
    else:
        limit = _positive_env_int("DECISION_RATE_LIMIT_PER_MINUTE", 30)
    subject = auth.user_id or (request.client.host if request.client else "anonymous")
    retry_after = await _WRITE_LIMITER.check(
        f"{action}:{subject}",
        limit=limit,
        window_seconds=60,
    )
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests; try again later",
            headers={"Retry-After": str(retry_after)},
        )


def qualification_account_limit() -> int:
    """Return the lifetime qualification allowance for one account."""
    return _positive_env_int("QUALIFY_ACCOUNT_LIMIT", 3)


def request_body_limit_bytes() -> int:
    """Return the configured request cap, defaulting to the Phase 6 policy."""
    default = COMPLIANCE_CONFIGURATION_PLAN.request_limits.max_body_bytes
    return _positive_env_int("MAX_REQUEST_BODY_BYTES", default)


def validate_compliance_configuration() -> None:
    """Fail production startup when critical runtime configuration is absent."""
    if os.environ.get("APP_ENV", "development").strip().lower() != "production":
        return
    missing = [name for name in ("OPENAI_API_KEY",) if not os.environ.get(name, "").strip()]
    if missing:
        raise RuntimeError(f"Missing critical production configuration: {', '.join(missing)}")


def _positive_env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a positive integer") from exc
    if value < 1:
        raise RuntimeError(f"{name} must be a positive integer")
    return value


def _rate_limit_enabled() -> bool:
    configured = os.environ.get("RATE_LIMIT_ENABLED")
    if configured is not None:
        return configured.strip().lower() in {"1", "true", "yes"}
    return os.environ.get("APP_ENV", "development").strip().lower() != "test"
