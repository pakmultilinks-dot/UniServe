"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadErrorState } from "@/components/ui/LoadErrorState";
import { getAuditEvents, getApiErrorInfo } from "@/lib/api";
import type { ApiErrorInfo, AuditEvent } from "@/lib/api";

// Page size for the audit table (backend caps limit at 200).
const PAGE_SIZE = 20;

// AuditEventType values from apps/api/app/core/audit.py — kept in sync
// with the backend enum so the filter never offers an unknown value.
const EVENT_TYPES = [
  "user_registered",
  "email_verification_requested",
  "email_verified",
  "login_success",
  "login_failed",
  "logout",
  "logout_all",
  "password_changed",
  "password_reset_requested",
  "password_reset_completed",
  "pin_enabled",
  "pin_disabled",
  "pin_changed",
  "pin_login_success",
  "pin_login_failed",
  "pin_locked",
  "account_suspended",
  "account_activated",
  "account_recovered",
  "account_deleted",
  "role_changed",
  "cafeteria_scope_changed",
  "session_created",
  "session_revoked",
  "rate_limited",
  "authorization_failed",
] as const;

function humanizeEventType(value: string): string {
  return value.replace(/_/g, " ");
}

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString();
  } catch {
    return iso;
  }
}

export default function AuditLogPage() {
  const { user } = useAuth();
  const router = useRouter();
  const isAdmin = user?.role === "university_admin";

  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [eventTypeFilter, setEventTypeFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<ApiErrorInfo | null>(null);

  const loadEvents = useCallback(async () => {
    setLoading(true);
    try {
      const params: Parameters<typeof getAuditEvents>[0] = {
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      };
      if (eventTypeFilter !== "all") params.event_type = eventTypeFilter;
      const data = await getAuditEvents(params);
      const rows = data.events ?? [];
      // If the current page emptied out (e.g. filter narrowed the set),
      // step back rather than showing an empty page with a valid total.
      if (rows.length === 0 && page > 1) {
        setPage((p) => Math.max(1, p - 1));
        return;
      }
      setEvents(rows);
      setTotal(data.total ?? rows.length);
      setLoadError(null);
    } catch (err) {
      setLoadError(getApiErrorInfo(err));
    } finally {
      setLoading(false);
    }
  }, [page, eventTypeFilter]);

  useEffect(() => {
    if (user && !isAdmin) {
      router.push("/dashboard");
    }
  }, [user, isAdmin, router]);

  useEffect(() => {
    if (!isAdmin) return;
    loadEvents();
  }, [isAdmin, loadEvents]);

  // Filter changes reset to page 1.
  useEffect(() => {
    setPage(1);
  }, [eventTypeFilter]);

  if (!user || !isAdmin) return null;

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Audit Log"
        description="Security events across the platform — sign-ins, password changes, role changes, session activity, and account recoveries. Newest first."
      />

      {/* Filter */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <select
          value={eventTypeFilter}
          onChange={(e) => setEventTypeFilter(e.target.value)}
          className="px-3 py-1.5 text-xs font-medium border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
          aria-label="Filter by event type"
        >
          <option value="all">All Event Types</option>
          {EVENT_TYPES.map((t) => (
            <option key={t} value={t}>
              {humanizeEventType(t)}
            </option>
          ))}
        </select>
        <p className="text-xs text-[var(--text-muted)]">
          {loading ? "Loading…" : `${total} event${total !== 1 ? "s" : ""}`}
        </p>
      </div>

      {/* Table */}
      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
            <div
              key={i}
              className="h-12 bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl skeleton"
            />
          ))}
        </div>
      ) : loadError && events.length === 0 ? (
        <LoadErrorState
          error={loadError}
          subject="audit events"
          onRetry={loadEvents}
        />
      ) : events.length === 0 ? (
        <EmptyState
          title="No audit events"
          description="No security events match the current filter."
          icon={
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          }
        />
      ) : (
        <>
          <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl overflow-hidden shadow-card">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border-default)] bg-[var(--bg-secondary)]/50">
                    <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Timestamp</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Event</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Actor</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Description</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">IP Address</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-default)]">
                  {events.map((e) => (
                    <tr key={e.id} className="hover:bg-[var(--bg-secondary)]/50 transition-colors">
                      <td className="px-4 py-3 text-xs text-[var(--text-muted)] whitespace-nowrap">
                        {formatTimestamp(e.created_at)}
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-[var(--bg-secondary)] text-[var(--text-secondary)] capitalize">
                          {humanizeEventType(e.event_type)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-[var(--text-primary)]">
                        {e.user_name ?? e.user_id ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-xs text-[var(--text-secondary)] max-w-md">
                        {e.description ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-xs text-[var(--text-muted)] font-mono">
                        {e.ip_address ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Pagination footer (Phase 54 convention) */}
          {total > 0 && (
            <div className="flex items-center justify-between pt-4 text-sm">
              <p className="text-xs text-[var(--text-muted)]">
                Showing {Math.min((page - 1) * PAGE_SIZE + 1, total)}–{Math.min(page * PAGE_SIZE, total)} of {total} events · Page {page} of {totalPages}
              </p>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={page <= 1 || loading}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={page >= totalPages || loading}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
