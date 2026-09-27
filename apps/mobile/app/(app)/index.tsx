/**
 * UniServe — Home Screen (Authenticated)
 *
 * Dashboard showing quick stats, recent orders, and notifications.
 */
import React, { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  RefreshControl,
  TouchableOpacity,
} from "react-native";

import { useAuth } from "../../src/contexts/AuthContext";
import { useTheme } from "../../src/contexts/ThemeContext";
import { LguSeal } from "../../src/components/LguSeal";
import { Card, CardHeader, Spinner, EmptyState, StatusChip } from "../../src/components/ui";
import { textColor, bgColor, borderColor, colors } from "../../src/theme";
import { getOrders, getNotifications, type Order, type Notification } from "../../src/services/data";

export default function HomeScreen() {
  const { user, logout } = useAuth();
  const { resolvedTheme, themePreference, setThemePreference } = useTheme();
  const [orders, setOrders] = useState<Order[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState("");

  const tc = (variant: "primary" | "secondary" | "muted") => textColor(resolvedTheme, variant);
  const bg = (variant: "primary" | "secondary" | "tertiary") => bgColor(resolvedTheme, variant);
  const bc = (variant: "default" | "subtle") => borderColor(resolvedTheme, variant);

  const loadData = useCallback(async () => {
    try {
      setError("");
      const [ordersRes, notifsRes] = await Promise.allSettled([
        getOrders({ limit: 5 }),
        getNotifications({ limit: 5 }),
      ]);
      if (ordersRes.status === "fulfilled") setOrders(ordersRes.value);
      if (notifsRes.status === "fulfilled") setNotifications(notifsRes.value);
    } catch {
      setError("Failed to load data");
    }
  }, []);

  useEffect(() => {
    loadData().finally(() => setIsLoading(false));
  }, [loadData]);

  const onRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await loadData();
    setIsRefreshing(false);
  }, [loadData]);

  // Time-based greeting
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  if (isLoading) {
    return (
      <View style={[styles.screen, { backgroundColor: bg("secondary") }]}>
        <Spinner label="Loading dashboard..." />
      </View>
    );
  }

  return (
    <ScrollView
      style={[styles.screen, { backgroundColor: bg("secondary") }]}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={isRefreshing} onRefresh={onRefresh} colors={[colors.brand[700]]} />}
    >
      {/* Welcome Header */}
      <View style={styles.welcomeSection}>
        <LguSeal size="sm" />
        <View style={styles.welcomeText}>
          <Text style={[styles.greeting, { color: tc("primary") }]}>
            {greeting}, {user?.first_name ?? "User"}
          </Text>
          <Text style={[styles.email, { color: tc("muted") }]}>{user?.university_email}</Text>
          <View style={[styles.roleBadge, { backgroundColor: colors.brand[700] + "20" }]}>
            <Text style={[styles.roleText, { color: colors.brand[700] }]}>
              {user?.role?.replace("_", " ").toUpperCase() ?? "USER"}
            </Text>
          </View>
        </View>
      </View>

      {/* Theme Toggle */}
      <Card style={{ backgroundColor: bg("primary"), borderColor: bc("default") }}>
        <View style={styles.themeRow}>
          <Text style={{ color: tc("primary"), fontSize: 14, fontWeight: "500" }}>Theme</Text>
          <View style={styles.themeButtons}>
            {(["light", "dark", "system"] as const).map((t) => (
              <TouchableOpacity
                key={t}
                onPress={() => setThemePreference(t)}
                style={[
                  styles.themeBtn,
                  themePreference === t && { backgroundColor: colors.brand[700] },
                  { borderColor: bc("default") },
                ]}
              >
                <Text
                  style={{
                    color: themePreference === t ? "#fff" : tc("secondary"),
                    fontSize: 12,
                    fontWeight: "500",
                    textTransform: "capitalize",
                  }}
                >
                  {t === "light" ? "☀️" : t === "dark" ? "🌙" : "💻"} {t}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      </Card>

      {/* Recent Orders */}
      <Card style={{ backgroundColor: bg("primary"), borderColor: bc("default") }}>
        <CardHeader title="Recent Orders" />
        {orders.length === 0 ? (
          <EmptyState emoji="📋" title="No orders yet" description="Your orders will appear here" />
        ) : (
          orders.slice(0, 3).map((order) => (
            <View key={order.id} style={[styles.orderRow, { borderBottomColor: bc("subtle") }]}>
              <View style={{ flex: 1 }}>
                <Text style={{ color: tc("primary"), fontSize: 14, fontWeight: "500" }}>
                  {order.order_number}
                </Text>
                <Text style={{ color: tc("muted"), fontSize: 12, marginTop: 2 }}>
                  {order.items?.length ?? 0} items · {order.currency} {order.total_amount}
                </Text>
              </View>
              <StatusChip status={order.status as any} />
            </View>
          ))
        )}
      </Card>

      {/* Notifications */}
      <Card style={{ backgroundColor: bg("primary"), borderColor: bc("default") }}>
        <CardHeader title="Notifications" />
        {notifications.length === 0 ? (
          <EmptyState emoji="🔔" title="No notifications" description="You're all caught up" />
        ) : (
          notifications.slice(0, 3).map((notif) => (
            <View key={notif.id} style={[styles.notifRow, { borderBottomColor: bc("subtle") }]}>
              {!notif.is_read && <View style={styles.unreadDot} />}
              <View style={{ flex: 1 }}>
                <Text style={{ color: tc("primary"), fontSize: 14, fontWeight: "500" }}>
                  {notif.title}
                </Text>
                <Text style={{ color: tc("muted"), fontSize: 12, marginTop: 2 }} numberOfLines={2}>
                  {notif.body}
                </Text>
              </View>
            </View>
          ))
        )}
      </Card>

      {/* Logout */}
      <TouchableOpacity style={styles.logoutBtn} onPress={logout}>
        <Text style={styles.logoutText}>Sign Out</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
  },
  content: {
    padding: 16,
    paddingBottom: 32,
  },
  welcomeSection: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 20,
    gap: 12,
  },
  welcomeText: {
    flex: 1,
  },
  greeting: {
    fontSize: 22,
    fontWeight: "700",
    letterSpacing: -0.3,
  },
  email: {
    fontSize: 13,
    marginTop: 2,
  },
  roleBadge: {
    alignSelf: "flex-start",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    marginTop: 6,
  },
  roleText: {
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.5,
  },
  themeRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  themeButtons: {
    flexDirection: "row",
    gap: 6,
  },
  themeBtn: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    borderWidth: 1,
  },
  orderRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    gap: 8,
  },
  notifRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    gap: 8,
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.info,
    marginTop: 4,
  },
  logoutBtn: {
    marginTop: 24,
    padding: 14,
    borderRadius: 8,
    backgroundColor: "#fef2f2",
    borderWidth: 1,
    borderColor: "#fecaca",
    alignItems: "center",
  },
  logoutText: {
    color: "#991b1b",
    fontSize: 14,
    fontWeight: "600",
  },
});
