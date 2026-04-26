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

## Phase 3 — Production Hardening [DONE]

- [x] AsyncPostgresSaver via lifespan; 5 integration tests skip without POSTGRES_URL (36251d4)
- [x] SendGrid email delivery; 5-branch send_email node; 14 new tests (f9fbc55)
- [x] Langfuse v3 None-safe singleton; CallbackHandler wired into _config(); 12 tests (b1e1823)
- [x] Chainlit v2 mounted at /chainlit AFTER router; DISABLE_CHAINLIT flag for tests; 19 tests (9ab6286)
- [x] Dockerfile (multi-stage) + docker-compose.yml + .dockerignore + DEPLOYMENT.md; 17 tests (f22094e)
- [x] Final state: ruff + mypy (27 files) + pytest (181 tests, 6 skipped) all green
- [x] ADRs 007–010 logged in decisions.md
- [x] Phase 3 specs moved to specs/done/

Specs: specs/done/phase-3-master-plan.md and step-by-step files

### Manual smoke tests still owed (require infra)

- [ ] Postgres persistence: `POSTGRES_URL=... uv run pytest tests/test_persistence.py -v`
- [ ] SendGrid delivery: full /qualify → /approve flow against a test inbox
- [ ] Langfuse: confirm trace appears in dashboard with all spans nested
- [ ] Chainlit UI: full flow in browser at http://localhost:8080/chainlit
- [ ] Docker build: `docker build .` on a machine with docker installed
- [ ] Cloud Run deploy: follow DEPLOYMENT.md end-to-end on a real GCP project

## Phase 4 — Operate & Iterate [TODO]

### Monitoring & alerting
- [ ] Cloud Run uptime check + alert on 5xx rate > 1% / 5 min
- [ ] Langfuse dashboard: per-agent latency p95, token cost per qualify
- [ ] SendGrid bounce/complaint webhook → state update + alert on >2% rate
- [ ] Postgres slow-query log review (any qualify > 30s gets a span dump)

### Scaling & cost
- [ ] Cold-start measurement at min-instances=0 vs 1 (decide tradeoff)
- [ ] Per-domain rate limiting on /api/qualify (Tavily + Hunter quotas)
- [ ] Concurrency tuning — measure single-instance throughput before raising max-instances
- [ ] Image size diet: drop unused LangChain/OTel sub-packages if cold-start hurts
- [ ] Cache hit-rate review: company profile cache for repeat-domain qualifies?

### Quality & safety
- [ ] Fit-score calibration: review 20+ real runs, tune the dossier_writer prompt
- [ ] Hallucination audit: spot-check 50 signals for off-domain leakage
- [ ] PII review: confirm no real client emails leak into Langfuse traces unredacted
- [ ] Email-domain reputation monitoring (SPF / DKIM / DMARC compliance check)
- [ ] Suppression list ingest: anyone who replies "stop" added automatically

### Features
- [ ] Bulk qualify: POST /api/qualify accepts a CSV of URLs
- [ ] Slack notification on each approve/reject decision
- [ ] HubSpot/Salesforce integration: write the dossier as a CRM record
- [ ] Reply detection: SendGrid inbound parse → mark thread "replied"
- [ ] Custom email templates per ICP segment

### CI/CD
- [ ] GitHub Actions: ruff + mypy + pytest on every PR
- [ ] Block merge to main on red CI
- [ ] Auto-build + push image on tag push (`v0.x.y`)
- [ ] Staging Cloud Run service for pre-production smoke tests
