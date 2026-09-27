/**
 * UniServe — Item Detail Screen
 *
 * Shows full details for a menu item with add-to-cart controls.
 */
import React, { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";

import { useTheme } from "../../../src/contexts/ThemeContext";
import { useCart } from "../../../src/contexts/CartContext";
import { Spinner } from "../../../src/components/ui";
import { textColor, bgColor, borderColor, colors } from "../../../src/theme";
import { getMenuItem } from "../../../src/services/data";
import type { MenuItem, MenuCategory } from "@uniserve/shared-types";

// ── Helpers ──

function formatPrice(paisa: number): string {
  const pkr = paisa / 100;
  return pkr % 1 === 0 ? `PKR ${pkr}` : `PKR ${pkr.toFixed(2)}`;
}

const CATEGORY_EMOJI: Record<MenuCategory, string> = {
  breakfast: "🍳",
  main_course: "🍛",
  side_dish: "🥗",
  dessert: "🍰",
  beverage: "☕",
  snack: "🍿",
  salad: "🥬",
  soup: "🍜",
};

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
  const { selectedCafeteria, addToCart, cartItemCount, cartTotal } = useCart();

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
      <View style={[styles.screen, { backgroundColor: bg("secondary") }]}>
        <Spinner label="Loading item..." />
      </View>
    );
  }

  // Error / not found
  if (error || !item) {
    return (
      <View style={[styles.screen, { backgroundColor: bg("secondary") }]}>
        <View style={styles.errorContainer}>
          <Text style={[styles.errorEmoji]}>😵</Text>
          <Text style={[styles.errorTitle, { color: tc("primary") }]}>
            {error || "Item not found"}
          </Text>
          <TouchableOpacity onPress={() => router.back()} style={styles.backLink}>
            <Text style={[styles.backLinkText, { color: colors.brand[700] }]}>← Go back</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.screen, { backgroundColor: bg("secondary") }]}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* ── Item Image Placeholder ── */}
        <View style={[styles.imagePlaceholder, { backgroundColor: bg("primary") }]}>
          <Text style={styles.imageEmoji}>
            {CATEGORY_EMOJI[item.category] ?? "🍽️"}
          </Text>
        </View>

        {/* ── Item Info ── */}
        <View style={styles.infoSection}>
          {/* Category badge */}
          <View style={[styles.categoryBadge, { backgroundColor: colors.brand[700] + "15" }]}>
            <Text style={[styles.categoryBadgeText, { color: colors.brand[700] }]}>
              {CATEGORY_LABELS[item.category]}
            </Text>
          </View>

          {/* Name */}
          <Text style={[styles.itemName, { color: tc("primary") }]}>{item.name}</Text>

          {/* Price */}
          <Text style={[styles.itemPrice, { color: colors.brand[700] }]}>
            {formatPrice(item.price)}
          </Text>

          {/* Availability */}
          {item.is_available ? (
            <View style={styles.availabilityRow}>
              <View style={[styles.availabilityDot, { backgroundColor: colors.success }]} />
              <Text style={[styles.availabilityText, { color: colors.success }]}>Available</Text>
            </View>
          ) : (
            <View style={styles.availabilityRow}>
              <View style={[styles.availabilityDot, { backgroundColor: colors.error }]} />
              <Text style={[styles.availabilityText, { color: colors.error }]}>Out of stock</Text>
            </View>
          )}

          {/* Description */}
          {item.description ? (
            <View style={[styles.descCard, { backgroundColor: bg("primary"), borderColor: bc("default") }]}>
              <Text style={[styles.descLabel, { color: tc("muted") }]}>Description</Text>
              <Text style={[styles.descText, { color: tc("secondary") }]}>{item.description}</Text>
            </View>
          ) : null}

          {/* Dietary / Allergens */}
          {(item.dietary_info || item.allergens) && (
            <View style={[styles.descCard, { backgroundColor: bg("primary"), borderColor: bc("default") }]}>
              {item.dietary_info ? (
                <View style={styles.infoRow}>
                  <Text style={styles.infoLabel}>🥗 Dietary</Text>
                  <Text style={[styles.infoValue, { color: tc("secondary") }]}>{item.dietary_info}</Text>
                </View>
              ) : null}
              {item.allergens ? (
                <View style={styles.infoRow}>
                  <Text style={styles.infoLabel}>⚠️ Allergens</Text>
                  <Text style={[styles.infoValue, { color: tc("secondary") }]}>{item.allergens}</Text>
                </View>
              ) : null}
            </View>
          )}
        </View>

        {/* Bottom padding for add-to-cart bar */}
        <View style={{ height: 120 }} />
      </ScrollView>

      {/* ── Add to Cart Bar ── */}
      {item.is_available ? (
        <View style={[styles.bottomBar, { backgroundColor: bg("primary"), borderTopColor: bc("default") }]}>
          {/* Quantity Control */}
          <View style={[styles.quantityControl, { borderColor: bc("default") }]}>
            <TouchableOpacity
              style={[styles.qtyButton, { borderColor: bc("default") }]}
              onPress={() => setQuantity((q) => Math.max(1, q - 1))}
              disabled={quantity <= 1}
            >
              <Text style={[styles.qtyButtonText, { color: quantity <= 1 ? tc("muted") : tc("primary") }]}>
                −
              </Text>
            </TouchableOpacity>
            <Text style={[styles.qtyValue, { color: tc("primary") }]}>{quantity}</Text>
            <TouchableOpacity
              style={[styles.qtyButton, { borderColor: bc("default") }]}
              onPress={() => setQuantity((q) => Math.min(10, q + 1))}
              disabled={quantity >= 10}
            >
              <Text style={[styles.qtyButtonText, { color: quantity >= 10 ? tc("muted") : tc("primary") }]}>
                +
              </Text>
            </TouchableOpacity>
          </View>

          {/* Add Button */}
          <TouchableOpacity
            style={[
              styles.addButton,
              { backgroundColor: isAdding ? colors.neutral[400] : colors.brand[700] },
            ]}
            onPress={handleAddToCart}
            disabled={isAdding}
            activeOpacity={0.8}
          >
            {isAdding ? (
              <ActivityIndicator size="small" color="#ffffff" />
            ) : (
              <Text style={styles.addButtonText}>
                Add to cart · {formatPrice(item.price * quantity)}
              </Text>
            )}
          </TouchableOpacity>
        </View>
      ) : null}
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
  imagePlaceholder: {
    height: 220,
    alignItems: "center",
    justifyContent: "center",
  },
  imageEmoji: {
    fontSize: 80,
  },
  infoSection: {
    padding: 20,
  },
  categoryBadge: {
    alignSelf: "flex-start",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
    marginBottom: 10,
  },
  categoryBadgeText: {
    fontSize: 12,
    fontWeight: "600",
  },
  itemName: {
    fontSize: 24,
    fontWeight: "700",
    letterSpacing: -0.3,
    marginBottom: 6,
  },
  itemPrice: {
    fontSize: 22,
    fontWeight: "700",
    marginBottom: 8,
  },
  availabilityRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: 16,
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
  descCard: {
    padding: 14,
    borderRadius: 10,
    borderWidth: 1,
    marginTop: 12,
  },
  descLabel: {
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
    marginBottom: 8,
  },
  infoLabel: {
    fontSize: 13,
    fontWeight: "600",
    marginBottom: 2,
  },
  infoValue: {
    fontSize: 13,
    lineHeight: 18,
  },
  errorContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 32,
  },
  errorEmoji: {
    fontSize: 48,
    marginBottom: 12,
  },
  errorTitle: {
    fontSize: 18,
    fontWeight: "600",
    textAlign: "center",
  },
  backLink: {
    marginTop: 16,
  },
  backLinkText: {
    fontSize: 15,
    fontWeight: "600",
  },

  // Bottom bar
  bottomBar: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 12,
    paddingBottom: 28,
    borderTopWidth: StyleSheet.hairlineWidth,
    gap: 12,
  },
  quantityControl: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 10,
    borderWidth: 1,
    height: 44,
  },
  qtyButton: {
    width: 40,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
    borderRightWidth: StyleSheet.hairlineWidth,
  },
  qtyButtonText: {
    fontSize: 20,
    fontWeight: "600",
  },
  qtyValue: {
    width: 40,
    textAlign: "center",
    fontSize: 16,
    fontWeight: "600",
  },
  addButton: {
    flex: 1,
    height: 44,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  addButtonText: {
    color: "#ffffff",
    fontSize: 15,
    fontWeight: "700",
  },
});
