/**
 * CafeteriaBadge — Shows currently selected cafeteria.
 *
 * Compact badge with restaurant icon, cafeteria name, and chevron.
 * Tapping triggers a callback to open cafeteria selector bottom sheet.
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
  const tcMuted = textColor(resolvedTheme, "muted");
  const bg = bgColor(resolvedTheme, "secondary");
  const brand = brandGreen(resolvedTheme);

  return (
    <Pressable
      onPress={onPress}
      style={[styles.badge, { backgroundColor: bg }]}
      hitSlop={8}
      accessibilityLabel={`Current cafeteria: ${name}. Tap to change.`}
      accessibilityRole="button"
    >
      <Ionicons name="restaurant-outline" size={14} color={brand} />
      <Text style={[styles.name, { color: tcMuted }]} numberOfLines={1}>
        {name}
      </Text>
      <Ionicons name="chevron-down" size={14} color={tcMuted} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    gap: 6,
    marginHorizontal: 20,
    marginTop: 4,
  },
  name: {
    fontSize: 13,
    fontWeight: "500",
    lineHeight: 16,
    flex: 1,
  },
});
