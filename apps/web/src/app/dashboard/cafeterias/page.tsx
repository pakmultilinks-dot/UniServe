"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { getCafeterias, updateCafeteriaStatus, updateCafeteria, createCafeteria, getApiErrorInfo } from "@/lib/api";
import type { ApiErrorInfo } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadErrorState } from "@/components/ui/LoadErrorState";
import { Button } from "@/components/ui/Button";
import type { Cafeteria } from "@uniserve/shared-types";

export default function CafeteriasPage() {
  const { user } = useAuth();
  const { toast } = useToast();
  const isManager = user?.role === "cafeteria_manager";
  const isAdmin = user?.role === "university_admin";
  // Status toggle: manager + admin (PATCH allows both). Edit: admin only
  // (PUT /cafeterias/{id} is university-admin only).
  const canManage = isManager || isAdmin;
  const canEdit = isAdmin;

  useEffect(() => {
    if (!user) return;
  }, [user]);

  const [cafeterias, setCafeterias] = useState<Cafeteria[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ name: "", location: "", description: "" });
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  /* Phase 46 — explicit request-failure state. A failed load must never be
     rendered as an empty cafeteria list (the Phase 45 defect behind the
     "Overview says 2 cafeterias / Cafeterias page says none" confusion). */
  const [loadError, setLoadError] = useState<ApiErrorInfo | null>(null);
  /* Phase 48A — cafeteria creation modal (admin) + deactivation confirmation. */
  const [showAddModal, setShowAddModal] = useState(false);
  const [confirmDeactivate, setConfirmDeactivate] = useState<Cafeteria | null>(null);
  const [toggleLoading, setToggleLoading] = useState(false);

  const loadCafeterias = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await getCafeterias();
      setCafeterias(data);
    } catch (err) {
      // Phase 46 — never swallow. Previously loaded data stays on screen;
      // the render shows a retryable error state when there is nothing to
      // show, and a compact banner when stale data is still visible.
      setLoadError(getApiErrorInfo(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (user) loadCafeterias(); }, [user, loadCafeterias]);

  const handleToggleStatus = async (cafeteria: Cafeteria) => {
    const newStatus = cafeteria.operational_status === "open" ? "closed" : "open";
    setActionLoading(cafeteria.id);
    try {
      await updateCafeteriaStatus(cafeteria.id, newStatus);
      await loadCafeterias();
      toast("Status updated", "success");
    } catch (err) {
      toast(getApiErrorInfo(err).message, "error");
    } finally {
      setActionLoading(null);
    }
  };

  /* 48A — is_active is a filter flag only: backend verified NOT to cascade
     to menu items, orders, staff assignments or users. Deactivation hides
     the cafeteria from active lists; all data is preserved. Activation is
     immediate; deactivation goes through a named confirmation modal. */
  const handleActivate = async (cafeteria: Cafeteria) => {
    setActionLoading(cafeteria.id);
    try {
      await updateCafeteria(cafeteria.id, { is_active: true });
      await loadCafeterias();
      toast(`${cafeteria.name} activated`, "success");
    } catch (err) {
      toast(getApiErrorInfo(err).message, "error");
    } finally {
      setActionLoading(null);
    }
  };

  const handleConfirmDeactivate = async () => {
    if (!confirmDeactivate) return;
    setToggleLoading(true);
    try {
      await updateCafeteria(confirmDeactivate.id, { is_active: false });
      const name = confirmDeactivate.name;
      setConfirmDeactivate(null);
      await loadCafeterias();
      toast(`${name} deactivated`, "success");
    } catch (err) {
      toast(getApiErrorInfo(err).message, "error");
    } finally {
      setToggleLoading(false);
    }
  };

  const handleEdit = (cafeteria: Cafeteria) => {
    setEditingId(cafeteria.id);
    setEditForm({
      name: cafeteria.name,
      location: cafeteria.location ?? "",
      description: cafeteria.description ?? "",
    });
  };

  const handleSaveEdit = async () => {
    if (!editingId) return;
    setActionLoading(editingId);
    try {
      await updateCafeteria(editingId, editForm);
      setEditingId(null);
      await loadCafeterias();
      toast("Cafeteria updated", "success");
    } catch (err) {
      toast(getApiErrorInfo(err).message, "error");
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Cafeterias"
        description="Manage cafeteria locations and status"
      />

      {/* 48A — admin creates new cafeterias through the real API */}
      {canEdit && (
        <div className="flex justify-end mb-4">
          <Button variant="primary" onClick={() => setShowAddModal(true)}>
            + Add Cafeteria
          </Button>
        </div>
      )}

      {/* Phase 46 — refresh failure while data is still on screen */}
      {!loading && loadError && cafeterias.length > 0 && (
        <LoadErrorState
          compact
          error={loadError}
          subject="cafeterias"
          onRetry={() => loadCafeterias()}
          className="mb-4 border border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-900/10 rounded-xl"
        />
      )}

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2].map((i) => (
            <div key={i} className="h-48 bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl skeleton" />
          ))}
        </div>
      ) : loadError && cafeterias.length === 0 ? (
        <LoadErrorState
          error={loadError}
          subject="cafeterias"
          onRetry={() => loadCafeterias()}
        />
      ) : cafeterias.length === 0 ? (
        <EmptyState
          title="No cafeterias found."
          description="Cafeteria locations will appear here."
          icon={
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 21v-8.25M15.75 21v-8.25M8.25 21v-8.25M3 9l9-6 9 6m-1.5 12V10.332A48.36 48.36 0 0012 9.75c-2.551 0-5.056.2-7.5.582V21M3 21h18M12 6.75h.008v.008H12V6.75z" />
            </svg>
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {cafeterias.map((cafeteria) => (
            <div
              key={cafeteria.id}
              className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-5 shadow-card hover:shadow-lg transition-shadow"
            >
              {editingId === cafeteria.id ? (
                <div className="space-y-3">
                  <input
                    type="text"
                    value={editForm.name}
                    onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
                    placeholder="Name"
                  />
                  <input
                    type="text"
                    value={editForm.location}
                    onChange={(e) => setEditForm({ ...editForm, location: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
                    placeholder="Location"
                  />
                  <textarea
                    value={editForm.description}
                    onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
                    placeholder="Description"
                    rows={2}
                  />
                  <div className="flex gap-2">
                    <Button size="sm" variant="primary" loading={actionLoading === cafeteria.id} onClick={handleSaveEdit}>
                      Save
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setEditingId(null)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <h3 className="text-lg font-semibold text-[var(--text-primary)]">{cafeteria.name}</h3>
                      <p className="text-xs text-[var(--text-muted)] mt-0.5">{cafeteria.location}</p>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {/* 48A — activation state shown alongside operational status */}
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          cafeteria.is_active
                            ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                            : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"
                        }`}
                      >
                        {cafeteria.is_active ? "Active" : "Inactive"}
                      </span>
                      <StatusBadge status={cafeteria.operational_status} />
                    </div>
                  </div>
                  {cafeteria.description && (
                    <p className="text-sm text-[var(--text-secondary)] mb-3">{cafeteria.description}</p>
                  )}
                  <div className="flex items-center gap-2 text-xs text-[var(--text-muted)] mb-3">
                    <span className="px-2 py-0.5 rounded-full bg-[var(--bg-secondary)] capitalize">
                      {cafeteria.type ?? "student"}
                    </span>
                    {cafeteria.operating_hours && (
                      <span className="flex items-center gap-1">
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        {cafeteria.operating_hours}
                      </span>
                    )}
                  </div>
                  {canManage && (
                    <div className="flex gap-2 pt-2 border-t border-[var(--border-default)]">
                      <Button
                        size="sm"
                        variant={cafeteria.operational_status === "open" ? "danger" : "primary"}
                        loading={actionLoading === cafeteria.id}
                        onClick={() => handleToggleStatus(cafeteria)}
                      >
                        {cafeteria.operational_status === "open" ? "Close" : "Open"}
                      </Button>
                      {canEdit && (
                        <Button size="sm" variant="ghost" onClick={() => handleEdit(cafeteria)}>
                          Edit
                        </Button>
                      )}
                      {canEdit && (
                        <Button
                          size="sm"
                          variant={cafeteria.is_active ? "danger" : "ghost"}
                          loading={actionLoading === cafeteria.id}
                          onClick={() =>
                            cafeteria.is_active
                              ? setConfirmDeactivate(cafeteria)
                              : handleActivate(cafeteria)
                          }
                        >
                          {cafeteria.is_active ? "Deactivate" : "Activate"}
                        </Button>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 48A — Add Cafeteria modal (admin) */}
      {showAddModal && (
        <AddCafeteriaModal
          onClose={() => setShowAddModal(false)}
          onSaved={async () => {
            setShowAddModal(false);
            await loadCafeterias();
            toast("Cafeteria created", "success");
          }}
        />
      )}

      {/* 48A — named deactivation confirmation; data preserved (no cascade) */}
      {confirmDeactivate && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={() => setConfirmDeactivate(null)}
        >
          <div
            className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-xl w-full max-w-sm mx-4 p-6 max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-base font-semibold text-[var(--text-primary)] mb-2">
              Deactivate {confirmDeactivate.name}?
            </h3>
            <p className="text-sm text-[var(--text-secondary)] mb-4">
              The cafeteria will be hidden from active cafeteria lists. Its menu
              items, orders and staff assignments are preserved — you can
              reactivate it at any time.
            </p>
            <div className="flex justify-end gap-2">
              <Button size="sm" variant="ghost" onClick={() => setConfirmDeactivate(null)}>
                Cancel
              </Button>
              <Button size="sm" variant="danger" loading={toggleLoading} onClick={handleConfirmDeactivate}>
                Deactivate
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* 48A — create cafeteria modal. Duplicates surface as 409 "Cafeteria
   already exists" via getApiErrorInfo; the modal stays open on failure. */
function AddCafeteriaModal({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: () => Promise<void> | void;
}) {
  const [form, setForm] = useState({
    name: "",
    type: "student",
    description: "",
    location: "",
  });
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = form.name.trim();
    if (!name) return;
    setSaving(true);
    try {
      await createCafeteria({
        name,
        type: form.type as "student" | "faculty",
        description: form.description.trim() || undefined,
        location: form.location.trim() || undefined,
      });
      await onSaved();
    } catch (err) {
      // Duplicates → 409 "Cafeteria already exists"; validation → 422.
      // Never a raw crash — message rendered through Phase 46 error info.
      toast(getApiErrorInfo(err).message, "error");
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-xl w-full max-w-md mx-4 p-6 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-4">
          Add Cafeteria
        </h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">
              Name *
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
              required
              maxLength={255}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">
              Type *
            </label>
            <select
              value={form.type}
              onChange={(e) => setForm({ ...form, type: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
            >
              <option value="student">Student</option>
              <option value="faculty">Faculty</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">
              Location
            </label>
            <input
              type="text"
              value={form.location}
              onChange={(e) => setForm({ ...form, location: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
              maxLength={255}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">
              Description
            </label>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-[var(--border-default)] rounded-lg bg-[var(--bg-primary)] text-[var(--text-primary)]"
              rows={2}
            />
          </div>
          <div className="flex gap-2 justify-end pt-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" loading={saving}>
              Create
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}