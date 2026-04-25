# Phase 2 Step 3: Real signal_detector agent

## Goal
Replace the Phase 1 stub in `agents/signal_detector.py` with a real
`create_agent` ReAct node that uses `web_search` (Tavily) to find buying
signals for a company, then uses Gemini to classify and structure them.

Returns `{"signals": list[dict]}` where each signal has:
`{signal_type, date, source, details}`

Signal types: `funding` | `hiring` | `product` | `leadership` | `other`

## Key difference from company_researcher / contact_finder

Those agents parse a JSON **object** from the final AIMessage.
`signal_detector` must parse a JSON **array**.

`_extract_json` in `utils.py` raises `ValueError` on non-dict input — it
cannot be reused as-is. A new `_extract_json_list` function is needed in
`utils.py` with the same fence-stripping logic but validating a `list`
instead of a `dict`.

## Files to change

| File | Action |
|------|--------|
| `src/saas_lead_agent/utils.py` | **edit** — add `_extract_json_list` |
| `src/saas_lead_agent/agents/signal_detector.py` | **rewrite** — real agent |
| `tests/test_agents.py` | **edit** — add 7 signal_detector tests |

No other files change. Graph topology, state, and API schemas are unchanged —
`signals: list[dict[str, Any]] | None` is already in `LeadState` and
`QualifyResponse`.

## Step-by-step

### Step A — Add `_extract_json_list` to utils.py

Add alongside `_extract_json`:

```python
def _extract_json_list(content: str) -> list[dict[str, Any]]:
    """Extract a JSON array of dicts from an LLM response string.

    Same fence-stripping logic as _extract_json.

    Raises:
        json.JSONDecodeError: If the text cannot be parsed as JSON.
        ValueError: If the parsed value is not a list, or any element
            is not a dict.
    """
```

Validation: parsed value must be a `list`; every element must be a `dict`.
Empty list `[]` is valid (no signals found).

Also add a test for `_extract_json_list` in `tests/test_agents.py` (plain array,
fenced array, empty array, raises on dict, raises on list-of-non-dicts).

**Verification:**
```
uv run ruff check src/saas_lead_agent/utils.py tests/test_agents.py
uv run mypy src/saas_lead_agent/utils.py
uv run pytest -x tests/test_agents.py -q
```

---

### Step B — Rewrite signal_detector.py

Implement following the `company_researcher` / `contact_finder` pattern:

**Agent:**
- Model: `ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite")`
- Tools: `[web_search]`
- `create_agent(model, tools=[web_search], system_prompt=..., name="signal_detector")`

**System prompt:**
```
You are a B2B sales intelligence analyst.

Given a company name and domain, search for recent buying signals using
web_search. Look for: funding rounds, hiring spikes (job postings surge),
product launches, leadership changes (new CTO/VP/CEO).

Run up to 4 searches targeting different signal types. Then return a JSON
array — no markdown, no explanation, only the JSON array — where each element
has these exact fields:

[
  {
    "signal_type": "funding"|"hiring"|"product"|"leadership"|"other",
    "date":        string | null,
    "source":      string | null,
    "details":     string
  },
  ...
]

If no signals are found, return an empty array [].
Return ONLY the JSON array.
```

**Node `signal_detector(state)`:**
- Reads `state["domain"]` and `state.get("company_profile")` — extracts
  `company_name = (company_profile or {}).get("name") or domain` so searches
  are more targeted when a profile is available.
- Prompt: `f"Find buying signals for company '{company_name}' (domain: {domain})"`
- On success: parses last AIMessage with `_extract_json_list`, returns
  `{"signals": list}`
- On `JSONDecodeError` / `ValueError`: returns `{"errors": [...]}`
- On agent exception: returns `{"errors": [...]}`
- On empty messages: returns `{"errors": [...]}`
- Empty list `[]` is a valid success result (no signals found — not an error).

**Lazy singleton:** same pattern as other agents —
`_signal_detector_agent: Any = None` + `_get_signal_detector_agent()`.

**Verification:**
```
uv run ruff check src/saas_lead_agent/agents/signal_detector.py
uv run mypy src/saas_lead_agent/agents/signal_detector.py
uv run pytest -x tests/test_agents.py -q
```

---

### Step C — Add 7 signal_detector tests to test_agents.py

Following the same `_make_agent_mock` + `patch("...._get_signal_detector_agent")`
pattern used for contact_finder.

Tests:
1. `test_signal_detector_happy_path` — agent returns valid JSON array, signals populated
2. `test_signal_detector_empty_array` — `[]` returned, `signals == []`, no errors
3. `test_signal_detector_markdown_response` — array inside ` ```json ` fence
4. `test_signal_detector_json_parse_error` — plain text response → errors
5. `test_signal_detector_agent_exception` — ainvoke raises → errors
6. `test_signal_detector_empty_messages` — empty messages list → errors
7. `test_signal_detector_uses_company_name_when_available` — when
   `company_profile` is populated, company name appears in the prompt

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

All 87 existing tests must stay green; new tests bring the total to ~100.

## Risks & unknowns

1. **Gemini returning a dict instead of a list.** If the model wraps the array
   in `{"signals": [...]}`, `_extract_json_list` will raise `ValueError`
   ("Expected JSON array"). The node catches this and returns `{"errors": [...]}`.
   The system prompt explicitly says "Return ONLY the JSON array" to prevent this.

2. **`company_profile` may be `None` at node execution time.** The three
   subagents run in parallel after `orchestrator` — `company_profile` is not
   yet populated when `signal_detector` starts. The node falls back to
   domain-only search gracefully. This is by design.

3. **Tavily quota.** Each `signal_detector` run makes up to 4 `web_search`
   calls. In production this is fine; in tests all calls are mocked so no
   quota is consumed.

4. **Date parsing.** The LLM returns `date` as a free-form string or null.
   We do not parse or validate it — the field is `string | null` in the
   schema. Normalisation (if needed) is a Phase 3 concern.

## ADR needed
None — no new architectural decisions. `_extract_json_list` is a mechanical
extension of the existing `utils.py` pattern.
