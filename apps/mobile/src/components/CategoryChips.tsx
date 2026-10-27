/**
 * CategoryChips — Horizontal scrollable category filter.
 *
 * Warm café filter chips with caramel selection and restrained cream surfaces.
 * NO emojis — uses Ionicons for each category.
 */

import React from "react";
import { ScrollView, Pressable, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTheme } from "../contexts/ThemeContext";
import { textColor, bgColor, brandGreen, colors } from "../theme";

type IoniconName = keyof typeof Ionicons.glyphMap;

const CATEGORY_ICONS: Record<string, IoniconName> = {
  all: "grid-outline",
  breakfast: "sunny-outline",
  main_course: "restaurant-outline",
  side_dish: "leaf-outline",
  dessert: "ice-cream-outline",
  beverage: "cafe-outline",
  snack: "pizza-outline",
  salad: "nutrition-outline",
  soup: "flask-outline",
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

export type CategoryKey = keyof typeof CATEGORY_ICONS;

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
      showsHorizontalScrollIndicator={true}
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
                backgroundColor: isActive ? brand : bg("primary"),
                borderColor: isActive ? brand : "#e8dac0",
              },
            ]}
          >
            <Ionicons
              name={CATEGORY_ICONS[cat] ?? "grid-outline"}
              size={14}
              color={isActive ? colors.neutral[900] : tc("secondary")}
              style={styles.icon}
            />
            <Text
              style={[
                styles.label,
                {
                  color: isActive ? colors.neutral[900] : tc("secondary"),
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
    borderRadius: 12,
    borderWidth: 1,
  },
  icon: {
    marginRight: 6,
  },
  label: {
    fontSize: 13,
    fontWeight: "500",
    lineHeight: 18,
  },
});
