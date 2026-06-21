# Phase 5 Tooling And Durable Execution Design

## Status

Phase 5 has started with no new runtime dependencies. This document defines the
first implementation boundary for typed tool contracts, MCP readiness, durable
execution planning, retry/timeout/idempotency policy, and provider fallback
behavior.

MCP, queues, durable job infrastructure, browser automation, code execution,
and new provider dependencies are not implemented in this milestone.

Implemented so far:

- Typed tool contracts in `src/saas_lead_agent/tools/contracts.py`.
- Scoped sanitized tool-result capture in
  `src/saas_lead_agent/tools/recording.py`.
- `web_search` returns the same LangChain list output to callers while
  producing a typed `ToolResult` internally.
- `scrape` returns the same LangChain string output to callers while producing
  a typed `ToolResult` internally.
- `hunt_contact` returns the same LangChain dict output to callers while
  producing a typed `ToolResult` internally.
- `company_researcher`, `contact_finder`, and `signal_detector` capture
  sanitized tool metadata into `tool_usage`.
- API processing metadata exposes additive `tool_events`, `tool_status`, and
  `tool.<node>.<tool>` timing entries.
- SendGrid delivery now has a typed `ToolResult` envelope, delivery
  idempotency key propagation, and sanitized `sendgrid_delivery` tool metadata
  for approved delivery attempts.
- A local tool-spec registry lists the current Phase 5 tool surface for future
  MCP, durable execution, and provider fallback work.

## Current Tool Surface

- `web_search`: Tavily-backed search tool, external provider call, now wrapped
  with typed `ToolResult` metadata while preserving existing `RuntimeError`
  behavior for missing configuration or provider failure.
- `scrape`: HTTP page fetch and clean-text extraction, external network call,
  now wrapped with typed `ToolResult` metadata while preserving existing
  validation/network/HTTP failure behavior.
- `hunt_contact`: Hunter.io contact-finding tool, external provider call, now
  wrapped with typed `ToolResult` metadata while preserving existing
  configuration/HTTP/network failure behavior.
- Email delivery exists outside `src/saas_lead_agent/tools/` under the
  SendGrid integration, remains human-in-the-loop through approval flow, and
  now exposes typed `sendgrid_delivery` metadata for approved attempts.

## Non-Goals For This Milestone

- No MCP server or client implementation.
- No queue, worker, or background-job dependency.
- No vector database, embedding provider, or retrieval infrastructure changes.
- No auth/session ownership changes.
- No change to existing SendGrid or durable runtime behavior until wrappers are
  introduced in later Phase 5 milestones.

## Tool Interface Design

The initial typed contract lives in
`src/saas_lead_agent/tools/contracts.py`.

Core concepts:

- `ToolSpec`: stable declaration of tool name, category, provider, timeout
  policy, idempotency support, and whether the tool performs an external
  action requiring human approval.
- `ToolTimeoutPolicy`: explicit per-tool timeout, retry-attempt, backoff, and
  circuit-breaker budget.
- `ToolCallContext`: request/run/thread/user correlation plus optional
  idempotency key and input hash. It should not contain raw prompts, API keys,
  full scraped text, full emails, or provider payloads.
- `ToolExecutionMetadata`: persisted runtime metadata safe for run events.
- `ToolError`: sanitized failure details with retryability and optional
  provider status/code.
- `ToolResult`: common result envelope for success, failure, skip, timeout, and
  rate-limit outcomes.

Current categories:

- `search`
- `scrape`
- `contact_finding`
- `email_drafting`
- `email_delivery`
- `crm_export`
- `internal`

Future typed wrappers should adapt existing LangChain tools into `ToolResult`
without breaking the current graph API. Agent nodes should still degrade
gracefully by appending errors to state instead of crashing the whole run.

## MCP Decision

Decision for this milestone: MCP-ready, not implemented yet.

Reasoning:

- Current external tools are local Python boundaries with simple inputs and
  outputs.
- There is no approved MCP dependency or separate tool-server runtime.
- Adding MCP before typed local contracts would add complexity before the
  boundaries are stable.

Future MCP candidates:

- External search/scraping/contact providers when they need shared access from
  multiple agents or processes.
- Internal read-only resources such as ICP profiles, offer documents, and run
  summaries once auth and tenant boundaries exist.
- Versioned prompts/resources if prompt/version tracking becomes part of the
  provider abstraction.

MCP should remain deferred if the local typed interface is sufficient.

## Durable Execution Model

Phase 3 already added app-owned run snapshots/events. Phase 5 should build on
that model rather than replace it.

Proposed durable statuses:

- `queued`
- `running`
- `waiting_for_approval`
- `completed`
- `failed`
- `cancelled`
- `stuck`

Minimum persisted fields for future durable work:

- `run_id`, `thread_id`, `request_id`, and `user_id`
- normalized URL and request/input hash
- current graph node
- status and status reason
- attempts per node/tool
- timeout/deadline metadata
- last heartbeat timestamp
- idempotency key
- retryable/non-retryable failure marker

No queue is added yet. The next implementation should first make tool/run
state explicit enough that adding a queue later is a mechanical change.

## Retry, Timeout, And Circuit Breaker Policy

Default policy direction:

| Boundary | Timeout | Attempts | Retry Notes |
| --- | ---: | ---: | --- |
| Tavily search | 15s | 2 | Retry transient network/rate-limit only |
| Scraper | 15s | 1-2 | Retry network timeouts only; preserve SSRF checks |
| Hunter.io | 15s | 2 | Retry transient network/rate-limit only |
| OpenAI node call | node-specific | 1-2 | Retry provider/network failure with cost guard |
| SendGrid delivery | 10s | 1 | Retry only with delivery idempotency key |

Circuit breakers should be provider-specific and visible in run metadata. When
a breaker is open, the node should return a typed skipped/failed result and
continue with degraded output where safe.

## Idempotency Policy

Qualification idempotency should be based on:

- user/tenant ID when auth exists
- normalized URL
- validated ICP context hash
- model/prompt/version when provider abstraction exists
- requested run mode

Email-delivery idempotency should be stricter:

- run ID
- outreach draft ID or draft content hash
- recipient hash
- SendGrid message/provider event ID when available

External actions must not be repeated automatically unless the idempotency key
proves the previous attempt did not already succeed.

Implemented planning helper:

- `src/saas_lead_agent/email/idempotency.py` defines a deterministic
  `delivery_idempotency_key()` for planned SendGrid delivery protection.
- The key is based on run ID plus hashes of recipient, subject, and body.
- Raw recipient email and raw email body must not be logged as part of the key.
- The key is carried on approved delivery attempts and persisted on app-owned
  delivery event records.
- The helper is intentionally not wired into delivery retries yet; retries need
  persisted delivery-event lookup first.

## Provider Fallback Strategy

- Search: if Tavily fails, return a typed failed result and allow downstream
  research to proceed from scraper/company URL evidence.
- Scraper: if scraping fails, keep the run alive with an explicit source/tool
  failure in metadata.
- Contact finding: if Hunter fails, degrade to no-contact/needs-review instead
  of inventing contact data.
- Email delivery: fail closed unless explicit development stub mode is enabled
  or a real provider success is returned.
- LLM/provider fallback belongs to a later provider abstraction milestone and
  must include cost tracking and prompt/version reproducibility.

## Sandboxing Policy

Future browser automation or code execution must be treated as a high-risk
tool category:

- allowlisted domains and actions
- request and run correlation
- explicit timeout and max-step budgets
- no credential exfiltration
- no arbitrary local filesystem writes outside approved workspace roots
- no external action without human approval

## First Implementation Sequence

1. Add typed tool contract models and focused tests. Done.
2. Document MCP-deferred decision, durable run-state model, retry/timeout,
   idempotency, fallback, and sandboxing policy. Done.
3. Wrap existing non-action tools with `ToolResult` adapters while keeping the
   graph response shape compatible. Done for `web_search`, `scrape`, and
   `hunt_contact`.
4. Persist sanitized tool-result metadata in run events. Done for captured
   `web_search`, `scrape`, and `hunt_contact` calls.
5. Add idempotency planning for qualification and SendGrid delivery before
   adding retries that could duplicate work. Done for delivery-key generation
   and recording; durable duplicate checks are still deferred.
6. Add a typed SendGrid delivery envelope and local tool-spec registry. Done.

## Phase 5 Closure

The no-dependency Phase 5 implementation boundary is complete:

- typed contracts exist for the current tool surface
- search, scraper, contact-finding, and SendGrid delivery produce typed
  envelopes internally
- graph nodes expose sanitized tool metadata through run processing metadata
- delivery idempotency keys are generated and recorded before any retry work
- MCP, queues, durable job runners, external-action retries, and provider
  fallback runtime remain deferred until explicitly approved
