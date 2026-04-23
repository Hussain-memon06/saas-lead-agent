# Architectural Decisions

## ADR-001 — InMemorySaver in Phase 1; AsyncPostgresSaver deferred to Phase 2
**Date:** 2026-04-22

Phase 1 uses LangGraph's `InMemorySaver` as the checkpointer so the skeleton is
runnable without Supabase credentials. Phase 2 will swap in `AsyncPostgresSaver`
backed by Supabase Postgres. All graph code is written so the checkpointer is
injected via `build_graph(checkpointer)`, making the swap a one-line change.

## ADR-002 — Chainlit UI deferred to Phase 2
**Date:** 2026-04-22

Chainlit is not mounted in Phase 1. The `api/main.py` `create_app()` factory
includes a comment marker where the mount will go. Rationale: stabilise core
graph wiring first; adding the UI layer onto a broken graph is expensive to debug.
Per CLAUDE.md, Chainlit must be mounted last in FastAPI or routes 404.

## ADR-003 — Context7 MCP gates Steps 4 and 5 before writing agent code
**Date:** 2026-04-22

LangGraph 1.1 supervisor and `create_agent` API shapes will be verified via
Context7 MCP before any agent code is written (Steps 4 and 5). `langgraph-prebuilt`
has shipped breaking changes on patch versions; guessing the API is not acceptable.

## ADR-005 — `_extract_json` factored into `utils.py`
**Date:** 2026-04-23

The fence-stripping + JSON-parse primitive was duplicated in `company_researcher`
and `orchestrator`. Moved to `saas_lead_agent/utils.py` as the canonical
location. `contact_finder` and all future agents import from there.
`_parse_orchestrator_output` retains its orchestrator-specific merge logic locally.
