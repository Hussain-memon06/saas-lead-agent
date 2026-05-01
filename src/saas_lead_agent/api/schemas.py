"""Pydantic v2 request/response models for the lead-research API."""

from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, field_validator


class QualifyRequest(BaseModel):
    url: str
    # User-supplied ICP from the frontend Settings page.  Free-form dict
    # (snake_case fields matching `frontend/lib/icp.ts`) so the dossier
    # prompt can read it directly without a backend-side schema rewrite
    # every time the frontend adds a field.  ``None`` means the user has
    # not configured an ICP — dossier_writer falls back to generic mode.
    icp_context: dict[str, Any] | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        parsed = urlparse(v.strip())
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(
                "url must be a fully-qualified HTTP/HTTPS URL "
                "(e.g. https://acme.example.com)"
            )
        return v.strip()


class QualifyResponse(BaseModel):
    thread_id: str
    company_profile: dict[str, Any] | None = None
    contact: dict[str, Any] | None = None
    signals: list[dict[str, Any]] | None = None
    fit_score: int | None = None
    score_explanation: str | None = None
    email_subject: str | None = None
    email_body: str | None = None
    email_approved: bool | None = None
    send_result: str | None = None
    message_id: str | None = None
    sent_at: str | None = None
    interrupted: bool = False
    errors: list[str] = []


class ApproveResponse(BaseModel):
    thread_id: str
    email_approved: bool | None = None
    send_result: str | None = None
    message_id: str | None = None
    sent_at: str | None = None
    interrupted: bool = False
    errors: list[str] = []
