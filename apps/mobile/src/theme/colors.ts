/**
 * UniServe — Mobile Color Theme
 *
 * Uni Cafe palette based on the supplied mobile design references.
 * Cream surfaces, espresso text, and caramel-gold actions.
 */

export const colors = {
  // LGU Brand Green (primary CTA)
  brand: {
    50: "#fbf4e4",
    100: "#f3e4bf",
    200: "#e8d19b",
    300: "#ddbd7b",
    400: "#d2ad69",
    500: "#c7a15b",
    600: "#ae8746",
    700: "#8c6935",
    800: "#6d4f2b",
    900: "#4b3421",
    950: "#302015",
  },

  // LGU Gold Accent
  gold: {
    50: "#fbf4e4",
    100: "#f3e4bf",
    200: "#e8d19b",
    300: "#ddbd7b",
    400: "#d2ad69",
    500: "#c7a15b",
    600: "#ae8746",
    700: "#8c6935",
    800: "#6d4f2b",
    900: "#4b3421",
  },

  // Neutral System (warm café neutrals)
  neutral: {
    0: "#fffdf8",
    50: "#fbf6ec",
    100: "#f3ead8",
    200: "#e6d8bf",
    300: "#d2bea0",
    400: "#b8a388",
    500: "#95816b",
    600: "#74604d",
    700: "#574433",
    800: "#3e2d20",
    900: "#2d1d13",
    950: "#1c120c",
  },

  // Semantic Colors — Light Mode
  light: {
    bgPrimary: "#fffdf8",
    bgSecondary: "#f6efdf",
    bgTertiary: "#eee2ca",
    textPrimary: "#302116",
    textSecondary: "#65513e",
    textMuted: "#927e68",
    borderDefault: "#e8dac0",
    borderSubtle: "#f0e7d7",
  },

  // Semantic Colors — Dark Mode
  dark: {
    bgPrimary: "#21170f",
    bgSecondary: "#2d2016",
    bgTertiary: "#3c2b1d",
    textPrimary: "#f8efdf",
    textSecondary: "#dac7a9",
    textMuted: "#ad9474",
    borderDefault: "#4a3523",
    borderSubtle: "#3a291b",
  },

  // Functional (Light — per spec §11.1)
  success: "#16a34a",
  warning: "#f59e0b",
  error: "#dc2626",
  info: "#2563eb",

  // Functional (Dark — brighter for contrast per spec §15.2)
  darkSuccess: "#4ade80",
  darkWarning: "#fbbf24",
  darkError: "#f87171",
  darkInfo: "#7da3c4",
} as const;

export type ColorToken = keyof typeof colors;
