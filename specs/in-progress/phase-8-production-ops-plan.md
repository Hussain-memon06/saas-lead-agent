# Phase 8 Production Deployment, CI/CD, And Operational Readiness Plan

## Status

Phase 8 has started with a planning-only milestone. This document defines the
implementation order for production operations without changing runtime
behavior, dependency manifests, CI configuration, Docker artifacts, or deployed
infrastructure yet.

The immediate goal is to make the remaining production work explicit and
sequential so each slice can be implemented and verified without broad,
expensive default checks.

## Current Known Production Surface

- Frontend is deployed on Vercel behind `agent.hussainflow.com`.
- Backend is FastAPI with LangGraph, optional Postgres checkpoints, Langfuse
  tracing, Clerk JWT verification, Tavily, Hunter.io, scraper, SendGrid, and
  OpenAI.
- Phase 6 production auth/CORS/startup checks now fail closed for the current
  protected route surface.
- Phase 7 provider-free evaluation exists and the golden dataset passes 30/30.
- Existing Docker, compose, deployment, and README artifacts need a focused
  Phase 8 review before implementation decisions.
- HTTP provider request logs now redact sensitive query-string fields such as
  `api_key` before formatting `httpx`/`httpcore` log records.

## Milestone 8.1 Operational Inventory

### Deployment Artifacts Reviewed

- `README.md`
- `DEPLOYMENT.md`
- `.env.example`
- `frontend/.env.local.example`
- `frontend/next.config.mjs`
- `frontend/package.json`
- `Dockerfile`
- `docker-compose.yml`
- `.github/` workflow directory check

### Current Topology

| Surface | Current Finding | Notes |
| --- | --- | --- |
| Frontend | Next.js app under `frontend/` | Live domain is `agent.hussainflow.com`; local dev runs on `localhost:3000`. |
| Frontend hosting | Vercel | `README.md` says Vercel; no Vercel config was reviewed in this slice. |
| Frontend API routing | Dev proxy to `http://localhost:8080` by default | `NEXT_PUBLIC_API_BASE_URL` disables the rewrite and makes browser calls absolute. |
| Backend | FastAPI app in Docker-capable Python service | Local dev can run directly with uvicorn or through compose. |
| Backend hosting | Unclear from source-of-truth docs | `README.md` says Railway; `DEPLOYMENT.md` is a Cloud Run runbook. Treat as documentation drift until the live backend host is confirmed. |
| Persistence | Optional Postgres | Required for durable HITL resume across process restart; unset uses in-memory state. |
| Auth | Clerk | Frontend sends Clerk JWT; backend verifies issuer/signature and owner scopes protected lead routes. |
| Email | SendGrid or explicit stub mode | Development should use `SENDGRID_STUB_ENABLED=true`; production must not report fake sends. |
| Observability | Optional Langfuse plus app metadata | No monitoring/alerting runbook exists yet. |
| CI | None found | `.github/` does not exist. |
| Docker | Multi-stage backend image plus local compose | Dockerfile comment/docs mention `$PORT`, but the current `CMD` uses fixed port `8080`; this needs a focused Docker slice. |
| Health/readiness | Not implemented in Phase 8 yet | `/health` and `/ready` semantics remain Milestone 8.2. |
| API versioning | Not implemented | `/api/v1` strategy remains Milestone 8.6. |

### Environment And Configuration Matrix

| Variable | Local Direct Dev | Local Docker/Compose | Staging | Production |
| --- | --- | --- | --- | --- |
| `APP_ENV` | `development` | `development` | `staging` | `production` |
| `AUTH_DEV_BYPASS_ENABLED` | optional explicit `true` only for local bypass | optional explicit `true` only for local bypass | `false` | `false` |
| `CLERK_ISSUER` | required when bypass is disabled | required when bypass is disabled | required | required |
| `CLERK_JWKS_URL` | optional | optional | optional | optional |
| `CLERK_AUDIENCE` | optional | optional | optional if configured in Clerk | optional if configured in Clerk |
| `CLERK_AUTHORIZED_PARTIES` | include `http://localhost:3000` when used | include `http://localhost:3000` when used | staging frontend origin | `https://agent.hussainflow.com` |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` or wildcard in development | `http://localhost:3000` | exact staging origin | `https://agent.hussainflow.com` |
| `OPENAI_API_KEY` | required for real research | required for real research | required | required |
| `TAVILY_API_KEY` | required for full search behavior | required for full search behavior | required for full search behavior | required for full search behavior |
| `HUNTER_API_KEY` | required for contact finding | required for contact finding | required for contact finding | required for contact finding |
| `SENDGRID_STUB_ENABLED` | `true` recommended | `true` recommended | usually `true` unless testing real delivery | `false` or unset when real delivery is enabled |
| `SENDGRID_API_KEY` | optional | optional | required for real delivery | required for real delivery |
| `SENDGRID_FROM_EMAIL` | optional | optional | required with SendGrid | required with SendGrid |
| `POSTGRES_URL` | optional; unset uses memory | compose sets in-cluster URL | recommended | required for durable approval resume |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | optional | optional | optional/recommended | recommended |
| `LANGFUSE_HOST` | optional | optional | optional | optional |
| OpenAI cost-rate env vars | optional | optional | optional | optional/recommended for cost monitoring |
| `MAX_REQUEST_BODY_BYTES` | optional, default policy value | optional | recommended explicit value | recommended explicit value |
| `RATE_LIMIT_ENABLED` | optional; defaults on outside tests | optional | `true` | `true` |
| `QUALIFY_RATE_LIMIT_PER_MINUTE` | optional | optional | explicit value | explicit value |
| `DECISION_RATE_LIMIT_PER_MINUTE` | optional | optional | explicit value | explicit value |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | required in `frontend/.env.local` | required for frontend dev | required in Vercel | required in Vercel |
| `CLERK_SECRET_KEY` | required by Clerk Next.js runtime | required by Clerk Next.js runtime | required in Vercel | required in Vercel |
| `NEXT_PUBLIC_API_BASE_URL` | usually unset for dev proxy | unset for dev proxy | staging backend URL | production backend URL |
| `BACKEND_PROXY_TARGET` | optional; defaults to `http://localhost:8080` | optional | not used when API base is set | not used when API base is set |

### Prioritized Phase 8 Gaps

1. Add `/health` and `/ready` endpoints with safe startup/config diagnostics.
2. Resolve deployment-doc drift: Railway/Vercel versus Cloud Run/Vercel and
   the actual live backend host.
3. Fix Docker `$PORT` behavior or update docs if fixed `8080` is intentional.
4. Add CI workflow with backend lint/format/type/tests, frontend build, and
   opt-in provider-free eval job.
5. Add monitoring/runbook docs for latency, 5xx, provider/tool failures,
   retrieval failures, token/cost spikes, and email delivery failures.
6. Add rollback, provider outage, cost spike, and data lifecycle notes.
7. Decide `/api/v1` alias/migration strategy before route changes.

## Non-Goals For This Planning Milestone

- No GitHub Actions workflow changes yet.
- No Dockerfile or compose changes yet.
- No dependency or package-manifest changes.
- No production build, Docker build, compose run, cloud smoke test, or external
  provider check.
- No API route rewrites or `/api/v1` migration yet.
- No monitoring vendor integration yet.
- No background queue, durable job runtime, vector database, or MCP runtime.

## Phase 8 Milestone Order

### Milestone 8.1: Operational Inventory And Config Matrix

Goal: document the real deployment topology, required environment variables,
release-only verification commands, and staging/production configuration
matrix before changing infrastructure.

Scope:

- inventory current frontend/backend deployment artifacts
- list required and optional environment variables by environment
- define what is dev-only, staging-only, production-required, and release-only
- identify current gaps in deployment docs, Docker behavior, CI, health checks,
  monitoring, rollback, and data lifecycle notes

Deliverables:

- updated Phase 8 section in `PLANS.md` and `PROGRESS.md`
- an environment/config matrix in docs
- a prioritized Phase 8 implementation checklist
- explicit release-only verification list

Acceptance criteria:

- Future Phase 8 implementation slices have a clear order.
- Critical production secrets and public frontend variables are documented
  without exposing secret values.
- Full verification, Docker, cloud, and external-provider checks remain
  explicitly opt-in.

### Milestone 8.2: Health, Readiness, And Startup Diagnostics

Goal: make backend service health inspectable without invoking external
providers by default.

Scope:

- define `/health` and `/ready` semantics
- distinguish process liveness from dependency readiness
- expose safe build/config/runtime metadata only
- keep provider checks shallow or opt-in

Acceptance criteria:

- Health endpoints do not leak secrets or PII.
- Readiness reports missing critical configuration clearly.
- Tests cover endpoint behavior without external API calls.

### Milestone 8.3: CI Quality Gates

Goal: add CI that matches the tiered verification policy.

Scope:

- backend lint/format/type/test jobs
- frontend install/lint/build job
- provider-free eval job as opt-in or scheduled/manual
- cache strategy that avoids logging secrets
- release-only gates separated from normal Codex iteration

Acceptance criteria:

- Pull requests get deterministic provider-free checks.
- External provider and deployment checks are gated behind explicit workflow
  dispatch or protected secrets.
- CI logs do not echo secrets.

### Milestone 8.4: Docker And Runtime Hardening

Goal: make container behavior predictable for the backend deployment target.

Scope:

- confirm `$PORT` handling
- add or validate healthcheck behavior
- review image size and build layers
- document local compose versus production deployment use
- avoid running Docker builds until explicitly requested

Acceptance criteria:

- Docker behavior is documented and testable.
- Docker build/compose checks remain release-candidate checks unless requested.

### Milestone 8.5: Monitoring, Alerts, And Runbooks

Goal: document operational response paths before adding vendor-specific
monitoring integrations.

Scope:

- latency, 5xx, provider failure, tool failure, retrieval failure, token/cost
  spike, and email delivery failure signals
- rollback runbook
- external provider outage runbook
- cost spike runbook
- data retention/export/deletion notes

Acceptance criteria:

- Operators know what to watch and what to do when a production signal fires.
- Runbooks avoid requiring secret values in docs.

### Milestone 8.6: API Version Strategy

Goal: decide how `/api/v1` should be introduced without breaking the current
frontend or deployed integrations.

Scope:

- define compatibility window for existing `/api/*` routes
- choose alias versus migration approach
- document response-envelope strategy
- defer implementation until the route compatibility plan is approved

Acceptance criteria:

- The versioning plan protects current app behavior.
- Any implementation slice can be tested with targeted API tests.

## Verification Policy

Normal Phase 8 planning edits are docs-only and do not require test execution.

For implementation slices, use targeted checks only:

```bash
uv run --extra dev python -m pytest tests/test_api.py -q
uv run --extra dev python -m pytest tests/test_docker.py -q
```

Release-only checks remain opt-in:

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
uv run pytest -x --ff
cd frontend && npm run build
docker compose build
docker compose up -d
```

## Immediate Next Step

Begin Milestone 8.1 by inspecting only the current deployment/config docs and
deployment artifacts needed to build an operational inventory. Do not modify
CI, Docker, source code, dependencies, or deployment settings until that
inventory is reviewed.
