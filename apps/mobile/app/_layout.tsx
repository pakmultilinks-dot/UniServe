/**
 * UniServe — Mobile Application Root Layout
 *
 * Wraps the app with AuthProvider and ThemeProvider.
 * Routes are organized as:
 *   - (auth): unauthenticated screens (login, register, verify-email)
 *   - (app):  authenticated screens (main app content)
 */

import React from "react";
import { ActivityIndicator, Text, View } from "react-native";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";

import { AuthProvider, useAuth } from "../src/contexts/AuthContext";
import { ThemeProvider, useTheme } from "../src/contexts/ThemeContext";
import { CartProvider } from "../src/contexts/CartContext";
import { FavoritesProvider } from "../src/contexts/FavoritesContext";
import { NotificationsProvider } from "../src/contexts/NotificationsContext";
import WebDashboardGate from "../src/components/WebDashboardGate";
import { assertApiConfigured, APP_ENV } from "../src/config";

// Fail fast on placeholder production API origins (see config.ts).
// Development (localhost/LAN) is unaffected.
if (APP_ENV !== "development") {
  assertApiConfigured();
}

/**
 * Roles allowed in the mobile ordering app.
 * The mobile app is for students and faculty only — cafeteria staff and
 * university admins use the web dashboard instead.
 */
const MOBILE_ROLES = ["student", "faculty"];

/**
 * Phase 53 — admins/managers/staff who sign in on mobile no longer get a
 * silent logout + blank screen. They see an explicit "Use the Web Dashboard"
 * gate with the existing Sign Out action. No admin data or management
 * surfaces are mounted for them; the session model is otherwise unchanged
 * and backend RBAC remains the enforcement boundary.
 */
function RoleGate({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, user } = useAuth();

  // Keep the root navigator mounted to display a visible loading screen.
  // Returning null here hid the entire app during session restoration.
  if (isLoading) return <>{children}</>;

  if (isAuthenticated && user && !MOBILE_ROLES.includes(user.role)) {
    return <WebDashboardGate />;
  }

  return <>{children}</>;
}

function RootNavigator() {
  const { isAuthenticated, isLoading } = useAuth();
  const { resolvedTheme } = useTheme();

  if (isLoading) {
    return (
      <View
        accessible
        accessibilityLabel="UniServe is restoring your session"
        style={{
          flex: 1,
          backgroundColor: resolvedTheme === "dark" ? "#231d17" : "#fcfaf5",
          alignItems: "center",
          justifyContent: "center",
          gap: 16,
          padding: 24,
        }}
      >
        <StatusBar style={resolvedTheme === "dark" ? "light" : "dark"} />
        <ActivityIndicator size="large" color="#bb9a55" />
        <Text style={{
          color: resolvedTheme === "dark" ? "#f5f0e7" : "#302116",
          fontSize: 17,
          fontWeight: "600",
          textAlign: "center",
        }}>
          Loading UniServe
        </Text>
        <Text style={{
          color: resolvedTheme === "dark" ? "#d1c4b6" : "#766c60",
          fontSize: 14,
          textAlign: "center",
        }}>
          Checking your session…
        </Text>
      </View>
    );
  }

  return (
    <>
      <StatusBar style={resolvedTheme === "dark" ? "light" : "dark"} />
      {/* Both route groups are always mounted. Which one is *reachable*
          is governed by the Redirect guards in (auth)/_layout and
          (app)/_layout — not by conditionally swapping <Stack.Screen>. A
          conditional swap here changed the mounted navigator at the same
          instant the auth-guard Redirect fired, so the two navigation
          mechanisms fought and SceneView looped ("Maximum update depth
          exceeded") during login (Phase 43). */}
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="(auth)" />
        <Stack.Screen name="(app)" />
      </Stack>
    </>
  );
}

export default function RootLayout() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <NotificationsProvider>
          <FavoritesProvider>
            <CartProvider>
              <RoleGate>
                <RootNavigator />
              </RoleGate>
            </CartProvider>
          </FavoritesProvider>
        </NotificationsProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
