"""Company profile contract produced by the company researcher."""

from typing import Literal

from pydantic import Field

from saas_lead_agent.schemas.base import StrictBaseModel

FundingStage = Literal[
    "Seed",
    "Series A",
    "Series B",
    "Series C+",
    "Public",
    "Bootstrapped",
    "Unknown",
]


class CompanyProfile(StrictBaseModel):
    name: str | None = Field(default=None, max_length=300)
    tagline: str | None = Field(default=None, max_length=500)
    hq: str | None = Field(default=None, max_length=300)
    employees_estimate: str | None = Field(default=None, max_length=100)
    funding_stage: FundingStage | None = None
    products: list[str] = Field(default_factory=list, max_length=50)
    notable_customers: list[str] = Field(default_factory=list, max_length=50)
    sources: list[str] = Field(default_factory=list, max_length=100)
