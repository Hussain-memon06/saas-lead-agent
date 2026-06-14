/**
 * TypeScript types mirroring the FastAPI backend's Pydantic schemas.
 *
 * These are hand-written for now; keep them in sync with
 * `src/saas_lead_agent/api/schemas.py` and the LeadState in
 * `src/saas_lead_agent/state.py`.
 */

export type CompanyProfile = {
  name: string;
  tagline?: string | null;
  hq?: string | null;
  employees_estimate?: string | null;
  funding_stage?: string | null;
  products?: string[] | null;
  notable_customers?: string[] | null;
  sources?: string[] | null;
};

export type Contact = {
  name: string | null;
  title: string | null;
  email: string | null;
  linkedin: string | null;
  confidence: number | null;
  source: string;
};

export type SignalType =
  | "funding"
  | "hiring"
  | "product"
  | "leadership"
  | "partnership"
  | "other";

export type Signal = {
  signal_type: SignalType | string;
  details: string;
  date: string | null;
  source: string;
};

export type SendResult = "sent" | "stubbed" | "rejected" | "no_contact" | "failed";

export type ScoreBreakdown = {
  baseline: number;
  profile_completeness: number;
  industry_match: number;
  stage_match: number;
  geography_match: number;
  company_size_fit: number;
  signal_strength: number;
  contact_quality: number;
  red_flag_penalty: number;
};

export type EvidenceItem = {
  claim: string;
  source_text: string;
  source_location: string;
  source_url: string | null;
  confidence: "low" | "medium" | "high";
};

export type GroundingReport = {
  evidence: {
    items: EvidenceItem[];
  };
  source_urls: string[];
  supported_claim_count: number;
  unsupported_claims: string[];
  missing_source_count: number;
  evidence_coverage: number;
  is_sufficient: boolean;
};

export type OutreachQuality = {
  quality_score: number;
  passed: boolean;
  issues: string[];
  personalization_hooks: string[];
  spam_terms: string[];
  placeholder_terms: string[];
  word_count: number;
};

export type ProcessingMetadata = {
  run_id: string;
  thread_id: string;
  model_used: string | null;
  total_tokens: number;
  estimated_cost_usd: number;
  timings_ms: Record<string, number>;
  token_usage: Record<string, number>;
  cost_breakdown_usd: Record<string, number>;
  provider_status: Record<string, string>;
  retrieval_events: Array<Record<string, unknown>>;
  duration_seconds: number;
  steps_completed: string[];
  errors: string[];
  started_at: string;
  completed_at: string | null;
};

export type QualifyRequest = {
  url: string;
  icp_context?: Record<string, unknown> | null;
};

export type QualifyResponse = {
  request_id: string | null;
  run_id: string | null;
  thread_id: string;
  company_profile: CompanyProfile | null;
  contact: Contact | null;
  signals: Signal[] | null;
  fit_score: number | null;
  fit_level: string | null;
  score_breakdown: ScoreBreakdown | null;
  score_confidence: string | null;
  score_explanation: string | null;
  needs_human_review: boolean | null;
  score_reasons: string[] | null;
  score_uncertainty: string[] | null;
  grounding_report: GroundingReport | null;
  outreach_quality: OutreachQuality | null;
  processing_metadata: ProcessingMetadata | null;
  email_subject: string | null;
  email_body: string | null;
  email_approved: boolean | null;
  send_result: SendResult | null;
  message_id: string | null;
  sent_at: string | null;
  interrupted: boolean;
  errors: string[];
};

export type ApproveResponse = {
  request_id: string | null;
  run_id: string | null;
  thread_id: string;
  email_approved: boolean | null;
  send_result: SendResult | null;
  message_id: string | null;
  sent_at: string | null;
  processing_metadata: ProcessingMetadata | null;
  interrupted: boolean;
  errors: string[];
};

export type LeadSummary = {
  request_id: string | null;
  run_id: string;
  thread_id: string;
  domain: string;
  company_url: string;
  company_name: string | null;
  status: string;
  fit_score: number | null;
  fit_level: string | null;
  score_confidence: string | null;
  needs_human_review: boolean | null;
  interrupted: boolean;
  send_result: SendResult | null;
  total_tokens: number;
  estimated_cost_usd: number;
  duration_seconds: number;
  created_at: string;
  updated_at: string;
};

export type LeadListResponse = {
  request_id: string | null;
  leads: LeadSummary[];
};

export type RunEventResponse = {
  run_id: string;
  thread_id: string;
  event_type: string;
  metadata: Record<string, unknown>;
  request_id: string | null;
  created_at: string;
};

export type RunEventsResponse = {
  request_id: string | null;
  thread_id: string;
  events: RunEventResponse[];
};
