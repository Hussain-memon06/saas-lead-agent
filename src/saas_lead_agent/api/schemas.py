"""Pydantic v2 request/response models for the lead-research API."""

from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, field_validator


class QualifyRequest(BaseModel):
    url: str

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
    email_subject: str | None = None
    email_body: str | None = None
    errors: list[str] = []
