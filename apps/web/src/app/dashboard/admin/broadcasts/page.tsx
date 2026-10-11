"use client";

/**
 * Phase 50 — Admin Broadcast Center (University Admin)
 *
 * Compose an in-app announcement → choose a supported audience → review
 * (exact content + backend-resolved recipient count) → confirm → real send.
 *
 * Channel: in-app notifications ONLY. A broadcast creates Notification rows
 * (type "admin_announcement") that recipients see in their existing
 * notification center. No push, SMS, or email is sent by this system.
 *
 * Safety rules honored here:
 *   - Backend RBAC is authoritative (RequireRole UNIVERSITY_ADMIN); this
 *     page additionally hides itself from non-admins as UX routing.
 *   - Client-side validation mirrors the backend but is NOT the enforcer.
 *   - Success is only shown after the backend returns a persisted result
 *     (201 create / 200 idempotent replay) with a real recipient count.
 *   - The send button is disabled while submitting; an idempotency key is
 *     kept across a failed retry so one compose attempt can never create
 *     duplicate broadcast records.
 */

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import {
  ApiClientError,
  broadcastNotification,
  getAdminBroadcasts,
  getBroadcastAudienceCount,
  getCafeterias,
  getApiErrorInfo,
} from "@/lib/api";
import type { ApiErrorInfo } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadErrorState } from "@/components/ui/LoadErrorState";
import { Button } from "@/components/ui/Button";
import { ModalShell } from "@/components/admin/ModalShell";
import type {
  BroadcastAudience,
  BroadcastResponse,
  Cafeteria,
} from "@uniserve/shared-types";

// ---------------------------------------------------------------------------
// Audience options — must mirror the backend BroadcastAudience enum exactly.
// ---------------------------------------------------------------------------

interface AudienceOption {
  value: BroadcastAudience;
  label: string;
}

const AUDIENCES: AudienceOption[] = [
  { value: "all_users", label: "All active users" },
  { value: "students", label: "Students" },
  { value: "faculty", label: "Faculty" },
  { value: "cafeteria_staff", label: "Cafeteria staff" },
  { value: "cafeteria_managers", label: "Cafeteria managers" },
  { value: "university_admins", label: "University admins" },
  { value: "cafeteria", label: "A specific cafeteria" },
];

const audienceLabel = (value: string): string => {
  const match = AUDIENCES.find((a) => a.value === value);
  return match ? match.label : value;
};

const MAX_TITLE = 255;
const MAX_MESSAGE = 5000;

/** Browser idempotency key — payments convention, one key per compose attempt. */
const generateIdempotencyKey = (): string => {
  try {
    if (
      typeof crypto !== "undefined" &&
      typeof crypto.randomUUID === "function"
    ) {
      return crypto.randomUUID();
    }
  } catch {
    // fall through to the local fallback
  }
  return `p50-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
};

const formatDateTime = (iso: string): string => {
  try {
    return new Date(iso).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
};

const MEGAPHONE_ICON = (
  <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M10.34 15.84c-.688-.06-1.386-.09-2.09-.09H7.5a4.5 4.5 0 110-9h.75c.704 0 1.402-.03 2.09-.09m0 9.18c.253.962.584 1.892.985 2.783.247.55.06 1.21-.463 1.511l-.657.38c-.551.318-1.26.117-1.527-.461a20.845 20.845 0 01-1.44-4.282m3.102.069a18.03 18.03 0 01-.59-4.59c0-1.586.205-3.124.59-4.59m0 9.18a23.848 23.848 0 018.835 2.535M10.34 6.66a23.847 23.847 0 008.835-2.535m0 0A23.74 23.74 0 0018.795 3m.38 1.125a23.91 23.91 0 011.014 5.395m-1.014 8.855c-.118.38-.245.754-.38 1.125m.38-1.125a23.91 23.91 0 001.014-5.395m0-3.46c.495.413.811 1.035.811 1.73 0 .695-.316 1.317-.811 1.73m0-3.46a24.347 24.347 0 010 3.46" />
  </svg>
);

const INPUT_CLASSES =
  "w-full rounded-lg border border-[var(--border-default)] bg-[var(--bg-primary)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-brand-500";

export default function AdminBroadcastsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const isAdmin = user?.role === "university_admin";

  // ---- Compose form --------------------------------------------------------
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [audience, setAudience] = useState<BroadcastAudience>("all_users");
  const [cafeteriaId, setCafeteriaId] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  // ---- Review / send modal -------------------------------------------------
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewCount, setPreviewCount] = useState<number | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<ApiErrorInfo | null>(null);
  const [sendError, setSendError] = useState<ApiErrorInfo | null>(null);
  const [sending, setSending] = useState(false);
  const [success, setSuccess] = useState<BroadcastResponse | null>(null);

  // ---- History -------------------------------------------------------------
  const [history, setHistory] = useState<BroadcastResponse[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<ApiErrorInfo | null>(null);
  const [historyReloadKey, setHistoryReloadKey] = useState(0);
  const [accessError, setAccessError] = useState<string | null>(null);

  // ---- Cafeteria selector (audience === "cafeteria" only) ------------------
  const [cafeterias, setCafeterias] = useState<Cafeteria[]>([]);
  const [cafeteriasError, setCafeteriasError] = useState<ApiErrorInfo | null>(
    null,
  );
  const [cafeteriasReloadKey, setCafeteriasReloadKey] = useState(0);

  // Idempotency: one key per compose attempt; kept across a failed send so a
  // retry can never create a duplicate broadcast; reset after success.
  const idempotencyKeyRef = useRef<string>("");
  const sendAttemptFailedRef = useRef(false);

  // ---- Effects -------------------------------------------------------------

  // Non-admin direct URL (e.g. manager): this surface is admin-only.
  useEffect(() => {
    if (user && !isAdmin) router.push("/dashboard");
  }, [user, isAdmin, router]);

  // Broadcast history — University Admin only (403 handled explicitly).
  useEffect(() => {
    if (!isAdmin) return;
    let cancelled = false;
    (async () => {
      setHistoryLoading(true);
      try {
        const data = await getAdminBroadcasts({ limit: 20 });
        if (cancelled) return;
        setHistory(data.items ?? []);
        setHistoryError(null);
        setAccessError(null);
      } catch (err) {
        if (cancelled) return;
        setHistory([]);
        if (err instanceof ApiClientError && err.status === 403) {
          setAccessError(
            err.message ||
              "You do not have permission to view broadcast history.",
          );
          setHistoryError(null);
        } else {
          setAccessError(null);
          setHistoryError(getApiErrorInfo(err));
        }
      } finally {
        if (!cancelled) setHistoryLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isAdmin, historyReloadKey]);

  // Cafeteria options only when the audience is a specific cafeteria.
  useEffect(() => {
    if (audience !== "cafeteria" || !isAdmin) return;
    let cancelled = false;
    (async () => {
      try {
        // Phase 56 — broadcasts target ACTIVE cafeterias only.
        const items = await getCafeterias({ isActive: true });
        if (!cancelled) {
          setCafeterias(items ?? []);
          setCafeteriasError(null);
        }
      } catch (err) {
        if (!cancelled) setCafeteriasError(getApiErrorInfo(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [audience, isAdmin, cafeteriasReloadKey]);

  // ---- Handlers ------------------------------------------------------------

  // Mirrors backend validation (title/message length, cafeteria targeting) —
  // the backend remains the authoritative validator on submit.
  const validateForm = (): string | null => {
    const trimmedTitle = title.trim();
    const trimmedMessage = message.trim();
    if (!trimmedTitle) return "Title is required.";
    if (trimmedTitle.length > MAX_TITLE)
      return `Title must be ${MAX_TITLE} characters or fewer.`;
    if (!trimmedMessage) return "Message is required.";
    if (trimmedMessage.length > MAX_MESSAGE)
      return `Message must be ${MAX_MESSAGE} characters or fewer.`;
    if (audience === "cafeteria" && !cafeteriaId)
      return "Choose a cafeteria before reviewing this broadcast.";
    return null;
  };

  const handleReview = async () => {
    const error = validateForm();
    if (error) {
      setFormError(error);
      return;
    }
    setFormError(null);
    // A fresh compose attempt gets a fresh key — unless the previous send
    // failed, in which case the key is kept so the retry stays replay-safe.
    if (!sendAttemptFailedRef.current) {
      idempotencyKeyRef.current = generateIdempotencyKey();
    }
    setPreviewOpen(true);
    setPreviewCount(null);
    setPreviewError(null);
    setSendError(null);
    setPreviewLoading(true);
    try {
      const data = await getBroadcastAudienceCount({
        audience,
        cafeteria_id: audience === "cafeteria" ? cafeteriaId : undefined,
      });
      setPreviewCount(data.recipient_count);
    } catch (err) {
      setPreviewError(getApiErrorInfo(err));
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleRetryPreviewCount = async () => {
    setPreviewError(null);
    setPreviewLoading(true);
    try {
      const data = await getBroadcastAudienceCount({
        audience,
        cafeteria_id: audience === "cafeteria" ? cafeteriaId : undefined,
      });
      setPreviewCount(data.recipient_count);
    } catch (err) {
      setPreviewError(getApiErrorInfo(err));
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleClosePreview = () => {
    if (sending) return; // never close mid-submit
    setPreviewOpen(false);
    setSendError(null);
  };

  const handleSend = async () => {
    if (sending) return; // double-click guard
    setSending(true);
    setSendError(null);
    try {
      const result = await broadcastNotification({
        title: title.trim(),
        message: message.trim(),
        audience,
        cafeteria_id: audience === "cafeteria" ? cafeteriaId : undefined,
        idempotency_key: idempotencyKeyRef.current,
      });
      sendAttemptFailedRef.current = false;
      idempotencyKeyRef.current = "";
      setPreviewOpen(false);
      setSuccess(result);
      setTitle("");
      setMessage("");
      setAudience("all_users");
      setCafeteriaId("");
      setFormError(null);
      setHistoryReloadKey((k) => k + 1);
      toast(
        result.duplicate
          ? "This broadcast was already sent — showing the original result."
          : `Broadcast sent to ${result.recipient_count} recipient${result.recipient_count === 1 ? "" : "s"}.`,
        "success",
      );
    } catch (err) {
      // Keep the modal (and the idempotency key) open so the send can be
      // retried without any risk of a duplicate broadcast.
      sendAttemptFailedRef.current = true;
      setSendError(getApiErrorInfo(err));
    } finally {
      setSending(false);
    }
  };

  const handleClearForm = () => {
    setTitle("");
    setMessage("");
    setAudience("all_users");
    setCafeteriaId("");
    setFormError(null);
    sendAttemptFailedRef.current = false;
    idempotencyKeyRef.current = "";
  };

  // ---- Non-admin rendering -------------------------------------------------

  if (!isAdmin) {
    return (
      <div className="animate-fade-in">
        <PageHeader
          title="Broadcasts"
          description="Admin-only broadcast center."
        />
        <EmptyState
          title="Admin access required"
          description="Only University Admins can compose and send campus broadcasts."
          icon={MEGAPHONE_ICON}
        />
      </div>
    );
  }

  // ---- Render --------------------------------------------------------------

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Broadcasts"
        description="Send an in-app announcement to a targeted audience. Recipients see it in their existing notification center — no push, SMS, or email."
        actions={
          <Button
            variant="secondary"
            size="sm"
            loading={historyLoading}
            onClick={() => setHistoryReloadKey((k) => k + 1)}
          >
            Refresh history
          </Button>
        }
      />

      {accessError && (
        <div className="mb-6 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-4 text-center">
          <p className="text-sm font-semibold text-amber-800 dark:text-amber-300">
            You don&apos;t have access to broadcast history
          </p>
          <p className="text-xs text-amber-700 dark:text-amber-400 mt-1 max-w-md mx-auto">
            {accessError}
          </p>
        </div>
      )}

      {/* ── Success state — only ever shown after a real backend result ── */}
      {success && (
        <div className="mb-6 bg-green-50 dark:bg-green-900/15 border border-green-200 dark:border-green-800 rounded-xl p-6">
          <div className="flex items-start gap-4">
            <div className="flex-shrink-0 w-10 h-10 rounded-full bg-green-100 dark:bg-green-900/40 flex items-center justify-center text-green-700 dark:text-green-300">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-green-900 dark:text-green-200">
                {success.duplicate
                  ? "Broadcast already sent"
                  : "Broadcast sent"}
              </p>
              <p className="text-sm text-green-800 dark:text-green-300 mt-1">
                &ldquo;{success.title}&rdquo; was delivered to{" "}
                <strong>{success.recipient_count}</strong> recipient
                {success.recipient_count === 1 ? "" : "s"} (
                {audienceLabel(success.audience)}).
              </p>
              <p className="text-xs text-green-700 dark:text-green-400 mt-1">
                {formatDateTime(success.created_at)} · in-app notifications
                only — no push/SMS/email channel was used.
              </p>
              <div className="mt-3">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => setSuccess(null)}
                >
                  Compose another broadcast
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Compose card ── */}
      <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-6 mb-6 shadow-card">
        <h2 className="text-sm font-semibold text-[var(--text-primary)] mb-4">
          Compose broadcast
        </h2>

        {formError && (
          <div
            className="mb-4 border border-red-200 dark:border-red-800 bg-red-50/60 dark:bg-red-900/15 rounded-lg px-4 py-2.5 text-sm text-red-700 dark:text-red-300"
            role="alert"
          >
            {formError}
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label
              htmlFor="broadcast-title"
              className="block text-xs font-medium text-[var(--text-secondary)] mb-1"
            >
              Title{" "}
              <span className="text-[var(--text-muted)]">
                ({title.trim().length}/{MAX_TITLE})
              </span>
            </label>
            <input
              id="broadcast-title"
              type="text"
              maxLength={MAX_TITLE}
              value={title}
              onChange={(e) => {
                setTitle(e.target.value);
                if (formError) setFormError(null);
              }}
              placeholder="e.g., Campus announcement"
              className={INPUT_CLASSES}
            />
          </div>

          <div>
            <label
              htmlFor="broadcast-message"
              className="block text-xs font-medium text-[var(--text-secondary)] mb-1"
            >
              Message{" "}
              <span className="text-[var(--text-muted)]">
                ({message.trim().length}/{MAX_MESSAGE})
              </span>
            </label>
            <textarea
              id="broadcast-message"
              rows={5}
              maxLength={MAX_MESSAGE}
              value={message}
              onChange={(e) => {
                setMessage(e.target.value);
                if (formError) setFormError(null);
              }}
              placeholder="Write the announcement your audience will read in their notification center…"
              className={`${INPUT_CLASSES} resize-y`}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label
                htmlFor="broadcast-audience"
                className="block text-xs font-medium text-[var(--text-secondary)] mb-1"
              >
                Audience
              </label>
              <select
                id="broadcast-audience"
                value={audience}
                onChange={(e) => {
                  setAudience(e.target.value as BroadcastAudience);
                  setCafeteriaId("");
                  if (formError) setFormError(null);
                }}
                className={INPUT_CLASSES}
              >
                {AUDIENCES.map((a) => (
                  <option key={a.value} value={a.value}>
                    {a.label}
                  </option>
                ))}
              </select>
            </div>

            {audience === "cafeteria" && (
              <div>
                <label
                  htmlFor="broadcast-cafeteria"
                  className="block text-xs font-medium text-[var(--text-secondary)] mb-1"
                >
                  Cafeteria
                </label>
                {cafeteriasError ? (
                  <div className="flex items-center gap-2">
                    <p className="text-xs text-red-600 dark:text-red-400">
                      Couldn&apos;t load cafeterias.
                    </p>
                    <button
                      type="button"
                      onClick={() => setCafeteriasReloadKey((k) => k + 1)}
                      className="text-xs font-medium text-brand-700 hover:underline"
                    >
                      Retry
                    </button>
                  </div>
                ) : (
                  <select
                    id="broadcast-cafeteria"
                    value={cafeteriaId}
                    onChange={(e) => {
                      setCafeteriaId(e.target.value);
                      if (formError) setFormError(null);
                    }}
                    className={INPUT_CLASSES}
                  >
                    <option value="">Select a cafeteria…</option>
                    {cafeterias.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="mt-5 flex items-center gap-3">
          <Button
            onClick={handleReview}
            loading={previewLoading && previewOpen}
          >
            Review broadcast
          </Button>
          <Button variant="ghost" onClick={handleClearForm}>
            Clear form
          </Button>
        </div>
        <p className="text-xs text-[var(--text-muted)] mt-3">
          Sending requires a review step and creates in-app notifications
          through the existing UniServe notification center.
        </p>
      </div>

      {/* ── History card ── */}
      <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-card overflow-hidden">
        <div className="px-6 py-4 border-b border-[var(--border-default)] flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">
            Broadcast history
          </h2>
          <span className="text-xs text-[var(--text-muted)]">
            {history.length} most recent
          </span>
        </div>
        {historyLoading ? (
          <div className="p-6 space-y-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-16 bg-[var(--bg-secondary)] rounded-lg skeleton"
              />
            ))}
          </div>
        ) : historyError ? (
          <LoadErrorState
            error={historyError}
            subject="broadcast history"
            onRetry={() => setHistoryReloadKey((k) => k + 1)}
          />
        ) : history.length === 0 ? (
          <EmptyState
            title="No broadcasts yet"
            description="Broadcasts you send will appear here with their audience and recipient count."
            icon={MEGAPHONE_ICON}
          />
        ) : (
          <div className="divide-y divide-[var(--border-default)]">
            {history.map((b) => (
              <div
                key={b.id}
                className="px-6 py-4 flex items-start gap-4"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-medium text-[var(--text-primary)] truncate">
                      {b.title}
                    </p>
                    {b.duplicate && (
                      <span className="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                        Duplicate replay
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-[var(--text-muted)] mt-0.5 line-clamp-2">
                    {b.message}
                  </p>
                  <p className="text-xs text-[var(--text-muted)] mt-1">
                    {audienceLabel(b.audience)}
                    {b.cafeteria_id
                      ? ` · ${
                          cafeterias.find((c) => c.id === b.cafeteria_id)
                            ?.name ?? "cafeteria"
                        }`
                      : ""}{" "}
                    · to {b.recipient_count} recipient
                    {b.recipient_count === 1 ? "" : "s"}
                  </p>
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="text-xs font-medium text-[var(--text-primary)]">
                    {b.recipient_count}
                  </p>
                  <p className="text-[11px] text-[var(--text-muted)]">
                    {formatDateTime(b.created_at)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Review / confirm modal ── */}
      {previewOpen && (
        <ModalShell onClose={handleClosePreview} maxWidth="max-w-lg">
          <h3 className="text-base font-semibold text-[var(--text-primary)]">
            Review broadcast
          </h3>
          <p className="text-xs text-[var(--text-muted)] mt-1">
            Check the details below. Nothing is sent until you confirm.
          </p>

          <dl className="mt-4 space-y-3 text-sm">
            <div>
              <dt className="text-xs font-medium text-[var(--text-secondary)]">
                Title
              </dt>
              <dd className="text-[var(--text-primary)] mt-0.5 break-words">
                {title.trim()}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-[var(--text-secondary)]">
                Message
              </dt>
              <dd className="text-[var(--text-primary)] mt-0.5 whitespace-pre-wrap break-words">
                {message.trim()}
              </dd>
            </div>
            <div className="flex gap-6 flex-wrap">
              <div>
                <dt className="text-xs font-medium text-[var(--text-secondary)]">
                  Audience
                </dt>
                <dd className="text-[var(--text-primary)] mt-0.5">
                  {audienceLabel(audience)}
                </dd>
              </div>
              {audience === "cafeteria" && cafeteriaId && (
                <div>
                  <dt className="text-xs font-medium text-[var(--text-secondary)]">
                    Cafeteria
                  </dt>
                  <dd className="text-[var(--text-primary)] mt-0.5">
                    {cafeterias.find((c) => c.id === cafeteriaId)?.name ??
                      cafeteriaId}
                  </dd>
                </div>
              )}
            </div>
            <div>
              <dt className="text-xs font-medium text-[var(--text-secondary)]">
                Recipients
              </dt>
              <dd className="mt-0.5">
                {previewLoading ? (
                  <span className="inline-flex items-center gap-2 text-[var(--text-muted)]">
                    <span className="w-3.5 h-3.5 border-2 border-brand-700 border-t-transparent rounded-full animate-spin inline-block" />
                    Counting active recipients…
                  </span>
                ) : previewError ? (
                  <span className="text-red-600 dark:text-red-400 text-xs">
                    Couldn&apos;t count recipients — {previewError.message}
                  </span>
                ) : previewCount !== null && previewCount > 0 ? (
                  <span className="text-[var(--text-primary)] font-medium">
                    {previewCount} recipient
                    {previewCount === 1 ? "" : "s"}
                  </span>
                ) : previewCount === 0 ? (
                  <span className="text-amber-700 dark:text-amber-300 text-xs">
                    No active recipients — the server will reject this send.
                  </span>
                ) : null}
              </dd>
            </div>
          </dl>

          {sendError && (
            <div
              className="mt-4 border border-red-200 dark:border-red-800 bg-red-50/60 dark:bg-red-900/15 rounded-lg px-4 py-2.5 text-sm text-red-700 dark:text-red-300"
              role="alert"
            >
              <p className="font-medium">Broadcast not sent</p>
              <p className="text-xs mt-0.5">{sendError.message}</p>
            </div>
          )}

          <div className="mt-6 flex items-center justify-end gap-3">
            <Button
              variant="secondary"
              onClick={handleClosePreview}
              disabled={sending}
            >
              Cancel
            </Button>
            {previewError && !previewLoading && (
              <Button
                variant="secondary"
                onClick={handleRetryPreviewCount}
                disabled={sending}
              >
                Retry count
              </Button>
            )}
            <Button
              onClick={handleSend}
              loading={sending}
              disabled={
                previewLoading || previewCount === null || previewCount === 0
              }
            >
              {sendError ? "Try again" : "Send broadcast"}
            </Button>
          </div>
        </ModalShell>
      )}
    </div>
  );
}
