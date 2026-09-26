import { Stack } from "expo-router";

import { AuthProvider, useAuth } from "../src/contexts/AuthContext";

/**
 * UniServe — Mobile Application Root Layout
 *
 * Wraps the app with AuthProvider for authentication state management.
 * Routes are organized as:
 *   - (auth): unauthenticated screens (login, register, verify-email)
 *   - (app):  authenticated screens (main app content)
 */

function RootNavigator() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return null; // Or a splash screen component
  }

  return (
    <Stack screenOptions={{ headerShown: false }}>
      {isAuthenticated ? (
        <Stack.Screen name="(app)" />
      ) : (
        <Stack.Screen name="(auth)" />
      )}
    </Stack>
  );
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <RootNavigator />
    </AuthProvider>
  );
}
