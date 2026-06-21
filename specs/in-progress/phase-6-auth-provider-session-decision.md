# Phase 6 Auth Provider And Session Decision

## Status

Decision status: Clerk selected and implemented for the existing app routes.

## Context

The application is currently a deployed prototype with unauthenticated API
routes. Phase 6 already has no-dependency contracts for:

- auth context
- protected route policies
- user-owned access policies
- compliance configuration
- SSRF hardening policy

The next runtime change should not lock the project into a provider before the
deployment and user model are clear.

## Decision

Use Clerk for Next.js authentication and verify Clerk session JWTs in FastAPI.

Production behavior:

- Clerk middleware protects `/`, `/settings`, and `/leads/*`.
- Existing frontend API calls send Clerk bearer tokens.
- FastAPI verifies JWT signature, issuer, expiry, subject, optional audience,
  and optional authorized party.
- Missing or invalid production credentials return HTTP 401.
- Plain identity headers are accepted only when explicit non-production bypass
  is enabled.

Implemented so far:

- `src/saas_lead_agent/api/auth.py` verifies Clerk bearer tokens and resolves
  `AuthContext`.
- Anonymous-demo is available only through explicit non-production bypass.
- Processing metadata and run-event metadata include sanitized auth mode and
  user-presence flags, not raw user identifiers.
- Existing lead list/detail/event/approve/reject API behavior is owner-scoped.

## Candidate Provider Criteria

When provider selection is approved, choose based on:

- Vercel/Next.js frontend compatibility
- FastAPI backend token/session verification support
- ability to map provider identity to internal `user_id`
- local development ergonomics
- production secret management
- webhook/audit support
- lock-in and migration cost

## Runtime Enforcement Order

When implementation is approved, proceed in this order:

1. Resolve and verify `AuthContext` per request. Done.
2. Attach `user_id` to new run snapshots and app-owned records. Started for
   run snapshots and normalized lead records; child artifacts remain pending.
3. Add repository-level owner filters for read paths. Pure snapshot ownership
   and normalized artifact aggregate helpers now exist; owner-aware snapshot
   listing is implemented in both repositories.
4. Enforce protected-route policy for existing read endpoints. Done.
5. Enforce approval/external-action ownership policy. Done.
6. Tighten production CORS and startup auth validation. Done.

Each step must be separately reviewable and covered by targeted tests.

## Follow-Up Decisions

- Existing anonymous records remain isolated unless an explicit backfill is
  designed.
- Approval currently requires the same verified owner identity as lead reads;
  stronger step-up authentication can be considered if risk changes.
- Persisted vector retrieval must define tenant metadata and filtering before
  it is introduced.
- Distributed rate limiting is deferred until Phase 8 deployment topology
  requires it.
