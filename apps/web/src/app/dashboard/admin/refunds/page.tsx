"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { getAllRefunds, processRefund } from "@/lib/api";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";
import type { Refund } from "@uniserve/shared-types";

export default function RefundsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const isAdmin = user?.role === "university_admin";

  const [refunds, setRefunds] = useState<Refund[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");

  useEffect(() => {
    if (!isAdmin) router.push("/dashboard");
  }, [isAdmin, router]);

  const loadRefunds = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getAllRefunds(statusFilter !== "all" ? { status: statusFilter } : {});
      setRefunds(data?.refunds ?? (Array.isArray(data) ? data : []));
    } catch {
      setRefunds([]);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { loadRefunds(); }, [loadRefunds]);

  const handleProcess = async (refundId: string, action: "approve" | "reject") => {
    const reason = prompt(`Reason for ${action}ing refund:`);
    if (reason === null) return;
    setActionLoading(refundId);
    try {
      await processRefund(refundId, { action, reason: reason || undefined });
      await loadRefunds();
    } catch (err: any) {
      alert(err?.message ?? "Failed");
    } finally {
      setActionLoading(null);
    }
  };

  const formatCurrency = (amount: number) => `Rs. ${amount.toLocaleString("en-PK")}`;

  const formatDate = (iso: string) => {
    try { return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" }); }
    catch { return iso; }
  };

  if (!isAdmin) return null;

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Refund Management"
        description="Review and process refund requests"
        actions={
          <div className="flex rounded-lg border border-[var(--border-default)] overflow-hidden">
            {["all", "pending", "approved", "rejected"].map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`px-3 py-2 text-xs font-medium capitalize transition-colors ${
                  statusFilter === s
                    ? "bg-brand-600 text-white"
                    : "bg-[var(--bg-primary)] text-[var(--text-secondary)] hover:bg-[var(--bg-secondary)]"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        }
      />

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-24 bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl skeleton" />
          ))}
        </div>
      ) : refunds.length === 0 ? (
        <EmptyState
          title="No refunds"
          description="Refund requests will appear here."
          icon={
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z" />
            </svg>
          }
        />
      ) : (
        <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl overflow-hidden shadow-card">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border-default)] bg-[var(--bg-secondary)]/50">
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Order</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Student</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Reason</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-[var(--text-muted)] uppercase">Amount</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Date</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-[var(--text-muted)] uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-default)]">
                {refunds.map((refund) => (
                  <tr key={refund.id} className="hover:bg-[var(--bg-secondary)]/50 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-[var(--text-secondary)]">
                      {(refund.order_id ?? "").slice(0, 8)}...
                    </td>
                    <td className="px-4 py-3 text-[var(--text-primary)]">
                      {(refund as any).student?.first_name ?? "N/A"} {(refund as any).student?.last_name ?? ""}
                    </td>
                    <td className="px-4 py-3 text-[var(--text-secondary)] text-xs max-w-[200px] truncate">
                      {refund.reason}
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-red-600 dark:text-red-400">
                      {formatCurrency(refund.amount)}
                    </td>
                    <td className="px-4 py-3"><StatusBadge status={refund.status} /></td>
                    <td className="px-4 py-3 text-xs text-[var(--text-muted)]">{formatDate(refund.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      {refund.status === "pending" && (
                        <div className="flex gap-1 justify-end">
                          <Button
                            size="sm"
                            variant="primary"
                            loading={actionLoading === refund.id}
                            onClick={() => handleProcess(refund.id, "approve")}
                          >
                            Approve
                          </Button>
                          <Button
                            size="sm"
                            variant="danger"
                            loading={actionLoading === refund.id}
                            onClick={() => handleProcess(refund.id, "reject")}
                          >
                            Reject
                          </Button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}