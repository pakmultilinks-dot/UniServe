/**
 * UniServe — App Route Group Layout
 *
 * Stack navigator wrapping the tab navigator and detail screens.
 * The tabs provide the main navigation, while cart, checkout,
 * item detail, and order detail are pushed on top (hiding the tab bar).
 */
import React from "react";
import { Redirect, Stack } from "expo-router";
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
  const { isAuthenticated, isLoading } = useAuth();
  const bg = bgColor(resolvedTheme, "primary");
  const tc = textColor(resolvedTheme, "primary");
  const brand = brandGreen(resolvedTheme);

  // Unauthenticated sessions are sent to the login screen — logout and
  // token expiry both land here cleanly (Phase 42 P2-3 symmetric guard).
  if (!isLoading && !isAuthenticated) {
    return <Redirect href="/login" />;
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
          headerLeft: ({ onPress }) => <BackButton onPress={onPress!} />,
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
          headerLeft: ({ onPress }) => <BackButton onPress={onPress!} />,
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
          headerLeft: ({ onPress }) => <BackButton onPress={onPress!} />,
        }}
      />
    </Stack>
  );
}
