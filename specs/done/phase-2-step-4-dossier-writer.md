# Phase 2 Step 4: dossier_writer + LeadState fields

## Goal
Add `fit_score` (int 1–10), `email_subject` (str), and `email_body` (str) to
`LeadState`, implement a `dossier_writer` node that uses GPT-4o-mini via direct
`model.ainvoke()` (no tools, no ReAct loop), wire it into the graph after the
parallel fan-in, and surface all three fields through the API response.

`email_subject` and `email_body` are stored and returned as **separate fields**
(not concatenated) so the UI can render them independently.

## Architecture decision (already approved)
Direct `model.ainvoke([SystemMessage, HumanMessage])` — not `create_agent`.
`dossier_writer` has no tools; wrapping it in a ReAct loop would add unnecessary
latency and token cost.

## Topology change
Current:
```
[company_researcher, contact_finder, signal_detector] → END
```
New:
```
[company_researcher, contact_finder, signal_detector] → dossier_writer → END
```
`dossier_writer` runs after the fan-in — it has all three upstream results
available in state.

## Files to change

| File | Action |
|------|--------|
| `src/saas_lead_agent/state.py` | **edit** — add `fit_score`, `email_subject`, `email_body` |
| `src/saas_lead_agent/agents/dossier_writer.py` | **new** |
| `src/saas_lead_agent/graph.py` | **edit** — add node + rewire fan-in → dossier_writer → END |
| `src/saas_lead_agent/api/schemas.py` | **edit** — add fields to `QualifyResponse` |
| `src/saas_lead_agent/api/routes.py` | **edit** — pass new fields through |
| `tests/test_state.py` | **edit** — update initial-state test for new fields |
| `tests/test_agents.py` | **edit** — add 6 dossier_writer tests |
| `tests/test_graph.py` | **edit** — update 4 topology tests + state-flow tests |
| `tests/test_api.py` | **edit** — update response fixture + add fit_score/email_draft assertions |

## Step-by-step

### Step A — LeadState: add fit_score, email_subject, email_body

In `state.py`, add three scalar fields (no reducer — plain overwrite):

```python
fit_score: int | None
email_subject: str | None
email_body: str | None
```

Update `tests/test_state.py`: add `fit_score: None, email_subject: None,
email_body: None` to the initial-state fixture; add one test confirming scalar
overwrite for the new fields.

**Verification:**
```
uv run ruff check src/saas_lead_agent/state.py tests/test_state.py
uv run mypy src/saas_lead_agent/state.py
uv run pytest -x tests/test_state.py -q
```

---

### Step B — dossier_writer.py (new)

**Model:** `ChatOpenAI(model="gpt-4o-mini")` — per CLAUDE.md (GPT-4o-mini for
email writer only).

**Pattern:** direct `model.ainvoke([SystemMessage(prompt), HumanMessage(context)])`.
No `create_agent`, no tools, no singleton needed — the model is instantiated
lazily in the node function (or as a module-level singleton following the same
`_get_*` pattern for consistency).

**System prompt:**
```
You are an expert B2B SaaS sales development representative.

Given a company research dossier, do two things:
1. Score the company as a sales prospect on a scale of 1–10 (fit_score),
   where 10 = ideal customer profile match.
2. Write a concise, personalised cold outreach email (3–4 sentences) to the
   primary contact, referencing specific signals from the dossier.

Return a single JSON object — no markdown, no explanation, only the JSON:

{
  "fit_score":    integer (1–10),
  "fit_rationale": string,
  "email_subject": string,
  "email_body":    string
}

Use null for fit_rationale if unknown. Return ONLY the JSON object.
```

**Node `dossier_writer(state)`:**
- Builds a human message from state fields:
  ```
  Company profile: {json.dumps(state["company_profile"])}
  Contact: {json.dumps(state["contact"])}
  Signals: {json.dumps(state["signals"])}
  ```
- Gracefully handles `None` fields (any of the three may be absent if an
  upstream node failed — use `state.get(field)` with `None` fallback,
  serialize to `"null"` in the prompt).
- Calls `await model.ainvoke([system_msg, human_msg])` — returns a single
  `AIMessage`.
- Parses the response with `_extract_json` from `utils.py`.
- Returns `{"fit_score": int, "email_subject": str, "email_body": str}` on success.
- Returns `{"errors": [...]}` on parse error or exception — does not crash.
- `fit_score` is clamped to `[1, 10]` after parsing (guard against model
  returning 0 or 11).

**Lazy singleton:**
```python
_model: ChatOpenAI | None = None

def _get_model() -> ChatOpenAI:
    global _model
    if _model is None:
        _model = ChatOpenAI(model="gpt-4o-mini")
    return _model
```

**Verification:**
```
uv run ruff check src/saas_lead_agent/agents/dossier_writer.py
uv run mypy src/saas_lead_agent/agents/dossier_writer.py
```

---

### Step C — graph.py: wire dossier_writer

Change the fan-in target from `END` to `dossier_writer`, then add
`dossier_writer → END`:

```python
# Before:
graph.add_edge(_SUBAGENT_NODES, END)

# After:
graph.add_edge(_SUBAGENT_NODES, "dossier_writer")
graph.add_edge("dossier_writer", END)
```

Also add `from saas_lead_agent.agents.dossier_writer import dossier_writer`
and `graph.add_node("dossier_writer", dossier_writer)`.

Update the docstring topology comment.

**Verification:**
```
uv run ruff check src/saas_lead_agent/graph.py
uv run mypy src/saas_lead_agent/graph.py
```

---

### Step D — API: schemas.py + routes.py

`schemas.py`: add to `QualifyResponse`:
```python
fit_score: int | None = None
email_subject: str | None = None
email_body: str | None = None
```

`routes.py`: pass through from graph result:
```python
return QualifyResponse(
    ...
    fit_score=result.get("fit_score"),
    email_subject=result.get("email_subject"),
    email_body=result.get("email_body"),
)
```

**Verification:**
```
uv run ruff check src/saas_lead_agent/api/
uv run mypy src/saas_lead_agent/api/
```

---

### Step E — Tests

**tests/test_agents.py** — add 6 dossier_writer tests.

Patching strategy: patch `saas_lead_agent.agents.dossier_writer._get_model`
to return a `MagicMock` whose `ainvoke` is an `AsyncMock` returning a fake
`AIMessage`.

Tests:
1. `test_dossier_writer_happy_path` — valid JSON response, fit_score,
   email_subject, email_body populated; fit_score clamped to [1,10]
2. `test_dossier_writer_separate_subject_and_body` — email_subject and
   email_body are distinct keys in the result (not concatenated)
3. `test_dossier_writer_handles_none_upstream_fields` — all three state
   fields `None`, still calls model and returns result
4. `test_dossier_writer_json_parse_error` — non-JSON response → errors
5. `test_dossier_writer_agent_exception` — `ainvoke` raises → errors
6. `test_dossier_writer_clamps_fit_score` — model returns 0 → clamped to 1;
   model returns 11 → clamped to 10

**tests/test_graph.py** — update 4 topology tests + 4 state-flow tests.

Topology tests that break:
- `test_graph_has_expected_nodes` — add `"dossier_writer"`
- `test_graph_subagents_fan_in_to_end` — rename to
  `test_graph_subagents_fan_in_to_dossier_writer`; check `__end__` source is
  now `dossier_writer`, not the three subagents
- add `test_graph_dossier_writer_goes_to_end`

State-flow tests: add `"saas_lead_agent.graph.dossier_writer"` to the patch
block with `return_value={"fit_score": 8, "email_subject": "Hi", "email_body":
"..."}`; assert `result["fit_score"] == 8`, `result["email_subject"]` in happy
path test.

**tests/test_api.py** — add `fit_score`, `email_subject`, `email_body` to
`_GRAPH_RESULT` fixture; add assertions in `test_qualify_happy_path`.

**Verification:**
```
uv run pytest -x tests/test_state.py tests/test_agents.py tests/test_graph.py tests/test_api.py -q
```

---

### Step F — Full sweep

```
uv run ruff check src/ tests/
uv run mypy src/
uv run pytest -x --ff
```

## Risks & unknowns

1. **`model.ainvoke` return type.** `ChatOpenAI.ainvoke([...])` returns a
   `BaseMessage` (concretely `AIMessage`). Access content via `.content` —
   same as the create_agent pattern. No new parsing logic needed.

2. **`fit_score` type coercion.** GPT-4o-mini may return `fit_score` as a
   float (`8.0`) or string (`"8"`). After `_extract_json`, cast with
   `int(result["fit_score"])` and then clamp.

3. **Graph topology tests use `graph.builder._all_edges`** (private attr,
   verified working in Phase 1). The new topology adds one more edge; the
   existing test pattern handles it cleanly.

4. **`test_graph_subagents_fan_in_to_end` name is now wrong** after the
   topology change. Rename it rather than patching the assertion — misleading
   test names cause confusion later.

5. **`QualifyResponse` is a Pydantic model** — adding nullable fields with
   defaults is backwards-compatible; existing `test_qualify_*` tests that
   don't assert on the new fields will continue to pass unchanged.

## ADR to log
**ADR-004** (per master plan): GPT-4o-mini for dossier_writer only; all
other agents use Gemini 2.5 Flash-Lite. Log after this step completes.
