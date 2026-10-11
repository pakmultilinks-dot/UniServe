/**
 * UniServe — Notifications Inbox (Phase 53)
 *
 * The mobile consumption surface for the existing in-app notification system
 * (Phase 50 broadcast + order lifecycle notifications). Students and faculty
 * are the intended audience; before this screen the backend wrote rows that
 * no mobile UI could display.
 *
 * Contract reused as-is (no new backend work):
 * - GET  /notifications            → list (user-scoped server-side)
 * - GET  /notifications/unread-count → authoritative badge count
 * - PATCH /notifications/{id}/read → mark one read (ownership verified → 404)
 * - PATCH /notifications/read-all  → mark all read (scoped UPDATE)
 *
 * Behavior mirrors the web notification center terminology (unread tint +
 * green dot, relative timestamps, "Mark All Read" only when unread > 0) and
 * the established mobile patterns: ActivityIndicator loading, ErrorState with
 * retry, EmptyState, RefreshControl pull-to-refresh, Toast for action
 * failures. Unread state updates only AFTER a successful request — a failed
 * mark-read surfaces visibly and never pretends the row was read.
 */
import React, { useCallback, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  RefreshControl,
  Pressable,
  ActivityIndicator,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";

import { useTheme } from "../../../src/contexts/ThemeContext";
import { useNotifications } from "../../../src/contexts/NotificationsContext";
import {
  getNotificationsPage,
  markNotificationRead,
  markAllNotificationsRead,
  type Notification,
} from "../../../src/services/data";
import { ApiClientError } from "../../../src/services/api";
import { Button, EmptyState, ErrorState, Toast } from "../../../src/components/ui";
import { bgColor, brandGreen, textColor } from "../../../src/theme";

type IoniconName = React.ComponentProps<typeof Ionicons>["name"];

/** Type → icon mapping, mirroring the web notification center's TYPE_ICONS. */
const TYPE_ICONS: Record<string, IoniconName> = {
  order_created: "receipt-outline",
  order_confirmed: "checkmark-circle-outline",
  order_rejected: "close-circle-outline",
  preparation_started: "flame-outline",
  order_ready: "notifications-outline",
  order_cancelled: "ban-outline",
  order_delayed: "time-outline",
  order_uncollected: "bag-handle-outline",
  cafeteria_closed: "storefront-outline",
  payment_confirmed: "card-outline",
  refund_requested: "return-down-back-outline",
  refund_processed: "cash-outline",
  refund_failed: "alert-circle-outline",
  refund_rejected: "close-circle-outline",
  admin_announcement: "megaphone-outline",
};

/** Same relative-time wording as the web notification center's formatDate. */
function formatTimeAgo(iso: string): string {
  try {
    const d = new Date(iso);
    const diff = Date.now() - d.getTime();
    if (diff < 60_000) return "Just now";
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return iso;
  }
}

function apiErrorMessage(err: unknown): string {
  return err instanceof ApiClientError ? err.message : "Please try again";
}

export default function NotificationsScreen() {
  const { resolvedTheme } = useTheme();
  // Single source of truth for the unread badge: the NotificationsContext.
  // The list endpoint (GET /notifications) already returns `unread_count`, so
  // every local change here is mirrored into the context instead of triggering
  // a second refetch — Home bell, Orders, Favorites and Profile all read the
  // same value.
  const { unreadCount, setUnreadCount } = useNotifications();

  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [markBusyId, setMarkBusyId] = useState<string | null>(null);
  const [markAllBusy, setMarkAllBusy] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(
    null,
  );

  const brand = brandGreen(resolvedTheme);
  const tc = textColor(resolvedTheme, "primary");
  const tcMuted = textColor(resolvedTheme, "muted");
  const bg = bgColor(resolvedTheme, "primary");

  const loadNotifications = useCallback(
    async (silent: boolean) => {
      if (silent) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      try {
        const data = await getNotificationsPage({ limit: 50 });
        setNotifications(data.items ?? []);
        setUnreadCount(data.unread_count ?? 0);
        setLoadError(null);
        // `unreadCount` from the list fetch already flows into the shared
        // context above — no second round-trip needed.
      } catch (err) {
        if (silent && notifications.length > 0) {
          // Pull-to-refresh failure with data on screen: keep the list,
          // surface the failure — never a silent stale view.
          setToast({ message: "Couldn't refresh notifications", type: "error" });
        } else {
          // "No notifications" must only ever be shown for a genuinely
          // empty result — a failed fetch gets the explicit error state.
          setLoadError(apiErrorMessage(err));
        }
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    // notifications.length is read only for the silent-refresh branch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  useFocusEffect(
    useCallback(() => {
      loadNotifications(false);
    }, [loadNotifications]),
  );

  const onRefresh = useCallback(() => {
    loadNotifications(true);
  }, [loadNotifications]);

  const handleMarkRead = async (notification: Notification) => {
    if (notification.is_read || markBusyId) return;
    setMarkBusyId(notification.id);
    try {
      await markNotificationRead(notification.id);
      // Update UI only after a successful request — never pretend success.
      setNotifications((prev) =>
        prev.map((n) => (n.id === notification.id ? { ...n, is_read: true } : n)),
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch (err) {
      setToast({ message: `Couldn't mark as read — ${apiErrorMessage(err)}`, type: "error" });
    } finally {
      setMarkBusyId(null);
    }
  };

  const handleMarkAllRead = async () => {
    if (markAllBusy || unreadCount === 0) return;
    setMarkAllBusy(true);
    try {
      await markAllNotificationsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch (err) {
      setToast({ message: `Couldn't mark all as read — ${apiErrorMessage(err)}`, type: "error" });
    } finally {
      setMarkAllBusy(false);
    }
  };

  const showSpinner = loading && !refreshing && notifications.length === 0;

  return (
    <SafeAreaView edges={["top"]} style={[styles.screen, { backgroundColor: bg }]}>
      <Toast
        message={toast?.message ?? ""}
        type={toast?.type ?? "info"}
        visible={toast !== null}
        onDismiss={() => setToast(null)}
      />

      {/* Header — mirrors web terminology: unread count + Mark All Read */}
      <View style={styles.screenHeader}>
        <View style={styles.headerTextBlock}>
          <Text style={[styles.screenTitle, { color: tc }]}>Notifications</Text>
          <Text style={[styles.screenSubtitle, { color: tcMuted }]}>
            {unreadCount > 0
              ? `${unreadCount} unread notification${unreadCount === 1 ? "" : "s"}`
              : "You're all caught up"}
          </Text>
        </View>
        {unreadCount > 0 && (
          <Button
            title="Mark All Read"
            onPress={handleMarkAllRead}
            variant="secondary"
            size="sm"
          />
        )}
      </View>

      {showSpinner ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color={brand} />
        </View>
      ) : loadError && notifications.length === 0 ? (
        <ErrorState
          title="Couldn't load notifications"
          message={loadError}
          onRetry={() => loadNotifications(false)}
        />
      ) : notifications.length === 0 && !loading ? (
        <EmptyState
          icon="notifications-outline"
          title="No notifications yet"
          description="Order updates and announcements from your cafeteria will appear here."
        />
      ) : (
        <ScrollView
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              colors={[brand]}
              tintColor={brand}
            />
          }
        >
          {notifications.map((n) => {
            const isUnread = !n.is_read;
            return (
              <Pressable
                key={n.id}
                onPress={() => {
                  // Mirror web: tapping an unread row marks it read; read
                  // rows are inert.
                  if (isUnread) handleMarkRead(n);
                }}
                style={({ pressed }) => [
                  styles.row,
                  {
                    backgroundColor: isUnread ? brand + "10" : "transparent",
                    borderBottomColor: resolvedTheme === "dark" ? "#233044" : "#e5e7eb",
                    opacity: pressed && isUnread ? 0.8 : 1,
                  },
                ]}
              >
                <View style={styles.iconColumn}>
                  <Ionicons
                    name={TYPE_ICONS[n.notification_type] ?? "notifications-outline"}
                    size={22}
                    color={tcMuted}
                  />
                </View>

                <View style={styles.contentColumn}>
                  <Text
                    style={[
                      styles.rowTitle,
                      { color: tc, fontWeight: isUnread ? "700" : "600" },
                    ]}
                    numberOfLines={1}
                  >
                    {n.title}
                  </Text>
                  {/* Rows are inert once read and there is no detail screen,
                      so a truncated body would be unreadable forever. */}
                  <Text style={[styles.rowBody, { color: tcMuted }]}>
                    {n.body}
                  </Text>
                </View>

                <View style={styles.metaColumn}>
                  <Text style={[styles.rowTime, { color: tcMuted }]}>
                    {formatTimeAgo(n.created_at)}
                  </Text>
                  {isUnread && (
                    <View style={[styles.unreadDot, { backgroundColor: brand }]} />
                  )}
                </View>
              </Pressable>
            );
          })}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  centerContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  screenHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 8,
  },
  headerTextBlock: { flex: 1, paddingRight: 12 },
  screenTitle: { fontSize: 28, fontWeight: "700", lineHeight: 34 },
  screenSubtitle: { fontSize: 13, marginTop: 4 },

  list: { paddingBottom: 32, paddingTop: 4 },

  row: {
    flexDirection: "row",
    alignItems: "flex-start",
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  iconColumn: { width: 34, paddingTop: 2 },
  contentColumn: { flex: 1, paddingRight: 10 },
  rowTitle: { fontSize: 14, lineHeight: 19 },
  rowBody: { fontSize: 12.5, lineHeight: 18, marginTop: 2 },
  metaColumn: { alignItems: "flex-end", minWidth: 64 },
  rowTime: { fontSize: 11 },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginTop: 6,
  },
});
