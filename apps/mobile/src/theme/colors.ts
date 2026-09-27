/**
 * UniServe — Mobile Color Theme
 *
 * LGU brand colors translated to React Native compatible format.
 * Mirrors the web CSS custom properties in globals.css.
 */

export const colors = {
  // LGU Brand Green
  brand: {
    50: "#f0fdf4",
    100: "#dcfce7",
    200: "#bbf7d0",
    300: "#86efac",
    400: "#4ade80",
    500: "#22c55e",
    600: "#16a34a",
    700: "#005400",
    800: "#004400",
    900: "#003300",
    950: "#001a00",
  },

  // LGU Gold Accent
  gold: {
    50: "#fffdf0",
    100: "#fff9d4",
    200: "#fff0a3",
    300: "#ffe466",
    400: "#ffd633",
    500: "#ffc000",
    600: "#e5a800",
    700: "#b38300",
    800: "#805f00",
    900: "#4d3900",
  },

  // Neutrals
  neutral: {
    0: "#ffffff",
    50: "#f9fafb",
    100: "#f3f4f6",
    200: "#e5e7eb",
    300: "#d1d5db",
    400: "#9ca3af",
    500: "#6b7280",
    600: "#4a4e57",
    700: "#374151",
    800: "#1f2937",
    900: "#111827",
    950: "#030712",
  },

  // Semantic Colors (Light Mode)
  light: {
    bgPrimary: "#ffffff",
    bgSecondary: "#f2f3f5",
    bgTertiary: "#e5e7eb",
    textPrimary: "#111827",
    textSecondary: "#4a4e57",
    textMuted: "#6b7280",
    borderDefault: "#e5e7eb",
    borderSubtle: "#f3f4f6",
  },

  // Semantic Colors (Dark Mode)
  dark: {
    bgPrimary: "#0f1218",
    bgSecondary: "#1a1f2e",
    bgTertiary: "#252b3b",
    textPrimary: "#f0f1f4",
    textSecondary: "#b0b5be",
    textMuted: "#6b7280",
    borderDefault: "#2a3042",
    borderSubtle: "#1e2433",
  },

  // Functional
  success: "#22c55e",
  warning: "#ffc000",
  error: "#ef4444",
  info: "#3b82f6",
} as const;

export type ColorToken = keyof typeof colors;
