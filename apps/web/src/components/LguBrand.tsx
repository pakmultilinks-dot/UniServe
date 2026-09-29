"use client";

import React from "react";

interface LguBrandProps {
  /** Compact mode: logo only, no text */
  compact?: boolean;
  /** Show full university name alongside logo */
  showFullName?: boolean;
  /** Override text color for dark backgrounds */
  light?: boolean;
  /** Size variant */
  size?: "sm" | "md" | "lg";
}

/**
 * LguBrand — Official LGU identity component.
 *
 * Uses the university seal/logo + name.
 * Primary usage: auth screens, sidebar, header, app identity areas.
 */
export function LguBrand({
  compact = false,
  showFullName = true,
  light = false,
  size = "md",
}: LguBrandProps) {
  const sizeConfig = {
    sm: { logo: 28, text: "text-sm", subtext: "text-2xs" },
    md: { logo: 36, text: "text-base", subtext: "text-xs" },
    lg: { logo: 48, text: "text-lg", subtext: "text-sm" },
  };

  const s = sizeConfig[size];
  const textColor = light ? "text-white" : "text-[var(--text-primary)]";
  const subTextColor = light ? "text-white/70" : "text-[var(--text-muted)]";

  return (
    <div className="flex items-center gap-2.5">
      <LguSeal size={s.logo} />
      {showFullName && !compact && (
        <div className="flex flex-col leading-tight">
          <span className={`font-bold tracking-tight ${s.text} ${textColor}`}>
            UniServe
          </span>
          <span className={`font-medium ${s.subtext} ${subTextColor}`}>
            Lahore Garrison University
          </span>
        </div>
      )}
      {compact && (
        <span className={`font-bold tracking-tight text-sm ${textColor}`}>
          UniServe
        </span>
      )}
    </div>
  );
}

/**
 * LguSeal — SVG logo mark representing the LGU institutional identity.
 * Green shield with gold accent, university-appropriate.
 */
export function LguSeal({ size = 36 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="Lahore Garrison University logo"
      role="img"
    >
      {/* Shield body */}
      <path
        d="M32 4L8 14v16c0 14.4 10.24 27.84 24 32 13.76-4.16 24-17.6 24-32V14L32 4z"
        fill="#8c6935"
      />
      {/* Inner shield accent */}
      <path
        d="M32 8.5L12 17v13c0 12.8 9.12 24.8 21.6 28.8C46.08 54.8 55.2 41.8 55.2 30V17L32 8.5z"
        fill="#ae8746"
      />
      {/* Gold accent bar */}
      <rect x="16" y="22" width="32" height="2.5" rx="1.25" fill="#c7a15b" />
      {/* Open book symbol */}
      <path
        d="M24 28h16v12H24z"
        fill="none"
        stroke="#c7a15b"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <line x1="32" y1="28" x2="32" y2="40" stroke="#c7a15b" strokeWidth="1.5" />
      {/* LGU text */}
      <text
        x="32"
        y="50"
        textAnchor="middle"
        fill="white"
        fontSize="8"
        fontWeight="700"
        fontFamily="Inter, system-ui, sans-serif"
        letterSpacing="1"
      >
        LGU
      </text>
    </svg>
  );
}
