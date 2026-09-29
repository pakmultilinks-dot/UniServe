"use client";

import React from "react";

interface AvatarProps {
  firstName?: string;
  lastName?: string;
  imageUrl?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

const sizeStyles = {
  sm: "h-7 w-7 text-xs",
  md: "h-9 w-9 text-sm",
  lg: "h-12 w-12 text-base",
};

function getInitials(firstName?: string, lastName?: string): string {
  const f = firstName?.[0] || "";
  const l = lastName?.[0] || "";
  return (f + l).toUpperCase() || "?";
}

function hashColor(str: string): string {
  const colors = [
    "bg-brand-700", "bg-brand-600", "bg-warm-600",
    "bg-warm-500", "bg-warm-700", "bg-warm-800",
    "bg-gold-600", "bg-amber-600",
  ];
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

export function Avatar({
  firstName,
  lastName,
  imageUrl,
  size = "md",
  className = "",
}: AvatarProps) {
  const initials = getInitials(firstName, lastName);
  const colorClass = hashColor(initials);

  if (imageUrl) {
    return (
      <img
        src={imageUrl}
        alt={`${firstName || ""} ${lastName || ""}`.trim() || "User"}
        className={`${sizeStyles[size]} rounded-full object-cover ${className}`}
      />
    );
  }

  return (
    <div
      className={`${sizeStyles[size]} ${colorClass} rounded-full flex items-center justify-center font-semibold text-white select-none ${className}`}
      aria-label={`${firstName || ""} ${lastName || ""}`.trim() || "User"}
    >
      {initials}
    </div>
  );
}
