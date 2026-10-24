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
import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  RefreshControl,
  Pressable,
  ActivityIndicator,
} from "react-native";
import { useRouter, useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "../../../src/contexts/AuthContext";
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
import { getTodaysMenu } from "../../../src/services/data";
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
  const { user } = useAuth();
  const {
    selectedCafeteria,
    cafeterias,
    cafeteriasError,
    isCafeteriaLoading: cafeteriasLoading,
    refreshCafeterias,
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

  // Time-aware greeting with the signed-in user's first name. Falls back
  // to a plain greeting while the profile is still loading.
  const firstName = user?.first_name?.trim() ?? "";
  const hour = new Date().getHours();
  const partOfDay =
    hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const greetingText = firstName ? `${partOfDay}, ${firstName}` : partOfDay;

  const brand = brandGreen(resolvedTheme);
  const tc = textColor(resolvedTheme, "primary");
  const tcSec = textColor(resolvedTheme, "secondary");
  const tcMuted = textColor(resolvedTheme, "muted");
  const bg = bgColor(resolvedTheme, "primary");
  const bc = borderColor(resolvedTheme, "default");

  // State
  const [allMenuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<CategoryKey>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [hasPublishedMenu, setHasPublishedMenu] = useState<boolean | null>(null);
  const [toast, setToast] = useState<ToastState>({ visible: false, message: "", type: "success" });
  const [cafeteriaSheetVisible, setCafeteriaSheetVisible] = useState(false);
  const menuRequest = useRef(0);

  const [busyItemId, setBusyItemId] = useState<string | null>(null);
  const cartItemMap = (cart?.items ?? []).reduce<Record<string, { cartItemId: string; quantity: number }>>(
    (map, item) => {
      map[item.menu_item_id] = { cartItemId: item.id, quantity: item.quantity };
      return map;
    },
    {},
  );

  const isCafeteriaOpen = selectedCafeteria?.operational_status === "open";

  // Load menu items
  const loadMenu = useCallback(async () => {
    const request = ++menuRequest.current;
    if (!selectedCafeteria) { setError(""); setMenuItems([]); return; }
    try {
      setError("");
      const dailyMenu = await getTodaysMenu(selectedCafeteria.id);
      if (request !== menuRequest.current) return;
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
      setMenuItems(dailyItems);
    } catch {
      if (request === menuRequest.current) setError("Unable to load the menu. Check your connection and try again.");
    }
  }, [selectedCafeteria]);

  const menuItems = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return allMenuItems.filter((item) =>
      (selectedCategory === "all" || item.category === selectedCategory) &&
      (!query || item.name.toLowerCase().includes(query)));
  }, [allMenuItems, selectedCategory, searchQuery]);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setMenuItems([]);
    setHasPublishedMenu(null);
    loadMenu().finally(() => {
      if (!active) return;
      setIsLoading(false);
      setIsRefreshing(false);
    });
    return () => { active = false; menuRequest.current += 1; };
  }, [loadMenu]);

  const onRefresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await refreshCafeterias();
    } catch {
      // Shared cafeteria state supplies the error; retry clears it everywhere.
    } finally {
      setIsRefreshing(false);
    }
  }, [refreshCafeterias]);

  const showLoading = isLoading || (cafeteriasLoading && !selectedCafeteria);
  const displayError = error || (!selectedCafeteria ? cafeteriasError : "");

  // Search: switch to "all" when searching
  useEffect(() => {
    if (searchQuery.trim() && selectedCategory !== "all") {
      setSelectedCategory("all");
    }
  }, [searchQuery]);

  // Handle add to cart
  const handleAddToCart = useCallback(
    async (menuItemId: string) => {
      // Never fail silently — every blocked path tells the user why.
      if (!selectedCafeteria) {
        setToast({ visible: true, message: "Select a cafeteria first", type: "error" });
        return;
      }
      if (!isCafeteriaOpen) {
        setToast({ visible: true, message: `${selectedCafeteria.name} is closed right now`, type: "error" });
        return;
      }
      setBusyItemId(menuItemId);
      try {
        await cartAddToCart(menuItemId, 1);
        setToast({ visible: true, message: "Added to cart", type: "success" });
      } catch (err: any) {
        const msg =
          typeof err?.message === "string" && err.message.trim()
            ? err.message
            : "Failed to add item";
        setToast({ visible: true, message: msg, type: "error" });
      } finally {
        setBusyItemId(null);
      }
    },
    [cartAddToCart, isCafeteriaOpen, selectedCafeteria],
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
      // The selection effect owns menu loading. Re-selecting the same
      // object triggers no effect, so never clear/start a loader here.
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
          <Text
            style={[styles.greeting, { color: tc }]}
            numberOfLines={1}
            ellipsizeMode="tail"
          >
            {greetingText}
          </Text>
        </View>
        <Pressable
          style={styles.headerIcon}
          hitSlop={8}
          onPress={() => router.push("/(app)/notifications")}
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
                {unreadCount > 99 ? "99+" : unreadCount}
              </Text>
            </View>
          )}
        </Pressable>
      </View>

      {/* ── Café selector: its own row so the name never sits clipped
          under the greeting or behind the sticky search block ── */}
      <View style={[styles.cafeteriaRow, { backgroundColor: bg }]}>
        {selectedCafeteria ? (
          <Pressable
            onPress={() => setCafeteriaSheetVisible(true)}
            style={styles.cafeteriaInline}
            accessibilityLabel={`Current cafeteria: ${selectedCafeteria.name}. Tap to change.`}
            accessibilityRole="button"
          >
            <Ionicons name="location-outline" size={16} color={brand} />
            <View style={styles.cafeteriaTextCol}>
              <View style={styles.cafeteriaNameRow}>
                <Text
                  style={[styles.cafeteriaInlineName, { color: tcSec }]}
                  numberOfLines={1}
                  ellipsizeMode="tail"
                >
                  {selectedCafeteria.name}
                </Text>
                <View
                  style={[
                    styles.statusDot,
                    {
                      backgroundColor: functionalColor(
                        resolvedTheme,
                        isCafeteriaOpen ? "success" : "error",
                      ),
                    },
                  ]}
                />
                <Text
                  style={[
                    styles.cafeteriaStatusText,
                    {
                      color: functionalColor(
                        resolvedTheme,
                        isCafeteriaOpen ? "success" : "error",
                      ),
                    },
                  ]}
                >
                  {isCafeteriaOpen ? "Open now" : "Closed"}
                </Text>
                <Ionicons name="chevron-down" size={14} color={tcMuted} />
              </View>
              {selectedCafeteria.location ? (
                <Text
                  style={[styles.cafeteriaInlineLoc, { color: tcMuted }]}
                  numberOfLines={1}
                  ellipsizeMode="tail"
                >
                  {selectedCafeteria.location}
                </Text>
              ) : null}
            </View>
          </Pressable>
        ) : (
          <Pressable
            onPress={() => setCafeteriaSheetVisible(true)}
            style={styles.cafeteriaInline}
            accessibilityLabel="No cafeteria chosen yet. Tap to choose one."
            accessibilityRole="button"
          >
            <Ionicons name="location-outline" size={16} color={brand} />
            <Text style={[styles.cafeteriaInlineName, { color: tcSec }]}>
              Choose a cafeteria
            </Text>
            <Ionicons name="chevron-down" size={14} color={tcMuted} />
          </Pressable>
        )}
      </View>

      {/* ── Zone 3+4: Search + Category Chips (solid background so the
          menu grid never shows through when scrolling underneath) ── */}
      {selectedCafeteria && (
        <View style={[styles.stickySearchWrap, { backgroundColor: bg }]}>
          <View style={{ marginTop: 12 }}>
            <SearchBar
              value={searchQuery}
              onChangeText={setSearchQuery}
              placeholder="Search products..."
            />
          </View>
          <View style={{ marginTop: 8 }}>
            <CategoryChips
              categories={ALL_CATEGORIES}
              selected={selectedCategory}
              onSelect={handleCategoryPress}
            />
          </View>
        </View>
      )}

      {/* ── Loading State ── */}
      {showLoading && (
        <View style={styles.loadingGrid}>
          {[1, 2, 3, 4].map((i) => (
            <View key={i} style={styles.gridItem}>
              <SkeletonCard />
            </View>
          ))}
        </View>
      )}

      {/* ── Error Banner ── */}
      {displayError ? (
        <View style={[styles.errorBanner, { backgroundColor: bg, borderColor: bc }]}>
          <View style={[styles.errorIcon, { backgroundColor: colors.gold[100] }]}>
            <Ionicons name="cafe-outline" size={21} color={colors.brand[800]} />
          </View>
          <View style={styles.errorCopy}>
            <Text style={[styles.errorTitle, { color: tc }]}>Unable to connect</Text>
            <Text style={[styles.errorText, { color: tcMuted }]}>{displayError}</Text>
          </View>
          <Pressable onPress={onRefresh} accessibilityRole="button" accessibilityLabel="Retry loading menu" style={styles.retryButton}>
            <Ionicons name="refresh" size={17} color={brand} />
          </Pressable>
        </View>
      ) : null}

      {/* ── Closed Cafeteria Warning ── */}
      {!isCafeteriaOpen && selectedCafeteria && !showLoading ? (
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
      {!showLoading && hasPublishedMenu === false && (
        <EmptyState
          icon="document-text-outline"
          title="Menu not published yet"
          description="Today's menu hasn't been published. Check back later!"
        />
      )}

      {!showLoading && menuItems.length === 0 && hasPublishedMenu !== false && !displayError && (
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
      {!showLoading && !selectedCafeteria && !displayError && (
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
      {!showLoading && menuItems.length > 0 && (
        <ScrollView
          style={styles.scrollContent}
          contentContainerStyle={[
            styles.scrollContainer,
            // Room for the tab bar (56) + inset + floating CartBar (52 + gap),
            // so the last row is never hidden behind the bar.
            { paddingBottom: cartItemCount > 0 ? 168 : 92 },
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
                      void cartUpdateQuantity(cartItem.cartItemId, cartItem.quantity - 1).catch((err: unknown) => {
                        setToast({ visible: true, message: err instanceof Error ? err.message : "Unable to update cart. Please try again.", type: "error" });
                      });
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
        {cafeterias.map((caf) => {
          const statusLabel =
            caf.operational_status === "open"
              ? "Open now"
              : caf.operational_status === "closing_soon"
                ? "Closing soon"
                : caf.operational_status === "maintenance"
                  ? "Temporarily paused"
                  : "Closed";
          const statusColor =
            caf.operational_status === "open"
              ? functionalColor(resolvedTheme, "success")
              : caf.operational_status === "closing_soon"
                ? functionalColor(resolvedTheme, "warning")
                : tcMuted;
          return (
            <BottomSheetRow
              key={caf.id}
              label={caf.name}
              subtitle={
                caf.location ? `${caf.location} · ${statusLabel}` : statusLabel
              }
              subtitleColor={statusColor}
              icon="restaurant-outline"
              selected={caf.id === selectedCafeteria?.id}
              onPress={() => handleCafeteriaSelect(caf)}
            />
          );
        })}
        {cafeteriasLoading ? (
          <View style={styles.emptySheet}>
            <ActivityIndicator size="large" color={brand} />
            <Text style={{ color: tcMuted, textAlign: "center", paddingVertical: 12 }}>
              Loading cafeterias...
            </Text>
          </View>
        ) : cafeteriasError ? (
          <View style={styles.emptySheet}>
            <Text style={{ color: tcMuted, textAlign: "center", paddingVertical: 12 }}>
              {cafeterias.length ? "Unable to refresh. Showing previously loaded cafeterias." : cafeteriasError}
            </Text>
            <Pressable
              onPress={() => { void onRefresh(); }}
              style={{ paddingVertical: 8 }}
            >
              <Text style={{ color: brand, textAlign: "center", fontWeight: "600" }}>
                Try Again
              </Text>
            </Pressable>
          </View>
        ) : cafeterias.length === 0 ? (
          <View style={styles.emptySheet}>
            <Text style={{ color: tcMuted, textAlign: "center", paddingVertical: 20 }}>
              No cafeterias available at the moment. Please check back later.
            </Text>
          </View>
        ) : null}
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
    paddingTop: 6,
    paddingBottom: 14,
  },
  // Solid background for the search/chips block so scrolling menu content
  // never shows through with a hard cut. No elevation/zIndex: on Android,
  // elevation promotes the view's paint layer ABOVE the header above it and
  // the shadow overlaps the café row ("Student Cafeteria" appeared sliced by
  // this panel). The block already sits outside the ScrollView, so it is
  // effectively fixed without any elevation trickery.
  stickySearchWrap: {
    paddingHorizontal: 20,
    paddingBottom: 10,
  },
  headerLeft: {
    flex: 1,
  },
  greeting: { fontSize: 27, fontWeight: "800", lineHeight: 32, letterSpacing: -0.7 },
  cafeteriaRow: {
    paddingHorizontal: 20,
    paddingBottom: 10,
  },
  cafeteriaInline: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "stretch",
    minHeight: 44,
    paddingVertical: 4,
    paddingRight: 8,
  },
  cafeteriaTextCol: {
    flex: 1,
    marginLeft: 4,
  },
  cafeteriaNameRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  cafeteriaInlineName: {
    fontSize: 14,
    fontWeight: "600",
    flexShrink: 1,
    lineHeight: 18,
  },
  cafeteriaInlineLoc: {
    fontSize: 12,
    fontWeight: "400",
    marginTop: 1,
    lineHeight: 16,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginLeft: 7,
    marginRight: 2,
  },
  cafeteriaStatusText: {
    fontSize: 12,
    fontWeight: "600",
    marginRight: 4,
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

  // Grid — two equal columns with 16px gaps. Uses space-between (not the
  // `gap` property) because gap + flexWrap is unreliable on some RN versions
  // and produced a single-column layout.
  gridContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    paddingHorizontal: 16,
    justifyContent: "space-between",
    paddingTop: 8,
  },
  gridItem: {
    width: "48%",
    marginBottom: 16,
  },

  // Bottom sheet
  emptySheet: {
    alignItems: "center",
    paddingVertical: 20,
  },
});
