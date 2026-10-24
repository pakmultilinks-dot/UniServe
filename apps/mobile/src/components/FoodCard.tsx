/**
 * FoodCard — Grid-view food item card.
 *
 * Design spec:
 * - Container: softly rounded café-white surface, overflow hidden
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
import { View, Text, Pressable, StyleSheet, ActivityIndicator } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTheme } from "../contexts/ThemeContext";
import { textColor, bgColor, borderColor, brandGreen } from "../theme";
import FoodImage from "./FoodImage";
import type { MenuCategory } from "@uniserve/shared-types";

interface FoodCardProps {
  name: string;
  description?: string;
  /**
   * Optional secondary context line (e.g. cafeteria name on Favorites).
   * Rendered above the description; omitted where there is no per-card
   * context to show (e.g. Home, where the cafeteria is in the header).
   */
  subtitle?: string;
  price: number; // paisa
  imageUri?: string | null;
  category?: MenuCategory | string;
  preparationTimeMinutes?: number;
  isAvailable?: boolean;
  isBusy?: boolean;
  quantity?: number;
  onPress?: () => void;
  onAdd?: () => void;
  onIncrement?: () => void;
  onDecrement?: () => void;
  /** P3-5: favorite heart state. When onToggleFavorite is omitted, no heart renders. */
  isFavorite?: boolean;
  onToggleFavorite?: () => void;
}

function formatPrice(paisa: number): string {
  return `PKR ${Math.round(paisa / 100)}`;
}

export default function FoodCard({
  name,
  description,
  subtitle,
  price,
  imageUri,
  category,
  preparationTimeMinutes,
  isAvailable = true,
  isBusy = false,
  quantity = 0,
  onPress,
  onAdd,
  onIncrement,
  onDecrement,
  isFavorite = false,
  onToggleFavorite,
}: FoodCardProps) {
  const { resolvedTheme } = useTheme();
  const tc = (v: "primary" | "secondary" | "muted") => textColor(resolvedTheme, v);
  const bg = bgColor(resolvedTheme, "primary");
  const bc = borderColor(resolvedTheme, "subtle");
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
        {/* P3-5: favorite heart (top-left so it never collides with the
            quantity badge at top-right). Nested Pressable swallows its own
            tap, so toggling a heart never opens the item detail screen. */}
        {onToggleFavorite ? (
          <Pressable
            onPress={onToggleFavorite}
            hitSlop={8}
            style={styles.favBtn}
            accessibilityRole="button"
            accessibilityLabel={isFavorite ? "Remove from favorites" : "Add to favorites"}
          >
            <Ionicons
              name={isFavorite ? "heart" : "heart-outline"}
              size={16}
              color={isFavorite ? "#b3412f" : "#5a4636"}
            />
          </Pressable>
        ) : null}
        {quantity > 0 && (
          <View style={[styles.qtyBadge, { backgroundColor: brand }]}>
            <Text style={styles.qtyText}>{quantity}</Text>
          </View>
        )}
      </View>

      {/* Content */}
      <View style={styles.content}>
        {subtitle ? (
          <Text
            style={[styles.subtitle, { color: tc("muted") }]}
            numberOfLines={1}
            ellipsizeMode="tail"
          >
            {subtitle}
          </Text>
        ) : null}
        <Text
          style={[styles.name, { color: tc("primary") }]}
          numberOfLines={1}
          ellipsizeMode="tail"
        >
          {name}
        </Text>
        {description || preparationTimeMinutes || !isAvailable ? (
          <Text
            style={[styles.desc, { color: tc("muted") }]}
            numberOfLines={2}
            ellipsizeMode="tail"
          >
            {isAvailable
              ? [description, preparationTimeMinutes ? `~${preparationTimeMinutes} min` : ""]
                  .filter(Boolean)
                  .join(" · ")
              : "Out of stock"}
          </Text>
        ) : null}

        {/* Price row — price uses dark primary text (not gold) so it stands
            out from the gold + button. */}
        <View style={styles.priceRow}>
          <Text style={[styles.price, { color: tc("primary") }]}>{formatPrice(price)}</Text>

          {quantity > 0 ? (
            /* Compact stepper */
            <View style={[styles.stepper, { backgroundColor: bgColor(resolvedTheme, "secondary") }]}>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={`Decrease ${name} quantity`}
                onPress={onDecrement}
                style={styles.stepBtn}
                hitSlop={8}
              >
                <Ionicons name="remove" size={14} color={tc("secondary")} />
              </Pressable>
              <Text style={[styles.stepQty, { color: tc("primary") }]}>{quantity}</Text>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={`Increase ${name} quantity`}
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
              accessibilityRole="button"
              accessibilityLabel={`Add ${name} to cart`}
              onPress={onAdd}
              disabled={!isAvailable || isBusy}
              style={[styles.addBtn, { backgroundColor: isAvailable ? brand : bgColor(resolvedTheme, "tertiary") }]}
              hitSlop={8}
            >
              {isBusy ? (
                <ActivityIndicator size="small" color="#302116" />
              ) : (
                <Ionicons
                  name={isAvailable ? "add" : "close"}
                  size={16}
                  color={isAvailable ? "#302116" : tc("muted")}
                />
              )}
            </Pressable>
          )}
        </View>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 16,
    overflow: "hidden",
    backgroundColor: "#fffdf8",
    borderWidth: 1,
    borderColor: "#f0e7d7",
    elevation: 1,
  },
  pressed: {
    opacity: 0.98,
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
    minWidth: 22,
    alignItems: "center",
  },
  favBtn: {
    position: "absolute",
    top: 8,
    left: 8,
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: "rgba(255,253,248,0.92)",
    borderWidth: 1,
    borderColor: "#f0e7d7",
    alignItems: "center",
    justifyContent: "center",
  },
  qtyText: {
    color: "#ffffff",
    fontSize: 12,
    fontWeight: "700",
  },
  content: {
    padding: 11,
  },
  subtitle: {
    fontSize: 11,
    fontWeight: "500",
    lineHeight: 14,
    marginBottom: 2,
  },
  name: {
    fontSize: 14,
    fontWeight: "700",
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
    fontSize: 16,
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
