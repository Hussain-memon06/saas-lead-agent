"""Normalized app-owned lead artifacts derived from graph snapshots."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Protocol

from pydantic import Field

from saas_lead_agent.schemas.base import StrictBaseModel

LeadArtifactStatus = Literal["interrupted", "completed", "failed"]
SourceType = Literal["company_profile", "company_signal", "grounding_report", "evidence"]
DecisionValue = Literal["approved", "rejected"]


class SnapshotForArtifacts(Protocol):
    run_id: str
    thread_id: str
    domain: str
    company_url: str
    status: LeadArtifactStatus
    result: dict[str, Any]
    request_id: str | None
    created_at: datetime
    updated_at: datetime


class UserRecord(StrictBaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    display_name: str | None = Field(default=None, max_length=300)
    created_at: datetime
    updated_at: datetime


class LeadRecord(StrictBaseModel):
    thread_id: str = Field(min_length=1, max_length=500)
    run_id: str = Field(min_length=1, max_length=200)
    user_id: str | None = Field(default=None, max_length=200)
    domain: str = Field(min_length=1, max_length=500)
    company_url: str = Field(min_length=1, max_length=2_048)
    company_name: str | None = Field(default=None, max_length=300)
    tagline: str | None = Field(default=None, max_length=500)
    hq: str | None = Field(default=None, max_length=300)
    employees_estimate: str | None = Field(default=None, max_length=100)
    funding_stage: str | None = Field(default=None, max_length=100)
    status: LeadArtifactStatus
    fit_score: int | None = Field(default=None, ge=1, le=10)
    fit_level: str | None = Field(default=None, max_length=100)
    score_confidence: str | None = Field(default=None, max_length=100)
    needs_human_review: bool | None = None
    created_at: datetime
    updated_at: datetime


class SourceRecord(StrictBaseModel):
    source_id: str = Field(min_length=1, max_length=700)
    thread_id: str = Field(min_length=1, max_length=500)
    run_id: str = Field(min_length=1, max_length=200)
    source_type: SourceType
    source_url: str | None = Field(default=None, max_length=2_048)
    source_location: str | None = Field(default=None, max_length=500)
    claim: str | None = Field(default=None, max_length=2_000)
    source_text: str | None = Field(default=None, max_length=10_000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ContactRecord(StrictBaseModel):
    contact_id: str = Field(min_length=1, max_length=700)
    thread_id: str = Field(min_length=1, max_length=500)
    run_id: str = Field(min_length=1, max_length=200)
    name: str | None = Field(default=None, max_length=300)
    title: str | None = Field(default=None, max_length=300)
    email: str | None = Field(default=None, max_length=320)
    linkedin: str | None = Field(default=None, max_length=500)
    confidence: float | None = Field(default=None, ge=0, le=100)
    source: str | None = Field(default=None, max_length=100)
    created_at: datetime
    updated_at: datetime


class CompanySignalRecord(StrictBaseModel):
    signal_id: str = Field(min_length=1, max_length=700)
    thread_id: str = Field(min_length=1, max_length=500)
    run_id: str = Field(min_length=1, max_length=200)
    position: int = Field(ge=0)
    signal_type: str = Field(min_length=1, max_length=100)
    date: str | None = Field(default=None, max_length=100)
    source: str = Field(min_length=1, max_length=2_048)
    details: str = Field(min_length=1, max_length=2_000)
    created_at: datetime


class ScoreBreakdownRecord(StrictBaseModel):
    thread_id: str = Field(min_length=1, max_length=500)
    run_id: str = Field(min_length=1, max_length=200)
    fit_score: int | None = Field(default=None, ge=1, le=10)
    fit_level: str | None = Field(default=None, max_length=100)
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
    score_confidence: str | None = Field(default=None, max_length=100)
    score_explanation: str | None = Field(default=None, max_length=2_000)
    needs_human_review: bool | None = None
    score_reasons: list[str] = Field(default_factory=list)
    score_uncertainty: list[str] = Field(default_factory=list)
    grounding_report: dict[str, Any] | None = None
    outreach_quality: dict[str, Any] | None = None
    updated_at: datetime


class OutreachDraftRecord(StrictBaseModel):
    thread_id: str = Field(min_length=1, max_length=500)
    run_id: str = Field(min_length=1, max_length=200)
    email_subject: str | None = Field(default=None, max_length=300)
    email_body: str | None = Field(default=None, max_length=10_000)
    outreach_quality: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class DecisionRecord(StrictBaseModel):
    thread_id: str = Field(min_length=1, max_length=500)
    run_id: str = Field(min_length=1, max_length=200)
    decision: DecisionValue
    request_id: str | None = Field(default=None, max_length=200)
    decided_at: datetime


class DeliveryEventRecord(StrictBaseModel):
    thread_id: str = Field(min_length=1, max_length=500)
    run_id: str = Field(min_length=1, max_length=200)
    send_result: str = Field(min_length=1, max_length=100)
    delivery_idempotency_key: str | None = Field(default=None, max_length=300)
    message_id: str | None = Field(default=None, max_length=500)
    sent_at: str | None = Field(default=None, max_length=100)
    request_id: str | None = Field(default=None, max_length=200)
    created_at: datetime


class LeadArtifacts(StrictBaseModel):
    user: UserRecord | None = None
    lead: LeadRecord
    sources: list[SourceRecord] = Field(default_factory=list)
    contacts: list[ContactRecord] = Field(default_factory=list)
    company_signals: list[CompanySignalRecord] = Field(default_factory=list)
    score_breakdown: ScoreBreakdownRecord | None = None
    outreach_draft: OutreachDraftRecord | None = None
    decision: DecisionRecord | None = None
    delivery_event: DeliveryEventRecord | None = None


def build_lead_artifacts(snapshot: SnapshotForArtifacts) -> LeadArtifacts:
    """Build queryable app-owned records from the latest graph/API snapshot."""
    result = snapshot.result
    profile = _dict_or_none(result.get("company_profile"))
    contact = _dict_or_none(result.get("contact"))
    signals = _list_of_dicts(result.get("signals"))

    lead = LeadRecord(
        thread_id=snapshot.thread_id,
        run_id=snapshot.run_id,
        user_id=_optional_string(result.get("user_id")),
        domain=snapshot.domain,
        company_url=snapshot.company_url,
        company_name=_profile_value(profile, "name"),
        tagline=_profile_value(profile, "tagline"),
        hq=_profile_value(profile, "hq"),
        employees_estimate=_profile_value(profile, "employees_estimate"),
        funding_stage=_profile_value(profile, "funding_stage"),
        status=snapshot.status,
        fit_score=_optional_int(result.get("fit_score")),
        fit_level=_optional_string(result.get("fit_level")),
        score_confidence=_optional_string(result.get("score_confidence")),
        needs_human_review=_optional_bool(result.get("needs_human_review")),
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
    )

    return LeadArtifacts(
        lead=lead,
        sources=_build_source_records(snapshot, profile, signals, result),
        contacts=_build_contact_records(snapshot, contact),
        company_signals=_build_signal_records(snapshot, signals),
        score_breakdown=_build_score_breakdown(snapshot, result),
        outreach_draft=_build_outreach_draft(snapshot, result),
        decision=_build_decision(snapshot, result),
        delivery_event=_build_delivery_event(snapshot, result),
    )


def _build_source_records(
    snapshot: SnapshotForArtifacts,
    profile: dict[str, Any] | None,
    signals: list[dict[str, Any]],
    result: dict[str, Any],
) -> list[SourceRecord]:
    records: list[SourceRecord] = []
    seen: set[tuple[str, str, str, str]] = set()

    def add_source(
        *,
        source_type: SourceType,
        source_url: str | None = None,
        source_location: str | None = None,
        claim: str | None = None,
        source_text: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        source_url_clean = _optional_string(source_url)
        source_location_clean = _optional_string(source_location)
        claim_clean = _optional_string(claim)
        source_text_clean = _optional_string(source_text, max_length=10_000)
        if not any((source_url_clean, source_location_clean, claim_clean, source_text_clean)):
            return

        key = (
            source_type,
            source_url_clean or "",
            source_location_clean or "",
            claim_clean or "",
        )
        if key in seen:
            return
        seen.add(key)

        records.append(
            SourceRecord(
                source_id=f"{snapshot.thread_id}:source:{len(records)}",
                thread_id=snapshot.thread_id,
                run_id=snapshot.run_id,
                source_type=source_type,
                source_url=source_url_clean,
                source_location=source_location_clean,
                claim=claim_clean,
                source_text=source_text_clean,
                metadata=metadata or {},
                created_at=snapshot.updated_at,
            )
        )

    if profile is not None:
        for source_url in _string_list(profile.get("sources")):
            add_source(
                source_type="company_profile",
                source_url=source_url,
                source_location="company_profile.sources",
            )

    for signal in signals:
        add_source(
            source_type="company_signal",
            source_url=_optional_string(signal.get("source")),
            source_location="signals",
            claim=_optional_string(signal.get("details")),
            metadata={
                "signal_type": _optional_string(signal.get("signal_type")),
                "date": _optional_string(signal.get("date")),
            },
        )

    grounding_report = _dict_or_none(result.get("grounding_report")) or {}
    for source_url in _string_list(grounding_report.get("source_urls")):
        add_source(
            source_type="grounding_report",
            source_url=source_url,
            source_location="grounding_report.source_urls",
        )

    evidence = _dict_or_none(grounding_report.get("evidence")) or {}
    for item in _list_of_dicts(evidence.get("items")):
        add_source(
            source_type="evidence",
            source_url=_optional_string(item.get("source_url")),
            source_location=_optional_string(item.get("source_location")),
            claim=_optional_string(item.get("claim")),
            source_text=_optional_string(item.get("source_text")),
            metadata={"confidence": _optional_string(item.get("confidence"))},
        )

    return records


def _build_contact_records(
    snapshot: SnapshotForArtifacts,
    contact: dict[str, Any] | None,
) -> list[ContactRecord]:
    if contact is None:
        return []
    has_contact_detail = any(contact.get(key) for key in ("name", "title", "email", "linkedin"))
    if not has_contact_detail:
        return []
    return [
        ContactRecord(
            contact_id=f"{snapshot.thread_id}:contact:primary",
            thread_id=snapshot.thread_id,
            run_id=snapshot.run_id,
            name=_optional_string(contact.get("name")),
            title=_optional_string(contact.get("title")),
            email=_optional_string(contact.get("email")),
            linkedin=_optional_string(contact.get("linkedin")),
            confidence=_optional_float(contact.get("confidence")),
            source=_optional_string(contact.get("source")),
            created_at=snapshot.created_at,
            updated_at=snapshot.updated_at,
        )
    ]


def _build_signal_records(
    snapshot: SnapshotForArtifacts,
    signals: list[dict[str, Any]],
) -> list[CompanySignalRecord]:
    records: list[CompanySignalRecord] = []
    for index, signal in enumerate(signals):
        signal_type = _optional_string(signal.get("signal_type"))
        source = _optional_string(signal.get("source"))
        details = _optional_string(signal.get("details"))
        if signal_type is None or source is None or details is None:
            continue
        records.append(
            CompanySignalRecord(
                signal_id=f"{snapshot.thread_id}:signal:{index}",
                thread_id=snapshot.thread_id,
                run_id=snapshot.run_id,
                position=index,
                signal_type=signal_type,
                date=_optional_string(signal.get("date")),
                source=source,
                details=details,
                created_at=snapshot.updated_at,
            )
        )
    return records


def _build_score_breakdown(
    snapshot: SnapshotForArtifacts,
    result: dict[str, Any],
) -> ScoreBreakdownRecord | None:
    fields = (
        "fit_score",
        "fit_level",
        "score_breakdown",
        "score_confidence",
        "score_explanation",
        "needs_human_review",
        "score_reasons",
        "score_uncertainty",
        "grounding_report",
        "outreach_quality",
    )
    if not any(result.get(field) is not None for field in fields):
        return None
    return ScoreBreakdownRecord(
        thread_id=snapshot.thread_id,
        run_id=snapshot.run_id,
        fit_score=_optional_int(result.get("fit_score")),
        fit_level=_optional_string(result.get("fit_level")),
        score_breakdown=_dict_or_none(result.get("score_breakdown")) or {},
        score_confidence=_optional_string(result.get("score_confidence")),
        score_explanation=_optional_string(result.get("score_explanation")),
        needs_human_review=_optional_bool(result.get("needs_human_review")),
        score_reasons=_string_list(result.get("score_reasons")),
        score_uncertainty=_string_list(result.get("score_uncertainty")),
        grounding_report=_dict_or_none(result.get("grounding_report")),
        outreach_quality=_dict_or_none(result.get("outreach_quality")),
        updated_at=snapshot.updated_at,
    )


def _build_outreach_draft(
    snapshot: SnapshotForArtifacts,
    result: dict[str, Any],
) -> OutreachDraftRecord | None:
    subject = _optional_string(result.get("email_subject"))
    body = _optional_string(result.get("email_body"), max_length=10_000)
    if subject is None and body is None:
        return None
    return OutreachDraftRecord(
        thread_id=snapshot.thread_id,
        run_id=snapshot.run_id,
        email_subject=subject,
        email_body=body,
        outreach_quality=_dict_or_none(result.get("outreach_quality")),
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
    )


def _build_decision(
    snapshot: SnapshotForArtifacts,
    result: dict[str, Any],
) -> DecisionRecord | None:
    approved = result.get("email_approved")
    if not isinstance(approved, bool):
        return None
    return DecisionRecord(
        thread_id=snapshot.thread_id,
        run_id=snapshot.run_id,
        decision="approved" if approved else "rejected",
        request_id=snapshot.request_id,
        decided_at=snapshot.updated_at,
    )


def _build_delivery_event(
    snapshot: SnapshotForArtifacts,
    result: dict[str, Any],
) -> DeliveryEventRecord | None:
    send_result = _optional_string(result.get("send_result"))
    if send_result is None:
        return None
    return DeliveryEventRecord(
        thread_id=snapshot.thread_id,
        run_id=snapshot.run_id,
        send_result=send_result,
        delivery_idempotency_key=_optional_string(
            result.get("delivery_idempotency_key"),
            max_length=300,
        ),
        message_id=_optional_string(result.get("message_id")),
        sent_at=_optional_string(result.get("sent_at")),
        request_id=snapshot.request_id,
        created_at=snapshot.updated_at,
    )


def _profile_value(profile: dict[str, Any] | None, key: str) -> str | None:
    if profile is None:
        return None
    return _optional_string(profile.get(key))


def _dict_or_none(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [clean for item in value if (clean := _optional_string(item)) is not None]


def _optional_string(value: Any, *, max_length: int = 2_000) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:max_length]


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None
