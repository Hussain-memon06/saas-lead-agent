"""Tests for delivery idempotency-key helpers."""

from saas_lead_agent.email.idempotency import delivery_idempotency_key, recipient_hash


def test_recipient_hash_normalizes_email_case_and_space() -> None:
    assert recipient_hash(" Alice@Example.com ") == recipient_hash("alice@example.com")


def test_delivery_idempotency_key_is_stable_for_same_delivery() -> None:
    key = delivery_idempotency_key(
        run_id="run-1",
        recipient_email="alice@example.com",
        subject="Hello",
        body="Hi Alice",
    )

    assert key == delivery_idempotency_key(
        run_id="run-1",
        recipient_email=" Alice@Example.com ",
        subject="Hello",
        body="Hi Alice",
    )
    assert key.startswith("delivery:")
    assert "alice@example.com" not in key


def test_delivery_idempotency_key_changes_with_delivery_inputs() -> None:
    base = delivery_idempotency_key(
        run_id="run-1",
        recipient_email="alice@example.com",
        subject="Hello",
        body="Hi Alice",
    )

    assert base != delivery_idempotency_key(
        run_id="run-2",
        recipient_email="alice@example.com",
        subject="Hello",
        body="Hi Alice",
    )
    assert base != delivery_idempotency_key(
        run_id="run-1",
        recipient_email="bob@example.com",
        subject="Hello",
        body="Hi Alice",
    )
    assert base != delivery_idempotency_key(
        run_id="run-1",
        recipient_email="alice@example.com",
        subject="Different subject",
        body="Hi Alice",
    )
