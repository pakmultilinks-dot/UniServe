/**
 * UniServe — Favorites Screen
 *
 * Placeholder for saved favorite items for quick reordering.
 * Shows empty state with heart icon per design spec.
 */
import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { useTheme } from "../../../src/contexts/ThemeContext";
import { textColor, bgColor, brandGreen } from "../../../src/theme";

export default function FavoritesScreen() {
  const { resolvedTheme } = useTheme();

  const brand = brandGreen(resolvedTheme);
  const tc = textColor(resolvedTheme, "primary");
  const tcMuted = textColor(resolvedTheme, "muted");
  const bg = bgColor(resolvedTheme, "primary");

  return (
    <View style={[styles.screen, { backgroundColor: bg }]}>
      <View style={styles.iconContainer}>
        <Ionicons name="heart-outline" size={56} color={brand + "30"} />
      </View>
      <Text style={[styles.title, { color: tc }]}>No favorites yet</Text>
      <Text style={[styles.description, { color: tcMuted }]}>
        Tap the heart icon on any menu item to save it here for quick reordering.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 40,
  },
  iconContainer: {
    width: 96,
    height: 96,
    borderRadius: 48,
    backgroundColor: "#005400" + "08",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16,
  },
  title: {
    fontSize: 18,
    fontWeight: "600",
    marginBottom: 8,
  },
  description: {
    fontSize: 14,
    textAlign: "center",
    lineHeight: 20,
  },
});
