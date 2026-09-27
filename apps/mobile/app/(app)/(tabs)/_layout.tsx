/**
 * UniServe — Tab Navigator Layout (App)
 *
 * Bottom tab navigator for Home, Orders, and Profile.
 * Uses LGU brand colors and Unicode icons.
 */
import React from "react";
import { Tabs } from "expo-router";
import { Text, StyleSheet, Platform } from "react-native";
import { useTheme } from "../../../src/contexts/ThemeContext";
import { useCart } from "../../../src/contexts/CartContext";
import { colors, bgColor, textColor } from "../../../src/theme";

function TabIcon({ emoji }: { emoji: string; color: string }) {
  return <Text style={{ fontSize: 22 }}>{emoji}</Text>;
}

/** Badge icon that shows cart item count */
function CartTabIcon({ emoji, count }: { emoji: string; color: string; count: number }) {
  return (
    <React.Fragment>
      <Text style={{ fontSize: 22 }}>{emoji}</Text>
      {count > 0 && (
        <Text
          style={{
            position: "absolute",
            top: -4,
            right: -8,
            backgroundColor: colors.brand[700],
            color: "#fff",
            fontSize: 9,
            fontWeight: "700",
            borderRadius: 8,
            minWidth: 16,
            height: 16,
            textAlign: "center",
            lineHeight: 16,
            paddingHorizontal: 4,
            overflow: "hidden",
          }}
        >
          {count > 99 ? "99+" : count}
        </Text>
      )}
    </React.Fragment>
  );
}

export default function TabsLayout() {
  const { resolvedTheme } = useTheme();
  const { cartItemCount } = useCart();
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
          borderTopColor:
            resolvedTheme === "dark"
              ? colors.dark.borderDefault
              : colors.light.borderDefault,
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
          tabBarIcon: ({ color }) => <TabIcon emoji="🏠" color={color} />,
        }}
      />
      <Tabs.Screen
        name="orders"
        options={{
          title: "Orders",
          tabBarLabel: "Orders",
          tabBarIcon: ({ color }) => <TabIcon emoji="📋" color={color} />,
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "Profile",
          tabBarLabel: "Profile",
          tabBarIcon: ({ color }) => <TabIcon emoji="👤" color={color} />,
        }}
      />
    </Tabs>
  );
}
