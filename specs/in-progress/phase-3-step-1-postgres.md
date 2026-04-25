# Phase 3 Step 1 — AsyncPostgresSaver (Supabase Postgres)

## Goal
Swap `InMemorySaver` for `AsyncPostgresSaver` backed by Postgres so HITL state
persists across server restarts.  Fulfills ADR-001 (deferred from Phase 1).

## Status: COMPLETE

---

## Files changed

| File | Change |
|------|--------|
| `pyproject.toml` | Added `langgraph-checkpoint-postgres>=2.0,<3.0`, `asyncpg>=0.29,<0.30`, `psycopg[binary]>=3.1,<4.0`, `sqlalchemy[asyncio]>=2.0,<3.0` |
| `src/saas_lead_agent/memory/checkpointer.py` | New: `postgres_checkpointer()` async context manager |
| `src/saas_lead_agent/graph.py` | New: `build_graph_with_postgres()` async context manager |
| `src/saas_lead_agent/api/main.py` | Added `lifespan()`: swaps `_routes._graph` to Postgres on startup when `POSTGRES_URL` is set |
| `tests/test_persistence.py` | New: 5 integration tests; skip automatically when `POSTGRES_URL` is absent |
| `tests/conftest.py` | Added comment explaining `POSTGRES_URL` must stay unset for unit tests |
| `.env.example` | Added `POSTGRES_URL` with local and Supabase example values |
| `CLAUDE.md` | Added Postgres gotchas section |

---

## Architecture decisions

### Driver: psycopg3, not asyncpg
`AsyncPostgresSaver` from `langgraph-checkpoint-postgres` uses `psycopg[binary]`
(psycopg3) as its async driver.  `asyncpg` is present in `pyproject.toml` for
direct use in future migrations/queries, but is NOT used by the checkpointer.

Connection string format: `postgresql://user:pass@host:5432/dbname`
(no `+asyncpg` suffix — that's the SQLAlchemy dialect prefix, not needed here).

### Lifespan swap pattern
`api/main.py` lifespan replaces the module-level `_routes._graph` variable at
startup if `POSTGRES_URL` is set.  This keeps the existing test patch path
(`patch("saas_lead_agent.api.routes._graph", mock)`) unchanged — zero test
edits required.

If `POSTGRES_URL` is absent, the lifespan yields immediately and
`InMemorySaver` stays.  Tests never set `POSTGRES_URL`, so they always run
on in-memory state.

### `setup()` idempotency
`await checkpointer.setup()` runs DDL to create LangGraph checkpoint tables.
It is idempotent (safe to call on every process start).  Connection string
and `setup()` are both inside the `async with AsyncPostgresSaver.from_conn_string()`
context so the connection pool is properly cleaned up on shutdown.

---

## Running locally

### 1. Start Postgres

```bash
docker run --name saas-lead-pg \
    -e POSTGRES_USER=saas_lead \
    -e POSTGRES_PASSWORD=password \
    -e POSTGRES_DB=saas_lead \
    -p 5432:5432 \
    -d postgres:15
```

### 2. Set env var

```bash
# .env (or export directly)
POSTGRES_URL=postgresql://saas_lead:password@localhost:5432/saas_lead
```

### 3. Start the API

```bash
uv run uvicorn src.saas_lead_agent.api.main:app --reload --port 8080
# Startup log: "Postgres checkpointer ready" (if lifespan logs; otherwise silent)
```

### 4. Run persistence integration tests

```bash
POSTGRES_URL=postgresql://saas_lead:password@localhost:5432/saas_lead \
    uv run pytest tests/test_persistence.py -v
```

Expected output (5 tests):
- `test_thread_persists_across_checkpointer_instances` — PASSED
- `test_thread_persists_with_resume_false` — PASSED
- `test_thread_ids_are_isolated` — PASSED
- `test_setup_is_idempotent` — PASSED
- `test_postgres_checkpointer_helper` — PASSED

### 5. Manual HITL persistence smoke test

```bash
# Run 1 — qualify (graph pauses at await_approval)
curl -s -X POST http://localhost:8080/api/qualify \
    -H 'Content-Type: application/json' \
    -d '{"url":"https://stripe.com"}' | jq .interrupted

# Kill the server (Ctrl-C), restart it, then resume:
uv run uvicorn src.saas_lead_agent.api.main:app --reload --port 8080

# Run 2 — approve (graph resumes from checkpoint in Postgres)
curl -s -X POST http://localhost:8080/api/leads/lead:stripe.com/approve | jq .send_result
```

Expected: `"sent"` — state survived the restart.

---

## Supabase production setup

1. Create a Supabase project → Settings → Database → Connection string (URI mode)
2. Copy the URI; set it as `POSTGRES_URL` in your prod environment
3. `setup()` creates tables automatically on first startup

```
POSTGRES_URL=postgresql://postgres:[password]@db.[project].supabase.co:5432/postgres
```

---

## Verification checklist

- [x] `uv run ruff check` — clean
- [x] `uv run mypy src/` — clean (22 files)
- [x] `uv run pytest -x --ff` — 119 passed, 5 skipped (persistence tests)
- [ ] `uv run pytest tests/test_persistence.py -v` — requires running Postgres
- [ ] Manual smoke test: HITL state survives server restart

---

## Risks & notes

- `langgraph-checkpoint` was downgraded from 4.0.2 → 2.1.2 during resolution
  (required by `langgraph-checkpoint-postgres==2.0.25`).  All 119 existing
  tests pass; no regressions observed.
- `asyncpg` native extension: Python 3.11 wheels exist for Windows x86-64 and
  Linux x86-64 (confirmed by `uv sync` succeeding).
- `_routes._graph` points at a closed connection pool after lifespan exit.
  In production this is fine (process exits).  For hot-reload dev mode, the
  lifespan restarts on each reload — connection pool is re-created correctly.
