"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import {
  getUsers,
  getCafeterias,
  suspendUser,
  activateUser,
  getApiErrorInfo,
} from "@/lib/api";
import type { ApiErrorInfo } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadErrorState } from "@/components/ui/LoadErrorState";
import { Button } from "@/components/ui/Button";
import { RoleBadge } from "@/components/admin/RoleBadge";
import { AddMemberModal } from "@/components/admin/AddMemberModal";
import { ChangeRoleModal } from "@/components/admin/ChangeRoleModal";
import { MemberDetailsModal } from "@/components/admin/MemberDetailsModal";
import { ModalShell } from "@/components/admin/ModalShell";
import type { Cafeteria, User } from "@uniserve/shared-types";

const STATUSES = ["all", "active", "suspended", "pending_verification"] as const;

const OPERATIONAL_ROLES = new Set(["cafeteria_staff", "cafeteria_manager"]);

/**
 * Phase 47 — Staff & Managers screen.
 * Loads all members once and filters to operational roles (staff + managers —
 * Phase 45 only listed staff). Reuses the shared member-management dialogs.
 */
export default function StaffPage() {
  const { user } = useAuth();
  const router = useRouter();
  const isAdmin = user?.role === "university_admin";

  const [users, setUsers] = useState<User[]>([]);
  const [cafeterias, setCafeterias] = useState<Cafeteria[]>([]);
  const [loading, setLoading] = useState(true);
  const [roleFilter, setRoleFilter] = useState<"all" | "cafeteria_staff" | "cafeteria_manager">("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [cafeteriaFilter, setCafeteriaFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  /* Phase 46 — explicit request-failure state (see LoadErrorState). */
  const [loadError, setLoadError] = useState<ApiErrorInfo | null>(null);
  const [cafeteriasError, setCafeteriasError] = useState<ApiErrorInfo | null>(null);
  const { toast } = useToast();

  /* Phase 47 — staff management dialogs */
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [detailsUserId, setDetailsUserId] = useState<string | null>(null);
  const [cafeteriaModalUser, setCafeteriaModalUser] = useState<User | null>(null);
  const [suspendModal, setSuspendModal] = useState<{ member: User; reason: string } | null>(null);
  const [activateModalUser, setActivateModalUser] = useState<User | null>(null);

  useEffect(() => {
    if (user && !isAdmin) {
      router.push("/dashboard");
    }
  }, [user, isAdmin, router]);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getUsers();
      setUsers(Array.isArray(data) ? data : []);
      setLoadError(null);
    } catch (err) {
      // Phase 46 — failures are surfaced explicitly, never as an empty list.
      setLoadError(getApiErrorInfo(err));
    } finally {
      setLoading(false);
    }
  }, []);

  const loadCafeterias = useCallback(async () => {
    try {
      // Phase 56 — staff assignment is an operational surface: only
      // ACTIVE cafeterias are offered.
      const data = await getCafeterias({ isActive: true });
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

  const handleSuspend = async (userId: string, reason: string) => {
    setActionLoading(userId);
    try {
      await suspendUser(userId, reason);
      await loadUsers();
      toast("Staff member suspended.", "success");
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
      toast("Staff member activated.", "success");
    } catch (err) {
      toast(getApiErrorInfo(err).message, "error");
    } finally {
      setActionLoading(null);
    }
  };

  /* Operational roles only — managers were missing from Phase 45. */
  const staffMembers = users.filter((u) => OPERATIONAL_ROLES.has(u.role));
  const filteredMembers = staffMembers.filter((u) => {
    if (roleFilter !== "all" && u.role !== roleFilter) return false;
    if (statusFilter !== "all" && u.status !== statusFilter) return false;
    if (cafeteriaFilter !== "all" && u.cafeteria_id !== cafeteriaFilter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matches =
        u.first_name?.toLowerCase().includes(q) ||
        u.last_name?.toLowerCase().includes(q) ||
        u.university_email?.toLowerCase().includes(q) ||
        u.university_id?.toLowerCase().includes(q) ||
        u.cafeteria_name?.toLowerCase().includes(q);
      if (!matches) return false;
    }
    return true;
  });

  const formatDate = (iso: string) => {
    try { return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }); }
    catch { return iso; }
  };

  if (!user || !isAdmin) return null;

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Staff & Managers"
        description="Cafeteria operational accounts — assignments, status, and access"
        actions={
          <Button onClick={() => setAddModalOpen(true)}>Add Staff</Button>
        }
      />

      {/* Phase 46 — staff list refresh failure (compact, retryable) */}
      {loadError && users.length > 0 && (
        <LoadErrorState
          compact
          error={loadError}
          subject="staff & managers"
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
        <div className="flex gap-1">
          {(["all", "cafeteria_staff", "cafeteria_manager"] as const).map((role) => (
            <button
              key={role}
              onClick={() => setRoleFilter(role)}
              className={`px-3 py-1.5 text-xs font-medium rounded-full transition-colors whitespace-nowrap ${
                roleFilter === role
                  ? "bg-brand-600 text-white"
                  : "bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-brand-50"
              }`}
            >
              {role === "all" ? "All Staff" : role === "cafeteria_staff" ? "Staff" : "Managers"}
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
          {cafeterias.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      </div>

      {cafeteriasError && (
        <LoadErrorState
          compact
          error={cafeteriasError}
          subject="cafeterias"
          onRetry={() => loadCafeterias()}
          className="mb-6 border border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-900/10 rounded-xl"
        />
      )}

      {/* Staff table */}
      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-14 bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl skeleton" />
          ))}
        </div>
      ) : loadError && users.length === 0 ? (
        <LoadErrorState
          error={loadError}
          subject="staff & managers"
          onRetry={() => loadUsers()}
        />
      ) : filteredMembers.length === 0 ? (
        <EmptyState
          title="No staff members found"
          description="Try adjusting your filters, or add a staff account."
          icon={
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
          }
        />
      ) : (
        <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl overflow-hidden shadow-card">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border-default)] bg-[var(--bg-secondary)]/50">
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Name</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Email</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Role</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Cafeteria</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Joined</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-[var(--text-muted)] uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-default)]">
                {filteredMembers.map((u) => (
                  <tr key={u.id} className="hover:bg-[var(--bg-secondary)]/50 transition-colors">
                    <td className="px-4 py-3 font-medium text-[var(--text-primary)]">
                      {u.first_name} {u.last_name}
                    </td>
                    <td className="px-4 py-3 text-[var(--text-secondary)]">{u.university_email}</td>
                    <td className="px-4 py-3"><RoleBadge role={u.role} /></td>
                    <td className="px-4 py-3 text-[var(--text-secondary)]">
                      {u.cafeteria_name ?? "—"}
                    </td>
                    <td className="px-4 py-3"><StatusBadge status={u.status} /></td>
                    <td className="px-4 py-3 text-xs text-[var(--text-muted)]">{formatDate(u.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex gap-1 justify-end flex-wrap">
                        <Button size="sm" variant="ghost" onClick={() => setDetailsUserId(u.id)}>
                          View
                        </Button>
                        <Button size="sm" variant="secondary" onClick={() => setCafeteriaModalUser(u)}>
                          Cafeteria
                        </Button>
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
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ─── Add staff modal (role preselected) ─── */}
      {addModalOpen && (
        <AddMemberModal
          cafeterias={cafeterias}
          preselectedRole="cafeteria_staff"
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

      {/* ─── Suspend staff modal (named target + reason) ─── */}
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
            placeholder="Provide a reason for suspending this staff member…"
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

      {/* ─── Activate staff modal (named target confirmation) ─── */}
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
    </div>
  );
}
