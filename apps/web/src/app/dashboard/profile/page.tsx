"use client";

import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { StatusBadge } from "@/components/ui/StatusBadge";

export default function ProfilePage() {
  const { user } = useAuth();
  const [editing, setEditing] = useState(false);

  if (!user) return null;

  const roleLabel = user.role.replace(/_/g, " ");

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="My Profile"
        description="View and manage your account"
        actions={
          <Button size="sm" variant="ghost" onClick={() => setEditing(!editing)}>
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

          {/* Profile fields */}
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
              <p className="text-sm text-[var(--text-primary)] mt-1">{user.email_verified ? "✅ Yes" : "❌ No"}</p>
            </div>
            <div>
              <label className="text-xs font-medium text-[var(--text-muted)] uppercase">Member Since</label>
              <p className="text-sm text-[var(--text-primary)] mt-1">
                {new Date(user.created_at).toLocaleDateString("en-US", { month: "long", year: "numeric" })}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}