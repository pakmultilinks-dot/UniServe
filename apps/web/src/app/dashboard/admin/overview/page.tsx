"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { getAdministrationOverview, getCafeterias } from "@/lib/api";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import type { Cafeteria } from "@uniserve/shared-types";

interface OverviewData {
  total_users: number;
  users_by_role: Record<string, number>;
  total_orders: number;
  orders_by_status: Record<string, number>;
  total_revenue: number;
  active_cafeterias: number;
  pending_refunds: number;
  total_menu_items: number;
}

export default function AdminOverviewPage() {
  const { user } = useAuth();
  const router = useRouter();
  const isAdmin = user?.role === "university_admin";

  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [cafeterias, setCafeterias] = useState<Cafeteria[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAdmin) {
      router.push("/dashboard");
      return;
    }
    Promise.all([
      getAdministrationOverview().catch(() => null),
      getCafeterias().catch(() => []),
    ]).then(([overviewData, cafData]) => {
      setOverview(overviewData);
      setCafeterias(cafData);
    }).finally(() => setLoading(false));
  }, [isAdmin, router]);

  const formatCurrency = (amount: number) => `Rs. ${amount.toLocaleString("en-PK")}`;

  if (!isAdmin) return null;

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

          {/* Pending refunds alert */}
          {overview.pending_refunds > 0 && (
            <div className="bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800 rounded-xl p-4 flex items-center gap-3">
              <span className="text-2xl">⚠️</span>
              <div>
                <p className="text-sm font-medium text-orange-800 dark:text-orange-300">
                  {overview.pending_refunds} pending refund{overview.pending_refunds !== 1 ? "s" : ""} requiring review
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