/**
 * UniServe — Web Dashboard Role Definitions
 *
 * Centralized definition of which roles may access the web dashboard
 * (localhost:3000). The web dashboard is intended ONLY for:
 *
 *   - university_admin
 *   - cafeteria_manager
 *   - cafeteria_staff
 *
 * Students and faculty use the mobile app (localhost:8081) for ordering.
 *
 * This module is the single source of truth for web-dashboard role checks.
 * Do not duplicate these role lists elsewhere.
 */

import type { UserRole } from "@uniserve/shared-types";

/** Roles allowed to access the web dashboard at /dashboard/* */
export const WEB_DASHBOARD_ROLES: readonly UserRole[] = [
  "university_admin",
  "cafeteria_manager",
  "cafeteria_staff",
];

/** Roles that belong on the mobile app (used for messaging / redirects) */
export const MOBILE_APP_ROLES: readonly UserRole[] = ["student", "faculty"];

/**
 * Returns true if the given role is allowed to access the web dashboard.
 * Students and faculty return false — they must use the mobile app.
 */
export function isWebDashboardRole(
  role: UserRole | undefined | null,
): boolean {
  return !!role && (WEB_DASHBOARD_ROLES as readonly UserRole[]).includes(role);
}

/**
 * Returns true if the given role belongs on the mobile app.
 */
export function isMobileAppRole(
  role: UserRole | undefined | null,
): boolean {
  return !!role && (MOBILE_APP_ROLES as readonly UserRole[]).includes(role);
}
