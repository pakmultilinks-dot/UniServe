/**
 * UniServe — Cart Screen
 *
 * Shows cart items with quantity controls, line totals, and overall total.
 * NO checkout/payment in this slice — that's next slice.
 */
import React, { useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
} from "react-native";

import { useTheme } from "../../src/contexts/ThemeContext";
import { useCart } from "../../src/contexts/CartContext";
import { EmptyState, Button } from "../../src/components/ui";
import { textColor, bgColor, borderColor, colors } from "../../src/theme";
import type { CartItemResponse } from "@uniserve/shared-types";

// ── Helpers ──

function formatPrice(paisa: number): string {
  const pkr = paisa / 100;
  return pkr % 1 === 0 ? `PKR ${pkr}` : `PKR ${pkr.toFixed(2)}`;
}

// ── Cart Item Row ──

interface CartItemRowProps {
  item: CartItemResponse;
  onUpdateQuantity: (cartItemId: string, quantity: number) => void;
  onRemove: (cartItemId: string) => void;
  theme: "light" | "dark";
}

function CartItemRow({ item, onUpdateQuantity, onRemove, theme }: CartItemRowProps) {
  const tc = (v: "primary" | "secondary" | "muted") => textColor(theme, v);
  const bg = (v: "primary" | "secondary") => bgColor(theme, v);
  const bc = (v: "default" | "subtle") => borderColor(theme, v);

  const isUnavailable = item.item_available === false;

  return (
    <View
      style={[
        styles.cartItem,
        { backgroundColor: bg("primary"), borderColor: bc("default") },
        isUnavailable && { opacity: 0.5 },
      ]}
    >
      {/* Item Info */}
      <View style={styles.cartItemInfo}>
        <Text style={[styles.cartItemName, { color: tc("primary") }]} numberOfLines={1}>
          {item.item_name ?? "Menu item"}
        </Text>
        {isUnavailable && (
          <Text style={[styles.unavailableLabel, { color: colors.error }]}>
            No longer available
          </Text>
        )}
        <Text style={[styles.cartItemUnitPrice, { color: tc("muted") }]}>
          {formatPrice(item.price_snapshot)} each
        </Text>
      </View>

      {/* Quantity Controls */}
      <View style={styles.cartItemRight}>
        <View style={[styles.qtyControl, { borderColor: bc("default") }]}>
          <TouchableOpacity
            style={styles.qtyBtn}
            onPress={() => onUpdateQuantity(item.id, item.quantity - 1)}
          >
            <Text style={[styles.qtyBtnText, { color: tc("primary") }]}>−</Text>
          </TouchableOpacity>
          <Text style={[styles.qtyValue, { color: tc("primary") }]}>{item.quantity}</Text>
          <TouchableOpacity
            style={styles.qtyBtn}
            onPress={() => onUpdateQuantity(item.id, item.quantity + 1)}
            disabled={item.quantity >= 10}
          >
            <Text style={[styles.qtyBtnText, { color: item.quantity >= 10 ? tc("muted") : tc("primary") }]}>
              +
            </Text>
          </TouchableOpacity>
        </View>
        <Text style={[styles.cartItemSubtotal, { color: tc("primary") }]}>
          {formatPrice(item.subtotal)}
        </Text>
      </View>
    </View>
  );
}

// ── Main Cart Screen ──

export default function CartScreen() {
  const { resolvedTheme } = useTheme();
  const {
    cart,
    cartItemCount,
    cartTotal,
    selectedCafeteria,
    updateQuantity,
    removeFromCart,
  } = useCart();

  const theme = resolvedTheme as "light" | "dark";
  const tc = (v: "primary" | "secondary" | "muted") => textColor(resolvedTheme, v);
  const bg = (v: "primary" | "secondary" | "tertiary") => bgColor(resolvedTheme, v);
  const bc = (v: "default" | "subtle") => borderColor(resolvedTheme, v);

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

  return (
    <View style={[styles.screen, { backgroundColor: bg("secondary") }]}>
      {items.length === 0 ? (
        <View style={styles.emptyContainer}>
          <EmptyState
            emoji="🛒"
            title="Your cart is empty"
            description="Browse the menu and add items to your cart"
          />
        </View>
      ) : (
        <>
          <ScrollView
            contentContainerStyle={styles.scrollContent}
            showsVerticalScrollIndicator={false}
          >
            {/* ── Cafeteria Name ── */}
            {selectedCafeteria && (
              <View style={[styles.cafeteriaHeader, { backgroundColor: bg("primary"), borderColor: bc("default") }]}>
                <Text style={[styles.cafeteriaName, { color: tc("primary") }]}>
                  🍽️ {selectedCafeteria.name}
                </Text>
              </View>
            )}

            {/* ── Cart Items ── */}
            <View style={styles.cartItemsList}>
              {items.map((item) => (
                <CartItemRow
                  key={item.id}
                  item={item}
                  onUpdateQuantity={handleUpdateQuantity}
                  onRemove={removeFromCart}
                  theme={theme}
                />
              ))}
            </View>

            {/* ── Summary ── */}
            <View style={[styles.summaryCard, { backgroundColor: bg("primary"), borderColor: bc("default") }]}>
              <View style={styles.summaryRow}>
                <Text style={[styles.summaryLabel, { color: tc("muted") }]}>Items</Text>
                <Text style={[styles.summaryValue, { color: tc("primary") }]}>
                  {cartItemCount}
                </Text>
              </View>
              <View style={[styles.summaryDivider, { backgroundColor: bc("subtle") }]} />
              <View style={styles.summaryRow}>
                <Text style={[styles.summaryLabelTotal, { color: tc("primary") }]}>Total</Text>
                <Text style={[styles.summaryValueTotal, { color: colors.brand[700] }]}>
                  {formatPrice(cartTotal)}
                </Text>
              </View>
            </View>

            {/* ── Checkout placeholder ── */}
            <View style={[styles.checkoutPlaceholder, { backgroundColor: bg("primary"), borderColor: bc("default") }]}>
              <Text style={[styles.checkoutPlaceholderText, { color: tc("muted") }]}>
                💳 Checkout and payment will be available in the next update.
              </Text>
            </View>

            <View style={{ height: 32 }} />
          </ScrollView>
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
  },
  scrollContent: {
    padding: 16,
  },

  // Cafeteria header
  cafeteriaHeader: {
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    marginBottom: 16,
  },
  cafeteriaName: {
    fontSize: 15,
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
    borderRadius: 8,
    borderWidth: 1,
  },
  qtyBtn: {
    width: 32,
    height: 32,
    alignItems: "center",
    justifyContent: "center",
  },
  qtyBtnText: {
    fontSize: 16,
    fontWeight: "600",
  },
  qtyValue: {
    width: 32,
    textAlign: "center",
    fontSize: 14,
    fontWeight: "600",
  },
  cartItemSubtotal: {
    fontSize: 14,
    fontWeight: "700",
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

  // Checkout placeholder
  checkoutPlaceholder: {
    padding: 16,
    borderRadius: 10,
    borderWidth: 1,
    borderStyle: "dashed",
    alignItems: "center",
  },
  checkoutPlaceholderText: {
    fontSize: 13,
    textAlign: "center",
    lineHeight: 18,
  },
});
