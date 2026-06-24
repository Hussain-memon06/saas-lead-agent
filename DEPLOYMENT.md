# Production deployment — Google Cloud Run

End-to-end runbook for deploying the AI SDR lead-research agent to Cloud Run
with Supabase as the Postgres backend.

Current deployment note: the production frontend is Vercel-backed at
`https://agent.hussainflow.com/`. Cloud Run is one supported backend target for
the Docker image; it is not required if another Docker-compatible backend host
is selected.

---

## Prerequisites

- A GCP project with billing enabled
- `gcloud` CLI authenticated: `gcloud auth login && gcloud auth application-default login`
- Project set as default: `gcloud config set project YOUR_PROJECT_ID`
- A Supabase project (or any managed Postgres) for state persistence
- API keys for OpenAI, Tavily, Hunter, SendGrid, Langfuse

---

## 1. Enable required Google APIs

```bash
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com
```

---

## 2. Create an Artifact Registry repo for the image

```bash
gcloud artifacts repositories create saas-lead-agent \
    --repository-format=docker \
    --location=us-central1 \
    --description="AI SDR lead-research container images"
```

Configure docker auth once per machine:

```bash
gcloud auth configure-docker us-central1-docker.pkg.dev
```

---

## 3. Store secrets in Secret Manager

**Never** put API keys in `.env` files that ship with the image.  Use Secret
Manager for anything that's not a connection string.

```bash
# Repeat for each secret
echo -n "sk-..."       | gcloud secrets create OPENAI_API_KEY      --data-file=-
echo -n "tvly-..."     | gcloud secrets create TAVILY_API_KEY      --data-file=-
echo -n "..."          | gcloud secrets create HUNTER_API_KEY      --data-file=-
echo -n "SENDGRID_KEY_PLACEHOLDER" | gcloud secrets create SENDGRID_API_KEY    --data-file=-
echo -n "pk-lf-..."    | gcloud secrets create LANGFUSE_PUBLIC_KEY --data-file=-
echo -n "LANGFUSE_SECRET_PLACEHOLDER" | gcloud secrets create LANGFUSE_SECRET_KEY --data-file=-
echo -n "postgresql://postgres:PWD@db.PROJ.supabase.co:5432/postgres" \
                       | gcloud secrets create POSTGRES_URL        --data-file=-
```

To rotate a secret later: `echo -n "new-value" | gcloud secrets versions add NAME --data-file=-`.

---

## 4. Grant Cloud Run access to the secrets

```bash
PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT_ID --format='value(projectNumber)')
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for SECRET in OPENAI_API_KEY TAVILY_API_KEY HUNTER_API_KEY \
              SENDGRID_API_KEY LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY \
              POSTGRES_URL; do
    gcloud secrets add-iam-policy-binding "$SECRET" \
        --member="serviceAccount:${SA}" \
        --role="roles/secretmanager.secretAccessor"
done
```

For tighter isolation create a dedicated service account and bind only what
this service needs.

---

## 5. Build and push the image

Cloud Build is the simplest path — it streams logs and pushes to Artifact
Registry in one command:

```bash
gcloud builds submit \
    --tag us-central1-docker.pkg.dev/YOUR_PROJECT_ID/saas-lead-agent/api:latest
```

If you prefer building locally:

```bash
docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT_ID/saas-lead-agent/api:latest .
docker push    us-central1-docker.pkg.dev/YOUR_PROJECT_ID/saas-lead-agent/api:latest
```

---

## 6. Deploy to Cloud Run

```bash
gcloud run deploy saas-lead-agent \
    --image=us-central1-docker.pkg.dev/YOUR_PROJECT_ID/saas-lead-agent/api:latest \
    --region=us-central1 \
    --platform=managed \
    --allow-unauthenticated \
    --port=8080 \
    --memory=1Gi \
    --cpu=1 \
    --min-instances=0 \
    --max-instances=10 \
    --concurrency=20 \
    --timeout=600 \
    --set-env-vars="SENDGRID_FROM_EMAIL=sales@yourdomain.com,LANGFUSE_HOST=https://cloud.langfuse.com" \
    --set-secrets="OPENAI_API_KEY=OPENAI_API_KEY:latest,TAVILY_API_KEY=TAVILY_API_KEY:latest,HUNTER_API_KEY=HUNTER_API_KEY:latest,SENDGRID_API_KEY=SENDGRID_API_KEY:latest,LANGFUSE_PUBLIC_KEY=LANGFUSE_PUBLIC_KEY:latest,LANGFUSE_SECRET_KEY=LANGFUSE_SECRET_KEY:latest,POSTGRES_URL=POSTGRES_URL:latest"
```

The deploy command prints a public URL like
`https://saas-lead-agent-xyz-uc.a.run.app`.  The Chainlit UI is at
`<URL>/chainlit`; the API at `<URL>/api/qualify`.

### Notes on the flags

| Flag                | Why                                                                                             |
|---------------------|-------------------------------------------------------------------------------------------------|
| `--memory=1Gi`      | LangGraph + Postgres + Langfuse + Chainlit need ~600 MB resident; 1 GiB is safe                 |
| `--cpu=1`           | One vCPU is enough; LLM calls are network-bound                                                 |
| `--timeout=600`     | A full pipeline (research → email draft) can take 60–120 s; 600 s leaves headroom for HITL pause |
| `--concurrency=20`  | One process can handle several concurrent qualify calls; tune after measuring                   |
| `--min-instances=0` | Scales to zero; first request after idle pays cold-start tax (~5 s)                             |

If cold starts hurt: bump `--min-instances=1` (≈ \$25/month for an idle 1Gi/1cpu instance).

---

## 7. First-time DB setup

`AsyncPostgresSaver.setup()` runs idempotent DDL inside the FastAPI lifespan
on every cold start, so no separate migration step is needed in Cloud Run.

To verify it ran cleanly, hit the health endpoint and check the logs:

```bash
curl https://saas-lead-agent-xyz-uc.a.run.app/api/qualify \
    -X POST -H 'Content-Type: application/json' \
    -d '{"url":"https://stripe.com"}'

gcloud run services logs read saas-lead-agent --region=us-central1 --limit=50
```

---

## 8. Smoke test the deploy

```bash
URL=$(gcloud run services describe saas-lead-agent \
      --region=us-central1 --format='value(status.url)')

# 1. Process liveness
curl -s "$URL/health" | jq .

# 2. Startup/config readiness
curl -s "$URL/ready" | jq .
```

Protected API routes such as `/api/qualify`, `/api/v1/qualify`, approval, and
lead recovery require a valid Clerk Bearer JWT in production. Do not use
unauthenticated curl calls as production smoke tests, and do not approve a real
send unless delivery behavior is intentionally being tested.

---

## 9. Rollback / redeploy

Cloud Run keeps every revision; rollback is instant:

```bash
# List revisions
gcloud run revisions list --service=saas-lead-agent --region=us-central1

# Roll back to the previous revision
gcloud run services update-traffic saas-lead-agent \
    --region=us-central1 \
    --to-revisions=saas-lead-agent-00012-abc=100
```

To redeploy: re-run step 5 (build) + step 6 (deploy).  A successful deploy
shifts traffic to the new revision atomically.

---

## 10. Local-dev parity

The exact same Dockerfile builds the local stack via `docker-compose`:

```bash
docker compose up --build
# → http://localhost:8080
```

`docker-compose.yml` adds a one-shot `migrate` service that runs
`AsyncPostgresSaver.setup()` once before the app boots — same DDL as
Cloud Run's lifespan path, just sequenced explicitly for first-boot clarity.

---

## Cost estimate (rough)

For a low-traffic deployment (~100 qualify calls / day):

- Cloud Run, scale-to-zero: \$0 – \$5 / month (mostly free tier)
- Supabase free tier: \$0
- LLM costs: ~\$0.02 / qualify (gpt-4o-mini × 5 agents) → \$60 / month
- SendGrid free tier: 100 emails / day = \$0
- Langfuse Hobby: \$0 (50k events / month)

Total: **~\$60 / month at 100 qualifies/day**, dominated by OpenAI usage.
