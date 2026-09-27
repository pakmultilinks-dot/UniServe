/**
 * FoodImage — Food item image with category-based placeholder.
 *
 * When no image URL is available, shows a colored background
 * with the category icon. When image URL exists, loads the image.
 */

import React from "react";
import { View, Image, StyleSheet, ViewStyle } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import type { MenuCategory } from "@uniserve/shared-types";
import { bgColor } from "../theme";

const CATEGORY_COLORS: Record<string, string> = {
  breakfast: "#fef3c7",
  main_course: "#dcfce7",
  side_dish: "#e0f2fe",
  dessert: "#fce7f3",
  beverage: "#f5f3ff",
  snack: "#fff7ed",
  salad: "#ecfdf5",
  soup: "#fef2f2",
};

interface FoodImageProps {
  uri?: string | null;
  category?: MenuCategory | string;
  size?: number;
  borderRadius?: number;
  style?: ViewStyle;
}

export default function FoodImage({
  uri,
  category,
  size,
  borderRadius = 12,
  style,
}: FoodImageProps) {
  const bgColorHex = CATEGORY_COLORS[category ?? ""] ?? "#f5f5f7";

  const containerStyle: ViewStyle[] = [
    styles.container,
    { borderRadius },
    size ? { width: size, height: size } : undefined,
    style,
  ].filter(Boolean) as ViewStyle[];

  if (uri) {
    return (
      <View style={containerStyle}>
        <Image
          source={{ uri }}
          style={[styles.image, { borderRadius }]}
          resizeMode="cover"
        />
      </View>
    );
  }

  return (
    <View style={[containerStyle, { backgroundColor: bgColorHex }]}>
      <Ionicons name="restaurant-outline" size={28} color="#9ca3af" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
  },
  image: {
    width: "100%",
    height: "100%",
  },
});
