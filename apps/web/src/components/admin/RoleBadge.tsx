"use client";

import React from "react";
import type { UserRole } from "@uniserve/shared-types";

const ROLE_BADGES: Record<UserRole, { label: string; className: string }> = {
  student: {
    label: "Student",
    className: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  },
  faculty: {
    label: "Faculty",
    className: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400",
  },
  cafeteria_staff: {
    label: "Staff",
    className: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400",
  },
  cafeteria_manager: {
    label: "Manager",
    className: "bg-teal-100 text-teal-800 dark:bg-teal-900/30 dark:text-teal-400",
  },
  university_admin: {
    label: "Admin",
    className: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
  },
};

/**
 * Phase 47 — colored role badge for the Admin Console.
 * Colors distinguish roles visually only; they do NOT imply permission
 * levels (backend RBAC remains authoritative).
 */
export function RoleBadge({ role }: { role: UserRole | string }) {
  const badge = ROLE_BADGES[role as UserRole] ?? {
    label: role.replace(/_/g, " "),
    className: "bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400",
  };
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${badge.className}`}
    >
      {badge.label}
    </span>
  );
}

export function roleLabel(role: UserRole | string): string {
  return ROLE_BADGES[role as UserRole]?.label ?? role.replace(/_/g, " ");
}
