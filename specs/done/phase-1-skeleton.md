# Phase 1: Project Skeleton

## Goal
Stand up a runnable project skeleton ending in a working `company_researcher` path:
input a company URL → orchestrator invokes `company_researcher` → returns a minimal
company profile via a real web search + scrape. This proves the LangGraph wiring,
state shape, tool integration, and FastAPI entry before we add contact_finder,
signal_detector, dossier_writer, HITL, and Chainlit in later phases.

**Out of scope for Phase 1** (tracked for later phases):
- contact_finder, signal_detector, dossier_writer agents
- Hunter.io tool
- `interrupt()` / human-in-the-loop email send
- Chainlit UI mount
- Langfuse observability
- Supabase `AsyncPostgresSaver` (use `InMemorySaver` in Phase 1; swap in Phase 2)

## Files to create
- `pyproject.toml` — uv-managed, Python 3.11, pinned deps
- `.python-version` — `3.11`
- `.env.example` — documented required env vars (no real values)
- `.gitignore` — standard Python + `.env`
- `README.md` — one-paragraph pointer to `CLAUDE.md`
- `src/saas_lead_agent/__init__.py`
- `src/saas_lead_agent/state.py` — `LeadState` TypedDict with `Annotated` reducers
- `src/saas_lead_agent/graph.py` — `StateGraph` assembly, `build_graph()` factory
- `src/saas_lead_agent/agents/__init__.py`
- `src/saas_lead_agent/agents/orchestrator.py` — supervisor via `create_agent`
- `src/saas_lead_agent/agents/company_researcher.py` — subgraph node
- `src/saas_lead_agent/tools/__init__.py`
- `src/saas_lead_agent/tools/web_search.py` — Tavily wrapper as `@tool`
- `src/saas_lead_agent/tools/scraper.py` — httpx+BeautifulSoup `@tool`
- `src/saas_lead_agent/memory/__init__.py`
- `src/saas_lead_agent/memory/checkpointer.py` — `InMemorySaver` factory (Phase 1)
- `src/saas_lead_agent/api/__init__.py`
- `src/saas_lead_agent/api/schemas.py` — Pydantic v2 request/response models
- `src/saas_lead_agent/api/routes.py` — `POST /research` endpoint
- `src/saas_lead_agent/api/main.py` — FastAPI app factory (Chainlit mount deferred)
- `tests/__init__.py`
- `tests/test_state.py` — reducer behavior
- `tests/test_graph_smoke.py` — graph compiles, runs with a stubbed tool
- `tests/conftest.py` — env loading, shared fixtures

## Step-by-step

### Step 1 — Package scaffolding and dependency pinning
Create `pyproject.toml`, `.python-version`, `.gitignore`, `.env.example`, `README.md`,
and empty `__init__.py` files for the package tree. Pin:
- `langgraph>=1.1,<1.2`
- `langchain>=1.0,<1.1`
- `langgraph-prebuilt` to a single explicit patch version (verify via Context7
  which patch is current and non-breaking)
- `langchain-google-genai` (Gemini), `langchain-openai`
- `fastapi`, `uvicorn[standard]`, `pydantic>=2`
- `httpx`, `beautifulsoup4`, `tavily-python`
- dev: `pytest`, `pytest-asyncio`, `ruff`, `mypy`

**Verify:**
```
uv sync
uv run python -c "import langgraph, langchain, fastapi; print('ok')"
uv run ruff check
```

### Step 2 — State definition
Implement `state.py` with `LeadState` TypedDict:
- `company_url: str` (input)
- `domain: str`
- `messages: Annotated[list[AnyMessage], add_messages]`
- `company_profile: dict | None`
- `errors: Annotated[list[str], operator.add]`

**Verify:**
```
uv run pytest -x tests/test_state.py
uv run mypy src/saas_lead_agent/state.py
```
`test_state.py` asserts: reducers accumulate (messages append, errors concat),
non-reducer fields overwrite.

### Step 3 — Tools: web_search + scraper
- `web_search.py`: thin `@tool` over `tavily-python`, returns top-N results as
  `list[dict]`. Reads `TAVILY_API_KEY` from env.
- `scraper.py`: `@tool` fetching a URL with httpx + realistic User-Agent header
  (per CLAUDE.md gotcha), parses with BeautifulSoup, returns cleaned text
  (truncated to a sane cap, e.g. 20k chars).

**Verify:**
```
uv run ruff check src/saas_lead_agent/tools/
uv run python -c "from saas_lead_agent.tools.scraper import scrape; print(scrape.invoke({'url':'https://example.com'})[:200])"
```

### Step 4 — company_researcher agent
Implement as a `create_agent` (tool-calling) with `web_search` + `scraper` bound,
Gemini 2.5 Flash-Lite model. System prompt: "Given a company URL, produce a JSON
profile with fields: name, tagline, hq, employees_estimate, funding_stage,
products, notable_customers." Returns structured output written to
`state["company_profile"]`.

**Verify:**
```
uv run ruff check src/saas_lead_agent/agents/company_researcher.py
uv run mypy src/saas_lead_agent/agents/company_researcher.py
```

### Step 5 — Orchestrator (supervisor)
Supervisor built via `langchain.agents.create_agent` per CLAUDE.md (never
`create_supervisor`). In Phase 1 it routes to `company_researcher` only. Verify
via Context7 the current tool-calling-supervisor pattern before coding.

**Verify:**
```
uv run ruff check src/saas_lead_agent/agents/orchestrator.py
uv run mypy src/saas_lead_agent/agents/orchestrator.py
```

### Step 6 — Graph assembly
`graph.py` exposes `build_graph(checkpointer) -> CompiledStateGraph`. Nodes:
orchestrator → company_researcher → END. Use `InMemorySaver` in tests.
thread_id format `lead:{domain}` per CLAUDE.md.

**Verify:**
```
uv run pytest -x tests/test_graph_smoke.py
```
Smoke test compiles the graph with stubbed tools (monkeypatched Tavily +
scraper returning fixtures) and asserts `company_profile` is populated.

### Step 7 — FastAPI entry
- `schemas.py`: `ResearchRequest {company_url}`, `ResearchResponse {profile, thread_id}`.
- `routes.py`: `POST /research` invokes the compiled graph with `durability="async"`.
- `main.py`: `create_app()` factory, mounts routes. **Do not mount Chainlit yet**
  (Phase 2); leave a comment marker where it will go.

**Verify:**
```
uv run uvicorn src.saas_lead_agent.api.main:app --port 8080 &
curl -X POST localhost:8080/research -H 'content-type: application/json' \
  -d '{"company_url":"https://example.com"}'
```
Expect 200 with `profile` and `thread_id`.

### Step 8 — Final sweep
```
uv run ruff check
uv run mypy src/
uv run pytest -x --ff
```

## Risks & unknowns
- **LangGraph 1.1 supervisor shape.** `create_agent` API details for tool-calling
  supervisors have shifted; `langgraph-prebuilt` ships breaking patches. Must
  confirm via Context7 MCP before Step 4 and Step 5.
- **Gemini structured output.** Gemini 2.5 Flash-Lite's JSON-mode behavior via
  `langchain-google-genai` may require `.with_structured_output(...)` rather
  than prompt-only; resolve in Step 4.
- **Tavily quota.** Live web_search in tests would burn quota; smoke test
  monkeypatches.
- **Checkpointer swap later.** Using `InMemorySaver` now means threads don't
  persist across restarts. Explicit Phase 2 task: swap to `AsyncPostgresSaver`.
- **Windows path quirks.** User-Agent header string and httpx async client
  work identically on Windows, but `uvicorn --reload` file-watching can be
  flaky; document in README if encountered.

## Exit criteria
- `uv run pytest -x --ff` green
- `uv run ruff check` clean
- `uv run mypy src/` clean
- `POST /research` on a real URL returns a populated `company_profile`
- `decisions.md` appended with one ADR: "Phase 1 uses InMemorySaver; Postgres deferred to Phase 2"
- `TODO.md` updated: Phase 1 item checked, Phase 2 seeded
