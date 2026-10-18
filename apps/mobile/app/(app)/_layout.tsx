/**
 * UniServe — App Route Group Layout
 *
 * Stack navigator wrapping the tab navigator and detail screens.
 * The tabs provide the main navigation, while cart, checkout,
 * item detail, and order detail are pushed on top (hiding the tab bar).
 */
import React from "react";
import { Redirect, Stack, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { TouchableOpacity } from "react-native";
import { useAuth } from "../../src/contexts/AuthContext";
import { useTheme } from "../../src/contexts/ThemeContext";
import { bgColor, textColor, brandGreen } from "../../src/theme";

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

export default function AppLayout() {
  const { resolvedTheme } = useTheme();
  const { isAuthenticated, isLoading, isEmailVerified, user } = useAuth();
  const router = useRouter();

  /* Expo Router SDK 57's native-stack header does NOT pass `onPress` into
     headerLeft on Android (the JS-header path does, native-stack does not),
     so a BackButton wired to the prop's onPress is silently inert. Call
     router.back() directly — works on both header implementations. */
  const headerBack = () => <BackButton onPress={() => router.back()} />;
  const bg = bgColor(resolvedTheme, "primary");
  const tc = textColor(resolvedTheme, "primary");
  const brand = brandGreen(resolvedTheme);

  // Unauthenticated sessions land on the landing page (hero → sign in /
  // sign up), not directly on the login form — logout and token expiry
  // both route through it cleanly (Phase 42 P2-3 symmetric guard).
  // The href names the (auth) group explicitly: a bare `/` is ambiguous
  // (both (auth)/index and (app)/(tabs)/index collapse to `/`) and bounces
  // between the two index routes while both groups are mounted (Phase 43).
  if (!isLoading && !isAuthenticated) {
    return <Redirect href="/landing" />;
  }

  // Defense in depth: an authenticated but unverified account must complete
  // email verification before entering the app. (The backend also rejects
  // unverified logins; this keeps the client from ever showing app content
  // to an unverified session.)
  if (!isLoading && isAuthenticated && !isEmailVerified && user) {
    const params = new URLSearchParams({
      user_id: user.id,
      email: user.university_email,
    });
    return <Redirect href={`/verify-email?${params.toString()}`} />;
  }

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        animation: "slide_from_right",
      }}
    >
      <Stack.Screen name="(tabs)" />
      <Stack.Screen
        name="notifications"
        options={{
          headerShown: true,
          title: "Notifications",
          headerStyle: { backgroundColor: bg },
          headerTintColor: brand,
          headerTitleStyle: { fontWeight: "600", fontSize: 16, color: tc },
          headerShadowVisible: false,
          headerLeft: headerBack,
        }}
      />
      <Stack.Screen
        name="item/[id]"
        options={{
          headerShown: false,
          presentation: "card",
        }}
      />
      <Stack.Screen
        name="checkout"
        options={{
          headerShown: true,
          title: "Checkout",
          headerStyle: { backgroundColor: bg },
          headerTintColor: brand,
          headerTitleStyle: { fontWeight: "600", fontSize: 16, color: tc },
          headerShadowVisible: false,
          headerLeft: headerBack,
        }}
      />
      <Stack.Screen
        name="order/[id]"
        options={{
          headerShown: true,
          title: "Order Details",
          headerStyle: { backgroundColor: bg },
          headerTintColor: brand,
          headerTitleStyle: { fontWeight: "600", fontSize: 16, color: tc },
          headerShadowVisible: false,
          headerLeft: headerBack,
        }}
      />
      <Stack.Screen
        name="order/[id]/qr"
        options={{
          headerShown: true,
          title: "Pickup QR",
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
