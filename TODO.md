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

## Phase 2 — Full Pipeline [DONE]

- [x] Hunter.io tool in tools/hunter.py (c4b7235)
- [x] contact_finder: real Hunter.io + GPT-4o-mini agent (240313a)
- [x] refactor: _extract_json → shared utils.py (357871e)
- [x] signal_detector: web_search buying-signal detection (0890bbb)
- [x] LeadState: add fit_score, email_subject, email_body fields (77ce670)
- [x] dossier_writer: GPT-4o-mini direct ainvoke (4c963fa)
- [x] cross-company hallucination guards in researcher and signal_detector (af42497, 5c9374b)
- [x] switch all research/orchestrator agents to GPT-4o-mini (d98b1bc)
- [x] HITL: await_approval (interrupt) + send_email stub nodes (322531a)
- [x] LeadState: email_approved, send_result fields (d58ac07)
- [x] /approve and /reject endpoints with Command(resume=…) (e954192)
- [x] Final state: ruff + mypy (21 files) + pytest (119 tests) all green

Specs: specs/done/phase-2-master-plan.md and step-by-step files

## Phase 3 — Production Hardening [TODO]

### Real email delivery (replaces Phase 2 stub per ADR-006)
- [ ] tools/mailer.py: SMTP or SES/SendGrid wrapper as @tool
- [ ] send_email node: replace stub with real delivery; capture provider message_id
- [ ] LeadState: add message_id, sent_at fields
- [ ] Bounce/suppression handling (provider webhook → state update)

### Persistence (ADR-001 fulfillment)
- [ ] AsyncPostgresSaver: swap InMemorySaver for Supabase Postgres
- [ ] FastAPI lifespan context to manage DB connection lifecycle
- [ ] Migration: `await checkpointer.setup()` (idempotent)
- [ ] SUPABASE_DB_URL in .env.example; conftest stays on InMemorySaver

### Observability
- [ ] Langfuse v3 CallbackHandler on every agent ainvoke
- [ ] LANGFUSE_PUBLIC_KEY / SECRET_KEY / HOST in .env.example
- [ ] None-safe handler: missing keys disable tracing without breaking graph

### UI (ADR-002 fulfillment)
- [ ] Chainlit v2 cl_app.py: paste URL → stream dossier → AskActionMessage
      for approve/reject → call resume endpoint
- [ ] Mount Chainlit at /chainlit in api/main.py LAST per CLAUDE.md
- [ ] Smoke test: full flow in browser

### Deployment
- [ ] Dockerfile (uv-based, Python 3.11, multi-stage)
- [ ] docker-compose.yml with Postgres for local dev
- [ ] CI: ruff + mypy + pytest on every PR
- [ ] Production deployment target (Fly.io / Railway / AWS — TBD)
- [ ] Secret management strategy (.env not shipped to prod)

### Quality / safety
- [ ] Rate limiting on /api/qualify (Tavily + Hunter quotas)
- [ ] End-to-end smoke test on a real company URL (Stripe, Vercel, etc.)
- [ ] Fit-score calibration: review 20+ real runs, tune prompt
- [ ] PII handling: never send real client emails through Gemini free tier (CLAUDE.md gotcha)
