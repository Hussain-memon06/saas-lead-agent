"""App-owned lead run persistence.

LangGraph checkpoints preserve executable graph state. These records preserve
product-facing run snapshots so the frontend can recover a dossier after a
browser refresh and operators can inspect coarse run lifecycle events.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from pydantic import Field

from saas_lead_agent.persistence.lead_artifacts import (
    CompanySignalRecord,
    ContactRecord,
    DecisionRecord,
    DeliveryEventRecord,
    LeadArtifacts,
    LeadRecord,
    OutreachDraftRecord,
    ScoreBreakdownRecord,
    SourceRecord,
    UserRecord,
    build_lead_artifacts,
)
from saas_lead_agent.schemas.base import StrictBaseModel

RunStatus = Literal["interrupted", "completed", "failed"]


def utc_now() -> datetime:
    return datetime.now(UTC)


def _snapshot_owner_id(snapshot: LeadRunSnapshot) -> str | None:
    value = snapshot.result.get("user_id")
    if not isinstance(value, str):
        return None
    clean = value.strip()
    return clean or None


class LeadRunSnapshot(StrictBaseModel):
    run_id: str = Field(min_length=1, max_length=200)
    thread_id: str = Field(min_length=1, max_length=500)
    domain: str = Field(min_length=1, max_length=500)
    company_url: str = Field(min_length=1, max_length=2_048)
    status: RunStatus
    result: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = Field(default=None, max_length=200)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RunEvent(StrictBaseModel):
    run_id: str = Field(min_length=1, max_length=200)
    thread_id: str = Field(min_length=1, max_length=500)
    event_type: str = Field(min_length=1, max_length=100)
    metadata: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = Field(default=None, max_length=200)
    created_at: datetime = Field(default_factory=utc_now)


class LeadRunRepository(Protocol):
    async def setup(self) -> None:
        """Prepare backing storage."""

    async def close(self) -> None:
        """Release backing resources."""

    async def save_snapshot(self, snapshot: LeadRunSnapshot) -> LeadRunSnapshot:
        """Persist the latest product-facing state for a thread."""

    async def get_by_thread_id(self, thread_id: str) -> LeadRunSnapshot | None:
        """Return the latest product-facing state for a thread."""

    async def list_snapshots(self, limit: int = 20) -> list[LeadRunSnapshot]:
        """Return recent product-facing states, newest first."""

    async def list_snapshots_for_owner(
        self,
        owner_user_id: str | None,
        limit: int = 20,
    ) -> list[LeadRunSnapshot]:
        """Return recent snapshots for one owner, or legacy unowned records."""

    async def save_artifacts(self, artifacts: LeadArtifacts) -> None:
        """Persist normalized app-owned records derived from a snapshot."""

    async def get_artifacts_by_thread_id(self, thread_id: str) -> LeadArtifacts | None:
        """Return normalized app-owned records for a thread."""

    async def record_event(self, event: RunEvent) -> None:
        """Persist an audit-style lifecycle event."""

    async def list_events(self, thread_id: str) -> list[RunEvent]:
        """Return lifecycle events for tests/debugging."""


class InMemoryLeadRunRepository:
    """Process-local repository used when app-owned Postgres is not configured."""

    def __init__(self) -> None:
        self._snapshots: dict[str, LeadRunSnapshot] = {}
        self._artifacts: dict[str, LeadArtifacts] = {}
        self._events: list[RunEvent] = []

    async def setup(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def save_snapshot(self, snapshot: LeadRunSnapshot) -> LeadRunSnapshot:
        existing = self._snapshots.get(snapshot.thread_id)
        saved = snapshot
        if existing is not None:
            saved = snapshot.model_copy(update={"created_at": existing.created_at})
        self._snapshots[snapshot.thread_id] = saved
        await self.save_artifacts(build_lead_artifacts(saved))
        return saved

    async def get_by_thread_id(self, thread_id: str) -> LeadRunSnapshot | None:
        return self._snapshots.get(thread_id)

    async def list_snapshots(self, limit: int = 20) -> list[LeadRunSnapshot]:
        return sorted(
            self._snapshots.values(),
            key=lambda snapshot: snapshot.updated_at,
            reverse=True,
        )[:limit]

    async def list_snapshots_for_owner(
        self,
        owner_user_id: str | None,
        limit: int = 20,
    ) -> list[LeadRunSnapshot]:
        snapshots = sorted(
            self._snapshots.values(),
            key=lambda snapshot: snapshot.updated_at,
            reverse=True,
        )
        return [
            snapshot for snapshot in snapshots if _snapshot_owner_id(snapshot) == owner_user_id
        ][:limit]

    async def save_artifacts(self, artifacts: LeadArtifacts) -> None:
        self._artifacts[artifacts.lead.thread_id] = artifacts

    async def get_artifacts_by_thread_id(self, thread_id: str) -> LeadArtifacts | None:
        return self._artifacts.get(thread_id)

    async def record_event(self, event: RunEvent) -> None:
        self._events.append(event)

    async def list_events(self, thread_id: str) -> list[RunEvent]:
        return [event for event in self._events if event.thread_id == thread_id]


class PostgresLeadRunRepository:
    """Postgres implementation for app-owned run snapshots and events."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._pool: Any | None = None

    async def setup(self) -> None:
        import asyncpg

        self._pool = await asyncpg.create_pool(self.database_url)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_lead_runs (
                    thread_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    company_url TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result JSONB NOT NULL,
                    request_id TEXT,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_app_lead_runs_run_id
                ON app_lead_runs (run_id)
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_run_events (
                    id BIGSERIAL PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    metadata JSONB NOT NULL,
                    request_id TEXT,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_app_run_events_thread_id
                ON app_run_events (thread_id, created_at)
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT,
                    display_name TEXT,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_leads (
                    thread_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    user_id TEXT,
                    domain TEXT NOT NULL,
                    company_url TEXT NOT NULL,
                    company_name TEXT,
                    tagline TEXT,
                    hq TEXT,
                    employees_estimate TEXT,
                    funding_stage TEXT,
                    status TEXT NOT NULL,
                    fit_score INTEGER,
                    fit_level TEXT,
                    score_confidence TEXT,
                    needs_human_review BOOLEAN,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_app_leads_domain
                ON app_leads (domain)
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_app_leads_run_id
                ON app_leads (run_id)
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_sources (
                    source_id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_url TEXT,
                    source_location TEXT,
                    claim TEXT,
                    source_text TEXT,
                    metadata JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_app_sources_thread_id
                ON app_sources (thread_id)
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_contacts (
                    contact_id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    name TEXT,
                    title TEXT,
                    email TEXT,
                    linkedin TEXT,
                    confidence DOUBLE PRECISION,
                    source TEXT,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_app_contacts_thread_id
                ON app_contacts (thread_id)
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_company_signals (
                    signal_id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    signal_type TEXT NOT NULL,
                    date TEXT,
                    source TEXT NOT NULL,
                    details TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_app_company_signals_thread_id
                ON app_company_signals (thread_id, position)
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_score_breakdowns (
                    thread_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    fit_score INTEGER,
                    fit_level TEXT,
                    score_breakdown JSONB NOT NULL,
                    score_confidence TEXT,
                    score_explanation TEXT,
                    needs_human_review BOOLEAN,
                    score_reasons JSONB NOT NULL,
                    score_uncertainty JSONB NOT NULL,
                    grounding_report JSONB,
                    outreach_quality JSONB,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_outreach_drafts (
                    thread_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    email_subject TEXT,
                    email_body TEXT,
                    outreach_quality JSONB,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_decisions (
                    thread_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    request_id TEXT,
                    decided_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_delivery_events (
                    thread_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    send_result TEXT NOT NULL,
                    delivery_idempotency_key TEXT,
                    message_id TEXT,
                    sent_at TEXT,
                    request_id TEXT,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            await conn.execute(
                """
                ALTER TABLE app_delivery_events
                ADD COLUMN IF NOT EXISTS delivery_idempotency_key TEXT
                """
            )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def save_snapshot(self, snapshot: LeadRunSnapshot) -> LeadRunSnapshot:
        pool = self._require_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO app_lead_runs (
                    thread_id,
                    run_id,
                    domain,
                    company_url,
                    status,
                    result,
                    request_id,
                    created_at,
                    updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9)
                ON CONFLICT (thread_id) DO UPDATE SET
                    run_id = EXCLUDED.run_id,
                    domain = EXCLUDED.domain,
                    company_url = EXCLUDED.company_url,
                    status = EXCLUDED.status,
                    result = EXCLUDED.result,
                    request_id = EXCLUDED.request_id,
                    updated_at = EXCLUDED.updated_at
                RETURNING *
                """,
                snapshot.thread_id,
                snapshot.run_id,
                snapshot.domain,
                snapshot.company_url,
                snapshot.status,
                json.dumps(snapshot.result),
                snapshot.request_id,
                snapshot.created_at,
                snapshot.updated_at,
            )
        saved = self._snapshot_from_row(row)
        await self.save_artifacts(build_lead_artifacts(saved))
        return saved

    async def get_by_thread_id(self, thread_id: str) -> LeadRunSnapshot | None:
        pool = self._require_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM app_lead_runs WHERE thread_id = $1",
                thread_id,
            )
        return self._snapshot_from_row(row) if row is not None else None

    async def list_snapshots(self, limit: int = 20) -> list[LeadRunSnapshot]:
        pool = self._require_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM app_lead_runs
                ORDER BY updated_at DESC, created_at DESC
                LIMIT $1
                """,
                limit,
            )
        return [self._snapshot_from_row(row) for row in rows]

    async def list_snapshots_for_owner(
        self,
        owner_user_id: str | None,
        limit: int = 20,
    ) -> list[LeadRunSnapshot]:
        pool = self._require_pool()
        async with pool.acquire() as conn:
            if owner_user_id is None:
                rows = await conn.fetch(
                    """
                    SELECT *
                    FROM app_lead_runs
                    WHERE NULLIF(BTRIM(result->>'user_id'), '') IS NULL
                    ORDER BY updated_at DESC, created_at DESC
                    LIMIT $1
                    """,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT *
                    FROM app_lead_runs
                    WHERE result->>'user_id' = $1
                    ORDER BY updated_at DESC, created_at DESC
                    LIMIT $2
                    """,
                    owner_user_id,
                    limit,
                )
        return [self._snapshot_from_row(row) for row in rows]

    async def save_artifacts(self, artifacts: LeadArtifacts) -> None:
        pool = self._require_pool()
        lead = artifacts.lead
        async with pool.acquire() as conn:
            async with conn.transaction():
                if artifacts.user is not None:
                    user = artifacts.user
                    await conn.execute(
                        """
                        INSERT INTO app_users (
                            user_id, email, display_name, created_at, updated_at
                        )
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (user_id) DO UPDATE SET
                            email = EXCLUDED.email,
                            display_name = EXCLUDED.display_name,
                            updated_at = EXCLUDED.updated_at
                        """,
                        user.user_id,
                        user.email,
                        user.display_name,
                        user.created_at,
                        user.updated_at,
                    )

                await conn.execute(
                    """
                    INSERT INTO app_leads (
                        thread_id,
                        run_id,
                        user_id,
                        domain,
                        company_url,
                        company_name,
                        tagline,
                        hq,
                        employees_estimate,
                        funding_stage,
                        status,
                        fit_score,
                        fit_level,
                        score_confidence,
                        needs_human_review,
                        created_at,
                        updated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                            $10, $11, $12, $13, $14, $15, $16, $17)
                    ON CONFLICT (thread_id) DO UPDATE SET
                        run_id = EXCLUDED.run_id,
                        user_id = EXCLUDED.user_id,
                        domain = EXCLUDED.domain,
                        company_url = EXCLUDED.company_url,
                        company_name = EXCLUDED.company_name,
                        tagline = EXCLUDED.tagline,
                        hq = EXCLUDED.hq,
                        employees_estimate = EXCLUDED.employees_estimate,
                        funding_stage = EXCLUDED.funding_stage,
                        status = EXCLUDED.status,
                        fit_score = EXCLUDED.fit_score,
                        fit_level = EXCLUDED.fit_level,
                        score_confidence = EXCLUDED.score_confidence,
                        needs_human_review = EXCLUDED.needs_human_review,
                        updated_at = EXCLUDED.updated_at
                    """,
                    lead.thread_id,
                    lead.run_id,
                    lead.user_id,
                    lead.domain,
                    lead.company_url,
                    lead.company_name,
                    lead.tagline,
                    lead.hq,
                    lead.employees_estimate,
                    lead.funding_stage,
                    lead.status,
                    lead.fit_score,
                    lead.fit_level,
                    lead.score_confidence,
                    lead.needs_human_review,
                    lead.created_at,
                    lead.updated_at,
                )

                await conn.execute("DELETE FROM app_sources WHERE thread_id = $1", lead.thread_id)
                if artifacts.sources:
                    await conn.executemany(
                        """
                        INSERT INTO app_sources (
                            source_id,
                            thread_id,
                            run_id,
                            source_type,
                            source_url,
                            source_location,
                            claim,
                            source_text,
                            metadata,
                            created_at
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10)
                        """,
                        [
                            (
                                source.source_id,
                                source.thread_id,
                                source.run_id,
                                source.source_type,
                                source.source_url,
                                source.source_location,
                                source.claim,
                                source.source_text,
                                json.dumps(source.metadata),
                                source.created_at,
                            )
                            for source in artifacts.sources
                        ],
                    )

                await conn.execute("DELETE FROM app_contacts WHERE thread_id = $1", lead.thread_id)
                if artifacts.contacts:
                    await conn.executemany(
                        """
                        INSERT INTO app_contacts (
                            contact_id,
                            thread_id,
                            run_id,
                            name,
                            title,
                            email,
                            linkedin,
                            confidence,
                            source,
                            created_at,
                            updated_at
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                        """,
                        [
                            (
                                contact.contact_id,
                                contact.thread_id,
                                contact.run_id,
                                contact.name,
                                contact.title,
                                contact.email,
                                contact.linkedin,
                                contact.confidence,
                                contact.source,
                                contact.created_at,
                                contact.updated_at,
                            )
                            for contact in artifacts.contacts
                        ],
                    )

                await conn.execute(
                    "DELETE FROM app_company_signals WHERE thread_id = $1",
                    lead.thread_id,
                )
                if artifacts.company_signals:
                    await conn.executemany(
                        """
                        INSERT INTO app_company_signals (
                            signal_id,
                            thread_id,
                            run_id,
                            position,
                            signal_type,
                            date,
                            source,
                            details,
                            created_at
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        """,
                        [
                            (
                                signal.signal_id,
                                signal.thread_id,
                                signal.run_id,
                                signal.position,
                                signal.signal_type,
                                signal.date,
                                signal.source,
                                signal.details,
                                signal.created_at,
                            )
                            for signal in artifacts.company_signals
                        ],
                    )

                score = artifacts.score_breakdown
                if score is None:
                    await conn.execute(
                        "DELETE FROM app_score_breakdowns WHERE thread_id = $1",
                        lead.thread_id,
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO app_score_breakdowns (
                            thread_id,
                            run_id,
                            fit_score,
                            fit_level,
                            score_breakdown,
                            score_confidence,
                            score_explanation,
                            needs_human_review,
                            score_reasons,
                            score_uncertainty,
                            grounding_report,
                            outreach_quality,
                            updated_at
                        )
                        VALUES (
                            $1, $2, $3, $4, $5::jsonb, $6, $7, $8,
                            $9::jsonb, $10::jsonb, $11::jsonb, $12::jsonb, $13
                        )
                        ON CONFLICT (thread_id) DO UPDATE SET
                            run_id = EXCLUDED.run_id,
                            fit_score = EXCLUDED.fit_score,
                            fit_level = EXCLUDED.fit_level,
                            score_breakdown = EXCLUDED.score_breakdown,
                            score_confidence = EXCLUDED.score_confidence,
                            score_explanation = EXCLUDED.score_explanation,
                            needs_human_review = EXCLUDED.needs_human_review,
                            score_reasons = EXCLUDED.score_reasons,
                            score_uncertainty = EXCLUDED.score_uncertainty,
                            grounding_report = EXCLUDED.grounding_report,
                            outreach_quality = EXCLUDED.outreach_quality,
                            updated_at = EXCLUDED.updated_at
                        """,
                        score.thread_id,
                        score.run_id,
                        score.fit_score,
                        score.fit_level,
                        json.dumps(score.score_breakdown),
                        score.score_confidence,
                        score.score_explanation,
                        score.needs_human_review,
                        json.dumps(score.score_reasons),
                        json.dumps(score.score_uncertainty),
                        (
                            json.dumps(score.grounding_report)
                            if score.grounding_report is not None
                            else None
                        ),
                        (
                            json.dumps(score.outreach_quality)
                            if score.outreach_quality is not None
                            else None
                        ),
                        score.updated_at,
                    )

                draft = artifacts.outreach_draft
                if draft is None:
                    await conn.execute(
                        "DELETE FROM app_outreach_drafts WHERE thread_id = $1",
                        lead.thread_id,
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO app_outreach_drafts (
                            thread_id,
                            run_id,
                            email_subject,
                            email_body,
                            outreach_quality,
                            created_at,
                            updated_at
                        )
                        VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
                        ON CONFLICT (thread_id) DO UPDATE SET
                            run_id = EXCLUDED.run_id,
                            email_subject = EXCLUDED.email_subject,
                            email_body = EXCLUDED.email_body,
                            outreach_quality = EXCLUDED.outreach_quality,
                            updated_at = EXCLUDED.updated_at
                        """,
                        draft.thread_id,
                        draft.run_id,
                        draft.email_subject,
                        draft.email_body,
                        (
                            json.dumps(draft.outreach_quality)
                            if draft.outreach_quality is not None
                            else None
                        ),
                        draft.created_at,
                        draft.updated_at,
                    )

                decision = artifacts.decision
                if decision is None:
                    await conn.execute(
                        "DELETE FROM app_decisions WHERE thread_id = $1",
                        lead.thread_id,
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO app_decisions (
                            thread_id, run_id, decision, request_id, decided_at
                        )
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (thread_id) DO UPDATE SET
                            run_id = EXCLUDED.run_id,
                            decision = EXCLUDED.decision,
                            request_id = EXCLUDED.request_id,
                            decided_at = EXCLUDED.decided_at
                        """,
                        decision.thread_id,
                        decision.run_id,
                        decision.decision,
                        decision.request_id,
                        decision.decided_at,
                    )

                delivery = artifacts.delivery_event
                if delivery is None:
                    await conn.execute(
                        "DELETE FROM app_delivery_events WHERE thread_id = $1",
                        lead.thread_id,
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO app_delivery_events (
                            thread_id,
                            run_id,
                            send_result,
                            delivery_idempotency_key,
                            message_id,
                            sent_at,
                            request_id,
                            created_at
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (thread_id) DO UPDATE SET
                            run_id = EXCLUDED.run_id,
                            send_result = EXCLUDED.send_result,
                            delivery_idempotency_key = EXCLUDED.delivery_idempotency_key,
                            message_id = EXCLUDED.message_id,
                            sent_at = EXCLUDED.sent_at,
                            request_id = EXCLUDED.request_id,
                            created_at = EXCLUDED.created_at
                        """,
                        delivery.thread_id,
                        delivery.run_id,
                        delivery.send_result,
                        delivery.delivery_idempotency_key,
                        delivery.message_id,
                        delivery.sent_at,
                        delivery.request_id,
                        delivery.created_at,
                    )

    async def get_artifacts_by_thread_id(self, thread_id: str) -> LeadArtifacts | None:
        pool = self._require_pool()
        async with pool.acquire() as conn:
            lead_row = await conn.fetchrow(
                "SELECT * FROM app_leads WHERE thread_id = $1",
                thread_id,
            )
            if lead_row is None:
                return None

            user_row = None
            if lead_row["user_id"] is not None:
                user_row = await conn.fetchrow(
                    "SELECT * FROM app_users WHERE user_id = $1",
                    lead_row["user_id"],
                )
            source_rows = await conn.fetch(
                """
                SELECT *
                FROM app_sources
                WHERE thread_id = $1
                ORDER BY source_id ASC
                """,
                thread_id,
            )
            contact_rows = await conn.fetch(
                """
                SELECT *
                FROM app_contacts
                WHERE thread_id = $1
                ORDER BY contact_id ASC
                """,
                thread_id,
            )
            signal_rows = await conn.fetch(
                """
                SELECT *
                FROM app_company_signals
                WHERE thread_id = $1
                ORDER BY position ASC
                """,
                thread_id,
            )
            score_row = await conn.fetchrow(
                "SELECT * FROM app_score_breakdowns WHERE thread_id = $1",
                thread_id,
            )
            draft_row = await conn.fetchrow(
                "SELECT * FROM app_outreach_drafts WHERE thread_id = $1",
                thread_id,
            )
            decision_row = await conn.fetchrow(
                "SELECT * FROM app_decisions WHERE thread_id = $1",
                thread_id,
            )
            delivery_row = await conn.fetchrow(
                "SELECT * FROM app_delivery_events WHERE thread_id = $1",
                thread_id,
            )

        return LeadArtifacts(
            user=self._user_from_row(user_row) if user_row is not None else None,
            lead=self._lead_from_row(lead_row),
            sources=[self._source_from_row(row) for row in source_rows],
            contacts=[self._contact_from_row(row) for row in contact_rows],
            company_signals=[self._signal_from_row(row) for row in signal_rows],
            score_breakdown=self._score_from_row(score_row) if score_row is not None else None,
            outreach_draft=self._draft_from_row(draft_row) if draft_row is not None else None,
            decision=self._decision_from_row(decision_row) if decision_row is not None else None,
            delivery_event=(
                self._delivery_from_row(delivery_row) if delivery_row is not None else None
            ),
        )

    async def record_event(self, event: RunEvent) -> None:
        pool = self._require_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO app_run_events (
                    run_id,
                    thread_id,
                    event_type,
                    metadata,
                    request_id,
                    created_at
                )
                VALUES ($1, $2, $3, $4::jsonb, $5, $6)
                """,
                event.run_id,
                event.thread_id,
                event.event_type,
                json.dumps(event.metadata),
                event.request_id,
                event.created_at,
            )

    async def list_events(self, thread_id: str) -> list[RunEvent]:
        pool = self._require_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT run_id, thread_id, event_type, metadata, request_id, created_at
                FROM app_run_events
                WHERE thread_id = $1
                ORDER BY created_at ASC, id ASC
                """,
                thread_id,
            )
        return [self._event_from_row(row) for row in rows]

    def _require_pool(self) -> Any:
        if self._pool is None:
            raise RuntimeError("PostgresLeadRunRepository.setup() has not been called")
        return self._pool

    def _snapshot_from_row(self, row: Any) -> LeadRunSnapshot:
        result = row["result"]
        if isinstance(result, str):
            result = json.loads(result)
        return LeadRunSnapshot(
            run_id=row["run_id"],
            thread_id=row["thread_id"],
            domain=row["domain"],
            company_url=row["company_url"],
            status=row["status"],
            result=result,
            request_id=row["request_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _event_from_row(self, row: Any) -> RunEvent:
        metadata = row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        return RunEvent(
            run_id=row["run_id"],
            thread_id=row["thread_id"],
            event_type=row["event_type"],
            metadata=metadata,
            request_id=row["request_id"],
            created_at=row["created_at"],
        )

    def _user_from_row(self, row: Any) -> UserRecord:
        return UserRecord(
            user_id=row["user_id"],
            email=row["email"],
            display_name=row["display_name"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _lead_from_row(self, row: Any) -> LeadRecord:
        return LeadRecord(
            thread_id=row["thread_id"],
            run_id=row["run_id"],
            user_id=row["user_id"],
            domain=row["domain"],
            company_url=row["company_url"],
            company_name=row["company_name"],
            tagline=row["tagline"],
            hq=row["hq"],
            employees_estimate=row["employees_estimate"],
            funding_stage=row["funding_stage"],
            status=row["status"],
            fit_score=row["fit_score"],
            fit_level=row["fit_level"],
            score_confidence=row["score_confidence"],
            needs_human_review=row["needs_human_review"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _source_from_row(self, row: Any) -> SourceRecord:
        return SourceRecord(
            source_id=row["source_id"],
            thread_id=row["thread_id"],
            run_id=row["run_id"],
            source_type=row["source_type"],
            source_url=row["source_url"],
            source_location=row["source_location"],
            claim=row["claim"],
            source_text=row["source_text"],
            metadata=self._json_value(row["metadata"], default={}),
            created_at=row["created_at"],
        )

    def _contact_from_row(self, row: Any) -> ContactRecord:
        return ContactRecord(
            contact_id=row["contact_id"],
            thread_id=row["thread_id"],
            run_id=row["run_id"],
            name=row["name"],
            title=row["title"],
            email=row["email"],
            linkedin=row["linkedin"],
            confidence=row["confidence"],
            source=row["source"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _signal_from_row(self, row: Any) -> CompanySignalRecord:
        return CompanySignalRecord(
            signal_id=row["signal_id"],
            thread_id=row["thread_id"],
            run_id=row["run_id"],
            position=row["position"],
            signal_type=row["signal_type"],
            date=row["date"],
            source=row["source"],
            details=row["details"],
            created_at=row["created_at"],
        )

    def _score_from_row(self, row: Any) -> ScoreBreakdownRecord:
        return ScoreBreakdownRecord(
            thread_id=row["thread_id"],
            run_id=row["run_id"],
            fit_score=row["fit_score"],
            fit_level=row["fit_level"],
            score_breakdown=self._json_value(row["score_breakdown"], default={}),
            score_confidence=row["score_confidence"],
            score_explanation=row["score_explanation"],
            needs_human_review=row["needs_human_review"],
            score_reasons=self._json_value(row["score_reasons"], default=[]),
            score_uncertainty=self._json_value(row["score_uncertainty"], default=[]),
            grounding_report=self._json_value(row["grounding_report"], default=None),
            outreach_quality=self._json_value(row["outreach_quality"], default=None),
            updated_at=row["updated_at"],
        )

    def _draft_from_row(self, row: Any) -> OutreachDraftRecord:
        return OutreachDraftRecord(
            thread_id=row["thread_id"],
            run_id=row["run_id"],
            email_subject=row["email_subject"],
            email_body=row["email_body"],
            outreach_quality=self._json_value(row["outreach_quality"], default=None),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _decision_from_row(self, row: Any) -> DecisionRecord:
        return DecisionRecord(
            thread_id=row["thread_id"],
            run_id=row["run_id"],
            decision=row["decision"],
            request_id=row["request_id"],
            decided_at=row["decided_at"],
        )

    def _delivery_from_row(self, row: Any) -> DeliveryEventRecord:
        return DeliveryEventRecord(
            thread_id=row["thread_id"],
            run_id=row["run_id"],
            send_result=row["send_result"],
            delivery_idempotency_key=row["delivery_idempotency_key"],
            message_id=row["message_id"],
            sent_at=row["sent_at"],
            request_id=row["request_id"],
            created_at=row["created_at"],
        )

    def _json_value(self, value: Any, *, default: Any) -> Any:
        if value is None:
            return default
        if isinstance(value, str):
            return json.loads(value)
        return value


def create_lead_run_repository(database_url: str | None) -> LeadRunRepository:
    if database_url:
        return PostgresLeadRunRepository(database_url)
    return InMemoryLeadRunRepository()
