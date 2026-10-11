"use client";

import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/components/ui/Toast";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { updateProfile } from "@/lib/api";

export default function ProfilePage() {
  const { user, refreshUser } = useAuth();
  const { toast } = useToast();
  const [editing, setEditing] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [saving, setSaving] = useState(false);

  if (!user) return null;

  const roleLabel = user.role.replace(/_/g, " ");

  const startEditing = () => {
    setFirstName(user.first_name ?? "");
    setLastName(user.last_name ?? "");
    setEditing(true);
  };

  const cancelEditing = () => {
    setEditing(false);
    setFirstName("");
    setLastName("");
  };

  const saveProfile = async () => {
    if (!firstName.trim() || !lastName.trim()) {
      toast("First and last name are required", "error");
      return;
    }
    setSaving(true);
    try {
      // Phase 55 — PATCH /auth/me (self-scoped profile update).
      await updateProfile({
        first_name: firstName.trim(),
        last_name: lastName.trim(),
      });
      await refreshUser();
      toast("Profile updated successfully", "success");
      setEditing(false);
    } catch (err: any) {
      toast(err?.message ?? "Failed to update profile", "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="My Profile"
        description="View and manage your account"
        actions={
          <Button size="sm" variant="ghost" onClick={editing ? cancelEditing : startEditing}>
            {editing ? "Cancel" : "Edit Profile"}
          </Button>
        }
      />

      <div className="max-w-2xl">
        <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-6 shadow-card">
          {/* Avatar + basic info */}
          <div className="flex items-center gap-4 mb-6 pb-6 border-b border-[var(--border-default)]">
            <div className="w-16 h-16 rounded-full bg-brand-100 dark:bg-brand-900/30 flex items-center justify-center text-brand-600 dark:text-brand-400 text-xl font-bold">
              {(user.first_name?.[0] ?? "U").toUpperCase()}{(user.last_name?.[0] ?? "").toUpperCase()}
            </div>
            <div>
              <h2 className="text-lg font-semibold text-[var(--text-primary)]">
                {user.first_name} {user.last_name}
              </h2>
              <p className="text-sm text-[var(--text-muted)]">{user.university_email}</p>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-xs px-2 py-0.5 rounded-full bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-300 capitalize">
                  {roleLabel}
                </span>
                <StatusBadge status={user.status ?? "active"} />
              </div>
            </div>
          </div>

          {editing ? (
            /* Edit form */
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="input-label">First Name</label>
                  <input
                    type="text"
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    className="input-field"
                  />
                </div>
                <div>
                  <label className="input-label">Last Name</label>
                  <input
                    type="text"
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    className="input-field"
                  />
                </div>
              </div>
              <div>
                <label className="input-label">Email</label>
                <p className="text-sm text-[var(--text-muted)]">{user.university_email} (cannot be changed)</p>
              </div>
              <div>
                <label className="input-label">University ID</label>
                <p className="text-sm text-[var(--text-muted)] font-mono">{user.university_id} (cannot be changed)</p>
              </div>
              <div className="flex gap-2 pt-2">
                <Button size="sm" variant="primary" loading={saving} onClick={saveProfile}>
                  Save Changes
                </Button>
                <Button size="sm" variant="ghost" onClick={cancelEditing}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            /* Read-only profile fields */
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)] uppercase">First Name</label>
                <p className="text-sm text-[var(--text-primary)] mt-1">{user.first_name || "—"}</p>
              </div>
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)] uppercase">Last Name</label>
                <p className="text-sm text-[var(--text-primary)] mt-1">{user.last_name || "—"}</p>
              </div>
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)] uppercase">Email</label>
                <p className="text-sm text-[var(--text-primary)] mt-1">{user.university_email}</p>
              </div>
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)] uppercase">University ID</label>
                <p className="text-sm text-[var(--text-primary)] mt-1 font-mono">{user.university_id || "—"}</p>
              </div>
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)] uppercase">Category</label>
                <p className="text-sm text-[var(--text-primary)] mt-1 capitalize">{user.category || "—"}</p>
              </div>
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)] uppercase">Role</label>
                <p className="text-sm text-[var(--text-primary)] mt-1 capitalize">{roleLabel}</p>
              </div>
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)] uppercase">Email Verified</label>
                <p className="text-sm text-[var(--text-primary)] mt-1 flex items-center gap-1.5">
                  {user.email_verified ? (
                    <>
                      <svg className="w-4 h-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      Yes
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 9.75l4.5 4.5m0-4.5l-4.5 4.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      No
                    </>
                  )}
                </p>
              </div>
              <div>
                <label className="text-xs font-medium text-[var(--text-muted)] uppercase">Member Since</label>
                <p className="text-sm text-[var(--text-primary)] mt-1">
                  {new Date(user.created_at).toLocaleDateString("en-US", { month: "long", year: "numeric" })}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}