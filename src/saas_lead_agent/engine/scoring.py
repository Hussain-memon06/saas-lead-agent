"""Deterministic lead scoring.

The LLM extracts company facts, signals, and outreach copy. This module owns the
final fit score so the decision is reproducible and inspectable.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Literal

from pydantic import Field

from saas_lead_agent.schemas import CompanyProfile, CompanySignal, Contact, IcpContext
from saas_lead_agent.schemas.base import StrictBaseModel

FitLevel = Literal["low", "medium", "high"]
ScoreConfidence = Literal["low", "medium", "high"]


class ScoreBreakdown(StrictBaseModel):
    baseline: float = Field(ge=0, le=3.5)
    profile_completeness: float = Field(ge=0, le=1.5)
    industry_match: float = Field(ge=0, le=1.5)
    stage_match: float = Field(ge=0, le=1)
    geography_match: float = Field(ge=0, le=1)
    company_size_fit: float = Field(ge=0, le=1)
    signal_strength: float = Field(ge=0, le=1.5)
    contact_quality: float = Field(ge=0, le=0.5)
    red_flag_penalty: float = Field(ge=-2, le=0)

    @property
    def total(self) -> float:
        return max(
            1.0,
            min(
                10.0,
                self.baseline
                + self.profile_completeness
                + self.industry_match
                + self.stage_match
                + self.geography_match
                + self.company_size_fit
                + self.signal_strength
                + self.contact_quality
                + self.red_flag_penalty,
            ),
        )


class ScoreResult(StrictBaseModel):
    fit_score: int = Field(ge=1, le=10)
    fit_level: FitLevel
    confidence: ScoreConfidence
    needs_human_review: bool
    score_breakdown: ScoreBreakdown
    score_explanation: str
    reasons: list[str] = Field(default_factory=list)
    uncertainty_reasons: list[str] = Field(default_factory=list)


class ScoringEngine:
    """Rule-based scoring engine for current Phase 2 data contracts."""

    def calculate_score(
        self,
        *,
        profile: CompanyProfile | None,
        contact: Contact | None,
        signals: list[CompanySignal],
        icp: IcpContext | None,
    ) -> ScoreResult:
        has_icp = self._has_meaningful_icp(icp)
        corpus = self._build_corpus(profile, signals)
        signal_corpus = self._join(signal.details for signal in signals)

        reasons: list[str] = []
        uncertainty: list[str] = []

        baseline = self._baseline(profile, signals, contact, has_icp)
        profile_score = self._score_profile(profile, reasons, uncertainty)
        industry_score = self._score_industry(icp, corpus, has_icp, reasons, uncertainty)
        stage_score = self._score_stage(profile, icp, has_icp, reasons, uncertainty)
        geography_score = self._score_geography(profile, icp, has_icp, reasons, uncertainty)
        size_score = self._score_company_size(profile, icp, has_icp, reasons, uncertainty)
        signal_score = self._score_signals(icp, signals, signal_corpus, reasons, uncertainty)
        contact_score = self._score_contact(contact, reasons, uncertainty)
        penalty = self._red_flag_penalty(icp, corpus, signal_corpus, reasons)

        breakdown = ScoreBreakdown(
            baseline=baseline,
            profile_completeness=profile_score,
            industry_match=industry_score,
            stage_match=stage_score,
            geography_match=geography_score,
            company_size_fit=size_score,
            signal_strength=signal_score,
            contact_quality=contact_score,
            red_flag_penalty=penalty,
        )

        fit_score = int(breakdown.total + 0.5)
        fit_level = self._classify(fit_score)
        confidence = self._confidence(profile, contact, signals, fit_score, uncertainty)
        needs_review = confidence == "low" or 4 <= fit_score <= 6 or penalty < 0

        return ScoreResult(
            fit_score=fit_score,
            fit_level=fit_level,
            confidence=confidence,
            needs_human_review=needs_review,
            score_breakdown=breakdown,
            score_explanation=self._explain(
                fit_score=fit_score,
                confidence=confidence,
                reasons=reasons,
                uncertainty=uncertainty,
            ),
            reasons=reasons,
            uncertainty_reasons=uncertainty,
        )

    def _baseline(
        self,
        profile: CompanyProfile | None,
        signals: list[CompanySignal],
        contact: Contact | None,
        has_icp: bool,
    ) -> float:
        has_profile = bool(profile and (profile.name or profile.tagline or profile.products))
        if has_icp:
            return 3.0 if has_profile else 1.5
        if has_profile or signals or contact:
            return 2.5
        return 1.5

    def _score_profile(
        self,
        profile: CompanyProfile | None,
        reasons: list[str],
        uncertainty: list[str],
    ) -> float:
        if profile is None:
            uncertainty.append("company profile missing")
            return 0.0

        checks = [
            bool(profile.name),
            bool(profile.tagline or profile.products),
            bool(profile.sources),
            bool(profile.funding_stage or profile.employees_estimate or profile.hq),
        ]
        score = 1.5 * (sum(checks) / len(checks))
        if score >= 1.0:
            reasons.append("company profile has usable sourced detail")
        else:
            uncertainty.append("company profile is thin")
        return round(score, 2)

    def _score_industry(
        self,
        icp: IcpContext | None,
        corpus: str,
        has_icp: bool,
        reasons: list[str],
        uncertainty: list[str],
    ) -> float:
        targets = icp.target_industries if icp else []
        match = self._first_match(targets, corpus)
        if match:
            reasons.append(f"industry matched {match}")
            return 1.5
        if targets:
            uncertainty.append("target industry not found in extracted facts")
            return 0.0
        if not has_icp and corpus:
            reasons.append("generic mode: company has descriptive business text")
            return 0.5
        return 0.0

    def _score_stage(
        self,
        profile: CompanyProfile | None,
        icp: IcpContext | None,
        has_icp: bool,
        reasons: list[str],
        uncertainty: list[str],
    ) -> float:
        funding_stage = profile.funding_stage if profile else None
        targets = icp.target_stages if icp else []
        if funding_stage and self._first_match(targets, funding_stage):
            reasons.append(f"stage matched {funding_stage}")
            return 1.0
        if targets:
            uncertainty.append("target stage not found")
            return 0.0
        if not has_icp and funding_stage and funding_stage != "Unknown":
            reasons.append(f"funding stage available: {funding_stage}")
            return 1.0
        return 0.0

    def _score_geography(
        self,
        profile: CompanyProfile | None,
        icp: IcpContext | None,
        has_icp: bool,
        reasons: list[str],
        uncertainty: list[str],
    ) -> float:
        hq = profile.hq if profile else None
        targets = icp.target_geographies if icp else []
        match = self._first_match(targets, hq or "")
        if match:
            reasons.append(f"geography matched {match}")
            return 1.0
        if targets:
            uncertainty.append("target geography not found")
            return 0.0
        if not has_icp and hq:
            reasons.append("headquarters available")
            return 0.5
        return 0.0

    def _score_company_size(
        self,
        profile: CompanyProfile | None,
        icp: IcpContext | None,
        has_icp: bool,
        reasons: list[str],
        uncertainty: list[str],
    ) -> float:
        size = profile.employees_estimate if profile else None
        target = icp.target_employees if icp else "Any"
        if target and target != "Any":
            if size and self._matches(target, size):
                reasons.append(f"company size matched {target}")
                return 1.0
            uncertainty.append("target employee range not found")
            return 0.0
        if not has_icp and size:
            reasons.append("employee estimate available")
            return 0.5
        return 0.0

    def _score_signals(
        self,
        icp: IcpContext | None,
        signals: list[CompanySignal],
        signal_corpus: str,
        reasons: list[str],
        uncertainty: list[str],
    ) -> float:
        required = icp.must_have_signals if icp else []
        if required:
            matched = [signal for signal in required if self._matches(signal, signal_corpus)]
            if matched:
                reasons.append(f"signals matched {', '.join(matched[:3])}")
            missing_count = len(required) - len(matched)
            if missing_count:
                uncertainty.append(f"{missing_count} must-have signal(s) not found")
            return round(1.5 * (len(matched) / len(required)), 2)

        if signals:
            reasons.append(f"{len(signals)} verified signal(s) found")
        else:
            uncertainty.append("no verified buying signals found")
        return min(1.5, len(signals) * 0.75)

    def _score_contact(
        self,
        contact: Contact | None,
        reasons: list[str],
        uncertainty: list[str],
    ) -> float:
        if contact is None:
            uncertainty.append("contact missing")
            return 0.0
        if contact.email:
            reasons.append("decision-maker email found")
            return 0.5
        if contact.name or contact.title:
            reasons.append("decision-maker identified without email")
            return 0.25
        uncertainty.append("contact missing")
        return 0.0

    def _red_flag_penalty(
        self,
        icp: IcpContext | None,
        corpus: str,
        signal_corpus: str,
        reasons: list[str],
    ) -> float:
        red_flags = icp.red_flags if icp else []
        matches = [flag for flag in red_flags if self._matches(flag, f"{corpus} {signal_corpus}")]
        if not matches:
            return 0.0
        reasons.append(f"red flag detected: {', '.join(matches[:2])}")
        return max(-2.0, -1.0 * len(matches))

    def _confidence(
        self,
        profile: CompanyProfile | None,
        contact: Contact | None,
        signals: list[CompanySignal],
        fit_score: int,
        uncertainty: list[str],
    ) -> ScoreConfidence:
        source_count = len(profile.sources) if profile else 0
        has_contact = bool(contact and contact.email)
        if fit_score >= 7 and source_count > 0 and (len(signals) >= 2 or has_contact):
            return "high"
        if profile and source_count > 0 and len(uncertainty) <= 2:
            return "medium"
        return "low"

    def _explain(
        self,
        *,
        fit_score: int,
        confidence: ScoreConfidence,
        reasons: list[str],
        uncertainty: list[str],
    ) -> str:
        parts = reasons[:3] if reasons else ["limited verified fit evidence"]
        if uncertainty:
            parts.append(f"uncertainty: {uncertainty[0]}")
        parts.append(f"confidence: {confidence}")
        return f"{fit_score}/10 - " + " | ".join(parts)

    def _classify(self, fit_score: int) -> FitLevel:
        if fit_score >= 8:
            return "high"
        if fit_score >= 5:
            return "medium"
        return "low"

    def _has_meaningful_icp(self, icp: IcpContext | None) -> bool:
        if icp is None:
            return False
        return bool(
            icp.target_industries
            or icp.target_stages
            or icp.target_geographies
            or icp.must_have_signals
            or icp.red_flags
            or (icp.target_employees and icp.target_employees != "Any")
        )

    def _build_corpus(
        self,
        profile: CompanyProfile | None,
        signals: list[CompanySignal],
    ) -> str:
        if profile is None:
            profile_bits: list[str] = []
        else:
            profile_bits = [
                profile.name or "",
                profile.tagline or "",
                profile.hq or "",
                profile.employees_estimate or "",
                profile.funding_stage or "",
                *profile.products,
                *profile.notable_customers,
            ]
        return self._join([*profile_bits, *(signal.details for signal in signals)])

    def _join(self, values: Iterable[object]) -> str:
        return " ".join(str(value) for value in values if value)

    def _first_match(self, targets: list[str], text: str) -> str | None:
        return next((target for target in targets if self._matches(target, text)), None)

    def _matches(self, needle: str, haystack: str) -> bool:
        normalized_needle = self._normalize(needle)
        normalized_haystack = self._normalize(haystack)
        if not normalized_needle or not normalized_haystack:
            return False
        if normalized_needle in normalized_haystack:
            return True
        needle_tokens = set(normalized_needle.split())
        haystack_tokens = set(normalized_haystack.split())
        return bool(needle_tokens) and needle_tokens.issubset(haystack_tokens)

    def _normalize(self, text: str) -> str:
        normalized = text.lower()
        normalized = normalized.replace("usa", "united states").replace("u.s.", "united states")
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
        return " ".join(normalized.split())
