# Phase 7 Evaluation Framework Design

## Status

Milestones 7.1 through 7.10 complete: deterministic evaluation contracts,
dataset boundaries, small synthetic seed datasets, strict local JSON loading,
scoring evaluation, structured-output evaluation, and retrieval evaluation
plus grounding and outreach-quality evaluation exist without running models,
providers, vector infrastructure, or broad eval suites.

## Goals

- Make agent quality measurable across scoring, retrieval, structured output,
  grounding, tool use, outreach, and adversarial safety.
- Keep deterministic business logic and deterministic metrics as the default.
- Make every result traceable to a dataset version, case ID, evaluator version,
  and prompt/model version when generation is involved.
- Keep normal development checks fast and provider-free.

## Dataset Boundaries

The planned datasets remain those named in `PLANS.md`:

- `evals/golden_dataset.json`: representative qualification, scoring,
  grounding, structured-output, and outreach expectations.
- `evals/adversarial_dataset.json`: prompt injection, unsafe URLs, incomplete
  sources, provider failures, no-contact flows, and disabled delivery cases.
- `evals/retrieval_dataset.json`: queries with expected chunk/source IDs and
  explicit `k` values.

Dataset records must contain synthetic or approved fixture data. They must not
contain credentials, production contact PII, full private documents, raw
provider payloads, or copied customer outreach.

## Contract Model

Each case has:

- stable `case_id`
- one evaluation category
- an input payload containing only fixture data
- typed expectations relevant to the category
- tags for filtering and coverage reporting
- an explicit external-provider requirement, defaulting to false

Each result has:

- case ID and category
- pass/fail status
- deterministic metric values and thresholds
- concise failure reasons
- evaluator version and duration

Run summaries additionally capture dataset name/version, totals, timestamps,
and optional token/cost data. Secrets, prompts, source text, and generated
outreach bodies are excluded from result artifacts by default.

## Metric Ownership

- Scoring: classification accuracy, score deviation, false positive rate, and
  false negative rate use the Python scoring result.
- Retrieval: reuse `evaluate_retrieval_quality` for recall@k, precision@k,
  MRR, source coverage, and expected chunk retrieval.
- Structured output: JSON parse success and Pydantic validation results.
- Grounding: deterministic evidence/claim coverage before any judge model.
- Tool use: typed tool events, selected tool, status, timeout, and retry data.
- Outreach: deterministic placeholder, CTA, length, personalization, and
  prohibited-content checks before any subjective judge.
- Safety: expected denial/degradation behavior for adversarial fixtures.

## Execution Policy

- Unit and integration evaluators must not call external APIs by default.
- Provider-backed and end-to-end cases require explicit opt-in flags.
- LLM-as-judge is optional, temperature-controlled, versioned, and used only
  where deterministic checks cannot represent the requirement.
- Normal Codex iterations do not run the eval suite automatically.
- Eval output is written under `evals/results/` only when explicitly invoked.

## Milestone Sequence

1. Typed contracts and focused contract tests.
2. Dataset files with a small reviewed seed set and schema loading.
3. Deterministic scoring and structured-output evaluators.
4. Retrieval evaluator adapter and retrieval dataset.
5. Grounding, tool-use, outreach, and adversarial evaluators.
6. Local runner and JSON result output.
7. Expand golden data to at least 30 curated cases.
8. Optional cost-controlled LLM-as-judge and opt-in end-to-end workflow.

## Milestone 7.1 Acceptance

- Dataset and result contracts are strict and versioned.
- Duplicate case IDs are rejected.
- Empty expectations are rejected.
- External-provider execution defaults to disabled.
- No runtime graph, API, frontend, provider, or dependency behavior changes.

## Milestone 7.2 Acceptance

- Golden, adversarial, and retrieval seed files load through strict contracts.
- Seed cases are synthetic and provider-free by default.
- Duplicate IDs and schema-invalid or malformed JSON are rejected.
- Loader failures do not echo fixture contents.
- Generated result files remain ignored until an eval run is explicitly
  requested.

## Milestone 7.3 Acceptance

- Scoring cases validate domain inputs and reuse the production Python scoring
  engine.
- Classification, score-range deviation, and human-review behavior are
  inspectable per case.
- Structured-output cases report JSON validity, missing required fields,
  Pydantic validation, and invalid enum counts.
- Invalid fixtures produce sanitized failed case results instead of escaping
  exceptions.
- No model/provider calls or runner output are introduced.

## Milestone 7.4 Acceptance

- Retrieval fixtures contain synthetic ranked chunks and dataset-owned metric
  thresholds.
- Existing Phase 4 retrieval metrics remain the single implementation for
  recall@k, precision@k, MRR, source coverage, and expected chunk retrieval.
- Malformed chunks produce sanitized failed case results.
- Evaluation does not execute retrieval, embeddings, or vector storage.

## Milestone 7.5 Acceptance

- Grounding evaluation reuses deterministic scoring and grounding engines over
  validated fixtures.
- Unsupported-claim, evidence-coverage, and missing-source rates are
  inspectable against dataset thresholds.
- Outreach evaluation reuses the deterministic quality engine and reports
  quality score, personalization density, spam incidence, CTA, placeholders,
  and approval gating.
- Invalid fixtures return sanitized failed case results.

## Milestone 7.6 Acceptance

- Tool-use evaluation consumes validated, sanitized recorded metadata and never
  invokes a tool.
- Tool selection, expected status/graceful handling, timeout behavior, retry
  budgets, and approval gating are inspectable.
- Safety URL cases invoke only the pure pre-fetch URL validator.
- Prompt-injection cases require untrusted labeling and a recorded
  `treated_as_data` instruction-boundary outcome.
- These offline observations do not claim to replace later opt-in end-to-end
  adversarial tests.

## Milestone 7.7 Acceptance

- A local dispatcher routes every current category to its deterministic
  evaluator.
- Provider-required cases are refused rather than executed implicitly.
- Aggregate scoring reports classification accuracy, average score deviation,
  false-positive rate, and false-negative rate with explicit thresholds.
- `evals/run_eval.py` supports dataset/category selection and writes only the
  sanitized versioned run-result model when explicitly invoked.
- Result exit status reflects both case failures and aggregate quality gates.

## Milestone 7.8 Acceptance

- Coverage reporting counts categories, tags, provider requirements, and
  missing dataset-kind-specific categories without running evaluators.
- Golden coverage reports its explicit gap to the 30-case target.
- Retrieval and adversarial datasets retain their dedicated category surfaces
  instead of being treated as missing golden categories.

## Milestone 7.9 Acceptance

- Golden data expands from five to ten reviewed provider-free cases.
- New scoring coverage includes medium fit, generic mode, and red-flag review
  behavior derived from established deterministic tests.
- New structured-output coverage includes minimal serialized API output and
  explicit stubbed-delivery state.
- Coverage reports a 20-case gap rather than treating this slice as complete.

## Milestone 7.10 Acceptance

- Golden data expands from ten to fifteen reviewed provider-free cases.
- Grounding cases require detection of uncited URLs and profile-backed claims
  without profile sources.
- Outreach cases require detection of placeholders, spam language, and missing
  CTA/short-copy quality failures.
- Negative examples pass only when deterministic evaluators detect the expected
  degraded behavior.
- Coverage reports a 15-case gap rather than treating this slice as complete.
