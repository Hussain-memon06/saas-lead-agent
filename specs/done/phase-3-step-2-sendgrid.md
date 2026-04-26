# Phase 3 Step 2 — SendGrid email delivery

## Goal
Replace the Phase 2 `send_email` stub with real outbound delivery via SendGrid.
Capture `message_id` and `sent_at` so downstream tracking and bounce-handling
have a delivery handle.  Fulfills ADR-006.

## Status: COMPLETE

---

## Files changed

| File | Change |
|------|--------|
| `pyproject.toml` | Added `sendgrid>=6.11,<7.0` |
| `src/saas_lead_agent/email/__init__.py` | New (empty package marker) |
| `src/saas_lead_agent/email/sendgrid_client.py` | New: `async def send_email_via_sendgrid(to, subject, body)` |
| `src/saas_lead_agent/agents/send_email.py` | Rewrite: real delivery branch + 4 fallback paths |
| `src/saas_lead_agent/state.py` | Added `message_id: str \| None`, `sent_at: str \| None` |
| `src/saas_lead_agent/api/schemas.py` | Exposed `message_id`, `sent_at` in `QualifyResponse` + `ApproveResponse` |
| `src/saas_lead_agent/api/routes.py` | Initial state populates new fields; responses surface them |
| `tests/test_sendgrid.py` | New: 8 client tests (mocked SDK) |
| `tests/test_agents.py` | Added 6 `send_email` node tests |
| `tests/test_state.py` | Added `_BASE` fields + delivery overwrite test |
| `tests/test_api.py` | Added defaults assertions for new response fields |
| `tests/conftest.py` | Documented `SENDGRID_API_KEY` must stay unset for tests |
| `.env.example` | Documented `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL` |

---

## Behavior matrix (`send_email` node)

| `email_approved` | `contact["email"]` | `SENDGRID_API_KEY` | `send_result` | `message_id` |
|------------------|---------------------|---------------------|----------------|----------------|
| `None` or `False` | any                 | any                 | `"rejected"`   | not set        |
| `True`           | missing / `None`    | any                 | `"no_contact"` | not set        |
| `True`           | present             | unset               | `"sent"` (stub) | not set        |
| `True`           | present             | set, SDK 2xx        | `"sent"`       | from `X-Message-Id` |
| `True`           | present             | set, SDK error/4xx/5xx | `"failed"`  | not set; error appended |

The stub-when-no-key branch preserves the Phase 2 contract for dev/test
environments without a SendGrid account.  Default-deny semantics are
unchanged (ADR-006).

---

## Architecture notes

### Async wrapping of a sync SDK
The official `sendgrid` Python SDK is sync (built on `python-http-client`).
`send_email_via_sendgrid` runs the SDK call inside `asyncio.to_thread` so the
event loop is not blocked during the HTTP round-trip.  No new event-loop work
or HTTP client is introduced for this single integration.

### `email/` vs `tools/`
Placed at `src/saas_lead_agent/email/`, not `src/saas_lead_agent/tools/`.
Rationale: `tools/` holds `@tool`-decorated functions invoked by LLM agents.
SendGrid is called directly from the `send_email` graph node, not via an
LLM ReAct loop, so it does not belong in `tools/`.

### `message_id` extraction
SendGrid returns the per-message ID in the `X-Message-Id` response header.
The wrapper reads it via `response.headers.get("X-Message-Id")` with a
defensive fallback to `None` if the header object lacks `.get`.  Tests
exercise both the present and missing paths.

---

## Running locally

### 1. Set env vars

```bash
# .env
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxx
SENDGRID_FROM_EMAIL=sales@yourdomain.com
```

The SendGrid free tier includes 100 emails/day — enough for end-to-end smoke
testing.  The `SENDGRID_FROM_EMAIL` must be a verified sender (Single Sender
Verification or domain authentication) or SendGrid will reject the request
with 403.

### 2. Smoke test

```bash
uv run uvicorn src.saas_lead_agent.api.main:app --reload --port 8080

# Trigger the pipeline against a test inbox
curl -s -X POST http://localhost:8080/api/qualify \
    -H 'Content-Type: application/json' \
    -d '{"url":"https://stripe.com"}'

# Approve the drafted email — SendGrid actually delivers
curl -s -X POST http://localhost:8080/api/leads/lead:stripe.com/approve | jq .

# Expected response:
# {
#   "thread_id": "lead:stripe.com",
#   "email_approved": true,
#   "send_result": "sent",
#   "message_id": "qhEHGXgARFucF8hEv7HtCw.filterdrecv-...",
#   "sent_at": "2026-04-25T12:34:56.789012+00:00",
#   "interrupted": false,
#   "errors": []
# }
```

---

## Verification checklist

- [x] `uv run ruff check` — clean
- [x] `uv run mypy src/` — clean (24 source files)
- [x] `uv run pytest -x --ff` — 133 passed, 5 skipped
- [ ] Manual smoke test against a real test inbox (requires SendGrid account)

---

## Risks & notes

- **Verified sender required.** SendGrid rejects unverified `from_email`
  addresses with 403.  Document this in onboarding before production rollout.
- **PII handling.** Real prospect emails now leave the system.  CLAUDE.md
  forbids sending real client PII through the Gemini free tier — verified:
  `dossier_writer` (the only node that touches the drafted body) uses
  `gpt-4o-mini` per ADR-004, not Gemini.
- **No retry.** A SendGrid 5xx surfaces as `send_result="failed"`; there is
  no automatic retry yet.  Bounce/suppression webhook handling is deferred
  (see TODO.md Phase 3).
- **Rate limiting.** Free tier is 100/day; production needs a paid plan and
  per-domain rate limiting (TODO.md "Quality / safety" section).

---

## ADR

ADR-007 to be logged in `decisions.md` after approval:
> SendGrid as primary email provider for Phase 3.  SDK is sync; wrap in
> `asyncio.to_thread`.  Stub fallback (no key → success) preserves Phase 2
> contract for tests.
