# TODO

## Phase 1 — Project Skeleton [DONE]

- [x] Package scaffolding and dependency pinning (pyproject.toml, uv sync)
- [x] LeadState TypedDict with Annotated reducers (messages, errors)
- [x] Tools: web_search (Tavily) and scraper (httpx + BeautifulSoup)
- [x] company_researcher agent (create_agent + Gemini 2.5 Flash-Lite)
- [x] Orchestrator supervisor with parallel subagent dispatch
- [x] StateGraph assembly: START → orchestrator → [researcher, contact, signal] → END
- [x] FastAPI app: POST /api/qualify with InMemorySaver, thread_id=lead:{domain}
- [x] Final sweep: ruff + mypy (16 files) + pytest (68 tests) all green

Spec: specs/done/phase-1-skeleton.md

## Phase 2 — Full Pipeline [TODO]

- [ ] contact_finder: replace Phase 1 stub with Hunter.io lookup + LLM enrichment
- [ ] signal_detector: replace Phase 1 stub with web_search buying-signal detection
- [ ] dossier_writer: GPT-4o-mini email composer node
- [ ] Human-in-the-loop: interrupt() before email send, Command(resume=...) to continue
- [ ] AsyncPostgresSaver: swap InMemorySaver for Supabase Postgres (ADR-001)
- [ ] Langfuse v3 observability: CallbackHandler on graph runs
- [ ] Chainlit v2 UI: mount at /chainlit in api/main.py (AFTER all other routes)
- [ ] Hunter.io tool in tools/hunter.py
- [ ] LeadState: add fit_score (int), email_draft (str) fields
- [ ] End-to-end smoke test on a real company URL
