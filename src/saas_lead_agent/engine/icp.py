"""Typed ICP and threshold configuration for deterministic scoring."""

from __future__ import annotations

from pydantic import Field

from saas_lead_agent.schemas import IcpContext
from saas_lead_agent.schemas.base import StrictBaseModel


class ScoreWeights(StrictBaseModel):
    baseline_with_icp_profile: float = Field(default=3.0, ge=0, le=3.5)
    baseline_with_icp_no_profile: float = Field(default=1.5, ge=0, le=3.5)
    baseline_generic_with_evidence: float = Field(default=2.5, ge=0, le=3.5)
    baseline_generic_empty: float = Field(default=1.5, ge=0, le=3.5)
    profile_completeness: float = Field(default=1.5, ge=0, le=1.5)
    industry_match: float = Field(default=1.5, ge=0, le=1.5)
    generic_industry_context: float = Field(default=0.5, ge=0, le=1.5)
    stage_match: float = Field(default=1.0, ge=0, le=1)
    generic_stage_context: float = Field(default=1.0, ge=0, le=1)
    geography_match: float = Field(default=1.0, ge=0, le=1)
    generic_geography_context: float = Field(default=0.5, ge=0, le=1)
    company_size_fit: float = Field(default=1.0, ge=0, le=1)
    generic_company_size_context: float = Field(default=0.5, ge=0, le=1)
    signal_strength: float = Field(default=1.5, ge=0, le=1.5)
    signal_each_generic: float = Field(default=0.75, ge=0, le=1.5)
    contact_email: float = Field(default=0.5, ge=0, le=0.5)
    contact_identified: float = Field(default=0.25, ge=0, le=0.5)
    red_flag_penalty_each: float = Field(default=-1.0, ge=-2, le=0)
    red_flag_penalty_floor: float = Field(default=-2.0, ge=-2, le=0)


class ScoringThresholds(StrictBaseModel):
    high_fit_min_score: int = Field(default=8, ge=1, le=10)
    medium_fit_min_score: int = Field(default=5, ge=1, le=10)
    high_confidence_min_score: int = Field(default=7, ge=1, le=10)
    high_confidence_min_sources: int = Field(default=1, ge=0)
    high_confidence_min_signals: int = Field(default=2, ge=0)
    medium_confidence_max_uncertainty: int = Field(default=2, ge=0)
    review_band_min_score: int = Field(default=4, ge=1, le=10)
    review_band_max_score: int = Field(default=6, ge=1, le=10)


class ICPConfig(StrictBaseModel):
    target_industries: list[str] = Field(default_factory=list, max_length=50)
    target_stages: list[str] = Field(default_factory=list, max_length=50)
    target_geographies: list[str] = Field(default_factory=list, max_length=50)
    target_employees: str = "Any"
    must_have_signals: list[str] = Field(default_factory=list, max_length=50)
    red_flags: list[str] = Field(default_factory=list, max_length=50)
    weights: ScoreWeights = Field(default_factory=ScoreWeights)
    thresholds: ScoringThresholds = Field(default_factory=ScoringThresholds)

    @classmethod
    def from_context(cls, icp: IcpContext | ICPConfig | None) -> ICPConfig:
        if isinstance(icp, ICPConfig):
            return icp
        if icp is None:
            return cls()
        return cls(
            target_industries=icp.target_industries,
            target_stages=icp.target_stages,
            target_geographies=icp.target_geographies,
            target_employees=icp.target_employees,
            must_have_signals=icp.must_have_signals,
            red_flags=icp.red_flags,
        )

    @property
    def has_meaningful_targets(self) -> bool:
        return bool(
            self.target_industries
            or self.target_stages
            or self.target_geographies
            or self.must_have_signals
            or self.red_flags
            or (self.target_employees and self.target_employees != "Any")
        )
