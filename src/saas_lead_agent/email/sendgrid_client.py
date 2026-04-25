"""Async wrapper around the SendGrid v3 Mail Send API.

The official `sendgrid` Python SDK is sync-only (built on python-http-client).
We invoke it inside ``asyncio.to_thread`` so the event loop is not blocked
during the HTTP round-trip.
"""

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


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
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        raise RuntimeError("SENDGRID_API_KEY environment variable is not set")

    from_email = os.environ.get("SENDGRID_FROM_EMAIL")
    if not from_email:
        raise RuntimeError("SENDGRID_FROM_EMAIL environment variable is not set")

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
        raise RuntimeError(f"SendGrid delivery failed: {exc}") from exc

    status_code = int(getattr(response, "status_code", 0))
    if status_code < 200 or status_code >= 300:
        raise RuntimeError(
            f"SendGrid returned non-2xx status {status_code} for recipient '{to}'"
        )

    message_id: str | None = None
    headers = getattr(response, "headers", None)
    if headers is not None:
        # response.headers may be a dict or a Headers-like object
        try:
            message_id = headers.get("X-Message-Id")
        except AttributeError:
            message_id = None

    return {
        "status_code": status_code,
        "message_id": message_id,
        "sent_at": datetime.now(UTC).isoformat(),
    }
