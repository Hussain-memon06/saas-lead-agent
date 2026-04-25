"""Tests for the async SendGrid wrapper.

The SendGrid SDK call is patched at the module level so no network traffic
occurs.  We exercise the success path, both env-var preconditions, the
non-2xx branch, and the header-extraction edge cases.
"""

import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from saas_lead_agent.email.sendgrid_client import send_email_via_sendgrid

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(status_code: int = 202, message_id: str | None = "msg-abc-123") -> Any:
    """Return a mock SendGrid response object."""
    response = MagicMock()
    response.status_code = status_code
    if message_id is None:
        response.headers = {}
    else:
        response.headers = {"X-Message-Id": message_id}
    return response


def _patch_client(send_return: Any = None, send_side_effect: Any = None) -> Any:
    """Return a patch context for the SendGridAPIClient class."""
    instance = MagicMock()
    if send_side_effect is not None:
        instance.send.side_effect = send_side_effect
    else:
        instance.send.return_value = send_return
    cls_mock = MagicMock(return_value=instance)
    return patch(
        "saas_lead_agent.email.sendgrid_client.SendGridAPIClient",
        cls_mock,
    )


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_email_via_sendgrid_happy_path() -> None:
    response = _mock_response(status_code=202, message_id="msg-xyz")
    with (
        patch.dict(os.environ, {
            "SENDGRID_API_KEY": "SG.test",
            "SENDGRID_FROM_EMAIL": "sales@acme.test",
        }),
        _patch_client(send_return=response),
    ):
        result = await send_email_via_sendgrid(
            to="alice@example.com",
            subject="Hello",
            body="Hi Alice",
        )

    assert result["status_code"] == 202
    assert result["message_id"] == "msg-xyz"
    assert isinstance(result["sent_at"], str)
    assert "T" in result["sent_at"]  # ISO-8601


@pytest.mark.asyncio
async def test_send_email_via_sendgrid_missing_message_id_header() -> None:
    """If SendGrid response has no X-Message-Id header, message_id is None."""
    response = _mock_response(status_code=202, message_id=None)
    with (
        patch.dict(os.environ, {
            "SENDGRID_API_KEY": "SG.test",
            "SENDGRID_FROM_EMAIL": "sales@acme.test",
        }),
        _patch_client(send_return=response),
    ):
        result = await send_email_via_sendgrid(
            to="bob@example.com", subject="S", body="B"
        )

    assert result["status_code"] == 202
    assert result["message_id"] is None


# ---------------------------------------------------------------------------
# Env-var preconditions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_email_raises_when_api_key_missing() -> None:
    with patch.dict(os.environ, {"SENDGRID_FROM_EMAIL": "sales@acme.test"}, clear=False):
        os.environ.pop("SENDGRID_API_KEY", None)
        with pytest.raises(RuntimeError, match="SENDGRID_API_KEY"):
            await send_email_via_sendgrid(to="x@y.com", subject="s", body="b")


@pytest.mark.asyncio
async def test_send_email_raises_when_from_email_missing() -> None:
    with patch.dict(os.environ, {"SENDGRID_API_KEY": "SG.test"}, clear=False):
        os.environ.pop("SENDGRID_FROM_EMAIL", None)
        with pytest.raises(RuntimeError, match="SENDGRID_FROM_EMAIL"):
            await send_email_via_sendgrid(to="x@y.com", subject="s", body="b")


# ---------------------------------------------------------------------------
# Failure branches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_email_raises_on_non_2xx() -> None:
    """SendGrid 4xx/5xx response surfaces as RuntimeError."""
    response = _mock_response(status_code=400, message_id=None)
    with (
        patch.dict(os.environ, {
            "SENDGRID_API_KEY": "SG.test",
            "SENDGRID_FROM_EMAIL": "sales@acme.test",
        }),
        _patch_client(send_return=response),
    ):
        with pytest.raises(RuntimeError, match="non-2xx status 400"):
            await send_email_via_sendgrid(
                to="x@y.com", subject="s", body="b"
            )


@pytest.mark.asyncio
async def test_send_email_wraps_sdk_exceptions() -> None:
    """Any exception from the SDK becomes a RuntimeError with context."""
    with (
        patch.dict(os.environ, {
            "SENDGRID_API_KEY": "SG.test",
            "SENDGRID_FROM_EMAIL": "sales@acme.test",
        }),
        _patch_client(send_side_effect=ConnectionError("network down")),
    ):
        with pytest.raises(RuntimeError, match="SendGrid delivery failed"):
            await send_email_via_sendgrid(
                to="x@y.com", subject="s", body="b"
            )


@pytest.mark.asyncio
async def test_send_email_accepts_2xx_boundary_values() -> None:
    """200 and 299 are both treated as success; 199 and 300 are not."""
    for ok_status in (200, 202, 299):
        response = _mock_response(status_code=ok_status)
        with (
            patch.dict(os.environ, {
                "SENDGRID_API_KEY": "SG.test",
                "SENDGRID_FROM_EMAIL": "sales@acme.test",
            }),
            _patch_client(send_return=response),
        ):
            result = await send_email_via_sendgrid(
                to="x@y.com", subject="s", body="b"
            )
            assert result["status_code"] == ok_status

    for fail_status in (199, 300, 500):
        response = _mock_response(status_code=fail_status)
        with (
            patch.dict(os.environ, {
                "SENDGRID_API_KEY": "SG.test",
                "SENDGRID_FROM_EMAIL": "sales@acme.test",
            }),
            _patch_client(send_return=response),
        ):
            with pytest.raises(RuntimeError, match="non-2xx"):
                await send_email_via_sendgrid(
                    to="x@y.com", subject="s", body="b"
                )
