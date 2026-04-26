# Dossify Frontend Architecture

## Goal
A professional Next.js 14 web UI for the AI SDR backend, replacing the
Chainlit chat surface for end-users.  The Chainlit UI stays — it's a great
internal/dev tool — but Dossify is the polished customer-facing front door.

Lives in `frontend/` inside this repo (monorepo) so the API contract and
TypeScript types stay in sync, and so a single PR can change a backend
field and its UI consumer.

---

## Backend contract (already shipped)

Three endpoints, all on `localhost:8080`:

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | `/api/qualify` | `{url: string}` | `QualifyResponse` |
| POST | `/api/leads/{thread_id}/approve` | _none_ | `ApproveResponse` |
| POST | `/api/leads/{thread_id}/reject` | _none_ | `ApproveResponse` |

`thread_id` format is `lead:{domain}` — the colon **must** be URL-encoded
in fetch calls (`encodeURIComponent`).  The qualify call blocks for
30–90 s while the graph runs to `await_approval`; not streaming, plain
sync request.

Response shapes (mirror Pydantic models in `src/saas_lead_agent/api/schemas.py`):

```ts
type QualifyResponse = {
  thread_id: string
  company_profile: CompanyProfile | null
  contact: Contact | null
  signals: Signal[] | null
  fit_score: number | null            // 1–10
  email_subject: string | null
  email_body: string | null
  email_approved: boolean | null
  send_result: "sent" | "rejected" | "no_contact" | "failed" | null
  message_id: string | null
  sent_at: string | null              // ISO-8601
  interrupted: boolean                // true while paused at await_approval
  errors: string[]
}

type ApproveResponse = Omit<QualifyResponse, "company_profile" | "contact"
                                          | "signals" | "fit_score"
                                          | "email_subject" | "email_body">
```

Sub-shapes derived from existing fixtures in `tests/test_agents.py`:

```ts
type CompanyProfile = {
  name: string
  tagline?: string
  hq?: string
  employees_estimate?: string
  funding_stage?: string
  products?: string[]
  notable_customers?: string[]
  sources?: string[]
}

type Contact = {
  name: string | null
  title: string | null
  email: string | null
  linkedin: string | null
  confidence: number | null
  source: string  // "hunter"
}

type Signal = {
  type: "funding" | "hiring" | "product" | "techstack" | "other"
  title: string
  summary?: string
  url?: string
  date?: string
}
```

---

## Architecture decisions

### Next.js 14 — **App Router**
Default for new Next 14 projects; React Server Components let the marketing
shell render server-side while interactive parts (form, dossier) are
client components.  Pages router has no advantage here and ships less of
Vercel's intended surface.  Two-page UX (`/` and `/leads/[threadId]`) maps
cleanly to two route segments under `app/`.

### Styling — **Tailwind CSS + shadcn/ui**
- Tailwind via `create-next-app --tailwind`.
- shadcn/ui via the official CLI (`npx shadcn@latest init`); components
  are copied into `frontend/components/ui/`, owned by us, no runtime
  package dependency.
- Light mode only (per request).  Skip `next-themes` for v1.
- Font: Inter, via `next/font/google` for self-hosting.
- Accent: single primary color (Stripe-Atlas-style indigo), neutral gray
  scale for everything else.

### Server-state — **TanStack Query v5**
- The two long-running mutations (qualify, approve/reject) use
  `useMutation`, not `useQuery` — they're triggered by the user, not
  polled.
- `QueryClientProvider` wraps the root layout via a thin client-component
  boundary (`lib/query-client.tsx`).
- Cache the qualify result under `["lead", thread_id]` so the dossier
  page can read it without a refetch.

### Client-state — **React Hook Form + Zod**
- The qualify form is a single field but Zod gives us URL validation
  matching the backend's exact rule (`http`/`https` scheme + non-empty
  netloc).  Keeps client-side parity with `QualifyRequest.validate_url`
  in `schemas.py`.
- No Redux / Zustand — everything else is form state or React Query
  cache.

### Types — **manual TypeScript first, OpenAPI codegen later**
For v1 with 3 endpoints, hand-written types in `lib/types.ts` are simpler
and the drift risk is low (we own both sides).  Future: generate from
`/openapi.json` via `openapi-typescript`, run in CI, commit the diff.
Logged as a Phase 4 follow-up, not done now.

### Backend ↔ frontend networking
- Dev: Next.js `rewrites()` proxies `/api/:path*` → `http://localhost:8080/api/:path*`.
  Frontend code calls relative `/api/qualify` and lives at the same
  origin in the browser.  **No CORS middleware needed on the backend.**
- Prod: env var `NEXT_PUBLIC_API_BASE_URL` overrides the base.  When set,
  `lib/api.ts` prepends it; when unset, paths stay relative and the dev
  rewrite handles routing.

This is cleaner than adding CORS to FastAPI now and reverses cleanly if
we later split the deploys.

---

## Folder structure

```
frontend/
  app/
    layout.tsx                # Root layout + <Providers>
    page.tsx                  # Landing: hero + qualify form
    leads/[threadId]/
      page.tsx                # Dossier + email preview + decision buttons
    globals.css               # Tailwind directives + design tokens
  components/
    ui/                       # shadcn/ui primitives (button, card, input, ...)
    qualify-form.tsx          # URL input + submit + RHF/Zod validation
    dossier-card.tsx          # Company profile block
    contact-card.tsx          # Decision-maker block
    signals-list.tsx          # Buying-signal pills + summaries
    fit-score-badge.tsx       # Visual 1–10 indicator
    email-preview.tsx         # Subject + body card
    decision-buttons.tsx      # Approve / Reject + result banner
    error-banner.tsx          # Maps QualifyResponse.errors → UI
    loading-state.tsx         # Skeleton + "this can take up to 90s"
  lib/
    api.ts                    # qualify(), approve(), reject() fetch wrappers
    types.ts                  # QualifyResponse, ApproveResponse, sub-types
    query-client.tsx          # 'use client' QueryClientProvider boundary
    utils.ts                  # cn() helper for shadcn class merging
  public/
    logo.svg
    favicon.ico
  package.json
  tsconfig.json
  tailwind.config.ts
  postcss.config.mjs
  next.config.mjs             # rewrites() for /api/* → localhost:8080
  components.json             # shadcn config
  .env.local.example
  README.md
```

---

## UX flow

```
   /  (landing)
   ├── hero: "Research any B2B SaaS company in 60 seconds"
   ├── qualify form: <input url> [Research] button
   └── on submit:
       └── useMutation(qualify) → loading state (90s skeleton)
           └── onSuccess: router.push(`/leads/${encodeURIComponent(thread_id)}`)
               (cache the response under ["lead", thread_id])

   /leads/[threadId]
   ├── reads cache; if empty (refresh / direct link) shows "no data"
   │   prompting back to /
   ├── DossierCard + ContactCard + SignalsList + FitScoreBadge
   ├── EmailPreview (subject + body, monospace-ish)
   └── DecisionButtons:
       ├── Approve → useMutation(approve) → success banner (✅ Sent · message_id …)
       └── Reject  → useMutation(reject)  → muted banner (🚫 Rejected)
```

Edge cases handled in the UI:
- `interrupted=false` after qualify → graph errored before draft.  Render
  errors banner, no buttons.
- `send_result="no_contact"` → warn the user no email was found; no resend.
- `send_result="failed"` → red banner with last error; no automatic retry.
- 422 from qualify → inline form error from RHF (URL parse failed).
- 500 from any endpoint → top-of-page error banner with retry button.
- Tab backgrounded during 90s wait → React Query keeps the in-flight
  mutation alive; no special handling needed.

---

## Step-by-step build plan

Each step has its own verification command.  Stop on red.

### Step 1 — Frontend scaffold
- Files: `frontend/` (everything created by `create-next-app`)
- Action: `cd frontend/.. && npx create-next-app@14 frontend --typescript --tailwind --eslint --app --src-dir=false --import-alias="@/*"` (no, drop `--src-dir` flag — keep it flat)
- Verification: `cd frontend && npm run build` succeeds; `npm run dev` serves a page on :3000
- Risks: create-next-app default Tailwind config differs slightly from shadcn's expected setup; we'll adjust in Step 3

### Step 2 — Next.js dev proxy + base-URL helper
- Files: `frontend/next.config.mjs`, `frontend/lib/api.ts` (skeleton),
  `frontend/.env.local.example`
- Action: configure `rewrites()` to proxy `/api/:path*` → `http://localhost:8080`
  in dev; export an `apiBase()` helper that reads `NEXT_PUBLIC_API_BASE_URL`
- Verification: with backend running, `curl http://localhost:3000/api/qualify -X POST -H 'Content-Type: application/json' -d '{"url":"https://stripe.com"}'` reaches the backend (visible in uvicorn logs); 422 response if backend can't parse — proves wiring
- Risks: dev rewrites only run while `next dev` is up; production deploy needs `NEXT_PUBLIC_API_BASE_URL`

### Step 3 — shadcn/ui init + base components
- Files: `frontend/components.json`, `frontend/components/ui/{button,card,input,label,badge,separator,skeleton}.tsx`
- Action: `npx shadcn@latest init` (light mode, slate base, Inter font); add the 7 primitives we'll use
- Verification: `npm run build` clean; `npm run lint` clean

### Step 4 — React Query provider + types
- Files: `frontend/lib/query-client.tsx`, `frontend/lib/types.ts`,
  `frontend/app/layout.tsx` (wrap children in `<Providers>`)
- Action: write the TypeScript types matching `QualifyResponse` /
  `ApproveResponse` / sub-shapes; create a `'use client'` Providers
  component that mounts a `QueryClient`
- Verification: `npm run build` clean; types referenced from a stub
  page render without TS errors

### Step 5 — API client (`lib/api.ts`)
- Files: `frontend/lib/api.ts`
- Action: implement `qualify(url)`, `approve(threadId)`, `reject(threadId)`
  using `fetch` with a 120 s `AbortController` timeout; throw a typed
  `ApiError` on non-2xx with `{status, errors[]}`
- Verification: write a tiny smoke test (`frontend/lib/api.test.ts` if we
  add Vitest in Step 9, otherwise verify manually in browser dev tools)

### Step 6 — Landing page + qualify form
- Files: `frontend/app/page.tsx`, `frontend/components/qualify-form.tsx`,
  `frontend/components/loading-state.tsx`
- Action: hero copy, RHF + Zod-validated URL input, submit triggers
  `useMutation(qualify)`; on success redirect to `/leads/[encoded threadId]`;
  loading state shows the 90 s skeleton with reassurance copy
- Verification: paste `https://stripe.com`, watch the request fire in
  network tab, redirect lands on dossier page; reject `not-a-url`
  inline before submit; backend 422 surfaces in form error

### Step 7 — Dossier page
- Files: `frontend/app/leads/[threadId]/page.tsx`,
  `frontend/components/{dossier-card,contact-card,signals-list,fit-score-badge,email-preview}.tsx`
- Action: read cached `QualifyResponse` from React Query under
  `["lead", threadId]`; render dossier components; if cache empty
  (refresh / direct link), render an empty state pointing back to `/`
- Verification: full flow from `/` → dossier page; all five sub-components
  render real data from a Stripe qualify

### Step 8 — Approve / Reject + outcome banner
- Files: `frontend/components/decision-buttons.tsx`,
  `frontend/components/error-banner.tsx`
- Action: two `useMutation` hooks, one per endpoint; on success update
  cache and show outcome banner mapping `send_result` → UI; disable
  buttons after a decision is taken
- Verification: Approve a real qualify, see `send_result="sent"` in the
  banner with `message_id`; Reject another, see the muted banner

### Step 9 — Polish + README
- Files: `frontend/README.md`, error handling tightening, accessibility
  pass (focus rings, aria-live regions for the loading + banner)
- Action: README documents `npm run dev`, env vars, expected ports,
  how to run both servers; aria-live="polite" on loading + result
  regions; keyboard nav verified on form
- Verification: README reproduces the local-dev story end-to-end on a
  fresh checkout (manual)

### Step 10 — Optional: Vitest + 1 component test per page
- Files: `frontend/vitest.config.ts`, a few `*.test.tsx` next to components
- Action: smoke tests for `qualify-form` (Zod validation) and
  `decision-buttons` (mutation wiring with mocked fetch)
- Verification: `cd frontend && npm test`

Phase 4 follow-ups (NOT in this plan):
- OpenAPI codegen for types
- Auth (none on backend yet)
- Frontend Cloud Run deploy + Dockerfile
- Bulk qualify (CSV upload UI)

---

## Risks / unknowns

1. **90 s qualify wait.**  Browser tab throttling + impatient users.  Mitigation:
   skeleton + reassurance copy + don't auto-redirect away from /.
2. **No auth.**  Anyone hitting localhost:8080 can qualify any domain.
   Acceptable for v1 (local-only).  Phase 4 must add an auth layer
   *before* exposing the UI publicly.
3. **No streaming.**  Backend doesn't support SSE today; qualify is sync.
   If wait time becomes painful we add SSE in a separate phase — would
   need backend changes to `routes.py` (yield events from each subagent
   completion).
4. **shadcn version drift.**  Components are copied at init time;
   re-running the CLI in 6 months may change styles.  Mitigation: pin
   `components.json` and document the upgrade path.
5. **Type drift between backend and frontend.**  Manual types now;
   OpenAPI codegen later.  In the meantime, every backend schema PR
   must touch `frontend/lib/types.ts` if it changes shape.
6. **CORS still needed if frontend deploys separately.**  Currently we
   sidestep with rewrites; if Phase 4 splits the deploys, FastAPI gets a
   `CORSMiddleware` and `NEXT_PUBLIC_API_BASE_URL` switches to the prod
   API host.

---

## Verification commands cheat-sheet

| When | Command | Pass criterion |
|------|---------|----------------|
| Step 1 | `cd frontend && npm run build` | Exit 0; `.next/` produced |
| Step 1 | `cd frontend && npm run dev` | :3000 serves Next default page |
| Step 2 | `curl -X POST http://localhost:3000/api/qualify -H 'Content-Type: application/json' -d '{"url":"https://stripe.com"}' -m 120` | Reaches backend (uvicorn log shows hit) |
| Step 3 | `cd frontend && npm run build` | Exit 0 |
| Step 4 | `cd frontend && npm run build` | Exit 0; types resolve |
| Step 5 | manual: open browser, watch network tab | qualify call fires; 422/500 surface |
| Step 6 | manual: paste valid + invalid URLs | redirect or inline error as expected |
| Step 7 | manual: full qualify → dossier | all 5 sub-components render |
| Step 8 | manual: approve a real qualify | `send_result="sent"` shown |
| Step 9 | manual: README reproducibility | fresh-clone teammate can run it |
| Step 10 | `cd frontend && npm test` | All tests pass |

---

## Out of scope (this plan)

- Backend CORS middleware (using rewrites instead)
- Backend SSE / streaming (sync request is fine for 90s)
- Frontend deploy infrastructure (separate Phase 4 plan)
- Authentication (separate Phase 4 plan)
- Bulk qualify UI
- Telemetry/analytics on the frontend
- E2E tests (Playwright) — defer until UI stabilises

---

## Approval gate

Stop here.  Awaiting approval before scaffolding `frontend/`.  After
approval, I will execute Step 1 (and only Step 1), report files +
verification output, then wait for the next go-ahead.
