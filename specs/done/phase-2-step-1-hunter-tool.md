# Phase 2 Step 1: tools/hunter.py

## Goal
Implement a `@tool` that calls the Hunter.io Domain Search API and returns
the top decision-maker contact for a given domain. Prerequisite for the real
`contact_finder` agent (Step 2).

## API shape verified
- Endpoint: `GET https://api.hunter.io/v2/domain-search`
- Auth: `api_key` query param
- Key params: `domain`, `limit`, `type=personal`
- Response: `data.emails[]` — each record has `value`, `first_name`,
  `last_name`, `position`, `seniority`, `department`, `confidence`, `linkedin`
- Errors: `errors[].code` + HTTP 4xx/429

## Files changed
- `src/saas_lead_agent/tools/hunter.py` — new `@tool` wrapping Domain Search
- `tests/test_hunter.py` — 12 tests (pure `_pick_best` + full tool)
- `tests/conftest.py` — add `HUNTER_API_KEY=test-stub` default
- `.env.example` — document `HUNTER_API_KEY`

## Step-by-step
1. Verify Hunter.io API shape via Context7 subagent ✓
2. Implement `hunter.py` with `_pick_best` selection logic ✓
3. Write `test_hunter.py` (12 tests, all mocked) ✓
4. Fix ruff import sort in test file ✓
5. Add `HUNTER_API_KEY` stub to `conftest.py` ✓
6. Add key to `.env.example` ✓

## Verification output
```
ruff check src/ tests/   → All checks passed
mypy src/.../hunter.py   → Success: no issues found in 1 source file
pytest tests/test_hunter.py  → 12 passed in 0.44s
pytest -x --ff           → 80 passed in 1.99s
```

## Commit
`c4b7235` feat(tools): add Hunter.io Domain Search tool with decision-maker ranking

## Deviations from master plan
None. Used Domain Search (not Email Finder) as planned — contact_finder
receives `state["domain"]`, not a person name.

## Status
DONE — merged to feat/hunter-tool, ready for PR to main.
