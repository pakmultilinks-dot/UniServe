/**
 * UniServe — Auth Route Group Layout
 *
 * Stack navigator for authentication screens.
 * Headers shown for verify-email, forgot-password, reset-password.
 */
import React from "react";
import { Redirect, Stack, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { TouchableOpacity } from "react-native";
import { useAuth } from "../../src/contexts/AuthContext";
import { useTheme } from "../../src/contexts/ThemeContext";
import { textColor, bgColor, brandGreen } from "../../src/theme";

function BackButton({ onPress }: { onPress: () => void }) {
  const { resolvedTheme } = useTheme();
  return (
    <TouchableOpacity
      onPress={onPress}
      hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
      style={{ paddingLeft: 4, minWidth: 44, minHeight: 44, justifyContent: "center" }}
    >
      <Ionicons name="chevron-back" size={24} color={textColor(resolvedTheme, "primary")} />
    </TouchableOpacity>
  );
}

export default function AuthLayout() {
  const { resolvedTheme } = useTheme();
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  /* Same fix as (app)/_layout.tsx: the SDK 57 native-stack header passes no
     `onPress` to headerLeft on Android, so navigate explicitly. */
  const headerBack = () => <BackButton onPress={() => router.back()} />;
  const bg = bgColor(resolvedTheme, "primary");
  const tc = textColor(resolvedTheme, "primary");
  const brand = brandGreen(resolvedTheme);

  // Authenticated users belong inside the app — route them to the tabs from
  // any auth screen (login/register/session restore). Login previously
  // succeeded but stayed on /login because the root navigator's declarative
  // screen switch never navigates (Phase 42 P2-3).
  //
  // We target the explicitly-grouped href `/(app)/(tabs)` rather than `/`.
  // The bare `/` is ambiguous: both (auth)/index (onboarding) and
  // (app)/(tabs)/index (home) collapse to `/` because the groups are
  // optional. During the login->app transition both groups are briefly
  // mounted, so a bare `/` redirect bounces between the two index routes and
  // the navigator loops ("Maximum update depth exceeded"). Naming the group
  // removes the ambiguity. (Phase 43.)
  if (!isLoading && isAuthenticated) {
    return <Redirect href="/(app)/(tabs)" />;
  }

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        animation: "slide_from_right",
      }}
    >
      <Stack.Screen name="landing" />
      <Stack.Screen name="login" />
      <Stack.Screen name="register" />
      <Stack.Screen
        name="verify-email"
        options={{
          headerShown: true,
          title: "Verify Email",
          headerStyle: { backgroundColor: bg },
          headerTintColor: brand,
          headerTitleStyle: { fontWeight: "600", fontSize: 16, color: tc },
          headerShadowVisible: false,
          headerLeft: headerBack,
        }}
      />
      <Stack.Screen
        name="forgot-password"
        options={{
          headerShown: true,
          title: "Forgot Password",
          headerStyle: { backgroundColor: bg },
          headerTintColor: brand,
          headerTitleStyle: { fontWeight: "600", fontSize: 16, color: tc },
          headerShadowVisible: false,
          headerLeft: headerBack,
        }}
      />
      <Stack.Screen
        name="reset-password"
        options={{
          headerShown: true,
          title: "Reset Password",
          headerStyle: { backgroundColor: bg },
          headerTintColor: brand,
          headerTitleStyle: { fontWeight: "600", fontSize: 16, color: tc },
          headerShadowVisible: false,
          headerLeft: headerBack,
        }}
      />
    </Stack>
  );
}

