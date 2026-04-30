# Dossify — Frontend

Next.js 14 App Router UI for the AI SDR lead-research agent.  Talks to the
FastAPI backend in `../src/saas_lead_agent/api/` over three endpoints
(`/api/qualify`, `/api/leads/{thread_id}/approve`, `/api/leads/{thread_id}/reject`).

## Stack

- Next.js 14 (App Router, React 18, TypeScript)
- Tailwind CSS + [shadcn/ui](https://ui.shadcn.com) components
- TanStack Query v5 for server state
- React Hook Form + Zod for form validation
- `lucide-react` icons

## Local development

You need **two processes running**: the FastAPI backend on `:8080`
and this Next.js dev server on `:3000`.  The dev server proxies
`/api/*` through to the backend via `next.config.mjs#rewrites`, so the
browser only ever talks to `localhost:3000` and there's no CORS dance.

### 1. Backend (port 8080)

From the repo root:

```bash
uv sync
uv run uvicorn src.saas_lead_agent.api.main:app --reload --port 8080 --timeout-keep-alive 120
```

You'll need a `.env` at the repo root with at minimum:

```
GOOGLE_API_KEY=...        # Gemini (research agents)
OPENAI_API_KEY=...        # GPT-4o-mini (email writer)
TAVILY_API_KEY=...        # Web search
HUNTER_API_KEY=...        # Decision-maker email lookup
SENDGRID_API_KEY=...      # (optional in dev — falls back to stub send)
POSTGRES_URL=...          # (optional — InMemorySaver if absent)
LANGFUSE_PUBLIC_KEY=...   # (optional — tracing disabled if absent)
LANGFUSE_SECRET_KEY=...
```

See `../CLAUDE.md` for the full env contract.

### 2. Frontend (port 3000)

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>.

### Environment variables

The frontend reads exactly one optional variable:

| Var | Default | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE` | `""` (relative) | Override the backend origin.  Leave unset for local dev — the rewrite proxy handles it.  Set to e.g. `https://api.example.com` when deploying without a proxy. |

In production, the simplest deploy is a Cloud Run service that serves
both the FastAPI app and a built frontend behind one origin; in that
case you also leave `NEXT_PUBLIC_API_BASE` unset.

## Scripts

```bash
npm run dev      # Next.js dev server with HMR
npm run build    # Production build
npm run start    # Run production build
npm run lint     # ESLint
```

## Folder layout

```
app/
  layout.tsx              # Root layout, header, providers
  page.tsx                # Landing — hero + qualify form + how-it-works
  leads/[threadId]/page.tsx   # Dossier view + approve/reject gate
components/
  qualify-form.tsx        # Form + mutation; routes on success
  loading-state.tsx       # Long-running progress UI (60-90s qualify)
  dossier-card.tsx        # Company profile
  contact-card.tsx        # Decision-maker
  signals-list.tsx        # Buying signals
  fit-score-badge.tsx     # 0-100 score with tier
  email-preview.tsx       # Drafted email, read-only
  decision-buttons.tsx    # Approve / Reject + outcome banner
  error-banner.tsx        # Reusable error surface
  site-header.tsx         # Sticky header with GitHub link
  ui/                     # shadcn/ui primitives
lib/
  api.ts                  # Typed fetch wrappers + ApiError
  api-base.ts             # apiUrl() helper
  query-client.tsx        # <Providers/> wrapping TanStack Query
  types.ts                # Backend response shapes
hooks/                    # (reserved)
```

## Architecture notes

- **State handoff:** `qualify` returns the full dossier in one response
  (the call blocks ~60-90s).  The form seeds the React Query cache under
  `["lead", thread_id]`, then `router.push`es to `/leads/{thread_id}`,
  which reads the cache without a refetch.  Hard refresh on the dossier
  route shows an empty state with a link back home — by design,
  dossiers are not persisted client-side.
- **Approve/reject:** mutations call `/api/leads/.../approve|reject` and
  merge the resume payload back into the same cache entry, so the
  decision UI swaps to an outcome banner without navigation.
- **Long wait UX:** `LoadingState` shows a fake-but-honest stepper
  (`aria-live="polite"`).  If the backend takes longer than the last
  step's duration, the final spinner keeps animating until either the
  response lands or the 120 s `AbortController` timeout fires.

## Accessibility

- All status surfaces (loading stepper, error banner, outcome banner)
  use `aria-live="polite"` so screen readers announce updates.
- Form errors use `aria-invalid` + `aria-describedby` and render with
  `role="alert"` so the message is announced on submit.
- A skip link in the layout jumps past the header to `#main-content`.
- Focus rings come from the `--ring` token; verify visible focus by
  tabbing through the landing form and the dossier action buttons.

## Troubleshooting

- **`/api/*` requests 404 in the browser** — backend isn't running on
  `:8080`, or you set `NEXT_PUBLIC_API_BASE` to something unreachable.
- **Qualify hangs past 2 min** — the client aborts at 120 s with an
  `ApiError` shown in the form.  Check the backend logs; one of the
  external tool calls (Tavily, Hunter, scraper) is likely the culprit.
- **Dossier page shows "No dossier data"** — expected after a hard
  refresh.  Run a new qualify; the cache lives in browser memory only.
