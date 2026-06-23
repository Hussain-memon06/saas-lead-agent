"""Tests for the Langfuse callback-handler factory and config wiring.

The tests never construct a real ``Langfuse`` client — when keys are
``"test-stub"`` the SDK still tries to reach the API.  We patch the imports
inside ``get_langfuse_handler`` instead, so the singleton machinery and the
None-safe contract are exercised without any network or SDK side-effects.
"""

import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from saas_lead_agent.api.routes import _config
from saas_lead_agent.memory.langfuse_handler import (
    flush_langfuse,
    get_langfuse_handler,
    langfuse_lifespan,
    reset_langfuse_handler,
)


@pytest.fixture(autouse=True)
def _reset_singleton() -> Any:
    """Each test starts with a fresh singleton so env-var changes take effect."""
    reset_langfuse_handler()
    yield
    reset_langfuse_handler()


# ---------------------------------------------------------------------------
# get_langfuse_handler — None-safe behavior
# ---------------------------------------------------------------------------


def test_handler_is_none_when_public_key_missing() -> None:
    """No LANGFUSE_PUBLIC_KEY → handler is None; no SDK import attempted."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
        assert get_langfuse_handler() is None


def test_handler_is_none_when_sdk_init_fails() -> None:
    """Even with a key set, SDK errors must produce None — graph keeps running."""
    with patch.dict(os.environ, {"LANGFUSE_PUBLIC_KEY": "pk-lf-test"}, clear=False):
        with patch(
            "langfuse.Langfuse",
            side_effect=RuntimeError("network down"),
        ):
            assert get_langfuse_handler() is None


def test_handler_returns_callback_when_configured() -> None:
    """Both keys set + SDK happy → returns a CallbackHandler instance."""
    fake_handler = MagicMock(name="CallbackHandler")
    with patch.dict(
        os.environ,
        {
            "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
            "LANGFUSE_SECRET_KEY": "sk-lf-test",
        },
        clear=False,
    ):
        with (
            patch("langfuse.Langfuse") as mock_client_cls,
            patch("langfuse.langchain.CallbackHandler", return_value=fake_handler),
        ):
            handler = get_langfuse_handler()

    assert handler is fake_handler
    # Langfuse client was constructed with the env-var credentials
    mock_client_cls.assert_called_once()
    kwargs = mock_client_cls.call_args.kwargs
    assert kwargs["public_key"] == "pk-lf-test"
    assert kwargs["secret_key"] == "sk-lf-test"


def test_handler_is_singleton() -> None:
    """Repeated calls return the same instance without re-importing the SDK."""
    fake_handler = MagicMock(name="CallbackHandler")
    with patch.dict(os.environ, {"LANGFUSE_PUBLIC_KEY": "pk-lf-test"}, clear=False):
        with (
            patch("langfuse.Langfuse") as mock_client_cls,
            patch("langfuse.langchain.CallbackHandler", return_value=fake_handler),
        ):
            first = get_langfuse_handler()
            second = get_langfuse_handler()
            third = get_langfuse_handler()

    assert first is second is third is fake_handler
    # Client constructed exactly once across three lookups
    assert mock_client_cls.call_count == 1


def test_handler_caches_none_after_failed_init() -> None:
    """A None result is also cached; we don't retry SDK init on every call."""
    with patch.dict(os.environ, {"LANGFUSE_PUBLIC_KEY": "pk-lf-test"}, clear=False):
        with patch("langfuse.Langfuse", side_effect=RuntimeError("boom")) as mock_client:
            assert get_langfuse_handler() is None
            assert get_langfuse_handler() is None
            assert get_langfuse_handler() is None

    assert mock_client.call_count == 1  # only the first call attempted init


# ---------------------------------------------------------------------------
# Routes _config — callback mounting
# ---------------------------------------------------------------------------


def test_config_omits_callbacks_when_handler_none() -> None:
    """No Langfuse → config is identical to Phase 2 (no callbacks key)."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
        cfg = _config("lead:acme.example.com")

    assert cfg["configurable"]["thread_id"] == "lead:acme.example.com"
    assert "callbacks" not in cfg


def test_config_includes_callbacks_when_handler_present() -> None:
    """Handler available → config carries it under 'callbacks'."""
    fake_handler = MagicMock(name="CallbackHandler")
    with patch.dict(os.environ, {"LANGFUSE_PUBLIC_KEY": "pk-lf-test"}, clear=False):
        with (
            patch("langfuse.Langfuse"),
            patch("langfuse.langchain.CallbackHandler", return_value=fake_handler),
        ):
            cfg = _config("lead:acme.example.com")

    assert cfg.get("callbacks") == [fake_handler]
    assert cfg["configurable"]["thread_id"] == "lead:acme.example.com"


# ---------------------------------------------------------------------------
# flush_langfuse / langfuse_lifespan — shutdown behavior
# ---------------------------------------------------------------------------


def test_flush_is_noop_when_handler_none() -> None:
    """Calling flush before any handler is created must not raise."""
    flush_langfuse()  # no exception, no SDK import


def test_flush_calls_sdk_when_handler_present() -> None:
    """When a handler exists, flush_langfuse forwards to get_client().flush()."""
    fake_handler = MagicMock(name="CallbackHandler")
    fake_client = MagicMock(name="LangfuseClient")
    with patch.dict(os.environ, {"LANGFUSE_PUBLIC_KEY": "pk-lf-test"}, clear=False):
        with (
            patch("langfuse.Langfuse"),
            patch("langfuse.langchain.CallbackHandler", return_value=fake_handler),
        ):
            assert get_langfuse_handler() is fake_handler

        with patch("langfuse.get_client", return_value=fake_client) as mock_get:
            flush_langfuse()

    mock_get.assert_called_once()
    fake_client.flush.assert_called_once()


def test_flush_swallows_sdk_errors() -> None:
    """A flush failure during shutdown must not propagate."""
    fake_handler = MagicMock(name="CallbackHandler")
    with patch.dict(os.environ, {"LANGFUSE_PUBLIC_KEY": "pk-lf-test"}, clear=False):
        with (
            patch("langfuse.Langfuse"),
            patch("langfuse.langchain.CallbackHandler", return_value=fake_handler),
        ):
            assert get_langfuse_handler() is fake_handler

        with patch("langfuse.get_client", side_effect=RuntimeError("oops")):
            flush_langfuse()  # must not raise


@pytest.mark.asyncio
async def test_langfuse_lifespan_flushes_on_exit() -> None:
    """The lifespan context yields the handler and flushes when exited."""
    fake_handler = MagicMock(name="CallbackHandler")
    fake_client = MagicMock(name="LangfuseClient")

    with patch.dict(os.environ, {"LANGFUSE_PUBLIC_KEY": "pk-lf-test"}, clear=False):
        with (
            patch("langfuse.Langfuse"),
            patch("langfuse.langchain.CallbackHandler", return_value=fake_handler),
            patch("langfuse.get_client", return_value=fake_client),
        ):
            async with langfuse_lifespan() as h:
                assert h is fake_handler

    fake_client.flush.assert_called_once()


@pytest.mark.asyncio
async def test_langfuse_lifespan_yields_none_when_unconfigured() -> None:
    """Lifespan yields None and skips flush when no key is set."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
        async with langfuse_lifespan() as h:
            assert h is None
        # no patches; flush is a no-op because handler stayed None
