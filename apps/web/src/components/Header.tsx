"use client";

import React from "react";
import { useAuth } from "@/contexts/AuthContext";
import { Avatar } from "@/components/ui/Avatar";
import { ThemeToggle } from "@/components/ThemeToggle";

interface HeaderProps {
  /** Page title or breadcrumb area */
  title?: string;
  /** Right-side actions */
  actions?: React.ReactNode;
  /** Hamburger menu toggle for mobile */
  onMenuToggle?: () => void;
}

export function Header({ title, actions, onMenuToggle }: HeaderProps) {
  const { user } = useAuth();

  return (
    <header className="sticky top-0 z-20 h-16 bg-[var(--bg-primary)]/95 backdrop-blur-sm border-b border-[var(--border-default)]">
      <div className="flex items-center justify-between h-full px-4 sm:px-6">
        {/* Left: Mobile menu + Title */}
        <div className="flex items-center gap-3">
          {/* Mobile hamburger */}
          <button
            onClick={onMenuToggle}
            className="lg:hidden p-2 -ml-2 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-secondary)] transition-colors"
            aria-label="Open navigation menu"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          {/* Page title */}
          {title && (
            <h1 className="text-lg font-semibold text-[var(--text-primary)]">{title}</h1>
          )}
        </div>

        {/* Right: Actions + Theme + User */}
        <div className="flex items-center gap-2">
          {actions}

          {/* Theme toggle */}
          <ThemeToggle />

          {/* Notifications bell (placeholder) */}
          <button
            className="relative p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-secondary)] transition-colors"
            aria-label="Notifications"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
            {/* Notification badge — wired up in future phases */}
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
