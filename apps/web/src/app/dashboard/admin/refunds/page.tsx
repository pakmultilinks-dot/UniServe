"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import {
  getAllRefunds,
  getAdminRefund,
  processRefund,
  rejectRefund,
  getApiErrorInfo,
} from "@/lib/api";
import type { ApiErrorInfo } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadErrorState } from "@/components/ui/LoadErrorState";
import { Button } from "@/components/ui/Button";
import { ModalShell } from "@/components/admin/ModalShell";
import type { RefundAdminResponse, RefundStatus } from "@uniserve/shared-types";

/**
 * Phase 51 — Admin refund management & resolution.
 *
 * Approval semantics (accurate, sandbox processor): approving a refund
 * request processes it through the configured refund processor in
 * sandbox/test mode. It does NOT represent a real bank transfer or money
 * returning to the student's account. Rejection records a persisted admin
 * decision reason and moves NO money at all.
 *
 * Authorization is backend-authoritative: every action below is enforced by
 * the API (University Admin for all refunds; Cafeteria Manager for their
 * assigned cafeteria only). The UI merely reflects those rules.
 */

/** Real backend refund statuses (the previous "approved" filter was not one). */
const STATUS_FILTERS: Array<RefundStatus | "all"> = [
  "all",
  "pending",
  "processing",
  "succeeded",
  "failed",
  "rejected",
];

const REJECT_MIN = 10;
const REJECT_MAX = 500;

type DialogState =
  | { kind: "approve"; refund: RefundAdminResponse }
  | { kind: "reject"; refund: RefundAdminResponse }
  | null;

export default function RefundsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const isAdmin = user?.role === "university_admin";

  const [refunds, setRefunds] = useState<RefundAdminResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<RefundStatus | "all">("all");
  /* Phase 46 — explicit request-failure state (see LoadErrorState). */
  const [loadError, setLoadError] = useState<ApiErrorInfo | null>(null);
  /* Phase 51 — detail view + confirmation dialogs. */
  const [detail, setDetail] = useState<RefundAdminResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<ApiErrorInfo | null>(null);
  const [dialog, setDialog] = useState<DialogState>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [rejectError, setRejectError] = useState<string | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    if (user && !isAdmin) router.push("/dashboard");
  }, [user, isAdmin, router]);

  const loadRefunds = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getAllRefunds(statusFilter !== "all" ? { status: statusFilter } : {});
      setRefunds(data?.refunds ?? []);
      setLoadError(null);
    } catch (err) {
      // Phase 46 — surface the failure; "No refunds" must only ever be
      // shown for a genuinely empty result.
      setLoadError(getApiErrorInfo(err));
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { loadRefunds(); }, [loadRefunds]);

  const openDetail = async (refundId: string) => {
    setDetailLoading(true);
    setDetailError(null);
    try {
      const data = await getAdminRefund(refundId);
      setDetail(data);
    } catch (err) {
      setDetailError(getApiErrorInfo(err));
    } finally {
      setDetailLoading(false);
    }
  };

  const closeDetail = () => {
    setDetail(null);
    setDetailError(null);
  };

  const openApprove = (refund: RefundAdminResponse) => {
    setDialog({ kind: "approve", refund });
  };

  const openReject = (refund: RefundAdminResponse) => {
    setRejectReason("");
    setRejectError(null);
    setDialog({ kind: "reject", refund });
  };

  const closeDialog = () => {
    if (actionLoading) return; // no closing mid-submit (double-submit guard)
    setDialog(null);
    setRejectError(null);
  };

  const handleApprove = async (refund: RefundAdminResponse) => {
    if (actionLoading) return;
    setActionLoading(refund.id);
    try {
      await processRefund(refund.id);
      toast(
        "Refund request approved — processed through the configured refund processor (sandbox/test mode).",
        "success",
      );
      setDialog(null);
      if (detail?.id === refund.id) await openDetail(refund.id);
      await loadRefunds();
    } catch (err) {
      const info = getApiErrorInfo(err);
      toast(info.message, "error");
      // Refresh so a backend-rejected action (e.g. already resolved) is visible.
      await loadRefunds();
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (refund: RefundAdminResponse) => {
    if (actionLoading) return;
    const reason = rejectReason.trim();
    // Client-side guard mirrors backend rules (min 10 / max 500 chars).
    if (reason.length < REJECT_MIN) {
      setRejectError(`A reason of at least ${REJECT_MIN} characters is required.`);
      return;
    }
    if (reason.length > REJECT_MAX) {
      setRejectError(`The reason must be at most ${REJECT_MAX} characters.`);
      return;
    }
    setRejectError(null);
    setActionLoading(refund.id);
    try {
      await rejectRefund(refund.id, { rejection_reason: reason });
      toast("Refund request rejected. The decision reason has been recorded.", "success");
      setDialog(null);
      if (detail?.id === refund.id) await openDetail(refund.id);
      await loadRefunds();
    } catch (err) {
      const info = getApiErrorInfo(err);
      toast(info.message, "error");
      await loadRefunds();
    } finally {
      setActionLoading(null);
    }
  };

  const formatCurrency = (amount: number) => `Rs. ${(amount / 100).toLocaleString("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  const formatDate = (iso: string) => {
    try { return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" }); }
    catch { return iso; }
  };

  const reasonLabel = (reason: string) => reason.replace(/_/g, " ");

  if (!user || !isAdmin) return null;

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Refund Management"
        description="Review, approve, or reject refund requests"
        actions={
          <div className="flex rounded-lg border border-[var(--border-default)] overflow-hidden">
            {STATUS_FILTERS.map((s) => (
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

      {/* Phase 46 — refunds refresh failure (compact, retryable) */}
      {loadError && refunds.length > 0 && (
        <LoadErrorState
          compact
          error={loadError}
          subject="refunds"
          onRetry={() => loadRefunds()}
          className="mb-4 border border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-900/10 rounded-xl"
        />
      )}

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-24 bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl skeleton" />
          ))}
        </div>
      ) : loadError && refunds.length === 0 ? (
        <LoadErrorState
          error={loadError}
          subject="refunds"
          onRetry={() => loadRefunds()}
        />
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
                      #{refund.order?.order_number ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-[var(--text-primary)]">
                      <div className="font-medium">
                        {refund.student
                          ? `${refund.student.first_name} ${refund.student.last_name}`
                          : "N/A"}
                      </div>
                      {refund.student && (
                        <div className="text-xs text-[var(--text-muted)]">{refund.student.university_email}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-[var(--text-secondary)] text-xs max-w-[200px] truncate">
                      {reasonLabel(refund.reason)}
                      {refund.reason_note && (
                        <div className="text-[var(--text-muted)] truncate" title={refund.reason_note}>
                          {refund.reason_note}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-red-600 dark:text-red-400">
                      {formatCurrency(refund.amount)}
                    </td>
                    <td className="px-4 py-3"><StatusBadge status={refund.status} /></td>
                    <td className="px-4 py-3 text-xs text-[var(--text-muted)]">{formatDate(refund.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex gap-1 justify-end">
                        <Button size="sm" variant="secondary" onClick={() => openDetail(refund.id)}>
                          View
                        </Button>
                        {refund.status === "pending" && (
                          <>
                            <Button
                              size="sm"
                              variant="primary"
                              disabled={actionLoading !== null}
                              loading={actionLoading === refund.id}
                              onClick={() => openApprove(refund)}
                            >
                              Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="danger"
                              disabled={actionLoading !== null}
                              onClick={() => openReject(refund)}
                            >
                              Reject
                            </Button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Detail dialog — student / order / payment / refund / resolution ── */}
      {(detail || detailLoading || detailError) && !dialog && (
        <ModalShell onClose={closeDetail} maxWidth="max-w-2xl">
          {detailLoading ? (
            <div className="space-y-3">
              <div className="h-5 w-40 bg-[var(--bg-secondary)] rounded skeleton" />
              <div className="h-24 bg-[var(--bg-secondary)] rounded skeleton" />
            </div>
          ) : detailError ? (
            <div>
              <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-2">Refund details</h3>
              <LoadErrorState
                compact
                error={detailError}
                subject="refund details"
                onRetry={() => detail && openDetail(detail.id)}
                className="border border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-900/10 rounded-xl"
              />
              <div className="mt-4 text-right">
                <Button size="sm" variant="secondary" onClick={closeDetail}>Close</Button>
              </div>
            </div>
          ) : detail ? (
            <div>
              <div className="flex items-start justify-between gap-3 mb-4">
                <div>
                  <h3 className="text-lg font-semibold text-[var(--text-primary)]">
                    Refund #{detail.id.slice(0, 8)} — Order #{detail.order?.order_number ?? "—"}
                  </h3>
                  <div className="mt-1 flex items-center gap-2">
                    <StatusBadge status={detail.status} />
                    <span className="text-sm font-medium text-red-600 dark:text-red-400">
                      {formatCurrency(detail.amount)}
                    </span>
                  </div>
                </div>
                <Button size="sm" variant="ghost" onClick={closeDetail}>Close</Button>
              </div>

              <div className="space-y-4 text-sm">
                {/* Student */}
                <section className="rounded-lg border border-[var(--border-default)] p-3">
                  <h4 className="text-xs font-semibold uppercase text-[var(--text-muted)] mb-2">Student</h4>
                  <div className="text-[var(--text-primary)] font-medium">
                    {detail.student
                      ? `${detail.student.first_name} ${detail.student.last_name}`
                      : "N/A"}
                  </div>
                  <div className="text-[var(--text-secondary)]">{detail.student?.university_email}</div>
                  <div className="text-[var(--text-muted)] text-xs">
                    University ID: {detail.student?.university_id ?? "—"} · Role: {detail.student?.role ?? "—"}
                  </div>
                </section>

                {/* Order */}
                <section className="rounded-lg border border-[var(--border-default)] p-3">
                  <h4 className="text-xs font-semibold uppercase text-[var(--text-muted)] mb-2">Order</h4>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[var(--text-secondary)]">
                    <span>Order number</span>
                    <span className="text-[var(--text-primary)]">#{detail.order?.order_number ?? "—"}</span>
                    <span>Status</span>
                    <span className="capitalize">{detail.order?.status?.replace(/_/g, " ") ?? "—"}</span>
                    <span>Payment method</span>
                    <span className="capitalize">{detail.order?.payment_method ?? "—"}</span>
                    <span>Total amount</span>
                    <span>{detail.order ? formatCurrency(detail.order.total_amount) : "—"}</span>
                    <span>Cafeteria</span>
                    <span>{detail.order?.cafeteria_name ?? "—"}</span>
                    <span>Placed</span>
                    <span>{detail.order?.created_at ? formatDate(detail.order.created_at) : "—"}</span>
                  </div>
                </section>

                {/* Payment */}
                <section className="rounded-lg border border-[var(--border-default)] p-3">
                  <h4 className="text-xs font-semibold uppercase text-[var(--text-muted)] mb-2">Payment</h4>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[var(--text-secondary)]">
                    <span>Status</span>
                    <span className="capitalize">{detail.payment?.status?.replace(/_/g, " ") ?? "—"}</span>
                    <span>Provider</span>
                    <span>{detail.payment?.provider_name ?? "—"}</span>
                    <span>Provider reference</span>
                    <span className="font-mono text-xs">{detail.payment?.provider_reference ?? "—"}</span>
                    <span>Amount</span>
                    <span>{detail.payment ? formatCurrency(detail.payment.amount) : "—"}</span>
                  </div>
                </section>

                {/* Refund request */}
                <section className="rounded-lg border border-[var(--border-default)] p-3">
                  <h4 className="text-xs font-semibold uppercase text-[var(--text-muted)] mb-2">Refund request</h4>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[var(--text-secondary)]">
                    <span>Reason</span>
                    <span className="capitalize text-[var(--text-primary)]">{reasonLabel(detail.reason)}</span>
                    <span>Requester note</span>
                    <span className="text-[var(--text-primary)]">{detail.reason_note || "—"}</span>
                    <span>Requested</span>
                    <span>{formatDate(detail.created_at)}</span>
                    <span>Refund provider ref</span>
                    <span className="font-mono text-xs">{detail.provider_reference ?? "—"}</span>
                  </div>
                </section>

                {/* Resolution */}
                <section className="rounded-lg border border-[var(--border-default)] p-3">
                  <h4 className="text-xs font-semibold uppercase text-[var(--text-muted)] mb-2">Resolution</h4>
                  {detail.status === "pending" ? (
                    <p className="text-[var(--text-secondary)]">
                      Awaiting an admin decision — approve or reject this request.
                    </p>
                  ) : (
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[var(--text-secondary)]">
                      <span>Decision</span>
                      <span className="text-[var(--text-primary)]">
                        {detail.status === "rejected" ? "Rejected" : `Processed (${detail.status})`}
                      </span>
                      <span>Resolved by</span>
                      <span className="font-mono text-xs">{detail.processed_by ?? "—"}</span>
                      <span>Resolved at</span>
                      <span>{detail.processed_at ? formatDate(detail.processed_at) : "—"}</span>
                      {detail.status === "rejected" && (
                        <>
                          <span>Rejection reason</span>
                          <span className="text-[var(--text-primary)]">{detail.rejection_reason || "—"}</span>
                        </>
                      )}
                    </div>
                  )}
                  {detail.status === "succeeded" && (
                    <p className="mt-2 text-xs text-[var(--text-muted)]">
                      Processed through the configured refund processor in sandbox/test mode — no real
                      bank transfer is represented by this record.
                    </p>
                  )}
                </section>
              </div>

              {detail.status === "pending" && (
                <div className="mt-5 flex justify-end gap-2">
                  <Button
                    size="sm"
                    variant="primary"
                    disabled={actionLoading !== null}
                    loading={actionLoading === detail.id}
                    onClick={() => openApprove(detail)}
                  >
                    Approve
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    disabled={actionLoading !== null}
                    onClick={() => openReject(detail)}
                  >
                    Reject
                  </Button>
                </div>
              )}
            </div>
          ) : null}
        </ModalShell>
      )}

      {/* ── Approve confirmation — accurate sandbox semantics ── */}
      {dialog?.kind === "approve" && (
        <ModalShell onClose={closeDialog} maxWidth="max-w-md">
          <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-2">Approve refund request?</h3>
          <p className="text-sm text-[var(--text-secondary)] mb-3">
            Order #{dialog.refund.order?.order_number ?? "—"} ·{" "}
            {dialog.refund.student
              ? `${dialog.refund.student.first_name} ${dialog.refund.student.last_name}`
              : "student"}{" "}
            · <span className="font-medium">{formatCurrency(dialog.refund.amount)}</span>
          </p>
          <div className="rounded-lg border border-yellow-200 dark:border-yellow-800 bg-yellow-50/60 dark:bg-yellow-900/10 p-3 text-sm text-yellow-900 dark:text-yellow-200 mb-4">
            <p className="font-semibold mb-1">Sandbox processing — no real money movement</p>
            <p>
              Approving marks this refund request as processed through the configured refund
              processor in <strong>sandbox/test mode</strong>. This does <strong>not</strong>{" "}
              represent a real bank transfer, and no money is actually returned to the
              student&apos;s account by this action.
            </p>
          </div>
          <div className="flex justify-end gap-2">
            <Button size="sm" variant="secondary" disabled={actionLoading !== null} onClick={closeDialog}>
              Cancel
            </Button>
            <Button
              size="sm"
              variant="primary"
              disabled={actionLoading !== null}
              loading={actionLoading === dialog.refund.id}
              onClick={() => handleApprove(dialog.refund)}
            >
              Approve request
            </Button>
          </div>
        </ModalShell>
      )}

      {/* ── Reject dialog — persisted reason required ── */}
      {dialog?.kind === "reject" && (
        <ModalShell onClose={closeDialog} maxWidth="max-w-md">
          <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-2">Reject refund request?</h3>
          <p className="text-sm text-[var(--text-secondary)] mb-3">
            Order #{dialog.refund.order?.order_number ?? "—"} ·{" "}
            {dialog.refund.student
              ? `${dialog.refund.student.first_name} ${dialog.refund.student.last_name}`
              : "student"}{" "}
            · <span className="font-medium">{formatCurrency(dialog.refund.amount)}</span>
          </p>
          <label htmlFor="reject-reason" className="block text-sm font-medium text-[var(--text-primary)] mb-1">
            Rejection reason <span className="text-red-500">*</span>
          </label>
          <textarea
            id="reject-reason"
            value={rejectReason}
            onChange={(e) => {
              setRejectReason(e.target.value);
              if (rejectError) setRejectError(null);
            }}
            rows={4}
            maxLength={REJECT_MAX}
            placeholder="Explain why this refund request is being rejected (10–500 characters)."
            className={`w-full rounded-lg border bg-[var(--bg-primary)] text-[var(--text-primary)] text-sm p-2.5 outline-none focus:ring-2 ${
              rejectError
                ? "border-red-400 focus:ring-red-300"
                : "border-[var(--border-default)] focus:ring-brand-500"
            }`}
          />
          <div className="mt-1 flex items-center justify-between text-xs">
            <span className={rejectError ? "text-red-600 dark:text-red-400" : "text-[var(--text-muted)]"}>
              {rejectError ?? `Minimum ${REJECT_MIN} characters.`}
            </span>
            <span className="text-[var(--text-muted)]">{rejectReason.trim().length}/{REJECT_MAX}</span>
          </div>
          <p className="mt-2 text-xs text-[var(--text-muted)]">
            Rejection records this decision and notifies the student. No money movement occurs.
          </p>
          <div className="mt-4 flex justify-end gap-2">
            <Button size="sm" variant="secondary" disabled={actionLoading !== null} onClick={closeDialog}>
              Cancel
            </Button>
            <Button
              size="sm"
              variant="danger"
              disabled={actionLoading !== null}
              loading={actionLoading === dialog.refund.id}
              onClick={() => handleReject(dialog.refund)}
            >
              Reject request
            </Button>
          </div>
        </ModalShell>
      )}
    </div>
  );
}