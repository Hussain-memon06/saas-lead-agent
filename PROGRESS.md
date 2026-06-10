# Outbound Lead Agent Progress

## Current Status

Phase 1 is complete and committed.

Phase 2 is complete pending commit of the final closure milestone.
Deterministic scoring, typed ICP configuration, first-pass evidence grounding,
outreach quality checks, and threshold configuration are implemented: the final
fit score and review flags now come from Python business logic instead of
LLM-generated dossier text.

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

## Next Plan

### Step 1: Review And Commit Phase 2 Closure Milestone

Suggested commit message:

```text
feat: finalize deterministic scoring configuration
```

### Step 2: Begin Phase 3 Planning

Phase 3 should start with a narrow implementation plan for persistence,
observability, and session recovery. Do not add RAG, MCP, auth, evals, or
production ops until their later phases.

## Phase 2 Guardrails

- The LLM may extract facts, signals, and draft outreach.
- Python business logic calculates the final fit score.
- The score must be reproducible for identical inputs.
- Every score component should have an inspectable reason.
- Missing or weak evidence should lower confidence or trigger human review.
- No new dependencies without explicit approval.
- No broad/full verification unless explicitly requested.

## Useful Targeted Verification For Phase 2

Run only the checks related to changed files:

```bash
uv run python -m ruff check <changed-python-files>
uv run python -m ruff format --check <changed-python-files>
uv run python -m pytest tests\test_scoring.py -q
uv run python -m pytest tests\test_icp_config.py -q
uv run python -m pytest tests\test_grounding.py -q
uv run python -m pytest tests\test_outreach_quality.py -q
```

If `dossier_writer`, graph flow, or API response behavior changes, add the
relevant targeted tests:

```bash
uv run python -m pytest tests\test_agents.py -q
uv run python -m pytest tests\test_api.py -q
uv run python -m pytest tests\test_state.py tests\test_schemas.py -q
```

## Open Decisions

- Whether to display score breakdown/confidence in the frontend now or wait
  until the UI has a designed section for it.
- Whether grounding/outreach quality reports should be rendered in the current
  lead page immediately or kept API-visible until a focused UI milestone.
- Which app-owned persistence schema should be created first in Phase 3:
  minimal run/session recovery or the broader users/leads/runs/sources model.
