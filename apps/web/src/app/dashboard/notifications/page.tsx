"use client";

import { useState, useEffect, useCallback } from "react";
import { getNotifications, markNotificationRead, markAllNotificationsRead } from "@/lib/api";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";
import type { Notification } from "@uniserve/shared-types";

const TYPE_ICONS: Record<string, string> = {
  order_created: "📋",
  order_confirmed: "✅",
  order_rejected: "❌",
  preparation_started: "👨‍🍳",
  order_ready: "🔔",
  order_cancelled: "🚫",
  order_delayed: "⏰",
  payment_confirmed: "💳",
  refund_requested: "💸",
  refund_processed: "💰",
};

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showUnreadOnly, setShowUnreadOnly] = useState(false);

  const loadNotifications = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getNotifications({ is_read: showUnreadOnly ? false : undefined, limit: 50 });
      setNotifications(data.items ?? []);
      setUnreadCount(data.unread_count ?? 0);
    } catch {
      setNotifications([]);
    } finally {
      setLoading(false);
    }
  }, [showUnreadOnly]);

  useEffect(() => { loadNotifications(); }, [loadNotifications]);

  const handleMarkRead = async (id: string) => {
    try {
      await markNotificationRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch {}
  };

  const handleMarkAllRead = async () => {
    try {
      await markAllNotificationsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch {}
  };

  const formatDate = (iso: string) => {
    try {
      const d = new Date(iso);
      const now = new Date();
      const diff = now.getTime() - d.getTime();
      if (diff < 60000) return "Just now";
      if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
      if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
      return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    } catch { return iso; }
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Notifications"
        description={`${unreadCount} unread notification${unreadCount !== 1 ? "s" : ""}`}
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowUnreadOnly(!showUnreadOnly)}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                showUnreadOnly
                  ? "bg-brand-600 text-white"
                  : "bg-[var(--bg-secondary)] text-[var(--text-secondary)]"
              }`}
            >
              {showUnreadOnly ? "Showing Unread" : "Show Unread Only"}
            </button>
            {unreadCount > 0 && (
              <Button size="sm" variant="ghost" onClick={handleMarkAllRead}>
                Mark All Read
              </Button>
            )}
          </div>
        }
      />

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-20 bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl skeleton" />
          ))}
        </div>
      ) : notifications.length === 0 ? (
        <EmptyState
          title="No notifications"
          description="You're all caught up!"
          icon={
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
            </svg>
          }
        />
      ) : (
        <div className="bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl overflow-hidden shadow-card divide-y divide-[var(--border-default)]">
          {notifications.map((n) => (
            <div
              key={n.id}
              onClick={() => !n.is_read && handleMarkRead(n.id)}
              className={`flex items-start gap-3 px-5 py-4 transition-colors ${
                !n.is_read
                  ? "bg-brand-50/30 dark:bg-brand-900/10 cursor-pointer"
                  : "hover:bg-[var(--bg-secondary)]/50"
              }`}
            >
              {!n.is_read && (
                <div className="mt-2 flex-shrink-0 w-2 h-2 rounded-full bg-brand-600" />
              )}
              <div className="flex-shrink-0 text-lg">
                {TYPE_ICONS[n.notification_type] ?? "📌"}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-[var(--text-primary)]">{n.title}</p>
                <p className="text-xs text-[var(--text-muted)] mt-0.5 line-clamp-2">{n.body}</p>
              </div>
              <span className="text-xs text-[var(--text-muted)] flex-shrink-0 whitespace-nowrap">
                {formatDate(n.created_at)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
