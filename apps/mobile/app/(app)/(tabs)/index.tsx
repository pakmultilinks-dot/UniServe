/**
 * UniServe — Home Screen (Food-First Browsing Experience)
 *
 * Design spec zones:
 *   Zone 1: Status bar (system)
 *   Zone 2: Header — greeting + notification + cafeteria badge
 *   Zone 3: Search bar
 *   Zone 4: Category chips (horizontal scroll)
 *   Zone 5: Food grid (2-column, vertical scroll)
 *   Zone 6: Floating cart bar (absolute, bottom: 70)
 *   — Bottom Tab Bar (below cart bar)
 */
import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  View,
  Text,
  ScrollView,
  FlatList,
  StyleSheet,
  RefreshControl,
  Pressable,
  Animated,
  Platform,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

import { useAuth } from "../../../src/contexts/AuthContext";
import { useTheme } from "../../../src/contexts/ThemeContext";
import { useCart } from "../../../src/contexts/CartContext";
import { Spinner } from "../../../src/components/ui";
import { FoodCard } from "../../../src/components/ui";
import { SearchBar } from "../../../src/components/ui";
import { CategoryChips, type CategoryKey } from "../../../src/components/ui";
import { CafeteriaBadge } from "../../../src/components/ui";
import { CartBar } from "../../../src/components/ui";
import { Toast } from "../../../src/components/ui";
import { SkeletonCard } from "../../../src/components/ui";
import { EmptyState } from "../../../src/components/ui";
import { textColor, bgColor, borderColor, brandGreen, functionalColor, colors } from "../../../src/theme";
import { getMenuItems, getTodaysMenu, type MenuItemsParams } from "../../../src/services/data";
import type { MenuItem, MenuCategory } from "@uniserve/shared-types";

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
    isCafeteriaLoading,
    cartItemCount,
    cartTotal,
    addToCart: cartAddToCart,
  } = useCart();

  const brand = brandGreen(resolvedTheme);
  const tc = (v: "primary" | "secondary" | "muted") => textColor(resolvedTheme, v);
  const bg = (v: "primary" | "secondary" | "tertiary") => bgColor(resolvedTheme, v);
  const bc = (v: "default" | "subtle") => borderColor(resolvedTheme, v);

  // State
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<CategoryKey>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [hasPublishedMenu, setHasPublishedMenu] = useState<boolean | null>(null);
  const [toast, setToast] = useState<ToastState>({ visible: false, message: "", type: "success" });

  // Track items in cart for quantity display
  const [cartItemMap, setCartItemMap] = useState<Record<string, number>>({});

  const isCafeteriaOpen = selectedCafeteria?.operational_status === "open";

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

  // Greeting
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  // Loading skeleton
  if (isLoading && isCafeteriaLoading) {
    return (
      <View style={[styles.screen, { backgroundColor: bg("primary") }]}>
        <Spinner label="Loading menu..." />
      </View>
    );
  }

  return (
    <View style={[styles.screen, { backgroundColor: bg("primary") }]}>
      {/* Toast */}
      <Toast
        visible={toast.visible}
        message={toast.message}
        type={toast.type}
        onDismiss={() => setToast((t) => ({ ...t, visible: false }))}
      />

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
        {/* ── Zone 2: Header ── */}
        <View style={styles.header}>
          <View style={styles.headerLeft}>
            <Text style={[styles.greeting, { color: tc("primary") }]}>
              {greeting}, {user?.first_name ?? "Student"}
            </Text>
          </View>
          <Pressable
            style={[styles.notifBtn, { backgroundColor: bg("secondary") }]}
            hitSlop={8}
          >
            <Ionicons name="notifications-outline" size={22} color={tc("secondary")} />
          </Pressable>
        </View>

        {/* Cafeteria badge */}
        {selectedCafeteria && (
          <CafeteriaBadge name={selectedCafeteria.name} />
        )}

        {/* ── Zone 3: Search ── */}
        <View style={{ marginTop: 12 }}>
          <SearchBar
            value={searchQuery}
            onChangeText={setSearchQuery}
            placeholder="Search menu..."
          />
        </View>

        {/* ── Zone 4: Category Chips ── */}
        <View style={{ marginTop: 12 }}>
          <CategoryChips
            categories={ALL_CATEGORIES}
            selected={selectedCategory}
            onSelect={handleCategoryPress}
          />
        </View>

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
        {!isCafeteriaOpen && selectedCafeteria && (
          <View style={[styles.warningBanner, { backgroundColor: functionalColor(resolvedTheme, "warning") + "10", borderColor: functionalColor(resolvedTheme, "warning") + "30" }]}>
            <Ionicons name="lock-closed" size={16} color={functionalColor(resolvedTheme, "warning")} />
            <Text style={[styles.warningText, { color: functionalColor(resolvedTheme, "warning"), flex: 1, marginLeft: 8 }]}>
              {selectedCafeteria.operational_status === "closing_soon"
                ? "Closing soon — ordering may be limited"
                : "Cafeteria is currently closed"}
            </Text>
          </View>
        )}

        {/* ── Empty States ── */}
        {hasPublishedMenu === false && !isLoading && (
          <EmptyState
            icon="document-text-outline"
            title="Menu not published yet"
            description="Today's menu hasn't been published. Check back later!"
          />
        )}

        {!isLoading && menuItems.length === 0 && hasPublishedMenu !== false && (
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
        {menuItems.length > 0 && (
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
        )}
      </ScrollView>

      {/* ── Zone 6: Floating Cart Bar ── */}
      {cartItemCount > 0 && (
        <CartBar
          itemCount={cartItemCount}
          total={cartTotal}
          onPress={() => router.push("/cart")}
        />
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
    flex: 1,
  },
  scrollContainer: {
    paddingTop: 12,
  },

  // Header
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 20,
    paddingBottom: 8,
  },
  headerLeft: {
    flex: 1,
  },
  greeting: {
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
    marginTop: 8,
  },
  gridItem: {
    flex: 1,
    minWidth: "45%",
    maxWidth: "48%",
  },
});
