"""Outreach draft and delivery contracts."""

from typing import Literal

from pydantic import Field

from saas_lead_agent.schemas.base import StrictBaseModel

SendResult = Literal["sent", "stubbed", "rejected", "no_contact", "failed"]


class OutreachDraft(StrictBaseModel):
    email_subject: str = Field(min_length=1, max_length=300)
    email_body: str = Field(min_length=1, max_length=10_000)


class DossierOutput(StrictBaseModel):
    fit_score: int = Field(ge=1, le=10)
    score_explanation: str = Field(default="", max_length=2_000)
    email_subject: str = Field(default="", max_length=300)
    email_body: str = Field(default="", max_length=10_000)


class DeliveryMetadata(StrictBaseModel):
    send_result: SendResult
    message_id: str | None = Field(default=None, max_length=500)
    sent_at: str | None = Field(default=None, max_length=100)
