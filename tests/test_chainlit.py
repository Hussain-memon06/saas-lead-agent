"""Tests for the Chainlit UI integration.

Three layers:
1. **Pure helpers** (URL validation, formatters) — unit-tested directly,
   no Chainlit runtime needed.
2. **Module import smoke** — chainlit_app.py imports cleanly with all
   decorators registered.
3. **Mount-order contract** — when Chainlit mounting is enabled the
   ``/chainlit`` mount is appended AFTER ``/api/*`` routes; with the
   ``DISABLE_CHAINLIT`` flag (the conftest default) the mount is absent
   and ``/api/*`` continues to serve.
"""

import importlib
import os
from typing import Any
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_validate_url_accepts_https() -> None:
    from saas_lead_agent.ui.chainlit_app import validate_url

    ok, payload = validate_url("https://stripe.com")
    assert ok is True
    assert payload == "https://stripe.com"


def test_validate_url_strips_whitespace() -> None:
    from saas_lead_agent.ui.chainlit_app import validate_url

    ok, payload = validate_url("  https://stripe.com  ")
    assert ok is True
    assert payload == "https://stripe.com"


def test_validate_url_rejects_bare_hostname() -> None:
    from saas_lead_agent.ui.chainlit_app import validate_url

    ok, msg = validate_url("stripe.com")
    assert ok is False
    assert "http" in msg.lower()


def test_validate_url_rejects_empty() -> None:
    from saas_lead_agent.ui.chainlit_app import validate_url

    ok, msg = validate_url("   ")
    assert ok is False
    assert msg


def test_validate_url_rejects_ftp() -> None:
    from saas_lead_agent.ui.chainlit_app import validate_url

    ok, msg = validate_url("ftp://stripe.com")
    assert ok is False
    assert "http" in msg.lower()


def test_format_dossier_includes_company_fields() -> None:
    from saas_lead_agent.ui.chainlit_app import format_dossier

    result: dict[str, Any] = {
        "company_profile": {
            "name": "Acme Corp",
            "tagline": "Anvils for everyone",
            "hq": "Tucson",
            "funding_stage": "Series A",
            "employees_estimate": "50-200",
        },
        "contact": {
            "name": "Alice Smith",
            "title": "CEO",
            "email": "alice@acme.test",
        },
        "signals": [
            {"type": "funding", "title": "Raised $20M Series A"},
            {"type": "hiring", "title": "Hiring 5 engineers"},
        ],
        "fit_score": 8,
    }
    rendered = format_dossier(result)

    assert "Acme Corp" in rendered
    assert "Series A" in rendered
    assert "alice@acme.test" in rendered
    assert "Raised $20M Series A" in rendered
    assert "8/10" in rendered


def test_format_dossier_handles_missing_fields() -> None:
    from saas_lead_agent.ui.chainlit_app import format_dossier

    rendered = format_dossier({})
    assert rendered  # always produces some string, never crashes


def test_format_email_preview_renders_subject_and_body() -> None:
    from saas_lead_agent.ui.chainlit_app import format_email_preview

    rendered = format_email_preview({"email_subject": "Quick question", "email_body": "Hi Alice,"})
    assert "Subject:" in rendered
    assert "Quick question" in rendered
    assert "Hi Alice," in rendered


def test_format_email_preview_handles_missing_fields() -> None:
    from saas_lead_agent.ui.chainlit_app import format_email_preview

    rendered = format_email_preview({})
    assert "(no subject)" in rendered
    assert "(no body)" in rendered


@pytest.mark.parametrize(
    "outcome,expected_substring",
    [
        ("sent", "Sent"),
        ("stubbed", "Stubbed"),
        ("rejected", "Rejected"),
        ("no_contact", "No contact"),
        ("failed", "failed"),
    ],
)
def test_format_send_result_known_outcomes(outcome: str, expected_substring: str) -> None:
    from saas_lead_agent.ui.chainlit_app import format_send_result

    rendered = format_send_result({"send_result": outcome})
    assert expected_substring.lower() in rendered.lower()


def test_format_send_result_includes_message_id_when_sent() -> None:
    from saas_lead_agent.ui.chainlit_app import format_send_result

    rendered = format_send_result({"send_result": "sent", "message_id": "msg-abc-123"})
    assert "msg-abc-123" in rendered


def test_format_send_result_includes_error_when_failed() -> None:
    from saas_lead_agent.ui.chainlit_app import format_send_result

    rendered = format_send_result(
        {"send_result": "failed", "errors": ["send_email: 5xx from SendGrid"]}
    )
    assert "5xx from SendGrid" in rendered


# ---------------------------------------------------------------------------
# Module import smoke
# ---------------------------------------------------------------------------


def test_chainlit_app_imports_cleanly() -> None:
    """No syntax errors, no decorator-time crashes."""
    import saas_lead_agent.ui.chainlit_app as cl_app

    assert hasattr(cl_app, "on_message")
    assert hasattr(cl_app, "on_chat_start")
    assert hasattr(cl_app, "on_approve")
    assert hasattr(cl_app, "on_reject")
    assert callable(cl_app.validate_url)
    assert callable(cl_app.format_dossier)


# ---------------------------------------------------------------------------
# Mount-order contract
# ---------------------------------------------------------------------------


def test_app_does_not_mount_chainlit_when_flag_set() -> None:
    """With DISABLE_CHAINLIT=1 (conftest default) the /chainlit mount is absent."""
    from saas_lead_agent.api.main import app

    routes_with_chainlit = [
        r for r in app.routes if str(getattr(r, "path", "")).startswith("/chainlit")
    ]
    assert routes_with_chainlit == [], (
        "DISABLE_CHAINLIT=1 should keep the test FastAPI app free of "
        f"Chainlit mounts; found: {routes_with_chainlit}"
    )


def test_app_still_serves_api_routes() -> None:
    """API routes work regardless of Chainlit's presence."""
    from saas_lead_agent.api.main import app

    paths = {str(getattr(r, "path", "")) for r in app.routes}
    assert "/api/qualify" in paths
    assert "/api/leads" in paths
    assert "/api/leads/{thread_id}" in paths
    assert "/api/leads/{thread_id}/events" in paths
    assert "/api/leads/{thread_id}/approve" in paths
    assert "/api/leads/{thread_id}/reject" in paths


def test_create_app_calls_mount_chainlit_after_router_when_enabled() -> None:
    """When mounting is enabled, mount_chainlit fires AFTER include_router.

    Order matters: mounting at "/chainlit" before /api/* routes are registered
    will not 404 the API in this case (different prefix), but the project
    contract per CLAUDE.md is "Chainlit last".  Verify the call order to
    keep that contract testable.
    """
    call_log: list[str] = []

    real_create = None  # populated below

    with patch.dict(os.environ, {"DISABLE_CHAINLIT": "0"}):
        # Reload main so create_app sees the flipped flag
        import saas_lead_agent.api.main as main_mod

        # Patch include_router and mount_chainlit on the FastAPI instance
        # produced by reload, by patching at the call sites.
        with patch("saas_lead_agent.api.main.mount_chainlit", create=True):
            # mount_chainlit is imported lazily inside create_app — patch
            # the module attribute it imports from instead:
            with patch("chainlit.utils.mount_chainlit") as mock_mount:
                from fastapi import FastAPI

                original_include_router = FastAPI.include_router

                def _track_include_router(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                    call_log.append("include_router")
                    return original_include_router(self, *args, **kwargs)

                def _track_mount(*args, **kwargs):  # type: ignore[no-untyped-def]
                    call_log.append("mount_chainlit")

                mock_mount.side_effect = _track_mount

                with patch.object(FastAPI, "include_router", _track_include_router):
                    importlib.reload(main_mod)
                    real_create = main_mod.create_app
                    real_create()

    # Reset back to test-mode app
    os.environ["DISABLE_CHAINLIT"] = "1"
    import saas_lead_agent.api.main as main_mod

    importlib.reload(main_mod)

    assert "include_router" in call_log
    assert "mount_chainlit" in call_log
    assert call_log.index("include_router") < call_log.index("mount_chainlit"), (
        f"include_router must run before mount_chainlit; got order: {call_log}"
    )
