/**
 * UniServe — Checkout Screen
 *
 * Payment method, order note, order summary, and place order button.
 * On success navigates to the order detail screen.
 */
import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  Pressable,
  TextInput,
  ActivityIndicator,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";

import { useTheme } from "../../src/contexts/ThemeContext";
import { useCart } from "../../src/contexts/CartContext";
import { checkoutCart } from "../../src/services/data";
import { textColor, bgColor, borderColor, brandGreen } from "../../src/theme";
import type { PaymentMethod } from "@uniserve/shared-types";

// ── Helpers ──

function formatPrice(paisa: number): string {
  return `PKR ${Math.round(paisa / 100)}`;
}

// ── Screen ──

export default function CheckoutScreen() {
  const { resolvedTheme } = useTheme();
  const router = useRouter();
  const { cart, cartItemCount, cartTotal, selectedCafeteria, refreshCart } = useCart();

  const brand = brandGreen(resolvedTheme);
  const tc = textColor(resolvedTheme, "primary");
  const tcSec = textColor(resolvedTheme, "secondary");
  const tcMuted = textColor(resolvedTheme, "muted");
  const bg = bgColor(resolvedTheme, "primary");
  const bgSec = bgColor(resolvedTheme, "secondary");
  const bc = borderColor(resolvedTheme, "default");
  const bcSub = borderColor(resolvedTheme, "subtle");

  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("cash");
  const [note, setNote] = useState("");
  const [isPlacing, setIsPlacing] = useState(false);
  const [error, setError] = useState("");

  const items = cart?.items ?? [];

  const handlePlaceOrder = useCallback(async () => {
    if (!selectedCafeteria) return;
    setIsPlacing(true);
    setError("");
    try {
      const order = await checkoutCart(selectedCafeteria.id, {
        payment_method: paymentMethod,
        order_type: "immediate",
        note: note.trim() || undefined,
      });
      await refreshCart();
      router.replace(`/order/${order.id}`);
    } catch (err: any) {
      const msg = err?.message || "Failed to place order. Please try again.";
      setError(msg);
    } finally {
      setIsPlacing(false);
    }
  }, [selectedCafeteria, paymentMethod, note, refreshCart, router]);

  if (!cart || items.length === 0) {
    return (
      <View style={[styles.screen, { backgroundColor: bg }]}>
        <View style={styles.emptyState}>
          <Ionicons name="cart-outline" size={48} color={tcMuted} />
          <Text style={[styles.emptyTitle, { color: tc }]}>Nothing to checkout</Text>
          <Pressable onPress={() => router.back()}>
            <Text style={[styles.emptyLink, { color: brand }]}>Go back</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.screen, { backgroundColor: bgSec }]}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* ── Payment Method ── */}
        <Text style={[styles.sectionTitle, { color: tc }]}>Payment Method</Text>
        <View style={styles.paymentOptions}>
          <Pressable
            style={[
              styles.paymentOption,
              {
                backgroundColor: bg,
                borderColor: paymentMethod === "cash" ? brand : bc,
              },
            ]}
            onPress={() => setPaymentMethod("cash")}
          >
            <Ionicons
              name="cash-outline"
              size={22}
              color={paymentMethod === "cash" ? brand : tcMuted}
            />
            <View style={styles.paymentOptionInfo}>
              <Text style={[styles.paymentOptionLabel, { color: tc }]}>Pay at Counter</Text>
              <Text style={[styles.paymentOptionSub, { color: tcMuted }]}>
                Pay when you pick up your order
              </Text>
            </View>
            {paymentMethod === "cash" && (
              <Ionicons name="checkmark-circle" size={20} color={brand} />
            )}
          </Pressable>

          <Pressable
            style={[
              styles.paymentOption,
              {
                backgroundColor: bg,
                borderColor: paymentMethod === "online" ? brand : bc,
                opacity: 0.5,
              },
            ]}
            onPress={() => setPaymentMethod("online")}
            disabled
          >
            <Ionicons
              name="card-outline"
              size={22}
              color={paymentMethod === "online" ? brand : tcMuted}
            />
            <View style={styles.paymentOptionInfo}>
              <Text style={[styles.paymentOptionLabel, { color: tc }]}>Online Payment</Text>
              <Text style={[styles.paymentOptionSub, { color: tcMuted }]}>
                Coming soon
              </Text>
            </View>
            {paymentMethod === "online" && (
              <Ionicons name="checkmark-circle" size={20} color={brand} />
            )}
          </Pressable>
        </View>

        {/* ── Order Note ── */}
        <Text style={[styles.sectionTitle, { color: tc }]}>Order Note</Text>
        <View style={[styles.noteContainer, { backgroundColor: bg, borderColor: bc }]}>
          <TextInput
            style={[styles.noteInput, { color: tc }]}
            placeholder="Any special requests? (optional)"
            placeholderTextColor={tcMuted}
            value={note}
            onChangeText={setNote}
            multiline
            maxLength={500}
            textAlignVertical="top"
          />
          <Text style={[styles.noteCounter, { color: tcMuted }]}>
            {note.length}/500
          </Text>
        </View>

        {/* ── Order Summary ── */}
        <Text style={[styles.sectionTitle, { color: tc }]}>Order Summary</Text>
        <View style={[styles.summaryCard, { backgroundColor: bg, borderColor: bc }]}>
          {/* Items */}
          {items.map((item) => (
            <View key={item.id} style={styles.summaryItem}>
              <View style={styles.summaryItemInfo}>
                <Text style={[styles.summaryItemQty, { color: tcMuted }]}>
                  {item.quantity}×
                </Text>
                <Text style={[styles.summaryItemName, { color: tc }]} numberOfLines={1}>
                  {item.item_name ?? "Item"}
                </Text>
              </View>
              <Text style={[styles.summaryItemPrice, { color: tc }]}>
                {formatPrice(item.subtotal)}
              </Text>
            </View>
          ))}

          {/* Divider */}
          <View style={[styles.summaryDivider, { backgroundColor: bcSub }]} />

          {/* Total */}
          <View style={styles.summaryItem}>
            <Text style={[styles.summaryTotalLabel, { color: tc }]}>Total</Text>
            <Text style={[styles.summaryTotalValue, { color: brand }]}>
              {formatPrice(cartTotal)}
            </Text>
          </View>
        </View>

        {/* ── Pickup Info ── */}
        {selectedCafeteria && (
          <View style={[styles.pickupInfo, { backgroundColor: bg, borderColor: bc }]}>
            <Ionicons name="storefront-outline" size={18} color={brand} />
            <View style={styles.pickupInfoText}>
              <Text style={[styles.pickupLabel, { color: tc }]}>
                Pickup at {selectedCafeteria.name}
              </Text>
              <Text style={[styles.pickupSub, { color: tcMuted }]}>
                You'll receive a notification when your order is ready
              </Text>
            </View>
          </View>
        )}

        {/* ── Error ── */}
        {error ? (
          <View style={[styles.errorBanner, { backgroundColor: "#FEE2E2", borderColor: "#FECACA" }]}>
            <Ionicons name="alert-circle" size={16} color="#DC2626" />
            <Text style={[styles.errorText, { color: "#DC2626" }]}>{error}</Text>
          </View>
        ) : null}

        <View style={{ height: 100 }} />
      </ScrollView>

      {/* ── Bottom Bar ── */}
      <SafeAreaView edges={["bottom"]} style={{ backgroundColor: bg }}>
        <View style={[styles.bottomBar, { backgroundColor: bg, borderTopColor: bc }]}>
          <View style={styles.bottomBarInfo}>
            <Text style={[styles.bottomBarCount, { color: tcMuted }]}>
              {cartItemCount} {cartItemCount === 1 ? "item" : "items"}
            </Text>
            <Text style={[styles.bottomBarTotal, { color: brand }]}>
              {formatPrice(cartTotal)}
            </Text>
          </View>
          <Pressable
            style={[styles.placeOrderBtn, { backgroundColor: isPlacing ? tcMuted : brand }]}
            onPress={handlePlaceOrder}
            disabled={isPlacing}
          >
            {isPlacing ? (
              <ActivityIndicator size="small" color="#ffffff" />
            ) : (
              <Text style={styles.placeOrderBtnText}>Place Order</Text>
            )}
          </Pressable>
        </View>
      </SafeAreaView>
    </View>
  );
}

// ── Styles ──

const styles = StyleSheet.create({
  screen: {
    flex: 1,
  },
  emptyState: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: "600",
  },
  emptyLink: {
    fontSize: 15,
    fontWeight: "600",
  },
  scrollContent: {
    padding: 16,
  },

  // Section
  sectionTitle: {
    fontSize: 16,
    fontWeight: "700",
    marginBottom: 10,
  },

  // Payment
  paymentOptions: {
    gap: 10,
    marginBottom: 24,
  },
  paymentOption: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    padding: 14,
    borderRadius: 12,
    borderWidth: 1.5,
  },
  paymentOptionInfo: {
    flex: 1,
  },
  paymentOptionLabel: {
    fontSize: 15,
    fontWeight: "600",
  },
  paymentOptionSub: {
    fontSize: 12,
    marginTop: 2,
  },

  // Note
  noteContainer: {
    borderRadius: 10,
    borderWidth: 1,
    padding: 12,
    marginBottom: 24,
  },
  noteInput: {
    fontSize: 14,
    minHeight: 60,
    lineHeight: 20,
  },
  noteCounter: {
    fontSize: 11,
    textAlign: "right",
    marginTop: 4,
  },

  // Summary
  summaryCard: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    marginBottom: 16,
  },
  summaryItem: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 4,
  },
  summaryItemInfo: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    flex: 1,
  },
  summaryItemQty: {
    fontSize: 13,
    fontWeight: "500",
    width: 28,
  },
  summaryItemName: {
    fontSize: 14,
    flex: 1,
  },
  summaryItemPrice: {
    fontSize: 14,
    fontWeight: "500",
  },
  summaryDivider: {
    height: StyleSheet.hairlineWidth,
    marginVertical: 10,
  },
  summaryTotalLabel: {
    fontSize: 16,
    fontWeight: "700",
  },
  summaryTotalValue: {
    fontSize: 18,
    fontWeight: "700",
  },

  // Pickup
  pickupInfo: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    marginBottom: 16,
  },
  pickupInfoText: {
    flex: 1,
  },
  pickupLabel: {
    fontSize: 14,
    fontWeight: "600",
  },
  pickupSub: {
    fontSize: 12,
    marginTop: 2,
  },

  // Error
  errorBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
  },
  errorText: {
    fontSize: 13,
    fontWeight: "500",
    flex: 1,
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
  },
  bottomBarTotal: {
    fontSize: 18,
    fontWeight: "700",
  },
  placeOrderBtn: {
    paddingHorizontal: 28,
    height: 44,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  placeOrderBtnText: {
    color: "#ffffff",
    fontSize: 15,
    fontWeight: "600",
  },
});
