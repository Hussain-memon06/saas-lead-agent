"""Tests for Phase 2 ICP and threshold configuration."""

import pytest
from pydantic import ValidationError

from saas_lead_agent.engine import ICPConfig, ScoreWeights, ScoringThresholds
from saas_lead_agent.schemas import IcpContext


def test_icp_config_from_context_preserves_targets() -> None:
    context = IcpContext.model_validate(
        {
            "target_industries": ["B2B SaaS"],
            "target_stages": ["Series B"],
            "target_geographies": ["United States"],
            "target_employees": "51-200",
            "must_have_signals": ["recent funding"],
            "red_flags": ["consumer app"],
        }
    )

    config = ICPConfig.from_context(context)

    assert config.has_meaningful_targets is True
    assert config.target_industries == ["B2B SaaS"]
    assert config.target_stages == ["Series B"]
    assert config.target_geographies == ["United States"]
    assert config.target_employees == "51-200"
    assert config.must_have_signals == ["recent funding"]
    assert config.red_flags == ["consumer app"]


def test_empty_icp_config_is_generic_mode() -> None:
    config = ICPConfig.from_context(None)

    assert config.has_meaningful_targets is False
    assert config.target_employees == "Any"
    assert config.weights.profile_completeness == 1.5
    assert config.thresholds.high_fit_min_score == 8


def test_icp_config_rejects_invalid_thresholds() -> None:
    with pytest.raises(ValidationError):
        ScoringThresholds(high_fit_min_score=11)


def test_icp_config_rejects_out_of_range_weights() -> None:
    with pytest.raises(ValidationError):
        ScoreWeights(contact_email=2.0)
