/**
 * UniServe — App Route Group Layout
 *
 * Stack navigator wrapping the tab navigator and detail screens.
 * The tabs provide the main navigation, while cart and item detail
 * are pushed on top (hiding the tab bar).
 */
import React from "react";
import { Stack } from "expo-router";
import { useTheme } from "../../src/contexts/ThemeContext";
import { colors, bgColor, textColor } from "../../src/theme";

export default function AppLayout() {
  const { resolvedTheme } = useTheme();
  const bg = bgColor(resolvedTheme, "primary");
  const tc = textColor(resolvedTheme, "primary");

  return (
    <Stack
      screenOptions={{
        headerShown: false,
      }}
    >
      <Stack.Screen name="(tabs)" />
      <Stack.Screen
        name="cart"
        options={{
          headerShown: true,
          title: "Cart",
          headerStyle: { backgroundColor: bg },
          headerTintColor: tc,
          headerTitleStyle: { fontWeight: "600" },
          presentation: "card",
        }}
      />
      <Stack.Screen
        name="item/[id]"
        options={{
          headerShown: true,
          title: "Item Details",
          headerStyle: { backgroundColor: bg },
          headerTintColor: tc,
          headerTitleStyle: { fontWeight: "600" },
          presentation: "card",
        }}
      />
    </Stack>
  );
}
