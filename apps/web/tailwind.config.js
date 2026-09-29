/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        brand: {
          50:  "#fbf4e4",
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
          DEFAULT: "#8c6935",
        },
        gold: {
          50:  "#fbf4e4",
          100: "#f3e4bf",
          200: "#e8d19b",
          300: "#ddbd7b",
          400: "#d2ad69",
          500: "#c7a15b",
          600: "#ae8746",
          700: "#8c6935",
          800: "#6d4f2b",
          900: "#4b3421",
          DEFAULT: "#c7a15b",
        },
        warm: {
          50:  "#fffdf8",
          100: "#fbf6ec",
          200: "#f3ead8",
          300: "#e6d8bf",
          400: "#d2bea0",
          500: "#b8a388",
          600: "#95816b",
          700: "#74604d",
          800: "#574433",
          900: "#3e2d20",
          950: "#2d1d13",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        display: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      fontSize: {
        "2xs": ["0.625rem", { lineHeight: "0.875rem" }],
      },
      boxShadow: {
        "card":      "0 1px 3px 0 rgba(0, 0, 0, 0.06), 0 1px 2px -1px rgba(0, 0, 0, 0.06)",
        "card-hover":"0 4px 6px -1px rgba(0, 0, 0, 0.08), 0 2px 4px -2px rgba(0, 0, 0, 0.06)",
        "sidebar":   "1px 0 3px 0 rgba(0, 0, 0, 0.05)",
      },
      borderRadius: {
        "xl":  "0.75rem",
        "2xl": "1rem",
      },
      animation: {
        "fade-in":    "fadeIn 0.2s ease-out",
        "slide-in":   "slideIn 0.25s ease-out",
        "pulse-soft": "pulseSoft 2s ease-in-out infinite",
      },
      keyframes: {
        fadeIn:    { "0%": { opacity: "0" }, "100%": { opacity: "1" } },
        slideIn:   { "0%": { opacity: "0", transform: "translateY(4px)" }, "100%": { opacity: "1", transform: "translateY(0)" } },
        pulseSoft: { "0%, 100%": { opacity: "1" }, "50%": { opacity: "0.7" } },
      },
    },
  },
  plugins: [],
};
