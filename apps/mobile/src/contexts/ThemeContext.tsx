/**
 * UniServe — Theme Context & Provider
 *
 * Manages light/dark theme state across the mobile app.
 * Persists to SecureStore. Supports system preference.
 */

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { useColorScheme } from "react-native";
import * as SecureStore from "expo-secure-store";

export type Theme = "light" | "dark" | "system";

interface ThemeContextType {
  /** Resolved theme — always "light" or "dark", never "system" */
  resolvedTheme: "light" | "dark";
  /** User preference — can be "system" */
  themePreference: Theme;
  /** Set user preference */
  setThemePreference: (theme: Theme) => void;
  /** Whether the theme has loaded from storage */
  isLoaded: boolean;
}

const THEME_KEY = "uniserve_theme";
const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

function resolveTheme(preference: Theme, systemScheme: "light" | "dark" | null | undefined): "light" | "dark" {
  if (preference === "system") {
    return systemScheme ?? "light";
  }
  return preference;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const systemColorScheme = useColorScheme();
  const [preference, setPreference] = useState<Theme>("system");
  const [isLoaded, setIsLoaded] = useState(false);

  // Load stored preference
  useEffect(() => {
    (async () => {
      try {
        const stored = await SecureStore.getItemAsync(THEME_KEY);
        if (stored === "light" || stored === "dark" || stored === "system") {
          setPreference(stored);
        }
      } catch {
        // Default to system
      } finally {
        setIsLoaded(true);
      }
    })();
  }, []);

  const setThemePreference = useCallback(async (theme: Theme) => {
    setPreference(theme);
    try {
      await SecureStore.setItemAsync(THEME_KEY, theme);
    } catch {
      // Non-critical
    }
  }, []);

  const resolvedTheme = resolveTheme(preference, systemColorScheme);

  const value: ThemeContextType = {
    resolvedTheme,
    themePreference: preference,
    setThemePreference,
    isLoaded,
  };

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextType {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
