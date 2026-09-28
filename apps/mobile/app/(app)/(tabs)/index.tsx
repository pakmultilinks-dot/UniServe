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
  ActivityIndicator,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "../../../src/contexts/AuthContext";
import { useTheme } from "../../../src/contexts/ThemeContext";
import { useCart } from "../../../src/contexts/CartContext";
import { FoodCard } from "../../../src/components/ui";
import { SearchBar } from "../../../src/components/ui";
import { CategoryChips, type CategoryKey } from "../../../src/components/ui";
import { CartBar } from "../../../src/components/ui";
import { Toast } from "../../../src/components/ui";
import { EmptyState } from "../../../src/components/ui";
import { BottomSheet, BottomSheetRow } from "../../../src/components/ui/BottomSheet";
import { SkeletonCard } from "../../../src/components/ui";
import { textColor, bgColor, borderColor, brandGreen, functionalColor, colors } from "../../../src/theme";
import { getMenuItems, getTodaysMenu, getCafeterias, type MenuItemsParams } from "../../../src/services/data";
import type { MenuItem, MenuCategory, Cafeteria } from "@uniserve/shared-types";

// ── Helpers ──

function formatPrice(paisa: number): string {
  return `PKR ${Math.round(paisa / 100)}`;
}

/** Map MenuCategory to CategoryKey for the chips */
const CATEGORY_MAP: Record<MenuCategory, CategoryKey> = {
  breakfast: "breakfast",
  main_course: "main_course",
  side_dish: "side_dish",
  dessert: "dessert",
  beverage: "beverage",
  snack: "snack",
  salad: "salad",
  soup: "soup",
};

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
  const { user } = useAuth();
  const { resolvedTheme } = useTheme();
  const router = useRouter();
  const {
    selectedCafeteria,
    selectCafeteria,
    isCafeteriaLoading,
    cartItemCount,
    cartTotal,
    addToCart: cartAddToCart,
  } = useCart();

  const brand = brandGreen(resolvedTheme);
  const tc = textColor(resolvedTheme, "primary");
  const tcSec = textColor(resolvedTheme, "secondary");
  const tcMuted = textColor(resolvedTheme, "muted");
  const bg = bgColor(resolvedTheme, "primary");
  const bgSec = bgColor(resolvedTheme, "secondary");

  // State
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [allMenuItems, setAllMenuItems] = useState<MenuItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<CategoryKey>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [hasPublishedMenu, setHasPublishedMenu] = useState<boolean | null>(null);
  const [toast, setToast] = useState<ToastState>({ visible: false, message: "", type: "success" });
  const [cafeteriaSheetVisible, setCafeteriaSheetVisible] = useState(false);
  const [cafeterias, setCafeterias] = useState<Cafeteria[]>([]);

  // Track items in cart for quantity display
  const [cartItemMap, setCartItemMap] = useState<Record<string, number>>({});

  const isCafeteriaOpen = selectedCafeteria?.operational_status === "open";

  // Load cafeterias for bottom sheet
  useEffect(() => {
    getCafeterias().then(setCafeterias).catch(() => {});
  }, []);

  // Load menu items
  const loadMenu = useCallback(async () => {
    if (!selectedCafeteria) return;
    try {
      setError("");
      const dailyMenu = await getTodaysMenu(selectedCafeteria.id);
      setHasPublishedMenu(dailyMenu !== null);

      const params: MenuItemsParams = {};
      if (selectedCategory !== "all") params.category = selectedCategory as MenuCategory;
      if (searchQuery.trim()) params.search = searchQuery.trim();

      const { items } = await getMenuItems(selectedCafeteria.id, params);
      setAllMenuItems(items);
      setMenuItems(items);
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

  const onRefresh = useCallback(() => {
    setIsRefreshing(true);
    loadMenu();
  }, [loadMenu]);

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
      try {
        await cartAddToCart(menuItemId, 1);
        setCartItemMap((prev) => ({ ...prev, [menuItemId]: (prev[menuItemId] || 0) + 1 }));
        setToast({ visible: true, message: "Added to cart", type: "success" });
      } catch {
        setToast({ visible: true, message: "Failed to add item", type: "error" });
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

  // Greeting
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

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
          <Text style={[styles.greeting, { color: tc }]}>
            {greeting}
          </Text>
          <Text style={[styles.name, { color: tc }]}>
            {user?.first_name ?? "Student"}
          </Text>
        </View>
        <Pressable
          style={[styles.notifBtn, { backgroundColor: bgSec }]}
          hitSlop={8}
        >
          <Ionicons name="notifications-outline" size={22} color={tcSec} />
        </Pressable>
      </View>

      {/* Cafeteria badge */}
      {selectedCafeteria && (
        <Pressable
          onPress={() => setCafeteriaSheetVisible(true)}
          accessibilityLabel={`Current cafeteria: ${selectedCafeteria.name}. Tap to change.`}
          accessibilityRole="button"
        >
          <View style={[styles.cafeteriaRow, { backgroundColor: bgSec }]}>
            <Ionicons name="restaurant-outline" size={14} color={brand} />
            <Text style={[styles.cafeteriaName, { color: tcMuted }]} numberOfLines={1}>
              {selectedCafeteria.name}
            </Text>
            <Ionicons name="chevron-down" size={14} color={tcMuted} />
          </View>
        </Pressable>
      )}

      {/* ── Zone 3: Search ── */}
      <View style={{ marginTop: 12 }}>
        <SearchBar
          value={searchQuery}
          onChangeText={setSearchQuery}
          placeholder="Search food, drinks, snacks..."
        />
      </View>

      {/* ── Zone 4: Category Chips ── */}
      <View style={{ marginTop: 8 }}>
        <CategoryChips
          categories={ALL_CATEGORIES}
          selected={selectedCategory}
          onSelect={handleCategoryPress}
        />
      </View>

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
        <View style={[styles.errorBanner, { backgroundColor: functionalColor(resolvedTheme, "error") + "10", borderColor: functionalColor(resolvedTheme, "error") + "30" }]}>
          <Ionicons name="alert-circle" size={18} color={functionalColor(resolvedTheme, "error")} />
          <Text style={[styles.errorText, { color: functionalColor(resolvedTheme, "error"), flex: 1, marginLeft: 8 }]}>{error}</Text>
          <Pressable onPress={onRefresh}>
            <Text style={[styles.retryText, { color: brand }]}>Retry</Text>
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
          title={searchQuery ? "No items found" : "No menu items available"}
          description={
            searchQuery
              ? `No items match "${searchQuery}"`
              : "No items have been added to today's menu yet."
          }
        />
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
                  quantity={cartItemMap[item.id] || 0}
                  onPress={() => handleItemPress(item)}
                  onAdd={() => handleAddToCart(item.id)}
                  onIncrement={() => handleAddToCart(item.id)}
                  onDecrement={() => {
                    setCartItemMap((prev) => ({
                      ...prev,
                      [item.id]: Math.max(0, (prev[item.id] || 0) - 1),
                    }));
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
          onPress={() => router.push("/cart")}
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
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 20,
    paddingTop: 4,
    paddingBottom: 4,
  },
  headerLeft: {
    flex: 1,
  },
  greeting: {
    fontSize: 14,
    fontWeight: "400",
    color: "#6b7280",
    lineHeight: 18,
  },
  name: {
    fontSize: 22,
    fontWeight: "700",
    letterSpacing: -0.3,
    lineHeight: 28,
  },
  notifBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
  },

  // Cafeteria
  cafeteriaRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    gap: 6,
    marginHorizontal: 20,
    marginTop: 4,
  },
  cafeteriaName: {
    fontSize: 13,
    fontWeight: "500",
    lineHeight: 16,
    flex: 1,
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
    borderRadius: 10,
    borderWidth: 1,
    marginHorizontal: 20,
    marginTop: 12,
  },
  errorText: {
    fontSize: 13,
    fontWeight: "500",
  },
  retryText: {
    fontSize: 13,
    fontWeight: "600",
    marginLeft: 12,
  },

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
    paddingHorizontal: 20,
    gap: 12,
    paddingTop: 4,
  },
  gridItem: {
    flex: 1,
    minWidth: "45%",
    maxWidth: "48%",
  },

  // Bottom sheet
  emptySheet: {
    alignItems: "center",
    paddingVertical: 20,
  },
});
