/**
 * UniServe — Home Screen (Food-First Browsing Experience)
 *
 * Design spec zones:
 *   Zone 1: Status bar (system)
 *   Zone 2: Header — greeting + notification bell
 *   Zone 2b: Cafeteria badge (tap → bottom sheet selector)
 *   Zone 3: Search bar
 *   Zone 4: Category chips (horizontal scroll, Ionicons, no emojis)
 *   Zone 5: Food grid (2-column, vertical scroll)
 *   Zone 6: Floating cart bar (absolute, bottom: 70)
 *   — Bottom Tab Bar (below cart bar)
 */
import React, { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  RefreshControl,
  Pressable,
} from "react-native";
import { useRouter, useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";

import { useTheme } from "../../../src/contexts/ThemeContext";
import { useCart } from "../../../src/contexts/CartContext";
import { useFavorites } from "../../../src/contexts/FavoritesContext";
import { useNotifications } from "../../../src/contexts/NotificationsContext";
import { FoodCard } from "../../../src/components/ui";
import { SearchBar } from "../../../src/components/ui";
import { CategoryChips, type CategoryKey } from "../../../src/components/ui";
import { CartBar } from "../../../src/components/ui";
import { Toast } from "../../../src/components/ui";
import { EmptyState } from "../../../src/components/ui";
import { BottomSheet, BottomSheetRow } from "../../../src/components/ui/BottomSheet";
import { SkeletonCard } from "../../../src/components/ui";
import { textColor, bgColor, borderColor, brandGreen, functionalColor, colors } from "../../../src/theme";
import { getTodaysMenu, getCafeterias } from "../../../src/services/data";
import type { MenuItem, Cafeteria } from "@uniserve/shared-types";

// ── Helpers ──

const ALL_CATEGORIES: CategoryKey[] = [
  "all",
  "breakfast",
  "main_course",
  "side_dish",
  "dessert",
  "beverage",
  "snack",
  "salad",
  "soup",
];

// ── Toast State ──

interface ToastState {
  visible: boolean;
  message: string;
  type: "success" | "error" | "info";
}

// ── Main Home Screen ──

export default function HomeScreen() {
  const { resolvedTheme } = useTheme();
  const router = useRouter();
  const {
    selectedCafeteria,
    selectCafeteria,
    cart,
    cartItemCount,
    cartTotal,
    addToCart: cartAddToCart,
    updateQuantity: cartUpdateQuantity,
  } = useCart();

  // P3-5: favorite hearts on the menu grid — backed by the server-side
  // favorites API via FavoritesContext (optimistic toggle + reconcile).
  const { isFavorite, toggleFavorite } = useFavorites();

  // Notifications moved out of the tab bar into a header bell. The unread
  // badge reads the shared NotificationsContext (single source of truth) and
  // is refreshed whenever Home regains focus so the count stays current.
  const { unreadCount, refreshUnreadCount } = useNotifications();
  useFocusEffect(
    useCallback(() => {
      refreshUnreadCount();
    }, [refreshUnreadCount]),
  );

  const brand = brandGreen(resolvedTheme);
  const tc = textColor(resolvedTheme, "primary");
  const tcSec = textColor(resolvedTheme, "secondary");
  const tcMuted = textColor(resolvedTheme, "muted");
  const bg = bgColor(resolvedTheme, "primary");
  const bc = borderColor(resolvedTheme, "default");

  // State
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<CategoryKey>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [hasPublishedMenu, setHasPublishedMenu] = useState<boolean | null>(null);
  const [toast, setToast] = useState<ToastState>({ visible: false, message: "", type: "success" });
  const [cafeteriaSheetVisible, setCafeteriaSheetVisible] = useState(false);
  const [cafeterias, setCafeterias] = useState<Cafeteria[]>([]);

  const [busyItemId, setBusyItemId] = useState<string | null>(null);
  const cartItemMap = (cart?.items ?? []).reduce<Record<string, { cartItemId: string; quantity: number }>>(
    (map, item) => {
      map[item.menu_item_id] = { cartItemId: item.id, quantity: item.quantity };
      return map;
    },
    {},
  );

  const isCafeteriaOpen = selectedCafeteria?.operational_status === "open";

  // Load cafeterias for bottom sheet
  useEffect(() => {
    getCafeterias()
      .then((data) => {
        setCafeterias(data);
        // First launch (or a previous auto-select that found nothing): surface
        // the picker straight away so choosing a cafeteria is the first action,
        // rather than leaving the user on an empty menu with no explanation.
        if (data.length > 0 && !selectedCafeteria) {
          setCafeteriaSheetVisible(true);
        }
      })
      .catch(() => setError("Failed to load cafeterias. Pull to retry."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load menu items
  const loadMenu = useCallback(async () => {
    if (!selectedCafeteria) return;
    try {
      setError("");
      const dailyMenu = await getTodaysMenu(selectedCafeteria.id);
      setHasPublishedMenu(dailyMenu !== null);

      if (!dailyMenu) {
        setMenuItems([]);
        return;
      }

      const dailyItems = dailyMenu.items
        .filter((dailyItem) => dailyItem.menu_item)
        .map((dailyItem) => ({
          ...dailyItem.menu_item!,
          price: dailyItem.special_price ?? dailyItem.menu_item!.price,
          is_available: dailyItem.menu_item!.is_available && dailyItem.is_available_today,
        }));
      const normalizedSearch = searchQuery.trim().toLowerCase();
      setMenuItems(
        dailyItems.filter((item) => {
          const matchesCategory = selectedCategory === "all" || item.category === selectedCategory;
          const matchesSearch = !normalizedSearch || item.name.toLowerCase().includes(normalizedSearch);
          return matchesCategory && matchesSearch;
        }),
      );
    } catch {
      setError("Failed to load menu");
    }
  }, [selectedCafeteria, selectedCategory, searchQuery]);

  useEffect(() => {
    loadMenu().finally(() => {
      setIsLoading(false);
      setIsRefreshing(false);
    });
  }, [loadMenu]);

  const onRefresh = useCallback(async () => {
    setIsRefreshing(true);
    // Pull-to-retry must also recover a failed cafeteria load — the empty
    // banner promises "Pull to retry", and loadMenu is a no-op without a
    // selected cafeteria.
    if (cafeterias.length === 0) {
      try {
        setCafeterias(await getCafeterias());
      } catch {
        setError("Failed to load cafeterias. Pull to retry.");
      }
    }
    // P3-15: reset isRefreshing here, in a finally on the fetch itself.
    // Previously the reset lived only in the mount useEffect's finally,
    // which runs when `loadMenu` identity changes — a pull-to-refresh with
    // unchanged deps called loadMenu directly and left isRefreshing stuck
    // true, so the RefreshControl spinner (rendered as a persistent
    // "Refreshing..." banner on Expo web) never dismissed.
    try {
      await loadMenu();
    } finally {
      setIsRefreshing(false);
    }
  }, [loadMenu, cafeterias.length]);

  // Search: switch to "all" when searching
  useEffect(() => {
    if (searchQuery.trim() && selectedCategory !== "all") {
      setSelectedCategory("all");
    }
  }, [searchQuery]);

  // Handle add to cart
  const handleAddToCart = useCallback(
    async (menuItemId: string) => {
      if (!isCafeteriaOpen) return;
      setBusyItemId(menuItemId);
      try {
        await cartAddToCart(menuItemId, 1);
        setToast({ visible: true, message: "Added to cart", type: "success" });
      } catch {
        setToast({ visible: true, message: "Failed to add item", type: "error" });
      } finally {
        setBusyItemId(null);
      }
    },
    [cartAddToCart, isCafeteriaOpen],
  );

  // Handle item press → navigate to detail
  const handleItemPress = useCallback(
    (item: MenuItem) => {
      router.push(`/item/${item.id}`);
    },
    [router],
  );

  // Handle category chip press
  const handleCategoryPress = useCallback((cat: CategoryKey) => {
    setSearchQuery("");
    setSelectedCategory(cat);
  }, []);

  // Handle cafeteria selection
  const handleCafeteriaSelect = useCallback(
    (cafeteria: Cafeteria) => {
      selectCafeteria(cafeteria);
      setCafeteriaSheetVisible(false);
      setMenuItems([]);
      setIsLoading(true);
    },
    [selectCafeteria],
  );

  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: bg }]} edges={["top"]}>
      {/* Toast */}
      <Toast
        visible={toast.visible}
        message={toast.message}
        type={toast.type}
        onDismiss={() => setToast((t) => ({ ...t, visible: false }))}
      />

      {/* ── Zone 2: Header ── */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Text style={[styles.greeting, { color: tc }]}>Uni Cafe Menu</Text>
          {selectedCafeteria ? (
            <Pressable
              onPress={() => setCafeteriaSheetVisible(true)}
              style={styles.cafeteriaInline}
              accessibilityLabel={`Current cafeteria: ${selectedCafeteria.name}. Tap to change.`}
              accessibilityRole="button"
            >
              <Ionicons name="location-outline" size={14} color={brand} />
              <Text style={[styles.cafeteriaInlineName, { color: tcSec }]}> 
                {selectedCafeteria.name}
              </Text>
              {selectedCafeteria.location ? (
                <Text style={[styles.cafeteriaInlineLoc, { color: tcMuted }]}>
                  {" · "}{selectedCafeteria.location}
                </Text>
              ) : null}
              <View style={[styles.statusDot, { backgroundColor: functionalColor(resolvedTheme, isCafeteriaOpen ? "success" : "error") }]} />
              <Ionicons name="chevron-down" size={14} color={tcMuted} />
            </Pressable>
          ) : (
            <Pressable
              onPress={() => setCafeteriaSheetVisible(true)}
              style={styles.cafeteriaInline}
              accessibilityLabel="No cafeteria chosen yet. Tap to choose one."
              accessibilityRole="button"
            >
              <Ionicons name="location-outline" size={14} color={brand} />
              <Text style={[styles.cafeteriaInlineName, { color: tcSec }]}>
                Choose a cafeteria
              </Text>
              <Ionicons name="chevron-down" size={14} color={tcMuted} />
            </Pressable>
          )}
        </View>
        <Pressable
          style={styles.headerIcon}
          hitSlop={8}
          onPress={() => router.push("/(tabs)/notifications")}
          accessibilityRole="button"
          accessibilityLabel={
            unreadCount > 0
              ? `Notifications, ${unreadCount} unread`
              : "Notifications"
          }
        >
          <Ionicons name="notifications-outline" size={24} color={brand} />
          {unreadCount > 0 && (
            <View style={styles.bellBadge}>
              <Text style={styles.bellBadgeText}>
                {unreadCount > 9 ? "9+" : unreadCount}
              </Text>
            </View>
          )}
        </Pressable>
      </View>

      {/* ── Zone 3: Search (only once a cafeteria is chosen) ── */}
      {selectedCafeteria && (
        <View style={{ marginTop: 12 }}>
          <SearchBar
            value={searchQuery}
            onChangeText={setSearchQuery}
            placeholder="Search products..."
          />
        </View>
      )}

      {/* ── Zone 4: Category Chips (only once a cafeteria is chosen) ── */}
      {selectedCafeteria && (
        <View style={{ marginTop: 8 }}>
          <CategoryChips
            categories={ALL_CATEGORIES}
            selected={selectedCategory}
            onSelect={handleCategoryPress}
          />
        </View>
      )}

      {/* ── Loading State ── */}
      {isLoading && (
        <View style={styles.loadingGrid}>
          {[1, 2, 3, 4].map((i) => (
            <View key={i} style={styles.gridItem}>
              <SkeletonCard />
            </View>
          ))}
        </View>
      )}

      {/* ── Error Banner ── */}
      {error ? (
        <View style={[styles.errorBanner, { backgroundColor: bg, borderColor: bc }]}>
          <View style={[styles.errorIcon, { backgroundColor: colors.gold[100] }]}>
            <Ionicons name="cafe-outline" size={21} color={colors.brand[800]} />
          </View>
          <View style={styles.errorCopy}>
            <Text style={[styles.errorTitle, { color: tc }]}>The menu is taking a break</Text>
            <Text style={[styles.errorText, { color: tcMuted }]}>{error}. Try again in a moment.</Text>
          </View>
          <Pressable onPress={onRefresh} style={styles.retryButton}>
            <Ionicons name="refresh" size={17} color={brand} />
          </Pressable>
        </View>
      ) : null}

      {/* ── Closed Cafeteria Warning ── */}
      {!isCafeteriaOpen && selectedCafeteria && !isLoading ? (
        <View style={[styles.warningBanner, { backgroundColor: functionalColor(resolvedTheme, "warning") + "10", borderColor: functionalColor(resolvedTheme, "warning") + "30" }]}>
          <Ionicons name="lock-closed" size={16} color={functionalColor(resolvedTheme, "warning")} />
          <Text style={[styles.warningText, { color: functionalColor(resolvedTheme, "warning"), flex: 1, marginLeft: 8 }]}>
            {selectedCafeteria.operational_status === "closing_soon"
              ? "Closing soon — ordering may be limited"
              : selectedCafeteria.operational_status === "maintenance"
                ? "Cafeteria is temporarily paused"
              : "Cafeteria is currently closed"}
          </Text>
        </View>
      ) : null}

      {/* ── Empty States ── */}
      {!isLoading && hasPublishedMenu === false && (
        <EmptyState
          icon="document-text-outline"
          title="Menu not published yet"
          description="Today's menu hasn't been published. Check back later!"
        />
      )}

      {!isLoading && menuItems.length === 0 && hasPublishedMenu !== false && !error && (
        <EmptyState
          icon={searchQuery ? "search-outline" : "restaurant-outline"}
          title={
            searchQuery
              ? "No items found"
              : selectedCafeteria
                ? "Today's menu is being prepared"
                : "Find your campus cafe"
          }
          description={
            searchQuery
              ? `No items match "${searchQuery}"`
              : selectedCafeteria
                ? "Fresh campus favorites will appear here once today's menu is published."
                : "Choose a campus cafe to explore meals, snacks, and drinks."
          }
        />
      )}

      {/* ── First-launch / no-cafeteria call to action ── */}
      {!isLoading && !selectedCafeteria && !error && (
        <View style={styles.chooseCafeteriaCta}>
          <Pressable
            onPress={() => setCafeteriaSheetVisible(true)}
            style={({ pressed }) => [
              styles.chooseCafeteriaBtn,
              { backgroundColor: brand },
              pressed && { opacity: 0.85 },
            ]}
            accessibilityRole="button"
            accessibilityLabel="Choose a cafeteria"
          >
            <Ionicons name="restaurant-outline" size={18} color="#ffffff" />
            <Text style={styles.chooseCafeteriaText}>Choose a cafeteria</Text>
          </Pressable>
        </View>
      )}

      {/* ── Zone 5: Food Grid ── */}
      {!isLoading && menuItems.length > 0 && (
        <ScrollView
          style={styles.scrollContent}
          contentContainerStyle={[
            styles.scrollContainer,
            { paddingBottom: cartItemCount > 0 ? 140 : 100 },
          ]}
          refreshControl={
            <RefreshControl
              refreshing={isRefreshing}
              onRefresh={onRefresh}
              colors={[brand]}
              tintColor={brand}
            />
          }
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.gridContainer}>
            {menuItems.map((item) => (
              <View key={item.id} style={styles.gridItem}>
                <FoodCard
                  name={item.name}
                  description={item.description}
                  price={item.price}
                  imageUri={item.image_url}
                  category={item.category}
                  preparationTimeMinutes={item.preparation_time_minutes}
                  isAvailable={item.is_available}
                  isBusy={busyItemId === item.id}
                  quantity={cartItemMap[item.id]?.quantity ?? 0}
                  isFavorite={isFavorite(item.id)}
                  onToggleFavorite={() => {
                    // Optimistic UI lives in FavoritesContext; errors revert there.
                    toggleFavorite(item.id).catch(() => {});
                  }}
                  onPress={() => handleItemPress(item)}
                  onAdd={() => handleAddToCart(item.id)}
                  onIncrement={() => handleAddToCart(item.id)}
                  onDecrement={() => {
                    const cartItem = cartItemMap[item.id];
                    if (cartItem) {
                      cartUpdateQuantity(cartItem.cartItemId, cartItem.quantity - 1);
                    }
                  }}
                />
              </View>
            ))}
          </View>
        </ScrollView>
      )}

      {/* ── Zone 6: Floating Cart Bar ── */}
      {cartItemCount > 0 && (
        <CartBar
          itemCount={cartItemCount}
          total={cartTotal}
          onPress={() => router.push("/(tabs)/cart")}
        />
      )}

      {/* ── Cafeteria Bottom Sheet ── */}
      <BottomSheet
        visible={cafeteriaSheetVisible}
        onClose={() => setCafeteriaSheetVisible(false)}
        title="Select Cafeteria"
      >
        {cafeterias.map((caf) => (
          <BottomSheetRow
            key={caf.id}
            label={caf.name}
            subtitle={caf.location ?? undefined}
            icon="restaurant-outline"
            selected={caf.id === selectedCafeteria?.id}
            onPress={() => handleCafeteriaSelect(caf)}
          />
        ))}
        {cafeterias.length === 0 && (
          <View style={styles.emptySheet}>
            <Text style={{ color: tcMuted, textAlign: "center", paddingVertical: 20 }}>
              No cafeterias available
            </Text>
          </View>
        )}
      </BottomSheet>
    </SafeAreaView>
  );
}

// ── Styles ──

const styles = StyleSheet.create({
  screen: {
    flex: 1,
  },
  scrollContent: {
    flex: 1,
  },
  scrollContainer: {
    paddingTop: 4,
  },

  // Header
  header: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    paddingHorizontal: 20,
    paddingTop: 4,
    paddingBottom: 4,
  },
  headerLeft: {
    flex: 1,
  },
  greeting: { fontSize: 27, fontWeight: "800", lineHeight: 32, letterSpacing: -0.7 },
  cafeteriaInline: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 7,
  },
  cafeteriaInlineName: {
    fontSize: 14,
    fontWeight: "600",
  },
  cafeteriaInlineLoc: {
    fontSize: 14,
    fontWeight: "400",
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginLeft: 7,
    marginRight: 2,
  },
  headerIcon: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
  },
  chooseCafeteriaCta: {
    alignItems: "center",
    marginTop: 20,
    paddingHorizontal: 32,
  },
  chooseCafeteriaBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    minHeight: 48,
    paddingHorizontal: 24,
    borderRadius: 24,
    alignSelf: "stretch",
  },
  chooseCafeteriaText: {
    color: "#ffffff",
    fontSize: 15,
    fontWeight: "600",
  },
  bellBadge: {
    position: "absolute",
    top: 4,
    right: 2,
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    paddingHorizontal: 4,
    backgroundColor: colors.error,
    alignItems: "center",
    justifyContent: "center",
  },
  bellBadgeText: {
    color: "#ffffff",
    fontSize: 10,
    fontWeight: "700",
  },

  // Loading
  loadingGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    paddingHorizontal: 20,
    gap: 12,
    paddingTop: 16,
  },

  // Error
  errorBanner: {
    flexDirection: "row",
    alignItems: "center",
    padding: 12,
    borderRadius: 14,
    borderWidth: 1,
    marginHorizontal: 20,
    marginTop: 12,
  },
  errorIcon: { width: 40, height: 40, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  errorCopy: { flex: 1, marginLeft: 10, gap: 3 },
  errorTitle: { fontSize: 13, fontWeight: "700" },
  errorText: {
    fontSize: 11,
    lineHeight: 15,
  },
  retryButton: { width: 36, height: 36, borderRadius: 18, alignItems: "center", justifyContent: "center", backgroundColor: colors.gold[50] },

  // Warning
  warningBanner: {
    flexDirection: "row",
    alignItems: "center",
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    marginHorizontal: 20,
    marginTop: 12,
  },
  warningText: {
    fontSize: 13,
    fontWeight: "500",
  },

  // Grid
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

  // Bottom sheet
  emptySheet: {
    alignItems: "center",
    paddingVertical: 20,
  },
});
