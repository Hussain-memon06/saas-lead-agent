# Outbound Lead Agent Production Transformation Plan

## Purpose

This document is the execution plan for transforming SaaS Lead Agent
(Outbound Lead Agent) from a working portfolio/MVP prototype into a production-grade,
enterprise-ready agentic AI system.

It is intentionally a planning artifact only. It does not implement code,
change runtime behavior, or modify existing contracts. Future phases should be
executed sequentially, with each phase verified before the next begins.

## Current Technical Assessment

### What Exists Today

Outbound Lead Agent is a functional full-stack AI lead research application with:

- A Next.js 14 frontend in `frontend/`.
- A FastAPI backend in `src/saas_lead_agent/api/`.
- A LangGraph sequential pipeline assembled in `src/saas_lead_agent/graph.py`.
- Six graph nodes:
  - `company_researcher`
  - `contact_finder`
  - `signal_detector`
  - `dossier_writer`
  - `await_approval`
  - `send_email`
- Human-in-the-loop approval via LangGraph `interrupt()`.
- External integrations:
  - OpenAI via `langchain-openai`
  - Tavily search
  - Hunter.io domain search
  - `httpx` + BeautifulSoup scraper
  - SendGrid email delivery
  - Langfuse tracing
  - Postgres checkpointing through `AsyncPostgresSaver`
- A customer-facing frontend flow:
  - `/` for URL submission
  - `/settings` for ICP configuration
  - `/leads/[threadId]` for the dossier and approve/reject gate
- A Chainlit chat UI mounted at `/chainlit`.
- A Dockerfile, docker-compose setup, deployment runbook, and test suite.

### Current Architecture

```text
Browser / User
  |
  | Next.js UI
  v
FastAPI REST API
  |
  | /api/qualify, /api/leads/{thread_id}/approve, /reject
  v
LangGraph StateGraph
  |
  | company_researcher
  | contact_finder
  | signal_detector
  | dossier_writer
  | await_approval
  | send_email
  v
External Providers
  |
  | OpenAI, Tavily, Hunter.io, scraper, SendGrid
  v
Optional Platform Services
  |
  | Postgres checkpoints, Langfuse traces
```

### Current Data Flow

1. User submits a fully qualified company URL.
2. Frontend reads local ICP settings from browser `localStorage`.
3. Frontend posts `{ url, icp_context }` to `/api/qualify`.
4. Backend derives `domain` and `thread_id = lead:{domain}`.
5. LangGraph runs sequentially until `await_approval`.
6. `await_approval` interrupts before email delivery.
7. UI renders dossier and draft email from the returned state.
8. User approves or rejects.
9. Backend resumes the graph with `Command(resume=True|False)`.
10. `send_email` either rejects, skips for no contact, stubs, sends, or fails.

### Strengths

- Clear graph topology and state flow.
- Sequential architecture avoids known rate-limit pressure.
- Optional Postgres checkpointing supports durable interrupt/resume.
- Langfuse is wired at the API config boundary, keeping node code clean.
- Tool failures generally degrade into `errors` instead of crashing the graph.
- Tests cover graph topology, agent parsing, tools, SendGrid, Langfuse,
  persistence, Chainlit, and Docker artifacts.
- Frontend and backend live in one repo, making contract changes easier to
  coordinate.

### Production Gaps

- No authentication or authorization.
- No app-owned relational schema for users, leads, runs, sources, drafts,
  audit logs, or delivery events.
- No durable frontend dossier recovery after page refresh.
- No API versioning or response envelope.
- No deterministic scoring engine; `dossier_writer` asks the LLM to score.
- No robust structured output layer with Pydantic contracts per agent.
- No embedding pipeline for ICP documents, offer documents, prior dossiers,
  lead examples, source chunks, or outreach examples.
- No vector store or pgvector/Qdrant/Pinecone-style retrieval layer.
- No RAG layer for grounding lead scoring and outreach in user-owned context.
- No chunking, metadata, document-versioning, or retrieval logging strategy.
- No retrieval-quality evals such as recall@k, precision@k, MRR, or source
  coverage.
- No prompt/context budget management for retrieved chunks.
- No prompt-injection protection for untrusted website/source content.
- No model/provider abstraction for cost control and fallback.
- No prompt/version tracking for reproducibility.
- No explicit timeout budget per graph node or tool call.
- No idempotency key for qualification runs or email delivery.
- No background job or queue abstraction for long-running research.
- No MCP server/client/tool abstraction for standardizing external tool access.
- No durable execution abstraction beyond current LangGraph checkpointing.
- No retry policy, circuit breaker, queue, or long-running job abstraction.
- No rate limiting.
- SSRF risk in server-side scraper.
- CORS is currently broad.
- SendGrid stub mode can report `"sent"` in misconfigured environments.
- No CI/CD workflow in the repository.
- No first-class eval framework, golden dataset, or regression harness for
  agent quality.
- No dedicated eval harness for scoring, retrieval, grounding, structured
  output validity, tool-use behavior, or outreach quality.
- Documentation drift exists around Gemini vs OpenAI, Cloud Run/Railway, and
  Docker `$PORT` behavior.
- Stale dependency/config surface appears to remain from prior Gemini usage.

### Current Codebase Boundaries

Backend:

- `state.py`: graph state contract.
- `graph.py`: topology and graph factories.
- `api/main.py`: FastAPI app, lifespan, CORS, Chainlit mount.
- `api/routes.py`: REST lifecycle and graph invocation/resume.
- `agents/`: graph node implementations.
- `tools/`: LLM-callable external tools.
- `memory/`: Postgres checkpointing and Langfuse handler.
- `email/`: direct SendGrid integration.
- `ui/`: Chainlit UI.

Frontend:

- `app/`: routes and page shells.
- `components/`: UI components and workflow surfaces.
- `lib/api.ts`: typed fetch wrappers.
- `lib/icp.ts`: local ICP state.
- `lib/types.ts`: manual mirror of backend response types.
- `lib/query-client.tsx`: React Query provider.

Tests:

- Existing tests are flat under `tests/`.
- Persistence and Docker build tests are infrastructure-gated.
- There is no dedicated eval dataset or LLM quality harness.

## Dependency Graph Between Phases

```text
Phase 1: Architecture Hardening, Structured Contracts & Critical Safety
  |
  v
Phase 2: Deterministic Business Logic & Scoring Engine
  |
  v
Phase 3: Persistence Layer, Observability & Session Management
  |
  v
Phase 4: RAG, Embeddings, Vector Memory & Context Management
  |
  v
Phase 5: MCP, Tooling Abstraction & Durable Agent Execution
  |
  v
Phase 6: Authentication, Authorization & Compliance
  |
  v
Phase 7: Evaluation Framework, Testing & Quality Gates
  |
  v
Phase 8: Production Deployment, CI/CD & Operational Readiness
```

Rules:

- Do not skip phases.
- Do not combine phases into one large change.
- Each phase must preserve or intentionally version existing API behavior.
- Dependency changes require explicit user approval before editing
  `pyproject.toml`, `uv.lock`, or frontend package manifests.
- Each phase should update tests and documentation as part of the same unit of
  work.

## Phase 1: Architecture Hardening, Structured Contracts & Critical Safety

### Goal

Introduce strict data contracts and validation boundaries so future production
features have stable shapes to depend on, while closing the highest-risk safety
gaps that should not wait for a full auth/security phase.

### Scope

- Add a schema package for validated domain models.
- Convert agent outputs from prompt-only JSON parsing toward validated
  Pydantic objects.
- Harden input validation.
- Introduce response envelope planning or implementation while protecting
  frontend compatibility.
- Add request ID / correlation ID propagation.
- Add first-pass SSRF-safe URL validation before scraping.
- Fix SendGrid stub safety so a misconfigured environment cannot report a fake
  `"sent"`.
- Document prompt-injection boundaries: scraped website content is untrusted
  data, not instructions.
- Fix documentation drift.

### Deliverables

- `src/saas_lead_agent/schemas/` package with Pydantic v2 models.
- Contact, company profile, signal, evidence, outreach, lead report, metadata,
  and API envelope models.
- Updated agent parsing/validation path.
- URL validation with SSRF first-pass checks.
- ICP validation schema.
- Request ID generation and correlation in API responses/log context.
- SendGrid stub behavior that cannot be confused with real delivery in
  production-like environments.
- Documentation updates for actual OpenAI usage.
- Documentation cleanup for OpenAI/Gemini drift, Cloud Run/Railway deployment
  drift, and Docker `$PORT` behavior.
- Prompt-injection boundary notes for scraper/retrieval consumers.
- Removal plan for stale Gemini dependency, gated by explicit dependency
  approval.

### Acceptance Criteria

- All schema modules pass strict mypy.
- Agent nodes validate their outputs before writing state.
- Invalid URLs fail early with specific error messages.
- API contract changes are either backward-compatible or versioned.
- Frontend build passes after any response shape changes.
- Request IDs are visible in structured logs and response metadata.
- SendGrid disabled/misconfigured mode cannot report real delivery success.
- Scraped website content is documented and handled as untrusted input.
- No Gemini references remain in source-of-truth docs after the drift fix.
- Existing tests pass, and new schema/validation tests are added.

### Estimated Complexity

High. This touches backend contracts, agents, API responses, frontend types,
tests, and docs. The highest risk is breaking the frontend or the graph state
contract while introducing structured schemas.

### Suggested Verification

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
uv run pytest -x --ff
cd frontend && npm run build
```

## Phase 2: Deterministic Business Logic & Scoring Engine

### Goal

Separate AI extraction from business decisions. The LLM should extract and
summarize; deterministic Python should calculate the final fit score and
explain why.

### Scope

- Define typed ICP configuration.
- Implement deterministic scoring.
- Add evidence grounding checks.
- Add outreach quality checks.
- Refactor `dossier_writer` so the LLM drafts text but does not own the score.
- Make the scoring result inspectable, reproducible, and traceable to extracted
  company profile fields, signals, and evidence.
- Add score breakdown and confidence/uncertainty modeling.
- Start with a simple deterministic ruleset; keep score weights configurable
  later without requiring a new architecture.

### Deliverables

- `engine/icp.py` with `ICPConfig`.
- `engine/scoring.py` with `ScoringEngine`, score breakdowns, and scoring
  results.
- Confidence/uncertainty fields that explain weak, missing, or conflicting
  evidence.
- Evidence grounding engine that maps claims to sources.
- Outreach quality engine for placeholder detection, CTA checks, length checks,
  personalization density, and compliance constraints.
- Tests for each deterministic rule.
- Updated dossier output with inspectable score breakdown.

### Acceptance Criteria

- Same structured inputs produce the same score every run.
- Score explanations are traceable to extracted profile, signals, and evidence.
- LLM cannot directly set the final fit score.
- LLM output can influence scoring only through validated extracted facts,
  signals, and evidence.
- Unit tests cover high, medium, low, and edge-case scoring.
- Existing `/qualify` flow still returns a dossier and email draft.

### Estimated Complexity

High. This is a business-logic refactor and will likely require coordinated
changes to schemas, state, dossier composition, frontend display, and tests.

### Suggested Verification

```bash
uv run pytest -x tests/test_state.py tests/test_agents.py tests/test_graph.py
uv run pytest -x tests/
uv run ruff check src/ tests/
uv run mypy src/
cd frontend && npm run build
```

## Phase 3: Persistence Layer, Observability & Session Management

### Goal

Move beyond LangGraph checkpoints as the only durable state. Add app-owned
storage and better operational visibility.

### Scope

- Design and implement relational app data schema.
- Persist app-owned entities for users, leads, runs, sources, contacts, company
  signals, score breakdowns, outreach drafts, decisions, delivery events, and
  audit-style run events.
- Add repository/service boundaries.
- Add durable frontend recovery by `thread_id` or lead ID.
- Add run metadata, structured logging, token/cost tracking, and timing
  instrumentation per graph node/tool.

### Deliverables

- Database schema and migration strategy.
- Repository layer for app-owned entities.
- Lead/session retrieval endpoints.
- Frontend dossier recovery after refresh.
- Run metadata including tokens, cost, timings, tool status, provider status,
  and errors.
- Structured logs with request IDs, thread IDs, and run IDs.
- Langfuse trace correlation with persisted run records.
- Explicit no-secrets/no-PII logging policy.

### Acceptance Criteria

- User can refresh a dossier page and recover persisted state.
- Paused approvals survive process restart through Postgres checkpoints.
- App-owned lead/run records are persisted independently of checkpoints.
- No secrets or PII are logged accidentally.
- Langfuse traces correlate to persisted runs without leaking secrets.
- Persistence tests run against a test database.
- Existing in-memory test mode remains available.

### Estimated Complexity

Very high. This introduces real product data modeling, migrations, retrieval
APIs, and frontend lifecycle changes.

### Suggested Verification

```bash
uv run pytest -x tests/test_persistence.py
uv run pytest -x --ff
uv run ruff check src/ tests/
uv run mypy src/
cd frontend && npm run build
```

## Phase 4: RAG, Embeddings, Vector Memory & Context Management

### Goal

Add retrieval that grounds lead qualification and outreach in user-owned ICP
context, offer documents, prior lead examples, previous dossiers, and source
evidence.

### Scope

- Define document types: `icp`, `offer`, `lead_example`, `source_page`,
  `prior_dossier`, and `outreach_example`.
- Define chunking, metadata, document versioning, and retention strategy.
- Define embedding generation pipeline and provider boundary.
- Store embeddings with metadata. Prefer Postgres + pgvector first because the
  project already uses Postgres, while keeping a vector-store abstraction open
  for Qdrant/Pinecone later.
- Retrieve relevant ICP and offer context during lead qualification.
- Retrieve similar positive/negative leads and relevant outreach examples.
- Assemble retrieved context with prompt/token-budget controls.
- Log retrieval events, query inputs, selected chunks, scores, and reasons.
- Separate trusted user-owned context from untrusted scraped website content.
- Add prompt-injection handling for retrieved/scraped content.
- Keep deterministic scoring separate from retrieval and generation.

### Deliverables

- RAG design section in the architecture docs or this plan before
  implementation.
- Proposed document, chunk, embedding, and retrieval-event entities.
- Graph plan for retrieval nodes such as `retrieve_icp_context` and
  `retrieve_similar_leads`.
- Context assembly policy with source trust labels and token budgets.
- Retrieval logging plan tied to run metadata.
- Basic retrieval-quality tests/evals.

### Acceptance Criteria

- Agent can retrieve relevant ICP, offer, lead-example, and outreach-example
  context before scoring/drafting.
- Retrieved chunks are cited or traceable in run metadata.
- Retrieval is reproducible enough for debugging.
- Retrieved untrusted website text cannot override system/developer
  instructions.
- Scoring remains deterministic and does not depend on generation-time prose.
- Basic retrieval evals report recall@k and precision@k.

### Estimated Complexity

Very high. This adds a new retrieval subsystem, storage shape, eval surface,
prompt/context assembly policy, and safety boundary around trusted versus
untrusted text.

### Suggested Verification

```bash
uv run pytest -x tests/
uv run python evals/run_eval.py --dataset evals/retrieval_dataset.json
uv run ruff check src/ tests/
uv run mypy src/
cd frontend && npm run build
```

## Phase 5: MCP, Tooling Abstraction & Durable Agent Execution

### Goal

Standardize tool boundaries and long-running execution without adding MCP for
buzzword value. MCP should be used only where it makes external tool/resource
interfaces cleaner, testable, and reusable.

### Scope

- Create a typed tool abstraction layer for search, scraping, contact finding,
  email drafting/delivery, CRM/export, and future internal tools.
- Evaluate where MCP server/client boundaries make sense.
- Add MCP-readiness plan for external tools, resources, and prompts, or record
  an explicit “MCP-ready but not implemented yet” decision.
- Add durable execution design for long-running research.
- Add retry/backoff/timeout budgets per graph node and provider call.
- Add idempotency keys for qualification runs and delivery operations.
- Add queue/background-job planning where synchronous requests are too fragile.
- Add circuit breaker and fallback strategy for external providers.
- Add sandboxing policy for any future code execution or browser automation.

### Deliverables

- Tool interface design with typed inputs/outputs and error envelopes.
- MCP integration plan or explicit MCP-deferred decision.
- Durable job/run state model.
- Retry, timeout, and circuit breaker policy.
- Idempotency policy for qualification and email delivery.
- Provider fallback strategy.

### Acceptance Criteria

- Tool calls have consistent interfaces and typed outputs.
- Long-running work has a durable status model.
- Failed tools degrade gracefully and are visible in run metadata.
- Repeated requests do not accidentally duplicate email sends or expensive
  qualification runs.
- MCP plan is realistic and not forced where unnecessary.

### Estimated Complexity

High. This touches graph execution, tool contracts, provider failure behavior,
and future scaling architecture.

### Suggested Verification

```bash
uv run pytest -x tests/
uv run ruff check src/ tests/
uv run mypy src/
cd frontend && npm run build
```

## Phase 6: Authentication, Authorization & Compliance

### Goal

Make the application safe to expose beyond private demos.

### Scope

- Authentication.
- Authorization/RBAC.
- Rate limiting.
- User-owned lead access checks and multi-user data boundaries.
- SSRF hardening beyond Phase 1.
- CORS restrictions.
- Secrets validation.
- Audit logs.
- PII and trace redaction policy.

### Deliverables

- Auth model and session/token flow.
- Protected API routes.
- User-owned leads and access checks.
- Multi-user data ownership constraints for leads, runs, sources, retrieval
  context, and drafts.
- Admin/user role boundaries if needed.
- URL validator that blocks private IPs, link-local, localhost, dangerous
  ports, unsafe redirects, DNS rebinding, and dangerous address ranges.
- Request size limits and input sanitization.
- Rate limits on `/api/qualify`, auth endpoints, and approve/reject.
- Audit logging for security-sensitive actions.
- Production CORS allowlist.
- SendGrid stub disabled or fail-fast in production.
- Trace/log redaction for secrets, PII, and user-owned documents.

### Acceptance Criteria

- Anonymous users cannot run qualification in non-development environments.
- Users cannot access another user's leads.
- SSRF test cases are blocked before any server-side fetch.
- Rate limits return clear 429 responses.
- Production startup fails on missing critical secrets.
- Langfuse/logging redaction policy is documented and tested.
- Retrieval queries cannot cross user/tenant boundaries.

### Estimated Complexity

Very high. This phase changes request identity, data ownership, deployment
configuration, and security posture.

### Suggested Verification

```bash
uv run pytest -x tests/
uv run ruff check src/ tests/
uv run mypy src/
cd frontend && npm run build
```

## Phase 7: Evaluation Framework, Testing & Quality Gates

### Goal

Create a repeatable quality system for the agent outputs, deterministic logic,
retrieval behavior, tool use, safety boundaries, and production regressions.

### Scope

- Golden datasets.
- Adversarial datasets.
- Retrieval datasets.
- Eval runner.
- LLM-as-judge optional checks.
- Expanded unit/integration/e2e test structure.
- Frontend contract verification.
- Agent-specific eval categories:
  - Scoring: high/medium/low classification, score deviation, false positive
    rate, and false negative rate.
  - Retrieval: recall@k, precision@k, MRR, source coverage, and expected chunk
    retrieval.
  - Structured output: JSON validity, Pydantic validation pass rate, missing
    required fields, and invalid enum values.
  - Grounding/hallucination: unsupported claim rate, evidence coverage, and
    missing source rate.
  - Tool use: correct tool selection, graceful failure handling, timeout
    behavior, and retry behavior.
  - Outreach quality: personalization density, specificity, spamminess, CTA
    clarity, prohibited placeholder detection, and tone match.
  - Safety/adversarial: prompt injection in scraped pages, malicious URLs,
    irrelevant company pages, incomplete websites, no-contact cases, and
    SendGrid disabled/misconfigured cases.

### Deliverables

- `evals/golden_dataset.json` with at least 30 curated cases.
- `evals/adversarial_dataset.json`.
- `evals/retrieval_dataset.json`.
- `evals/run_eval.py` with scoring, schema, grounding, email quality, latency,
  token, and cost metrics.
- Eval result output under `evals/results/`.
- Unit tests for scoring, grounding, outreach quality, URL validation, ICP,
  schemas.
- Integration tests for API, auth, leads, database, graph execution.
- E2E tests gated behind environment flags.
- Cost-controlled LLM-as-judge checks only where deterministic metrics are not
  enough.

### Acceptance Criteria

- Eval pipeline runs locally and emits JSON results.
- Structured output validity target is 100%.
- Golden classification target starts at 80% minimum.
- Retrieval evals produce recall@k and precision@k.
- Unit and integration tests are deterministic and do not call external APIs.
- E2E tests are opt-in and cost-controlled.
- Frontend build remains a required quality gate.

### Estimated Complexity

High. The core challenge is creating stable datasets and meaningful quality
metrics without making the suite brittle or expensive.

### Suggested Verification

```bash
uv run pytest -x --ff
uv run python evals/run_eval.py --dataset evals/golden_dataset.json
cd frontend && npm run build
```

## Phase 8: Production Deployment, CI/CD & Operational Readiness

### Goal

Make the system deployable, observable, recoverable, and maintainable in a
real production environment.

### Scope

- Docker hardening.
- CI/CD.
- Health/readiness endpoints.
- Environment tiers.
- Monitoring and alerting runbooks.
- API versioning.
- Production documentation.

### Deliverables

- Hardened Dockerfile with correct `$PORT` handling and healthcheck.
- Local full-stack compose for API, DB, and frontend.
- GitHub Actions workflow for backend lint/type/tests, frontend build, and
  gated evals.
- Opt-in eval workflow for golden/adversarial/retrieval datasets.
- `/health` and `/ready` endpoints.
- Central environment configuration module.
- Development/staging/production config matrix.
- Runbooks for monitoring, incidents, deployment, rollback, cost spikes, and
  external API outages.
- API version prefix strategy, ideally `/api/v1/`.
- Monitoring for latency, 5xx responses, provider failures, tool failures,
  retrieval failures, token/cost spikes, and email delivery failures.
- Data retention, export, and deletion notes.
- Updated README and architecture docs.

### Acceptance Criteria

- CI runs on pull requests and blocks red merges.
- Docker compose can start the intended local stack.
- Health/readiness endpoints are accurate.
- Production environment fails fast on unsafe or missing configuration.
- Deployment and rollback instructions are reproducible.
- Monitoring plan includes alert thresholds for latency, 5xx, provider
  failures, tool failures, retrieval failures, costs, and delivery failures.
- Rollback, external provider outage, and cost spike runbooks are documented.

### Estimated Complexity

Medium to high. Most changes are operational, but API versioning and Docker
full-stack integration can touch broad parts of the system.

### Suggested Verification

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
uv run pytest -x --ff
cd frontend && npm run build
docker compose build
docker compose up -d
curl http://localhost:8080/health
curl http://localhost:8080/ready
docker compose down
```

## Cross-Phase Risk Register

| ID | Phase | Risk | Probability | Impact | Mitigation |
| --- | --- | --- | --- | --- | --- |
| R1 | 1 | Schema changes break frontend pages or TypeScript types | Medium | High | Add fields compatibly, update `frontend/lib/types.ts`, run frontend build |
| R2 | 1 | Structured output fails with current prompts | Medium | High | Add retries, schema-specific prompts, and fallback error paths |
| R3 | 1 | API response envelope breaks existing consumers | Medium | High | Version endpoints or preserve current response during transition |
| R4 | 1 | Removing stale Gemini dependency breaks hidden import path | Low | Medium | Search imports, run full test suite, require dependency approval |
| R5 | 2 | Deterministic score disagrees with expected sales intuition | High | Medium | Make weights configurable and inspectable; validate against examples |
| R6 | 2 | Evidence grounding drops too much useful context | Medium | Medium | Track confidence levels and require human review for weak evidence |
| R7 | 3 | Database schema grows before domain model stabilizes | Medium | High | Keep migrations small; design around run/source/draft primitives |
| R8 | 3 | Checkpoint state and app database drift apart | Medium | High | Store graph thread IDs on app runs; define reconciliation behavior |
| R9 | 3 | Persisted PII appears in logs or traces | Medium | High | Add redaction policy and tests before broad persistence |
| R10 | 4 | RAG retrieval returns irrelevant context | Medium | High | Add retrieval evals, metadata filters, traceable chunk logs, and reviewable examples |
| R11 | 4 | Vector metadata drift causes wrong lead/user context retrieval | Medium | Critical | Enforce user/run/document IDs in metadata and tests for tenant isolation |
| R12 | 4 | Embedding provider cost spikes | Medium | High | Track embedding cost, cache embeddings, batch jobs, and alert on anomalies |
| R13 | 4 | Prompt injection hidden inside scraped/retrieved content | Medium | Critical | Trust labels, instruction/data separation, adversarial evals, and prompt hardening |
| R14 | 5 | MCP integration adds complexity without value | Medium | Medium | Require explicit value decision and allow MCP-ready/deferred outcome |
| R15 | 5 | Durable jobs get stuck or duplicate work | Medium | High | Durable status model, idempotency keys, retries with caps, and stuck-run recovery |
| R16 | 5 | Idempotency failures cause duplicate email sends | Medium | Critical | Delivery idempotency keys, provider event tracking, and duplicate-send tests |
| R17 | 6 | SSRF bypass through redirects or DNS rebinding | Medium | Critical | Validate before fetch, after DNS resolution, and after redirects |
| R18 | 6 | Auth retrofit disrupts Chainlit and frontend flows | Medium | High | Define shared auth/session model before implementation |
| R19 | 6 | Overly broad CORS remains in production | Medium | High | Environment-specific CORS allowlist and startup validation |
| R20 | 6 | SendGrid stub reports fake success in production | Medium | High | Fail startup if production email config is incomplete |
| R21 | 7 | Golden dataset is too small or biased | High | Medium | Include diverse industries, sizes, regions, failures, adversarial cases |
| R22 | 7 | Eval suite becomes slow or costly | Medium | Medium | Split unit/eval/e2e gates; cache fixtures; gate real API runs |
| R23 | 7 | Eval metrics become gamed or too brittle | Medium | Medium | Keep human review samples, rotate cases, and track multiple metrics |
| R24 | 7 | LLM-as-judge gives inconsistent scores | Medium | Medium | Use deterministic rubrics, temperature 0, repeated runs, and thresholds |
| R25 | 8 | Docker image remains too large for good cold starts | Medium | Medium | Audit dependencies, multi-stage builds, measure cold starts |
| R26 | 8 | CI lacks secrets or accidentally logs them | Low | Critical | Use encrypted secrets; never echo secret values; review workflow logs |
| R27 | All | External providers fail or rate-limit requests | Medium | High | Add retry/backoff, provider status metrics, and graceful degradation |
| R28 | All | OpenAI cost spikes from repeated runs | Medium | High | Track token/cost per run, rate-limit, alert on cost anomalies |
| R29 | All | Long synchronous qualify requests time out | Medium | High | Add job/session model or streaming after persistence phase |
| R30 | All | Documentation drifts again after refactors | High | Medium | Update docs in the same PR as behavior changes |
| R31 | All | User data from one tenant leaks into another tenant’s retrieval context | Low | Critical | Tenant-scoped persistence, vector metadata filters, auth tests, and retrieval eval fixtures |

## Operating Model

### Branching

- Use feature branches per phase or milestone:
  - `feat/phase-1-contracts`
  - `feat/phase-2-scoring`
  - `feat/phase-3-persistence`
  - `feat/phase-4-rag`
  - `feat/phase-5-tools-durable-execution`
  - `feat/phase-6-auth-compliance`
  - `feat/phase-7-evals`
  - `feat/phase-8-ops`

### Change Discipline

- Keep each milestone small enough to review.
- Prefer schema additions before breaking renames.
- Avoid unrelated refactors during production hardening.
- Update tests and docs with the code they describe.
- Do not send real emails during development.
- Do not commit secrets or `.env` files.
- Do not modify dependencies without explicit approval.
- Each phase must end with tests passing, frontend build passing if touched,
  docs updated, and one manual happy-path verification.
- Any new AI behavior must include either deterministic tests or an eval case.
- Any new external provider/tool must have timeout, retry, logging, and failure
  behavior documented.
- Any new retrieval behavior must log what was retrieved and why.
- Any user-facing automation that can take external action must have human
  approval unless explicitly enabled later.
- Treat scraped web content as untrusted data.
- Do not add MCP, vector DB, queue, or auth dependencies without explicit user
  approval.

### Verification Baseline

Unless a phase explicitly narrows verification, use:

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
uv run pytest -x --ff
cd frontend && npm run build
```

Infrastructure-gated checks, such as real Postgres persistence tests, Docker
builds, SendGrid delivery, Langfuse trace verification, and cloud deployment,
should be run before release candidates and documented with their outputs.

## Immediate Next Step

After this plan is reviewed, begin Phase 1 with a narrow implementation plan
for structured contracts, critical URL/input safety, request IDs, SendGrid stub
correctness, and documentation drift cleanup. Do not implement deterministic
scoring, persistence, RAG, MCP, auth, or evals yet. Those come later in order.
