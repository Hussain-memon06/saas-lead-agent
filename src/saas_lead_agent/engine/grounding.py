"""Deterministic evidence grounding checks.

This is not a semantic verifier. It is a conservative first pass that checks
whether generated dossier/outreach claims are traceable to the structured facts
already extracted by upstream nodes.
"""

from collections.abc import Iterable
from urllib.parse import urlparse

from pydantic import Field

from saas_lead_agent.engine.scoring import ScoreResult
from saas_lead_agent.schemas import (
    CompanyProfile,
    CompanySignal,
    Contact,
    Evidence,
    EvidenceCollection,
    OutreachDraft,
)
from saas_lead_agent.schemas.base import StrictBaseModel


class GroundingReport(StrictBaseModel):
    evidence: EvidenceCollection = Field(default_factory=EvidenceCollection)
    source_urls: list[str] = Field(default_factory=list)
    supported_claim_count: int = 0
    unsupported_claims: list[str] = Field(default_factory=list)
    missing_source_count: int = 0
    evidence_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    is_sufficient: bool = False


class GroundingEngine:
    """Build evidence and flag obvious ungrounded claims."""

    def validate(
        self,
        *,
        profile: CompanyProfile | None,
        contact: Contact | None,
        signals: list[CompanySignal],
        draft: OutreachDraft,
        score: ScoreResult,
    ) -> GroundingReport:
        evidence_items: list[Evidence] = []
        unsupported: list[str] = []

        profile_sources = self._clean_urls(profile.sources if profile else [])
        signal_sources = self._clean_urls(signal.source for signal in signals)
        source_urls = sorted({*profile_sources, *signal_sources})

        if profile and profile.name:
            if profile_sources:
                source_text = (
                    " ".join(
                        [
                            profile.tagline or "",
                            " ".join(profile.products),
                            profile.hq or "",
                            profile.funding_stage or "",
                        ]
                    ).strip()
                    or profile.name
                )
                evidence_items.append(
                    Evidence(
                        claim=f"Company profile for {profile.name}",
                        source_text=source_text,
                        source_location="company_profile",
                        source_url=profile_sources[0],
                        confidence="high",
                    )
                )
            else:
                unsupported.append("company profile has no source URL")

        for signal in signals:
            if signal.source:
                evidence_items.append(
                    Evidence(
                        claim=f"{signal.signal_type} signal",
                        source_text=signal.details,
                        source_location="signals",
                        source_url=signal.source,
                        confidence="high",
                    )
                )
            else:
                unsupported.append(f"{signal.signal_type} signal has no source URL")

        if contact and (contact.name or contact.email or contact.title):
            if contact.source and contact.source != "unknown":
                evidence_items.append(
                    Evidence(
                        claim="Decision-maker contact",
                        source_text=" ".join(
                            str(part)
                            for part in (contact.name, contact.title, contact.email, contact.source)
                            if part
                        ),
                        source_location=f"contact:{contact.source}",
                        source_url=None,
                        confidence="medium",
                    )
                )
            else:
                unsupported.append("contact has no trusted source")

        unsupported.extend(self._draft_unsupported_claims(draft, profile, signals, source_urls))
        unsupported.extend(self._score_unsupported_claims(score, profile, signals, contact))

        evidence = EvidenceCollection(items=evidence_items)
        supported_count = len(evidence_items)
        total_claims = supported_count + len(unsupported)
        coverage = supported_count / total_claims if total_claims else 0.0
        missing_source_count = sum(
            1 for item in evidence_items if item.confidence == "high" and item.source_url is None
        )

        return GroundingReport(
            evidence=evidence,
            source_urls=source_urls,
            supported_claim_count=supported_count,
            unsupported_claims=unsupported,
            missing_source_count=missing_source_count,
            evidence_coverage=round(coverage, 2),
            is_sufficient=bool(evidence_items) and not unsupported,
        )

    def _draft_unsupported_claims(
        self,
        draft: OutreachDraft,
        profile: CompanyProfile | None,
        signals: list[CompanySignal],
        source_urls: list[str],
    ) -> list[str]:
        text = f"{draft.email_subject} {draft.email_body}".lower()
        unsupported: list[str] = []

        known_hosts = {urlparse(url).netloc.lower() for url in source_urls}
        for token in draft.email_body.split():
            if token.startswith(("http://", "https://")):
                host = urlparse(token.rstrip(".,)")).netloc.lower()
                if host and host not in known_hosts:
                    unsupported.append(f"draft contains uncited URL: {host}")

        signal_terms = {"funding", "hiring", "launch", "partnership", "expansion"}
        signal_text = " ".join(
            f"{signal.signal_type} {signal.details}".lower() for signal in signals
        )
        for term in signal_terms:
            if term in text and term not in signal_text:
                unsupported.append(f"draft mentions {term} without matching signal evidence")

        if profile and profile.name and profile.name.lower() not in text:
            unsupported.append("draft does not mention the researched company")
        if signals and not any(
            self._keyword_overlap(f"{signal.signal_type} {signal.details}", text)
            for signal in signals
        ):
            unsupported.append("draft does not reference any verified signal")
        return unsupported

    def _score_unsupported_claims(
        self,
        score: ScoreResult,
        profile: CompanyProfile | None,
        signals: list[CompanySignal],
        contact: Contact | None,
    ) -> list[str]:
        unsupported: list[str] = []
        breakdown = score.score_breakdown
        uses_profile = any(
            value > 0
            for value in (
                breakdown.profile_completeness,
                breakdown.industry_match,
                breakdown.stage_match,
                breakdown.geography_match,
                breakdown.company_size_fit,
            )
        )
        if uses_profile and not (profile and profile.sources):
            unsupported.append("score uses company profile detail without profile sources")
        if breakdown.signal_strength > 0 and not signals:
            unsupported.append("score uses signal strength without verified signals")
        if breakdown.contact_quality > 0 and not (
            contact and contact.source and contact.source != "unknown"
        ):
            unsupported.append("score uses contact quality without trusted contact source")
        return unsupported

    def _keyword_overlap(self, source: str, target: str) -> bool:
        source_terms = {term for term in self._tokens(source) if len(term) >= 5}
        target_terms = set(self._tokens(target))
        return bool(source_terms & target_terms)

    def _tokens(self, text: str) -> list[str]:
        return [token.strip(".,;:!?()[]{}").lower() for token in text.split()]

    def _clean_urls(self, urls: Iterable[object]) -> list[str]:
        return [
            url for url in urls if isinstance(url, str) and url.startswith(("http://", "https://"))
        ]
