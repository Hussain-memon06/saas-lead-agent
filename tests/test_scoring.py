"""Tests for deterministic Phase 2 lead scoring."""

from saas_lead_agent.engine import ICPConfig, ScoringEngine, ScoringThresholds
from saas_lead_agent.schemas import CompanyProfile, CompanySignal, Contact, IcpContext


def _profile(**overrides: object) -> CompanyProfile:
    data = {
        "name": "Acme Corp",
        "tagline": "B2B SaaS workflow automation for sales teams",
        "hq": "New York, United States",
        "employees_estimate": "51-200",
        "funding_stage": "Series B",
        "products": ["Sales automation platform", "Outbound workflow engine"],
        "notable_customers": ["ExampleCo"],
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
            details="Acme announced recent funding to expand sales automation.",
        ),
        CompanySignal(
            signal_type="hiring",
            date="2026-02",
            source="https://acme.example.com/careers",
            details="Acme is hiring sales and RevOps roles.",
        ),
    ]


def _contact(email: str | None = "alice@acme.example.com") -> Contact:
    return Contact(
        name="Alice Smith",
        title="VP Sales",
        email=email,
        linkedin=None,
        confidence=92,
        source="hunter",
    )


def _icp(**overrides: object) -> IcpContext:
    data = {
        "target_industries": ["B2B SaaS"],
        "target_stages": ["Series B"],
        "target_geographies": ["United States"],
        "target_employees": "51-200",
        "must_have_signals": ["recent funding", "hiring sales"],
        "red_flags": ["consumer app"],
    }
    data.update(overrides)
    return IcpContext.model_validate(data)


def test_scoring_high_fit_icp_match_is_reproducible() -> None:
    engine = ScoringEngine()
    first = engine.calculate_score(
        profile=_profile(),
        contact=_contact(),
        signals=_signals(),
        icp=_icp(),
    )
    second = engine.calculate_score(
        profile=_profile(),
        contact=_contact(),
        signals=_signals(),
        icp=_icp(),
    )

    assert first.fit_score == second.fit_score
    assert first.fit_score >= 8
    assert first.fit_level == "high"
    assert first.confidence == "high"
    assert first.score_breakdown.industry_match == 1.5
    assert first.needs_human_review is False


def test_scoring_medium_fit_when_some_icp_evidence_missing() -> None:
    result = ScoringEngine().calculate_score(
        profile=_profile(funding_stage="Seed", hq="Berlin, Germany"),
        contact=_contact(email=None),
        signals=[],
        icp=_icp(),
    )

    assert 5 <= result.fit_score <= 7
    assert result.fit_level == "medium"
    assert result.needs_human_review is True
    assert result.uncertainty_reasons


def test_scoring_low_fit_when_profile_is_missing() -> None:
    result = ScoringEngine().calculate_score(
        profile=None,
        contact=None,
        signals=[],
        icp=_icp(),
    )

    assert result.fit_score < 5
    assert result.fit_level == "low"
    assert result.confidence == "low"
    assert result.needs_human_review is True


def test_scoring_red_flags_penalize_fit() -> None:
    result = ScoringEngine().calculate_score(
        profile=_profile(tagline="Consumer app for personal budgeting"),
        contact=_contact(),
        signals=_signals(),
        icp=_icp(red_flags=["consumer app", "personal budgeting"]),
    )

    assert result.score_breakdown.red_flag_penalty == -2
    assert result.needs_human_review is True
    assert any("red flag" in reason for reason in result.reasons)


def test_scoring_generic_mode_does_not_require_icp() -> None:
    result = ScoringEngine().calculate_score(
        profile=_profile(),
        contact=_contact(),
        signals=_signals(),
        icp=None,
    )

    assert result.fit_score == 9
    assert result.fit_level == "high"
    assert result.score_explanation.startswith("9/10 - ")


def test_scoring_accepts_explicit_icp_config() -> None:
    config = ICPConfig.from_context(_icp())

    result = ScoringEngine().calculate_score(
        profile=_profile(),
        contact=_contact(),
        signals=_signals(),
        icp=config,
    )

    assert result.fit_score >= 8
    assert result.fit_level == "high"
    assert result.score_breakdown.industry_match == config.weights.industry_match


def test_scoring_thresholds_can_tune_fit_classification() -> None:
    config = ICPConfig(
        thresholds=ScoringThresholds(
            high_fit_min_score=10,
            medium_fit_min_score=6,
        )
    )

    result = ScoringEngine().calculate_score(
        profile=_profile(),
        contact=_contact(),
        signals=_signals(),
        icp=config,
    )

    assert result.fit_score == 9
    assert result.fit_level == "medium"
