"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { getUnreadNotificationCount } from "@/lib/api";
import { Avatar } from "@/components/ui/Avatar";
import { ThemeToggle } from "@/components/ThemeToggle";

interface HeaderProps {
  title?: string;
  actions?: React.ReactNode;
  onMenuToggle?: () => void;
}

export function Header({ title, actions, onMenuToggle }: HeaderProps) {
  const { user } = useAuth();
  const router = useRouter();
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    const fetchCount = async () => {
      try {
        const res = await getUnreadNotificationCount();
        if (!cancelled) setUnreadCount(res.unread_count ?? 0);
      } catch { /* ignore */ }
    };
    fetchCount();
    const interval = setInterval(fetchCount, 5000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [user]);

  return (
    <header className="sticky top-0 z-20 h-16 bg-[var(--bg-primary)]/95 backdrop-blur-sm border-b border-[var(--border-default)]">
      <div className="flex items-center justify-between h-full px-4 sm:px-6">
        <div className="flex items-center gap-3">
          <button
            onClick={onMenuToggle}
            className="lg:hidden p-2 -ml-2 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-secondary)] transition-colors"
            aria-label="Open navigation menu"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          {title && (
            <h1 className="text-lg font-semibold text-[var(--text-primary)]">{title}</h1>
          )}
        </div>

        <div className="flex items-center gap-2">
          {actions}
          <ThemeToggle />

          {/* Notifications bell — wired to unread count */}
          <button
            onClick={() => router.push("/dashboard/notifications")}
            className="relative p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-secondary)] transition-colors"
            aria-label="Notifications"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
            {unreadCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] flex items-center justify-center px-1 text-[10px] font-bold text-white bg-red-500 rounded-full">
                {unreadCount > 99 ? "99+" : unreadCount}
              </span>
            )}
          </button>

          {/* User avatar (visible on mobile where sidebar is hidden) */}
          <div className="lg:hidden">
            <Avatar firstName={user?.first_name} lastName={user?.last_name} size="sm" />
          </div>
        </div>
      </div>
    </header>
  );
}
