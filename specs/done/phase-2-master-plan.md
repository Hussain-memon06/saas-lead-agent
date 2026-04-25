# Phase 2: Full Pipeline

## Goal
Complete the system from skeleton to a working end-to-end AI SDR:
input a company URL → orchestrator fans out to company_researcher +
contact_finder (real Hunter.io) + signal_detector (real web_search) →
dossier_writer scores and drafts email → HITL interrupt before send →
all persisted in Supabase Postgres, observable via Langfuse, served via
Chainlit UI.

## Dependency graph

```
tools/hunter.py
    └── contact_finder (real)

signal_detector (real)        ← web_search already exists

LeadState: fit_score, email_draft
    └── dossier_writer
            └── HITL (interrupt/resume)

AsyncPostgresSaver            ← swap after HITL works
Langfuse                      ← add after graph is stable
Chainlit                      ← add last (CLAUDE.md: mount last)
```

Critical ordering constraints:
1. `hunter.py` before real `contact_finder`
2. `LeadState` fields before `dossier_writer`
3. `dossier_writer` before HITL (needs the email draft to interrupt on)
4. Graph stable + all agents real before adding `AsyncPostgresSaver`
5. Postgres working before Langfuse (tracing needs durable threads)
6. Everything working before Chainlit (UI on a broken graph is expensive)

## Sequenced steps

---

### Step 1 — tools/hunter.py

**Goal:** Implement a `@tool` that calls the Hunter.io Domain Search API and
returns the top decision-maker contact for a given domain.

**Files to change:**
- `src/saas_lead_agent/tools/hunter.py` — new
- `tests/test_tools.py` — extend with Hunter tests
- `pyproject.toml` — no new dep; Hunter.io is plain httpx (REST, no SDK)
- `.env.example` — add `HUNTER_API_KEY`

**Actions:**
1. Verify Hunter.io Domain Search API shape (endpoint, params, response schema)
   via Context7 or direct docs read — do not guess.
2. Implement `hunt_contact(domain: str) -> dict[str, Any]` as a `@tool`:
   - `GET https://api.hunter.io/v2/domain-search?domain={domain}&api_key={key}&limit=5`
   - Filter results to seniority `senior`/`executive` and department
     `executive`/`it`/`engineering` if available; take the top hit.
   - Return dict: `{name, first_name, last_name, title, email, linkedin, confidence, source}`.
   - Raise `RuntimeError` on missing key, 4xx, or network error.
3. Add 5 tests (mock httpx): happy path, no results, key missing, HTTP 4xx,
   network error.

**Verification:**
```
uv run ruff check src/saas_lead_agent/tools/hunter.py
uv run mypy src/saas_lead_agent/tools/hunter.py
uv run pytest -x tests/test_tools.py
```

**Risks:**
- Hunter free tier returns limited fields; confirm `linkedin` is present or mark nullable.
- Response shape: `data.emails[]` not `results[]` — must read docs, not guess.

---

### Step 2 — Real contact_finder agent

**Goal:** Replace the Phase 1 stub with a `create_agent` node that calls
`hunt_contact`, then uses Gemini to enrich/normalise the result.

**Files to change:**
- `src/saas_lead_agent/agents/contact_finder.py` — rewrite
- `tests/test_agents.py` — extend with contact_finder tests (mock agent)

**Actions:**
1. Rewrite `contact_finder.py` following the `company_researcher` pattern:
   - `build_contact_finder_agent()` → `create_agent(model, tools=[hunt_contact], system_prompt=..., name="contact_finder")`
   - System prompt: "Given a domain, call hunt_contact, then return a single JSON
     object with fields: name, title, email, linkedin, confidence. Use null for
     unknowns. Return ONLY the JSON."
   - `contact_finder(state)` async node: reads `state["domain"]`, invokes agent,
     parses last AIMessage JSON, writes `{"contact": {...}}`. Errors → `{"errors": [...]}`.
2. Add `_extract_json` reuse: factor the shared JSON-extraction logic (currently
   duplicated in `company_researcher.py` and `orchestrator.py`) into
   `saas_lead_agent/utils.py`. This is the right moment — three files need it.
3. Add 6 tests: happy path, null fields, JSON parse error, agent exception,
   empty messages, domain passed in prompt.

**Verification:**
```
uv run ruff check src/saas_lead_agent/agents/contact_finder.py src/saas_lead_agent/utils.py
uv run mypy src/saas_lead_agent/agents/contact_finder.py src/saas_lead_agent/utils.py
uv run pytest -x tests/test_agents.py
```

**Risks:**
- If Hunter returns zero results for a domain, the agent must handle gracefully
  (return nulls, not error).

---

### Step 3 — Real signal_detector agent

**Goal:** Replace the Phase 1 stub with a `create_agent` node that uses
`web_search` to detect buying signals (funding, hiring, tech-stack changes).

**Files to change:**
- `src/saas_lead_agent/agents/signal_detector.py` — rewrite
- `tests/test_agents.py` — extend

**Actions:**
1. Rewrite `signal_detector.py` following the `company_researcher` pattern:
   - `build_signal_detector_agent()` → `create_agent(model, tools=[web_search], ...)`
   - System prompt: "Search for recent buying signals for {company_name} /
     {domain}: funding rounds, executive hires, product launches, tech-stack
     changes, job postings. Return a JSON array of signal objects, each with
     fields: type (funding|hiring|product|techstack|other), title, summary,
     url, date. Return ONLY the JSON array."
   - Node reads `state["domain"]` and `state["company_profile"]` (name for
     better search queries). Writes `{"signals": [...]}`.
2. `_extract_json` in `utils.py` needs a list variant — extend it to handle
   both dict and list top-level JSON, or add `_extract_json_list`.
3. Add 5 tests: happy path (array returned), empty array, JSON parse error,
   agent exception, empty messages.

**Verification:**
```
uv run ruff check src/saas_lead_agent/agents/signal_detector.py
uv run mypy src/saas_lead_agent/agents/signal_detector.py
uv run pytest -x tests/test_agents.py
```

**Risks:**
- Signal detector runs after company_researcher in the parallel fan-out —
  `company_profile` may be `None` if researcher failed. Node must handle
  `None` gracefully (fall back to domain-only search).

---

### Step 4 — LeadState fields + dossier_writer agent

**Goal:** Add `fit_score` and `email_draft` to LeadState, then implement
`dossier_writer` as a GPT-4o-mini node that scores fit (0–100) and writes
the outreach email.

**Files to change:**
- `src/saas_lead_agent/state.py` — add `fit_score: int | None`, `email_draft: str | None`
- `src/saas_lead_agent/agents/dossier_writer.py` — new
- `src/saas_lead_agent/graph.py` — add `dossier_writer` node after fan-in
- `src/saas_lead_agent/api/schemas.py` — add fields to `QualifyResponse`
- `tests/test_state.py` — update for new fields
- `tests/test_agents.py` — add dossier_writer tests
- `tests/test_graph.py` — update topology tests

**Actions:**
1. Add `fit_score: int | None` and `email_draft: str | None` to `LeadState`
   (no reducer needed — these are scalar overwrites).
2. Implement `dossier_writer.py`:
   - Uses `ChatOpenAI(model="gpt-4o-mini")` (per CLAUDE.md: GPT-4o-mini for
     email writer only).
   - No tools — pure generation. Use `create_agent` or a direct
     `model.ainvoke([SystemMessage(...), HumanMessage(...)])` call.
   - System prompt provides company_profile + contact + signals; asks for JSON:
     `{fit_score: 0-100, fit_rationale: str, email_subject: str, email_body: str}`.
   - Node reads all three upstream fields from state; writes
     `{"fit_score": int, "email_draft": str}`. Errors → `{"errors": [...]}`.
3. Wire `dossier_writer` into `graph.py`:
   - Current: `[researcher, contact, signal] → END`
   - New: `[researcher, contact, signal] → dossier_writer → END`
   - `dossier_writer` runs after the fan-in — it needs all three results.
4. Add `fit_score` and `email_draft` to `QualifyResponse`.
5. Add 6 tests for dossier_writer: happy path, missing upstream fields (nulls),
   JSON parse error, exception.

**Verification:**
```
uv run ruff check src/saas_lead_agent/agents/dossier_writer.py src/saas_lead_agent/state.py src/saas_lead_agent/graph.py
uv run mypy src/saas_lead_agent/agents/dossier_writer.py src/saas_lead_agent/state.py src/saas_lead_agent/graph.py
uv run pytest -x tests/test_state.py tests/test_agents.py tests/test_graph.py
```

**Risks:**
- Graph topology change (`dossier_writer` inserted between fan-in and END) will
  break existing `test_graph.py` topology assertions — update them as part of
  this step.
- GPT-4o-mini JSON output may include markdown fences — `_extract_json` in
  `utils.py` already handles this.

---

### Step 5 — Human-in-the-loop (interrupt / resume)

**Goal:** Add an `interrupt()` before the email is sent, so a human can approve
or edit the draft. The graph pauses at `await_approval`, resumes with
`Command(resume={"approved": True/False, "edited_draft": str | None})`.

**Files to change:**
- `src/saas_lead_agent/agents/dossier_writer.py` — split into `score_and_draft`
  and `send_email` nodes, with interrupt between them
- `src/saas_lead_agent/graph.py` — add `await_approval` interrupt node
- `src/saas_lead_agent/state.py` — add `email_approved: bool | None`,
  `send_result: str | None`
- `src/saas_lead_agent/api/routes.py` — add `POST /api/qualify/{thread_id}/approve`
  endpoint that resumes the graph with `Command`
- `src/saas_lead_agent/api/schemas.py` — add `ApproveRequest`, `ApproveResponse`
- `tests/test_graph.py` — add interrupt/resume test
- `tests/test_api.py` — add approve endpoint test

**Actions:**
1. Verify LangGraph 1.1 `interrupt()` and `Command(resume=...)` API via Context7
   before writing any code.
2. Split `dossier_writer` into two nodes:
   - `score_and_draft` (existing logic — runs after fan-in)
   - `send_email` (stub for now — just marks `send_result = "sent"`)
3. Add `interrupt_before=["send_email"]` to `graph.compile(...)` call.
   Per CLAUDE.md: use `durability="sync"` around the interrupt.
4. Add `POST /api/qualify/{thread_id}/approve` that calls
   `graph.ainvoke(Command(resume=payload), config={"configurable":{"thread_id":...}})`.
5. Tests: interrupt fires, resume with approved=True proceeds to send_email,
   resume with approved=False short-circuits.

**Verification:**
```
uv run ruff check src/saas_lead_agent/
uv run mypy src/saas_lead_agent/
uv run pytest -x tests/test_graph.py tests/test_api.py
```

**Risks:**
- CLAUDE.md says `durability="sync"` around interrupts — this is a LangGraph
  constraint, must verify exact usage in Context7.
- `interrupt()` in LangGraph 1.1 may work differently than 0.x — Context7 gate
  is mandatory before this step.
- The `send_email` node is a stub in Phase 2; actual SMTP/API send is Phase 3+.

---

### Step 6 — AsyncPostgresSaver (Supabase)

**Goal:** Swap `InMemorySaver` for `AsyncPostgresSaver` so graph state persists
across restarts. Required for HITL to survive a server bounce between interrupt
and resume.

**Files to change:**
- `pyproject.toml` — add `langgraph-checkpoint-postgres`
- `src/saas_lead_agent/memory/checkpointer.py` — implement async factory
- `src/saas_lead_agent/api/routes.py` — use `get_checkpointer()` instead of
  `build_graph_with_memory()`
- `src/saas_lead_agent/api/main.py` — lifespan context manager for DB conn
- `.env.example` — add `SUPABASE_DB_URL`
- `tests/conftest.py` — keep `InMemorySaver` for tests (do not hit real DB)

**Actions:**
1. Verify `AsyncPostgresSaver` API via Context7 (`langgraph-checkpoint-postgres`
   package, not `langgraph` core) before writing code.
2. Add `langgraph-checkpoint-postgres>=2.0,<3.0` to `pyproject.toml`.
3. Implement `checkpointer.py`:
   - `async def get_checkpointer()` — reads `SUPABASE_DB_URL` from env,
     returns `AsyncPostgresSaver` (async context manager).
4. Wire into FastAPI via `lifespan`:
   - On startup: create checkpointer, run `await checkpointer.setup()` (creates
     tables), store on `app.state`.
   - On shutdown: close connection.
5. `routes.py` reads `request.app.state.checkpointer` instead of singleton graph.
6. Tests stay on `InMemorySaver` — no DB in CI.

**Verification:**
```
uv run ruff check src/saas_lead_agent/memory/ src/saas_lead_agent/api/
uv run mypy src/saas_lead_agent/memory/ src/saas_lead_agent/api/
uv run pytest -x --ff   # tests stay in-memory
```
Manual: `SUPABASE_DB_URL=... uv run uvicorn ... --port 8080` + curl confirms
tables created and thread persists across restart.

**Risks:**
- `AsyncPostgresSaver` requires `asyncpg` driver and a running Postgres.
  Tests must not depend on it — conftest must keep `InMemorySaver` isolation.
- `await checkpointer.setup()` DDL: must be idempotent (safe to re-run on
  restart).

---

### Step 7 — Langfuse v3 observability

**Goal:** Add `CallbackHandler` from `langfuse.langchain` to all agent `ainvoke`
calls so every LLM call is traced in Langfuse.

**Files to change:**
- `pyproject.toml` — add `langfuse>=3.0,<4.0`
- `src/saas_lead_agent/agents/company_researcher.py` — pass callback
- `src/saas_lead_agent/agents/contact_finder.py` — pass callback
- `src/saas_lead_agent/agents/signal_detector.py` — pass callback
- `src/saas_lead_agent/agents/dossier_writer.py` — pass callback
- `src/saas_lead_agent/agents/orchestrator.py` — pass callback
- `.env.example` — add `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`

**Actions:**
1. Verify `langfuse.langchain.CallbackHandler` constructor signature and how to
   pass it into LangChain `ainvoke` config via Context7.
2. Add `langfuse>=3.0,<4.0` to `pyproject.toml`, `uv sync`.
3. Implement `src/saas_lead_agent/observability.py` — lazy singleton:
   ```python
   def get_langfuse_handler() -> CallbackHandler | None:
       # returns None if LANGFUSE_PUBLIC_KEY not set (test/dev mode)
   ```
4. In each agent's async node function, pass handler via `config={"callbacks": [handler]}`
   when `handler is not None`.
5. No test changes needed — handler is `None` when keys absent (conftest
   doesn't set Langfuse keys).

**Verification:**
```
uv run ruff check src/saas_lead_agent/
uv run mypy src/saas_lead_agent/
uv run pytest -x --ff   # all existing tests still pass
```
Manual: set real Langfuse keys + run curl → confirm trace appears in dashboard.

**Risks:**
- CLAUDE.md import path: `from langfuse.langchain import CallbackHandler` — must
  confirm this is still correct for v3 (the path changed between v2 and v3).
- Langfuse keys absent in CI → handler must be `None`-safe. Do not let missing
  keys break the graph.

---

### Step 8 — Chainlit v2 UI

**Goal:** Mount Chainlit at `/chainlit` in FastAPI. Users paste a URL, see the
dossier streamed back, and can approve/edit the email draft in the chat.

**Files to change:**
- `pyproject.toml` — add `chainlit>=2.0,<3.0`
- `src/saas_lead_agent/cl_app.py` — Chainlit app: on_message → qualify →
  stream results → show email draft → await human approval → resume
- `src/saas_lead_agent/api/main.py` — mount Chainlit LAST (per CLAUDE.md)

**Actions:**
1. Verify Chainlit v2 FastAPI mount API and `cl.Message` / `cl.AskActionMessage`
   shape via Context7 before writing code.
2. Implement `cl_app.py`:
   - `@cl.on_message`: extract URL from message, call graph with streaming,
     surface company_profile + contact + signals as formatted messages.
   - When `fit_score` available, display score + rationale.
   - Use `cl.AskActionMessage` to present email draft and await approve/reject.
   - On approve: call resume endpoint or invoke graph directly with
     `Command(resume={"approved": True})`.
3. Mount: `app.mount("/chainlit", create_cl_app())` — AFTER `app.include_router(router)`.
4. Tests: Chainlit integration is UI-only — no unit tests; add a
   `tests/test_cl_smoke.py` that imports `cl_app` without error.

**Verification:**
```
uv run ruff check src/saas_lead_agent/cl_app.py src/saas_lead_agent/api/main.py
uv run mypy src/saas_lead_agent/cl_app.py
uv run pytest -x --ff
```
Manual: `uv run uvicorn src.saas_lead_agent.api.main:app --port 8080` →
open `http://localhost:8080/chainlit` in browser, paste a URL, confirm flow.

**Risks:**
- CLAUDE.md: "Mount Chainlit last in FastAPI or routes 404." If mounted before
  the API router, `/api/qualify` returns 404 — enforced by mount order.
- Chainlit v2 FastAPI integration API has changed from v1; Context7 gate mandatory.
- Chainlit `AskActionMessage` timeout: if user doesn't respond, graph stays
  interrupted indefinitely. Need a timeout or a `/api/qualify/{id}/cancel` endpoint.

---

## ADRs needed

| # | Decision | When to log |
|---|----------|-------------|
| ADR-004 | GPT-4o-mini for dossier_writer only; all other agents use Gemini 2.5 Flash-Lite | Before Step 4 |
| ADR-005 | `_extract_json` factored into `utils.py` shared module | Before Step 2 |
| ADR-006 | `send_email` is a stub in Phase 2; actual delivery (SES/SendGrid) is Phase 3 | Before Step 5 |
| ADR-007 | Langfuse handler is `None`-safe — missing keys disable tracing, not break the graph | Before Step 7 |
| ADR-008 | Chainlit mounts last; this is a hard constraint from CLAUDE.md, not discretionary | Before Step 8 |

---

## Risks & unknowns (cross-cutting)

1. **`create_agent` vs direct LLM call for dossier_writer.** `dossier_writer`
   has no tools — it's a pure generation step. Using `create_agent` adds an
   unnecessary ReAct loop. A direct `model.ainvoke([...])` call may be cleaner.
   Decide in Step 4.

2. **Orchestrator prompt update.** After Step 4, the orchestrator's system prompt
   references three tools; after Step 4 a fourth node (`dossier_writer`) exists
   but is not a tool (it runs after fan-in). The orchestrator prompt does not
   need to change — `dossier_writer` is wired as a graph edge, not a tool call.

3. **`state.get("domain")` in contact_finder stub.** Current Phase 1 stub calls
   `state.get("domain")` which is not a TypedDict method (TypedDict uses `[]`
   not `.get()`). This works at runtime (TypedDict is a dict subclass) but mypy
   strict flags it. Step 2 rewrite will fix this.

4. **Hunter.io availability.** If `HUNTER_API_KEY` is absent, `contact_finder`
   must degrade gracefully (return null contact, not hard error). Design the
   node to return `{"contact": null_contact}` not `{"errors": [...]}` when the
   key is missing, since missing contact is not a pipeline-fatal error.

5. **Graph topology across steps.** Steps 1–3 don't change the graph.
   Step 4 changes the graph (adds dossier_writer node). Step 5 changes it again
   (interrupt). Steps 6–8 don't change graph topology. Keep topology tests
   up-to-date at Steps 4 and 5.

6. **asyncpg on Windows.** `AsyncPostgresSaver` uses `asyncpg` which has a
   native extension. Confirm it installs cleanly on Windows (Python 3.11
   wheels exist). If not, `psycopg[binary]` is the fallback
   (`langgraph-checkpoint-postgres` supports both).

---

## Exit criteria for Phase 2

- `uv run pytest -x --ff` green (all tests, including new ones)
- `uv run ruff check` clean
- `uv run mypy src/` clean
- End-to-end: `POST /api/qualify` on a real URL returns populated
  `company_profile`, `contact`, `signals`, `fit_score`, `email_draft`
- HITL: graph pauses, `/api/qualify/{id}/approve` resumes it
- Postgres: thread persists across `uvicorn` restart
- Langfuse: traces visible in dashboard for a real run
- Chainlit: UI accessible at `/chainlit`, full flow works in browser
