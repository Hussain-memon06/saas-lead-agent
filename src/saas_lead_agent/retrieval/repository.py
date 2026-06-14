"""In-memory retrieval repository for Phase 4 tests and local development."""

from __future__ import annotations

import re
from collections.abc import Iterable

from saas_lead_agent.retrieval.chunking import chunk_text
from saas_lead_agent.schemas import (
    DocumentType,
    KnowledgeChunk,
    KnowledgeDocument,
    RetrievedChunk,
    TrustLabel,
)

_TERM_RE = re.compile(r"[a-zA-Z0-9]+")


class InMemoryRetrievalRepository:
    """Simple lexical repository used before embedding/vector dependencies exist."""

    def __init__(self) -> None:
        self._documents: dict[str, KnowledgeDocument] = {}
        self._chunks: dict[str, KnowledgeChunk] = {}

    def upsert_document(self, document: KnowledgeDocument) -> KnowledgeDocument:
        self._documents[document.document_id] = document
        return document

    def upsert_chunks(self, chunks: Iterable[KnowledgeChunk]) -> list[KnowledgeChunk]:
        saved = list(chunks)
        for chunk in saved:
            self._chunks[chunk.chunk_id] = chunk
        return saved

    def ingest_document(
        self,
        *,
        document: KnowledgeDocument,
        text: str,
        target_tokens: int = 500,
        overlap_tokens: int = 50,
    ) -> list[KnowledgeChunk]:
        """Store a document and replace its chunks with deterministic chunks."""
        self.upsert_document(document)
        for chunk_id, chunk in list(self._chunks.items()):
            if chunk.document_id == document.document_id:
                del self._chunks[chunk_id]
        return self.upsert_chunks(
            chunk_text(
                document=document,
                text=text,
                target_tokens=target_tokens,
                overlap_tokens=overlap_tokens,
            )
        )

    def get_document(self, document_id: str) -> KnowledgeDocument | None:
        return self._documents.get(document_id)

    def list_chunks(
        self,
        *,
        user_id: str | None = None,
        document_types: set[DocumentType] | None = None,
        trust_labels: set[TrustLabel] | None = None,
    ) -> list[KnowledgeChunk]:
        chunks = [
            chunk
            for chunk in self._chunks.values()
            if self._is_searchable(chunk)
            and (user_id is None or chunk.user_id == user_id)
            and (document_types is None or chunk.document_type in document_types)
            and (trust_labels is None or chunk.trust_label in trust_labels)
        ]
        return sorted(chunks, key=lambda chunk: chunk.chunk_id)

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        user_id: str | None = None,
        document_types: set[DocumentType] | None = None,
        trust_labels: set[TrustLabel] | None = None,
    ) -> list[RetrievedChunk]:
        """Return lexical matches sorted by score, then stable chunk ID."""
        if top_k < 1:
            raise ValueError("top_k must be at least 1")

        query_terms = _terms(query)
        if not query_terms:
            return []

        results: list[RetrievedChunk] = []
        for chunk in self.list_chunks(
            user_id=user_id,
            document_types=document_types,
            trust_labels=trust_labels,
        ):
            chunk_terms = _terms(chunk.text)
            matched_terms = sorted(query_terms & chunk_terms)
            if not matched_terms:
                continue
            score = round(len(matched_terms) / len(query_terms), 6)
            results.append(_retrieved_chunk(chunk, score=score, matched_terms=matched_terms))

        return sorted(results, key=lambda chunk: (-(chunk.score or 0.0), chunk.chunk_id))[:top_k]

    def _is_searchable(self, chunk: KnowledgeChunk) -> bool:
        document = self._documents.get(chunk.document_id)
        return document is not None and document.status == "active"


def _retrieved_chunk(
    chunk: KnowledgeChunk,
    *,
    score: float,
    matched_terms: list[str],
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        document_type=chunk.document_type,
        trust_label=chunk.trust_label,
        text=chunk.text,
        token_count=chunk.token_count,
        score=score,
        source_uri=chunk.source_uri,
        source_location=chunk.source_location,
        metadata={
            **chunk.metadata,
            "matched_terms": matched_terms,
            "retrieval_reason": "lexical_term_match",
            "text_hash": chunk.text_hash,
        },
    )


def _terms(text: str) -> set[str]:
    return {term.lower() for term in _TERM_RE.findall(text)}
