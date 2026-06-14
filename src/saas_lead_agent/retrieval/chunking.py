"""Deterministic text chunking for retrieval documents."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from saas_lead_agent.schemas import KnowledgeChunk, KnowledgeDocument

_WHITESPACE_RE = re.compile(r"\s+")


def hash_text(text: str) -> str:
    """Return a stable content hash for normalized text."""
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def estimate_token_count(text: str) -> int:
    """Return a deterministic, dependency-free token estimate."""
    normalized = normalize_text(text)
    return len(normalized.split()) if normalized else 0


def normalize_text(text: str) -> str:
    """Collapse whitespace without changing word order."""
    return _WHITESPACE_RE.sub(" ", text).strip()


def chunk_text(
    *,
    document: KnowledgeDocument,
    text: str,
    target_tokens: int = 500,
    overlap_tokens: int = 50,
) -> list[KnowledgeChunk]:
    """Split text into stable word-based chunks for later embedding.

    This intentionally uses a simple word estimate instead of a tokenizer so
    Phase 4 can start without model/provider dependencies.
    """
    if target_tokens < 1:
        raise ValueError("target_tokens must be at least 1")
    if overlap_tokens < 0:
        raise ValueError("overlap_tokens cannot be negative")
    if overlap_tokens >= target_tokens:
        raise ValueError("overlap_tokens must be smaller than target_tokens")

    normalized = normalize_text(text)
    if not normalized:
        return []

    words = normalized.split()
    chunks: list[KnowledgeChunk] = []
    start = 0
    created_at = datetime.now(UTC)
    while start < len(words):
        end = min(start + target_tokens, len(words))
        chunk_words = words[start:end]
        chunk_body = " ".join(chunk_words)
        chunk_index = len(chunks)
        chunks.append(
            KnowledgeChunk(
                chunk_id=f"{document.document_id}:v{document.version}:chunk:{chunk_index}",
                document_id=document.document_id,
                user_id=document.user_id,
                document_type=document.document_type,
                trust_label=document.trust_label,
                chunk_index=chunk_index,
                text=chunk_body,
                text_hash=hash_text(chunk_body),
                token_count=len(chunk_words),
                source_uri=document.source_uri,
                source_location=f"tokens:{start}-{end}",
                metadata={
                    "document_version": document.version,
                    "token_start": start,
                    "token_end": end,
                },
                created_at=created_at,
            )
        )
        if end == len(words):
            break
        start = end - overlap_tokens

    return chunks
