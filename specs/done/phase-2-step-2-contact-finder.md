# Phase 2 Step 2: Real contact_finder agent

## Goal
Replace the Phase 1 stub in `agents/contact_finder.py` with a real
`create_agent` ReAct node that calls `hunt_contact`, then uses Gemini to
normalise the result into a canonical contact dict written to `state["contact"]`.

Also factor the duplicated `_extract_json` helper (currently copy-pasted in
`company_researcher.py` and `orchestrator.py`) into a shared `utils.py` module.
This is the right moment — `contact_finder` will be a third consumer.

## Files to change

| File | Action |
|------|--------|
| `src/saas_lead_agent/utils.py` | **new** — shared `_extract_json` |
| `src/saas_lead_agent/agents/contact_finder.py` | **rewrite** — real agent |
| `src/saas_lead_agent/agents/company_researcher.py` | **edit** — import from utils |
| `src/saas_lead_agent/agents/orchestrator.py` | **edit** — import from utils |
| `tests/test_agents.py` | **edit** — fix `_BASE_STATE`, add contact_finder tests |

## Step-by-step

### Step A — Extract `_extract_json` into utils.py

Create `src/saas_lead_agent/utils.py` with:

```python
def _extract_json(content: str) -> dict[str, Any]: ...
```

Exact logic copied from `company_researcher.py` (handles plain JSON and
markdown-fenced JSON, raises `json.JSONDecodeError` / `ValueError`).

Then update `company_researcher.py` and `orchestrator.py` to import from utils
instead of defining their own copies. Delete the local definitions.

**Verification:**
```
uv run ruff check src/saas_lead_agent/utils.py src/saas_lead_agent/agents/company_researcher.py src/saas_lead_agent/agents/orchestrator.py
uv run mypy src/saas_lead_agent/utils.py src/saas_lead_agent/agents/company_researcher.py src/saas_lead_agent/agents/orchestrator.py
uv run pytest -x tests/test_agents.py tests/test_orchestrator.py
```
(All existing tests must stay green — `_extract_json` behaviour is unchanged.)

---

### Step B — Rewrite contact_finder.py

Implement following the `company_researcher` pattern exactly:

**Agent:**
- Model: `ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite")`
- Tools: `[hunt_contact]`
- `create_agent(model, tools=[hunt_contact], system_prompt=..., name="contact_finder")`

**System prompt:**
```
You are a B2B sales intelligence assistant.

Given a company domain, call hunt_contact to find the primary decision-maker,
then return a single JSON object — no markdown, no explanation, only the JSON —
with these exact fields:

{
  "name":       string | null,
  "title":      string | null,
  "email":      string | null,
  "linkedin":   string | null,
  "confidence": number | null,
  "source":     "hunter"
}

If hunt_contact returns an empty result, return the JSON with all fields null
except source. Use null for unknown fields. Return ONLY the JSON object.
```

**Node `contact_finder(state)`:**
- Reads `state["domain"]`
- Prompt: `f"Find the primary decision-maker contact for domain: {domain}"`
- On success: parses last AIMessage with `_extract_json`, returns `{"contact": dict}`
- On `JSONDecodeError` / `ValueError`: returns `{"errors": [...]}`
- On agent exception: returns `{"errors": [...]}`
- On empty messages: returns `{"errors": [...]}`

**Graceful degradation when `HUNTER_API_KEY` is absent:**
The `hunt_contact` tool raises `RuntimeError("HUNTER_API_KEY … not set")`.
The agent will surface this as a tool error; Gemini will respond with a
message the node cannot JSON-parse → falls into the `JSONDecodeError` branch
→ returns `{"errors": [...]}`. This is acceptable: missing key is a config
error, not a silent failure.

**Verification:**
```
uv run ruff check src/saas_lead_agent/agents/contact_finder.py
uv run mypy src/saas_lead_agent/agents/contact_finder.py
uv run pytest -x tests/test_agents.py
```

---

### Step C — Fix _BASE_STATE in test_agents.py + add contact_finder tests

`_BASE_STATE` in `test_agents.py` is missing `contact` and `signals` fields
(added to `LeadState` in Phase 1 Step 5). Fix it now while touching the file.

Add 7 new tests for `contact_finder`:

1. `test_contact_finder_happy_path` — agent returns valid JSON, contact populated
2. `test_contact_finder_null_fields` — all fields null (no Hunter result), still valid
3. `test_contact_finder_markdown_response` — JSON inside ```json fence
4. `test_contact_finder_json_parse_error` — plain text response → errors
5. `test_contact_finder_agent_exception` — ainvoke raises → errors
6. `test_contact_finder_empty_messages` — empty messages list → errors
7. `test_contact_finder_passes_domain_in_prompt` — domain in ainvoke messages

All tests patch `_get_contact_finder_agent` with `AsyncMock`, no real LLM calls.

**Verification:**
```
uv run pytest -x tests/test_agents.py -v
```

---

### Step D — Full sweep

```
uv run ruff check src/ tests/
uv run mypy src/
uv run pytest -x --ff
```

## Risks & unknowns

1. **`orchestrator.py` imports `_extract_json` locally** — it uses the same
   function name but operates on a different JSON shape (the orchestrator's
   multi-key output). After factoring, both files import the same function;
   the orchestrator's usage (dict with optional keys) is compatible.

2. **`_extract_json` in orchestrator.py** is actually called
   `_parse_orchestrator_output` (a wrapper around the shared logic). We import
   only `_extract_json` from utils; `_parse_orchestrator_output` stays local to
   orchestrator since its post-processing logic is orchestrator-specific.

3. **Gemini tool-call behaviour with a single tool** — Gemini 2.5 Flash-Lite
   with one tool (`hunt_contact`) should call it then return JSON. If it loops
   or refuses, the existing `JSONDecodeError` fallback handles it.

4. **`state.get("domain")`** — the Phase 1 stub uses `.get()` which mypy strict
   allows on TypedDict (it's inherited from dict). The rewrite will use
   `state["domain"]` (direct key access) to be consistent with other nodes.

## ADR to log

**ADR-005** (per master plan): `_extract_json` factored into `utils.py`.
Log after this step completes.
