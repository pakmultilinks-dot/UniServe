/**
 * UniServe — App Route Group Layout
 *
 * Tab navigator for the main (authenticated) application.
 * Uses LGU brand colors and proper Unicode icons.
 */
import React from "react";
import { Tabs } from "expo-router";
import { Text, StyleSheet, Platform } from "react-native";
import { useTheme } from "../../src/contexts/ThemeContext";
import { colors, bgColor, textColor } from "../../src/theme";

function TabIcon({ emoji }: { emoji: string; color: string; focused?: boolean }) {
  return (
    <Text style={{ fontSize: 22 }}>{emoji}</Text>
  );
}

export default function AppLayout() {
  const { resolvedTheme } = useTheme();
  const bg = bgColor(resolvedTheme, "primary");
  const tc = textColor(resolvedTheme, "primary");
  const tcMuted = textColor(resolvedTheme, "muted");
  const tabBg = bgColor(resolvedTheme, "secondary");

  return (
    <Tabs
      screenOptions={{
        headerShown: true,
        headerStyle: {
          backgroundColor: bg,
        },
        headerTintColor: tc,
        headerTitleStyle: {
          fontWeight: "600",
        },
        tabBarStyle: {
          backgroundColor: tabBg,
          borderTopColor: resolvedTheme === "dark" ? colors.dark.borderDefault : colors.light.borderDefault,
          borderTopWidth: StyleSheet.hairlineWidth,
          paddingTop: 4,
          height: Platform.OS === "ios" ? 88 : 64,
        },
        tabBarActiveTintColor: colors.brand[700],
        tabBarInactiveTintColor: tcMuted,
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: "500",
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Home",
          tabBarLabel: "Home",
          tabBarIcon: ({ color }) => (
            <TabIcon emoji="🏠" color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="orders"
        options={{
          title: "Orders",
          tabBarLabel: "Orders",
          tabBarIcon: ({ color }) => (
            <TabIcon emoji="📋" color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="cafeterias"
        options={{
          title: "Cafeterias",
          tabBarLabel: "Cafeterias",
          tabBarIcon: ({ color }) => (
            <TabIcon emoji="🍽️" color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "Profile",
          tabBarLabel: "Profile",
          tabBarIcon: ({ color }) => (
            <TabIcon emoji="👤" color={color} />
          ),
        }}
      />
    </Tabs>
  );
}
