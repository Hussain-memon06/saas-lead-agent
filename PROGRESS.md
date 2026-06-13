# Outbound Lead Agent Progress

## Current Status

Phase 1 is complete and committed.

Phase 2 is complete and committed.
Deterministic scoring, typed ICP configuration, first-pass evidence grounding,
outreach quality checks, and threshold configuration are implemented: the final
fit score and review flags now come from Python business logic instead of
LLM-generated dossier text.

Phase 3 is in progress. The first four milestones are now implemented in the
working tree:

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

In progress:

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

### Next Phase 3 Milestone

After this slice is reviewed, continue Phase 3 with one of these narrow
milestones:

- deeper provider metadata capture for actual token/cost and node/tool timings,
  only if it can be done without new dependencies
- explicit no-secrets/no-PII logging tests or documentation hardening

Do not add RAG, MCP, auth, evals, production ops, queues, or new dependencies
until their later phases and explicit approval.

## Phase 3 Guardrails

- Keep app-owned persistence independent of LangGraph checkpoints.
- Preserve the current flat API response shape.
- Keep in-memory fallback available when `POSTGRES_URL` is unset.
- Do not log secrets or raw provider credentials.
- Do not introduce auth, queue, vector DB, MCP, or new provider dependencies.
- No new dependencies without explicit approval.
- No broad/full verification unless explicitly requested.

## Useful Targeted Verification For Phase 3

Run only the checks related to changed files:

```bash
uv run python -m ruff check <changed-python-files>
uv run python -m ruff format --check <changed-python-files>
uv run python -m pytest tests\test_lead_runs.py -q
uv run python -m pytest tests\test_api.py -q
```

Latest Phase 3 targeted verification:

- app-owned run/session recovery slice: `131 passed`
- normalized artifact persistence slice: `37 passed`
- combined targeted Phase 3 path after both slices: `133 passed`
- first-pass processing metadata slice: `154 passed`
- summary history and sanitized run-event endpoint slice: `61 passed`
- changed-file Ruff checks passed
- changed-file Ruff format checks passed

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
