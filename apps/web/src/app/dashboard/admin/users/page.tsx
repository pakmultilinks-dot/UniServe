"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { getUsers, suspendUser, activateUser, changeUserRole } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";
import type { User } from "@uniserve/shared-types";

const ROLES = ["all", "student", "faculty", "cafeteria_staff", "cafeteria_manager", "university_admin"] as const;
const STATUSES = ["all", "active", "suspended", "pending_verification"] as const;

export default function UsersPage() {
  const { user } = useAuth();
  const router = useRouter();
  const isAdmin = user?.role === "university_admin";

  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [roleFilter, setRoleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const { toast } = useToast();

  /* Inline modal state — replaces window.prompt */
  const [suspendModal, setSuspendModal] = useState<{ userId: string; reason: string } | null>(null);

  useEffect(() => {
    if (user && !isAdmin) {
      router.push("/dashboard");
    }
  }, [user, isAdmin, router]);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getUsers({
        role: roleFilter !== "all" ? roleFilter : undefined,
        status: statusFilter !== "all" ? statusFilter : undefined,
      });
      setUsers(Array.isArray(data) ? data : []);
    } catch {
      setUsers([]);
    } finally {
      setLoading(false);
    }
  }, [roleFilter, statusFilter]);

  useEffect(() => { loadUsers(); }, [loadUsers]);

  const handleSuspend = async (userId: string, reason: string) => {
    setActionLoading(userId);
    try {
      await suspendUser(userId, reason);
      await loadUsers();
      toast("User suspended", "success");
    } catch (err: any) {
      toast(err?.message ?? "Failed", "error");
    } finally {
      setActionLoading(null);
    }
  };

  const handleActivate = async (userId: string) => {
    setActionLoading(userId);
    try {
      await activateUser(userId);
      await loadUsers();
      toast("User activated", "success");
    } catch (err: any) {
      toast(err?.message ?? "Failed", "error");
    } finally {
      setActionLoading(null);
    }
  };

  const handleRoleChange = async (userId: string, newRole: string) => {
    setActionLoading(userId);
    try {
      await changeUserRole(userId, newRole);
      await loadUsers();
      toast("Role updated", "success");
    } catch (err: any) {
      toast(err?.message ?? "Failed", "error");
    } finally {
      setActionLoading(null);
    }
  };

  const filteredUsers = users.filter((u) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      u.first_name?.toLowerCase().includes(q) ||
      u.last_name?.toLowerCase().includes(q) ||
      u.university_email?.toLowerCase().includes(q) ||
      u.university_id?.toLowerCase().includes(q)
    );
  });

  const formatDate = (iso: string) => {
    try { return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }); }
    catch { return iso; }
  };

  if (!user || !isAdmin) return null;

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="User Management"
        description="Manage student, faculty, staff, and manager accounts"
        actions={
          <input
            type="text"
            placeholder="Search users..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)] w-64"
          />
        }
      />

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        <div className="flex gap-1">
          {ROLES.map((role) => (
            <button
              key={role}
              onClick={() => setRoleFilter(role)}
              className={`px-3 py-1.5 text-xs font-medium rounded-full capitalize transition-colors whitespace-nowrap ${
                roleFilter === role
                  ? "bg-brand-600 text-white"
                  : "bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-brand-50"
              }`}
            >
              {role.replace(/_/g, " ")}
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
      </div>

      {/* Users table */}
      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-14 bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl skeleton" />
          ))}
        </div>
      ) : filteredUsers.length === 0 ? (
        <EmptyState
          title="No users found"
          description="Try adjusting your filters."
          icon={
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
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
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">ID</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Role</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase">Joined</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-[var(--text-muted)] uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-default)]">
                {filteredUsers.map((u) => (
                  <tr key={u.id} className="hover:bg-[var(--bg-secondary)]/50 transition-colors">
                    <td className="px-4 py-3 font-medium text-[var(--text-primary)]">
                      {u.first_name} {u.last_name}
                    </td>
                    <td className="px-4 py-3 text-[var(--text-secondary)]">{u.university_email}</td>
                    <td className="px-4 py-3 text-[var(--text-secondary)] font-mono text-xs">{u.university_id}</td>
                    <td className="px-4 py-3">
                      <select
                        value={u.role}
                        onChange={(e) => handleRoleChange(u.id, e.target.value)}
                        disabled={u.id === user?.id}
                        className="text-xs px-2 py-1 rounded border border-[var(--border-default)] bg-[var(--bg-primary)] text-[var(--text-primary)] disabled:opacity-50"
                      >
                        {["student", "faculty", "cafeteria_staff", "cafeteria_manager", "university_admin"].map((r) => (
                          <option key={r} value={r}>{r.replace(/_/g, " ")}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-3"><StatusBadge status={u.status} /></td>
                    <td className="px-4 py-3 text-xs text-[var(--text-muted)]">{formatDate(u.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      {u.id !== user?.id && (
                        <div className="flex gap-1 justify-end">
                          {u.status === "active" ? (
                            <Button
                              size="sm"
                              variant="danger"
                              loading={actionLoading === u.id}
                              onClick={() => setSuspendModal({ userId: u.id, reason: "" })}
                            >
                              Suspend
                            </Button>
                          ) : u.status === "suspended" ? (
                            <Button
                              size="sm"
                              variant="primary"
                              loading={actionLoading === u.id}
                              onClick={() => handleActivate(u.id)}
                            >
                              Activate
                            </Button>
                          ) : null}
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

      {/* ─── Suspend user modal ─── */}
      {suspendModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setSuspendModal(null)}>
          <div
            className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-xl w-full max-w-sm mx-4 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-base font-semibold text-[var(--text-primary)] mb-3">Suspend User</h3>
            <label className="block text-sm text-[var(--text-secondary)] mb-1">Reason for suspension</label>
            <textarea
              value={suspendModal.reason}
              onChange={(e) => setSuspendModal({ ...suspendModal, reason: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
              rows={3}
              placeholder="Provide a reason for suspending this user..."
              autoFocus
            />
            <div className="flex justify-end gap-2 mt-4">
              <Button size="sm" variant="ghost" onClick={() => setSuspendModal(null)}>Cancel</Button>
              <Button
                size="sm"
                variant="danger"
                loading={actionLoading === suspendModal.userId}
                onClick={() => {
                  if (!suspendModal.reason.trim()) return;
                  handleSuspend(suspendModal.userId, suspendModal.reason);
                  setSuspendModal(null);
                }}
              >
                Confirm Suspend
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
