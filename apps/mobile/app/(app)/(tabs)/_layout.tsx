/**
 * UniServe — Tab Navigator Layout (App)
 *
 * Bottom tab navigator with 4 tabs: Home, Orders, Favorites, Profile.
 * Uses Ionicons for all tab icons. Cart is contextual, NOT a tab.
 * Tab bar height 56px (Android) / 84px (iOS with safe area).
 * Active: brandGreen. Inactive: textMuted.
 * Cart badge on Home tab when items in cart.
 */
import React from "react";
import { Tabs } from "expo-router";
import { Platform, StyleSheet, View, Text } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTheme } from "../../../src/contexts/ThemeContext";
import { useCart } from "../../../src/contexts/CartContext";
import { textColor, bgColor, brandGreen, colors } from "../../../src/theme";

type IoniconName = React.ComponentProps<typeof Ionicons>["name"];

function TabBarIcon({
  name,
  outline,
  color,
  focused,
}: {
  name: IoniconName;
  outline: IoniconName;
  color: string;
  focused: boolean;
}) {
  return <Ionicons name={focused ? name : outline} size={24} color={color} />;
}

export default function TabsLayout() {
  const { resolvedTheme } = useTheme();
  const { cartItemCount } = useCart();
  const bg = bgColor(resolvedTheme, "primary");
  const brand = brandGreen(resolvedTheme);
  const muted = textColor(resolvedTheme, "muted");
  const bc = resolvedTheme === "dark" ? colors.dark.borderDefault : colors.light.borderDefault;

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: brand,
        tabBarInactiveTintColor: muted,
        tabBarStyle: {
          backgroundColor: bg,
          borderTopColor: bc,
          borderTopWidth: 1,
          height: Platform.OS === "ios" ? 84 : 56,
          paddingBottom: Platform.OS === "ios" ? 24 : 4,
          paddingTop: 4,
        },
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: "600",
          lineHeight: 14,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Home",
          tabBarIcon: ({ color, focused }) => (
            <View>
              <TabBarIcon name="home" outline="home-outline" color={color} focused={focused} />
              {cartItemCount > 0 && (
                <View
                  style={[
                    styles.badge,
                    {
                      backgroundColor: colors.error,
                    },
                  ]}
                >
                  <Text style={styles.badgeText}>
                    {cartItemCount > 99 ? "99+" : cartItemCount}
                  </Text>
                </View>
              )}
            </View>
          ),
        }}
      />
      <Tabs.Screen
        name="orders"
        options={{
          title: "Orders",
          tabBarIcon: ({ color, focused }) => (
            <TabBarIcon name="receipt" outline="receipt-outline" color={color} focused={focused} />
          ),
        }}
      />
      <Tabs.Screen
        name="favorites"
        options={{
          title: "Favorites",
          tabBarIcon: ({ color, focused }) => (
            <TabBarIcon name="heart" outline="heart-outline" color={color} focused={focused} />
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "Profile",
          tabBarIcon: ({ color, focused }) => (
            <TabBarIcon name="person" outline="person-outline" color={color} focused={focused} />
          ),
        }}
      />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  badge: {
    position: "absolute",
    top: -2,
    right: -6,
    borderRadius: 10,
    minWidth: 18,
    height: 18,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 4,
  },
  badgeText: {
    color: "#ffffff",
    fontSize: 10,
    fontWeight: "700",
    lineHeight: 14,
  },
});
