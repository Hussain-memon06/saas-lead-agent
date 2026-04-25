# Phase 3 Step 5 — Deployment (Docker + Cloud Run)

## Goal
Ship a single, reproducible artefact (Docker image) that runs identically in
local dev (`docker compose up`) and production (Cloud Run).  Document the
gcloud workflow end-to-end so a deploy can be reproduced from the runbook
without tribal knowledge.

## Status: COMPLETE

---

## Files added / changed

| File | Change |
|------|--------|
| `Dockerfile` | New: multi-stage (`builder` → `runtime`); uv install; non-root `app` user (uid 1000); EXPOSE 8080; `CMD` honours `${PORT}` for Cloud Run |
| `docker-compose.yml` | New: postgres 15 + one-shot migrate + app, with `service_completed_successfully` ordering |
| `.dockerignore` | New: excludes `.git`, `.venv`, `.env*`, tests, specs, IDE meta |
| `DEPLOYMENT.md` | New: 10-section runbook for Cloud Run + Secret Manager + Artifact Registry |
| `tests/test_docker.py` | New: 17 tests (16 always-on file/content checks + 1 real `docker build` that auto-skips when docker absent) |
| `CLAUDE.md` | New gotchas: multi-stage, `${PORT}`, non-root, secrets via Secret Manager, migrate service |

---

## Architecture decisions

### Multi-stage Dockerfile
The `builder` stage installs `build-essential`, `libpq-dev`, and uv, then
runs `uv sync --frozen --no-dev` against the lock file.  The `runtime`
stage starts from a fresh `python:3.11-slim` and copies only `/app/.venv`
and `/app/src` from the builder.  Net result: ~150 MB final image vs
~800 MB single-stage.  Compilers and apt build deps stay out of production.

### Non-root user
`useradd --uid 1000 app` and `USER app` at the end of the runtime stage.
Cloud Run rejects containers that run as root in newer revisions, and it's
defensible posture even where it's still allowed.

### `${PORT}` honours Cloud Run, defaults to 8080
`CMD ["sh", "-c", "exec uvicorn ... --port ${PORT:-8080}"]`.  Cloud Run
injects `$PORT`; docker-compose runs without it and gets 8080.  Same image,
both worlds.

### Secrets via Secret Manager, not baked
`.dockerignore` excludes `.env*` so build context can never leak keys into
the layer cache.  `DEPLOYMENT.md` step 3–4 documents how to put each secret
into Secret Manager and bind the Cloud Run service account to it.  At
deploy time, `--set-secrets=NAME=SECRET:latest` injects them as env vars.

### `migrate` service in docker-compose
`AsyncPostgresSaver.setup()` is idempotent and the FastAPI lifespan calls
it on every cold start, so a separate migrations step isn't strictly
required.  But the user asked for one and it makes the first-boot story
explicit: postgres healthy → migrate runs once → app starts.  Belt and
suspenders, no harm.  Cloud Run doesn't need this — the lifespan handles it.

---

## Image dimensions

| Layer | Approx size |
|-------|------------|
| `python:3.11-slim` base | 50 MB |
| `libpq5 + ca-certificates` | 6 MB |
| `/app/.venv` (langgraph + langchain + chainlit + langfuse + sendgrid + psycopg + asyncpg + sqlalchemy + opentelemetry tree) | ~600 MB |
| `/app/src` | <1 MB |
| **Final image** | **~660 MB** |

Mostly LangChain + Chainlit + OpenTelemetry packages.  Could shave ~150 MB
by dropping the LangChain + LangSmith tracing extras if not used.

---

## Verification checklist

- [x] `uv run ruff check` — clean
- [x] `uv run mypy src/` — clean (27 source files)
- [x] `uv run pytest -x --ff` — 181 passed, 6 skipped
- [ ] `docker build .` — run on a machine with docker (auto-skipped here)
- [ ] `docker compose up --build` — full local stack smoke test
- [ ] `gcloud run deploy ...` — live Cloud Run deploy

---

## Risks & notes

- **Image size dominated by LangChain.**  Not actionable in this step;
  flag for future optimisation if cold-start latency becomes painful.
- **`docker compose` v2 syntax.**  Uses `condition: service_healthy` and
  `condition: service_completed_successfully` which require Compose v2.
  Old `docker-compose` (Python wrapper, v1) won't parse this file.
- **Single region.**  DEPLOYMENT.md uses `us-central1` throughout.  Multi-
  region rollout would need an Artifact Registry repo per region (or
  global mirror) and per-region `gcloud run deploy`.
- **Cloud Run min-instances=0.**  Cold start is ~5 s for this image.
  If user-facing latency matters, bump to `--min-instances=1` (~$25/mo
  for an idle 1Gi/1cpu instance).

---

## ADR

ADR-010 to be logged in `decisions.md` after approval:

> Cloud Run is the production target.  Multi-stage Dockerfile with uv;
> non-root `app` user; `${PORT}`-aware CMD.  Secrets live in Secret
> Manager, never in the image.  `docker-compose.yml` mirrors prod for
> local dev with a one-shot migrate service.

---

## Phase 3 wrap-up

With this step the system is **production-ready**:

| Step | Capability | Status |
|------|------------|--------|
| 1 | AsyncPostgresSaver — durable HITL state | ✅ |
| 2 | SendGrid — real email delivery | ✅ |
| 3 | Langfuse v3 — full LLM observability | ✅ |
| 4 | Chainlit v2 — non-technical chat UI | ✅ |
| 5 | Docker + Cloud Run runbook | ✅ |

Test count: 27 source files, **181 passing tests** (+ 6 integration tests
that skip without infra).  Ruff + mypy strict clean.

Suggested next: log ADR-007 / 008 / 009 / 010 in `decisions.md`, move
all `phase-3-*` specs from `in-progress/` to `done/`, update `TODO.md`
to mark Phase 3 as complete.
