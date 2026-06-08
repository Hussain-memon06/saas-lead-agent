"""Buying signal contracts."""

from typing import Literal

from pydantic import Field

from saas_lead_agent.schemas.base import StrictBaseModel

SignalType = Literal[
    "funding",
    "hiring",
    "product",
    "leadership",
    "partnership",
    "other",
]


class CompanySignal(StrictBaseModel):
    signal_type: SignalType
    date: str | None = Field(default=None, max_length=100)
    source: str = Field(min_length=1, max_length=2_048)
    details: str = Field(min_length=1, max_length=2_000)
