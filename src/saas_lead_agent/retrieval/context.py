"""Context assembly policy for retrieved chunks."""

from collections.abc import Iterable

from saas_lead_agent.schemas import ContextBundle, RetrievedChunk


def assemble_context_bundle(
    chunks: Iterable[RetrievedChunk],
    *,
    token_budget: int,
) -> ContextBundle:
    """Build a trusted/untrusted context bundle within a token budget."""
    if token_budget < 0:
        raise ValueError("token_budget cannot be negative")

    trusted_chunks: list[RetrievedChunk] = []
    untrusted_chunks: list[RetrievedChunk] = []
    citations: list[dict[str, object]] = []
    omitted_reasons: dict[str, str] = {}
    selected_tokens = 0
    seen_text_hashes: set[str] = set()

    for chunk in _prioritized_chunks(chunks):
        text_hash = _text_hash(chunk)
        if text_hash in seen_text_hashes:
            omitted_reasons[chunk.chunk_id] = "duplicate_text"
            continue

        if selected_tokens + chunk.token_count > token_budget:
            omitted_reasons[chunk.chunk_id] = "token_budget_exceeded"
            continue

        seen_text_hashes.add(text_hash)
        selected_tokens += chunk.token_count
        citations.append(_citation(chunk))
        if chunk.trust_label == "untrusted_external":
            untrusted_chunks.append(chunk)
        else:
            trusted_chunks.append(chunk)

    return ContextBundle(
        trusted_chunks=trusted_chunks,
        untrusted_chunks=untrusted_chunks,
        citations=citations,
        token_count=selected_tokens,
        omitted_reasons=omitted_reasons,
    )


def _prioritized_chunks(chunks: Iterable[RetrievedChunk]) -> list[RetrievedChunk]:
    return sorted(
        chunks,
        key=lambda chunk: (
            chunk.trust_label == "untrusted_external",
            -(chunk.score or 0.0),
            chunk.chunk_id,
        ),
    )


def _text_hash(chunk: RetrievedChunk) -> str:
    value = chunk.metadata.get("text_hash")
    return value if isinstance(value, str) and value else chunk.text


def _citation(chunk: RetrievedChunk) -> dict[str, object]:
    return {
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "document_type": chunk.document_type,
        "trust_label": chunk.trust_label,
        "source_uri": chunk.source_uri,
        "source_location": chunk.source_location,
        "score": chunk.score,
        "token_count": chunk.token_count,
    }
