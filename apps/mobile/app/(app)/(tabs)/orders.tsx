/**
 * UniServe — Orders Screen
 *
 * List of user orders with status indicators, pull-to-refresh,
 * skeleton loading, and clickable rows navigating to order detail.
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
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";

import { useTheme } from "../../../src/contexts/ThemeContext";
import { getOrders, getCafeterias } from "../../../src/services/data";
import { textColor, bgColor, borderColor, brandGreen, functionalColor } from "../../../src/theme";
import type { Order, OrderStatus, Cafeteria } from "@uniserve/shared-types";

// ── Helpers ──

function formatPrice(paisa: number): string {
  return `PKR ${Math.round(paisa / 100)}`;
}

function formatOrderDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

/** Summarise the items on an order card, e.g. "Chicken Karahi ×2 · Fries" */
function itemNamesSummary(order: Order): string {
  const names = (order.items ?? []).map((i) =>
    i.quantity > 1 ? `${i.item_name} ×${i.quantity}` : i.item_name,
  );
  if (names.length === 0) return "No items";
  return names.join(" · ");
}

const STATUS_STYLE: Record<OrderStatus, { label: string; icon: keyof typeof Ionicons.glyphMap; colorKey: "success" | "warning" | "error" | "info" }> = {
  pending: { label: "Pending", icon: "time-outline", colorKey: "warning" },
  preparing: { label: "Preparing", icon: "flame-outline", colorKey: "info" },
  ready: { label: "Ready", icon: "checkmark-circle-outline", colorKey: "success" },
  completed: { label: "Completed", icon: "checkmark-done-outline", colorKey: "success" },
  cancelled: { label: "Cancelled", icon: "close-circle-outline", colorKey: "error" },
};

// ── Skeleton ──

function OrderSkeleton({ bg, bc }: { bg: string; bc: string }) {
  return (
    <View style={[styles.skeletonCard, { backgroundColor: bg, borderColor: bc }]}>
      <View style={styles.skeletonRow}>
        <View style={[styles.skeletonBlock, { width: 80, height: 16, backgroundColor: bc }]} />
        <View style={[styles.skeletonBlock, { width: 60, height: 20, borderRadius: 10, backgroundColor: bc }]} />
      </View>
      <View style={[styles.skeletonBlock, { width: 140, height: 12, backgroundColor: bc, marginTop: 10 }]} />
      <View style={[styles.skeletonBlock, { width: 100, height: 12, backgroundColor: bc, marginTop: 8 }]} />
    </View>
  );
}

// ── Screen ──

export default function OrdersScreen() {
  const { resolvedTheme } = useTheme();
  const router = useRouter();
  const [orders, setOrders] = useState<Order[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState("");
  // id → name, so each card can show which cafeteria the order was from.
  const [cafeteriaNames, setCafeteriaNames] = useState<Record<string, string>>({});
  // Lookback window in days (backend supports 1-90). The scope is explicit
  // in the UI so the 7-day default is never a silent limit.
  const [days, setDays] = useState(7);

  const brand = brandGreen(resolvedTheme);
  const tc = textColor(resolvedTheme, "primary");
  const tcMuted = textColor(resolvedTheme, "muted");
  const bg = bgColor(resolvedTheme, "primary");
  const bgSec = bgColor(resolvedTheme, "secondary");
  const bc = borderColor(resolvedTheme, "default");
  const bcSub = borderColor(resolvedTheme, "subtle");

  const loadOrders = useCallback(async () => {
    try {
      setError("");
      const data = await getOrders({ days });
      setOrders(data);
    } catch {
      setError("Failed to load order history.");
    }
  }, [days]);

  useEffect(() => {
    loadOrders().finally(() => setIsLoading(false));
  }, [loadOrders]);

  // Load the id → name map used for the per-card cafeteria label. Best-effort:
  // if this fails the cards simply omit the name, so it never surfaces as an
  // order-history error.
  useEffect(() => {
    let mounted = true;
    getCafeterias()
      .then((list: Cafeteria[]) => {
        if (!mounted) return;
        const map: Record<string, string> = {};
        for (const c of list) map[c.id] = c.name;
        setCafeteriaNames(map);
      })
      .catch(() => undefined);
    return () => {
      mounted = false;
    };
  }, []);

  const onRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await loadOrders();
    setIsRefreshing(false);
  }, [loadOrders]);

  return (
    <SafeAreaView edges={["top"]} style={[styles.screen, { backgroundColor: bgSec }]}>
      <ScrollView
        contentContainerStyle={styles.list}
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
        <View style={styles.screenHeader}>
          <Text style={[styles.screenTitle, { color: tc }]}>Order history</Text>
          <Text style={[styles.screenSubtitle, { color: tcMuted }]}>UniServe · your recent orders</Text>
        </View>
        {/* Lookback scope — explicit so the default window is never silent */}
        <View style={styles.scopeRow}>
          {([7, 30, 90] as const).map((d) => {
            const selected = days === d;
            return (
              <Pressable
                key={d}
                accessibilityRole="button"
                accessibilityLabel={`Show orders from the last ${d} days`}
                accessibilityState={{ selected }}
                onPress={() => setDays(d)}
                style={[
                  styles.scopeChip,
                  { borderColor: selected ? brand : bc, backgroundColor: selected ? brand + "14" : "transparent" },
                ]}
              >
                <Text style={[styles.scopeChipText, { color: selected ? brand : tcMuted }]}>
                  {d === 90 ? "3 months" : `${d} days`}
                </Text>
              </Pressable>
            );
          })}
        </View>
        {isLoading ? (
          <>
            <OrderSkeleton bg={bg} bc={bc} />
            <OrderSkeleton bg={bg} bc={bc} />
            <OrderSkeleton bg={bg} bc={bc} />
          </>
        ) : error ? (
          <View style={styles.errorContainer}>
            <Ionicons name="cloud-offline-outline" size={48} color={tcMuted} />
            <Text style={[styles.emptyTitle, { color: tc }]}>Order history unavailable</Text>
            <Text style={[styles.emptyDesc, { color: tcMuted }]}>{error}</Text>
            <Pressable onPress={loadOrders}>
              <Text style={[styles.retryText, { color: brand }]}>Try again</Text>
            </Pressable>
          </View>
        ) : orders.length === 0 ? (
          <View style={styles.emptyContainer}>
            <Ionicons name="receipt-outline" size={48} color={tcMuted} />
            <Text style={[styles.emptyTitle, { color: tc }]}>No orders yet</Text>
            <Text style={[styles.emptyDesc, { color: tcMuted }]}>
              Your order history will appear here
            </Text>
          </View>
        ) : (
          orders.map((order) => {
            const orderStatus = order.status as OrderStatus;
            const statusCfg = STATUS_STYLE[orderStatus] ?? STATUS_STYLE.pending;
            const statusColor = functionalColor(resolvedTheme, statusCfg.colorKey);
            // A pending order that staff have confirmed is a distinct sub-state.
            // Fold it into the single status pill (label + icon) rather than
            // rendering a second "Confirmed" chip, so each card shows exactly
            // one status.
            const isConfirmedPending =
              orderStatus === "pending" && !!order.confirmed_at;
            const pillLabel = isConfirmedPending
              ? "Confirmed"
              : statusCfg.label;
            const pillIcon: keyof typeof Ionicons.glyphMap =
              isConfirmedPending ? "shield-checkmark-outline" : statusCfg.icon;
            const cafeteriaName = cafeteriaNames[order.cafeteria_id];

            return (
              <Pressable
                key={order.id}
                style={[styles.orderCard, { backgroundColor: bg, borderColor: bc }]}
                onPress={() => router.push(`/order/${order.id}`)}
              >
                {/* Header row */}
                <View style={styles.orderHeader}>
                  <View style={styles.orderHeaderLeft}>
                    <Text style={[styles.orderNumber, { color: tc }]}>
                      #{order.order_number}
                    </Text>
                    {cafeteriaName ? (
                      <Text numberOfLines={1} ellipsizeMode="tail" style={[styles.orderCafeteria, { color: tcMuted }]}>
                        {cafeteriaName}
                      </Text>
                    ) : null}
                  </View>
                  <View style={styles.badgeRow}>
                    <View style={[styles.statusBadge, { backgroundColor: statusColor + "15" }]}>
                      <Ionicons name={pillIcon} size={12} color={statusColor} />
                      <Text style={[styles.statusLabel, { color: statusColor }]}>
                        {pillLabel}
                      </Text>
                    </View>
                  </View>
                </View>

                {/* Item names */}
                <Text numberOfLines={2} ellipsizeMode="tail" style={[styles.orderItems, { color: tcMuted }]}>
                  {itemNamesSummary(order)}
                </Text>

                {/* Footer row */}
                <View style={[styles.orderFooter, { borderTopColor: bcSub }]}>
                  <Text style={[styles.orderTotal, { color: tc }]}>
                    {formatPrice(order.total_amount)}
                  </Text>
                  <Text style={[styles.orderDate, { color: tcMuted }]}>
                    {formatOrderDate(order.created_at)}
                  </Text>
                </View>
              </Pressable>
            );
          })
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

// ── Styles ──

const styles = StyleSheet.create({
  screen: { flex: 1 },
  list: { paddingHorizontal: 20, paddingTop: 20, paddingBottom: 32 },
  screenHeader: { marginBottom: 12 },
  screenTitle: { fontSize: 28, fontWeight: "700", lineHeight: 34 },
  screenSubtitle: { fontSize: 13, marginTop: 4 },
  scopeRow: { flexDirection: "row", gap: 8, marginBottom: 18 },
  scopeChip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
  },
  scopeChipText: { fontSize: 13, fontWeight: "600" },

  // Empty
  emptyContainer: {
    alignItems: "center",
    paddingTop: 88,
    gap: 8,
  },
  emptyTitle: { fontSize: 18, fontWeight: "600" },
  emptyDesc: { fontSize: 14 },
  errorContainer: {
    alignItems: "center",
    paddingTop: 88,
    gap: 8,
  },
  retryText: { fontSize: 14, fontWeight: "600", marginTop: 4 },

  // Skeleton
  skeletonCard: {
    padding: 14,
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 12,
    opacity: 0.5,
  },
  skeletonRow: { flexDirection: "row", justifyContent: "space-between" },
  skeletonBlock: { borderRadius: 4 },

  // Order card
  orderCard: {
    padding: 14,
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 10,
  },
  orderHeader: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
  },
  orderHeaderLeft: { flex: 1, gap: 2 },
  orderNumber: { fontSize: 16, fontWeight: "700" },
  orderCafeteria: { fontSize: 12 },
  statusBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 10,
  },
  statusLabel: { fontSize: 11, fontWeight: "600" },
  orderItems: { fontSize: 12, lineHeight: 17, marginTop: 8 },
  badgeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    flexShrink: 1,
    flexWrap: "wrap",
    justifyContent: "flex-end",
  },
  orderFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  orderTotal: { fontSize: 14, fontWeight: "600" },
  orderDate: { fontSize: 12 },
});
