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

import { useTheme } from "../../../src/contexts/ThemeContext";
import { getOrders } from "../../../src/services/data";
import { textColor, bgColor, borderColor, brandGreen, functionalColor } from "../../../src/theme";
import type { Order, OrderStatus } from "@uniserve/shared-types";

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

  const brand = brandGreen(resolvedTheme);
  const tc = textColor(resolvedTheme, "primary");
  const tcMuted = textColor(resolvedTheme, "muted");
  const bg = bgColor(resolvedTheme, "primary");
  const bgSec = bgColor(resolvedTheme, "secondary");
  const bc = borderColor(resolvedTheme, "default");
  const bcSub = borderColor(resolvedTheme, "subtle");

  const loadOrders = useCallback(async () => {
    try {
      const data = await getOrders({ limit: 20 });
      setOrders(data);
    } catch {
      // Silent fail
    }
  }, []);

  useEffect(() => {
    loadOrders().finally(() => setIsLoading(false));
  }, [loadOrders]);

  const onRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await loadOrders();
    setIsRefreshing(false);
  }, [loadOrders]);

  return (
    <View style={[styles.screen, { backgroundColor: bgSec }]}>
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
        {isLoading ? (
          <>
            <OrderSkeleton bg={bg} bc={bc} />
            <OrderSkeleton bg={bg} bc={bc} />
            <OrderSkeleton bg={bg} bc={bc} />
          </>
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
            const statusCfg = STATUS_STYLE[order.status as OrderStatus] ?? STATUS_STYLE.pending;
            const statusColor = functionalColor(resolvedTheme, statusCfg.colorKey);

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
                    <Text style={[styles.orderCafeteria, { color: tcMuted }]}>
                      {order.items?.length ?? 0} {(order.items?.length ?? 0) === 1 ? "item" : "items"}
                    </Text>
                  </View>
                  <View style={[styles.statusBadge, { backgroundColor: statusColor + "15" }]}>
                    <Ionicons name={statusCfg.icon} size={12} color={statusColor} />
                    <Text style={[styles.statusLabel, { color: statusColor }]}>
                      {statusCfg.label}
                    </Text>
                  </View>
                </View>

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
    </View>
  );
}

// ── Styles ──

const styles = StyleSheet.create({
  screen: { flex: 1 },
  list: { padding: 16, paddingBottom: 32 },

  // Empty
  emptyContainer: {
    alignItems: "center",
    paddingTop: 120,
    gap: 8,
  },
  emptyTitle: { fontSize: 18, fontWeight: "600" },
  emptyDesc: { fontSize: 14 },

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
