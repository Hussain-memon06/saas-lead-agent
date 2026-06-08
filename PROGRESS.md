# Outbound Lead Agent Progress

## Current Status

Phase 1 is complete. The project is still a deployed prototype, but it now has
the first contract and safety layer needed before deeper production work.

The next planned phase is Phase 2: deterministic scoring.

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

## Current Worktree Note

The Phase 1 work is not committed yet. The current recommended next action is
to commit Phase 1 before starting Phase 2, so future changes have a clean base.

Suggested commit message:

```text
feat: complete phase 1 contracts and safety hardening
```

## Next Plan

### Step 1: Commit Phase 1

Commit the current Phase 1 changes once reviewed.

Before committing, optionally inspect:

```bash
git status --short
git diff --stat
```

### Step 2: Begin Phase 2 Narrowly

Start Phase 2 with deterministic scoring only. Do not begin persistence, RAG,
MCP, auth, evals, or production ops yet.

Recommended first Phase 2 milestone:

1. Define scoring contracts:
   - score breakdown
   - scoring result
   - confidence/uncertainty fields
   - human-readable reasons
2. Add a small pure-Python scoring engine.
3. Keep `dossier_writer` responsible for draft text only.
4. Ensure the LLM cannot directly set the final fit score.
5. Add focused tests for high, medium, low, and edge-case scoring.

Suggested initial files:

- `src/saas_lead_agent/engine/__init__.py`
- `src/saas_lead_agent/engine/scoring.py`
- `tests/test_scoring.py`

### Step 3: Integrate Scoring Carefully

After the scoring engine is tested in isolation:

1. Feed validated company profile, signals, contact, and ICP context into the
   scoring engine.
2. Have `dossier_writer` use the deterministic score result instead of trusting
   the model-provided score.
3. Preserve the existing API response shape unless a versioned contract change
   is explicitly planned.
4. Update frontend types only if the response gains new optional fields.

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
```

If `dossier_writer`, graph flow, or API response behavior changes, add the
relevant targeted tests:

```bash
uv run python -m pytest tests\test_agents.py -q
uv run python -m pytest tests\test_api.py -q
```

## Open Decisions

- Whether to commit Phase 1 immediately or inspect the diff first.
- Whether Phase 2 should expose score breakdown fields in the current flat API
  response or keep them internal until the frontend display is updated.
- Whether the first deterministic scoring rules should be minimal and
  conservative, or closer to the full future scoring model described in
  `PLANS.md`.
