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
import { checkoutCart, initiatePayment } from "../../src/services/data";
import { textColor, bgColor, borderColor, brandGreen, functionalColor } from "../../src/theme";
import type { OrderType, PaymentMethod } from "@uniserve/shared-types";

// ── Helpers ──

function formatPrice(paisa: number): string {
  return `PKR ${Math.round(paisa / 100)}`;
}

function getCollectionSlots(operatingHours?: string, timezone?: string): string[] {
  const match = operatingHours?.match(/^(\d{2}):(\d{2})-(\d{2}):(\d{2})$/);
  if (!match) return [];

  const [, startHour, startMinute, endHour, endMinute] = match;
  const start = Number(startHour) * 60 + Number(startMinute);
  const end = Number(endHour) * 60 + Number(endMinute);

  // "Now" in the cafeteria's timezone (not the device's): a student with
  // their phone set to another timezone still sees correct local slots.
  // Falls back to Asia/Karachi (LGU) when the cafeteria has no timezone.
  const tz = timezone || "Asia/Karachi";
  let nowMinutes: number;
  try {
    const parts = new Intl.DateTimeFormat("en-GB", {
      timeZone: tz,
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).formatToParts(new Date());
    const h = Number(parts.find((p) => p.type === "hour")?.value ?? "0");
    const m = Number(parts.find((p) => p.type === "minute")?.value ?? "0");
    nowMinutes = h * 60 + m;
  } catch {
    const now = new Date();
    nowMinutes = now.getHours() * 60 + now.getMinutes();
  }

  const roundedNow = nowMinutes + 30;
  const firstSlot = Math.max(start, Math.ceil(roundedNow / 30) * 30);
  const slots: string[] = [];

  for (let minutes = firstSlot; minutes <= end; minutes += 30) {
    slots.push(`${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`);
  }
  return slots;
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
  const errorColor = functionalColor(resolvedTheme, "error");
  const errorBg = resolvedTheme === "dark" ? "#3b1515" : "#fef2f2";
  const errorBorder = resolvedTheme === "dark" ? "#5c2020" : "#fecaca";

  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("cash");
  const [orderType, setOrderType] = useState<OrderType>("immediate");
  const [scheduledTime, setScheduledTime] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [isPlacing, setIsPlacing] = useState(false);
  const [error, setError] = useState("");
  const [checkoutKey] = useState(
    () => `mobile-checkout-${Date.now()}-${Math.random().toString(36).slice(2)}`,
  );

  const items = cart?.items ?? [];
  const collectionSlots = getCollectionSlots(
    selectedCafeteria?.operating_hours,
    selectedCafeteria?.timezone
  );

  const handlePlaceOrder = useCallback(async () => {
    if (!selectedCafeteria) return;
    if (orderType === "scheduled" && !scheduledTime) {
      setError("Choose a collection time for your scheduled order.");
      return;
    }
    setIsPlacing(true);
    setError("");
    let createdOrder: { id: string } | null = null;
    try {
      const order = await checkoutCart(selectedCafeteria.id, {
        payment_method: paymentMethod,
        order_type: orderType,
        scheduled_collection_time: scheduledTime ?? undefined,
        note: note.trim() || undefined,
        idempotency_key: checkoutKey,
      });
      createdOrder = order;
      if (paymentMethod === "online") {
        const payment = await initiatePayment(order.id, checkoutKey);
        if (payment.status === "failed") {
          throw new Error(payment.message || "Online payment could not be initiated.");
        }
      }
      await refreshCart();
      router.replace(`/order/${order.id}`);
    } catch (err: any) {
      if (createdOrder) {
        // The order was already created server-side before payment initiation
        // failed (e.g. the production 503 guard). Route the user to the real
        // order so its truthful state is visible, and sync the cart — never
        // claim the payment succeeded.
        await refreshCart().catch(() => {});
        router.replace(`/order/${createdOrder.id}`);
        return;
      }
      const msg = err?.message || "Failed to place order. Please try again.";
      setError(msg);
    } finally {
      setIsPlacing(false);
    }
  }, [selectedCafeteria, paymentMethod, orderType, scheduledTime, note, checkoutKey, refreshCart, router]);

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
        {/* ── Collection Type ── */}
        <Text style={[styles.sectionTitle, { color: tc }]}>Collection</Text>
        <View style={styles.paymentOptions}>
          {(["immediate", "scheduled"] as OrderType[]).map((type) => {
            // No computable slots (missing/malformed operating hours): the
            // scheduled option would only lead to a dead-end error, so it is
            // disabled with an explanation instead of being selectable.
            const scheduledDisabled = type === "scheduled" && collectionSlots.length === 0;
            return (
            <Pressable
              key={type}
              disabled={scheduledDisabled}
              style={[
                styles.paymentOption,
                {
                  backgroundColor: bg,
                  borderColor: orderType === type ? brand : bc,
                  opacity: scheduledDisabled ? 0.5 : 1,
                },
              ]}
              onPress={() => {
                setOrderType(type);
                if (type === "immediate") setScheduledTime(null);
              }}
            >
              <Ionicons
                name={type === "immediate" ? "flash-outline" : "time-outline"}
                size={22}
                color={orderType === type ? brand : tcMuted}
              />
              <View style={styles.paymentOptionInfo}>
                <Text style={[styles.paymentOptionLabel, { color: tc }]}>
                  {type === "immediate" ? "Collect as soon as ready" : "Schedule collection"}
                </Text>
                <Text style={[styles.paymentOptionSub, { color: tcMuted }]}>
                  {type === "immediate"
                    ? "The cafeteria will prepare it now"
                    : scheduledDisabled
                      ? "Not available right now — cafeteria hours are not published"
                      : "Choose a time during cafeteria hours"}
                </Text>
              </View>
              {orderType === type && <Ionicons name="checkmark-circle" size={20} color={brand} />}
            </Pressable>
            );
          })}
        </View>

        {orderType === "scheduled" && (
          <View style={styles.slotSection}>
            <Text style={[styles.slotLabel, { color: tcMuted }]}>Collection time</Text>
            {collectionSlots.length > 0 ? (
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.slotList}>
                {collectionSlots.map((slot) => (
                  <Pressable
                    key={slot}
                    onPress={() => setScheduledTime(slot)}
                    style={[styles.slot, { backgroundColor: scheduledTime === slot ? brand : bg, borderColor: scheduledTime === slot ? brand : bc }]}
                  >
                    <Text style={[styles.slotText, { color: scheduledTime === slot ? textColor(resolvedTheme, "primary") : tc }]}>{slot}</Text>
                  </Pressable>
                ))}
              </ScrollView>
            ) : (
              <Text style={[styles.noSlotsText, { color: tcMuted }]}>No future collection times are available today.</Text>
            )}
          </View>
        )}

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
              },
            ]}
            onPress={() => setPaymentMethod("online")}
          >
            <Ionicons
              name="card-outline"
              size={22}
              color={paymentMethod === "online" ? brand : tcMuted}
            />
            <View style={styles.paymentOptionInfo}>
              <Text style={[styles.paymentOptionLabel, { color: tc }]}>Online Payment</Text>
              <Text style={[styles.paymentOptionSub, { color: tcMuted }]}>
                Secure payment through the configured provider
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
          <View style={[styles.errorBanner, { backgroundColor: errorBg, borderColor: errorBorder }]}>
            <Ionicons name="alert-circle" size={16} color={errorColor} />
            <Text style={[styles.errorText, { color: errorColor }]}>{error}</Text>
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
  slotSection: {
    marginTop: -10,
    marginBottom: 24,
  },
  slotLabel: {
    fontSize: 13,
    fontWeight: "600",
    marginBottom: 8,
  },
  slotList: {
    gap: 8,
  },
  slot: {
    minWidth: 76,
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 10,
    borderWidth: 1,
    alignItems: "center",
  },
  slotText: {
    fontSize: 14,
    fontWeight: "600",
  },
  noSlotsText: {
    fontSize: 13,
    lineHeight: 18,
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
