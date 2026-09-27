/**
 * UniServe — Mobile Typography
 *
 * Consistent text styles for React Native.
 */

import { TextStyle } from "react-native";
import { colors } from "./colors";

export const typography = {
  // Heading styles
  h1: {
    fontSize: 28,
    fontWeight: "700" as TextStyle["fontWeight"],
    lineHeight: 36,
    letterSpacing: -0.5,
  },
  h2: {
    fontSize: 24,
    fontWeight: "700" as TextStyle["fontWeight"],
    lineHeight: 32,
    letterSpacing: -0.3,
  },
  h3: {
    fontSize: 20,
    fontWeight: "600" as TextStyle["fontWeight"],
    lineHeight: 28,
  },
  h4: {
    fontSize: 16,
    fontWeight: "600" as TextStyle["fontWeight"],
    lineHeight: 24,
  },

  // Body styles
  body: {
    fontSize: 16,
    fontWeight: "400" as TextStyle["fontWeight"],
    lineHeight: 24,
  },
  bodySmall: {
    fontSize: 14,
    fontWeight: "400" as TextStyle["fontWeight"],
    lineHeight: 20,
  },
  caption: {
    fontSize: 12,
    fontWeight: "400" as TextStyle["fontWeight"],
    lineHeight: 16,
  },

  // Label styles
  label: {
    fontSize: 14,
    fontWeight: "500" as TextStyle["fontWeight"],
    lineHeight: 20,
  },
  labelSmall: {
    fontSize: 12,
    fontWeight: "500" as TextStyle["fontWeight"],
    lineHeight: 16,
  },

  // Button styles
  button: {
    fontSize: 16,
    fontWeight: "600" as TextStyle["fontWeight"],
    lineHeight: 24,
  },
  buttonSmall: {
    fontSize: 14,
    fontWeight: "600" as TextStyle["fontWeight"],
    lineHeight: 20,
  },
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
