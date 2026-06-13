/**
 * Typed fetch wrappers for the FastAPI backend.
 *
 * Current backend endpoints:
 *   /api/qualify                            { url } -> QualifyResponse
 *   /api/leads                              -> LeadListResponse
 *   /api/leads/{thread_id}                  -> QualifyResponse
 *   /api/leads/{thread_id}/events           -> RunEventsResponse
 *   /api/leads/{thread_id}/approve          (no body) -> ApproveResponse
 *   /api/leads/{thread_id}/reject           (no body) -> ApproveResponse
 *
 * thread_id format is `lead:{domain}` — the colon must be URL-encoded
 * (handled here, callers pass it raw).
 *
 * Qualify can take 60-90 s; we set a 120 s AbortController timeout so a
 * stuck backend doesn't hang the tab forever.
 */

import { apiUrl } from "./api-base";
import { isIcpConfigured, loadIcp } from "./icp";
import type {
  ApproveResponse,
  LeadListResponse,
  QualifyRequest,
  QualifyResponse,
  RunEventsResponse,
} from "./types";

const QUALIFY_TIMEOUT_MS = 120_000;
const RESUME_TIMEOUT_MS = 60_000;

/** Thrown when the backend returns a non-2xx response. */
export class ApiError extends Error {
  status: number;
  detail?: string;
  errors?: string[];

  constructor(status: number, message: string, detail?: string, errors?: string[]) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.errors = errors;
  }
}

async function postJson<TResponse>(
  path: string,
  body: unknown,
  timeoutMs: number,
): Promise<TResponse> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      method: "POST",
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    });
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new ApiError(
        0,
        `Request timed out after ${Math.round(timeoutMs / 1000)} s`,
      );
    }
    throw new ApiError(
      0,
      err instanceof Error ? err.message : "Network error",
    );
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    // Try to parse FastAPI / Pydantic error body for a helpful message.
    let detail: string | undefined;
    let errors: string[] | undefined;
    try {
      const payload = (await response.json()) as {
        detail?: string | { msg?: string }[];
        errors?: string[];
      };
      if (typeof payload.detail === "string") {
        detail = payload.detail;
      } else if (Array.isArray(payload.detail)) {
        // Pydantic validation errors
        detail = payload.detail
          .map((d) => d?.msg)
          .filter(Boolean)
          .join("; ");
      }
      errors = payload.errors;
    } catch {
      // body was not JSON — leave detail undefined
    }
    throw new ApiError(
      response.status,
      detail || `Request failed with status ${response.status}`,
      detail,
      errors,
    );
  }

  return (await response.json()) as TResponse;
}

async function getJson<TResponse>(
  path: string,
  timeoutMs: number,
): Promise<TResponse> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      method: "GET",
      signal: ctrl.signal,
    });
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new ApiError(
        0,
        `Request timed out after ${Math.round(timeoutMs / 1000)} s`,
      );
    }
    throw new ApiError(
      0,
      err instanceof Error ? err.message : "Network error",
    );
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    let detail: string | undefined;
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload.detail;
    } catch {
      // body was not JSON; leave detail undefined
    }
    throw new ApiError(
      response.status,
      detail || `Request failed with status ${response.status}`,
      detail,
    );
  }

  return (await response.json()) as TResponse;
}

export async function qualify(req: QualifyRequest): Promise<QualifyResponse> {
  // Always read the latest ICP from localStorage at call time so the user
  // doesn't have to refresh after editing settings.  An unconfigured ICP
  // is sent as `null` — the backend prompt branches on presence.
  const stored = loadIcp();
  const icp_context = isIcpConfigured(stored) ? stored : null;
  return postJson<QualifyResponse>(
    "/api/qualify",
    { ...req, icp_context },
    QUALIFY_TIMEOUT_MS,
  );
}

export async function getLead(threadId: string): Promise<QualifyResponse> {
  const encoded = encodeURIComponent(threadId);
  return getJson<QualifyResponse>(`/api/leads/${encoded}`, RESUME_TIMEOUT_MS);
}

export async function listLeads(limit = 20): Promise<LeadListResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  return getJson<LeadListResponse>(`/api/leads?${params.toString()}`, RESUME_TIMEOUT_MS);
}

export async function getLeadEvents(threadId: string): Promise<RunEventsResponse> {
  const encoded = encodeURIComponent(threadId);
  return getJson<RunEventsResponse>(`/api/leads/${encoded}/events`, RESUME_TIMEOUT_MS);
}

export async function approve(threadId: string): Promise<ApproveResponse> {
  const encoded = encodeURIComponent(threadId);
  return postJson<ApproveResponse>(
    `/api/leads/${encoded}/approve`,
    undefined,
    RESUME_TIMEOUT_MS,
  );
}

export async function reject(threadId: string): Promise<ApproveResponse> {
  const encoded = encodeURIComponent(threadId);
  return postJson<ApproveResponse>(
    `/api/leads/${encoded}/reject`,
    undefined,
    RESUME_TIMEOUT_MS,
  );
}
