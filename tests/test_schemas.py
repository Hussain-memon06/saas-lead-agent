"""Tests for Phase 1 Pydantic domain schemas."""

import pytest
from pydantic import ValidationError

from saas_lead_agent.schemas import (
    APIError,
    APIResponse,
    CompanyProfile,
    CompanySignal,
    Contact,
    DossierOutput,
    Evidence,
    EvidenceCollection,
    IcpContext,
    LeadReport,
    OutreachDraft,
    ProcessingMetadata,
    normalize_public_http_url,
)


def test_company_profile_accepts_current_agent_shape() -> None:
    profile = CompanyProfile.model_validate(
        {
            "name": "Acme Corp",
            "tagline": "Anvils for every occasion",
            "hq": "Tucson, USA",
            "employees_estimate": "50-200",
            "funding_stage": "Series A",
            "products": ["Heavy Anvil"],
            "notable_customers": ["ExampleCo"],
            "sources": ["https://acme.example.com/about"],
        }
    )

    assert profile.name == "Acme Corp"
    assert profile.funding_stage == "Series A"


def test_company_profile_rejects_invalid_stage() -> None:
    with pytest.raises(ValidationError):
        CompanyProfile.model_validate({"name": "Acme", "funding_stage": "Mega Round"})


def test_contact_bounds_confidence() -> None:
    assert Contact(name="Alice", confidence=92, source="hunter").confidence == 92
    with pytest.raises(ValidationError):
        Contact(name="Alice", confidence=120, source="hunter")


def test_signal_requires_known_type_and_source() -> None:
    signal = CompanySignal(
        signal_type="funding",
        date="2026-01-01",
        source="https://acme.example.com/news",
        details="Acme raised a Series A.",
    )
    assert signal.signal_type == "funding"

    with pytest.raises(ValidationError):
        CompanySignal(signal_type="vibes", source="", details="Nope")


def test_icp_context_normalizes_partial_frontend_payload() -> None:
    icp = IcpContext.model_validate(
        {
            "seller_name": "  Hussain  ",
            "target_industries": [" B2B SaaS ", "", "Fintech"],
            "must_have_signals": None,
        }
    )

    assert icp.seller_name == "Hussain"
    assert icp.target_industries == ["B2B SaaS", "Fintech"]
    assert icp.must_have_signals == []
    assert icp.target_employees == "Any"


def test_outreach_and_lead_report_compose() -> None:
    report = LeadReport(
        company_profile=CompanyProfile(name="Acme", sources=[]),
        signals=[],
        fit_score=8,
        outreach=OutreachDraft(email_subject="Quick question", email_body="Hi Alice"),
        send_result="stubbed",
    )

    assert report.fit_score == 8
    assert report.send_result == "stubbed"


def test_dossier_output_bounds_fit_score() -> None:
    assert DossierOutput(fit_score=8).fit_score == 8
    with pytest.raises(ValidationError):
        DossierOutput(fit_score=11)


def test_api_response_envelope_success_and_error_shapes() -> None:
    ok = APIResponse[dict[str, str]](
        success=True,
        data={"thread_id": "lead:acme.example"},
        request_id="req-123",
    )
    assert ok.data == {"thread_id": "lead:acme.example"}

    failed = APIResponse[None](
        success=False,
        error=APIError(code="invalid_url", message="URL is not allowed"),
        request_id="req-124",
    )
    assert failed.error is not None
    assert failed.error.code == "invalid_url"

    with pytest.raises(ValidationError):
        APIResponse[None](success=False, request_id="req-125")


def test_evidence_collection_counts_high_confidence_items() -> None:
    collection = EvidenceCollection(
        items=[
            Evidence(
                claim="Acme sells workflow automation.",
                source_text="Workflow automation for modern teams.",
                source_location="Homepage hero",
                source_url="https://acme.example.com",
                confidence="high",
            ),
            Evidence(
                claim="Acme may serve enterprise buyers.",
                source_text="Trusted by growing teams.",
                source_location="Customers page",
                confidence="medium",
            ),
        ]
    )

    assert collection.high_confidence_count == 1


def test_processing_metadata_defaults() -> None:
    metadata = ProcessingMetadata(run_id="run-1", thread_id="lead:acme.example")

    assert metadata.total_tokens == 0
    assert metadata.steps_completed == []
    assert metadata.started_at.tzinfo is not None


@pytest.mark.parametrize(
    "url",
    [
        "https://acme.example.com",
        " http://acme.example.com/path?q=1 ",
    ],
)
def test_normalize_public_http_url_accepts_public_http_urls(url: str) -> None:
    assert normalize_public_http_url(url).startswith(("http://", "https://"))


def test_normalize_public_http_url_normalizes_scheme_host_and_trailing_slash() -> None:
    assert normalize_public_http_url(" HTTPS://Acme.Example.Com/ ") == "https://acme.example.com"


@pytest.mark.parametrize(
    "url",
    [
        "ftp://acme.example.com",
        "https://localhost",
        "https://127.0.0.1",
        "http://10.0.0.5",
        "http://169.254.169.254/latest/meta-data",
        "https://user:pass@acme.example.com",
        "https://acme.example.com:5432",
    ],
)
def test_normalize_public_http_url_rejects_unsafe_first_pass_urls(url: str) -> None:
    with pytest.raises(ValueError):
        normalize_public_http_url(url)
