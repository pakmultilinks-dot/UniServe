/**
 * UniServe — Role Guard Component
 *
 * Wraps the dashboard layout to enforce the web/mobile role boundary.
 *
 * Behaviour:
 *   - While auth state is loading  → render a neutral loading spinner
 *     (no dashboard flash).
 *   - If not authenticated          → redirect to /login.
 *   - If role is not in WEB_DASHBOARD_ROLES
 *                                  → redirect to /mobile-required.
 *   - Otherwise                    → render children (the dashboard).
 *
 * This is a UX/access-routing guard. Backend RBAC remains the authoritative
 * security enforcement — this component never replaces it.
 */

"use client";

import React, { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { isWebDashboardRole } from "@/lib/roles";

function LoadingScreen({ message }: { message: string }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--bg-secondary)]">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-2 border-brand-700 border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-[var(--text-muted)]">{message}</p>
      </div>
    </div>
  );
}

export function RoleGuard({ children }: { children: React.ReactNode }) {
  const { user, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (isLoading) return;

    if (!isAuthenticated || !user) {
      const loginUrl = new URL("/login", window.location.origin);
      loginUrl.searchParams.set("redirect", pathname);
      router.replace(loginUrl.pathname + loginUrl.search);
      return;
    }

    if (!isWebDashboardRole(user.role)) {
      router.replace("/mobile-required");
    }
  }, [isLoading, isAuthenticated, user, pathname, router]);

  // Auth still loading — neutral spinner, no dashboard flash
  if (isLoading) {
    return <LoadingScreen message="Loading..." />;
  }

  // Not authenticated or wrong role — spinner while redirect completes
  if (!isAuthenticated || !user || !isWebDashboardRole(user.role)) {
    return <LoadingScreen message="Redirecting..." />;
  }

  return <>{children}</>;
}
