/**
 * UniServe — Favorites Screen (P3-5)
 *
 * Server-backed list of the user's favorited menu items. The backend
 * favorites API (GET/POST/DELETE /favorites) has existed since Phase 3 —
 * this screen was a static placeholder. FavoritesContext loads the list
 * (user-scoped server-side) and provides an optimistic toggle.
 *
 * - Two-column FoodCard grid matching the home menu layout
 * - Heart on each card removes the favorite (optimistic)
 * - Tapping a card opens item detail (with cafeteria context)
 * - Pull-to-refresh re-fetches from the server
 * - Empty state keeps the original design-spec presentation
 */
import React, { useCallback, useEffect, useState } from "react";
import { View, Text, ScrollView, StyleSheet, RefreshControl, ActivityIndicator, Pressable } from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";

import { useTheme } from "../../../src/contexts/ThemeContext";
import { useFavorites } from "../../../src/contexts/FavoritesContext";
import { FoodCard } from "../../../src/components/ui";
import { textColor, bgColor, borderColor, brandGreen } from "../../../src/theme";
import { getCafeterias } from "../../../src/services/data";

export default function FavoritesScreen() {
  const { resolvedTheme } = useTheme();
  const router = useRouter();
  const { favorites, isFavorite, toggleFavorite, refresh, isLoading } = useFavorites();

  // id → name, so each card can show which cafeteria the item belongs to
  // (favorites can span cafeterias, unlike the Home menu). Best-effort: if the
  // lookup fails the cards simply omit the cafeteria line.
  const [cafeteriaNames, setCafeteriaNames] = useState<Record<string, string>>({});

  const brand = brandGreen(resolvedTheme);
  const tc = textColor(resolvedTheme, "primary");
  const tcMuted = textColor(resolvedTheme, "muted");
  const bg = bgColor(resolvedTheme, "primary");

  useEffect(() => {
    let mounted = true;
    getCafeterias()
      .then((list) => {
        if (!mounted) return;
        const map: Record<string, string> = {};
        for (const c of list) map[c.id] = c.name;
        setCafeteriaNames(map);
      })
      .catch(() => undefined);
    return () => {
      mounted = false;
    };
  }, []);

  const onRefresh = useCallback(async () => {
    await refresh();
  }, [refresh]);

  // Favorites whose menu item was deleted come back without a payload —
  // render only the ones we can show.
  const items = favorites
    .map((fav) => fav.menu_item)
    .filter((item): item is NonNullable<typeof item> => Boolean(item));

  return (
    <SafeAreaView edges={["top"]} style={[styles.screen, { backgroundColor: bg }]}>
      <ScrollView
        contentContainerStyle={styles.list}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={isLoading} onRefresh={onRefresh} colors={[brand]} tintColor={brand} />
        }
      >
        {/* Header */}
        <View style={styles.screenHeader}>
          <Text style={[styles.screenTitle, { color: tc }]}>Favorites</Text>
          <Text style={[styles.screenSubtitle, { color: tcMuted }]}>
            Your saved menu items, ready to reorder
          </Text>
        </View>

        {isLoading && items.length === 0 ? (
          // Loading state — show spinner while fetching
          <View style={styles.emptyContainer}>
            <ActivityIndicator size="large" color={brand} />
            <Text style={[styles.emptyDesc, { color: tcMuted, marginTop: 12 }]}>
              Loading favorites...
            </Text>
          </View>
        ) : items.length === 0 ? (
          // Empty state — original design-spec presentation
          <View style={styles.emptyContainer}>
            <View style={[styles.iconContainer, { backgroundColor: brand + "15" }]}>
              <Ionicons name="heart-outline" size={56} color={brand + "30"} />
            </View>
            <Text style={[styles.emptyTitle, { color: tc }]}>No favorites yet</Text>
            <Text style={[styles.emptyDesc, { color: tcMuted }]}>
              Tap the heart icon on any menu item to save it here for quick reordering.
            </Text>
            <Pressable
              onPress={() => router.push("/(app)/(tabs)")}
              style={[styles.browseButton, { backgroundColor: brand }]}
            >
              <Text style={styles.browseButtonText}>Browse Menu</Text>
            </Pressable>
          </View>
        ) : (
          <View style={styles.gridContainer}>
            {items.map((item) => (
              <View key={item.id} style={styles.gridItem}>
                <FoodCard
                  name={item.name}
                  subtitle={cafeteriaNames[item.cafeteria_id]}
                  description={item.description}
                  price={item.price}
                  imageUri={item.image_url}
                  category={item.category}
                  preparationTimeMinutes={item.preparation_time_minutes}
                  isAvailable={item.is_available}
                  isFavorite={isFavorite(item.id)}
                  onToggleFavorite={() => {
                    // Optimistic removal — the heart disappears immediately;
                    // FavoritesContext reverts if the server rejects it.
                    toggleFavorite(item.id).catch(() => {});
                  }}
                  onPress={() =>
                    router.push(
                      `/item/${item.id}?cafeteriaId=${item.cafeteria_id}`,
                    )
                  }
                />
              </View>
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  list: { paddingBottom: 96 },
  screenHeader: { paddingHorizontal: 20, paddingTop: 20, marginBottom: 8 },
  screenTitle: { fontSize: 28, fontWeight: "700", lineHeight: 34 },
  screenSubtitle: { fontSize: 13, marginTop: 4 },

  // Empty
  emptyContainer: {
    alignItems: "center",
    paddingHorizontal: 40,
    paddingTop: 72,
  },
  iconContainer: {
    width: 96,
    height: 96,
    borderRadius: 48,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16,
  },
  emptyTitle: { fontSize: 18, fontWeight: "600", marginBottom: 8 },
  emptyDesc: { fontSize: 14, textAlign: "center", lineHeight: 20 },
  browseButton: {
    marginTop: 20,
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 24,
  },
  browseButtonText: {
    color: "#fff",
    fontSize: 15,
    fontWeight: "600",
  },

  // Grid — matches home menu layout
  gridContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    paddingHorizontal: 16,
    gap: 10,
    paddingTop: 8,
  },
  gridItem: {
    width: "48.5%",
    flexGrow: 0,
    flexShrink: 0,
  },
});
