/**
 * CafeteriaBadge — Shows currently selected cafeteria.
 *
 * Compact badge with restaurant icon and cafeteria name.
 * Tapping triggers a callback (future: cafeteria selector).
 */

import React from "react";
import { View, Text, Pressable, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTheme } from "../contexts/ThemeContext";
import { textColor, bgColor, brandGreen } from "../theme";

interface CafeteriaBadgeProps {
  name: string;
  onPress?: () => void;
}

export default function CafeteriaBadge({ name, onPress }: CafeteriaBadgeProps) {
  const { resolvedTheme } = useTheme();
  const tc = (v: "primary" | "secondary" | "muted") => textColor(resolvedTheme, v);
  const bg = (v: "primary" | "secondary") => bgColor(resolvedTheme, v);
  const brand = brandGreen(resolvedTheme);

  return (
    <Pressable
      onPress={onPress}
      style={[styles.badge, { backgroundColor: bg("secondary") }]}
      hitSlop={8}
    >
      <Ionicons name="restaurant-outline" size={14} color={brand} />
      <Text style={[styles.name, { color: tc("secondary") }]} numberOfLines={1}>
        {name}
      </Text>
      <Ionicons name="chevron-forward" size={12} color={tc("muted")} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 20,
    gap: 6,
  },
  name: {
    fontSize: 13,
    fontWeight: "500",
    lineHeight: 16,
    maxWidth: 160,
  },
});
