"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { getSalesReport, getCafeterias } from "@/lib/api";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import type { Cafeteria } from "@uniserve/shared-types";

// Flat shape produced by getSalesReport (lib/api.ts) after unwrapping the
// backend SalesReportResponse.summary. All money values are in paisa.
interface SalesData {
  total_orders: number;
  total_revenue: number;
  net_revenue: number;
  total_refunded: number;
}

export default function ReportsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const isAdmin = user?.role === "university_admin";
  const isManager = user?.role === "cafeteria_manager";

  const [cafeterias, setCafeterias] = useState<Cafeteria[]>([]);
  const [selectedCafeteria, setSelectedCafeteria] = useState("");
  const [dateRange, setDateRange] = useState("7d");
  const [salesData, setSalesData] = useState<SalesData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user && !isAdmin && !isManager) {
      router.push("/dashboard");
      return;
    }
    if (!isAdmin && !isManager) return;
    getCafeterias().then((data) => {
      setCafeterias(data);
      if (data.length > 0) setSelectedCafeteria(data[0].id);
    }).catch(() => {});
  }, [user, isAdmin, isManager, router]);

  useEffect(() => {
    if (!selectedCafeteria) return;
    setLoading(true);

    const now = new Date();
    const toDateStr = (d: Date) => d.toISOString().split("T")[0];
    let start: string;
    if (dateRange === "7d") start = toDateStr(new Date(now.getTime() - 7 * 86400000));
    else if (dateRange === "30d") start = toDateStr(new Date(now.getTime() - 30 * 86400000));
    else start = toDateStr(new Date(now.getFullYear(), now.getMonth(), 1));

    getSalesReport({ cafeteria_id: selectedCafeteria, start_date: start, end_date: toDateStr(now) })
      .then((data) => setSalesData(data))
      .catch(() => setSalesData(null))
      .finally(() => setLoading(false));
  }, [selectedCafeteria, dateRange]);

  const formatCurrency = (amount: number) => `Rs. ${(amount / 100).toLocaleString("en-PK", { minimumFractionDigits: 0 })}`;

  if (!user || (!isAdmin && !isManager)) return null;

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Sales Reports"
        description="Revenue analytics and order insights"
        actions={
          <div className="flex items-center gap-2">
            <select
              value={selectedCafeteria}
              onChange={(e) => setSelectedCafeteria(e.target.value)}
              className="px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
            >
              {cafeterias.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            <div className="flex rounded-lg border border-[var(--border-default)] overflow-hidden">
              {(["7d", "30d", "month"] as const).map((range) => (
                <button
                  key={range}
                  onClick={() => setDateRange(range)}
                  className={`px-3 py-2 text-xs font-medium transition-colors ${
                    dateRange === range
                      ? "bg-brand-600 text-white"
                      : "bg-[var(--bg-primary)] text-[var(--text-secondary)] hover:bg-[var(--bg-secondary)]"
                  }`}
                >
                  {range === "7d" ? "7 Days" : range === "30d" ? "30 Days" : "This Month"}
                </button>
              ))}
            </div>
          </div>
        }
      />

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl skeleton" />
          ))}
        </div>
      ) : !salesData ? (
        <EmptyState
          title="No report data"
          description="Sales data for this period will appear here."
          icon={
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
            </svg>
          }
        />
      ) : (
        <>
          {/* Summary cards — fields sourced from GET /reports/sales only */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-4 shadow-card">
              <p className="text-xs font-medium text-[var(--text-muted)] uppercase">Total Orders</p>
              <p className="text-2xl font-bold text-[var(--text-primary)] mt-1">{salesData.total_orders.toLocaleString()}</p>
            </div>
            <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-4 shadow-card">
              <p className="text-xs font-medium text-[var(--text-muted)] uppercase">Total Revenue</p>
              <p className="text-2xl font-bold text-green-600 dark:text-green-400 mt-1">{formatCurrency(salesData.total_revenue)}</p>
            </div>
            <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-4 shadow-card">
              <p className="text-xs font-medium text-[var(--text-muted)] uppercase">Avg. Order Value</p>
              <p className="text-2xl font-bold text-[var(--text-primary)] mt-1">
                {formatCurrency(salesData.total_orders > 0 ? Math.round(salesData.total_revenue / salesData.total_orders) : 0)}
              </p>
            </div>
            <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-4 shadow-card">
              <p className="text-xs font-medium text-[var(--text-muted)] uppercase">Net Revenue</p>
              <p className="text-2xl font-bold text-green-600 dark:text-green-400 mt-1">{formatCurrency(salesData.net_revenue)}</p>
            </div>
          </div>

          {/* Refunds summary */}
          <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-5 shadow-card">
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-1">Refunds</h3>
            <p className="text-sm text-[var(--text-secondary)]">
              {formatCurrency(salesData.total_refunded)} refunded in this period (already deducted from net revenue).
            </p>
          </div>
        </>
      )}
    </div>
  );
}