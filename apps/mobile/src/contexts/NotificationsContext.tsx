/**
 * UniServe — Notifications Context (Phase 53)
 *
 * Shared unread-notification count for the mobile tab badge, mirroring the
 * CartContext pattern already used by the Home-tab cart badge.
 *
 * The count is always fetched from the server (GET /notifications/unread-count)
 * — never derived locally — so the badge cannot drift from authoritative
 * backend state. Refreshes run on demand (tab focus, after successful
 * mark-read actions) and only while authenticated: a logged-out session must
 * not fire API calls (401 would trip the auth-failure logout hook).
 *
 * The badge is a passive indicator. Fetch failures are swallowed here on
 * purpose — the inbox screen owns error UX (ErrorState + retry).
 */
import React, { createContext, useCallback, useContext, useEffect, useState } from "react";

import { useAuth } from "./AuthContext";
import { getUnreadNotificationCount } from "../services/data";

interface NotificationsContextValue {
  /** Authoritative unread count from the server (0 when logged out). */
  unreadCount: number;
  /** Re-fetch the unread count from GET /notifications/unread-count. */
  refreshUnreadCount: () => Promise<void>;
  /**
   * Adopt a count already fetched by a surface that read the list endpoint
   * (GET /notifications returns `unread_count` alongside the items). Lets the
   * inbox and the badge share one value without a second request, keeping both
   * surfaces in lock-step. Still derived from server truth — never a local tally.
   */
  setUnreadCount: React.Dispatch<React.SetStateAction<number>>;
}

const NotificationsContext = createContext<NotificationsContextValue | undefined>(undefined);

export function useNotifications(): NotificationsContextValue {
  const ctx = useContext(NotificationsContext);
  if (!ctx) {
    throw new Error("useNotifications must be used within NotificationsProvider");
  }
  return ctx;
}

export function NotificationsProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  const [unreadCount, setUnreadCount] = useState(0);

  const refreshUnreadCount = useCallback(async () => {
    try {
      setUnreadCount(await getUnreadNotificationCount());
    } catch {
      // Passive badge — the inbox screen surfaces real error/retry UX.
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      refreshUnreadCount();
    } else {
      setUnreadCount(0);
    }
  }, [isAuthenticated, refreshUnreadCount]);

  return (
    <NotificationsContext.Provider
      value={{ unreadCount, refreshUnreadCount, setUnreadCount }}
    >
      {children}
    </NotificationsContext.Provider>
  );
}
