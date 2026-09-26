/**
 * UniServe — Next.js Middleware
 *
 * Protects /dashboard routes: if no refresh token is stored in
 * sessionStorage, redirect to /login. The actual session validation
 * happens client-side in AuthContext via silent refresh.
 *
 * NOTE: This is a lightweight guard. Full token verification happens
 * server-side via the API's auth middleware.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = ["/login", "/register", "/verify-email", "/api"];

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

  // For dashboard routes, check for a session indicator cookie
  // The actual token lives in sessionStorage (in-memory for access,
  // sessionStorage for refresh). We use a lightweight flag cookie
  // to avoid redirecting every page load to the server.
  //
  // If no session exists, redirect to login — AuthContext will handle
  // the full validation client-side.
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
