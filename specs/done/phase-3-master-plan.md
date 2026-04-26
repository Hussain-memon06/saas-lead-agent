# Phase 3: Production Hardening

## Goal
Take the working Phase 2 pipeline to production: persistent state, real email
delivery, full observability, a human-facing UI, and a deployable container.

Input: company URL (via Chainlit or REST)
Output: approved outreach email actually delivered; every run traced in Langfuse;
state durable across restarts; one `docker compose up` for local dev.

---

## Dependency graph

```
AsyncPostgresSaver (Step 1)
    └── required by HITL across restarts (interrupt → process bounce → resume)
    └── required by Chainlit (UI needs durable thread_ids)

Real email delivery (Step 2)
    └── replaces send_email stub (ADR-006)
    └── depends on nothing except LeadState fields already present

Langfuse v3 (Step 3)
    └── add after Postgres — traces need durable thread_ids to correlate runs
    └── None-safe: missing keys → tracing disabled, graph unaffected

Chainlit v2 UI (Step 4)
    └── add after Postgres + email work (UI on a broken pipeline is expensive)
    └── mount LAST in FastAPI (CLAUDE.md hard constraint — routes 404 otherwise)

Deployment (Step 5)
    └── add after everything works locally
    └── Dockerfile → docker-compose → CI → prod target
```

Critical ordering constraints:
1. Postgres before Chainlit (UI references thread_ids that must survive restarts)
2. Postgres before Langfuse (trace correlation needs durable threads)
3. Email delivery independent of 1–3 (but do it early to validate ADR-006 fulfillment)
4. Chainlit before deployment (smoke-test in browser before containerizing)
5. Deployment last (everything green locally first)

---

## Sequenced steps

---

### Step 1 — AsyncPostgresSaver (Supabase Postgres)

**Goal:** Swap `InMemorySaver` for `AsyncPostgresSaver` backed by Supabase so
HITL state persists across server restarts (ADR-001 fulfillment).

**Files to change:**
- `pyproject.toml` — add `langgraph-checkpoint-postgres>=2.0,<3.0`
- `src/saas_lead_agent/memory/checkpointer.py` — new: async factory
- `src/saas_lead_agent/api/main.py` — lifespan context manager for DB lifecycle
- `src/saas_lead_agent/api/routes.py` — consume checkpointer from `app.state`
- `src/saas_lead_agent/graph.py` — `build_graph(checkpointer)` already injectable; verify
- `.env.example` — add `SUPABASE_DB_URL`
- `tests/conftest.py` — keep `InMemorySaver` for tests (never touch real DB)

**Actions:**
1. Verify `AsyncPostgresSaver` constructor, `setup()`, and async context manager
   shape via Context7 (`langgraph-checkpoint-postgres` package) before writing code.
2. Add `langgraph-checkpoint-postgres>=2.0,<3.0` to `pyproject.toml`; `uv sync`.
3. Implement `src/saas_lead_agent/memory/checkpointer.py`:
   ```python
   from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

   async def get_checkpointer() -> AsyncPostgresSaver:
       url = os.environ["SUPABASE_DB_URL"]
       checkpointer = AsyncPostgresSaver.from_conn_string(url)
       await checkpointer.setup()   # idempotent DDL
       return checkpointer
   ```
4. Add `lifespan` to `api/main.py`:
   - On startup: `app.state.checkpointer = await get_checkpointer()`
   - On shutdown: close async connection (confirm teardown API in Context7)
5. Update `routes.py`: replace module-level `_graph = build_graph_with_memory()`
   with a per-request `build_graph(request.app.state.checkpointer)` call — or
   cache the graph on `app.state` alongside the checkpointer.
6. `SUPABASE_DB_URL` required at runtime; absent → startup error with clear message.
   Tests stay on `InMemorySaver` — `conftest.py` already provides this fixture.

**Verification:**
```
uv run ruff check src/saas_lead_agent/memory/ src/saas_lead_agent/api/
uv run mypy src/saas_lead_agent/memory/ src/saas_lead_agent/api/
uv run pytest -x --ff   # all tests still pass with InMemorySaver
```
Manual: `SUPABASE_DB_URL=... uv run uvicorn ... --port 8080`
- `POST /api/qualify` → interrupt → kill server → restart → `POST /api/leads/{id}/approve`
  → confirm resume succeeds (thread survived restart).

**Risks:**
- `AsyncPostgresSaver` needs `asyncpg` (native extension). Confirm wheels exist
  for Python 3.11 on Windows and Linux; if not, use `psycopg[binary]` driver path.
- `await checkpointer.setup()` creates tables — must be idempotent (safe on restart).
- `app.state` vs request-scoped graph: if graph holds a reference to the
  checkpointer and the checkpointer's connection pool is closed on shutdown,
  a pending request will crash. Use `app.state.graph` (singleton) not per-request.

---

### Step 2 — Real email delivery (replaces send_email stub)

**Goal:** Replace the Phase 2 `send_email` stub with real outbound delivery via
SendGrid (primary) or SMTP (fallback). Capture `message_id` and `sent_at`.
(ADR-006 fulfillment)

**Files to change:**
- `pyproject.toml` — add `sendgrid>=6.0,<7.0` (or `aiosmtplib` for SMTP path)
- `src/saas_lead_agent/tools/mailer.py` — new: delivery wrapper as `@tool`
- `src/saas_lead_agent/agents/send_email.py` — rewrite: real delivery
- `src/saas_lead_agent/state.py` — add `message_id: str | None`, `sent_at: str | None`
- `src/saas_lead_agent/api/schemas.py` — expose `message_id`, `sent_at` in responses
- `.env.example` — add `SENDGRID_API_KEY`, `OUTBOUND_FROM_EMAIL`
- `tests/test_tools.py` — add mailer tests (mock HTTP)
- `tests/test_agents.py` — update send_email tests

**Actions:**
1. Decide provider: **SendGrid** preferred (REST API, delivery analytics,
   suppression lists). SMTP fallback for local dev/test.
   Log as ADR-007 before writing code.
2. Implement `tools/mailer.py`:
   ```python
   @tool
   async def send_outbound_email(
       to_email: str, subject: str, body: str
   ) -> dict[str, Any]:
       # POST https://api.sendgrid.com/v3/mail/send
       # Returns {"message_id": str, "sent_at": ISO-8601}
       # Raises RuntimeError on 4xx/5xx or missing SENDGRID_API_KEY
   ```
3. Rewrite `agents/send_email.py`:
   - If `state["email_approved"] is True`: call `send_outbound_email` with
     `contact["email"]`, `email_subject`, `email_body`.
   - Capture `message_id` and `sent_at` from tool result.
   - If `email_approved` is `False` or `None`: record `send_result = "rejected"`,
     skip delivery.
   - If delivery fails: record `send_result = "failed"`, append to `errors`.
     Do NOT raise — a send failure must not erase the dossier from state.
4. Add `message_id: str | None` and `sent_at: str | None` to `LeadState`.
5. Expose both fields in `QualifyResponse` and `ApproveResponse`.
6. Tests: happy send, rejected (no delivery), missing `to_email` (null contact),
   SendGrid 4xx, SendGrid 5xx, missing API key.

**Verification:**
```
uv run ruff check src/saas_lead_agent/tools/mailer.py src/saas_lead_agent/agents/send_email.py
uv run mypy src/saas_lead_agent/tools/mailer.py src/saas_lead_agent/agents/send_email.py
uv run pytest -x tests/test_tools.py tests/test_agents.py tests/test_api.py
```
Manual: full flow with real `SENDGRID_API_KEY` + a test inbox → confirm delivery.

**Risks:**
- `contact["email"]` may be `None` (Hunter returned no result). `send_email` node
  must check and skip delivery gracefully — write `send_result = "no_contact"`.
- SendGrid free tier: 100 emails/day limit. Fine for dev; prod will need a paid plan.
- Do NOT send real client PII through Gemini free tier (CLAUDE.md constraint).
  Check that `dossier_writer` only uses GPT-4o-mini (it does — ADR-004).

---

### Step 3 — Langfuse v3 observability

**Goal:** Add `CallbackHandler` from `langfuse.langchain` to all agent `ainvoke`
calls so every LLM interaction is traced, latency is visible, and cost is tracked.

**Files to change:**
- `pyproject.toml` — add `langfuse>=3.0,<4.0`
- `src/saas_lead_agent/observability.py` — new: lazy None-safe singleton
- `src/saas_lead_agent/agents/company_researcher.py` — pass callback
- `src/saas_lead_agent/agents/contact_finder.py` — pass callback
- `src/saas_lead_agent/agents/signal_detector.py` — pass callback
- `src/saas_lead_agent/agents/dossier_writer.py` — pass callback
- `src/saas_lead_agent/agents/orchestrator.py` — pass callback
- `.env.example` — add `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`

**Actions:**
1. Verify `langfuse.langchain.CallbackHandler` constructor and `ainvoke` config
   injection shape for LangChain 1.1 via Context7.
2. Add `langfuse>=3.0,<4.0` to `pyproject.toml`; `uv sync`.
3. Implement `observability.py`:
   ```python
   from langfuse.langchain import CallbackHandler

   _handler: CallbackHandler | None = None

   def get_langfuse_handler() -> CallbackHandler | None:
       global _handler
       if _handler is not None:
           return _handler
       key = os.environ.get("LANGFUSE_PUBLIC_KEY")
       if not key:
           return None
       _handler = CallbackHandler(
           public_key=key,
           secret_key=os.environ["LANGFUSE_SECRET_KEY"],
           host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
       )
       return _handler
   ```
4. In each agent's async node, pass handler via
   `config={"callbacks": [h] if (h := get_langfuse_handler()) else []}`.
5. No test changes needed — handler is `None` when keys absent. No mocking
   required; missing keys are the test-safe code path.
6. Log as ADR-008: "Langfuse handler is None-safe — missing keys disable tracing
   without breaking the graph."

**Verification:**
```
uv run ruff check src/saas_lead_agent/
uv run mypy src/saas_lead_agent/
uv run pytest -x --ff   # all existing tests still pass
```
Manual: set real Langfuse keys → `POST /api/qualify` → confirm trace appears
in Langfuse dashboard with correct agent names and token counts.

**Risks:**
- CLAUDE.md import path: `from langfuse.langchain import CallbackHandler`.
  This path changed between v2 and v3 — verify in Context7 before writing code.
- Langfuse v3 may require `flush()` on shutdown; add to `api/main.py` lifespan
  teardown if the docs say so.
- Handler must not throw if Langfuse is unreachable (network partition in prod).
  Wrap in try/except inside `get_langfuse_handler()` — degrade to `None`.

---

### Step 4 — Chainlit v2 UI

**Goal:** Mount Chainlit at `/chainlit` in FastAPI so non-technical users can
paste a URL, watch the dossier stream in, and approve/reject the email from chat.
(ADR-002 fulfillment)

**Files to change:**
- `pyproject.toml` — add `chainlit>=2.0,<3.0`
- `src/saas_lead_agent/cl_app.py` — new: Chainlit app
- `src/saas_lead_agent/api/main.py` — mount Chainlit LAST
- `tests/test_cl_smoke.py` — new: import-level smoke test

**Actions:**
1. Verify Chainlit v2 FastAPI mount API, `cl.Message`, `cl.AskActionMessage`, and
   streaming support via Context7 before writing any code.
2. Implement `cl_app.py`:
   - `@cl.on_message`: parse URL from message text; validate HTTP/HTTPS scheme.
   - `POST /api/qualify` (internal call via `httpx.AsyncClient`) → stream
     response fields back as `cl.Message` objects as they arrive:
     - Company profile summary
     - Contact found (or "no contact found")
     - Signals list
     - Fit score with emoji indicator
   - When interrupted: display email subject + body; use `cl.AskActionMessage`
     with `[Approve, Reject]` actions and a configurable timeout.
   - On approve: `POST /api/leads/{thread_id}/approve`
   - On reject: `POST /api/leads/{thread_id}/reject`
   - Show final `send_result` ("sent" / "rejected" / "failed") as closing message.
3. Mount in `api/main.py` — **AFTER** `app.include_router(router)`:
   ```python
   # Chainlit MUST be mounted last — mounting before the router causes 404 on /api/*
   from chainlit.utils import mount_chainlit
   mount_chainlit(app=app, target="src/saas_lead_agent/cl_app.py", path="/chainlit")
   ```
4. Add `tests/test_cl_smoke.py` — just `import saas_lead_agent.cl_app` without
   error (catches import-time syntax and missing dep issues).

**Verification:**
```
uv run ruff check src/saas_lead_agent/cl_app.py src/saas_lead_agent/api/main.py
uv run mypy src/saas_lead_agent/cl_app.py
uv run pytest -x --ff
```
Manual: `uv run uvicorn src.saas_lead_agent.api.main:app --port 8080` →
open `http://localhost:8080/chainlit` → paste a real URL → confirm full flow
including email approval in browser.

**Risks:**
- **CLAUDE.md hard constraint**: Chainlit must be mounted last. If mounted
  before `app.include_router(router)`, all `/api/*` routes return 404.
- Chainlit v2 FastAPI integration API differs from v1 — `mount_chainlit` may be
  a different import path. Context7 gate is mandatory.
- `cl.AskActionMessage` timeout: if the user doesn't click Approve/Reject, the
  graph stays interrupted indefinitely. Implement a 24-hour timeout on the
  Chainlit side; if timed out, call `/reject` automatically.
- Chainlit's internal websocket may conflict with FastAPI's own websocket handling
  if mounted at the root. Mount at `/chainlit` (non-root) as planned.

---

### Step 5 — Deployment

**Goal:** One `docker compose up` for local dev; one `docker push` for prod.
CI runs ruff + mypy + pytest on every PR. Production on Cloud Run (or Fly.io).

**Files to change:**
- `Dockerfile` — new: uv-based, Python 3.11, multi-stage
- `docker-compose.yml` — new: app + Postgres service for local dev
- `.github/workflows/ci.yml` — new: ruff + mypy + pytest on PR
- `.env.example` — finalize all required env vars
- `decisions.md` — ADR-009: deployment target choice

**Actions:**
1. **Dockerfile** (multi-stage):
   ```dockerfile
   # Stage 1: builder
   FROM python:3.11-slim AS builder
   RUN pip install uv
   WORKDIR /app
   COPY pyproject.toml uv.lock ./
   RUN uv sync --no-dev --frozen

   # Stage 2: runtime
   FROM python:3.11-slim
   WORKDIR /app
   COPY --from=builder /app/.venv ./.venv
   COPY src/ ./src/
   ENV PATH="/app/.venv/bin:$PATH"
   EXPOSE 8080
   CMD ["uvicorn", "src.saas_lead_agent.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
   ```
2. **docker-compose.yml**:
   ```yaml
   services:
     app:
       build: .
       ports: ["8080:8080"]
       env_file: .env
       depends_on: [postgres]
     postgres:
       image: postgres:16
       environment:
         POSTGRES_DB: saas_lead
         POSTGRES_USER: saas_lead
         POSTGRES_PASSWORD: secret
       ports: ["5432:5432"]
   ```
   `SUPABASE_DB_URL` in `.env` should point to `postgres://saas_lead:secret@postgres:5432/saas_lead`
   for local compose; prod points to real Supabase.
3. **CI** (`.github/workflows/ci.yml`):
   ```yaml
   on: [pull_request]
   jobs:
     test:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: astral-sh/setup-uv@v3
         - run: uv sync
         - run: uv run ruff check
         - run: uv run mypy src/
         - run: uv run pytest -x --ff
   ```
   No real API keys in CI — tests run on InMemorySaver with mocked agents.
4. **Deployment target**: Cloud Run (serverless, scales to zero, no infra
   management). Log as ADR-009.
   - `gcloud run deploy saas-lead-agent --image gcr.io/PROJECT/saas-lead-agent`
   - Secrets via Cloud Run secret manager (not `.env` in image).
5. **Secret management**: all secrets injected as environment variables at
   runtime. `.env` is gitignored and never shipped in the image.

**Verification:**
```
docker build -t saas-lead-agent .         # image builds without error
docker compose up                          # app starts, postgres healthy
curl -X POST http://localhost:8080/api/qualify -H 'Content-Type: application/json' \
  -d '{"url":"https://stripe.com"}'        # end-to-end smoke test
uv run pytest -x --ff                      # still green outside Docker
```
CI: open a PR → confirm workflow runs green.

**Risks:**
- `asyncpg` native extension may need a different base image on Cloud Run (ARM vs
  x86). Use `python:3.11-slim` (x86) or confirm `asyncpg` wheels on the target arch.
- Cold-start time on Cloud Run: `AsyncPostgresSaver.setup()` runs on every
  cold start. `setup()` is idempotent but adds latency; consider Cloud Run
  `min-instances=1` for prod if cold starts are unacceptable.
- uv's virtual environment path differs from pip installs — ensure `COPY --from=builder`
  copies `.venv` and `PATH` is set correctly in the runtime stage.
- GitHub Actions: `uv sync` needs a pinned `uv.lock` to be reproducible.

---

## ADRs needed

| # | Decision | When to log |
|---|----------|-------------|
| ADR-007 | SendGrid as primary email provider; SMTP as local dev fallback | Before Step 2 |
| ADR-008 | Langfuse handler is None-safe — missing keys disable tracing, not break graph | Before Step 3 |
| ADR-009 | Deployment target: Cloud Run (serverless, no infra, scales to zero) | Before Step 5 |

---

## Exit criteria for Phase 3

- `uv run pytest -x --ff` green (all 119+ tests, no new failures)
- `uv run ruff check` clean
- `uv run mypy src/` clean
- `docker compose up` starts app + Postgres locally; `/api/qualify` returns 200
- End-to-end smoke test: Stripe or Vercel URL → dossier → Chainlit UI shows
  results → approve → email delivered to test inbox → `send_result = "sent"`
- Thread survives restart: interrupt → kill server → restart → `/approve` resumes
- Langfuse: traces visible in dashboard for a real run with token counts
- CI: PR workflow runs green in under 3 minutes
- Production: `gcloud run deploy` succeeds; public URL accessible
