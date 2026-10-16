/**
 * Host-independent menu-image URL resolver (Phase 48).
 *
 * The API persists image references in the host-independent form
 * `/api/v1/static/food/<file>` (migration 0011 + new uploads). Rendering
 * must attach the configured API origin at read time, so the same database
 * value works on localhost, LAN IPs and production hosts.
 *
 * Absolute http(s) URLs pass through untouched (legacy values, other hosts).
 */

// Same configuration source and fallback as lib/api.ts (module-private there).
// Production builds fail loudly in next.config.js when NEXT_PUBLIC_API_URL
// is unset, so the localhost fallback below only ever applies in development.
const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/** API origin derived from API_BASE_URL (scheme://host[:port] only). */
const API_ORIGIN = API_BASE_URL.replace(/\/api\/v1\/?$/, "");

/**
 * Resolve a persisted image reference to a renderable URL.
 *
 * - `null`/`""` → `null` (callers fall back to placeholders).
 * - `http(s)://…` → returned as-is.
 * - `/api/v1/…` (or any relative path) → API_ORIGIN + path.
 */
export function resolveApiImageUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  if (/^https?:\/\//i.test(url)) return url;
  if (url.startsWith("/")) return `${API_ORIGIN}${url}`;
  // Defensive: unknown relative form — treat as static path.
  return `${API_ORIGIN}/api/v1/static/food/${url}`;
}
