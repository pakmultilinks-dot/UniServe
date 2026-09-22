import { Stack } from "expo-router";

import { AuthProvider } from "../src/contexts/AuthContext";

/**
 * UniServe — Mobile Application Root Layout
 *
 * Wraps the app with AuthProvider for authentication state management.
 */
export default function RootLayout() {
  return (
    <AuthProvider>
      <Stack
        screenOptions={{
          headerShown: false,
        }}
      >
        <Stack.Screen name="(tabs)" />
      </Stack>
    </AuthProvider>
  );
}
