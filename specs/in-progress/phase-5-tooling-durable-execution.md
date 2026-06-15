# Phase 5 Tooling And Durable Execution Design

## Status

Phase 5 has started with no new runtime dependencies. This document defines the
first implementation boundary for typed tool contracts, MCP readiness, durable
execution planning, retry/timeout/idempotency policy, and provider fallback
behavior.

MCP, queues, durable job infrastructure, browser automation, code execution,
and new provider dependencies are not implemented in this milestone.

## Current Tool Surface

- `web_search`: Tavily-backed search tool, external provider call, currently
  raises `RuntimeError` on missing configuration or provider failure.
- `scrape`: HTTP page fetch and clean-text extraction, external network call,
  currently uses first-pass URL validation and a 15-second timeout.
- `hunt_contact`: Hunter.io contact-finding tool, external provider call,
  currently raises `RuntimeError` on missing configuration, HTTP errors, or
  network errors.
- Email delivery exists outside `src/saas_lead_agent/tools/` under the
  SendGrid integration and remains human-in-the-loop through approval flow.

## Non-Goals For This Milestone

- No MCP server or client implementation.
- No queue, worker, or background-job dependency.
- No vector database, embedding provider, or retrieval infrastructure changes.
- No auth/session ownership changes.
- No change to existing tool runtime behavior until wrappers are introduced in
  a later Phase 5 milestone.

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

1. Add typed tool contract models and focused tests.
2. Document MCP-deferred decision, durable run-state model, retry/timeout,
   idempotency, fallback, and sandboxing policy.
3. Wrap one existing non-action tool with a `ToolResult` adapter while keeping
   the graph response shape compatible.
4. Persist sanitized tool-result metadata in run events.
5. Add idempotency planning for qualification and SendGrid delivery before
   adding retries that could duplicate work.
