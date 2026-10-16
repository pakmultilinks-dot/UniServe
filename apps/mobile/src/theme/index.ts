export { colors } from "./colors";
export { typography, textColor, bgColor, borderColor, brandGreen, brandText, functionalColor } from "./typography";

/**
 * Spacing scale (4/8/12/16/20/24/32/40)
 * Use these consistently. Do not invent in-between values.
 */
export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  base: 16,
  lg: 20,
  xl: 24,
  xxl: 32,
  xxxl: 40,
} as const;

/**
 * Corner radius hierarchy.
 * Buttons/inputs: 10, Surfaces: 12-16, Hero images: 16-20,
 * Bottom sheet top: 20-24. Pills only for status chips / filters.
 */
export const radii = {
  sm: 8,
  md: 10,
  lg: 12,
  xl: 16,
  xxl: 20,
  pill: 999,
} as const;

/**
 * Icon sizing tokens. Use thin/medium stroke Ionicons.
 */
export const iconSize = {
  xs: 16,
  sm: 20,
  md: 24,
  lg: 28,
} as const;
