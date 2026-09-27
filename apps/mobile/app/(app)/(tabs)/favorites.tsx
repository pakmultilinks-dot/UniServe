/**
 * UniServe — Favorites Screen (Placeholder)
 *
 * Placeholder screen for future favorites feature.
 * Shows empty state with heart icon per design spec.
 */
import React from "react";
import { View, StyleSheet } from "react-native";
import { useTheme } from "../../../src/contexts/ThemeContext";
import { bgColor } from "../../../src/theme";
import { EmptyState } from "../../../src/components/ui";

export default function FavoritesScreen() {
  const { resolvedTheme } = useTheme();
  const bg = bgColor(resolvedTheme, "primary");

  return (
    <View style={[styles.screen, { backgroundColor: bg }]}>
      <EmptyState
        icon="heart-outline"
        title="No favorites yet"
        description="Tap the heart icon on any item to save it here for quick reordering."
      />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
});
