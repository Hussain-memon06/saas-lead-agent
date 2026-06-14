"""Contracts for Phase 4 retrieval and context assembly."""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from saas_lead_agent.schemas.base import StrictBaseModel

DocumentType = Literal[
    "icp",
    "offer",
    "lead_example",
    "source_page",
    "prior_dossier",
    "outreach_example",
]
TrustLabel = Literal["trusted_user", "trusted_generated", "untrusted_external"]
DocumentStatus = Literal["active", "superseded", "deleted"]


class KnowledgeDocument(StrictBaseModel):
    document_id: str = Field(min_length=1, max_length=200)
    user_id: str | None = Field(default=None, max_length=200)
    document_type: DocumentType
    trust_label: TrustLabel
    title: str | None = Field(default=None, max_length=300)
    source_uri: str | None = Field(default=None, max_length=2_048)
    content_hash: str = Field(min_length=16, max_length=128)
    version: int = Field(default=1, ge=1)
    status: DocumentStatus = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_trust_boundary(self) -> "KnowledgeDocument":
        if self.document_type == "source_page" and self.trust_label != "untrusted_external":
            raise ValueError("source_page documents must use trust_label='untrusted_external'")
        if self.document_type in {"icp", "offer", "lead_example"}:
            if self.trust_label != "trusted_user":
                raise ValueError(
                    f"{self.document_type} documents must use trust_label='trusted_user'"
                )
        if self.document_type == "prior_dossier" and self.trust_label != "trusted_generated":
            raise ValueError("prior_dossier documents must use trust_label='trusted_generated'")
        return self


class KnowledgeChunk(StrictBaseModel):
    chunk_id: str = Field(min_length=1, max_length=300)
    document_id: str = Field(min_length=1, max_length=200)
    user_id: str | None = Field(default=None, max_length=200)
    document_type: DocumentType
    trust_label: TrustLabel
    chunk_index: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=20_000)
    text_hash: str = Field(min_length=16, max_length=128)
    token_count: int = Field(ge=1)
    source_uri: str | None = Field(default=None, max_length=2_048)
    source_location: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EmbeddingRecord(StrictBaseModel):
    embedding_id: str = Field(min_length=1, max_length=300)
    chunk_id: str = Field(min_length=1, max_length=300)
    document_id: str = Field(min_length=1, max_length=200)
    user_id: str | None = Field(default=None, max_length=200)
    provider: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=200)
    dimensions: int = Field(ge=1, le=16_384)
    embedding_hash: str = Field(min_length=16, max_length=128)
    vector: list[float] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_vector_dimensions(self) -> "EmbeddingRecord":
        if self.vector is not None and len(self.vector) != self.dimensions:
            raise ValueError("vector length must match dimensions")
        return self


class RetrievedChunk(StrictBaseModel):
    chunk_id: str = Field(min_length=1, max_length=300)
    document_id: str = Field(min_length=1, max_length=200)
    document_type: DocumentType
    trust_label: TrustLabel
    text: str = Field(min_length=1, max_length=20_000)
    token_count: int = Field(ge=1)
    score: float | None = Field(default=None, ge=0.0)
    source_uri: str | None = Field(default=None, max_length=2_048)
    source_location: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalEvent(StrictBaseModel):
    event_id: str = Field(min_length=1, max_length=300)
    run_id: str = Field(min_length=1, max_length=200)
    thread_id: str = Field(min_length=1, max_length=500)
    request_id: str | None = Field(default=None, max_length=200)
    user_id: str | None = Field(default=None, max_length=200)
    retrieval_node: str = Field(min_length=1, max_length=100)
    query_text_hash: str = Field(min_length=16, max_length=128)
    query_metadata: dict[str, Any] = Field(default_factory=dict)
    filters: dict[str, Any] = Field(default_factory=dict)
    top_k: int = Field(ge=1, le=100)
    selected_chunk_ids: list[str] = Field(default_factory=list, max_length=100)
    scores: dict[str, float] = Field(default_factory=dict)
    reasons: dict[str, str] = Field(default_factory=dict)
    token_budget: int = Field(default=0, ge=0)
    tokens_selected: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ContextBundle(StrictBaseModel):
    trusted_chunks: list[RetrievedChunk] = Field(default_factory=list, max_length=50)
    untrusted_chunks: list[RetrievedChunk] = Field(default_factory=list, max_length=50)
    citations: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    token_count: int = Field(default=0, ge=0)
    omitted_reasons: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_trust_split(self) -> "ContextBundle":
        for chunk in self.trusted_chunks:
            if chunk.trust_label == "untrusted_external":
                raise ValueError("trusted_chunks cannot include untrusted_external chunks")
        for chunk in self.untrusted_chunks:
            if chunk.trust_label != "untrusted_external":
                raise ValueError("untrusted_chunks must use trust_label='untrusted_external'")
        return self
