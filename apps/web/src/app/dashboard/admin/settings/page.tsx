"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const isAdmin = user?.role === "university_admin";

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Settings"
        description="Application settings and preferences"
      />

      <div className="max-w-2xl space-y-6">
        {/* Appearance */}
        <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-5 shadow-card">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">Appearance</h3>
          <p className="text-xs text-[var(--text-muted)]">
            Theme and display settings are managed through the theme toggle in the header.
            Light and dark mode are supported.
          </p>
        </div>

        {/* Notifications */}
        <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-5 shadow-card">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">Notifications</h3>
          <p className="text-xs text-[var(--text-muted)]">
            Notification preferences are managed in your mobile app profile settings.
            The web console displays notifications received from the backend.
          </p>
          <button
            onClick={() => router.push("/dashboard/notifications")}
            className="mt-3 text-xs text-brand-600 dark:text-brand-400 hover:underline"
          >
            View Notifications →
          </button>
        </div>

        {/* Account */}
        <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-5 shadow-card">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">Account</h3>
          <div className="space-y-3">
            <button
              onClick={() => router.push("/dashboard/profile")}
              className="text-sm text-brand-600 dark:text-brand-400 hover:underline"
            >
              View Profile →
            </button>
            <div className="pt-3 border-t border-[var(--border-default)]">
              <p className="text-xs text-[var(--text-muted)] mb-3">Sign out of the operations console.</p>
              <Button
                size="sm"
                variant="danger"
                onClick={() => { logout(); router.push("/login"); }}
              >
                Sign Out
              </Button>
            </div>
          </div>
        </div>

        {/* Platform info */}
        <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-5 shadow-card">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3">Platform</h3>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <span className="text-[var(--text-muted)]">Version</span>
              <p className="text-[var(--text-primary)] font-medium">1.0.0</p>
            </div>
            <div>
              <span className="text-[var(--text-muted)]">Environment</span>
              <p className="text-[var(--text-primary)] font-medium">Development</p>
            </div>
            <div>
              <span className="text-[var(--text-muted)]">Role</span>
              <p className="text-[var(--text-primary)] font-medium capitalize">{user?.role?.replace(/_/g, " ")}</p>
            </div>
            <div>
              <span className="text-[var(--text-muted)]">API</span>
              <p className="text-[var(--text-primary)] font-medium">localhost:8000</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}