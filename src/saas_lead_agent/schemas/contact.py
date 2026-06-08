"""Decision-maker contact contract."""

from typing import Literal

from pydantic import Field

from saas_lead_agent.schemas.base import StrictBaseModel


class Contact(StrictBaseModel):
    name: str | None = Field(default=None, max_length=300)
    title: str | None = Field(default=None, max_length=300)
    email: str | None = Field(default=None, max_length=320)
    linkedin: str | None = Field(default=None, max_length=500)
    confidence: float | None = Field(default=None, ge=0, le=100)
    source: Literal["hunter", "manual", "unknown"] = "unknown"
