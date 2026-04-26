# Phase 3 Step 4 — Chainlit v2 UI

## Goal
Provide a non-technical chat UI for the lead-research pipeline.  Users paste
a company URL, watch the dossier render, and approve or reject the drafted
email from the chat itself — no curl required.  Fulfills ADR-002.

## Status: COMPLETE

---

## Files changed

| File | Change |
|------|--------|
| `pyproject.toml` | Added `chainlit>=2.0,<3.0`; per-module mypy override for `saas_lead_agent.ui.chainlit_app` (Chainlit ships without stubs) |
| `src/saas_lead_agent/ui/__init__.py` | New (empty package marker) |
| `src/saas_lead_agent/ui/chainlit_app.py` | New: chat handlers + pure helpers (`validate_url`, `format_dossier`, `format_email_preview`, `format_send_result`) |
| `src/saas_lead_agent/api/main.py` | `create_app()` mounts Chainlit at `/chainlit` AFTER `include_router(router)`; gated by `DISABLE_CHAINLIT` env var |
| `tests/test_chainlit.py` | New: 16 tests covering helpers, import smoke, mount-order contract |
| `tests/conftest.py` | Sets `DISABLE_CHAINLIT=1` at module load so Chainlit is absent from the test FastAPI fixture |
| `CLAUDE.md` | Added Chainlit gotchas (mount order, `cl.Action.payload` v2 shape, `DISABLE_CHAINLIT` flag) |

---

## Architecture decisions

### Direct graph access, not HTTP round-trips
Approve/Reject buttons resume the graph by calling the same module-level
`_routes._graph` instance with `Command(resume=<bool>)`.  This is
semantically identical to hitting `POST /api/leads/{id}/approve` but skips
the loopback HTTP overhead and the hardcoded localhost URL problem.  The
HITL state lives in one place — the shared graph — regardless of whether
the user came in via REST or chat.

### Chainlit gated by env var (`DISABLE_CHAINLIT`)
Mounting Chainlit attaches socket.io routes, static asset handlers, and
service-worker endpoints to the FastAPI app at import time.  For the test
FastAPI fixture this is unnecessary cost and can interfere with route
discovery.  `tests/conftest.py` sets `DISABLE_CHAINLIT=1` at module load
(before any test imports `api.main`), and `create_app()` checks that flag
before calling `mount_chainlit`.

Production runs have the flag unset, so the UI is mounted as expected.

### Pure helpers extracted for unit testing
The Chainlit decorators (`@cl.on_message`, `@cl.action_callback`) cannot be
directly invoked in tests without spinning up Chainlit's full session
runtime.  Instead, the testable logic — URL validation, Markdown
formatting — lives in pure module-level functions (`validate_url`,
`format_dossier`, `format_email_preview`, `format_send_result`) that
unit tests call directly.  Decorator handlers stay thin orchestration
glue that's exercised manually in browser smoke testing.

### Chainlit v2 vs v1
Initial pin was `>=1.0,<2.0` but conflicted with `uvicorn[standard]>=0.34`
(Chainlit 1.x caps uvicorn at <0.26).  Bumped to `>=2.0,<3.0` — same API
shape for our use case, compatible with the rest of the stack.  Only
v2-specific change: `cl.Action(name=..., payload={...}, label=...)` —
v1's `value: str` field is replaced by `payload: dict`.

---

## Behavior matrix (`on_message` handler)

| URL input          | Result                                                    |
|--------------------|-----------------------------------------------------------|
| empty / whitespace | `❌ Please paste a company URL.`                          |
| bare hostname      | `❌ URL must start with http:// or https:// ...`           |
| `ftp://...`        | `❌ URL must start with http:// or https:// ...`           |
| valid http/https   | research → render dossier → AskActionMessage with email draft |

After AskActionMessage:

| User action     | Graph call                       | Final message              |
|-----------------|-----------------------------------|----------------------------|
| Approve         | `Command(resume=True)`            | `✅ Sent · message_id=...` |
| Reject          | `Command(resume=False)`           | `🚫 Rejected ...`          |
| Timeout (10 min)| `Command(resume=False)` (auto)    | `⏱️  Timed out — auto-rejected.` |

---

## Running locally

### 1. Start the app

```bash
uv run uvicorn src.saas_lead_agent.api.main:app --reload --port 8080
```

`DISABLE_CHAINLIT` is unset by default in production env, so Chainlit
mounts at `/chainlit`.

### 2. Open the UI

Browse to <http://localhost:8080/chainlit>.

### 3. Paste a URL

Try `https://stripe.com`.  You should see:

1. "Researching stripe.com" step indicator
2. Dossier card (company profile + contact + signals + fit score)
3. Email preview (subject + body) with **Approve** / **Reject** buttons
4. Final outcome line after you click

### 4. API still works

```bash
curl -X POST http://localhost:8080/api/qualify \
    -H 'Content-Type: application/json' \
    -d '{"url":"https://stripe.com"}'
```

The mount order (router first, Chainlit second) is verified by
`test_create_app_calls_mount_chainlit_after_router_when_enabled`.

---

## Verification checklist

- [x] `uv run ruff check` — clean
- [x] `uv run mypy src/` — clean (27 source files)
- [x] `uv run pytest -x --ff` — 164 passed, 5 skipped
- [ ] Manual smoke test: full chat flow in browser at `/chainlit`

---

## Risks & notes

- **Chainlit auto-creates `.chainlit/` config + translation files** on
  first import.  These are checked in / gitignored at the project's
  discretion; current state has them untracked.
- **traceloop deprecation warning.** Chainlit 2.x pulls in `traceloop-sdk`
  which uses Pydantic V1-style class-based config — emits a deprecation
  warning at test collection.  Not actionable on our side.
- **Action timeout = 600s.**  If the user walks away mid-review, the graph
  auto-rejects after 10 minutes so it doesn't hang forever.  Tunable.
- **Single-process state.**  The shared `_routes._graph` works because all
  requests (REST + Chainlit) hit the same Python process.  In a multi-worker
  prod deployment, HITL state must come from the Postgres checkpointer
  (Step 1) — already wired.

---

## ADR

ADR-009 to be logged in `decisions.md` after approval:

> Chainlit 2.x mounted at `/chainlit` AFTER all `/api/*` routes in
> `create_app()`.  Approve/Reject in the UI calls the shared module-level
> graph directly with `Command(resume=<bool>)` — same logic as the HTTP
> endpoints, without a localhost round-trip.  Tests skip the mount via
> `DISABLE_CHAINLIT=1`.
