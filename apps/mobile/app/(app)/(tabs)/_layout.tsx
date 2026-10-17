/**
 * UniServe — Tab Navigator Layout (App)
 *
 * Bottom tab navigator with 5 tabs: Home, Orders, Cart, Favorites, Profile.
 * Notifications is no longer a tab — it is reachable from the header bell on
 * Home (where the user browses and waits on orders), keeping the tab bar to
 * the five requested destinations. Uses Ionicons for all tab icons.
 *
 * Android: the tab bar height + paddingBottom is computed from the bottom
 * safe-area inset (via onLayout of the tab bar container) so the bar clears
 * Android's gesture/navigation bar and every tab stays tappable. Cart badge
 * on the Home tab when items in cart (same absolute-positioned pattern as
 * before). Unread badge is shown on the Home header bell, not a tab.
 */
import React from "react";
import { Tabs } from "expo-router";
import { Platform, StyleSheet, View, Text } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
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
  const insets = useSafeAreaInsets();
  const bg = bgColor(resolvedTheme, "primary");
  const brand = brandGreen(resolvedTheme);
  const muted = textColor(resolvedTheme, "muted");
  const bc = resolvedTheme === "dark" ? colors.dark.borderDefault : colors.light.borderDefault;

  // Base tab bar content is 56dp tall. Adding the bottom safe-area inset as
  // padding guarantees the bar clears Android's gesture/navigation controls,
  // leaving every tab label and icon in the tappable area above the system UI.
  const tabBarHeight = 56 + Math.max(insets.bottom, Platform.OS === "ios" ? 20 : 8);
  const tabBarPaddingBottom = Math.max(insets.bottom, Platform.OS === "ios" ? 20 : 8);

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
          height: tabBarHeight,
          paddingBottom: tabBarPaddingBottom,
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
            <TabBarIcon name="home" outline="home-outline" color={color} focused={focused} />
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
        name="cart"
        options={{
          title: "Cart",
          tabBarIcon: ({ color, focused }) => (
            <View>
              <TabBarIcon name="cart" outline="cart-outline" color={color} focused={focused} />
              {cartItemCount > 0 && (
                <View style={[styles.badge, { backgroundColor: colors.error }]}>
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
