"use client";

import React from "react";

interface CardProps {
  children: React.ReactNode;
  className?: string;
  /** Remove default padding */
  noPadding?: boolean;
  /** Add hover effect */
  hoverable?: boolean;
  onClick?: () => void;
}

export function Card({
  children,
  className = "",
  noPadding = false,
  hoverable = false,
  onClick,
}: CardProps) {
  return (
    <div
      className={`bg-[var(--bg-primary)] border border-[var(--border-default)] rounded-xl shadow-card
        ${hoverable ? "hover:shadow-card-hover transition-shadow duration-200 cursor-pointer" : ""}
        ${onClick ? "cursor-pointer" : ""}
        ${noPadding ? "" : "p-5"}
        ${className}`}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex items-center justify-between mb-4 ${className}`}>
      {children}
    </div>
  );
}

export function CardTitle({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <h3 className={`text-base font-semibold text-[var(--text-primary)] ${className}`}>
      {children}
    </h3>
  );
}
