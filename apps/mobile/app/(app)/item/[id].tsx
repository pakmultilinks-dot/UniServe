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
import { useFavorites } from "../../../src/contexts/FavoritesContext";
import FoodImage from "../../../src/components/FoodImage";
import { textColor, bgColor, borderColor, brandGreen, functionalColor } from "../../../src/theme";
import { getMenuItem, getTodaysMenu, getCafeterias } from "../../../src/services/data";
import { ApiClientError } from "../../../src/services/api";
import type { MenuItem, MenuCategory } from "@uniserve/shared-types";

// ── Helpers ──

function formatPrice(paisa: number): string {
  return `PKR ${Math.round(paisa / 100)}`;
}

/* Phase 56 — dietary_info/allergens are JSON array strings on the backend
   (e.g. '["vegetarian","gluten_free"]'). Render humanized labels, with a
   fallback to the raw string for legacy/unparseable values. */
function formatTags(raw?: string | null): string | null {
  if (!raw || !raw.trim()) return null;
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      const labels = parsed
        .filter((t): t is string => typeof t === "string")
        .map((t) => t.replace(/_/g, " "));
      return labels.length > 0 ? labels.join(", ") : null;
    }
  } catch {
    /* not JSON — fall through to raw display */
  }
  return raw;
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
  // P3-5: `cafeteriaId` is an optional route param passed by the favorites
  // tab — a favorite may reference an item in a different cafeteria than the
  // currently selected one, so the param takes precedence when provided.
  const { id, cafeteriaId } = useLocalSearchParams<{ id: string; cafeteriaId?: string }>();
  const { resolvedTheme } = useTheme();
  const router = useRouter();
  const { selectedCafeteria, selectCafeteria, addToCart } = useCart();

  const effectiveCafeteriaId = cafeteriaId ?? selectedCafeteria?.id ?? null;

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
  // D6 (Phase 8): add-to-cart failures must NOT replace the whole screen —
  // they render inline above the bottom bar so the user keeps context.
  const [addError, setAddError] = useState("");

  // P3-5: favorite state is server-backed (FavoritesContext) — the previous
  // local useState never persisted and reset on every navigation.
  const { isFavorite: isFavoriteItem, toggleFavorite } = useFavorites();
  const isFavorite = item ? isFavoriteItem(item.id) : false;

  const loadItem = useCallback(async () => {
    if (!id || !effectiveCafeteriaId) return;
    setIsLoading(true);
    setError("");
    try {
      const data = await getMenuItem(effectiveCafeteriaId, id);
      const dailyMenu = await getTodaysMenu(effectiveCafeteriaId);
      const dailyItem = dailyMenu?.items.find((entry) => entry.menu_item_id === data.id);
      setItem(
        dailyItem
          ? {
              ...data,
              price: dailyItem.special_price ?? data.price,
              is_available: data.is_available && dailyItem.is_available_today,
            }
          : data,
      );
    } catch {
      setError("Failed to load item details");
    } finally {
      setIsLoading(false);
    }
  }, [id, effectiveCafeteriaId]);

  useEffect(() => {
    loadItem();
  }, [loadItem]);

  // P3-5: when arriving from favorites the route may reference another
  // cafeteria's item — align the cart's selected cafeteria so Add to Cart
  // targets the right one (cart ops resolve through selectedCafeteria).
  useEffect(() => {
    if (!item || !selectedCafeteria || item.cafeteria_id === selectedCafeteria.id) return;
    let cancelled = false;
    (async () => {
      try {
        const cafeterias = await getCafeterias();
        const match = cafeterias.find((c) => c.id === item.cafeteria_id);
        if (match && !cancelled) selectCafeteria(match);
      } catch {
        // Non-fatal — item still displays; add-to-cart may no-op until the
        // user returns to the home menu for this cafeteria.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [item, selectedCafeteria, selectCafeteria]);

  const handleAddToCart = useCallback(async () => {
    if (!item || !selectedCafeteria) return;
    setIsAdding(true);
    setAddError("");
    try {
      await addToCart(item.id, quantity);
      router.back();
    } catch (err) {
      // D6 (Phase 8): the menu API's is_available flag is the staff toggle,
      // not live stock — inventory is only checked at add-to-cart time.
      // Show the server's real reason inline and, when the failure is a
      // stock/unavailability rejection, reflect it in the availability row
      // instead of pretending the item is orderable.
      const message =
        err instanceof ApiClientError ? err.message : "Failed to add to cart";
      setAddError(message);
      if (
        err instanceof ApiClientError &&
        err.status === 400 &&
        /unavailable|inventory/i.test(message)
      ) {
        setItem((prev) => (prev ? { ...prev, is_available: false } : prev));
        setQuantity(1);
      }
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
          {error && (
            <Pressable onPress={loadItem} style={styles.backLink}>
              <Text style={[styles.backLinkText, { color: brand }]}>Try again</Text>
            </Pressable>
          )}
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

          {/* Overlay controls — one safe-area-aware row so both buttons
              clear the status bar/notch on every device (the old fixed
              top:56 favorite button collided with tall status bars). */}
          <SafeAreaView style={styles.overlayBar} edges={["top"]}>
            <Pressable
              style={[styles.circleBtn, { backgroundColor: bg + "CC" }]}
              onPress={() => router.back()}
              hitSlop={12}
              accessibilityRole="button"
              accessibilityLabel="Go back"
            >
              <Ionicons name="chevron-back" size={22} color={tc} />
            </Pressable>

            <Pressable
              style={[styles.circleBtn, { backgroundColor: bg + "CC" }]}
            onPress={() => {
              // Optimistic heart via FavoritesContext; server rejection reverts.
              toggleFavorite(item.id).catch(() => {});
            }}
            hitSlop={12}
            accessibilityRole="button"
            accessibilityLabel={isFavorite ? "Remove from favorites" : "Add to favorites"}
          >
            <Ionicons
              name={isFavorite ? "heart" : "heart-outline"}
              size={20}
              color={isFavorite ? functionalColor(resolvedTheme, "error") : tc}
            />
            </Pressable>
          </SafeAreaView>
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

          {/* Dietary / Allergens — Phase 56: JSON arrays → humanized labels */}
          {formatTags(item.dietary_info) && (
            <View style={[styles.infoTag, { backgroundColor: functionalColor(resolvedTheme, "success") + "10" }]}>
              <Ionicons name="leaf-outline" size={16} color={functionalColor(resolvedTheme, "success")} />
              <Text style={[styles.tagText, { color: functionalColor(resolvedTheme, "success") }]}>{formatTags(item.dietary_info)}</Text>
            </View>
          )}

          {formatTags(item.allergens) && (
            <View style={[styles.infoTag, { backgroundColor: functionalColor(resolvedTheme, "warning") + "10" }]}>
              <Ionicons name="warning-outline" size={16} color={functionalColor(resolvedTheme, "warning")} />
              <Text style={[styles.tagText, { color: functionalColor(resolvedTheme, "warning") }]}>{formatTags(item.allergens)}</Text>
            </View>
          )}
        </View>

        {/* Bottom padding for bar */}
        <View style={{ height: 120 }} />
      </ScrollView>

      {/* D6: inline add-to-cart error — keeps the item detail visible instead
          of replacing it with a full-screen failure. */}
      {addError ? (
        <View style={[styles.addErrorBar, { backgroundColor: functionalColor(resolvedTheme, "error") + "12" }]}>
          <Ionicons name="alert-circle-outline" size={16} color={functionalColor(resolvedTheme, "error")} />
          <Text style={[styles.addErrorText, { color: functionalColor(resolvedTheme, "error") }]}>{addError}</Text>
        </View>
      ) : null}

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
  overlayBar: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    paddingHorizontal: 12,
    paddingTop: 8,
  },
  circleBtn: {
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
  // D6: inline add-to-cart error above the bottom bar
  addErrorBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginHorizontal: 16,
    marginBottom: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 10,
  },
  addErrorText: {
    flex: 1,
    fontSize: 13,
    fontWeight: "500",
  },
});
