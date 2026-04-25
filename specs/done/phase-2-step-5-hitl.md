# Phase 2 Step 5: Human-in-the-Loop (interrupt + resume)

## Goal
Pause the graph AFTER `dossier_writer` produces an email draft, BEFORE any
send action, so a human can approve or reject. Add `/approve` and `/reject`
HTTP endpoints that resume the graph with `Command(resume=True|False)`.

## Context7 gate — API verified
- `from langgraph.types import interrupt, Command`
- `interrupt(value: Any) -> Any` — raises `GraphInterrupt`; value surfaces to client
- `Command(*, resume=None, update=None, goto=(), graph=None)` — resume input
- **Critical**: "graph resumes from the start of the node, **re-executing** all logic"
- Checkpointer required (we have `InMemorySaver` via `build_graph_with_memory`)
- Resume via: `graph.ainvoke(Command(resume=...), config=...)`

## Topology change

Current:
```
[researcher, contact, signal] → dossier_writer → END
```

New:
```
[researcher, contact, signal] → dossier_writer → await_approval → send_email → END
                                                      (interrupt)   (or skip if rejected)
```

Why split `dossier_writer` / `await_approval` / `send_email` into **three nodes**:

The docstring says "graph resumes from the start of the node, re-executing all logic".
If `interrupt()` lives inside `dossier_writer`, the GPT-4o-mini call runs twice
(once before the interrupt, once on resume) — wasted tokens and latency.
Splitting it means the LLM call stays in `dossier_writer` (runs once), and
`await_approval` is a cheap node whose only work is calling `interrupt()` and
writing the decision to state.

`send_email` is a **stub** in Phase 2 (Phase 3 will wire real SMTP/API delivery).
Per ADR-006 (master plan): Phase 2 just marks `send_result = "sent"` or
`send_result = "rejected"` based on the approval decision.

## Files to change

| File | Action |
|------|--------|
| `src/saas_lead_agent/state.py` | **edit** — add `email_approved: bool \| None`, `send_result: str \| None` |
| `src/saas_lead_agent/agents/dossier_writer.py` | **edit** — keep as-is (LLM call only) |
| `src/saas_lead_agent/agents/await_approval.py` | **new** — the `interrupt()` node |
| `src/saas_lead_agent/agents/send_email.py` | **new** — stub that writes send_result |
| `src/saas_lead_agent/graph.py` | **edit** — add two nodes + conditional edge from await_approval |
| `src/saas_lead_agent/api/schemas.py` | **edit** — add `email_approved`, `send_result` to `QualifyResponse`; add `ApproveResponse` |
| `src/saas_lead_agent/api/routes.py` | **edit** — add `/approve` and `/reject` endpoints |
| `tests/test_state.py` | **edit** — fixture covers new fields |
| `tests/test_agents.py` | **edit** — add 4 tests (await_approval + send_email) |
| `tests/test_graph.py` | **edit** — topology tests + interrupt/resume integration |
| `tests/test_api.py` | **edit** — add 4 tests for approve/reject endpoints |

## Step-by-step

### Step A — LeadState fields

Add to `state.py`:
```python
email_approved: bool | None
send_result: str | None  # "sent" | "rejected" | None
```

Update `tests/test_state.py` `_BASE` fixture to include both.

**Verification:**
```
uv run ruff check src/saas_lead_agent/state.py tests/test_state.py
uv run mypy src/saas_lead_agent/state.py
uv run pytest -x tests/test_state.py -q
```

---

### Step B — await_approval node (new)

`src/saas_lead_agent/agents/await_approval.py`:

```python
from langgraph.types import interrupt
from saas_lead_agent.state import LeadState

async def await_approval(state: LeadState) -> dict[str, Any]:
    """Pause until a human approves or rejects the drafted email.

    The client resumes via graph.ainvoke(Command(resume=<bool>), ...).
    Resume value is interpreted as:
      - True  → approved; downstream send_email proceeds
      - False → rejected; downstream send_email marks as rejected
    """
    decision = interrupt({
        "type": "email_approval",
        "email_subject": state.get("email_subject"),
        "email_body": state.get("email_body"),
        "fit_score": state.get("fit_score"),
    })
    return {"email_approved": bool(decision)}
```

The `interrupt(value)` payload is what the client sees. We surface the email
draft + fit_score so the UI can display it at the pause point.

**Verification:**
```
uv run ruff check src/saas_lead_agent/agents/await_approval.py
uv run mypy src/saas_lead_agent/agents/await_approval.py
```

---

### Step C — send_email stub (new)

`src/saas_lead_agent/agents/send_email.py`:

```python
async def send_email(state: LeadState) -> dict[str, Any]:
    """Phase 2 stub — marks the outcome but does not actually send.

    Phase 3 will replace with real SMTP or provider API (SES/SendGrid).
    """
    if state.get("email_approved"):
        return {"send_result": "sent"}
    return {"send_result": "rejected"}
```

**Verification:**
```
uv run ruff check src/saas_lead_agent/agents/send_email.py
uv run mypy src/saas_lead_agent/agents/send_email.py
```

---

### Step D — Graph wiring

Update `graph.py`:
```python
# new imports:
from saas_lead_agent.agents.await_approval import await_approval
from saas_lead_agent.agents.send_email import send_email

# new nodes:
graph.add_node("await_approval", await_approval)
graph.add_node("send_email", send_email)

# replace the old "dossier_writer → END" edge with:
graph.add_edge("dossier_writer", "await_approval")
graph.add_edge("await_approval", "send_email")
graph.add_edge("send_email", END)
```

No conditional edge needed — `send_email` inspects `state["email_approved"]`
and branches its output. The graph always runs to END; the resume decision
just changes what `send_result` says.

**Verification:**
```
uv run ruff check src/saas_lead_agent/graph.py
uv run mypy src/saas_lead_agent/graph.py
```

---

### Step E — API: approve/reject endpoints

`schemas.py` — add to `QualifyResponse`:
```python
email_approved: bool | None = None
send_result: str | None = None
interrupted: bool = False  # true when the graph paused at await_approval
```

New response model:
```python
class ApproveResponse(BaseModel):
    thread_id: str
    send_result: str | None = None
    email_approved: bool | None = None
    errors: list[str] = []
```

`routes.py` — `POST /api/qualify` needs to detect interrupts. After `ainvoke`,
inspect the graph state to see if it's paused (via
`_graph.aget_state(config)` — returns a snapshot with `.next` tuple listing
pending nodes; empty `.next` means done). If interrupted, set
`interrupted=True` in the response.

Two new endpoints:

```python
@router.post("/api/leads/{thread_id}/approve", response_model=ApproveResponse)
async def approve(thread_id: str) -> ApproveResponse:
    config: RunnableConfig = cast(RunnableConfig, {"configurable": {"thread_id": thread_id}})
    try:
        result = await _graph.ainvoke(Command(resume=True), config=config)
    except Exception as exc:
        raise HTTPException(500, f"Resume failed: {exc}")
    return ApproveResponse(
        thread_id=thread_id,
        send_result=result.get("send_result"),
        email_approved=result.get("email_approved"),
        errors=result.get("errors", []),
    )

@router.post("/api/leads/{thread_id}/reject", response_model=ApproveResponse)
async def reject(thread_id: str) -> ApproveResponse:
    # identical but Command(resume=False)
    ...
```

**Verification:**
```
uv run ruff check src/saas_lead_agent/api/
uv run mypy src/saas_lead_agent/api/
```

---

### Step F — Tests

**tests/test_agents.py** — 4 new tests:

1. `test_await_approval_raises_interrupt` — calling `await_approval` outside a
   compiled graph raises `GraphInterrupt` with the draft payload
2. `test_send_email_marks_sent_when_approved` — `email_approved=True` →
   `send_result == "sent"`
3. `test_send_email_marks_rejected_when_not_approved` — `email_approved=False` →
   `send_result == "rejected"`
4. `test_send_email_marks_rejected_when_approval_absent` — `email_approved=None` →
   `send_result == "rejected"` (default deny)

**tests/test_graph.py** — update topology + add integration:

- `test_graph_has_expected_nodes` — add `await_approval`, `send_email`
- `test_graph_dossier_writer_goes_to_end` → rename to
  `test_graph_dossier_writer_goes_to_await_approval`; update to assert new chain
- add `test_graph_await_approval_to_send_email`
- add `test_graph_send_email_to_end`
- add `test_graph_interrupts_before_send_email` — full run; assert the graph
  pauses after dossier_writer; state inspected via `aget_state`; then resume
  with `Command(resume=True)` and assert `send_result == "sent"`

**tests/test_api.py** — 4 new tests:

1. `test_qualify_interrupts_and_returns_interrupted_flag` — mock `_graph.ainvoke`
   to return a partial state (pre-send_email); mock `aget_state` to show next=await_approval;
   assert `body["interrupted"] is True`
2. `test_approve_resumes_graph_with_true` — mock `_graph.ainvoke` called with
   `Command(resume=True)`; returns `send_result="sent"`; assert response
3. `test_reject_resumes_graph_with_false` — symmetric
4. `test_approve_500_on_graph_failure` — ainvoke raises → 500

**Verification:**
```
uv run pytest -x tests/test_state.py tests/test_agents.py tests/test_graph.py tests/test_api.py -q
```

---

### Step G — Full sweep

```
uv run ruff check src/ tests/
uv run mypy src/
uv run pytest -x --ff
```

## Risks & unknowns

1. **Re-execution semantics on resume.** Per Context7 docs, the resumed node
   re-runs from its start. `await_approval` re-runs, but it only calls
   `interrupt()` — on resume, the interrupt returns the Command value instead
   of raising. No LLM re-call, no side effects.

2. **`CLAUDE.md` says `durability="sync"` around interrupts.** The default is
   `async`. Need to pass `durability="sync"` to `ainvoke` for the initial call
   that may interrupt, and for the resume call. This is a Phase 2 requirement;
   flagging for the ACT phase so I don't forget.

3. **Interrupt detection in `POST /api/qualify`.** `ainvoke` with a checkpointer
   does NOT raise when the graph interrupts — it returns the current state
   (without the fields the interrupted node would have written). The route
   must call `_graph.aget_state(config)` after `ainvoke` to check
   `snapshot.next`: if non-empty, the graph is paused. Need to verify
   `aget_state` is async (it should be — `a` prefix) via direct inspection
   before writing.

4. **Mocking `_graph.aget_state` in tests.** Same pattern as mocking
   `ainvoke` — `mock_graph.aget_state = AsyncMock(return_value=snapshot_mock)`.
   The snapshot needs `.next` attribute (tuple of pending node names).

5. **Default-deny semantics.** If `email_approved` is `None` (somehow the
   interrupt was bypassed or state is malformed), `send_email` marks it
   `"rejected"`. Safer than accidentally sending an unapproved email.

6. **ADR to log.** ADR-006: `send_email` is a stub in Phase 2; real delivery
   (SES/SendGrid/SMTP) is Phase 3. Log after this step completes.

## Verification before ACT

Before starting Step A, I'll do one more quick Context7 check:
- `CompiledStateGraph.aget_state` signature and return shape (`.next` attribute)
- Whether `durability="sync"` on `ainvoke` is still the current flag name

I'll report findings then proceed.
