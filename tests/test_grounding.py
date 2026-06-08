"""Tests for deterministic evidence grounding checks."""

from saas_lead_agent.engine import GroundingEngine, ScoringEngine
from saas_lead_agent.schemas import CompanyProfile, CompanySignal, Contact, OutreachDraft


def _profile(**overrides: object) -> CompanyProfile:
    data = {
        "name": "Acme Corp",
        "tagline": "B2B SaaS sales automation",
        "hq": "New York, United States",
        "employees_estimate": "51-200",
        "funding_stage": "Series B",
        "products": ["Outbound workflow platform"],
        "notable_customers": [],
        "sources": ["https://acme.example.com/about"],
    }
    data.update(overrides)
    return CompanyProfile.model_validate(data)


def _signals() -> list[CompanySignal]:
    return [
        CompanySignal(
            signal_type="funding",
            date="2026-01",
            source="https://acme.example.com/news",
            details="Acme announced funding for sales team expansion.",
        ),
        CompanySignal(
            signal_type="hiring",
            date="2026-02",
            source="https://acme.example.com/careers",
            details="Acme is hiring sales and RevOps roles.",
        ),
    ]


def _contact(source: str = "hunter") -> Contact:
    return Contact(
        name="Alice Smith",
        title="VP Sales",
        email="alice@acme.example.com",
        linkedin=None,
        confidence=92,
        source=source,
    )


def _draft(body: str) -> OutreachDraft:
    return OutreachDraft(
        email_subject="Quick question about Acme Corp",
        email_body=body,
    )


def test_grounding_accepts_sourced_profile_signals_and_draft() -> None:
    profile = _profile()
    signals = _signals()
    score = ScoringEngine().calculate_score(
        profile=profile,
        contact=_contact(),
        signals=signals,
        icp=None,
    )

    report = GroundingEngine().validate(
        profile=profile,
        contact=_contact(),
        signals=signals,
        draft=_draft(
            "Hi Alice, I saw Acme Corp's funding and hiring momentum. "
            "Could a quick chat next week about outbound workflows be useful?"
        ),
        score=score,
    )

    assert report.is_sufficient is True
    assert report.unsupported_claims == []
    assert report.supported_claim_count == 4
    assert report.evidence.high_confidence_count == 3
    assert "https://acme.example.com/news" in report.source_urls


def test_grounding_flags_profile_without_source_url() -> None:
    profile = _profile(sources=[])
    score = ScoringEngine().calculate_score(
        profile=profile,
        contact=_contact(),
        signals=[],
        icp=None,
    )

    report = GroundingEngine().validate(
        profile=profile,
        contact=_contact(),
        signals=[],
        draft=_draft("Hi Alice, Acme Corp looks relevant. Could we chat next week?"),
        score=score,
    )

    assert report.is_sufficient is False
    assert "company profile has no source URL" in report.unsupported_claims
    assert "score uses company profile detail without profile sources" in report.unsupported_claims


def test_grounding_flags_uncited_url_in_draft() -> None:
    profile = _profile()
    signals = _signals()
    score = ScoringEngine().calculate_score(
        profile=profile,
        contact=_contact(),
        signals=signals,
        icp=None,
    )

    report = GroundingEngine().validate(
        profile=profile,
        contact=_contact(),
        signals=signals,
        draft=_draft(
            "Hi Alice, Acme Corp's funding looks timely. "
            "Could we discuss this next week? https://competitor.example.com"
        ),
        score=score,
    )

    assert report.is_sufficient is False
    assert "draft contains uncited URL: competitor.example.com" in report.unsupported_claims


def test_grounding_flags_signal_claim_without_signal_evidence() -> None:
    profile = _profile()
    score = ScoringEngine().calculate_score(
        profile=profile,
        contact=_contact(),
        signals=[],
        icp=None,
    )

    report = GroundingEngine().validate(
        profile=profile,
        contact=_contact(),
        signals=[],
        draft=_draft(
            "Hi Alice, I saw Acme Corp's recent funding and hiring push. Could we chat next week?"
        ),
        score=score,
    )

    assert report.is_sufficient is False
    assert "draft mentions funding without matching signal evidence" in report.unsupported_claims
    assert "draft mentions hiring without matching signal evidence" in report.unsupported_claims
