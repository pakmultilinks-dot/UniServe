/**
 * CategoryChips — Horizontal scrollable category filter.
 *
 * Design spec: paddingHorizontal 20, gap 8, chip paddingHorizontal 14,
 * paddingVertical 8, borderRadius 20. Active: brandGreen bg, white text.
 * Inactive: bgSecondary bg, textSecondary text.
 */

import React from "react";
import { ScrollView, Pressable, Text, StyleSheet, ViewStyle } from "react-native";
import { useTheme } from "../contexts/ThemeContext";
import { textColor, bgColor, brandGreen } from "../theme";

const CATEGORY_EMOJI: Record<string, string> = {
  all: "🍽️",
  breakfast: "🍳",
  main_course: "🍛",
  side_dish: "🥗",
  dessert: "🍰",
  beverage: "☕",
  snack: "🍿",
  salad: "🥬",
  soup: "🍜",
};

const CATEGORY_LABELS: Record<string, string> = {
  all: "All",
  breakfast: "Breakfast",
  main_course: "Main",
  side_dish: "Sides",
  dessert: "Desserts",
  beverage: "Drinks",
  snack: "Snacks",
  salad: "Salad",
  soup: "Soup",
};

export type CategoryKey = keyof typeof CATEGORY_EMOJI;

interface CategoryChipsProps {
  categories: CategoryKey[];
  selected: CategoryKey;
  onSelect: (category: CategoryKey) => void;
}

export default function CategoryChips({
  categories,
  selected,
  onSelect,
}: CategoryChipsProps) {
  const { resolvedTheme } = useTheme();
  const tc = (v: "primary" | "secondary" | "muted") => textColor(resolvedTheme, v);
  const bg = (v: "primary" | "secondary" | "tertiary") => bgColor(resolvedTheme, v);
  const brand = brandGreen(resolvedTheme);

  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.container}
    >
      {categories.map((cat) => {
        const isActive = cat === selected;
        return (
          <Pressable
            key={cat}
            onPress={() => onSelect(cat)}
            style={[
              styles.chip,
              {
                backgroundColor: isActive ? brand : bg("secondary"),
              },
            ]}
          >
            <Text style={styles.emoji}>{CATEGORY_EMOJI[cat] ?? "🍽️"}</Text>
            <Text
              style={[
                styles.label,
                {
                  color: isActive ? "#ffffff" : tc("secondary"),
                },
              ]}
            >
              {CATEGORY_LABELS[cat] ?? cat}
            </Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 20,
    gap: 8,
    paddingVertical: 4,
  },
  chip: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
  },
  emoji: {
    fontSize: 14,
    marginRight: 6,
  },
  label: {
    fontSize: 13,
    fontWeight: "500",
    lineHeight: 18,
  },
});
