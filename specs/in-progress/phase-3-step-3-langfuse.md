# Phase 3 Step 3 — Langfuse v3 observability

## Goal
Trace every LLM call inside the lead-research graph in Langfuse v3 — token
counts, latency, cost, full prompt/response — so production failures and
quality regressions are observable from outside the process.

## Status: COMPLETE

---

## Files changed

| File | Change |
|------|--------|
| `pyproject.toml` | Added `langfuse>=3.0,<4.0` |
| `src/saas_lead_agent/memory/langfuse_handler.py` | New: singleton factory, lifespan helper, flush hook |
| `src/saas_lead_agent/api/routes.py` | `_config()` attaches handler to `callbacks`; LangChain propagates through the whole graph |
| `src/saas_lead_agent/api/main.py` | Lifespan calls `flush_langfuse()` on shutdown |
| `tests/test_langfuse.py` | New: 12 tests covering None-safe, singleton, config wiring, flush, lifespan |
| `tests/conftest.py` | Documented `LANGFUSE_PUBLIC_KEY` must stay unset for tests |
| `.env.example` | Documented `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` |
| `CLAUDE.md` | Added Langfuse integration pattern to gotchas |

---

## Architecture decisions

### Single wiring point: `_config()` in routes.py
The handler is attached once, at the top-level `graph.ainvoke()` call.
LangChain's runnable framework propagates the `callbacks` field through every
nested Runnable, so a single attachment traces:

- The orchestrator node
- All three subagents (company_researcher, contact_finder, signal_detector)
  including their internal tool calls and ReAct loops
- dossier_writer's direct `ChatOpenAI.ainvoke()`
- await_approval (interrupt is captured as a span)
- send_email

No node-level changes were needed.  This is the lowest-touch correct wiring.

### None-safe singleton
`get_langfuse_handler()` caches both presence and absence — once we've
decided the handler is `None` (no key, or SDK init failed), every subsequent
lookup returns `None` without re-importing the SDK.  This protects the
hot path from repeated import / network attempts when Langfuse is misconfigured.

`reset_langfuse_handler()` is exported solely for tests; never call it
from production code.

### Failure surface
SDK import failure, network unreachable, bad credentials — all of these
collapse to "handler is `None`".  The graph runs unchanged.  Tracing is a
soft-fail observability concern, never a hard dependency for the pipeline.

### Flush on shutdown
Langfuse buffers events and flushes asynchronously; if the worker exits
mid-batch, traces are lost.  The FastAPI lifespan calls `flush_langfuse()`
in its `finally` block so traces from the final request reach Langfuse before
the process terminates.

---

## Behavior matrix

| `LANGFUSE_PUBLIC_KEY` | SDK init | `get_langfuse_handler()` | `_config["callbacks"]` |
|------------------------|----------|---------------------------|--------------------------|
| unset                  | not attempted | `None`                | omitted                  |
| set                    | success      | `CallbackHandler` instance | `[handler]`            |
| set                    | failure      | `None`                | omitted                  |

---

## Running locally with real tracing

### 1. Get keys

Sign up at <https://cloud.langfuse.com> → Settings → API Keys → create new
project → copy public + secret keys.

### 2. Set env

```bash
# .env
LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxxxxxxxxxx
LANGFUSE_SECRET_KEY=sk-lf-xxxxxxxxxxxxxxxx
LANGFUSE_HOST=https://cloud.langfuse.com  # optional, this is the default
```

### 3. Run a real qualify

```bash
uv run uvicorn src.saas_lead_agent.api.main:app --reload --port 8080

curl -X POST http://localhost:8080/api/qualify \
    -H 'Content-Type: application/json' \
    -d '{"url":"https://stripe.com"}'
```

Expected in Langfuse dashboard within ~10s:

- One root trace per qualify call
- Spans for each agent node
- Nested spans for each LLM call (model, tokens, cost, latency)
- Tool-call spans for `web_search`, `hunt_contact`

---

## Verification checklist

- [x] `uv run ruff check` — clean
- [x] `uv run mypy src/` — clean (25 source files)
- [x] `uv run pytest -x --ff` — 145 passed, 5 skipped
- [ ] Manual smoke test: real keys → trace appears in Langfuse dashboard

---

## Risks & notes

- **Trace cardinality.** Langfuse free tier has limits; a single qualify
  generates ~10–15 spans.  Production rollout should add per-domain rate
  limiting (already on the TODO.md "Quality / safety" list).
- **PII in traces.** Langfuse stores prompt + response text.  Real prospect
  emails will appear in Langfuse spans.  This is acceptable — Langfuse is a
  trusted observability vendor (SOC 2) — but document in onboarding.
- **OpenTelemetry deps.** Langfuse v3 brought 8 OTel sub-packages into the
  resolved set; no functional impact, but `uv sync` time grew slightly.
- **Singleton across worker reload.** uvicorn `--reload` re-imports the
  module so the singleton resets cleanly between reloads.  Multi-worker
  prod (gunicorn) initialises one handler per worker — expected and correct.

---

## ADR

ADR-008 to be logged in `decisions.md` after approval:

> Langfuse handler is None-safe and singleton-cached.  Missing keys or SDK
> failures degrade tracing silently; the graph never breaks because of
> observability misconfiguration.  Wiring lives in `_config()` only —
> LangChain propagates callbacks down the runnable tree, so node code is
> unchanged.
