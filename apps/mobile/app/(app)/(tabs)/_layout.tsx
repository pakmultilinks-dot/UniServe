/**
 * UniServe — Tab Navigator Layout (App)
 *
 * Bottom tab navigator with 4 tabs: Home, My Orders, Favorites, Profile.
 * Uses Ionicons for all tab icons per design spec.
 * Tab bar height 56px, active brandGreen, inactive textMuted.
 */
import React from "react";
import { Tabs } from "expo-router";
import { Platform, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTheme } from "../../../src/contexts/ThemeContext";
import { useCart } from "../../../src/contexts/CartContext";
import { textColor, bgColor, brandGreen } from "../../../src/theme";

type IoniconName = React.ComponentProps<typeof Ionicons>["name"];

function TabBarIcon({
  name,
  outline,
  color,
}: {
  name: IoniconName;
  outline: IoniconName;
  color: string;
}) {
  return <Ionicons name={color === "#005400" || color === "#22c55e" ? name : outline} size={24} color={color} />;
}

export default function TabsLayout() {
  const { resolvedTheme } = useTheme();
  const { cartItemCount } = useCart();
  const bg = bgColor(resolvedTheme, "primary");
  const brand = brandGreen(resolvedTheme);
  const borderCol = textColor(resolvedTheme, "primary") === "#f0f1f4"
    ? "#2a3042" : "#e2e4e8";

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: brand,
        tabBarInactiveTintColor: textColor(resolvedTheme, "muted"),
        tabBarStyle: {
          backgroundColor: bg,
          borderTopColor: borderCol,
          borderTopWidth: StyleSheet.hairlineWidth,
          height: Platform.OS === "ios" ? 84 : 56,
          paddingBottom: Platform.OS === "ios" ? 24 : 4,
          paddingTop: 4,
        },
        tabBarLabelStyle: {
          fontSize: 10,
          fontWeight: "500",
          lineHeight: 14,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Home",
          tabBarIcon: ({ color }) => (
            <TabBarIcon name="home" outline="home-outline" color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="orders"
        options={{
          title: "My Orders",
          tabBarIcon: ({ color }) => (
            <TabBarIcon name="receipt" outline="receipt-outline" color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="favorites"
        options={{
          title: "Favorites",
          tabBarIcon: ({ color }) => (
            <TabBarIcon name="heart" outline="heart-outline" color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "Profile",
          tabBarIcon: ({ color }) => (
            <TabBarIcon name="person" outline="person-outline" color={color} />
          ),
        }}
      />
    </Tabs>
  );
}
