"""Deterministic idempotency helpers for outbound delivery planning."""

import hashlib
import json


def delivery_idempotency_key(
    *,
    run_id: str,
    recipient_email: str,
    subject: str,
    body: str,
) -> str:
    """Return a stable key for one intended email delivery."""

    payload = {
        "run_id": run_id.strip(),
        "recipient_hash": recipient_hash(recipient_email),
        "subject_hash": _hash_text(subject),
        "body_hash": _hash_text(body),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"delivery:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


def recipient_hash(email: str) -> str:
    """Hash a recipient address without preserving raw PII."""

    return _hash_text(email.strip().lower())


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
