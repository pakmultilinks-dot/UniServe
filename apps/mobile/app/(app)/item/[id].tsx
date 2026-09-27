/**
 * UniServe — Item Detail Screen
 *
 * Design spec:
 * - Full-width image with borderRadius 16-20
 * - Back button (absolute top-left, 44x44 touch target)
 * - Favorite icon (absolute top-right)
 * - Category badge (brandGreen+15% opacity bg, brandGreen text, 12px/600)
 * - Name 24px/700, Price 20px/700, availability dot + text
 * - Prep time with clock-outline Ionicon
 * - Description with uppercase label
 * - Dietary/Allergens section
 * - Bottom bar: QuantityStepper (borderRadius 10, borderWidth 1, height 48)
 *   + "Add to Cart" button (flex:1, height 48, borderRadius 10, brandGreen bg)
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
import { SafeAreaView } from "react-native-safe-area-context";

import { useTheme } from "../../../src/contexts/ThemeContext";
import { useCart } from "../../../src/contexts/CartContext";
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
  const tc = textColor(resolvedTheme, "primary");
  const tcSec = textColor(resolvedTheme, "secondary");
  const tcMuted = textColor(resolvedTheme, "muted");
  const bg = bgColor(resolvedTheme, "primary");
  const bgSec = bgColor(resolvedTheme, "secondary");
  const bc = borderColor(resolvedTheme, "default");

  const [item, setItem] = useState<MenuItem | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAdding, setIsAdding] = useState(false);
  const [quantity, setQuantity] = useState(1);
  const [error, setError] = useState("");
  const [isFavorite, setIsFavorite] = useState(false);

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
      <View style={[styles.screen, { backgroundColor: bg }]}>
        <View style={styles.loadingCenter}>
          <ActivityIndicator size="large" color={brand} />
        </View>
      </View>
    );
  }

  // Error / not found
  if (error || !item) {
    return (
      <View style={[styles.screen, { backgroundColor: bg }]}>
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle-outline" size={48} color={functionalColor(resolvedTheme, "error")} />
          <Text style={[styles.errorTitle, { color: tc }]}>
            {error || "Item not found"}
          </Text>
          <Pressable onPress={() => router.back()} style={styles.backLink}>
            <Text style={[styles.backLinkText, { color: brand }]}>Go back</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.screen, { backgroundColor: bg }]}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* ── Full-width Hero Image ── */}
        <View>
          <FoodImage
            uri={item.image_url}
            category={item.category}
            style={styles.heroImage}
            borderRadius={0}
          />

          {/* Back button overlay */}
          <SafeAreaView style={styles.backOverlay} edges={["top"]}>
            <Pressable
              style={[styles.circleBtn, { backgroundColor: bg + "CC" }]}
              onPress={() => router.back()}
              hitSlop={12}
            >
              <Ionicons name="chevron-back" size={22} color={tc} />
            </Pressable>
          </SafeAreaView>

          {/* Favorite button overlay */}
          <Pressable
            style={[styles.favBtn, { backgroundColor: bg + "CC" }]}
            onPress={() => setIsFavorite(!isFavorite)}
            hitSlop={12}
          >
            <Ionicons
              name={isFavorite ? "heart" : "heart-outline"}
              size={20}
              color={isFavorite ? functionalColor(resolvedTheme, "error") : tc}
            />
          </Pressable>
        </View>

        {/* ── Content ── */}
        <View style={styles.content}>
          {/* Category badge */}
          <View style={[styles.categoryBadge, { backgroundColor: brand + "15" }]}>
            <Text style={[styles.categoryBadgeText, { color: brand }]}>
              {CATEGORY_LABELS[item.category]}
            </Text>
          </View>

          {/* Name */}
          <Text style={[styles.itemName, { color: tc }]}>{item.name}</Text>

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
              {item.is_available ? "Available now" : "Out of stock"}
            </Text>
          </View>

          {/* Prep time */}
          {item.preparation_time_minutes && (
            <View style={styles.infoRow}>
              <Ionicons name="time-outline" size={16} color={tcMuted} />
              <Text style={[styles.infoTextMuted, { color: tcMuted }]}>
                ~{item.preparation_time_minutes} min preparation
              </Text>
            </View>
          )}

          {/* Divider */}
          <View style={[styles.divider, { backgroundColor: bc }]} />

          {/* Description */}
          {item.description ? (
            <View style={styles.section}>
              <Text style={[styles.sectionLabel, { color: tcMuted }]}>DESCRIPTION</Text>
              <Text style={[styles.descText, { color: tcSec }]}>{item.description}</Text>
            </View>
          ) : null}

          {/* Dietary / Allergens */}
          {item.dietary_info && (
            <View style={[styles.infoTag, { backgroundColor: functionalColor(resolvedTheme, "success") + "10" }]}>
              <Ionicons name="leaf-outline" size={16} color={functionalColor(resolvedTheme, "success")} />
              <Text style={[styles.tagText, { color: functionalColor(resolvedTheme, "success") }]}>{item.dietary_info}</Text>
            </View>
          )}

          {item.allergens && (
            <View style={[styles.infoTag, { backgroundColor: functionalColor(resolvedTheme, "warning") + "10" }]}>
              <Ionicons name="warning-outline" size={16} color={functionalColor(resolvedTheme, "warning")} />
              <Text style={[styles.tagText, { color: functionalColor(resolvedTheme, "warning") }]}>{item.allergens}</Text>
            </View>
          )}
        </View>

        {/* Bottom padding for bar */}
        <View style={{ height: 120 }} />
      </ScrollView>

      {/* ── Bottom Bar ── */}
      {item.is_available && (
        <SafeAreaView edges={["bottom"]} style={{ backgroundColor: bg }}>
          <View style={[styles.bottomBar, { backgroundColor: bg, borderTopColor: bc }]}>
            {/* Quantity Control */}
            <View style={[styles.quantityControl, { borderColor: bc, backgroundColor: bgSec }]}>
              <Pressable
                style={styles.qtyButton}
                onPress={() => setQuantity((q) => Math.max(1, q - 1))}
                disabled={quantity <= 1}
                hitSlop={8}
              >
                <Ionicons
                  name={quantity <= 1 ? "remove-circle-outline" : "remove-circle"}
                  size={22}
                  color={quantity <= 1 ? tcMuted : brand}
                />
              </Pressable>
              <Text style={[styles.qtyValue, { color: tc }]}>{quantity}</Text>
              <Pressable
                style={styles.qtyButton}
                onPress={() => setQuantity((q) => Math.min(10, q + 1))}
                disabled={quantity >= 10}
                hitSlop={8}
              >
                <Ionicons
                  name={quantity >= 10 ? "add-circle-outline" : "add-circle"}
                  size={22}
                  color={quantity >= 10 ? tcMuted : brand}
                />
              </Pressable>
            </View>

            {/* Add Button */}
            <Pressable
              style={[styles.addButton, { backgroundColor: isAdding ? tcMuted : brand }]}
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
        </SafeAreaView>
      )}
    </View>
  );
}

// ── Styles ──

const styles = StyleSheet.create({
  screen: {
    flex: 1,
  },
  loadingCenter: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  scrollContent: {
    paddingBottom: 32,
  },
  heroImage: {
    width: "100%",
    aspectRatio: 3 / 2,
  },

  // Overlays
  backOverlay: {
    position: "absolute",
    top: 8,
    left: 12,
  },
  circleBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
  },
  favBtn: {
    position: "absolute",
    top: 56,
    right: 16,
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
  },

  // Content
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
  infoRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: 8,
  },
  infoTextMuted: {
    fontSize: 13,
  },
  divider: {
    height: StyleSheet.hairlineWidth,
    marginVertical: 16,
  },
  section: {
    marginBottom: 12,
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
    lineHeight: 22,
  },
  infoTag: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    padding: 10,
    borderRadius: 8,
    marginTop: 8,
  },
  tagText: {
    fontSize: 13,
    fontWeight: "500",
    flex: 1,
  },

  // Error
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
    paddingHorizontal: 16,
    paddingVertical: 12,
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
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  qtyValue: {
    width: 40,
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
