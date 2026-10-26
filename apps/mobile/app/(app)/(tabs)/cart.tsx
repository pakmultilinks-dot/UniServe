/**
 * UniServe — Cart tab
 *
 * One of the five main tabs (Home, Orders, Cart, Favorites, Profile). Wraps
 * the shared CartScreen; "Browse menu" navigates to the Home tab so the user
 * lands on the menu grid rather than popping a stack that has no parent here.
 */
import React, { useCallback } from "react";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";

import CartScreen from "../../../src/components/CartScreen";
import { useTheme } from "../../../src/contexts/ThemeContext";
import { bgColor } from "../../../src/theme";

export default function CartTab() {
  const { resolvedTheme } = useTheme();
  const router = useRouter();
  const bg = bgColor(resolvedTheme, "primary");

  const handleBrowseMenu = useCallback(() => {
    router.push("/");
  }, [router]);

  return (
    <SafeAreaView edges={["top"]} style={{ flex: 1, backgroundColor: bg }}>
      <CartScreen onBrowseMenu={handleBrowseMenu} bottomSafeArea={false} />
    </SafeAreaView>
  );
}
