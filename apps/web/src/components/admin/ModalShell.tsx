"use client";

import React from "react";

interface ModalShellProps {
  onClose: () => void;
  maxWidth?: string;
  children: React.ReactNode;
}

/**
 * Phase 47 — shared modal backdrop/card used by the admin member-management
 * dialogs. Matches the inline modal pattern already used across the dashboard
 * (fixed backdrop + centered card + click-outside to close).
 */
export function ModalShell({ onClose, maxWidth = "max-w-sm", children }: ModalShellProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className={`bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-xl w-full ${maxWidth} mx-4 p-6 max-h-[90vh] overflow-y-auto`}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}
