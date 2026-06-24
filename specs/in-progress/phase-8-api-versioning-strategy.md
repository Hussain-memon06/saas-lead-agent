# Phase 8 API Versioning Strategy

Status: Milestone 8.6 strategy plus first alias implementation slice.

## Current Route Surface

The current production frontend calls these unversioned backend routes:

- `POST /api/qualify`
- `GET /api/leads`
- `GET /api/leads/{thread_id}`
- `GET /api/leads/{thread_id}/events`
- `POST /api/leads/{thread_id}/approve`
- `POST /api/leads/{thread_id}/reject`

These routes are already protected by Clerk-backed FastAPI auth in production
and are used by `frontend/lib/api.ts`.

## Decision

Introduce `/api/v1` as backward-compatible aliases first, not as a breaking
migration.

The initial implementation slice should preserve the current flat response
shapes and auth behavior. Existing `/api/*` routes should remain live until a
later explicit deprecation window is approved.

## Compatibility Policy

- Existing `/api/*` routes remain the stable app contract for the current
  deployed frontend.
- New `/api/v1/*` aliases should return the same response models, status codes,
  auth requirements, ownership checks, and error behavior as their unversioned
  equivalents.
- The frontend should not be moved to `/api/v1` in the same slice that creates
  aliases. First add aliases and targeted API tests, then migrate the frontend
  in a separate small change.
- Any future response envelope must be versioned or opt-in. Do not wrap current
  `/api/*` responses without a frontend compatibility plan.

## Proposed `/api/v1` Aliases

| Current route | Versioned alias |
| --- | --- |
| `POST /api/qualify` | `POST /api/v1/qualify` |
| `GET /api/leads` | `GET /api/v1/leads` |
| `GET /api/leads/{thread_id}` | `GET /api/v1/leads/{thread_id}` |
| `GET /api/leads/{thread_id}/events` | `GET /api/v1/leads/{thread_id}/events` |
| `POST /api/leads/{thread_id}/approve` | `POST /api/v1/leads/{thread_id}/approve` |
| `POST /api/leads/{thread_id}/reject` | `POST /api/v1/leads/{thread_id}/reject` |

Avoid `/api/v1/api/...`; the version prefix should replace the current
top-level `/api` segment.

## Implemented Alias Slice

The first alias slice registers `/api/v1` paths against the existing route
handlers while preserving current `/api/*` routes and frontend URLs.

Implemented aliases:

- `POST /api/v1/qualify`
- `GET /api/v1/leads`
- `GET /api/v1/leads/{thread_id}`
- `GET /api/v1/leads/{thread_id}/events`
- `POST /api/v1/leads/{thread_id}/approve`
- `POST /api/v1/leads/{thread_id}/reject`

## Implementation Shape

Completed implementation shape:

1. Register both unversioned and `/api/v1` paths against the same handlers.
2. Keep the current flat response models and summaries.
3. Add targeted tests confirming alias registration, existing response shape,
   and unauthenticated rejection when dev bypass is disabled.
4. Do not change frontend API URLs until a later migration slice.

## Response Envelope Policy

- Current responses stay flat for compatibility.
- A future envelope can be introduced only under a versioned contract, for
  example `/api/v2`, an explicit request header, or a dedicated response model.
- Error responses should remain predictable and documented before envelope
  migration starts.

## Acceptance Criteria For Alias Implementation

- Existing `/api/*` tests continue to pass.
- `/api/v1/*` aliases exist for the six current protected route families.
- Auth, ownership, rate limits, request-size limits, and SSRF/input safety
  behavior are unchanged.
- Frontend behavior is unchanged until a later frontend migration slice.
- Targeted API tests cover at least one authenticated success path and one
  unauthenticated rejection path for the versioned surface.

## Non-Goals

- No response-envelope migration in the alias slice.
- No frontend route migration in the alias slice.
- No API gateway, service mesh, or deployment platform rewrite.
- No deprecation of existing `/api/*` routes until real production usage is
  understood.
