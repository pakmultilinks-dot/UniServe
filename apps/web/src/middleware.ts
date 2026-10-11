/**
 * UniServe — Next.js Middleware (DEVELOPMENT ONLY)
 *
 * Protects /dashboard routes in `next dev`: if the lightweight session flag
 * cookie is absent, redirect to /login. This cookie is set by the web token
 * provider when tokens are stored and cleared when they are removed.
 *
 * IMPORTANT — READ BEFORE RELYING ON THIS FILE:
 * The production web app ships as a static export (`output: "export"` in
 * next.config.js) served by Caddy. There is NO Next.js server runtime in
 * production, so this middleware NEVER EXECUTES there. The real,
 * always-on enforcement points are:
 *   1. client-side `src/components/RoleGuard.tsx` (route-level UX guard), and
 *   2. server-side RBAC in the FastAPI backend (authoritative — every
 *      /dashboard page only renders data the API authorizes).
 * This cookie is NOT proof of authentication. It is a routing hint —
 * "this browser might have tokens." Real authentication validation happens
 * client-side in AuthContext via silent token refresh. If the cookie is
 * stale or forged, the client-side guard catches it and redirects to /login.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = [
  "/login",
  "/register",
  "/verify-email",
  "/forgot-password",
  "/reset-password",
  "/mobile-required",
  "/api",
];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow public paths and static assets
  if (
    PUBLIC_PATHS.some((p) => pathname.startsWith(p)) ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/favicon")
  ) {
    return NextResponse.next();
  }

  // For dashboard routes, check for the session flag cookie.
  // Absence = definitely no tokens stored → redirect to login.
  // Presence = tokens may exist → let page load, client-side validates.
  const sessionFlag = request.cookies.get("uniserve_session");

  if (pathname.startsWith("/dashboard") && !sessionFlag) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*"],
};
