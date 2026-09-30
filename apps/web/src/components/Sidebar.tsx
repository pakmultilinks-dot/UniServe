"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { LguBrand, LguSeal } from "@/components/LguBrand";
import { Avatar } from "@/components/ui/Avatar";
import type { UserRole } from "@uniserve/shared-types";

/* ─── Navigation structure by role ─── */

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
  roles?: UserRole[];
}

const navItems: NavItem[] = [
  {
    label: "Home",
    href: "/dashboard",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1" />
      </svg>
    ),
  },
  {
    label: "Cafeterias",
    href: "/dashboard/cafeterias",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
      </svg>
    ),
  },
  {
    label: "Orders",
    href: "/dashboard/orders",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
      </svg>
    ),
    roles: ["cafeteria_staff", "cafeteria_manager", "university_admin"],
  },
  {
    label: "Favorites",
    href: "/dashboard/favorites",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
      </svg>
    ),
    roles: ["student", "faculty"],
  },
  {
    label: "Notifications",
    href: "/dashboard/notifications",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
      </svg>
    ),
  },
  {
    label: "Profile",
    href: "/dashboard/profile",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
      </svg>
    ),
  },
];

/* Manager/Staff extra nav */
const managerNavItems: NavItem[] = [
  {
    label: "Menu",
    href: "/dashboard/menu",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
      </svg>
    ),
    roles: ["cafeteria_manager", "cafeteria_staff"],
  },
  {
    label: "Inventory",
    href: "/dashboard/inventory",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
      </svg>
    ),
    roles: ["cafeteria_manager", "cafeteria_staff"],
  },
  {
    label: "Staff",
    href: "/dashboard/staff",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
    roles: ["cafeteria_manager"],
  },
];

/* Admin extra nav */
const adminNavItems: NavItem[] = [
  {
    label: "Overview",
    href: "/dashboard/admin/overview",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
    roles: ["university_admin"],
  },
  {
    label: "Users",
    href: "/dashboard/admin/users",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
      </svg>
    ),
    roles: ["university_admin"],
  },
  {
    label: "Reports",
    href: "/dashboard/admin/reports",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
    roles: ["university_admin"],
  },
  {
    label: "Refunds",
    href: "/dashboard/admin/refunds",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
      </svg>
    ),
    roles: ["university_admin"],
  },
  {
    label: "Settings",
    href: "/dashboard/admin/settings",
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
    roles: ["university_admin"],
  },
];

function getNavForRole(role: UserRole | undefined): NavItem[] {
  if (!role) return navItems.filter((n) => !n.roles);

  let items = navItems.filter((n) => !n.roles || n.roles.includes(role));

  if (role === "cafeteria_manager" || role === "cafeteria_staff") {
    items = [...items, ...managerNavItems.filter((n) => n.roles?.includes(role))];
  }

  if (role === "university_admin") {
    items = [...items, ...adminNavItems];
  }

  return items;
}

/* ─── Sidebar Component ─── */

interface SidebarProps {
  collapsed?: boolean;
  onToggle?: () => void;
}

export function Sidebar({ collapsed = false, onToggle }: SidebarProps) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [loggingOut, setLoggingOut] = useState(false);
  const navItemsForRole = getNavForRole(user?.role);

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await logout();
    } finally {
      setLoggingOut(false);
    }
  };

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className={`hidden lg:flex flex-col fixed inset-y-0 left-0 z-30
          bg-[var(--bg-primary)] border-r border-[var(--border-default)] shadow-sidebar
          transition-all duration-300 ${collapsed ? "w-[68px]" : "w-64"}`}
      >
        {/* Brand */}
        <div className={`flex items-center h-16 px-4 border-b border-[var(--border-default)] ${collapsed ? "justify-center" : ""}`}>
          <LguBrand compact={collapsed} showFullName={!collapsed} size="sm" />
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
          {navItemsForRole.map((item) => {
            const isActive =
              item.href === "/dashboard"
                ? pathname === "/dashboard"
                : pathname.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-lg transition-colors duration-150
                  ${isActive
                    ? "bg-brand-700/10 text-brand-700 dark:text-brand-400 font-semibold"
                    : "text-[var(--text-secondary)] hover:bg-brand-700/5 hover:text-[var(--text-primary)]"
                  }
                  ${collapsed ? "justify-center px-2" : ""}`}
                title={collapsed ? item.label : undefined}
                aria-current={isActive ? "page" : undefined}
              >
                <span className="flex-shrink-0">{item.icon}</span>
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* User section */}
        <div className={`border-t border-[var(--border-default)] p-3 ${collapsed ? "flex justify-center" : ""}`}>
          {collapsed ? (
            <button
              onClick={handleLogout}
              disabled={loggingOut}
              className="p-2 rounded-lg text-[var(--text-muted)] hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
              title="Sign out"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
            </button>
          ) : (
            <div className="flex items-center gap-3">
              <Avatar firstName={user?.first_name} lastName={user?.last_name} size="sm" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-[var(--text-primary)] truncate">
                  {user?.first_name} {user?.last_name}
                </p>
                <p className="text-2xs text-[var(--text-muted)] capitalize">{user?.role?.replace(/_/g, " ")}</p>
              </div>
              <button
                onClick={handleLogout}
                disabled={loggingOut}
                className="p-1.5 rounded-md text-[var(--text-muted)] hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                title="Sign out"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Mobile sidebar overlay — rendered in parent */}
    </>
  );
}

/* ─── Mobile Sidebar ─── */

interface MobileSidebarProps {
  open: boolean;
  onClose: () => void;
}

export function MobileSidebar({ open, onClose }: MobileSidebarProps) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [loggingOut, setLoggingOut] = useState(false);
  const navItemsForRole = getNavForRole(user?.role);

  if (!open) return null;

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await logout();
      onClose();
    } finally {
      setLoggingOut(false);
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/40 lg:hidden animate-fade-in"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Sidebar panel */}
      <aside className="fixed inset-y-0 left-0 z-50 w-64 bg-[var(--bg-primary)] border-r border-[var(--border-default)] lg:hidden animate-slide-in flex flex-col">
        {/* Brand */}
        <div className="flex items-center justify-between h-16 px-4 border-b border-[var(--border-default)]">
          <LguBrand size="sm" />
          <button
            onClick={onClose}
            className="p-1.5 rounded-md text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-secondary)] transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
          {navItemsForRole.map((item) => {
            const isActive =
              item.href === "/dashboard"
                ? pathname === "/dashboard"
                : pathname.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onClose}
                className={`flex items-center gap-3 px-3 py-2.5 text-sm font-medium rounded-lg transition-colors
                  ${isActive
                    ? "bg-brand-700/10 text-brand-700 dark:text-brand-400 font-semibold"
                    : "text-[var(--text-secondary)] hover:bg-brand-700/5 hover:text-[var(--text-primary)]"
                  }`}
                aria-current={isActive ? "page" : undefined}
              >
                <span className="flex-shrink-0">{item.icon}</span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* User + Logout */}
        <div className="border-t border-[var(--border-default)] p-3">
          <div className="flex items-center gap-3 mb-3">
            <Avatar firstName={user?.first_name} lastName={user?.last_name} size="sm" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-[var(--text-primary)] truncate">
                {user?.first_name} {user?.last_name}
              </p>
              <p className="text-2xs text-[var(--text-muted)] capitalize">{user?.role?.replace(/_/g, " ")}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            disabled={loggingOut}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            {loggingOut ? "Signing out..." : "Sign out"}
          </button>
        </div>
      </aside>
    </>
  );
}

export { getNavForRole };
