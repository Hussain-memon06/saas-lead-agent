"""Async wrapper around the SendGrid v3 Mail Send API.

The official `sendgrid` Python SDK is sync-only (built on python-http-client).
We invoke it inside ``asyncio.to_thread`` so the event loop is not blocked
during the HTTP round-trip.
"""

import asyncio
import hashlib
import os
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from saas_lead_agent.tools.contracts import (
    ToolCallContext,
    ToolResult,
    ToolSpec,
    ToolTimeoutPolicy,
    completed_tool_result,
    failed_tool_result,
)

SENDGRID_DELIVERY_SPEC = ToolSpec(
    name="sendgrid_delivery",
    category="email_delivery",
    provider="sendgrid",
    description="Send an approved outbound email through SendGrid.",
    timeout_policy=ToolTimeoutPolicy(timeout_ms=10_000, max_attempts=1),
    supports_idempotency=True,
    external_action=True,
    requires_human_approval=True,
)


async def send_email_via_sendgrid(
    to: str,
    subject: str,
    body: str,
) -> dict[str, Any]:
    """Send a plain-text email via SendGrid v3 and return delivery metadata.

    Reads ``SENDGRID_API_KEY`` and ``SENDGRID_FROM_EMAIL`` from the environment.
    Runs the sync SendGrid client in a worker thread so we don't block the
    event loop.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Plain-text email body.

    Returns:
        Dict with ``status_code`` (int), ``message_id`` (str | None — pulled
        from the ``X-Message-Id`` header), and ``sent_at`` (ISO-8601 UTC).

    Raises:
        RuntimeError: If either env var is missing, the SDK call raises, or
            SendGrid returns a non-2xx status.
    """
    result = await run_sendgrid_delivery(to=to, subject=subject, body=body)
    if result.metadata.status == "completed" and isinstance(result.output, dict):
        return result.output
    message = result.error.message if result.error is not None else "SendGrid delivery failed"
    raise RuntimeError(message)


async def run_sendgrid_delivery(
    *,
    to: str,
    subject: str,
    body: str,
    idempotency_key: str | None = None,
) -> ToolResult:
    """Send an approved email and return a typed, sanitized delivery envelope."""
    started = perf_counter()
    context = ToolCallContext(
        idempotency_key=idempotency_key,
        input_hash=_input_hash(to=to, subject=subject, body=body),
    )
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        return failed_tool_result(
            spec=SENDGRID_DELIVERY_SPEC,
            context=context,
            error_kind="configuration",
            error_message="SENDGRID_API_KEY environment variable is not set",
            duration_ms=_elapsed_ms(started),
        )

    from_email = os.environ.get("SENDGRID_FROM_EMAIL")
    if not from_email:
        return failed_tool_result(
            spec=SENDGRID_DELIVERY_SPEC,
            context=context,
            error_kind="configuration",
            error_message="SENDGRID_FROM_EMAIL environment variable is not set",
            duration_ms=_elapsed_ms(started),
        )

    message = Mail(
        from_email=from_email,
        to_emails=to,
        subject=subject,
        plain_text_content=body,
    )

    def _send() -> Any:
        client = SendGridAPIClient(api_key)
        return client.send(message)

    try:
        response = await asyncio.to_thread(_send)
    except Exception as exc:
        return failed_tool_result(
            spec=SENDGRID_DELIVERY_SPEC,
            context=context,
            error_kind="provider",
            error_message=f"SendGrid delivery failed: {exc}",
            retryable=True,
            duration_ms=_elapsed_ms(started),
        )

    status_code = int(getattr(response, "status_code", 0))
    if status_code < 200 or status_code >= 300:
        return failed_tool_result(
            spec=SENDGRID_DELIVERY_SPEC,
            context=context,
            error_kind="http_status",
            error_message=f"SendGrid returned non-2xx status {status_code}",
            retryable=status_code >= 500 or status_code == 429,
            duration_ms=_elapsed_ms(started),
            provider_status_code=status_code if 100 <= status_code <= 599 else None,
        )

    message_id: str | None = None
    headers = getattr(response, "headers", None)
    if headers is not None:
        # response.headers may be a dict or a Headers-like object
        try:
            message_id = headers.get("X-Message-Id")
        except AttributeError:
            message_id = None

    return completed_tool_result(
        spec=SENDGRID_DELIVERY_SPEC,
        context=context,
        output={
            "status_code": status_code,
            "message_id": message_id,
            "sent_at": datetime.now(UTC).isoformat(),
        },
        duration_ms=_elapsed_ms(started),
    )


def _input_hash(*, to: str, subject: str, body: str) -> str:
    raw = f"{to.strip().lower()}\n{subject}\n{body}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)
