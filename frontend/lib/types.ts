/**
 * TypeScript types mirroring the FastAPI backend's Pydantic schemas.
 *
 * These are hand-written for Phase 1 — keep them in sync with
 * `src/saas_lead_agent/api/schemas.py` and the LeadState in
 * `src/saas_lead_agent/state.py`.  Phase 4 follow-up: generate from
 * /openapi.json via openapi-typescript.
 */

// ---------------------------------------------------------------------------
// Sub-shapes (derived from agent fixtures and the LangGraph state contract)
// ---------------------------------------------------------------------------

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
  | "techstack"
  | "leadership"
  | "partnership"
  | "other";

export type Signal = {
  type: SignalType | string; // backend may emit additional types
  title: string;
  summary?: string | null;
  url?: string | null;
  date?: string | null;
};

export type SendResult = "sent" | "rejected" | "no_contact" | "failed";

// ---------------------------------------------------------------------------
// Request / response models (POST /api/qualify, /approve, /reject)
// ---------------------------------------------------------------------------

export type QualifyRequest = {
  url: string;
};

export type QualifyResponse = {
  thread_id: string;
  company_profile: CompanyProfile | null;
  contact: Contact | null;
  signals: Signal[] | null;
  fit_score: number | null; // 1-10
  email_subject: string | null;
  email_body: string | null;
  email_approved: boolean | null;
  send_result: SendResult | null;
  message_id: string | null;
  sent_at: string | null; // ISO-8601
  interrupted: boolean;
  errors: string[];
};

export type ApproveResponse = {
  thread_id: string;
  email_approved: boolean | null;
  send_result: SendResult | null;
  message_id: string | null;
  sent_at: string | null;
  interrupted: boolean;
  errors: string[];
};
