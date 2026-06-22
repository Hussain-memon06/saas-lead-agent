# Outbound Lead Agent Progress

## Current Status

Phase 1 is complete and committed.

Phase 2 is complete and committed.
Deterministic scoring, typed ICP configuration, first-pass evidence grounding,
outreach quality checks, and threshold configuration are implemented: the final
fit score and review flags now come from Python business logic instead of
LLM-generated dossier text.

Phase 3 is complete for the current roadmap milestone and committed in slices.

- app-owned run/session recovery with latest lead run snapshots, audit-style
  run events, `run_id` correlation, `GET /api/leads/{thread_id}`, and frontend
  dossier recovery after refresh
- normalized latest-run app artifacts for leads, sources, contacts, company
  signals, score breakdowns, outreach drafts, approval decisions, and delivery
  events
- first-pass processing metadata with run-level timings, zero-value token/cost
  placeholders, steps-completed inference, and structured log correlation
  context
- summary history and sanitized run-event endpoints with frontend API helpers:
  `GET /api/leads` and `GET /api/leads/{thread_id}/events`
- provider metadata capture with node-level timings/status, OpenAI token usage
  extraction when LangChain exposes usage metadata, and optional
  env-configured cost estimates

Phase 4 is complete for the no-dependency roadmap milestone and committed.
The graph now has retrieval insertion points and retrieved-context drafting,
but vector storage, embedding providers, persisted retrieval-event tables,
knowledge-base UI, and the full retrieval eval runner still require explicit
approval before implementation.

Phase 5 has started with a no-dependency tooling foundation.
Typed tool contracts and a durable-execution/MCP design note exist, but existing
runtime tools are partially wrapped. `web_search`, `scrape`, and
`hunt_contact` now have typed `ToolResult` adapters and sanitized tool-event
capture, but SendGrid, MCP server/client, queue, durable job runner,
retry/circuit-breaker runtime, and provider fallback abstraction are not
implemented yet.

## What We Completed

### Planning And Operating Model

- Rebranded the project from Dossify to Outbound Lead Agent across active
  source, docs, frontend text, and deployment-facing references.
- Updated `PLANS.md` from the earlier 6-phase roadmap to the current 8-phase
  roadmap:
  - Phase 1: Architecture Hardening, Structured Contracts & Critical Safety
  - Phase 2: Deterministic Business Logic & Scoring Engine
  - Phase 3: Persistence Layer, Observability & Session Management
  - Phase 4: RAG, Embeddings, Vector Memory & Context Management
  - Phase 5: MCP, Tooling Abstraction & Durable Agent Execution
  - Phase 6: Authentication, Authorization & Compliance
  - Phase 7: Evaluation Framework, Testing & Quality Gates
  - Phase 8: Production Deployment, CI/CD & Operational Readiness
- Updated the verification policy so full `pytest`, full `mypy`, frontend
  production builds, Docker builds, eval suites, and external API checks are
  release-only unless explicitly requested.
- Rewrote `AGENTS.md` so it aligns with `PLANS.md` and no longer contains stale
  6-phase or heavy-verification instructions.

### Phase 1: Contracts And Critical Safety

- Added `src/saas_lead_agent/schemas/` with Pydantic v2 contracts for:
  - API envelope planning
  - company profiles
  - contacts
  - ICP context
  - signals
  - evidence
  - lead reports
  - outreach/delivery results
  - processing metadata
  - URL validation
- Added first-pass Pydantic validation to agent outputs before writing graph
  state.
- Added ICP validation to `/api/qualify`.
- Added request ID propagation through FastAPI responses and LangGraph config
  metadata.
- Added first-pass SSRF-safe URL validation before scraper/API use:
  - rejects non-HTTP(S)
  - rejects credentials in URLs
  - rejects localhost/private/link-local/reserved IPs
  - rejects dangerous ports
  - normalizes scheme/host/trailing slash
- Fixed SendGrid stub behavior:
  - missing `SENDGRID_API_KEY` no longer reports fake `"sent"`
  - explicit `SENDGRID_STUB_ENABLED=true` returns `"stubbed"`
  - missing SendGrid config without stub mode fails closed
- Updated frontend contract types and approve/reject UI to understand
  `request_id` and `stubbed`.
- Documented the prompt-injection boundary: scraped pages/search snippets are
  untrusted data, not instructions.
- Updated active docs around OpenAI, SendGrid stub mode, deployment target, and
  environment variables.

## Verification Completed

Targeted Phase 1 verification passed:

```bash
uv run python -m ruff check <changed-python-files>
uv run python -m ruff format --check <changed-python-files>
uv run python -m pytest tests\test_schemas.py tests\test_api.py tests\test_tools.py tests\test_agents.py tests\test_chainlit.py -q
```

Result:

- `137 passed`
- changed-file Ruff checks passed
- `git diff --check` passed

## Not Run By Policy

These were intentionally not run because `PLANS.md` marks them as release-only
or explicitly requested checks:

- full `uv run pytest -x --ff`
- full `uv run mypy src/`
- frontend production build
- Docker build/compose
- eval suites
- real external API checks
- SendGrid real delivery
- Langfuse trace verification

## Commit History

- `0310420 feat: complete phase 1 contracts and safety hardening`
- `3be9fe3 feat: add deterministic lead scoring engine`
- `a6cedb8 feat: add deterministic grounding and outreach quality checks`
- `ebe13e6 feat: finalize deterministic scoring configuration`
- `8fa6b60 feat: add phase 3 lead persistence and run metadata`
- `8469b03 feat: add phase 3 lead history endpoints`
- `ef07b9c feat: complete phase 3 provider metadata`
- `8b0541b feat: add phase 4 retrieval contracts`
- `2557ca1 feat: add phase 4 retrieval context metadata`
- `8fc91c5 feat: complete phase 4 retrieval graph foundation`

## Phase 2 Progress

Completed so far:

- Added `src/saas_lead_agent/engine/` with a pure-Python deterministic scoring
  engine.
- Added scoring contracts for:
  - score breakdown
  - fit level
  - score confidence
  - human-review flag
  - reasons
  - uncertainty reasons
- Updated `dossier_writer` so:
  - the model drafts only `email_subject` and `email_body`
  - Python calculates the final `fit_score`
  - model-provided score fields are ignored
  - deterministic score metadata is returned with the dossier state
- Threaded optional score metadata through:
  - `LeadState`
  - FastAPI qualify response schema
  - REST route response construction
  - frontend TypeScript response types
  - HITL interrupt payload
- Added focused tests for deterministic scoring and scorer/dossier integration.
- Added `engine/grounding.py` for deterministic evidence grounding checks:
  - maps profile, signal, and contact facts to evidence items
  - flags missing profile/signal/contact sources
  - flags uncited URLs and unsupported signal claims in draft outreach
  - checks score components against available evidence
- Added `engine/outreach_quality.py` for deterministic outreach quality checks:
  - placeholder detection
  - CTA checks
  - length checks
  - personalization density
  - spam/high-pressure wording detection
- Updated `dossier_writer` so weak grounding or outreach quality issues trigger
  `needs_human_review` and return inspectable review reasons.
- Threaded optional grounding and outreach quality metadata through:
  - `LeadState`
  - FastAPI qualify response schema
  - REST route response construction
  - frontend TypeScript response types
  - HITL interrupt payload
  - Chainlit initial state
- Added focused tests for grounding, outreach quality, and contract threading.
- Added `engine/icp.py` with typed `ICPConfig`, score weights, and scoring
  thresholds.
- Updated `ScoringEngine` to accept either the existing `IcpContext` or the new
  `ICPConfig`, preserving current API behavior while making score weights and
  classification/review thresholds explicit.
- Added explicit outreach quality thresholds so CTA, length, personalization,
  and pass/fail settings can be tuned without changing scattered constants.
- Added focused tests for ICP config conversion, invalid threshold/weight
  bounds, scoring threshold tuning, and outreach quality threshold tuning.

Verification completed:

```bash
uv run python -m ruff check <phase-2-changed-python-files>
uv run python -m ruff format --check <phase-2-changed-python-files>
uv run python -m pytest tests\test_scoring.py tests\test_agents.py tests\test_state.py tests\test_api.py -q
```

Result:

- scoring milestone: `98 passed`
- grounding/outreach-quality milestone: `155 passed`
- ICP/threshold closure slice: `129 passed`
- changed-file Ruff checks passed
- changed-file Ruff format checks passed

Not run by policy:

- full pytest
- full mypy
- frontend production build
- Docker
- eval suites
- external API checks

## Phase 3 Progress

Complete for the current roadmap milestone:

- Added app-owned lead run snapshot and run event repository design with:
  - in-memory default for dev/tests
  - Postgres implementation using existing `POSTGRES_URL` and `asyncpg`
  - idempotent `app_lead_runs` and `app_run_events` table setup
- Added `run_id` to graph state, API responses, frontend types, and LangGraph
  config metadata for trace/run correlation.
- Added `GET /api/leads/{thread_id}` to recover the latest stored dossier
  snapshot.
- Updated qualify and approve/reject flows to save snapshots and record
  audit-style events.
- Updated the frontend lead page to fetch stored lead state after refresh
  instead of relying only on React Query memory.
- Added `persistence/lead_artifacts.py` to normalize the latest snapshot into
  app-owned records for:
  - leads
  - sources
  - contacts
  - company signals
  - score breakdowns
  - outreach drafts
  - decisions
  - delivery events
- Extended the in-memory and Postgres repositories so saving a snapshot also
  materializes those normalized artifact records.
- Added idempotent Postgres setup for normalized artifact tables:
  `app_users`, `app_leads`, `app_sources`, `app_contacts`,
  `app_company_signals`, `app_score_breakdowns`, `app_outreach_drafts`,
  `app_decisions`, and `app_delivery_events`.
- Added tests for artifact extraction, in-memory artifact persistence, and API
  route wiring.
- Extended `ProcessingMetadata` with:
  - `timings_ms`
  - `token_usage`
  - `cost_breakdown_usd`
  - `provider_status`
- Added `processing_metadata` to `LeadState`, qualify responses, approve/reject
  responses, frontend response types, and persisted run snapshots.
- Timed the REST graph invocation, interrupt-state check, and total API handler
  duration for qualify and approve/reject flows.
- Added safe structured log context for qualify/resume start, completion, and
  failure events using request IDs, thread IDs, and run IDs without logging
  contact emails, provider credentials, raw prompts, or raw scraped content.
- Added run-event metadata for timings, total token placeholder, and estimated
  cost placeholder.
- Added summary/history access for app-owned lead snapshots:
  - repository-level `list_snapshots`
  - `GET /api/leads?limit=...`
  - summary-only response models that exclude raw dossier body text
- Added sanitized run-event retrieval through
  `GET /api/leads/{thread_id}/events`, with metadata allowlisting so raw
  errors, prompts, provider payloads, and source text are not exposed.
- Added frontend API helpers and TypeScript contract mirrors for lead summaries
  and run events.
- Added sanitized provider metadata records from LLM-backed graph nodes:
  - `company_researcher`
  - `contact_finder`
  - `signal_detector`
  - `dossier_writer`
- Added a reducer-backed `provider_usage` state field so node metadata
  accumulates instead of overwriting.
- Aggregated provider metadata into `processing_metadata`:
  - `token_usage`
  - `total_tokens`
  - `provider_status`
  - `node.<node_name>` timings
  - optional `estimated_cost_usd` and `cost_breakdown_usd`
- Kept cost estimates opt-in through explicit env rates instead of hard-coded
  pricing:
  - `OPENAI_GPT_4O_MINI_INPUT_COST_PER_MILLION`
  - `OPENAI_GPT_4O_MINI_OUTPUT_COST_PER_MILLION`
- Added tests proving provider metadata aggregation does not expose raw
  prompts, completions, emails, raw scraped content, or provider payloads.

## Phase 4 Progress

Started with a design/context-management milestone:

- Added `specs/in-progress/phase-4-rag-design.md` covering:
  - proposed document, chunk, embedding, retrieval-event, and context-bundle
    entities
  - trusted user-owned context versus untrusted scraped/source text boundaries
  - retrieval node plan such as `retrieve_icp_context` and
  `retrieve_similar_leads`
  - context assembly and token-budget policy
  - retrieval logging plan
  - retrieval-quality metrics to add later
  - implementation sequence that starts with contracts/chunking before
    embedding or vector dependencies
- Added Phase 4 retrieval contracts in `src/saas_lead_agent/schemas/retrieval.py`:
  - `KnowledgeDocument`
  - `KnowledgeChunk`
  - `EmbeddingRecord`
  - `RetrievedChunk`
  - `RetrievalEvent`
  - `ContextBundle`
- Added dependency-free deterministic chunking utilities in
  `src/saas_lead_agent/retrieval/chunking.py`:
  - whitespace normalization
  - stable SHA-256 text hashes
  - simple word-based token estimates
  - stable chunk IDs
  - configurable overlap
- Added `tests/test_retrieval.py` for trust boundaries, vector dimension
  checks, event redaction boundaries, context trust splits, and chunking.
- Added `InMemoryRetrievalRepository` in
  `src/saas_lead_agent/retrieval/repository.py`:
  - active-document filtering
  - user-scoped filtering
  - document-type filtering
  - trust-label filtering
  - deterministic lexical scoring
  - stable score/chunk ordering
- Added context assembly in `src/saas_lead_agent/retrieval/context.py`:
  - trusted chunks are selected before untrusted external chunks
  - token budget is enforced
  - duplicate text is omitted by `text_hash`
  - citations include IDs/source metadata, not raw chunk text
- Added retrieval state and metadata support:
  - `LeadState` now has `retrieval_context` and reducer-backed
    `retrieval_events`
  - FastAPI and Chainlit initial states include empty retrieval state fields
  - `ProcessingMetadata` includes sanitized `retrieval_events`
  - qualify/resume run events include retrieval metadata without raw prompts,
    vectors, provider payloads, or chunk text
  - `GET /api/leads/{thread_id}/events` sanitizes nested retrieval-event
    metadata before returning it
  - `frontend/lib/types.ts` mirrors the processing metadata field
- Added `src/saas_lead_agent/retrieval/events.py` with
  `build_retrieval_event()` for deterministic, text-redacted retrieval event
  construction from assembled context bundles.
- Added no-provider retrieval graph nodes in
  `src/saas_lead_agent/agents/retrieval.py`:
  - `retrieve_icp_context` turns the submitted ICP payload into transient
    trusted ICP and offer documents, runs deterministic lexical matching,
    assembles a token-budgeted context bundle, and appends a sanitized
    retrieval event
  - `retrieve_similar_leads` establishes the post-signal graph insertion point
    and records a sanitized skipped event until a real lead-example/prior-dossier
    corpus exists
  - `retrieve_outreach_examples` establishes the pre-dossier drafting insertion
    point and records a sanitized skipped event until a real outreach-example
    corpus exists
- Updated the LangGraph topology to:
  `retrieve_icp_context -> company_researcher -> contact_finder ->
  signal_detector -> retrieve_similar_leads -> retrieve_outreach_examples ->
  dossier_writer -> await_approval -> send_email`
- Updated processing metadata step inference so retrieval nodes appear in
  `steps_completed` when retrieval events exist.
- Updated `dossier_writer` so retrieved context is included only in the human
  prompt as labeled drafting data, while system prompts explicitly say retrieved
  text must not be treated as instructions or used to create/change/explain the
  deterministic score.
- Added `src/saas_lead_agent/retrieval/quality.py` with dependency-free
  retrieval-quality metrics:
  - recall@k
  - precision@k
  - MRR
  - source coverage
  - expected chunk retrieval mapping

Do not add vector DB, embedding, queue, MCP implementation/dependencies, auth,
eval, production ops, or new provider dependencies without explicit approval.

### Next Phase 4 Milestone

Phase 4 is now at the approval boundary for heavier infrastructure. The next
meaningful milestones require explicit approval before adding one of:
Postgres-backed document/chunk storage, pgvector/vector storage, embedding
provider abstraction, retrieval datasets/eval runner, or frontend
knowledge-base upload/management UI.

## Phase 5 Progress

Started with a no-dependency tool-interface and durable-execution planning
milestone:

- Added `specs/in-progress/phase-5-tooling-durable-execution.md` covering:
  - current tool surface
  - non-goals for the first Phase 5 milestone
  - typed tool interface design
  - MCP-ready-but-deferred decision
  - durable run status model
  - retry, timeout, circuit-breaker, and fallback policy
  - qualification and delivery idempotency policy
  - sandboxing policy for any future browser automation or code execution
  - implementation sequence that starts with local contracts before MCP,
    queues, or provider/runtime changes
- Added `src/saas_lead_agent/tools/contracts.py` with strict Pydantic
  contracts for:
  - tool specs
  - timeout/retry policies
  - call context and idempotency metadata
  - sanitized execution metadata
  - sanitized tool errors
  - common tool result envelopes
- Added helper builders for completed and failed tool-result envelopes.
- Added `tests/test_tool_contracts.py` covering success/failure envelopes,
  extra-field rejection, result-shape validation, attempt-budget validation,
  and human-approval requirements for external-action tools.
- Exported the tool contracts from `src/saas_lead_agent/tools/__init__.py`.
- Added `src/saas_lead_agent/tools/recording.py` for scoped, sanitized
  tool-result capture during graph node execution.
- Adapted `src/saas_lead_agent/tools/web_search.py` so Tavily calls produce a
  typed `ToolResult` internally while preserving the existing LangChain tool
  return shape and error behavior.
- Adapted `src/saas_lead_agent/tools/scraper.py` so HTTP scrape calls produce a
  typed `ToolResult` internally while preserving the existing LangChain tool
  string output and error behavior.
- Adapted `src/saas_lead_agent/tools/hunter.py` so Hunter.io contact-finding
  calls produce a typed `ToolResult` internally while preserving the existing
  LangChain tool dict output and error behavior.
- Added `tool_usage` to `LeadState` and capture scopes in:
  - `company_researcher`
  - `contact_finder`
  - `signal_detector`
- Added processing metadata fields for:
  - sanitized `tool_events`
  - aggregate `tool_status`
  - `tool.<node>.<tool>` timing entries
- Added API/run-event sanitization so raw provider payloads, tool outputs, and
  raw error messages are not exposed through run events.
- Added `src/saas_lead_agent/email/idempotency.py` with deterministic
  delivery-idempotency key helpers for future SendGrid retry protection without
  logging raw recipient/body data.
- Wired `delivery_idempotency_key` into approved delivery attempts so stubbed,
  failed, and sent SendGrid paths carry the key through API responses,
  sanitized run-event metadata, and app-owned delivery event records.
- Added typed SendGrid delivery envelopes for approved send attempts and a
  local tool-spec registry for `web_search`, `scrape`, `hunt_contact`, and
  `sendgrid_delivery`.

The graph and API remain backward-compatible for existing consumers; the
additional metadata is additive.

### Phase 5 Closure

Phase 5's no-dependency milestone set is complete. The project now has typed
tool contracts, typed wrappers for the current tool surface, sanitized
tool-event metadata, delivery idempotency-key recording, and a local tool
registry. MCP runtime, queues, durable job infrastructure, new provider
dependencies, provider fallback runtime, and external-action retries remain
deferred until explicitly approved.

### Next Phase Milestone

Started Phase 6 with a narrow planning milestone in
`specs/in-progress/phase-6-auth-compliance-plan.md`. Do not add auth
dependencies, session storage, production CORS changes, rate limiting, or
deeper SSRF enforcement without a small approved Phase 6 implementation scope.

### Next Phase 6 Milestone

Started the first Phase 6 implementation slice with no-dependency auth context
and protected-route policy contracts in `src/saas_lead_agent/schemas/auth.py`.
Current unauthenticated runtime behavior is unchanged.

Added Milestone 6.2 user-owned access model contracts for lead runs, sources,
contacts, company signals, score breakdowns, outreach drafts, decisions,
delivery events, and retrieval context. Existing unauthenticated records remain
modeled as legacy anonymous-demo resources until auth enforcement is approved.

Next: choose either an auth provider/session decision record or Milestone 6.3's
critical compliance configuration contracts. Do not enforce auth, add
dependencies, or alter CORS without a narrow approved scope.

Added Milestone 6.3 compliance configuration contracts for environment CORS
intent, request-size limits, startup critical-secret expectations, trace/log
redaction fields, and audit event categories. Runtime CORS, request-limit,
startup-secret, redaction, and audit-log enforcement remain deferred.

Next: choose either an auth provider/session decision record or Milestone 6.4's
SSRF hardening design contracts. Do not enforce auth, add dependencies, alter
CORS, or change scraper behavior without a narrow approved scope.

Added Milestone 6.4 SSRF hardening contracts for redirect revalidation, DNS
rebinding checks, post-resolution validation, private/link-local ranges,
localhost aliases, and dangerous ports. Scraper behavior is unchanged.

Next: document the auth provider/session decision or request approval for one
narrow Phase 6 runtime enforcement slice.

Added `specs/in-progress/phase-6-auth-provider-session-decision.md`. Provider
choice remains deferred; the approved next runtime shape is dependency-free
auth context resolution with anonymous-demo behavior preserved.

Added dependency-free request auth context plumbing in
`src/saas_lead_agent/api/auth.py`. It records sanitized auth mode/user-presence
metadata while preserving anonymous-demo behavior and avoiding route
enforcement.

Next: request approval for the next narrow runtime slice, likely attaching
`user_id` to new run snapshots and app-owned records without read enforcement.

Added ownership propagation for new authenticated qualification runs: resolved
`user_id` is persisted in run snapshots and normalized lead records while
remaining absent from public API responses. Read enforcement and child artifact
ownership remain deferred.

Next: add repository-level owner filtering contracts or propagate ownership to
child artifacts, without enforcing routes yet.

Added pure owner-aware persistence helpers in
`src/saas_lead_agent/persistence/access.py` for snapshot owner extraction,
read decisions, and list filtering. API routes and repository methods do not
enforce these helpers yet.

Next: either propagate ownership to normalized child artifacts or request
approval to wire owner filtering into one read endpoint.

Extended the pure persistence access layer to normalized `LeadArtifacts`
aggregates using `lead.user_id`. Snapshot and artifact aggregate filtering are
now centralized, but repository methods and routes still do not enforce them.

Next: request approval to enforce ownership on one read endpoint, or undertake
the larger child-artifact ownership/schema migration separately.

Enforced owner-aware listing on `GET /api/leads`. Filtering now occurs inside
both repository implementations before pagination. Authenticated users see
their snapshots; anonymous-demo requests see legacy unowned snapshots. Admin
contexts retain the all-records path.

Next: enforce ownership on `GET /api/leads/{thread_id}` as a separate slice.
Events and approve/reject must remain unchanged until their own milestones.

Implemented Clerk authentication for the existing route surface:

- `ClerkProvider` wraps the Next.js app.
- Clerk middleware protects `/`, `/settings`, and `/leads/*`.
- Existing qualification, dossier, approve, and reject calls send Clerk JWTs.
- FastAPI verifies Clerk JWT signature/issuer/expiry/subject plus optional
  audience and authorized-party constraints.
- Plain identity headers are disabled unless explicit non-production bypass is
  enabled.
- Lead list/detail/events/approve/reject enforce snapshot ownership.
- Production requires Clerk issuer and CORS configuration; Chainlit is not
  mounted in production.

Phase 6 is complete for the current roadmap milestone:

- Request bodies are capped at 128 KB and ICP JSON at 32 KB.
- Qualification is limited to 10 requests per authenticated user per minute;
  approve/reject share a 30-per-minute decision limit.
- Production startup requires Clerk configuration, an explicit CORS allowlist,
  and `OPENAI_API_KEY`.
- Scraper redirects are followed manually for at most three hops. Every target
  is normalized, resolved, checked for non-public addresses, and connected by
  validated IP while preserving the original HTTP Host and TLS SNI.
- Security metadata remains allowlisted and excludes raw identity, credentials,
  contact email, outreach bodies, and scraped/retrieved text.
- Focused tests were added for JWT behavior, ownership, request limits, rate
  limiting, production startup validation, redirect revalidation, private DNS,
  and pinned TLS/Host behavior.

Operational notes: rate limiting is currently per backend process, and legacy
unowned demo records are isolated rather than backfilled. Distributed limiting
and migration operations belong to Phase 8 if deployment topology requires
them.

### Next Phase Milestone

Begin Phase 7 with a narrow evaluation-contract and dataset-design milestone.
Do not start broad eval runs or external LLM-as-judge calls without explicit
approval.

## Phase 7 Progress

Milestone 7.1 establishes the provider-free evaluation foundation:

- Added `specs/in-progress/phase-7-evaluation-design.md` with dataset,
  reproducibility, privacy, metric-ownership, execution, and milestone policy.
- Added strict evaluation contracts for datasets, cases, expectations, metric
  results, case results, and run summaries.
- External-provider execution defaults to false.
- Duplicate case IDs, empty expectations, retrieval expectations without `k`,
  incomplete metric threshold pairs, and inconsistent run totals are rejected.
- Added focused contract tests without introducing an eval runner, datasets,
  provider calls, or dependencies.

Next: add small reviewed seed files for golden, adversarial, and retrieval
datasets plus deterministic schema loading. Do not run models or external APIs.

Milestone 7.2 adds the first provider-free dataset slice:

- Added four synthetic golden cases, four adversarial cases, and two retrieval
  cases under `evals/`.
- Added strict UTF-8 JSON loading with a 2 MB limit, expected-kind checks, and
  sanitized parse/schema failures.
- Added focused tests for all seed files, provider-free defaults, kind
  mismatches, malformed JSON, and schema-invalid data.
- Added an ignore boundary for generated `evals/results/` artifacts.

Next: implement deterministic scoring and structured-output evaluators against
the seed cases. Do not add a broad runner or provider-backed evaluation yet.

Milestone 7.3 adds the first executable deterministic evaluators:

- Scoring fixtures validate existing company/contact/signal/ICP contracts and
  run through the production `ScoringEngine`.
- Per-case scoring metrics cover classification accuracy, score deviation, and
  human-review safety behavior.
- Structured-output evaluation covers JSON validity, required fields, selected
  existing Pydantic schemas, and invalid enum counts.
- Invalid fixture data returns sanitized failed case results instead of
  escaping into a future runner.
- Added focused tests against the synthetic seed data and malformed cases.

Next: add the retrieval evaluator adapter using existing Phase 4 metrics. Keep
aggregate runner behavior and provider-backed evaluation deferred.

Milestone 7.4 adds deterministic retrieval evaluation:

- Retrieval seed cases now contain synthetic ranked `RetrievedChunk` records
  and explicit minimum recall, precision, MRR, and source-coverage thresholds.
- The adapter reuses Phase 4's `evaluate_retrieval_quality` implementation.
- Per-case output includes recall@k, precision@k, MRR, source coverage, and
  expected chunk retrieval.
- Malformed chunks return sanitized failed case results.
- Added focused passing, threshold-failure, and invalid-fixture tests.

Next: add deterministic grounding and outreach-quality evaluator adapters.
Keep tool execution, safety execution, aggregate runners, and provider-backed
evaluation deferred.

Milestone 7.5 adds deterministic grounding and outreach evaluation:

- Added a fully sourced synthetic grounding case and an engine-compatible
  outreach case.
- Grounding metrics cover unsupported-claim rate, evidence coverage, and
  missing-source rate using existing scoring/grounding engines.
- Outreach metrics cover quality score, personalization density, spam
  incidence, CTA clarity, placeholder safety, and approval gating using the
  existing outreach-quality engine.
- Invalid fixtures return sanitized failed case results.
- Added focused passing and failure tests for both adapters.

Next: add provider-free tool-event and adversarial safety evaluators over
already-recorded fixture data. Do not execute tools, fetch URLs, or send email.

Milestone 7.6 adds offline tool-use and adversarial safety evaluation:

- Tool-use cases now contain sanitized `ToolExecutionMetadata` observations.
- Metrics cover tool selection, expected status/graceful handling, timeout
  behavior, retry budgets, and approval gating without invoking tools.
- Safety cases exercise the pure URL validator or verify that untrusted prompt
  injection text has a recorded `treated_as_data` boundary outcome.
- Added focused passing, mismatch, and invalid-metadata tests.
- These checks do not replace later opt-in live adversarial tests.

Next: add aggregate scoring metrics and a local provider-free runner that emits
sanitized JSON results. Do not add external-provider or LLM-as-judge execution.

Milestone 7.7 adds aggregate metrics and the local provider-free runner:

- Aggregate scoring reports classification accuracy, average score deviation,
  false-positive rate, and false-negative rate with explicit quality gates.
- A category dispatcher routes every current case type to its deterministic
  evaluator.
- Provider-required cases are refused rather than executed implicitly.
- `evals/run_eval.py` supports dataset/category selection and writes the
  sanitized versioned run-result contract only when explicitly invoked.
- Exit status reflects both per-case failures and aggregate quality gates.
- Added focused dispatch, filtering, provider-refusal, and aggregation tests.

Next: expand the golden dataset toward 30 reviewed cases and add coverage
reporting. Keep live end-to-end and LLM-as-judge evaluation opt-in and deferred.

Milestone 7.8 adds deterministic dataset coverage reporting:

- Reports category and tag counts, provider-free/provider-required counts, and
  missing categories appropriate to each dataset kind.
- Reports the golden target and remaining gap without running evaluators.
- Current coverage is ten golden cases with a 20-case gap; all three datasets
  contain their required category surfaces and remain provider-free.
- Added focused coverage and target-override tests.

Next: expand the golden dataset in small reviewed slices, beginning with more
high/medium/low scoring and structured-output edge cases. Do not bulk-generate
cases merely to satisfy the count.

Milestone 7.9 adds five reviewed golden cases:

- Medium-fit scoring with missing evidence and mandatory review.
- Generic-mode scoring with the established deterministic score of nine.
- Red-flag scoring that must remain human-review gated.
- Minimal serialized `QualifyResponse` validation.
- Explicit stubbed-delivery `LeadReport` validation.

Golden coverage is now 10 cases with a 20-case gap. Next: add a small reviewed
grounding/outreach edge-case slice, including unsupported claims, missing
sources, placeholders, spam language, and missing CTA behavior.

Milestone 7.10 adds five reviewed negative-example cases:

- Grounding detects an uncited external URL.
- Grounding detects profile-backed scoring without profile source evidence.
- Outreach detects unresolved placeholders.
- Outreach detects high-pressure spam language.
- Outreach detects a short body with no CTA.

The expectation model now supports bounded degraded outcomes, CTA presence,
and placeholder presence so correctly detected bad output passes the eval.
Golden coverage is now 15 cases with a 15-case gap. Next: add another reviewed
slice covering scoring uncertainty, structured-output failures represented as
expected outcomes, and additional grounding source variation.

## Phase 5 Guardrails

- MCP is deferred unless a concrete tool/resource boundary benefits from it.
- Keep existing graph/API behavior backward-compatible while tool wrappers are
  introduced.
- Tool metadata must be sanitized: no API keys, raw provider payloads, full
  prompts, full scraped text, full outreach bodies, or contact emails.
- External-action tools, especially email delivery, must require human approval
  unless a later approved phase explicitly changes that policy.
- Do not add retries that can duplicate email delivery or expensive provider
  work before idempotency is checked against durable delivery records.
- No MCP, queue, durable-job, browser-automation, or provider dependencies
  without explicit approval.

## Phase 4 Guardrails

- Keep deterministic scoring separate from retrieval and generation.
- Treat scraped/source-page text as untrusted external evidence.
- Keep user-owned ICP/offer/example context separate from untrusted website
  content.
- Do not log raw prompts, vectors, provider payloads, credentials, contact
  emails, full outreach bodies, or raw scraped text in retrieval events.
- Do not introduce auth, queue, vector DB, MCP implementation/dependencies,
  eval runner, or new provider dependencies.
- No new dependencies without explicit approval.
- No broad/full verification unless explicitly requested.

## Useful Targeted Verification For Phase 4

Run only the checks related to changed files:

```bash
uv run python -m ruff check <changed-python-files>
uv run python -m ruff format --check <changed-python-files>
uv run python -m pytest tests\test_retrieval.py tests\test_state.py tests\test_schemas.py tests\test_api.py -q
uv run python -m pytest tests\test_retrieval_nodes.py tests\test_graph.py -q
uv run python -m pytest tests\test_agents.py tests\test_retrieval_quality.py -q
```

## Useful Targeted Verification For Phase 5

Run only the checks related to changed files:

```bash
uv run python -m ruff check <changed-python-files>
uv run python -m ruff format --check <changed-python-files>
uv run python -m pytest tests\test_tool_contracts.py -q
uv run python -m pytest tests\test_tools.py -q
uv run python -m pytest tests\test_email_idempotency.py -q
uv run python -m pytest tests\test_sendgrid.py -q
uv run python -m pytest tests\test_agents.py tests\test_lead_runs.py -q
uv run python -m pytest tests\test_agents.py tests\test_api.py tests\test_state.py tests\test_schemas.py -q
```

## Useful Targeted Verification For Phase 6

Run only checks related to the Phase 6 boundary being reviewed:

```bash
uv run python -m ruff check <changed-python-files>
uv run python -m ruff format --check <changed-python-files>
uv run python -m pytest tests\test_auth_context.py -q
uv run python -m pytest tests\test_access_policy.py -q
uv run python -m pytest tests\test_auth_policy.py -q
uv run python -m pytest tests\test_api_auth.py tests\test_api.py -q
uv run python -m pytest tests\test_compliance_policy.py -q
uv run python -m pytest tests\test_ssrf_policy.py -q
uv run python -m pytest tests\test_api_security.py tests\test_tools.py -q
```

Latest Phase 3 targeted verification:

- app-owned run/session recovery slice: `131 passed`
- normalized artifact persistence slice: `37 passed`
- combined targeted Phase 3 path after both slices: `133 passed`
- first-pass processing metadata slice: `154 passed`
- summary history and sanitized run-event endpoint slice: `61 passed`
- provider metadata closure slice: `116 passed, 5 skipped`
- changed-file Ruff checks passed
- changed-file Ruff format checks passed

Latest Phase 4 targeted verification:

- design/context-management spec: docs-only; `git diff --check` is sufficient
- retrieval contracts/chunking slice: `8 passed`
- in-memory retrieval/context assembly slice: `12 passed`
- retrieval state/metadata slice: `150 passed, 5 skipped`
- no-provider retrieval graph-node slice: `67 passed`
- retrieval context consumption and quality metrics slice: `127 passed`
- outreach-example insertion and transient offer context slice: `128 passed`

Latest Phase 5 targeted verification:

- tool contract slice: `8 passed`
- web-search tool-event metadata slice: `167 passed`
- changed-file Ruff checks passed
- changed-file Ruff format checks passed
- `git diff --check` passed

If frontend recovery behavior changes, explain that frontend production build
was not run unless explicitly requested under the release-only verification
policy.

## Open Decisions

- Whether to display score breakdown/confidence in the frontend now or wait
  until the UI has a designed section for it.
- Whether grounding/outreach quality reports should be rendered in the current
  lead page immediately or kept API-visible until a focused UI milestone.
- Whether normalized artifacts beyond summary snapshots should get query/list
  API endpoints during Phase 3 or remain internal until auth and user-owned
  access checks exist.
- Whether SendGrid should get a typed delivery envelope before the first
  durable run-status model.
