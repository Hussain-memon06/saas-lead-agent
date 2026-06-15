"""Retrieval utilities for Phase 4 RAG work."""

from saas_lead_agent.retrieval.chunking import chunk_text, estimate_token_count, hash_text
from saas_lead_agent.retrieval.context import assemble_context_bundle
from saas_lead_agent.retrieval.events import build_retrieval_event
from saas_lead_agent.retrieval.quality import RetrievalQualityResult, evaluate_retrieval_quality
from saas_lead_agent.retrieval.repository import InMemoryRetrievalRepository

__all__ = [
    "InMemoryRetrievalRepository",
    "RetrievalQualityResult",
    "assemble_context_bundle",
    "build_retrieval_event",
    "chunk_text",
    "evaluate_retrieval_quality",
    "estimate_token_count",
    "hash_text",
]
