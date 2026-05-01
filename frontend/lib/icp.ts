/**
 * ICP (Ideal Customer Profile) — client-side storage and shape.
 *
 * Persisted in localStorage under `STORAGE_KEY`.  The same shape is
 * sent to the backend as `icp_context` on every /api/qualify call so
 * the dossier_writer can score against the user's actual targets.
 *
 * Field naming matches the snake_case shape the backend prompt reads,
 * so the JSON we ship over the wire is the same object we round-trip
 * through localStorage — no mapping layer.
 */

import { useEffect, useState } from "react";

export const STORAGE_KEY = "dossify_icp";

/** Custom event the save/clear helpers dispatch so `useIcp()` subscribers
 *  in the same tab see updates immediately (the native `storage` event
 *  only fires across tabs, not within the tab that wrote the value). */
const CHANGE_EVENT = "dossify-icp-change";

export type IcpContext = {
  seller_name: string;
  offering: string;
  target_industries: string[];
  target_stages: string[];
  target_geographies: string[];
  target_employees: string;
  must_have_signals: string[];
  red_flags: string[];
  value_proposition: string;
};

export const INDUSTRY_OPTIONS = [
  "B2B SaaS",
  "Fintech",
  "DevTools",
  "Healthcare",
  "MarTech",
  "HR Tech",
  "LegalTech",
  "Ecommerce",
  "Other",
] as const;

export const STAGE_OPTIONS = [
  "Seed",
  "Series A",
  "Series B",
  "Series C",
  "Series D+",
  "Public",
  "Bootstrapped",
] as const;

export const GEOGRAPHY_OPTIONS = [
  "US",
  "UK",
  "EU",
  "Canada",
  "Australia",
  "Global",
] as const;

export const EMPLOYEE_RANGE_OPTIONS = [
  "Any",
  "1-10",
  "11-50",
  "51-200",
  "201-500",
  "501-1000",
  "1000+",
] as const;

export const MUST_HAVE_SIGNAL_OPTIONS = [
  "Recent funding",
  "Hiring sales team",
  "Product launch",
  "New market expansion",
  "Leadership change",
  "Partnership announcement",
  "IPO preparation",
] as const;

export const RED_FLAG_OPTIONS = [
  "Pre-revenue",
  "Consumer app",
  "Gaming",
  "Solo founder",
  "Free-tier only",
  "Recent layoffs",
  "Competitor of existing client",
] as const;

export const EMPTY_ICP: IcpContext = {
  seller_name: "",
  offering: "",
  target_industries: [],
  target_stages: [],
  target_geographies: [],
  target_employees: "Any",
  must_have_signals: [],
  red_flags: [],
  value_proposition: "",
};

/** A saved ICP "counts" once any meaningful field is filled in. */
export function isIcpConfigured(icp: IcpContext | null): boolean {
  if (!icp) return false;
  return Boolean(
    icp.seller_name.trim() ||
      icp.offering.trim() ||
      icp.value_proposition.trim() ||
      icp.target_industries.length > 0 ||
      icp.target_stages.length > 0 ||
      icp.target_geographies.length > 0 ||
      icp.must_have_signals.length > 0 ||
      icp.red_flags.length > 0,
  );
}

export function loadIcp(): IcpContext | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<IcpContext>;
    return { ...EMPTY_ICP, ...parsed };
  } catch {
    return null;
  }
}

export function saveIcp(icp: IcpContext): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(icp));
  window.dispatchEvent(new CustomEvent(CHANGE_EVENT));
}

export function clearIcp(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(STORAGE_KEY);
  window.dispatchEvent(new CustomEvent(CHANGE_EVENT));
}

/**
 * Reactive hook: returns the current ICP and whether one is configured.
 * Re-reads on cross-tab `storage` events and on our intra-tab
 * `dossify-icp-change` event so the header badge stays in sync.
 */
export function useIcp(): { icp: IcpContext | null; configured: boolean } {
  const [icp, setIcp] = useState<IcpContext | null>(null);

  useEffect(() => {
    const refresh = () => setIcp(loadIcp());
    refresh();
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY || e.key === null) refresh();
    };
    window.addEventListener("storage", onStorage);
    window.addEventListener(CHANGE_EVENT, refresh);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener(CHANGE_EVENT, refresh);
    };
  }, []);

  return { icp, configured: isIcpConfigured(icp) };
}
