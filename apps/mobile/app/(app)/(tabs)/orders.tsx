/**
 * UniServe — Orders Screen
 *
 * List of user orders with status indicators.
 */
import React, { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  RefreshControl,
} from "react-native";

import { useTheme } from "../../../src/contexts/ThemeContext";
import { Card, StatusChip, Spinner, EmptyState } from "../../../src/components/ui";
import { textColor, bgColor, borderColor, colors } from "../../../src/theme";
import { getOrders, type Order } from "../../../src/services/data";

export default function OrdersScreen() {
  const { resolvedTheme } = useTheme();
  const [orders, setOrders] = useState<Order[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const tc = (variant: "primary" | "secondary" | "muted") => textColor(resolvedTheme, variant);
  const bg = (variant: "primary" | "secondary" | "tertiary") => bgColor(resolvedTheme, variant);
  const bc = (variant: "default" | "subtle") => borderColor(resolvedTheme, variant);

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

  if (isLoading) {
    return (
      <View style={[styles.screen, { backgroundColor: bg("secondary") }]}>
        <Spinner label="Loading orders..." />
      </View>
    );
  }

  return (
    <View style={[styles.screen, { backgroundColor: bg("secondary") }]}>
      <ScrollView
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={isRefreshing} onRefresh={onRefresh} colors={[colors.brand[700]]} />}
      >
        {orders.length === 0 ? (
          <EmptyState emoji="📋" title="No orders yet" description="Your order history will appear here" />
        ) : (
          orders.map((item) => (
            <Card key={item.id} style={{ marginBottom: 12, backgroundColor: bg("primary"), borderColor: bc("default") }}>
              <View style={styles.orderHeader}>
                <View style={{ flex: 1 }}>
                  <Text style={{ color: tc("primary"), fontSize: 16, fontWeight: "600" }}>
                    {item.order_number}
                  </Text>
                  <Text style={{ color: tc("muted"), fontSize: 12, marginTop: 2 }}>
                    {item.cafeteria_name} · {item.items?.length ?? 0} items
                  </Text>
                </View>
                <StatusChip status={item.status as any} />
              </View>
              <View style={[styles.orderFooter, { borderTopColor: bc("subtle") }]}>
                <Text style={{ color: tc("secondary"), fontSize: 14, fontWeight: "600" }}>
                  {item.currency} {item.total_amount}
                </Text>
                <Text style={{ color: tc("muted"), fontSize: 12 }}>
                  {new Date(item.created_at).toLocaleDateString()}
                </Text>
              </View>
            </Card>
          ))
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
  },
  list: {
    padding: 16,
    paddingBottom: 32,
  },
  orderCard: {
    marginBottom: 12,
  },
  orderHeader: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
  },
  orderFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
});
