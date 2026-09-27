/**
 * UniServe — Order Detail Screen
 *
 * Shows order status, items, and pickup QR code.
 * Uses OrderStatusTimeline for status visualization.
 */
import React, { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  Pressable,
  ActivityIndicator,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

import { useTheme } from "../../../src/contexts/ThemeContext";
import { getOrder } from "../../../src/services/data";
import { textColor, bgColor, borderColor, brandGreen, functionalColor } from "../../../src/theme";
import type { Order, OrderStatus } from "@uniserve/shared-types";

// ── Helpers ──

function formatPrice(paisa: number): string {
  return `PKR ${Math.round(paisa / 100)}`;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

const STATUS_CONFIG: Record<OrderStatus, { label: string; icon: keyof typeof Ionicons.glyphMap; colorKey: "success" | "warning" | "error" | "info" }> = {
  pending: { label: "Pending", icon: "time-outline", colorKey: "warning" },
  preparing: { label: "Preparing", icon: "flame-outline", colorKey: "info" },
  ready: { label: "Ready for Pickup", icon: "checkmark-circle-outline", colorKey: "success" },
  completed: { label: "Completed", icon: "checkmark-done-circle-outline", colorKey: "success" },
  cancelled: { label: "Cancelled", icon: "close-circle-outline", colorKey: "error" },
};

const STATUS_ORDER: OrderStatus[] = ["pending", "preparing", "ready", "completed"];

// ── Status Timeline ──

interface TimelineProps {
  currentStatus: OrderStatus;
  theme: "light" | "dark";
}

function OrderStatusTimeline({ currentStatus, theme }: TimelineProps) {
  const brand = brandGreen(theme);
  const tc = textColor(theme, "primary");
  const tcMuted = textColor(theme, "muted");
  const bg = bgColor(theme, "secondary");
  const bc = borderColor(theme, "default");

  const currentIdx = STATUS_ORDER.indexOf(currentStatus as any);
  const isCancelled = currentStatus === "cancelled";
  const isCompleted = currentStatus === "completed";

  return (
    <View style={[styles.timelineCard, { backgroundColor: bg, borderColor: bc }]}>
      {STATUS_ORDER.map((status, idx) => {
        const config = STATUS_CONFIG[status];
        const isActive = idx === currentIdx;
        const isPast = !isCancelled && idx < currentIdx;
        const isFuture = !isCancelled && idx > currentIdx;

        return (
          <View key={status} style={styles.timelineStep}>
            {/* Icon + line */}
            <View style={styles.timelineIconCol}>
              <View
                style={[
                  styles.timelineIcon,
                  {
                    backgroundColor: isPast || isActive ? brand : bg,
                    borderColor: isPast || isActive ? brand : bc,
                  },
                ]}
              >
                <Ionicons
                  name={isPast ? "checkmark" : config.icon}
                  size={14}
                  color={isPast || isActive ? "#ffffff" : tcMuted}
                />
              </View>
              {idx < STATUS_ORDER.length - 1 && (
                <View
                  style={[
                    styles.timelineLine,
                    { backgroundColor: isPast ? brand : bc },
                  ]}
                />
              )}
            </View>

            {/* Label */}
            <View style={styles.timelineLabelCol}>
              <Text
                style={[
                  styles.timelineLabel,
                  {
                    color: isActive ? tc : isPast ? brand : tcMuted,
                    fontWeight: isActive ? "700" : "500",
                  },
                ]}
              >
                {config.label}
              </Text>
            </View>
          </View>
        );
      })}

      {/* Cancelled override */}
      {isCancelled && (
        <View style={[styles.cancelledBanner, { borderColor: functionalColor(theme, "error") + "30" }]}>
          <Ionicons name="close-circle" size={16} color={functionalColor(theme, "error")} />
          <Text style={[styles.cancelledText, { color: functionalColor(theme, "error") }]}>
            This order was cancelled
          </Text>
        </View>
      )}
    </View>
  );
}

// ── Screen ──

export default function OrderDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { resolvedTheme } = useTheme();
  const router = useRouter();

  const brand = brandGreen(resolvedTheme);
  const tc = textColor(resolvedTheme, "primary");
  const tcSec = textColor(resolvedTheme, "secondary");
  const tcMuted = textColor(resolvedTheme, "muted");
  const bg = bgColor(resolvedTheme, "primary");
  const bgSec = bgColor(resolvedTheme, "secondary");
  const bc = borderColor(resolvedTheme, "default");
  const bcSub = borderColor(resolvedTheme, "subtle");

  const [order, setOrder] = useState<Order | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    (async () => {
      try {
        const data = await getOrder(id);
        setOrder(data);
      } catch {
        setError("Failed to load order");
      } finally {
        setIsLoading(false);
      }
    })();
  }, [id]);

  if (isLoading) {
    return (
      <View style={[styles.screen, { backgroundColor: bg }]}>
        <View style={styles.loadingCenter}>
          <ActivityIndicator size="large" color={brand} />
        </View>
      </View>
    );
  }

  if (error || !order) {
    return (
      <View style={[styles.screen, { backgroundColor: bg }]}>
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle-outline" size={48} color={functionalColor(resolvedTheme, "error")} />
          <Text style={[styles.errorTitle, { color: tc }]}>{error || "Order not found"}</Text>
          <Pressable onPress={() => router.back()}>
            <Text style={[styles.errorLink, { color: brand }]}>Go back</Text>
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
        {/* ── Status Header ── */}
        <View style={[styles.statusHeader, { backgroundColor: bg, borderColor: bc }]}>
          <Text style={[styles.orderNumber, { color: tc }]}>
            Order #{order.order_number}
          </Text>
          <Text style={[styles.orderDate, { color: tcMuted }]}>
            {formatDate(order.created_at)}
          </Text>
        </View>

        {/* ── Status Timeline ── */}
        <OrderStatusTimeline
          currentStatus={order.status}
          theme={resolvedTheme as "light" | "dark"}
        />

        {/* ── Pickup QR (only when ready) ── */}
        {order.status === "ready" && (
          <Pressable
            style={[styles.qrBanner, { backgroundColor: brand + "10", borderColor: brand + "30" }]}
            onPress={() => router.push(`/order/${order.id}/qr`)}
          >
            <Ionicons name="qr-code-outline" size={24} color={brand} />
            <View style={styles.qrBannerText}>
              <Text style={[styles.qrBannerTitle, { color: brand }]}>Show Pickup QR Code</Text>
              <Text style={[styles.qrBannerSub, { color: tcMuted }]}>Tap to view</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={brand} />
          </Pressable>
        )}

        {/* ── Items ── */}
        <Text style={[styles.sectionTitle, { color: tc }]}>Items</Text>
        <View style={[styles.itemsCard, { backgroundColor: bg, borderColor: bc }]}>
          {order.items.map((item) => (
            <View key={item.id} style={styles.itemRow}>
              <View style={styles.itemInfo}>
                <Text style={[styles.itemQty, { color: tcMuted }]}>
                  {item.quantity}×
                </Text>
                <Text style={[styles.itemName, { color: tc }]} numberOfLines={1}>
                  {item.item_name}
                </Text>
              </View>
              <Text style={[styles.itemPrice, { color: tc }]}>
                {formatPrice(item.subtotal)}
              </Text>
            </View>
          ))}

          <View style={[styles.itemsDivider, { backgroundColor: bcSub }]} />

          <View style={styles.itemRow}>
            <Text style={[styles.totalLabel, { color: tc }]}>Total</Text>
            <Text style={[styles.totalValue, { color: brand }]}>
              {formatPrice(order.total_amount)}
            </Text>
          </View>
        </View>

        {/* ── Payment Info ── */}
        <View style={[styles.infoRow, { backgroundColor: bg, borderColor: bc }]}>
          <Ionicons
            name={order.payment_method === "cash" ? "cash-outline" : "card-outline"}
            size={18}
            color={tcMuted}
          />
          <Text style={[styles.infoLabel, { color: tcMuted }]}>Payment</Text>
          <Text style={[styles.infoValue, { color: tc }]}>
            {order.payment_method === "cash" ? "Pay at Counter" : "Online"}
          </Text>
        </View>

        {order.note && (
          <View style={[styles.infoRow, { backgroundColor: bg, borderColor: bc }]}>
            <Ionicons name="chatbubble-outline" size={18} color={tcMuted} />
            <Text style={[styles.infoLabel, { color: tcMuted }]}>Note</Text>
            <Text style={[styles.infoValue, { color: tc }]} numberOfLines={2}>
              {order.note}
            </Text>
          </View>
        )}

        {/* ── ETA ── */}
        {order.eta_minutes && order.status === "preparing" && (
          <View style={[styles.etaBanner, { backgroundColor: brand + "10", borderColor: brand + "30" }]}>
            <Ionicons name="time-outline" size={18} color={brand} />
            <Text style={[styles.etaText, { color: brand }]}>
              Estimated {order.eta_minutes} minutes
            </Text>
          </View>
        )}

        <View style={{ height: 32 }} />
      </ScrollView>
    </View>
  );
}

// ── Styles ──

const styles = StyleSheet.create({
  screen: { flex: 1 },
  loadingCenter: { flex: 1, alignItems: "center", justifyContent: "center" },
  errorContainer: { flex: 1, alignItems: "center", justifyContent: "center", padding: 32, gap: 12 },
  errorTitle: { fontSize: 18, fontWeight: "600", textAlign: "center" },
  errorLink: { fontSize: 15, fontWeight: "600" },
  scrollContent: { padding: 16 },

  // Status header
  statusHeader: {
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 16,
  },
  orderNumber: { fontSize: 18, fontWeight: "700" },
  orderDate: { fontSize: 13, marginTop: 4 },

  // Timeline
  timelineCard: {
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 16,
  },
  timelineStep: {
    flexDirection: "row",
    alignItems: "flex-start",
  },
  timelineIconCol: {
    alignItems: "center",
    width: 28,
  },
  timelineIcon: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 1.5,
    alignItems: "center",
    justifyContent: "center",
  },
  timelineLine: {
    width: 2,
    height: 20,
    marginVertical: 4,
  },
  timelineLabelCol: {
    flex: 1,
    paddingLeft: 10,
    paddingVertical: 3,
  },
  timelineLabel: { fontSize: 14 },
  cancelledBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: 12,
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    backgroundColor: "#FEE2E220",
  },
  cancelledText: { fontSize: 13, fontWeight: "600" },

  // QR banner
  qrBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    padding: 14,
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 16,
  },
  qrBannerText: { flex: 1 },
  qrBannerTitle: { fontSize: 14, fontWeight: "600" },
  qrBannerSub: { fontSize: 12, marginTop: 2 },

  // Items
  sectionTitle: { fontSize: 16, fontWeight: "700", marginBottom: 10 },
  itemsCard: {
    padding: 14,
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 16,
  },
  itemRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 4,
  },
  itemInfo: { flexDirection: "row", alignItems: "center", gap: 6, flex: 1 },
  itemQty: { fontSize: 13, fontWeight: "500", width: 28 },
  itemName: { fontSize: 14, flex: 1 },
  itemPrice: { fontSize: 14, fontWeight: "500" },
  itemsDivider: { height: StyleSheet.hairlineWidth, marginVertical: 10 },
  totalLabel: { fontSize: 16, fontWeight: "700" },
  totalValue: { fontSize: 18, fontWeight: "700" },

  // Info rows
  infoRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    marginBottom: 8,
  },
  infoLabel: { fontSize: 13, width: 60 },
  infoValue: { fontSize: 14, fontWeight: "500", flex: 1 },

  // ETA
  etaBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    marginTop: 4,
  },
  etaText: { fontSize: 14, fontWeight: "600" },
});
