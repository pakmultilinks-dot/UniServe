/**
 * UniServe — Item Detail Screen
 *
 * Design spec:
 * - Full-width image with aspectRatio 3/2
 * - Category badge (brandGreen+15% opacity bg, brandGreen text, 12px/600)
 * - Name 24px/700, Price 20px/700, availability dot + text
 * - Description with uppercase label
 * - Dietary/Allergens section
 * - Bottom bar: quantity control (borderRadius 10, borderWidth 1, height 48)
 *   + "Add to Cart" button (flex:1, height 48, borderRadius 10, brandGreen bg)
 * - Prep time with clock icon
 */
import React, { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  Pressable,
  ActivityIndicator,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

import { useTheme } from "../../../src/contexts/ThemeContext";
import { useCart } from "../../../src/contexts/CartContext";
import { Spinner } from "../../../src/components/ui";
import FoodImage from "../../../src/components/FoodImage";
import { textColor, bgColor, borderColor, brandGreen, functionalColor } from "../../../src/theme";
import { getMenuItem } from "../../../src/services/data";
import type { MenuItem, MenuCategory } from "@uniserve/shared-types";

// ── Helpers ──

function formatPrice(paisa: number): string {
  return `PKR ${Math.round(paisa / 100)}`;
}

const CATEGORY_LABELS: Record<MenuCategory, string> = {
  breakfast: "Breakfast",
  main_course: "Main Course",
  side_dish: "Side Dish",
  dessert: "Dessert",
  beverage: "Beverage",
  snack: "Snack",
  salad: "Salad",
  soup: "Soup",
};

// ── Screen ──

export default function ItemDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { resolvedTheme } = useTheme();
  const router = useRouter();
  const { selectedCafeteria, addToCart } = useCart();

  const brand = brandGreen(resolvedTheme);
  const tc = (v: "primary" | "secondary" | "muted") => textColor(resolvedTheme, v);
  const bg = (v: "primary" | "secondary" | "tertiary") => bgColor(resolvedTheme, v);
  const bc = (v: "default" | "subtle") => borderColor(resolvedTheme, v);

  const [item, setItem] = useState<MenuItem | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAdding, setIsAdding] = useState(false);
  const [quantity, setQuantity] = useState(1);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id || !selectedCafeteria) return;
    (async () => {
      try {
        const data = await getMenuItem(selectedCafeteria.id, id);
        setItem(data);
      } catch {
        setError("Failed to load item details");
      } finally {
        setIsLoading(false);
      }
    })();
  }, [id, selectedCafeteria]);

  const handleAddToCart = useCallback(async () => {
    if (!item || !selectedCafeteria) return;
    setIsAdding(true);
    try {
      await addToCart(item.id, quantity);
      router.back();
    } catch {
      setError("Failed to add to cart");
    } finally {
      setIsAdding(false);
    }
  }, [item, selectedCafeteria, quantity, addToCart, router]);

  // Loading
  if (isLoading) {
    return (
      <View style={[styles.screen, { backgroundColor: bg("primary") }]}>
        <Spinner label="Loading item..." />
      </View>
    );
  }

  // Error / not found
  if (error || !item) {
    return (
      <View style={[styles.screen, { backgroundColor: bg("primary") }]}>
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle" size={48} color={functionalColor(resolvedTheme, "error")} />
          <Text style={[styles.errorTitle, { color: tc("primary") }]}>
            {error || "Item not found"}
          </Text>
          <Pressable onPress={() => router.back()} style={styles.backLink}>
            <Text style={[styles.backLinkText, { color: brand }]}>← Go back</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.screen, { backgroundColor: bg("primary") }]}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* ── Full-width Image ── */}
        <FoodImage
          uri={item.image_url}
          category={item.category}
          style={styles.heroImage}
          borderRadius={0}
        />

        {/* ── Content ── */}
        <View style={styles.content}>
          {/* Category badge */}
          <View style={[styles.categoryBadge, { backgroundColor: brand + "15" }]}>
            <Text style={[styles.categoryBadgeText, { color: brand }]}>
              {CATEGORY_LABELS[item.category]}
            </Text>
          </View>

          {/* Name */}
          <Text style={[styles.itemName, { color: tc("primary") }]}>{item.name}</Text>

          {/* Price */}
          <Text style={[styles.itemPrice, { color: brand }]}>
            {formatPrice(item.price)}
          </Text>

          {/* Availability */}
          <View style={styles.availabilityRow}>
            <View
              style={[
                styles.availabilityDot,
                { backgroundColor: functionalColor(resolvedTheme, item.is_available ? "success" : "error") },
              ]}
            />
            <Text
              style={[
                styles.availabilityText,
                { color: functionalColor(resolvedTheme, item.is_available ? "success" : "error") },
              ]}
            >
              {item.is_available ? "Available" : "Out of stock"}
            </Text>
          </View>

          {/* Description */}
          {item.description ? (
            <View style={styles.section}>
              <Text style={[styles.sectionLabel, { color: tc("muted") }]}>DESCRIPTION</Text>
              <Text style={[styles.descText, { color: tc("secondary") }]}>{item.description}</Text>
            </View>
          ) : null}

          {/* Dietary / Allergens */}
          {item.dietary_info ? (
            <View style={styles.infoRow}>
              <Ionicons name="leaf-outline" size={18} color={functionalColor(resolvedTheme, "success")} />
              <Text style={[styles.infoText, { color: tc("secondary") }]}>{item.dietary_info}</Text>
            </View>
          ) : null}

          {item.allergens ? (
            <View style={styles.infoRow}>
              <Ionicons name="warning-outline" size={18} color={functionalColor(resolvedTheme, "warning")} />
              <Text style={[styles.infoText, { color: tc("secondary") }]}>{item.allergens}</Text>
            </View>
          ) : null}
        </View>

        {/* Bottom padding for bar */}
        <View style={{ height: 120 }} />
      </ScrollView>

      {/* ── Bottom Bar ── */}
      {item.is_available && (
        <View style={[styles.bottomBar, { backgroundColor: bg("primary"), borderTopColor: bc("default") }]}>
          {/* Quantity Control */}
          <View style={[styles.quantityControl, { borderColor: bc("default") }]}>
            <Pressable
              style={styles.qtyButton}
              onPress={() => setQuantity((q) => Math.max(1, q - 1))}
              disabled={quantity <= 1}
            >
              <Ionicons
                name="remove"
                size={16}
                color={quantity <= 1 ? tc("muted") : tc("secondary")}
                style={{ opacity: quantity <= 1 ? 0.3 : 1 }}
              />
            </Pressable>
            <Text style={[styles.qtyValue, { color: tc("primary") }]}>{quantity}</Text>
            <Pressable
              style={styles.qtyButton}
              onPress={() => setQuantity((q) => Math.min(10, q + 1))}
              disabled={quantity >= 10}
            >
              <Ionicons
                name="add"
                size={16}
                color={quantity >= 10 ? tc("muted") : tc("secondary")}
                style={{ opacity: quantity >= 10 ? 0.3 : 1 }}
              />
            </Pressable>
          </View>

          {/* Add Button */}
          <Pressable
            style={[styles.addButton, { backgroundColor: isAdding ? tc("muted") : brand }]}
            onPress={handleAddToCart}
            disabled={isAdding}
          >
            {isAdding ? (
              <ActivityIndicator size="small" color="#ffffff" />
            ) : (
              <Text style={styles.addButtonText}>
                Add · {formatPrice(item.price * quantity)}
              </Text>
            )}
          </Pressable>
        </View>
      )}
    </View>
  );
}

// ── Styles ──

const styles = StyleSheet.create({
  screen: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 32,
  },
  heroImage: {
    width: "100%",
    aspectRatio: 3 / 2,
  },
  content: {
    padding: 20,
  },
  categoryBadge: {
    alignSelf: "flex-start",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
  },
  categoryBadgeText: {
    fontSize: 12,
    fontWeight: "600",
  },
  itemName: {
    fontSize: 24,
    fontWeight: "700",
    letterSpacing: -0.3,
    marginTop: 12,
  },
  itemPrice: {
    fontSize: 20,
    fontWeight: "700",
    marginTop: 4,
  },
  availabilityRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: 8,
  },
  availabilityDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  availabilityText: {
    fontSize: 13,
    fontWeight: "600",
  },
  section: {
    marginTop: 16,
  },
  sectionLabel: {
    fontSize: 12,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  descText: {
    fontSize: 14,
    lineHeight: 20,
  },
  infoRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: 8,
  },
  infoText: {
    fontSize: 14,
    fontWeight: "400",
  },
  errorContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 32,
    gap: 12,
  },
  errorTitle: {
    fontSize: 18,
    fontWeight: "600",
    textAlign: "center",
  },
  backLink: {
    marginTop: 8,
  },
  backLinkText: {
    fontSize: 15,
    fontWeight: "600",
  },
  // Bottom bar
  bottomBar: {
    flexDirection: "row",
    alignItems: "center",
    padding: 16,
    paddingBottom: 28,
    borderTopWidth: StyleSheet.hairlineWidth,
    gap: 12,
  },
  quantityControl: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 10,
    borderWidth: 1,
    height: 48,
  },
  qtyButton: {
    width: 48,
    height: 48,
    alignItems: "center",
    justifyContent: "center",
  },
  qtyValue: {
    width: 48,
    textAlign: "center",
    fontSize: 16,
    fontWeight: "600",
  },
  addButton: {
    flex: 1,
    height: 48,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  addButtonText: {
    color: "#ffffff",
    fontSize: 15,
    fontWeight: "600",
  },
});
