"use client";

import React from "react";

interface EmptyStateProps {
  /** SVG icon or element */
  icon?: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className = "",
}: EmptyStateProps) {
  return (
    <div className={`flex w-full min-w-0 max-w-full flex-col items-center justify-center py-12 px-6 text-center ${className}`}>
      {icon && (
        <div className="mb-4 text-[var(--text-muted)] opacity-50">
          {icon}
        </div>
      )}
      <h3 className="text-base font-semibold text-[var(--text-primary)] mb-1.5">
        {title}
      </h3>
      <p className="text-sm text-[var(--text-muted)] w-full max-w-sm break-words mb-5">
        {description}
      </p>
      {action}
    </div>
  );
}
