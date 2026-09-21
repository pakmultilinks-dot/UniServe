import { Stack } from "expo-router";

/**
 * UniServe — Mobile Application Root Layout
 *
 * This is the entry point for the React Native + Expo mobile app.
 * Navigation structure will be built out in Phase 2+.
 */
export default function RootLayout() {
  return (
    <Stack
      screenOptions={{
        headerShown: false,
      }}
    >
      <Stack.Screen name="(tabs)" />
    </Stack>
  );
}
