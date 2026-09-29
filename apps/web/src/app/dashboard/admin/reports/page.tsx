"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { getSalesReport, getCafeterias } from "@/lib/api";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import type { Cafeteria } from "@uniserve/shared-types";

interface SalesData {
  total_orders: number;
  total_revenue: number;
  average_order_value: number;
  peak_hour: string;
  popular_items: Array<{ name: string; quantity: number; revenue: number }>;
  daily_breakdown: Array<{ date: string; orders: number; revenue: number }>;
  cafeteria_breakdown: Array<{ cafeteria_id: string; cafeteria_name: string; orders: number; revenue: number }>;
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
    let start: string;
    if (dateRange === "7d") start = new Date(now.getTime() - 7 * 86400000).toISOString();
    else if (dateRange === "30d") start = new Date(now.getTime() - 30 * 86400000).toISOString();
    else start = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();

    getSalesReport({ cafeteria_id: selectedCafeteria, start_date: start, end_date: now.toISOString() })
      .then((data) => setSalesData(data))
      .catch(() => setSalesData(null))
      .finally(() => setLoading(false));
  }, [selectedCafeteria, dateRange]);

  const formatCurrency = (amount: number) => `Rs. ${amount.toLocaleString("en-PK", { minimumFractionDigits: 0 })}`;

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
          {/* Summary cards */}
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
              <p className="text-2xl font-bold text-[var(--text-primary)] mt-1">{formatCurrency(salesData.average_order_value)}</p>
            </div>
            <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-4 shadow-card">
              <p className="text-xs font-medium text-[var(--text-muted)] uppercase">Peak Hour</p>
              <p className="text-2xl font-bold text-[var(--text-primary)] mt-1">{salesData.peak_hour ?? "N/A"}</p>
            </div>
          </div>

          {/* Popular items */}
          {salesData.popular_items && salesData.popular_items.length > 0 && (
            <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-5 shadow-card mb-6">
              <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">Popular Items</h3>
              <div className="space-y-2">
                {salesData.popular_items.slice(0, 5).map((item, idx) => (
                  <div key={idx} className="flex items-center justify-between py-2 border-b border-[var(--border-default)] last:border-0">
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-medium text-[var(--text-primary)]">{item.name}</span>
                      <span className="text-xs text-[var(--text-muted)]">{item.quantity} sold</span>
                    </div>
                    <span className="text-sm font-medium text-green-600 dark:text-green-400">{formatCurrency(item.revenue)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Daily breakdown */}
          {salesData.daily_breakdown && salesData.daily_breakdown.length > 0 && (
            <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-5 shadow-card">
              <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">Daily Breakdown</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--border-default)]">
                      <th className="px-3 py-2 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Date</th>
                      <th className="px-3 py-2 text-right text-xs font-semibold text-[var(--text-muted)] uppercase">Orders</th>
                      <th className="px-3 py-2 text-right text-xs font-semibold text-[var(--text-muted)] uppercase">Revenue</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-default)]">
                    {salesData.daily_breakdown.map((day, idx) => (
                      <tr key={idx} className="hover:bg-[var(--bg-secondary)]/50">
                        <td className="px-3 py-2 text-[var(--text-primary)]">
                          {new Date(day.date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                        </td>
                        <td className="px-3 py-2 text-right text-[var(--text-secondary)]">{day.orders}</td>
                        <td className="px-3 py-2 text-right font-medium text-green-600 dark:text-green-400">
                          {formatCurrency(day.revenue)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}