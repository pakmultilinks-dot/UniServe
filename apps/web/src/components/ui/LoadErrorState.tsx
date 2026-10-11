"use client";

import React from "react";
import { Button } from "./Button";
import type { ApiErrorInfo } from "@/lib/api";

interface LoadErrorStateProps {
  /** Structured error produced by getApiErrorInfo(err) in lib/api. */
  error: ApiErrorInfo;
  /** What failed to load, e.g. "cafeterias", "recent orders". */
  subject: string;
  /** Re-runs the exact request that failed. */
  onRetry?: () => void;
  /** Dense variant for inline sections (selectors, side panels, banners). */
  compact?: boolean;
  className?: string;
}

/**
 * Phase 46 — explicit request-failure state.
 *
 * Rendered INSTEAD of an empty-state whenever an API request failed, so a
 * broken backend/network is never presented as a legitimately empty dataset.
 * Uses the same visual language as EmptyState (centered card, muted text)
 * with an error accent and — when the failure is retryable — a "Try again"
 * button that re-runs the exact request that failed.
 *
 * Authentication failures (401) never show retry: the AuthContext /
 * RoleGuard flow handles redirecting to login.
 */
export function LoadErrorState({
  error,
  subject,
  onRetry,
  compact = false,
  className = "",
}: LoadErrorStateProps) {
  const canRetry = Boolean(onRetry) && error.retryable && error.kind !== "auth";
  return (
    <div
      className={`flex flex-col items-center justify-center text-center ${
        compact ? "py-4 px-4" : "py-12 px-6"
      } ${className}`}
    >
      <div className={`${compact ? "mb-2" : "mb-4"} text-red-400 opacity-70`}>
        <svg
          className={compact ? "w-6 h-6" : "w-8 h-8"}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v3.75m0 3.75h.008v.008H12v-.008zM21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      </div>
      <h3 className="text-base font-semibold text-[var(--text-primary)] mb-1.5">
        {`Unable to load ${subject}.`}
      </h3>
      <p
        className={`text-[var(--text-muted)] max-w-sm ${
          compact ? "text-xs mb-2" : "text-sm mb-5"
        }`}
      >
        {error.message}
      </p>
      {canRetry && (
        <Button size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
