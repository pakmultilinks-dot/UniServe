/**
 * UniServe — Cart Screen
 *
 * Shows cart items with quantity controls, line totals, summary, and checkout button.
 * Cart is contextual (not a tab) — user arrives here from home/cart bar.
 */
import React, { useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  Pressable,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";

import { useTheme } from "../../src/contexts/ThemeContext";
import { useCart } from "../../src/contexts/CartContext";
import { EmptyState } from "../../src/components/ui";
import { textColor, bgColor, borderColor, brandGreen, functionalColor } from "../../src/theme";
import type { CartItemResponse } from "@uniserve/shared-types";

// ── Helpers ──

function formatPrice(paisa: number): string {
  return `PKR ${Math.round(paisa / 100)}`;
}

// ── Cart Item Row ──

interface CartItemRowProps {
  item: CartItemResponse;
  onUpdateQuantity: (cartItemId: string, quantity: number) => void;
  theme: "light" | "dark";
}

function CartItemRow({ item, onUpdateQuantity, theme }: CartItemRowProps) {
  const tc = textColor(theme, "primary");
  const tcMuted = textColor(theme, "muted");
  const bg = bgColor(theme, "secondary");
  const bc = borderColor(theme, "default");
  const brand = brandGreen(theme);

  const isUnavailable = item.item_available === false;

  return (
    <View
      style={[
        styles.cartItem,
        { backgroundColor: bg, borderColor: bc },
        isUnavailable && styles.cartItemUnavailable,
      ]}
    >
      {/* Item Info */}
      <View style={styles.cartItemInfo}>
        <Text style={[styles.cartItemName, { color: tc }]} numberOfLines={1}>
          {item.item_name ?? "Menu item"}
        </Text>
        {isUnavailable && (
          <Text style={[styles.unavailableLabel, { color: functionalColor(theme, "error") }]}>
            No longer available
          </Text>
        )}
        <Text style={[styles.cartItemUnitPrice, { color: tcMuted }]}>
          {formatPrice(item.price_snapshot)} each
        </Text>
      </View>

      {/* Quantity + Subtotal */}
      <View style={styles.cartItemRight}>
        <View style={[styles.qtyControl, { borderColor: bc, backgroundColor: bgColor(theme, "primary") }]}>
          <Pressable
            style={styles.qtyBtn}
            onPress={() => onUpdateQuantity(item.id, item.quantity - 1)}
            hitSlop={6}
          >
            <Ionicons
              name={item.quantity <= 1 ? "remove-circle-outline" : "remove-circle"}
              size={20}
              color={item.quantity <= 1 ? tcMuted : brand}
            />
          </Pressable>
          <Text style={[styles.qtyValue, { color: tc }]}>{item.quantity}</Text>
          <Pressable
            style={styles.qtyBtn}
            onPress={() => onUpdateQuantity(item.id, item.quantity + 1)}
            disabled={item.quantity >= 10}
            hitSlop={6}
          >
            <Ionicons
              name={item.quantity >= 10 ? "add-circle-outline" : "add-circle"}
              size={20}
              color={item.quantity >= 10 ? tcMuted : brand}
            />
          </Pressable>
        </View>
        <Text style={[styles.cartItemSubtotal, { color: tc }]}>
          {formatPrice(item.subtotal)}
        </Text>
      </View>
    </View>
  );
}

// ── Main Cart Screen ──

export default function CartScreen() {
  const { resolvedTheme } = useTheme();
  const router = useRouter();
  const {
    cart,
    cartItemCount,
    cartTotal,
    selectedCafeteria,
    updateQuantity,
    removeFromCart,
  } = useCart();

  const brand = brandGreen(resolvedTheme);
  const tc = textColor(resolvedTheme, "primary");
  const tcMuted = textColor(resolvedTheme, "muted");
  const bg = bgColor(resolvedTheme, "primary");
  const bgSec = bgColor(resolvedTheme, "secondary");
  const bc = borderColor(resolvedTheme, "default");
  const bcSub = borderColor(resolvedTheme, "subtle");

  const handleUpdateQuantity = useCallback(
    async (cartItemId: string, newQty: number) => {
      if (newQty <= 0) {
        await removeFromCart(cartItemId);
      } else {
        await updateQuantity(cartItemId, newQty);
      }
    },
    [updateQuantity, removeFromCart],
  );

  const items = cart?.items ?? [];
  const hasUnavailable = items.some((i) => i.item_available === false);

  return (
    <View style={[styles.screen, { backgroundColor: bgSec }]}>
      {items.length === 0 ? (
        <View style={styles.emptyContainer}>
          <EmptyState
            icon="cart-outline"
            title="Your cart is empty"
            description="Browse the menu and add items to get started"
          />
          <View style={{ paddingHorizontal: 32, marginTop: 12 }}>
            <Pressable
              style={[styles.browseBtn, { backgroundColor: brand }]}
              onPress={() => router.back()}
            >
              <Text style={styles.browseBtnText}>Browse menu</Text>
            </Pressable>
          </View>
        </View>
      ) : (
        <>
          <ScrollView
            contentContainerStyle={styles.scrollContent}
            showsVerticalScrollIndicator={false}
          >
            {/* ── Cafeteria header ── */}
            {selectedCafeteria && (
              <View style={[styles.cafeteriaHeader, { backgroundColor: bg, borderColor: bc }]}>
                <Ionicons name="storefront-outline" size={16} color={brand} />
                <Text style={[styles.cafeteriaName, { color: tc }]}>
                  {selectedCafeteria.name}
                </Text>
              </View>
            )}

            {/* ── Cart items ── */}
            <View style={styles.cartItemsList}>
              {items.map((item) => (
                <CartItemRow
                  key={item.id}
                  item={item}
                  onUpdateQuantity={handleUpdateQuantity}
                  theme={resolvedTheme as "light" | "dark"}
                />
              ))}
            </View>

            {/* ── Unavailable warning ── */}
            {hasUnavailable && (
              <View style={[styles.warningBanner, { backgroundColor: functionalColor(resolvedTheme, "warning") + "10", borderColor: functionalColor(resolvedTheme, "warning") + "30" }]}>
                <Ionicons name="warning-outline" size={16} color={functionalColor(resolvedTheme, "warning")} />
                <Text style={[styles.warningText, { color: functionalColor(resolvedTheme, "warning") }]}>
                  Some items are no longer available and will be removed at checkout
                </Text>
              </View>
            )}

            {/* ── Summary card ── */}
            <View style={[styles.summaryCard, { backgroundColor: bg, borderColor: bc }]}>
              <View style={styles.summaryRow}>
                <Text style={[styles.summaryLabel, { color: tcMuted }]}>
                  Items ({cartItemCount})
                </Text>
                <Text style={[styles.summaryValue, { color: tc }]}>
                  {formatPrice(cartTotal)}
                </Text>
              </View>
              <View style={[styles.summaryDivider, { backgroundColor: bcSub }]} />
              <View style={styles.summaryRow}>
                <Text style={[styles.summaryLabelTotal, { color: tc }]}>Total</Text>
                <Text style={[styles.summaryValueTotal, { color: brand }]}>
                  {formatPrice(cartTotal)}
                </Text>
              </View>
            </View>

            <View style={{ height: 32 }} />
          </ScrollView>

          {/* ── Bottom checkout bar ── */}
          <SafeAreaView edges={["bottom"]} style={{ backgroundColor: bg }}>
            <View style={[styles.bottomBar, { backgroundColor: bg, borderTopColor: bc }]}>
              <View style={styles.bottomBarInfo}>
                <Text style={[styles.bottomBarCount, { color: tc }]}>
                  {cartItemCount} {cartItemCount === 1 ? "item" : "items"}
                </Text>
                <Text style={[styles.bottomBarTotal, { color: brand }]}>
                  {formatPrice(cartTotal)}
                </Text>
              </View>
              <Pressable
                style={[styles.checkoutBtn, { backgroundColor: brand }]}
                onPress={() => router.push("/checkout")}
              >
                <Text style={styles.checkoutBtnText}>Checkout</Text>
                <Ionicons name="arrow-forward" size={16} color="#ffffff" />
              </Pressable>
            </View>
          </SafeAreaView>
        </>
      )}
    </View>
  );
}

// ── Styles ──

const styles = StyleSheet.create({
  screen: {
    flex: 1,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  browseBtn: {
    height: 44,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 8,
  },
  browseBtnText: {
    color: "#ffffff",
    fontSize: 15,
    fontWeight: "600",
  },
  scrollContent: {
    padding: 16,
  },

  // Cafeteria header
  cafeteriaHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    marginBottom: 16,
  },
  cafeteriaName: {
    fontSize: 14,
    fontWeight: "600",
  },

  // Cart items
  cartItemsList: {
    gap: 10,
    marginBottom: 16,
  },
  cartItem: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: 14,
    borderRadius: 12,
    borderWidth: 1,
  },
  cartItemUnavailable: {
    opacity: 0.5,
  },
  cartItemInfo: {
    flex: 1,
    marginRight: 12,
  },
  cartItemName: {
    fontSize: 15,
    fontWeight: "600",
  },
  unavailableLabel: {
    fontSize: 11,
    fontWeight: "500",
    marginTop: 2,
  },
  cartItemUnitPrice: {
    fontSize: 12,
    marginTop: 3,
  },
  cartItemRight: {
    alignItems: "flex-end",
    gap: 6,
  },
  qtyControl: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 10,
    borderWidth: 1,
    height: 36,
  },
  qtyBtn: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  qtyValue: {
    width: 36,
    textAlign: "center",
    fontSize: 14,
    fontWeight: "600",
  },
  cartItemSubtotal: {
    fontSize: 14,
    fontWeight: "700",
  },

  // Warning
  warningBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    marginBottom: 16,
  },
  warningText: {
    fontSize: 12,
    fontWeight: "500",
    flex: 1,
    lineHeight: 16,
  },

  // Summary
  summaryCard: {
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 12,
  },
  summaryRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 4,
  },
  summaryLabel: {
    fontSize: 14,
  },
  summaryValue: {
    fontSize: 14,
    fontWeight: "500",
  },
  summaryDivider: {
    height: StyleSheet.hairlineWidth,
    marginVertical: 10,
  },
  summaryLabelTotal: {
    fontSize: 16,
    fontWeight: "700",
  },
  summaryValueTotal: {
    fontSize: 20,
    fontWeight: "700",
  },

  // Bottom bar
  bottomBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  bottomBarInfo: {
    gap: 2,
  },
  bottomBarCount: {
    fontSize: 13,
    fontWeight: "500",
  },
  bottomBarTotal: {
    fontSize: 18,
    fontWeight: "700",
  },
  checkoutBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 24,
    height: 44,
    borderRadius: 10,
  },
  checkoutBtnText: {
    color: "#ffffff",
    fontSize: 15,
    fontWeight: "600",
  },
});
