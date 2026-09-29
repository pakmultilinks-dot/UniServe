"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { getCafeterias, updateCafeteriaStatus, updateCafeteria } from "@/lib/api";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";
import type { Cafeteria } from "@uniserve/shared-types";

export default function CafeteriasPage() {
  const { user } = useAuth();
  const router = useRouter();
  const isManager = user?.role === "cafeteria_manager";
  const isAdmin = user?.role === "university_admin";
  const canManage = isManager || isAdmin;

  useEffect(() => {
    if (!user) return;
  }, [user]);

  const [cafeterias, setCafeterias] = useState<Cafeteria[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ name: "", location: "", description: "" });
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const loadCafeterias = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getCafeterias();
      setCafeterias(data);
    } catch {
      setCafeterias([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadCafeterias(); }, [loadCafeterias]);

  const handleToggleStatus = async (cafeteria: Cafeteria) => {
    const newStatus = cafeteria.operational_status === "open" ? "closed" : "open";
    setActionLoading(cafeteria.id);
    try {
      await updateCafeteriaStatus(cafeteria.id, newStatus);
      await loadCafeterias();
    } catch (err: any) {
      alert(err?.message ?? "Failed");
    } finally {
      setActionLoading(null);
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
    } catch (err: any) {
      alert(err?.message ?? "Failed");
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

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2].map((i) => (
            <div key={i} className="h-48 bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl skeleton" />
          ))}
        </div>
      ) : cafeterias.length === 0 ? (
        <EmptyState
          title="No cafeterias"
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
                    <StatusBadge status={cafeteria.operational_status} />
                  </div>
                  {cafeteria.description && (
                    <p className="text-sm text-[var(--text-secondary)] mb-3">{cafeteria.description}</p>
                  )}
                  <div className="flex items-center gap-2 text-xs text-[var(--text-muted)] mb-3">
                    <span className="px-2 py-0.5 rounded-full bg-[var(--bg-secondary)] capitalize">
                      {cafeteria.type ?? "student"}
                    </span>
                    {cafeteria.operating_hours && (
                      <span>🕐 {cafeteria.operating_hours}</span>
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
                      <Button size="sm" variant="ghost" onClick={() => handleEdit(cafeteria)}>
                        Edit
                      </Button>
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}