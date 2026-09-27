/**
 * FoodCard — Grid-view food item card.
 *
 * Design spec:
 * - Container: borderRadius 12, bgPrimary, overflow hidden
 * - Image: aspectRatio 1 (square), full width, resizeMode cover
 * - Quantity badge: absolute top-right of image
 * - Content padding: 10
 * - Name: 14px/600, textPrimary, numberOfLines 1
 * - Description: 12px/400, textMuted, numberOfLines 1
 * - Price row: space-between, center aligned, marginTop 6
 * - Price: 15px/700, brandGreen
 * - Add button: 28x28 circle, brandGreen bg, white + icon
 * - Compact stepper when qty > 0
 */

import React from "react";
import { View, Text, Pressable, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTheme } from "../contexts/ThemeContext";
import { textColor, bgColor, borderColor, brandGreen } from "../theme";
import FoodImage from "./FoodImage";
import type { MenuCategory } from "@uniserve/shared-types";

interface FoodCardProps {
  name: string;
  description?: string;
  price: number; // paisa
  imageUri?: string | null;
  category?: MenuCategory | string;
  quantity?: number;
  onPress?: () => void;
  onAdd?: () => void;
  onIncrement?: () => void;
  onDecrement?: () => void;
}

function formatPrice(paisa: number): string {
  return `PKR ${Math.round(paisa / 100)}`;
}

export default function FoodCard({
  name,
  description,
  price,
  imageUri,
  category,
  quantity = 0,
  onPress,
  onAdd,
  onIncrement,
  onDecrement,
}: FoodCardProps) {
  const { resolvedTheme } = useTheme();
  const tc = (v: "primary" | "secondary" | "muted") => textColor(resolvedTheme, v);
  const bg = bgColor(resolvedTheme, "primary");
  const bc = borderColor(resolvedTheme, "default");
  const brand = brandGreen(resolvedTheme);

  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.card,
        { backgroundColor: bg, borderColor: bc },
        pressed && styles.pressed,
      ]}
    >
      {/* Image */}
      <View style={styles.imageContainer}>
        <FoodImage
          uri={imageUri}
          category={category as MenuCategory}
          style={styles.image}
        />
        {quantity > 0 && (
          <View style={[styles.qtyBadge, { backgroundColor: brand }]}>
            <Text style={styles.qtyText}>{quantity}</Text>
          </View>
        )}
      </View>

      {/* Content */}
      <View style={styles.content}>
        <Text
          style={[styles.name, { color: tc("primary") }]}
          numberOfLines={1}
          ellipsizeMode="tail"
        >
          {name}
        </Text>
        {description ? (
          <Text
            style={[styles.desc, { color: tc("muted") }]}
            numberOfLines={1}
            ellipsizeMode="tail"
          >
            {description}
          </Text>
        ) : null}

        {/* Price row */}
        <View style={styles.priceRow}>
          <Text style={[styles.price, { color: brand }]}>{formatPrice(price)}</Text>

          {quantity > 0 ? (
            /* Compact stepper */
            <View style={[styles.stepper, { backgroundColor: bgColor(resolvedTheme, "secondary") }]}>
              <Pressable
                onPress={onDecrement}
                style={styles.stepBtn}
                hitSlop={8}
              >
                <Ionicons name="remove" size={14} color={tc("secondary")} />
              </Pressable>
              <Text style={[styles.stepQty, { color: tc("primary") }]}>{quantity}</Text>
              <Pressable
                onPress={onIncrement}
                style={styles.stepBtn}
                hitSlop={8}
              >
                <Ionicons name="add" size={14} color={tc("secondary")} />
              </Pressable>
            </View>
          ) : (
            /* Add button */
            <Pressable
              onPress={onAdd}
              style={[styles.addBtn, { backgroundColor: brand }]}
              hitSlop={8}
            >
              <Ionicons name="add" size={16} color="#ffffff" />
            </Pressable>
          )}
        </View>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 12,
    overflow: "hidden",
    borderWidth: 1,
  },
  pressed: {
    opacity: 0.85,
    transform: [{ scale: 0.98 }],
  },
  imageContainer: {
    width: "100%",
    aspectRatio: 1,
    position: "relative",
  },
  image: {
    width: "100%",
    height: "100%",
    borderRadius: 0,
  },
  qtyBadge: {
    position: "absolute",
    top: 8,
    right: 8,
    borderRadius: 10,
    paddingHorizontal: 8,
    paddingVertical: 2,
    minWidth: 20,
    alignItems: "center",
  },
  qtyText: {
    color: "#ffffff",
    fontSize: 12,
    fontWeight: "700",
  },
  content: {
    padding: 10,
  },
  name: {
    fontSize: 14,
    fontWeight: "600",
    lineHeight: 18,
  },
  desc: {
    fontSize: 12,
    fontWeight: "400",
    lineHeight: 16,
    marginTop: 2,
  },
  priceRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 6,
  },
  price: {
    fontSize: 15,
    fontWeight: "700",
    lineHeight: 20,
  },
  addBtn: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
  },
  stepper: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 8,
    height: 28,
  },
  stepBtn: {
    width: 28,
    height: 28,
    alignItems: "center",
    justifyContent: "center",
  },
  stepQty: {
    fontSize: 13,
    fontWeight: "600",
    minWidth: 20,
    textAlign: "center",
  },
});
