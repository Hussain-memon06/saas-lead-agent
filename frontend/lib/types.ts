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

export type QualifyRequest = {
  url: string;
  icp_context?: Record<string, unknown> | null;
};

export type QualifyResponse = {
  request_id: string | null;
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
  thread_id: string;
  email_approved: boolean | null;
  send_result: SendResult | null;
  message_id: string | null;
  sent_at: string | null;
  interrupted: boolean;
  errors: string[];
};
