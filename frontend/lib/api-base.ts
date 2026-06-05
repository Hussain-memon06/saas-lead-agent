/**
 * Resolve the base URL the frontend uses to reach the FastAPI backend.
 *
 * - Dev: `NEXT_PUBLIC_API_BASE_URL` is unset, so we return an empty string
 *   and let Next.js `rewrites()` proxy `/api/*` to localhost:8080.
 * - Prod: set `NEXT_PUBLIC_API_BASE_URL=https://api.outbound-lead-agent.example.com` (or
 *   wherever the backend lives); we prepend it to every path.
 *
 * Always call paths starting with `/` so the join below is safe in both
 * modes.
 */
export function apiBase(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
}

/**
 * Join the configured base with a path. Prevents double slashes and the
 * common "forgot to set the env var" footgun that produces `undefined/api/...`.
 */
export function apiUrl(path: string): string {
  if (!path.startsWith("/")) {
    throw new Error(`apiUrl path must start with "/" — got: ${path}`);
  }
  return `${apiBase()}${path}`;
}
