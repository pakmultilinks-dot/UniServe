"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import {
  getUsersPaginated,
  getCafeterias,
  suspendUser,
  activateUser,
  recoverUser,
  getApiErrorInfo,
} from "@/lib/api";
import type { ApiErrorInfo } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadErrorState } from "@/components/ui/LoadErrorState";
import { Button } from "@/components/ui/Button";
import { RoleBadge, roleLabel } from "@/components/admin/RoleBadge";
import { AddMemberModal } from "@/components/admin/AddMemberModal";
import { ChangeRoleModal } from "@/components/admin/ChangeRoleModal";
import { MemberDetailsModal } from "@/components/admin/MemberDetailsModal";
import { ModalShell } from "@/components/admin/ModalShell";
import type { Cafeteria, User } from "@uniserve/shared-types";

const ROLE_FILTERS = ["all", "student", "faculty", "cafeteria_staff", "cafeteria_manager", "university_admin"] as const;
const STATUSES = ["all", "active", "suspended", "pending_verification"] as const;

export default function UsersPage() {
  const { user } = useAuth();
  const router = useRouter();
  const isAdmin = user?.role === "university_admin";

  const [users, setUsers] = useState<User[]>([]);
  const [cafeterias, setCafeterias] = useState<Cafeteria[]>([]);
  const [loading, setLoading] = useState(true);
  const [roleFilter, setRoleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [cafeteriaFilter, setCafeteriaFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  /* Phase 46 — explicit request-failure state (see LoadErrorState). */
  const [loadError, setLoadError] = useState<ApiErrorInfo | null>(null);
  const [cafeteriasError, setCafeteriasError] = useState<ApiErrorInfo | null>(null);
  const { toast } = useToast();

  /* Phase 47 — member management dialogs */
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [detailsUserId, setDetailsUserId] = useState<string | null>(null);
  const [roleModalUser, setRoleModalUser] = useState<User | null>(null);
  const [cafeteriaModalUser, setCafeteriaModalUser] = useState<User | null>(null);
  const [suspendModal, setSuspendModal] = useState<{ member: User; reason: string } | null>(null);
  const [activateModalUser, setActivateModalUser] = useState<User | null>(null);
  /* Phase 55 — server-side pagination + account recovery */
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [copied, setCopied] = useState(false);
  const [recoverModal, setRecoverModal] = useState<{
    member: User;
    universityId: string;
    reason: string;
    tempPassword: string | null;
  } | null>(null);
  const PAGE_SIZE = 10;

  useEffect(() => {
    if (user && !isAdmin) {
      router.push("/dashboard");
    }
  }, [user, isAdmin, router]);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      // Phase 55 — server-side pagination + filters via GET /users?limit&offset.
      const params: Parameters<typeof getUsersPaginated>[0] = {
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      };
      if (roleFilter !== "all") params.role = roleFilter;
      if (statusFilter !== "all") params.status = statusFilter;
      if (cafeteriaFilter !== "all") params.cafeteria_id = cafeteriaFilter;
      if (debouncedSearch) params.q = debouncedSearch;
      const data = await getUsersPaginated(params);
      const rows = data.users ?? [];
      // If the current page emptied out (e.g. an action removed the last
      // row on this page under an active filter), step back one page.
      if (rows.length === 0 && page > 1) {
        setPage((p) => Math.max(1, p - 1));
        return;
      }
      setUsers(rows);
      setTotal(data.total ?? rows.length);
      setLoadError(null);
    } catch (err) {
      // Phase 46 — surface the failure; "No members found" must only ever be
      // shown for a genuinely empty result. Previously loaded members stay on
      // screen (with a compact retry banner) if a refresh fails.
      setLoadError(getApiErrorInfo(err));
    } finally {
      setLoading(false);
    }
  }, [page, roleFilter, statusFilter, cafeteriaFilter, debouncedSearch]);

  const loadCafeterias = useCallback(async () => {
    try {
      const data = await getCafeterias();
      setCafeterias(Array.isArray(data) ? data : []);
      setCafeteriasError(null);
    } catch (err) {
      setCafeteriasError(getApiErrorInfo(err));
    }
  }, []);

  useEffect(() => {
    if (!isAdmin) return;
    loadUsers();
    loadCafeterias();
  }, [isAdmin, loadUsers, loadCafeterias]);

  /* Phase 55 — filter/search changes reset to page 1 (server-side paging). */
  useEffect(() => {
    setPage(1);
  }, [roleFilter, statusFilter, cafeteriaFilter]);

  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedSearch(searchQuery.trim());
      setPage(1);
    }, 400);
    return () => clearTimeout(t);
  }, [searchQuery]);

  const handleSuspend = async (userId: string, reason: string) => {
    setActionLoading(userId);
    try {
      await suspendUser(userId, reason);
      await loadUsers();
      toast("Member suspended.", "success");
    } catch (err) {
      toast(getApiErrorInfo(err).message, "error");
    } finally {
      setActionLoading(null);
    }
  };

  const handleActivate = async (userId: string) => {
    setActionLoading(userId);
    try {
      await activateUser(userId);
      await loadUsers();
      toast("Member activated.", "success");
    } catch (err) {
      toast(getApiErrorInfo(err).message, "error");
    } finally {
      setActionLoading(null);
    }
  };

  /* Phase 55 — client-side filtering removed: role/status/cafeteria/search
     are applied server-side (GET /users?role&status&cafeteria_id&q) together
     with limit/offset pagination. */

  const handleRecover = async (member: User, universityId: string, reason: string) => {
    setActionLoading(member.id);
    try {
      const res = await recoverUser(member.id, {
        university_id: universityId,
        reason: reason || undefined,
      });
      // Show the one-time temporary password exactly once in the modal.
      setRecoverModal({
        member,
        universityId,
        reason,
        tempPassword: res.temporary_password,
      });
      await loadUsers();
    } catch (err) {
      toast(getApiErrorInfo(err).message, "error");
      setRecoverModal(null);
    } finally {
      setActionLoading(null);
    }
  };

  const formatDate = (iso: string) => {
    try { return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }); }
    catch { return iso; }
  };

  if (!user || !isAdmin) return null;

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Members"
        description="Manage member accounts, roles, cafeteria assignments, and access status"
        actions={
          <Button onClick={() => setAddModalOpen(true)}>Add Member</Button>
        }
      />

      {/* Phase 46 — member list refresh failure (compact, retryable) */}
      {loadError && users.length > 0 && (
        <LoadErrorState
          compact
          error={loadError}
          subject="members"
          onRetry={() => loadUsers()}
          className="mb-6 border border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-900/10 rounded-xl"
        />
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <input
          type="text"
          placeholder="Search name, email, ID, cafeteria…"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)] w-72"
        />
        <div className="flex gap-1 flex-wrap">
          {ROLE_FILTERS.map((role) => (
            <button
              key={role}
              onClick={() => setRoleFilter(role)}
              className={`px-3 py-1.5 text-xs font-medium rounded-full capitalize transition-colors whitespace-nowrap ${
                roleFilter === role
                  ? "bg-brand-600 text-white"
                  : "bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-brand-50"
              }`}
            >
              {role === "all" ? "All Roles" : roleLabel(role)}
            </button>
          ))}
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-1.5 text-xs font-medium border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>{s === "all" ? "All Statuses" : s.replace(/_/g, " ")}</option>
          ))}
        </select>
        <select
          value={cafeteriaFilter}
          onChange={(e) => setCafeteriaFilter(e.target.value)}
          className="px-3 py-1.5 text-xs font-medium border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
        >
          <option value="all">All Cafeterias</option>
          <option value="none">Unassigned</option>
          {cafeterias.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      </div>

      {/* Cafeteria list failure — filter still works, but cafeteria options
          and staff assignment pickers may be empty until retried. */}
      {cafeteriasError && (
        <LoadErrorState
          compact
          error={cafeteriasError}
          subject="cafeterias"
          onRetry={() => loadCafeterias()}
          className="mb-6 border border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-900/10 rounded-xl"
        />
      )}

      {/* Members table */}
      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-14 bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl skeleton" />
          ))}
        </div>
      ) : loadError && users.length === 0 ? (
        <LoadErrorState
          error={loadError}
          subject="members"
          onRetry={() => loadUsers()}
        />
      ) : users.length === 0 ? (
        <EmptyState
          title="No members found"
          description="Try adjusting your filters, or add a new member."
          icon={
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
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
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Member</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">University ID</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Role</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Cafeteria</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Joined</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-[var(--text-muted)] uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-default)]">
                {users.map((u) => {
                  const isSelf = u.id === user?.id;
                  const needsCafeteria = u.role === "cafeteria_staff" || u.role === "cafeteria_manager";
                  return (
                    <tr key={u.id} className="hover:bg-[var(--bg-secondary)]/50 transition-colors">
                      <td className="px-4 py-3">
                        <div className="font-medium text-[var(--text-primary)]">
                          {u.first_name} {u.last_name}
                          {isSelf && (
                            <span className="ml-2 text-xs text-[var(--text-muted)]">(you)</span>
                          )}
                        </div>
                        <div className="text-xs text-[var(--text-muted)]">{u.university_email}</div>
                      </td>
                      <td className="px-4 py-3 text-[var(--text-secondary)] font-mono text-xs">{u.university_id}</td>
                      <td className="px-4 py-3"><RoleBadge role={u.role} /></td>
                      <td className="px-4 py-3 text-[var(--text-secondary)]">
                        {u.cafeteria_name ?? (needsCafeteria ? "—" : "Not assigned")}
                      </td>
                      <td className="px-4 py-3"><StatusBadge status={u.status} /></td>
                      <td className="px-4 py-3 text-xs text-[var(--text-muted)]">{formatDate(u.created_at)}</td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex gap-1 justify-end flex-wrap">
                          <Button size="sm" variant="ghost" onClick={() => setDetailsUserId(u.id)}>
                            View
                          </Button>
                          {!isSelf && (
                            <>
                              <Button size="sm" variant="secondary" onClick={() => setRoleModalUser(u)}>
                                Role
                              </Button>
                              {needsCafeteria && (
                                <Button size="sm" variant="secondary" onClick={() => setCafeteriaModalUser(u)}>
                                  Cafeteria
                                </Button>
                              )}
                              {u.status === "active" ? (
                                <Button
                                  size="sm"
                                  variant="danger"
                                  loading={actionLoading === u.id}
                                  onClick={() => setSuspendModal({ member: u, reason: "" })}
                                >
                                  Suspend
                                </Button>
                              ) : u.status === "suspended" ? (
                                <Button
                                  size="sm"
                                  variant="primary"
                                  loading={actionLoading === u.id}
                                  onClick={() => setActivateModalUser(u)}
                                >
                                  Activate
                                </Button>
                              ) : null}
                              <Button
                                size="sm"
                                variant="secondary"
                                loading={actionLoading === u.id}
                                onClick={() => {
                                  setCopied(false);
                                  setRecoverModal({
                                    member: u,
                                    universityId: "",
                                    reason: "",
                                    tempPassword: null,
                                  });
                                }}
                              >
                                Recover
                              </Button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Phase 55 — pagination footer (backend limit/offset; filters and
            search are preserved because loadUsers reads all filter state) */}
        {total > 0 && (
          <div className="flex items-center justify-between pt-4 text-sm">
            <p className="text-xs text-[var(--text-muted)]">
              Showing {Math.min((page - 1) * PAGE_SIZE + 1, total)}–{Math.min(page * PAGE_SIZE, total)} of {total} members · Page {page} of {Math.max(1, Math.ceil(total / PAGE_SIZE))}
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
                disabled={page >= Math.ceil(total / PAGE_SIZE) || loading}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
        </>
      )}

      {/* ─── Add member modal ─── */}
      {addModalOpen && (
        <AddMemberModal
          cafeterias={cafeterias}
          onClose={() => setAddModalOpen(false)}
          onCreated={loadUsers}
        />
      )}

      {/* ─── Member details modal ─── */}
      {detailsUserId && (
        <MemberDetailsModal
          userId={detailsUserId}
          onClose={() => setDetailsUserId(null)}
        />
      )}

      {/* ─── Change role modal ─── */}
      {roleModalUser && (
        <ChangeRoleModal
          member={roleModalUser}
          mode="role"
          cafeterias={cafeterias}
          onClose={() => setRoleModalUser(null)}
          onUpdated={loadUsers}
        />
      )}

      {/* ─── Change cafeteria modal ─── */}
      {cafeteriaModalUser && (
        <ChangeRoleModal
          member={cafeteriaModalUser}
          mode="cafeteria"
          cafeterias={cafeterias}
          onClose={() => setCafeteriaModalUser(null)}
          onUpdated={loadUsers}
        />
      )}

      {/* ─── Suspend member modal (named target + reason) ─── */}
      {suspendModal && (
        <ModalShell onClose={() => setSuspendModal(null)}>
          <h3 className="text-base font-semibold text-[var(--text-primary)] mb-2">
            Suspend {suspendModal.member.first_name} {suspendModal.member.last_name}?
          </h3>
          <p className="text-sm text-[var(--text-secondary)] mb-4">
            They will no longer be able to sign in until reactivated. Any active
            sessions will be revoked.
          </p>
          <label className="block text-sm text-[var(--text-secondary)] mb-1">Reason for suspension</label>
          <textarea
            value={suspendModal.reason}
            onChange={(e) => setSuspendModal({ ...suspendModal, reason: e.target.value })}
            className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
            rows={3}
            placeholder="Provide a reason for suspending this member…"
            autoFocus
          />
          <div className="flex justify-end gap-2 mt-4">
            <Button size="sm" variant="ghost" onClick={() => setSuspendModal(null)}>Cancel</Button>
            <Button
              size="sm"
              variant="danger"
              loading={actionLoading === suspendModal.member.id}
              disabled={!suspendModal.reason.trim()}
              onClick={() => {
                handleSuspend(suspendModal.member.id, suspendModal.reason.trim());
                setSuspendModal(null);
              }}
            >
              Confirm Suspend
            </Button>
          </div>
        </ModalShell>
      )}

      {/* ─── Activate member modal (named target confirmation) ─── */}
      {activateModalUser && (
        <ModalShell onClose={() => setActivateModalUser(null)}>
          <h3 className="text-base font-semibold text-[var(--text-primary)] mb-2">
            Activate {activateModalUser.first_name} {activateModalUser.last_name}?
          </h3>
          <p className="text-sm text-[var(--text-secondary)] mb-4">
            They will be able to sign in again with their existing credentials.
          </p>
          <div className="flex justify-end gap-2">
            <Button size="sm" variant="ghost" onClick={() => setActivateModalUser(null)}>Cancel</Button>
            <Button
              size="sm"
              loading={actionLoading === activateModalUser.id}
              onClick={() => {
                handleActivate(activateModalUser.id);
                setActivateModalUser(null);
              }}
            >
              Confirm Activate
            </Button>
          </div>
        </ModalShell>
      )}

      {/* ─── Phase 55 — Account recovery modal ─── */}
      {recoverModal && (
        <ModalShell onClose={() => setRecoverModal(null)} maxWidth="max-w-md">
          {recoverModal.tempPassword ? (
            /* One-time temporary password display */
            <div>
              <h3 className="text-base font-semibold text-[var(--text-primary)] mb-2">
                Account recovered
              </h3>
              <p className="text-sm text-[var(--text-secondary)] mb-4">
                {recoverModal.member.first_name} {recoverModal.member.last_name} can
                now sign in with this temporary password:
              </p>
              <div className="flex items-center gap-2 mb-3">
                <code className="flex-1 px-3 py-2 text-sm font-mono bg-[var(--bg-secondary)] border border-[var(--border-default)] rounded-lg text-[var(--text-primary)] select-all">
                  {recoverModal.tempPassword}
                </code>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    const value = recoverModal.tempPassword;
                    if (!value) return;
                    navigator.clipboard
                      ?.writeText(value)
                      .then(() => {
                        setCopied(true);
                        setTimeout(() => setCopied(false), 2000);
                      })
                      .catch(() =>
                        toast("Copy failed — select the password manually.", "error"),
                      );
                  }}
                >
                  {copied ? "Copied" : "Copy"}
                </Button>
              </div>
              <p className="text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg px-3 py-2 mb-4">
                This password is shown only once. Deliver it to the user through a
                secure channel and ask them to change it after signing in.
              </p>
              <div className="flex justify-end">
                <Button size="sm" variant="primary" onClick={() => setRecoverModal(null)}>
                  Done
                </Button>
              </div>
            </div>
          ) : (
            /* Confirmation step — university ID must match exactly */
            <div>
              <h3 className="text-base font-semibold text-[var(--text-primary)] mb-2">
                Recover {recoverModal.member.first_name} {recoverModal.member.last_name}?
              </h3>
              <p className="text-sm text-[var(--text-secondary)] mb-4">
                This resets their password to a one-time temporary password, clears
                any login lockouts, and reactivates the account if suspended. The
                current password stops working immediately.
              </p>
              <label className="block text-sm text-[var(--text-secondary)] mb-1">
                Confirm University ID
              </label>
              <input
                type="text"
                value={recoverModal.universityId}
                onChange={(e) =>
                  setRecoverModal({ ...recoverModal, universityId: e.target.value })
                }
                placeholder={recoverModal.member.university_id}
                className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)] font-mono mb-3"
                autoFocus
              />
              <label className="block text-sm text-[var(--text-secondary)] mb-1">
                Reason (optional)
              </label>
              <textarea
                value={recoverModal.reason}
                onChange={(e) =>
                  setRecoverModal({ ...recoverModal, reason: e.target.value })
                }
                className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
                rows={2}
                placeholder="e.g. Forgot password — verified in person"
              />
              <div className="flex justify-end gap-2 mt-4">
                <Button size="sm" variant="ghost" onClick={() => setRecoverModal(null)}>
                  Cancel
                </Button>
                <Button
                  size="sm"
                  variant="danger"
                  loading={actionLoading === recoverModal.member.id}
                  disabled={
                    recoverModal.universityId.trim() !==
                    recoverModal.member.university_id
                  }
                  onClick={() =>
                    handleRecover(
                      recoverModal.member,
                      recoverModal.universityId.trim(),
                      recoverModal.reason.trim(),
                    )
                  }
                >
                  Confirm Recover
                </Button>
              </div>
            </div>
          )}
        </ModalShell>
      )}
    </div>
  );
}
