/**
 * UniServe — Mobile Application Root Layout
 *
 * Wraps the app with AuthProvider and ThemeProvider.
 * Routes are organized as:
 *   - (auth): unauthenticated screens (login, register, verify-email)
 *   - (app):  authenticated screens (main app content)
 */

import React from "react";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";

import { AuthProvider, useAuth } from "../src/contexts/AuthContext";
import { ThemeProvider, useTheme } from "../src/contexts/ThemeContext";
import { CartProvider } from "../src/contexts/CartContext";
import { FavoritesProvider } from "../src/contexts/FavoritesContext";
import { NotificationsProvider } from "../src/contexts/NotificationsContext";
import WebDashboardGate from "../src/components/WebDashboardGate";

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

  if (isLoading) return null;

  if (isAuthenticated && user && !MOBILE_ROLES.includes(user.role)) {
    return <WebDashboardGate />;
  }

  return <>{children}</>;
}

function RootNavigator() {
  const { isAuthenticated, isLoading } = useAuth();
  const { resolvedTheme } = useTheme();

  if (isLoading) {
    return null;
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
