/**
 * UniServe — Mobile Typography
 *
 * Consistent text styles for React Native.
 */

import { TextStyle } from "react-native";
import { colors } from "./colors";

export const typography = {
  // Display
  display: {
    fontSize: 28,
    fontWeight: "700" as TextStyle["fontWeight"],
    lineHeight: 34,
    letterSpacing: -0.5,
  },

  // Heading styles
  title: {
    fontSize: 22,
    fontWeight: "700" as TextStyle["fontWeight"],
    lineHeight: 28,
    letterSpacing: -0.3,
  },
  heading: {
    fontSize: 18,
    fontWeight: "700" as TextStyle["fontWeight"],
    lineHeight: 24,
    letterSpacing: -0.2,
  },
  subheading: {
    fontSize: 16,
    fontWeight: "600" as TextStyle["fontWeight"],
    lineHeight: 22,
  },

  // Body styles
  body: {
    fontSize: 15,
    fontWeight: "400" as TextStyle["fontWeight"],
    lineHeight: 20,
  },
  bodySmall: {
    fontSize: 13,
    fontWeight: "400" as TextStyle["fontWeight"],
    lineHeight: 18,
  },
  caption: {
    fontSize: 12,
    fontWeight: "400" as TextStyle["fontWeight"],
    lineHeight: 16,
  },

  // Price
  price: {
    fontSize: 16,
    fontWeight: "700" as TextStyle["fontWeight"],
    lineHeight: 20,
  },
  priceLarge: {
    fontSize: 20,
    fontWeight: "700" as TextStyle["fontWeight"],
    lineHeight: 24,
  },

  // Label styles
  label: {
    fontSize: 13,
    fontWeight: "600" as TextStyle["fontWeight"],
    lineHeight: 16,
  },
  labelSmall: {
    fontSize: 11,
    fontWeight: "700" as TextStyle["fontWeight"],
    lineHeight: 14,
    letterSpacing: 0.5,
  },
  tabLabel: {
    fontSize: 10,
    fontWeight: "500" as TextStyle["fontWeight"],
    lineHeight: 14,
  },

  // Button styles
  button: {
    fontSize: 15,
    fontWeight: "600" as TextStyle["fontWeight"],
    lineHeight: 20,
  },
  buttonSmall: {
    fontSize: 13,
    fontWeight: "600" as TextStyle["fontWeight"],
    lineHeight: 18,
  },

  // Aliases for backward compat
  h1: { fontSize: 28, fontWeight: "700" as TextStyle["fontWeight"], lineHeight: 34, letterSpacing: -0.5 },
  h2: { fontSize: 22, fontWeight: "700" as TextStyle["fontWeight"], lineHeight: 28, letterSpacing: -0.3 },
  h3: { fontSize: 20, fontWeight: "600" as TextStyle["fontWeight"], lineHeight: 28 },
  h4: { fontSize: 16, fontWeight: "600" as TextStyle["fontWeight"], lineHeight: 24 },
} as const;

/**
 * Get the text color for the current theme.
 */
export function textColor(
  theme: "light" | "dark",
  variant: "primary" | "secondary" | "muted" = "primary",
): string {
  const map = {
    primary: theme === "dark" ? colors.dark.textPrimary : colors.light.textPrimary,
    secondary: theme === "dark" ? colors.dark.textSecondary : colors.light.textSecondary,
    muted: theme === "dark" ? colors.dark.textMuted : colors.light.textMuted,
  };
  return map[variant];
}

/**
 * Get the background color for the current theme.
 */
export function bgColor(
  theme: "light" | "dark",
  variant: "primary" | "secondary" | "tertiary" = "primary",
): string {
  const map = {
    primary: theme === "dark" ? colors.dark.bgPrimary : colors.light.bgPrimary,
    secondary: theme === "dark" ? colors.dark.bgSecondary : colors.light.bgSecondary,
    tertiary: theme === "dark" ? colors.dark.bgTertiary : colors.light.bgTertiary,
  };
  return map[variant];
}

/**
 * Get the border color for the current theme.
 */
export function borderColor(
  theme: "light" | "dark",
  variant: "default" | "subtle" = "default",
): string {
  const map = {
    default: theme === "dark" ? colors.dark.borderDefault : colors.light.borderDefault,
    subtle: theme === "dark" ? colors.dark.borderSubtle : colors.light.borderSubtle,
  };
  return map[variant];
}

/**
 * Get the brand green color for the current theme.
 * Light: #005400, Dark: #22c55e
 */
export function brandGreen(theme: "light" | "dark"): string {
  return theme === "dark" ? colors.brand[500] : colors.brand[700];
}

/**
 * Get a functional color for the current theme.
 */
export function functionalColor(
  theme: "light" | "dark",
  variant: "success" | "warning" | "error" | "info",
): string {
  if (theme === "dark") {
    const darkMap = {
      success: colors.darkSuccess,
      warning: colors.darkWarning,
      error: colors.darkError,
      info: colors.darkInfo,
    };
    return darkMap[variant];
  }
  return colors[variant];
}
