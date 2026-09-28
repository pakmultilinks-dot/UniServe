/**
 * CartBar — Floating cart summary bar above the tab bar.
 *
 * Design spec:
 * - position absolute, bottom 70, left/right 16
 * - height 52, borderRadius 14
 * - Espresso background with high-contrast white text
 * - shadow: 0 4 8 rgba(0,0,0,0.2)
 * - Cart icon 20px white, count badge white bg/green text,
 *   count text 15px/600 white, total 16px/700 white, arrow 16px white
 */

import React, { useEffect, useRef } from "react";
import { View, Text, Pressable, StyleSheet, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTheme } from "../contexts/ThemeContext";
import { colors } from "../theme";

interface CartBarProps {
  itemCount: number;
  total: number; // paisa
  onPress: () => void;
}

function formatPrice(paisa: number): string {
  return `PKR ${Math.round(paisa / 100)}`;
}

export default function CartBar({ itemCount, total, onPress }: CartBarProps) {
  const { resolvedTheme } = useTheme();
  const bounceAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    Animated.sequence([
      Animated.timing(bounceAnim, {
        toValue: 1.2,
        duration: 100,
        useNativeDriver: true,
      }),
      Animated.spring(bounceAnim, {
        toValue: 1,
        friction: 3,
        tension: 100,
        useNativeDriver: true,
      }),
    ]).start();
  }, [itemCount]);

  return (
    <Pressable onPress={onPress} style={[styles.bar, { backgroundColor: colors.brand[900] }]}>
      <View style={styles.left}>
        <View style={styles.cartIconWrap}>
          <Ionicons name="cart" size={20} color="#ffffff" />
          {itemCount > 0 && (
            <Animated.View
              style={[
                styles.countBadge,
                { transform: [{ scale: bounceAnim }] },
              ]}
            >
              <Text style={styles.countText}>{itemCount}</Text>
            </Animated.View>
          )}
        </View>
        <Text style={styles.itemsLabel}>
          {itemCount} {itemCount === 1 ? "item" : "items"}
        </Text>
      </View>
      <View style={styles.right}>
        <Text style={styles.total}>{formatPrice(total)}</Text>
        <Ionicons name="arrow-forward" size={16} color="#ffffff" />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  bar: {
    position: "absolute",
    bottom: 70,
    left: 16,
    right: 16,
    height: 52,
    borderRadius: 14,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 8,
  },
  left: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  cartIconWrap: {
    position: "relative",
    width: 24,
    height: 24,
    alignItems: "center",
    justifyContent: "center",
  },
  countBadge: {
    position: "absolute",
    top: -6,
    right: -8,
    backgroundColor: "#ffffff",
    borderRadius: 10,
    paddingHorizontal: 6,
    paddingVertical: 2,
    minWidth: 18,
    alignItems: "center",
  },
  countText: {
    color: "#302116",
    fontSize: 11,
    fontWeight: "700",
  },
  itemsLabel: {
    color: "#ffffff",
    fontSize: 15,
    fontWeight: "600",
  },
  right: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  total: {
    color: "#ffffff",
    fontSize: 16,
    fontWeight: "700",
  },
});
