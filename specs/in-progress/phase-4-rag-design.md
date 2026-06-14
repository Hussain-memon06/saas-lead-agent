# Phase 4: RAG, Embeddings, Vector Memory & Context Management

## Status

Design milestone complete. The first implementation slice added Pydantic
contracts and deterministic chunking without adding dependencies, vector
storage, embeddings, graph nodes, queues, MCP, auth, or eval runners.

## Goal

Ground qualification and outreach in user-owned context while preserving the
current deterministic scoring boundary.

Retrieval should help the agent find relevant ICP guidance, offers, prior lead
examples, prior dossiers, outreach examples, and source evidence. Retrieval
must not let generated prose or untrusted website text directly set the final
fit score.

## Current Baseline

The current graph is:

```text
company_researcher
  -> contact_finder
  -> signal_detector
  -> dossier_writer
  -> await_approval
  -> send_email
```

Phase 3 already added:

- app-owned latest-run records for leads, sources, contacts, company signals,
  score breakdowns, outreach drafts, decisions, and delivery events
- run events and sanitized run-event retrieval
- processing metadata with request/run IDs, timings, provider status, and token
  usage where provider metadata is available

Phase 4 should reuse those boundaries instead of creating a separate product
data model.

## Out Of Scope For This Milestone

- No embedding provider integration.
- No vector database, pgvector extension, Qdrant, Pinecone, or local ANN index.
- No dependency changes.
- No production auth or tenant enforcement beyond proposed metadata fields.
- No background queue or durable job system.
- No MCP integration.
- No eval runner implementation.
- No frontend upload/knowledge-base UI.

## Proposed Document Types

| Type | Owner | Trust Label | Purpose |
| --- | --- | --- | --- |
| `icp` | user | `trusted_user` | Target customer rules, must-have signals, red flags, geography, stage, size, personas |
| `offer` | user | `trusted_user` | Seller offer, value proposition, proof points, differentiation, constraints |
| `lead_example` | user | `trusted_user` | Positive or negative lead examples used for similarity and calibration |
| `source_page` | external web | `untrusted_external` | Scraped company pages, search-result snippets, public evidence |
| `prior_dossier` | app/generated | `trusted_generated` | Prior finalized lead reports and score breakdowns |
| `outreach_example` | user/app | `trusted_user` or `trusted_generated` | Approved outreach examples, tone references, winning patterns |

Trust labels are required because retrieval context is not all equally safe.
User-owned context may guide scoring and drafting. External scraped text is
evidence only and must never be treated as instructions.

## Proposed Entities

These are proposed app-owned entities for a later implementation. They can
start as Pydantic contracts and in-memory tests before any storage dependency
changes.

### `KnowledgeDocument`

- `document_id`: stable ID
- `user_id`: nullable until Phase 6 auth; required once auth exists
- `document_type`: one of the Phase 4 document types
- `trust_label`: `trusted_user`, `trusted_generated`, or `untrusted_external`
- `title`
- `source_uri`: URL, upload name, or internal reference
- `content_hash`
- `version`
- `status`: `active`, `superseded`, `deleted`
- `metadata`: structured metadata only
- `created_at`
- `updated_at`

### `KnowledgeChunk`

- `chunk_id`
- `document_id`
- `user_id`
- `document_type`
- `trust_label`
- `chunk_index`
- `text`
- `text_hash`
- `token_count`
- `source_uri`
- `source_location`
- `metadata`
- `created_at`

### `EmbeddingRecord`

- `embedding_id`
- `chunk_id`
- `document_id`
- `user_id`
- `provider`
- `model`
- `dimensions`
- `embedding_hash`
- `vector`: storage-specific, not exposed through public API
- `created_at`

### `RetrievalEvent`

- `event_id`
- `run_id`
- `thread_id`
- `request_id`
- `user_id`
- `retrieval_node`
- `query_text_hash`
- `query_metadata`
- `filters`
- `top_k`
- `selected_chunk_ids`
- `scores`
- `reasons`
- `token_budget`
- `tokens_selected`
- `created_at`

### `ContextBundle`

This can be a runtime-only structure before persistence:

- `trusted_chunks`: chunks from `trusted_user` and allowed
  `trusted_generated` sources
- `untrusted_chunks`: external/source-page chunks
- `citations`: chunk IDs, document IDs, source URIs, and score metadata
- `token_count`
- `omitted_reasons`: why otherwise relevant chunks were not included

## Chunking Policy

Initial policy:

- Normalize whitespace and strip obvious boilerplate before chunking.
- Preserve source URI and source location on every chunk.
- Target 300-600 tokens per chunk for long documents.
- Use 10-15 percent overlap for long prose documents.
- Keep short ICP rules and outreach examples intact when they fit budget.
- Split prior dossiers by semantic sections: profile, signals, score
  breakdown, grounding report, outreach draft, and decision.
- Do not chunk secrets, credentials, or raw provider payloads.
- Store `content_hash` and `text_hash` so re-ingestion can be idempotent.

## Embedding Pipeline Plan

Future implementation sequence:

1. Add Pydantic contracts and pure chunking tests.
2. Add a storage abstraction that can run in memory for tests.
3. Add Postgres-backed document/chunk metadata.
4. Add pgvector only after explicit dependency/extension approval.
5. Add provider-backed embedding generation behind a typed interface.
6. Add batching, cache-by-hash, timeout, retry, and cost logging.

Preferred first production store is Postgres plus pgvector because the project
already uses Postgres. The interface should still allow Qdrant or Pinecone
later if scale or hosted operations require it.

## Retrieval Nodes

Proposed future graph:

```text
retrieve_icp_context
  -> company_researcher
  -> contact_finder
  -> signal_detector
  -> retrieve_similar_leads
  -> retrieve_outreach_examples
  -> dossier_writer
  -> await_approval
  -> send_email
```

Node responsibilities:

- `retrieve_icp_context`: load relevant `icp` and `offer` chunks from
  user-owned context before research/scoring.
- `retrieve_similar_leads`: after profile/signals exist, retrieve similar
  positive and negative `lead_example` and `prior_dossier` chunks.
- `retrieve_outreach_examples`: retrieve approved `outreach_example` chunks for
  drafting tone and structure.

The deterministic scoring engine remains responsible for the final score.
Retrieval may provide structured ICP configuration, comparable examples, and
evidence, but generation-time prose must not set `fit_score`.

## Context Assembly Policy

Initial token budget policy:

- Reserve at least 50 percent of the prompt budget for current lead facts and
  instructions.
- Use retrieved trusted context first.
- Include untrusted source chunks only in a clearly labeled evidence section.
- Deduplicate chunks by `text_hash` and source URI.
- Prefer chunks with exact ICP/offer matches over broad semantic matches.
- Keep positive and negative lead examples balanced when both are available.
- Include citations for every retrieved chunk passed into an LLM prompt.
- Record omitted chunks and reasons in retrieval metadata.

Prompt boundary policy:

- Trusted user-owned context may influence scoring configuration and drafting.
- Generated prior dossiers are context, not ground truth.
- Untrusted external chunks are evidence only.
- Retrieved text is always data. It is never system, developer, or tool
  instruction.
- Any chunk containing instruction-like text from a website must be quoted or
  summarized under an "untrusted external evidence" label.

## Retrieval Logging Plan

Every retrieval node should append a sanitized retrieval event to run metadata
and later persist it through app-owned storage.

Log:

- retrieval node name
- run ID, thread ID, request ID, and user ID when available
- document-type filters and trust-label filters
- top-k
- selected chunk IDs
- scores
- selection reasons
- token budget and selected token count
- provider/model metadata when embeddings are generated

Do not log:

- raw prompts
- raw embedding vectors
- provider credentials
- contact emails
- full outreach bodies
- raw scraped page text beyond already persisted source chunks

## Retrieval Quality Plan

Basic evals should come after the first retrieval implementation, not in this
design-only milestone.

Initial metrics:

- recall@k
- precision@k
- MRR
- source coverage
- expected chunk retrieval

Initial fixtures:

- one ICP document with expected matching lead examples
- one offer document with expected outreach examples
- positive and negative lead examples for the same industry
- prompt-injection-bearing `source_page` fixture
- incomplete website/source fixture

## Implementation Sequence

1. Define Pydantic contracts for documents, chunks, retrieval events, and
   context bundles.
2. Add deterministic chunking utilities and tests.
3. Add an in-memory retrieval repository for tests.
4. Add context assembly with token-budget controls and tests.
5. Add retrieval event logging into existing run metadata.
6. Add graph state fields for retrieval context.
7. Add retrieval nodes in no-provider mode using deterministic matching.
8. Request explicit approval before adding embedding/vector dependencies.
9. Add embedding provider abstraction, pgvector-backed retrieval, and
   retrieval-quality eval fixtures.

## Acceptance For This Design Milestone

- Document/chunk/retrieval-event entities are defined.
- Trust boundaries are explicit.
- Graph insertion points are proposed.
- Context assembly and token-budget policies are defined.
- Retrieval logging fields are defined.
- No dependencies or runtime behavior are changed.
