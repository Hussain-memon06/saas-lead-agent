"""Evidence contracts for source-grounded lead claims."""

from typing import Literal

from pydantic import Field

from saas_lead_agent.schemas.base import StrictBaseModel

Confidence = Literal["low", "medium", "high"]


class Evidence(StrictBaseModel):
    claim: str = Field(min_length=1, max_length=2_000)
    source_text: str = Field(min_length=1, max_length=10_000)
    source_location: str = Field(min_length=1, max_length=500)
    source_url: str | None = Field(default=None, max_length=2_048)
    confidence: Confidence


class EvidenceCollection(StrictBaseModel):
    items: list[Evidence] = Field(default_factory=list)

    @property
    def high_confidence_count(self) -> int:
        return sum(1 for item in self.items if item.confidence == "high")
