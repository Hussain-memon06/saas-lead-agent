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
  | "leadership"
  | "partnership"
  | "other";

/**
 * Mirrors the backend's signal shape exactly (see
 * `agents/signal_detector.py`): `signal_type`, `details`, `date`, `source`.
 * Earlier versions of this type used `type/title/summary/url` and silently
 * fell back to empty UI — the rename here fixes that.
 */
export type Signal = {
  signal_type: SignalType | string;
  details: string;
  date: string | null;
  source: string;
};

export type SendResult = "sent" | "rejected" | "no_contact" | "failed";

// ---------------------------------------------------------------------------
// Request / response models (POST /api/qualify, /approve, /reject)
// ---------------------------------------------------------------------------

export type QualifyRequest = {
  url: string;
  icp_context?: Record<string, unknown> | null;
};

export type QualifyResponse = {
  thread_id: string;
  company_profile: CompanyProfile | null;
  contact: Contact | null;
  signals: Signal[] | null;
  fit_score: number | null; // 1-10
  score_explanation: string | null; // e.g. "9/10 — B2B SaaS ✅, Series C ✅, …"
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
