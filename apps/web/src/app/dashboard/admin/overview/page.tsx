"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { getAdministrationOverview, getCafeterias, getApiErrorInfo } from "@/lib/api";
import type { ApiErrorInfo } from "@/lib/api";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { LoadErrorState } from "@/components/ui/LoadErrorState";
import type { Cafeteria } from "@uniserve/shared-types";

interface OverviewData {
  total_users: number;
  users_by_role: Record<string, number>;
  total_orders: number;
  orders_by_status: Record<string, number>;
  total_revenue: number;
  active_cafeterias: number;
  // Phase 55 — honest label: refunds pending/processing beyond 7 days.
  overdue_refunds: number;
  total_menu_items: number;
}

export default function AdminOverviewPage() {
  const { user } = useAuth();
  const router = useRouter();
  const isAdmin = user?.role === "university_admin";

  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [cafeterias, setCafeterias] = useState<Cafeteria[]>([]);
  const [loading, setLoading] = useState(true);
  /* Phase 46 — explicit request-failure states (see LoadErrorState). A
     failed request must never masquerade as missing data. */
  const [loadError, setLoadError] = useState<ApiErrorInfo | null>(null);
  const [cafeteriasError, setCafeteriasError] = useState<ApiErrorInfo | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (user && !isAdmin) {
      router.push("/dashboard");
      return;
    }
    if (!isAdmin) return;
    // Phase 46 — each request owns its failure state; no more
    // catch(() => null / []) that silently fabricates missing data.
    getAdministrationOverview()
      .then((data) => {
        setOverview(data);
        setLoadError(null);
      })
      .catch((err) => setLoadError(getApiErrorInfo(err)))
      .finally(() => setLoading(false));
    getCafeterias()
      .then((data) => {
        setCafeterias(data);
        setCafeteriasError(null);
      })
      .catch((err) => setCafeteriasError(getApiErrorInfo(err)));
  }, [user, isAdmin, router, reloadKey]);

  // getAdministrationOverview (lib/api.ts) already converts paisa -> rupees
  // in exactly one layer; do not divide by 100 again here.
  const formatCurrency = (amount: number) => `Rs. ${amount.toLocaleString("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  if (!user || !isAdmin) return null;

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Administration Overview"
        description="Platform-wide statistics and management"
      />

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl skeleton" />
          ))}
        </div>
      ) : loadError ? (
        <LoadErrorState
          error={loadError}
          subject="administration overview"
          onRetry={() => setReloadKey((k) => k + 1)}
        />
      ) : overview ? (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-4 shadow-card">
              <p className="text-xs font-medium text-[var(--text-muted)] uppercase">Total Users</p>
              <p className="text-2xl font-bold text-[var(--text-primary)] mt-1">{overview.total_users}</p>
              <div className="flex flex-wrap gap-1 mt-2">
                {Object.entries(overview.users_by_role ?? {}).map(([role, count]) => (
                  <span key={role} className="text-[10px] px-1.5 py-0.5 rounded bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-300 capitalize">
                    {role.replace(/_/g, " ")}: {count}
                  </span>
                ))}
              </div>
            </div>
            <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-4 shadow-card">
              <p className="text-xs font-medium text-[var(--text-muted)] uppercase">Total Orders</p>
              <p className="text-2xl font-bold text-[var(--text-primary)] mt-1">{overview.total_orders}</p>
              <div className="flex flex-wrap gap-1 mt-2">
                {Object.entries(overview.orders_by_status ?? {}).slice(0, 3).map(([status, count]) => (
                  <span key={status} className="text-[10px]">
                    <StatusBadge status={status} /> <span className="text-[var(--text-muted)]">{count}</span>
                  </span>
                ))}
              </div>
            </div>
            <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-4 shadow-card">
              <p className="text-xs font-medium text-[var(--text-muted)] uppercase">Total Revenue</p>
              <p className="text-2xl font-bold text-green-600 dark:text-green-400 mt-1">{formatCurrency(overview.total_revenue)}</p>
            </div>
            <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-4 shadow-card">
              <p className="text-xs font-medium text-[var(--text-muted)] uppercase">Active Cafeterias</p>
              <p className="text-2xl font-bold text-[var(--text-primary)] mt-1">{overview.active_cafeterias}</p>
              <p className="text-xs text-[var(--text-muted)] mt-1">{overview.total_menu_items} menu items</p>
            </div>
          </div>

          {/* Cafeteria cards */}
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">Cafeterias</h3>
          {cafeteriasError ? (
            <LoadErrorState
              compact
              error={cafeteriasError}
              subject="cafeterias"
              onRetry={() => setReloadKey((k) => k + 1)}
              className="border border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-900/10 rounded-xl"
            />
          ) : cafeterias.length === 0 ? (
            <p className="text-sm text-[var(--text-muted)] mb-6">
              No cafeterias to display.
            </p>
          ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            {cafeterias.map((c) => (
              <div key={c.id} className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-4 shadow-card">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-semibold text-[var(--text-primary)]">{c.name}</h4>
                    <p className="text-xs text-[var(--text-muted)]">{c.location}</p>
                  </div>
                  <StatusBadge status={c.operational_status} />
                </div>
              </div>
            ))}
          </div>
          )}

          {/* Phase 55 — overdue refunds alert (honest wording: the count is
              refunds pending/processing for more than 7 days, not all
              pending refunds) */}
          {overview.overdue_refunds > 0 && (
            <div className="bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800 rounded-xl p-4 flex items-center gap-3">
              <svg className="w-6 h-6 text-orange-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
              </svg>
              <div>
                <p className="text-sm font-medium text-orange-800 dark:text-orange-300">
                  {overview.overdue_refunds} overdue refund{overview.overdue_refunds !== 1 ? "s" : ""}
                </p>
                <p className="text-xs text-orange-600 dark:text-orange-400 mt-0.5">
                  Refunds pending or processing for more than 7 days that need review.
                </p>
                <button
                  onClick={() => router.push("/dashboard/admin/refunds")}
                  className="text-xs text-orange-600 dark:text-orange-400 underline mt-0.5"
                >
                  View Refunds →
                </button>
              </div>
            </div>
          )}
        </>
      ) : (
        <p className="text-sm text-[var(--text-muted)]">Failed to load overview data.</p>
      )}
    </div>
  );
}