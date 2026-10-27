"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadErrorState } from "@/components/ui/LoadErrorState";
import { ModalShell } from "@/components/admin/ModalShell";
import { useToast } from "@/components/ui/Toast";
import {
  getSessions,
  logoutAll,
  changePassword,
  getApiErrorInfo,
} from "@/lib/api";
import type { ApiErrorInfo } from "@/lib/api";
import type { Session } from "@uniserve/shared-types";


function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString();
}

function PasswordStrength({ password }: { password: string }) {
  if (!password) return null;
  let score = 0;
  if (password.length >= 8) score++;
  if (password.length >= 12) score++;
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score++;
  if (/\d/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;

  const levels = ["Very weak", "Weak", "Fair", "Good", "Strong", "Excellent"];
  const colors = [
    "text-red-600 dark:text-red-400",
    "text-red-600 dark:text-red-400",
    "text-amber-600 dark:text-amber-400",
    "text-amber-600 dark:text-amber-400",
    "text-green-600 dark:text-green-400",
    "text-green-600 dark:text-green-400",
  ];

  return (
    <div className="flex items-center gap-2 mt-1">
      <div className="flex gap-1">
        {[0, 1, 2, 3, 4].map((i) => (
          <span
            key={i}
            className={`h-1 w-5 rounded ${
              i < score
                ? score <= 2
                  ? "bg-red-500"
                  : score <= 3
                    ? "bg-amber-500"
                    : "bg-green-500"
                : "bg-[var(--border-default)]"
            }`}
          />
        ))}
      </div>
      <span className={`text-xs ${colors[score]}`}>{levels[score]}</span>
    </div>
  );
}

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const { toast } = useToast();
  const isAdmin = user?.role === "university_admin";

  // ── Sessions ──
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionsError, setSessionsError] = useState<ApiErrorInfo | null>(null);
  const [showLogoutAllConfirm, setShowLogoutAllConfirm] = useState(false);
  const [loggingOutAll, setLoggingOutAll] = useState(false);

  // ── Change password ──
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);
  const [changingPassword, setChangingPassword] = useState(false);

  const loadSessions = useCallback(async () => {
    setSessionsLoading(true);
    setSessionsError(null);
    try {
      const data = await getSessions();
      setSessions(data.sessions ?? []);
    } catch (err) {
      setSessionsError(getApiErrorInfo(err));
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user && !isAdmin) {
      router.push("/dashboard");
    }
  }, [user, isAdmin, router]);

  useEffect(() => {
    if (user && isAdmin) {
      loadSessions();
    }
  }, [user, isAdmin, loadSessions]);

  if (!user || !isAdmin) return null;

  const handleLogoutAll = async () => {
    setLoggingOutAll(true);
    try {
      const result = await logoutAll();
      toast(result?.message || "All sessions have been signed out.", "success");
      // The current session is also revoked — force a clean sign-out.
      logout();
      router.push("/login");
    } catch (err) {
      toast(
        err instanceof Error ? err.message : "Failed to sign out all sessions",
        "error",
      );
      setLoggingOutAll(false);
      setShowLogoutAllConfirm(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError(null);
    setPasswordSuccess(null);

    if (!currentPassword || !newPassword) {
      setPasswordError("Both current and new password are required.");
      return;
    }
    if (newPassword.length < 8) {
      setPasswordError("New password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("New password and confirmation do not match.");
      return;
    }
    if (newPassword === currentPassword) {
      setPasswordError("New password must differ from the current password.");
      return;
    }

    setChangingPassword(true);
    try {
      await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setPasswordSuccess(
        "Password changed successfully. Use the new password next time you sign in.",
      );
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setPasswordError(
        err instanceof Error ? err.message : "Failed to change password",
      );
    } finally {
      setChangingPassword(false);
    }
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Settings"
        description="Application settings, account security, and platform information"
      />

      <div className="max-w-2xl space-y-6">
        {/* ── Active sessions (Phase 55) ── */}
        <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-5 shadow-card">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                Active Sessions
              </h3>
              <p className="text-xs text-[var(--text-muted)] mt-1">
                Devices currently signed in to your account. Signing out all
                sessions ends every session, including this one.
              </p>
            </div>
            <Button
              size="sm"
              variant="danger"
              onClick={() => setShowLogoutAllConfirm(true)}
              disabled={sessions.length === 0 || loggingOutAll}
            >
              Logout All Sessions
            </Button>
          </div>

          {sessionsLoading ? (
            <p className="text-xs text-[var(--text-muted)] py-4">
              Loading sessions…
            </p>
          ) : sessionsError ? (
            <LoadErrorState
              error={sessionsError}
              subject="sessions"
              onRetry={loadSessions}
              compact
            />
          ) : sessions.length === 0 ? (
            <EmptyState
              title="No active sessions"
              description="No other devices are signed in to this account."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-[var(--text-muted)] border-b border-[var(--border-default)]">
                    <th className="py-2 pr-3 font-medium">Device</th>
                    <th className="py-2 pr-3 font-medium">IP Address</th>
                    <th className="py-2 pr-3 font-medium">Signed In</th>
                    <th className="py-2 pr-3 font-medium">Last Activity</th>
                    <th className="py-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((s) => (
                    <tr
                      key={s.id}
                      className="border-b border-[var(--border-default)] last:border-0"
                    >
                      <td className="py-2 pr-3 text-[var(--text-primary)]">
                        {s.device_info || "Unknown device"}
                      </td>
                      <td className="py-2 pr-3 text-[var(--text-primary)] font-mono">
                        {s.ip_address || "—"}
                      </td>
                      <td className="py-2 pr-3 text-[var(--text-muted)]">
                        {formatTimestamp(s.created_at)}
                      </td>
                      <td className="py-2 pr-3 text-[var(--text-muted)]">
                        {formatTimestamp(s.last_activity_at)}
                      </td>
                      <td className="py-2">
                        {s.is_current ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300">
                            Current
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[var(--bg-secondary)] text-[var(--text-muted)]">
                            Other
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* ── Change password (Phase 55) ── */}
        <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl p-5 shadow-card">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-1">
            Change Password
          </h3>
          <p className="text-xs text-[var(--text-muted)] mb-4">
            Your new password must be at least 8 characters and different from
            your current password.
          </p>

          <form onSubmit={handleChangePassword} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">
                Current Password
              </label>
              <input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                autoComplete="current-password"
                className="w-full px-3 py-2 text-sm rounded-lg border border-[var(--border-default)] bg-[var(--bg-secondary)] text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">
                New Password
              </label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                autoComplete="new-password"
                className="w-full px-3 py-2 text-sm rounded-lg border border-[var(--border-default)] bg-[var(--bg-secondary)] text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <PasswordStrength password={newPassword} />
            </div>
            <div>
              <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">
                Confirm New Password
              </label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
                className="w-full px-3 py-2 text-sm rounded-lg border border-[var(--border-default)] bg-[var(--bg-secondary)] text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>

            {passwordError && (
              <p
                role="alert"
                className="text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg px-3 py-2"
              >
                {passwordError}
              </p>
            )}
            {passwordSuccess && (
              <p
                role="status"
                className="text-xs text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg px-3 py-2"
              >
                {passwordSuccess}
              </p>
            )}

            <Button
              type="submit"
              variant="primary"
              size="sm"
              loading={changingPassword}
              disabled={changingPassword}
            >
              Change Password
            </Button>
          </form>
        </div>

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
            Your notifications are available in the notification center.
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
              <span className="text-[var(--text-muted)]">Role</span>
              <p className="text-[var(--text-primary)] font-medium capitalize">{user?.role?.replace(/_/g, " ")}</p>
            </div>
            <div>
              <span className="text-[var(--text-muted)]">Signed in as</span>
              <p className="text-[var(--text-primary)] font-medium">{user?.university_email}</p>
            </div>
            <div>
              <span className="text-[var(--text-muted)]">University ID</span>
              <p className="text-[var(--text-primary)] font-medium">{user?.university_id}</p>
            </div>
          </div>
        </div>
      </div>

      {/* ── Logout-all confirmation modal (Phase 55) ── */}
      {showLogoutAllConfirm && (
        <ModalShell onClose={() => !loggingOutAll && setShowLogoutAllConfirm(false)}>
          <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-2">
            Sign out of all sessions?
          </h3>
          <p className="text-xs text-[var(--text-muted)] mb-4">
            This immediately ends every session for your account on all devices,
            including the one you are using now. You will need to sign in again
            on this device.
          </p>
          <div className="flex justify-end gap-2">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setShowLogoutAllConfirm(false)}
              disabled={loggingOutAll}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              variant="danger"
              onClick={handleLogoutAll}
              loading={loggingOutAll}
              disabled={loggingOutAll}
            >
              Logout All Sessions
            </Button>
          </div>
        </ModalShell>
      )}
    </div>
  );
}
