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

## ADR-004 — GPT-4o-mini for dossier_writer; Gemini 2.5 Flash-Lite for all other agents
**Date:** 2026-04-24

`dossier_writer` uses `ChatOpenAI(model="gpt-4o-mini")` via direct `model.ainvoke()` (no
tools, no ReAct loop). All other agents (company_researcher, contact_finder,
signal_detector, orchestrator) use `ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite")`.
Rationale: GPT-4o-mini produces higher-quality prose for email drafting; Gemini
Flash-Lite is faster and cheaper for the tool-calling research nodes.

## ADR-005 — `_extract_json` factored into `utils.py`
**Date:** 2026-04-23

The fence-stripping + JSON-parse primitive was duplicated in `company_researcher`
and `orchestrator`. Moved to `saas_lead_agent/utils.py` as the canonical
location. `contact_finder` and all future agents import from there.
`_parse_orchestrator_output` retains its orchestrator-specific merge logic locally.

## ADR-006 — `send_email` is a Phase 2 stub; real delivery deferred to Phase 3
**Date:** 2026-04-25

The `send_email` node in Phase 2 only records an outcome (`send_result =
"sent" | "rejected"`) based on the HITL approval decision. Actual email
delivery — SMTP, AWS SES, SendGrid, or similar — is intentionally deferred
to Phase 3.

Rationale: Phase 2 focuses on the agentic pipeline and HITL plumbing. Real
delivery introduces transactional concerns (retries, bounces, suppression
lists, DKIM/SPF) that warrant a dedicated phase rather than being bolted on.
Default-deny semantics in the stub (`email_approved=None` → `"rejected"`) are
preserved so Phase 3 can drop in real delivery without changing the contract.

## ADR-007 — SendGrid as primary email provider; sync SDK wrapped in `asyncio.to_thread`
**Date:** 2026-04-25

Phase 3 fulfills ADR-006 with the official `sendgrid` Python SDK rather than
SES, raw SMTP, or a competitor (Postmark, Mailgun). The SDK is sync-only
(built on `python-http-client`); we invoke it inside `asyncio.to_thread` so
the event loop is not blocked during the HTTP round-trip.

Rationale: SendGrid has the cleanest free tier (100 emails/day) for testing,
ships delivery analytics + suppression lists out of the box, and the SDK is
well-documented. The `asyncio.to_thread` wrapper avoids pulling in `aiohttp`
or rolling a custom async REST client for a single integration.

A stub-fallback path is preserved for dev/test: if `SENDGRID_API_KEY` is
unset, the `send_email` node returns `send_result="sent"` without actually
delivering, so the rest of the pipeline can be exercised end-to-end without
provider credentials. Tests rely on this branch.

## ADR-008 — Langfuse handler is None-safe; missing keys disable tracing without breaking the graph
**Date:** 2026-04-25

`get_langfuse_handler()` in `memory/langfuse_handler.py` returns `None`
whenever `LANGFUSE_PUBLIC_KEY` is unset OR the Langfuse SDK fails to
initialise (network unreachable, bad credentials, import error). The result
— both presence and absence — is cached in a module-level singleton so
repeated lookups don't re-import the SDK or retry initialisation.

Rationale: Tracing is an observability concern, never a hard dependency.
A misconfigured Langfuse account or a network partition during a deploy must
not crash the lead-research pipeline. Tests are simpler too: with no key
set, the handler is `None` and no callbacks are attached — no mocking of
the Langfuse SDK needed in any test that doesn't directly exercise it.

Wiring lives in one place: `_config()` in `api/routes.py` adds
`{"callbacks": [handler]}` when `handler is not None`. LangChain
propagates the config through every nested Runnable, so a single attachment
traces the orchestrator, all three subagents, dossier_writer, await_approval,
and send_email. No node-level changes were needed.

## ADR-009 — Chainlit 2.x mounted last in `create_app()`; UI calls graph directly, not via HTTP
**Date:** 2026-04-25

Chainlit was originally pinned at `>=1.0,<2.0` per the Phase 4 spec, but
Chainlit 1.x caps `uvicorn` at `<0.26` which conflicts with our pinned
`uvicorn[standard]>=0.34`. Bumped to `>=2.0,<3.0`. The Chainlit v2 API
shape used here (`cl.Action`, `cl.AskActionMessage`, `mount_chainlit`) is
stable across both major versions for our use case; only `cl.Action` changed
its `value: str` field to `payload: dict`.

The Chainlit app is mounted at `/chainlit` in `create_app()` AFTER
`app.include_router(router)`. Mounting before the router would 404 every
`/api/*` route. The mount is gated by `DISABLE_CHAINLIT=1` in
`tests/conftest.py` so the test FastAPI fixture stays free of socket.io
and static-file side-effects.

Approve/Reject actions in the UI resume the graph directly via
`_routes._graph.ainvoke(Command(resume=<bool>), ...)` rather than making a
loopback HTTP call to `/api/leads/{id}/approve`. Same logic as the REST
endpoints, no localhost URL hardcoding, single source of truth for HITL
state across REST and chat clients.

## ADR-010 — Google Cloud Run as production target; Secret Manager for credentials
**Date:** 2026-04-25

Cloud Run was chosen over Fly.io, Railway, AWS App Runner, and a custom
Kubernetes deploy. Reasons:

- **Scale-to-zero pricing.** A low-traffic deployment costs ~\$0–5/mo on
  Cloud Run vs ~\$25/mo for an always-on Fly.io machine.
- **Native GCP integration.** Secret Manager, Cloud Build, Artifact
  Registry, and Cloud Run all share IAM and service accounts; no
  third-party secret vault needed.
- **Reproducible from a Dockerfile.** Same multi-stage image runs locally
  via `docker compose up` and on Cloud Run via `gcloud run deploy`. No
  platform-specific buildpacks or magic.

The Dockerfile is multi-stage (`builder` → `runtime`); only `libpq5` and
`ca-certificates` ship in the final image. The container runs as non-root
(`app`, uid 1000) — required by recent Cloud Run revisions and good
hygiene regardless. The `CMD` honours `${PORT:-8080}` so the same image
works locally on 8080 and on whatever port Cloud Run injects.

Secrets live in Secret Manager, never baked into the image. `.dockerignore`
excludes all `.env*` files from the build context. At deploy time
`--set-secrets=NAME=SECRET:latest` injects them as environment variables.
Rotation is `gcloud secrets versions add NAME --data-file=-` followed by a
re-deploy; revisions are immutable so a rollback is one `update-traffic`
command away.
