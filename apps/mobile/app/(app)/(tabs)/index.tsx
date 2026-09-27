/**
 * UniServe — Home Screen (Student Ordering Experience)
 *
 * The primary customer experience: cafeteria selector, category chips,
 * search, and menu item browsing with add-to-cart.
 */
import React, { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  RefreshControl,
  TouchableOpacity,
  TextInput,
} from "react-native";
import { useRouter } from "expo-router";

import { useAuth } from "../../../src/contexts/AuthContext";
import { useTheme } from "../../../src/contexts/ThemeContext";
import { useCart } from "../../../src/contexts/CartContext";
import { Spinner, EmptyState } from "../../../src/components/ui";
import { textColor, bgColor, borderColor, colors } from "../../../src/theme";
import { getMenuItems, getTodaysMenu, type MenuItemsParams } from "../../../src/services/data";
import type { MenuItem, MenuCategory } from "@uniserve/shared-types";

// ── Helpers ──

/** Format paisa (integer) to PKR display string. E.g. 15000 → "PKR 150" */
function formatPrice(paisa: number): string {
  const pkr = paisa / 100;
  return pkr % 1 === 0 ? `PKR ${pkr}` : `PKR ${pkr.toFixed(2)}`;
}

/** Human-readable labels for menu categories */
const CATEGORY_LABELS: Record<MenuCategory, string> = {
  breakfast: "🍳 Breakfast",
  main_course: "🍛 Main Course",
  side_dish: "🥗 Side Dish",
  dessert: "🍰 Dessert",
  beverage: "☕ Beverage",
  snack: "🍿 Snack",
  salad: "🥬 Salad",
  soup: "🍜 Soup",
};

const ALL_CATEGORIES: MenuCategory[] = [
  "breakfast",
  "main_course",
  "side_dish",
  "dessert",
  "beverage",
  "snack",
  "salad",
  "soup",
];

// ── Menu Item Card ──

interface MenuItemCardProps {
  item: MenuItem;
  onAddToCart: (itemId: string) => void;
  onPress: (item: MenuItem) => void;
  theme: "light" | "dark";
}

function MenuItemCard({ item, onAddToCart, onPress, theme }: MenuItemCardProps) {
  const tc = (v: "primary" | "secondary" | "muted") => textColor(theme, v);
  const bg = (v: "primary" | "secondary") => bgColor(theme, v);
  const bc = (v: "default" | "subtle") => borderColor(theme, v);

  return (
    <TouchableOpacity
      style={[styles.itemCard, { backgroundColor: bg("primary"), borderColor: bc("default") }]}
      onPress={() => onPress(item)}
      activeOpacity={0.7}
      disabled={!item.is_available}
    >
      {/* Item image placeholder (emoji based on category) */}
      <View style={[styles.itemImagePlaceholder, { backgroundColor: bg("secondary") }]}>
        <Text style={styles.itemEmoji}>
          {item.category === "main_course"
            ? "🍛"
            : item.category === "beverage"
              ? "☕"
              : item.category === "dessert"
                ? "🍰"
                : item.category === "snack"
                  ? "🍿"
                  : item.category === "breakfast"
                    ? "🍳"
                    : item.category === "salad"
                      ? "🥬"
                      : item.category === "soup"
                        ? "🍜"
                        : "🍽️"}
        </Text>
      </View>

      {/* Item info */}
      <View style={styles.itemInfo}>
        <Text style={[styles.itemName, { color: tc("primary") }]} numberOfLines={1}>
          {item.name}
        </Text>
        {item.description ? (
          <Text style={[styles.itemDesc, { color: tc("muted") }]} numberOfLines={2}>
            {item.description}
          </Text>
        ) : null}
        <View style={styles.itemBottomRow}>
          <Text style={[styles.itemPrice, { color: colors.brand[700] }]}>
            {formatPrice(item.price)}
          </Text>
          {item.is_available ? (
            <TouchableOpacity
              style={[styles.addButton, { backgroundColor: colors.brand[700] }]}
              onPress={() => onAddToCart(item.id)}
              activeOpacity={0.7}
            >
              <Text style={styles.addButtonText}>+</Text>
            </TouchableOpacity>
          ) : (
            <View style={[styles.addButton, { backgroundColor: colors.neutral[300] }]}>
              <Text style={[styles.addButtonText, { color: colors.neutral[500] }]}>—</Text>
            </View>
          )}
        </View>
        {!item.is_available && (
          <Text style={[styles.outOfStockLabel, { color: colors.error }]}>Out of stock</Text>
        )}
      </View>
    </TouchableOpacity>
  );
}

// ── Cart Bottom Bar ──

function CartBar({
  itemCount,
  total,
  onPress,
}: {
  itemCount: number;
  total: number;
  onPress: () => void;
}) {
  if (itemCount === 0) return null;

  return (
    <TouchableOpacity
      style={[styles.cartBar, { backgroundColor: colors.brand[700] }]}
      onPress={onPress}
      activeOpacity={0.85}
    >
      <View style={styles.cartBarLeft}>
        <View style={styles.cartBadge}>
          <Text style={styles.cartBadgeText}>{itemCount}</Text>
        </View>
        <Text style={styles.cartBarLabel}>
          {itemCount === 1 ? "1 item" : `${itemCount} items`}
        </Text>
      </View>
      <View style={styles.cartBarRight}>
        <Text style={styles.cartBarTotal}>{formatPrice(total)}</Text>
        <Text style={styles.cartBarArrow}>→</Text>
      </View>
    </TouchableOpacity>
  );
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

  const theme = resolvedTheme as "light" | "dark";
  const tc = (v: "primary" | "secondary" | "muted") => textColor(resolvedTheme, v);
  const bg = (v: "primary" | "secondary" | "tertiary") => bgColor(resolvedTheme, v);
  const bc = (v: "default" | "subtle") => borderColor(resolvedTheme, v);

  // State
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<MenuCategory | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [hasPublishedMenu, setHasPublishedMenu] = useState<boolean | null>(null);

  // Check if cafeteria is open
  const isCafeteriaOpen = selectedCafeteria?.operational_status === "open";

  // Load menu items
  const loadMenu = useCallback(async () => {
    if (!selectedCafeteria) return;
    try {
      setError("");

      // Check for published daily menu first
      const dailyMenu = await getTodaysMenu(selectedCafeteria.id);
      setHasPublishedMenu(dailyMenu !== null);

      // Fetch all available menu items
      const params: MenuItemsParams = {};
      if (selectedCategory) params.category = selectedCategory;
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

  // Search: clear category when searching
  useEffect(() => {
    if (searchQuery.trim()) {
      setSelectedCategory(null);
    }
  }, [searchQuery]);

  // Handle add to cart
  const handleAddToCart = useCallback(
    async (menuItemId: string) => {
      if (!isCafeteriaOpen) return;
      await cartAddToCart(menuItemId, 1);
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
  const handleCategoryPress = useCallback((cat: MenuCategory) => {
    setSearchQuery("");
    setSelectedCategory((prev) => (prev === cat ? null : cat));
  }, []);

  // Greeting
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  // Loading state
  if (isLoading && isCafeteriaLoading) {
    return (
      <View style={[styles.screen, { backgroundColor: bg("secondary") }]}>
        <Spinner label="Loading menu..." />
      </View>
    );
  }

  return (
    <View style={[styles.screen, { backgroundColor: bg("secondary") }]}>
      <ScrollView
        style={styles.scrollContent}
        contentContainerStyle={styles.scrollContainer}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={onRefresh}
            colors={[colors.brand[700]]}
          />
        }
        showsVerticalScrollIndicator={false}
      >
        {/* ── Header ── */}
        <View style={styles.header}>
          <View style={styles.headerLeft}>
            <Text style={[styles.greeting, { color: tc("primary") }]}>
              {greeting}, {user?.first_name ?? "Student"}
            </Text>
            <Text style={[styles.headerSubtext, { color: tc("muted") }]}>
              What would you like today?
            </Text>
          </View>
          <TouchableOpacity
            style={[styles.iconButton, { backgroundColor: bg("tertiary"), borderColor: bc("default") }]}
            onPress={() => {}}
          >
            <Text style={styles.iconButtonText}>🔔</Text>
          </TouchableOpacity>
        </View>

        {/* ── Cafeteria Badge ── */}
        {selectedCafeteria ? (
          <View
            style={[
              styles.cafeteriaBadge,
              {
                backgroundColor: bg("primary"),
                borderColor: bc("default"),
                opacity: isCafeteriaOpen ? 1 : 0.7,
              },
            ]}
          >
            <View style={styles.cafeteriaBadgeLeft}>
              <Text style={styles.cafeteriaEmoji}>🍽️</Text>
              <View>
                <Text style={[styles.cafeteriaName, { color: tc("primary") }]}>
                  {selectedCafeteria.name}
                </Text>
                <Text style={[styles.cafeteriaLocation, { color: tc("muted") }]}>
                  {selectedCafeteria.location ?? "Campus"}
                </Text>
              </View>
            </View>
            <View
              style={[
                styles.statusDot,
                { backgroundColor: isCafeteriaOpen ? colors.success : colors.error },
              ]}
            />
          </View>
        ) : !isCafeteriaLoading ? (
          <View style={[styles.cafeteriaBadge, { backgroundColor: bg("primary"), borderColor: bc("default") }]}>
            <Text style={[styles.noCafeteria, { color: tc("muted") }]}>
              No cafeteria available
            </Text>
          </View>
        ) : null}

        {/* ── Category Chips ── */}
        {hasPublishedMenu !== false && (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            style={styles.categoryScroll}
            contentContainerStyle={styles.categoryContainer}
          >
            {ALL_CATEGORIES.map((cat) => {
              const isActive = selectedCategory === cat;
              return (
                <TouchableOpacity
                  key={cat}
                  style={[
                    styles.categoryChip,
                    {
                      backgroundColor: isActive ? colors.brand[700] : bg("primary"),
                      borderColor: isActive ? colors.brand[700] : bc("default"),
                    },
                  ]}
                  onPress={() => handleCategoryPress(cat)}
                  activeOpacity={0.7}
                >
                  <Text
                    style={[
                      styles.categoryChipText,
                      { color: isActive ? "#ffffff" : tc("secondary") },
                    ]}
                    numberOfLines={1}
                  >
                    {CATEGORY_LABELS[cat]}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        )}

        {/* ── Search Bar ── */}
        {hasPublishedMenu !== false && (
          <View style={[styles.searchBar, { backgroundColor: bg("primary"), borderColor: bc("default") }]}>
            <Text style={styles.searchIcon}>🔍</Text>
            <TextInput
              style={[styles.searchInput, { color: tc("primary") }]}
              placeholder="Search menu items..."
              placeholderTextColor={resolvedTheme === "dark" ? colors.neutral[500] : colors.neutral[400]}
              value={searchQuery}
              onChangeText={setSearchQuery}
              returnKeyType="search"
            />
            {searchQuery.length > 0 && (
              <TouchableOpacity onPress={() => setSearchQuery("")}>
                <Text style={[styles.searchClear, { color: tc("muted") }]}>✕</Text>
              </TouchableOpacity>
            )}
          </View>
        )}

        {/* ── Error State ── */}
        {error ? (
          <View style={[styles.errorBanner, { backgroundColor: "#fef2f2", borderColor: "#fecaca" }]}>
            <Text style={[styles.errorText, { color: "#991b1b" }]}>{error}</Text>
            <TouchableOpacity onPress={onRefresh}>
              <Text style={[styles.retryText, { color: colors.brand[700] }]}>Retry</Text>
            </TouchableOpacity>
          </View>
        ) : null}

        {/* ── Closed Cafeteria Warning ── */}
        {!isCafeteriaOpen && selectedCafeteria && (
          <View style={[styles.closedBanner, { backgroundColor: "#fff7ed", borderColor: "#fed7aa" }]}>
            <Text style={styles.closedBannerIcon}>⚠️</Text>
            <Text style={[styles.closedBannerText, { color: "#9a3412" }]}>
              {selectedCafeteria.operational_status === "closing_soon"
                ? "Cafeteria is closing soon"
                : "Cafeteria is currently closed"}{" "}
              — ordering is not available right now.
            </Text>
          </View>
        )}

        {/* ── No Published Menu State ── */}
        {hasPublishedMenu === false && !isLoading && (
          <EmptyState
            emoji="📋"
            title="Menu not published yet"
            description="Today's menu hasn't been published. Check back later!"
          />
        )}

        {/* ── No Search Results ── */}
        {!isLoading && menuItems.length === 0 && hasPublishedMenu !== false && (
          <EmptyState
            emoji={searchQuery ? "🔍" : "🍽️"}
            title={searchQuery ? "No items found" : "No menu items available"}
            description={
              searchQuery
                ? `No items match "${searchQuery}"`
                : "No items have been added to today's menu yet."
            }
          />
        )}

        {/* ── Menu Items ── */}
        {menuItems.length > 0 && (
          <View style={styles.menuSection}>
            {searchQuery ? (
              <Text style={[styles.menuSectionTitle, { color: tc("muted") }]}>
                Results for "{searchQuery}"
              </Text>
            ) : selectedCategory ? (
              <Text style={[styles.menuSectionTitle, { color: tc("muted") }]}>
                {CATEGORY_LABELS[selectedCategory]}
              </Text>
            ) : (
              <Text style={[styles.menuSectionTitle, { color: tc("muted") }]}>
                All items
              </Text>
            )}
            <View style={styles.menuGrid}>
              {menuItems.map((item) => (
                <MenuItemCard
                  key={item.id}
                  item={item}
                  onAddToCart={handleAddToCart}
                  onPress={handleItemPress}
                  theme={theme}
                />
              ))}
            </View>
          </View>
        )}

        {/* Bottom padding for cart bar */}
        {cartItemCount > 0 && <View style={{ height: 80 }} />}
      </ScrollView>

      {/* ── Floating Cart Bar ── */}
      <CartBar
        itemCount={cartItemCount}
        total={cartTotal}
        onPress={() => router.push("/cart")}
      />
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
    padding: 16,
    paddingBottom: 24,
  },

  // Header
  header: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    marginBottom: 16,
  },
  headerLeft: {
    flex: 1,
  },
  greeting: {
    fontSize: 22,
    fontWeight: "700",
    letterSpacing: -0.3,
  },
  headerSubtext: {
    fontSize: 14,
    marginTop: 4,
  },
  iconButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
  },
  iconButtonText: {
    fontSize: 18,
  },

  // Cafeteria badge
  cafeteriaBadge: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: 14,
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 16,
  },
  cafeteriaBadgeLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  cafeteriaEmoji: {
    fontSize: 28,
  },
  cafeteriaName: {
    fontSize: 15,
    fontWeight: "600",
  },
  cafeteriaLocation: {
    fontSize: 12,
    marginTop: 1,
  },
  statusDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  noCafeteria: {
    fontSize: 14,
    textAlign: "center",
    width: "100%",
  },

  // Category chips
  categoryScroll: {
    marginBottom: 12,
  },
  categoryContainer: {
    gap: 8,
    paddingRight: 16,
  },
  categoryChip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
  },
  categoryChipText: {
    fontSize: 13,
    fontWeight: "600",
  },

  // Search
  searchBar: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 10,
    borderWidth: 1,
    paddingHorizontal: 12,
    height: 44,
    marginBottom: 16,
    gap: 8,
  },
  searchIcon: {
    fontSize: 16,
  },
  searchInput: {
    flex: 1,
    fontSize: 15,
    paddingVertical: 0,
  },
  searchClear: {
    fontSize: 16,
    fontWeight: "600",
    paddingLeft: 4,
  },

  // Error
  errorBanner: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    marginBottom: 12,
  },
  errorText: {
    fontSize: 13,
    fontWeight: "500",
    flex: 1,
  },
  retryText: {
    fontSize: 13,
    fontWeight: "600",
    marginLeft: 12,
  },

  // Closed banner
  closedBanner: {
    flexDirection: "row",
    alignItems: "center",
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    marginBottom: 16,
    gap: 8,
  },
  closedBannerIcon: {
    fontSize: 18,
  },
  closedBannerText: {
    fontSize: 13,
    fontWeight: "500",
    flex: 1,
  },

  // Menu section
  menuSection: {
    marginTop: 4,
  },
  menuSectionTitle: {
    fontSize: 13,
    fontWeight: "600",
    marginBottom: 10,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  menuGrid: {
    gap: 10,
  },

  // Menu item card
  itemCard: {
    flexDirection: "row",
    borderRadius: 12,
    borderWidth: 1,
    overflow: "hidden",
  },
  itemImagePlaceholder: {
    width: 80,
    height: 80,
    alignItems: "center",
    justifyContent: "center",
  },
  itemEmoji: {
    fontSize: 32,
  },
  itemInfo: {
    flex: 1,
    padding: 12,
    justifyContent: "space-between",
  },
  itemName: {
    fontSize: 15,
    fontWeight: "600",
  },
  itemDesc: {
    fontSize: 12,
    marginTop: 2,
    lineHeight: 16,
  },
  itemBottomRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 6,
  },
  itemPrice: {
    fontSize: 15,
    fontWeight: "700",
  },
  addButton: {
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: "center",
    justifyContent: "center",
  },
  addButtonText: {
    color: "#ffffff",
    fontSize: 18,
    fontWeight: "700",
    lineHeight: 20,
  },
  outOfStockLabel: {
    fontSize: 11,
    fontWeight: "500",
    marginTop: 2,
  },

  // Cart bar
  cartBar: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 20,
    paddingVertical: 14,
    marginHorizontal: 16,
    marginBottom: 16,
    borderRadius: 14,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 8,
  },
  cartBarLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  cartBadge: {
    backgroundColor: "#ffffff",
    borderRadius: 12,
    minWidth: 24,
    height: 24,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 6,
  },
  cartBadgeText: {
    color: colors.brand[700],
    fontSize: 12,
    fontWeight: "700",
  },
  cartBarLabel: {
    color: "#ffffff",
    fontSize: 15,
    fontWeight: "600",
  },
  cartBarRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  cartBarTotal: {
    color: "#ffffff",
    fontSize: 16,
    fontWeight: "700",
  },
  cartBarArrow: {
    color: "#ffffff",
    fontSize: 16,
    fontWeight: "600",
  },
});
