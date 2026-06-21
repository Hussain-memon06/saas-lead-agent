# Phase 6 Auth, Authorization, And Compliance Plan

> Compatibility copy: the completed canonical record is under `specs/done/`.
> This path is retained because the local Windows filesystem denied removal.

## Status

Complete for the current roadmap milestone. This record preserves the
implementation order and remaining operational constraints.

Implemented so far:

- `src/saas_lead_agent/schemas/auth.py` defines the no-dependency auth context
  and protected-route policy contracts.
- The current API route surface is represented as an anonymous-demo-compatible
  policy matrix.
- User-owned resource policy contracts now cover lead runs, sources, contacts,
  company signals, score breakdowns, outreach drafts, decisions, delivery
  events, and retrieval context.
- Compliance configuration contracts now document the environment CORS matrix,
  request-size limits, critical secrets, redaction rules, and audit events.
- SSRF hardening contracts now document redirect revalidation, DNS rebinding
  checks, post-resolution validation, private/link-local ranges, localhost
  aliases, and dangerous ports.
- Clerk is selected in `specs/in-progress/phase-6-auth-provider-session-decision.md`.
- Request-level Clerk JWT verification and owner-scoped access now protect the
  existing API route surface in production.
- New authenticated qualification runs now persist `user_id` on run snapshots
  and normalized lead records without exposing it in public API responses.
- Pure persistence access helpers now resolve snapshot ownership and filter
  snapshot/artifact aggregate lists under the planned access policy; routes do
  not use them yet.
- `GET /api/leads` now enforces owner-aware listing at the repository boundary
  before pagination. Other lead routes remain unenforced.
- Explicit non-production bypass remains available for local development only.
- Request and ICP payload limits are enforced.
- Per-process authenticated write limits protect qualification and decisions.
- Production startup validates critical auth/CORS/OpenAI configuration.
- Scraper redirects are bounded and each hop uses public-DNS validation plus
  validated-IP connection pinning with the original Host and TLS SNI.

## Historical Non-Goals For The Planning Milestone

- No new auth dependency.
- No frontend login UI.
- No session/cookie implementation.
- No production CORS switch.
- No rate-limit middleware.
- No deeper SSRF resolver implementation.
- No database migration tooling change.

## Residual Constraints

- Legacy unowned demo records are isolated rather than automatically backfilled.
- Rate limits are process-local; multi-replica deployments need a distributed
  limiter in Phase 8.
- Persisted vector retrieval does not exist yet, so tenant-scoped vector
  filtering remains a future retrieval concern.
- Run events and metadata use explicit allowlists and do not expose raw user
  identity, credentials, contact email, outreach bodies, or source text.
- SendGrid remains human-in-the-loop through approval and fails closed unless
  explicit stub mode or real provider success is available.

## Phase 6 Milestone Order

### Milestone 6.1: Auth Boundary Design

Goal: decide the auth/session shape before touching runtime behavior.

Scope:

- choose auth strategy candidates without adding dependencies
- define user identity fields that app-owned records need
- define anonymous/demo-mode behavior during migration
- define API routes that will eventually require auth
- document compatibility expectations for the current deployed prototype

Deliverables:

- auth boundary decision record
- user identity contract draft
- protected-route matrix
- open questions for provider choice

Current implementation status: Clerk middleware protects the existing Next.js
routes, frontend API calls send Clerk tokens, and FastAPI verifies tokens and
enforces lead ownership.

### Milestone 6.2: User-Owned Access Model

Goal: make data ownership explicit before enforcing access.

Scope:

- define user-owned lead/run/source/contact/draft/decision/retrieval boundaries
- define repository access-check points
- define tenant-safe retrieval metadata requirements
- document how existing unauthenticated records are treated

Deliverables:

- access-control matrix
- repository enforcement plan
- migration/backfill notes for existing records

Current implementation status: the access-control matrix exists as pure
Pydantic contracts. Existing unauthenticated records are treated as legacy
anonymous-demo resources until an auth provider/session strategy is approved.
Repository enforcement and backfill remain deferred.

### Milestone 6.3: Critical Compliance Configuration

Goal: make production safety settings explicit before changing defaults.

Scope:

- production CORS allowlist design
- request size limit plan
- startup fail-fast plan for critical secrets
- trace/log redaction rules
- audit-log event categories

Deliverables:

- config matrix for development/staging/production
- redaction policy
- audit event list

Current implementation status: the compliance configuration matrix is enforced
through production CORS/startup validation, request limits, write throttling,
sanitized metadata, and audit-style run events.

### Milestone 6.4: SSRF Hardening Design

Goal: design deeper SSRF protections before changing scraper behavior.

Scope:

- redirects
- DNS rebinding
- private IP ranges
- link-local ranges
- localhost aliases
- dangerous ports
- post-resolution validation

Deliverables:

- URL fetch safety policy
- blocked-host test matrix
- implementation plan for scraper integration

Current implementation status: scraper integration enforces bounded manual
redirects, public resolved addresses, and connections pinned to the validated
address with the original HTTP Host and TLS SNI.

## Recommended First Implementation After Planning

Start with a no-dependency user identity and route-protection design slice:

- add typed auth context models only if needed
- keep current unauthenticated runtime behavior unchanged
- do not enforce auth until provider/session strategy is approved
- add targeted tests for any pure policy helpers introduced

Status: complete for the current Phase 6 milestone. Authentication, ownership,
production CORS/startup validation, request limits, rate limiting, metadata
redaction boundaries, audit-style events, and runtime SSRF controls are
implemented.

## Targeted Verification

For this planning milestone, no verification command is required because only
Markdown changes are expected.

When implementation begins, use targeted checks only, for example:

```bash
uv run python -m pytest tests/test_auth_context.py -q
uv run python -m pytest tests/test_access_policy.py -q
uv run python -m pytest tests/test_auth_policy.py -q
uv run python -m pytest tests/test_compliance_policy.py -q
uv run python -m pytest tests/test_ssrf_policy.py -q
```

Full verification remains release-only unless explicitly requested.
