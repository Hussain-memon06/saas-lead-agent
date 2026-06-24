# Phase 8 Operations Runbooks

Status: Milestone 8.5 planning and operations documentation.

These runbooks define what to watch and what to do before adding a
vendor-specific monitoring stack. They intentionally avoid secret values,
external API checks, Docker builds, or cloud smoke tests.

## Monitoring Signals

| Signal | Initial Alert Threshold | First Check |
| --- | --- | --- |
| API latency | p95 `/api/qualify` over 120 seconds for 10 minutes | Check backend saturation, provider latency, and graph node timings. |
| 5xx responses | 5xx rate over 2% for 5 minutes | Check recent deploy, `/ready`, application logs, and provider errors. |
| Provider failures | OpenAI, Tavily, Hunter, SendGrid, or Langfuse errors above baseline for 10 minutes | Check provider status pages and recent secret/config changes. |
| Tool failures | Search, scrape, contact finding, or email delivery failures above baseline | Check sanitized tool events and provider-specific error categories. |
| Retrieval failures | Missing retrieval context or retrieval evaluator regressions | Check retrieval events, source trust labels, and dataset coverage. |
| Token/cost spikes | Daily projected cost exceeds expected budget by 50% | Check run volume, repeated retries, prompt sizes, and model usage. |
| Email delivery failures | SendGrid rejected, blocked, or failed sends above baseline | Check SendGrid activity, verified sender/domain state, and delivery events. |
| Auth failures | Sudden increase in 401/403 responses | Check Clerk configuration, token audience/issuer, and frontend env vars. |
| Readiness failures | `/ready` returns 503 outside a deploy window | Check production env vars and startup validation errors. |

## Incident Triage

1. Confirm whether `/health` is alive and `/ready` is passing.
2. Identify whether the issue started after a deploy, config change, provider
   outage, or traffic spike.
3. Use request IDs, thread IDs, run IDs, sanitized tool events, and Langfuse
   trace IDs to connect user-visible failures to backend execution.
4. Do not paste secrets, raw provider payloads, raw scraped pages, full prompts,
   or full outreach bodies into tickets or logs.
5. If real email delivery might be affected, pause approval-driven sends until
   SendGrid status and idempotency behavior are understood.

## Rollback Runbook

1. Freeze new deploys and record the failing version, commit, and deploy time.
2. Confirm whether the failure is code, config, provider, or data related.
3. Roll back the frontend and backend independently if only one surface changed.
4. After rollback, verify `/health`, `/ready`, one authenticated page load, and
   one non-sending qualification path.
5. Keep full release verification optional during incident response unless the
   rollback candidate is uncertain.
6. Capture the failed version, rollback version, user impact, and follow-up
   fixes in the incident notes.

## External Provider Outage Runbook

1. Identify the provider and affected tool or graph node from sanitized run
   metadata.
2. Check the provider status page from an operator browser, not from automated
   app code.
3. If the provider is OpenAI, Tavily, Hunter, or scraper-related, expect
   qualification quality or completion to degrade.
4. If the provider is SendGrid, keep human approval visible but prevent retry
   loops that could duplicate sends.
5. Communicate the degraded capability and whether users should retry later.
6. After recovery, review failed run events for stuck, duplicate, or partial
   work before reprocessing anything.

## Cost Spike Runbook

1. Compare run count, token usage, and per-node timings against the previous
   normal day.
2. Look for repeated qualifications for the same company, retries, unusually
   large prompts, or retrieval context expansion.
3. Temporarily lower rate limits or pause expensive provider-backed actions if
   spend is still accelerating.
4. Do not change models, prompts, or provider settings broadly during triage
   unless the root cause is clear.
5. Add a deterministic test or eval case for any behavior that caused runaway
   usage.

## Email Delivery Failure Runbook

1. Confirm whether the send was `sent`, `stubbed`, `failed`, or blocked before
   retrying.
2. Check the delivery idempotency key and existing delivery events.
3. Do not retry an approved send unless the previous attempt is confirmed not
   to have been accepted by SendGrid.
4. Check SendGrid sender/domain verification, API key permissions, and account
   status.
5. If production email config is missing, startup should fail closed rather
   than report fake success.

## Data Lifecycle Notes

- User-owned leads, runs, contacts, outreach drafts, decisions, delivery
  events, retrieval events, and audit-style run events should remain scoped to
  the owning user or tenant.
- Export should include lead summaries, source references, score breakdowns,
  outreach drafts, decisions, and delivery status without exposing unrelated
  tenants.
- Deletion should remove or anonymize user-owned application records and avoid
  orphaned retrieval/vector metadata in future vector-store work.
- Retention periods are not implemented yet. Until explicit retention policy is
  approved, avoid adding new long-lived stores for raw scraped content or full
  prompts.

## Follow-Up Implementation Candidates

- Add vendor-specific dashboards and alert routing after the deployment target
  is confirmed.
- Add persisted incident/audit events if operational reporting needs more than
  current run-event metadata.
- Add explicit cost budget configuration once production usage patterns are
  known.
- Add data export/deletion endpoints only after Phase 8 API versioning and
  persistence ownership constraints are finalized.
