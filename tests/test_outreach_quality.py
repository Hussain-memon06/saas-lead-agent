"""Tests for deterministic outreach quality checks."""

from saas_lead_agent.engine import OutreachQualityEngine, OutreachQualityThresholds
from saas_lead_agent.schemas import CompanyProfile, CompanySignal, Contact, OutreachDraft


def _profile() -> CompanyProfile:
    return CompanyProfile(
        name="Acme Corp",
        tagline="B2B SaaS sales automation",
        hq="New York, United States",
        employees_estimate="51-200",
        funding_stage="Series B",
        products=["Outbound workflow platform"],
        notable_customers=[],
        sources=["https://acme.example.com/about"],
    )


def _contact() -> Contact:
    return Contact(
        name="Alice Smith",
        title="VP Sales",
        email="alice@acme.example.com",
        linkedin=None,
        confidence=92,
        source="hunter",
    )


def _signals() -> list[CompanySignal]:
    return [
        CompanySignal(
            signal_type="funding",
            date="2026-01",
            source="https://acme.example.com/news",
            details="Acme announced funding to expand sales.",
        )
    ]


def _draft(subject: str, body: str) -> OutreachDraft:
    return OutreachDraft(email_subject=subject, email_body=body)


def test_outreach_quality_passes_personalized_cta() -> None:
    result = OutreachQualityEngine().evaluate(
        profile=_profile(),
        contact=_contact(),
        signals=_signals(),
        draft=_draft(
            "Quick question about Acme Corp",
            "Hi Alice, I noticed Acme Corp's recent funding and the outbound "
            "workflow work your sales team is likely scaling. We help B2B SaaS "
            "teams turn that kind of momentum into qualified meetings without "
            "adding manual research. Would it be worth a quick chat next week?",
        ),
    )

    assert result.passed is True
    assert result.quality_score >= 90
    assert "contact_name" in result.personalization_hooks
    assert "company_name" in result.personalization_hooks
    assert "buying_signal" in result.personalization_hooks
    assert result.issues == []


def test_outreach_quality_flags_placeholders() -> None:
    result = OutreachQualityEngine().evaluate(
        profile=_profile(),
        contact=_contact(),
        signals=_signals(),
        draft=_draft(
            "Quick question for [company name]",
            "Hi {{name}}, I saw [company name] is growing. "
            "Would you be open to a quick chat next week?",
        ),
    )

    assert result.passed is False
    assert result.placeholder_terms
    assert "draft contains unresolved placeholder text" in result.issues


def test_outreach_quality_flags_missing_cta_and_short_body() -> None:
    result = OutreachQualityEngine().evaluate(
        profile=_profile(),
        contact=_contact(),
        signals=_signals(),
        draft=_draft("Acme", "Hi Alice, congrats on the funding."),
    )

    assert result.passed is False
    assert "draft is missing a clear call to action" in result.issues
    assert "email body is too short for useful personalization" in result.issues
    assert "email subject is too short" in result.issues


def test_outreach_quality_flags_spammy_language() -> None:
    result = OutreachQualityEngine().evaluate(
        profile=_profile(),
        contact=_contact(),
        signals=_signals(),
        draft=_draft(
            "Quick question about Acme Corp",
            "Hi Alice, I saw Acme Corp's funding and outbound workflow growth. "
            "This is a risk-free, 100% guaranteed way to get qualified meetings. "
            "Act now and we can discuss the details on a quick call next week.",
        ),
    )

    assert result.passed is False
    assert "risk-free" in result.spam_terms
    assert "100% guaranteed" in result.spam_terms
    assert "act now" in result.spam_terms
    assert "draft contains spammy or high-pressure wording" in result.issues


def test_outreach_quality_thresholds_can_be_tuned() -> None:
    engine = OutreachQualityEngine(
        thresholds=OutreachQualityThresholds(
            min_body_words=5,
            min_personalization_hooks=1,
            passing_score=60,
        )
    )

    result = engine.evaluate(
        profile=_profile(),
        contact=_contact(),
        signals=_signals(),
        draft=_draft(
            "Quick question about Acme Corp",
            "Hi Alice, Acme Corp looks timely. Open to a quick chat?",
        ),
    )

    assert result.passed is True
    assert result.word_count >= 5
