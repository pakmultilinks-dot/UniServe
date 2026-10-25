/**
 * UniServe — Order Detail Screen
 *
 * Shows order status, items, and pickup QR code.
 * Uses OrderStatusTimeline for status visualization.
 */
import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  Pressable,
  ActivityIndicator,
  TextInput,
} from "react-native";
import { useLocalSearchParams, useRouter, useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";

import { useTheme } from "../../../src/contexts/ThemeContext";
import { useCart } from "../../../src/contexts/CartContext";
import {
  getOrder,
  getOrderPayment,
  cancelOrder,
  partialCancelItem,
  getRefundableAmount,
  requestRefund,
  getOrderRefunds,
} from "../../../src/services/data";
import type { OrderRefund, RefundableAmount } from "../../../src/services/data";
import { ApiClientError } from "../../../src/services/api";
import { textColor, bgColor, borderColor, brandGreen, functionalColor } from "../../../src/theme";
import type { Order, OrderStatus, Payment, RefundReason } from "@uniserve/shared-types";

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

// ── Refunds (Phase 58, Workstream B) ──
// Backend RefundReason enum is authoritative; free text in the reason field
// is rejected server-side with a 400.
const REFUND_REASONS: { value: RefundReason; label: string }[] = [
  { value: "order_cancelled", label: "Order was cancelled" },
  { value: "item_unavailable", label: "Item was unavailable" },
  { value: "payment_error", label: "Payment error" },
  { value: "duplicate_payment", label: "Duplicate payment" },
  { value: "cafeteria_closed", label: "Cafeteria was closed" },
  { value: "other", label: "Other" },
];

const REFUND_STATUS_CONFIG: Record<
  string,
  { label: string; colorKey: "success" | "warning" | "error" | "info" }
> = {
  pending: { label: "Pending review", colorKey: "warning" },
  processing: { label: "Processing", colorKey: "info" },
  succeeded: { label: "Approved — returned", colorKey: "success" },
  failed: { label: "Failed", colorKey: "error" },
  rejected: { label: "Rejected", colorKey: "error" },
};

// ── Real-time polling (Phase 22) ──
// REST polling on the existing authenticated endpoints — the same mechanism the
// web dashboard uses (30 s on the order list). Interval is 15 s here because
// this screen watches a single, actively awaited order. Polling runs only while
// the screen is focused and the order is non-terminal.
const ORDER_POLL_INTERVAL_MS = 15000;
const TERMINAL_ORDER_STATUSES: readonly OrderStatus[] = ["completed", "cancelled"];

// ── Status Timeline ──

interface TimelineProps {
  currentStatus: OrderStatus;
  theme: "light" | "dark";
  /** Confirmation alone never proves preparation started. */
  preparationStartedAt?: string | null;
  readyAt?: string | null;
  /** Staff rejection reason/note, surfaced so a cancelled order never shows a
   *  vague "cancelled" with no explanation (fixes contradictory notifications). */
  rejectionReason?: string | null;
  rejectionNote?: string | null;
}

function OrderStatusTimeline({
  currentStatus,
  theme,
  preparationStartedAt,
  readyAt,
  rejectionReason,
  rejectionNote,
}: TimelineProps) {
  const brand = brandGreen(theme);
  const tc = textColor(theme, "primary");
  const tcMuted = textColor(theme, "muted");
  const bg = bgColor(theme, "secondary");
  const bc = borderColor(theme, "default");

  const currentIdx = STATUS_ORDER.indexOf(currentStatus as any);
  const isCancelled = currentStatus === "cancelled";

  // Render only stages evidenced by actual lifecycle timestamps. Staff
  // confirmation keeps an order pending; treating it as preparation gave
  // rejected scheduled orders a misleading Preparing stage.
  const reachedIdx = isCancelled
    ? (readyAt ? 2 : preparationStartedAt ? 1 : 0)
    : currentIdx;
  const visibleSteps = STATUS_ORDER.filter(
    (_, idx) => !isCancelled || idx <= reachedIdx,
  );

  return (
    <View style={[styles.timelineCard, { backgroundColor: bg, borderColor: bc }]}>
      {visibleSteps.map((status, idx) => {
        const config = STATUS_CONFIG[status];
        const isActive = !isCancelled && idx === reachedIdx;
        const isPast = isCancelled ? idx <= reachedIdx : idx < currentIdx;

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
              {idx < visibleSteps.length - 1 && (
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

      {/* A terminal cancellation must be the primary status, not an active
          Pending/Preparing heading. Earlier stages remain historical. */}
      {isCancelled && (
        <View style={styles.timelineStep}>
          <View style={styles.timelineIconCol}>
            <View style={[styles.timelineIcon, { backgroundColor: functionalColor(theme, "error"), borderColor: functionalColor(theme, "error") }]}>
              <Ionicons name="close-circle-outline" size={14} color="#ffffff" />
            </View>
          </View>
          <View style={styles.timelineLabelCol}>
            <Text style={[styles.timelineLabel, { color: functionalColor(theme, "error"), fontWeight: "700" }]}>Cancelled</Text>
          </View>
        </View>
      )}
      {/* Cancelled override */}
      {isCancelled && (
        <View style={[styles.cancelledBanner, { borderColor: functionalColor(theme, "error") + "30" }]}>
          <Ionicons name="close-circle" size={16} color={functionalColor(theme, "error")} />
          <View style={{ flex: 1 }}>
            <Text style={[styles.cancelledText, { color: functionalColor(theme, "error") }]}>
              This order was cancelled
            </Text>
            {rejectionReason ? (
              <Text style={[styles.cancelledReason, { color: tcMuted }]}>
                Reason: {rejectionReason}
              </Text>
            ) : null}
            {rejectionNote ? (
              <Text style={[styles.cancelledReason, { color: tcMuted }]}>
                {rejectionNote}
              </Text>
            ) : null}
          </View>
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
  const { selectedCafeteria } = useCart();

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
  const [payment, setPayment] = useState<Payment | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!id) return;
    (async () => {
      try {
        const data = await getOrder(id);
        setOrder(data);
        if (data.payment_method === "online") {
          try {
            setPayment(await getOrderPayment(data.id));
          } catch {
            // The order remains the source of truth if payment details are not yet available.
          }
        }
      } catch {
        setError("Failed to load order");
      } finally {
        setIsLoading(false);
      }
    })();
  }, [id]);

  /** Silent background refresh — never toggles the initial-loading state. */
  const refreshOrderQuietly = useCallback(async () => {
    if (!id) return;
    try {
      const data = await getOrder(id);
      setOrder(data);
      if (data.payment_method === "online") {
        try {
          setPayment(await getOrderPayment(data.id));
        } catch {
          // Payment details are optional; order status remains authoritative.
        }
      }
    } catch {
      // Keep last-known state on transient errors. Auth expiry is handled by
      // the global ApiClient failure path (tokens cleared → redirect → unmount).
    }
  }, [id]);

  // ── Customer cancellation (P2 — Phase 40 acceptance) ──
  // Backend rules are unchanged (pending-only, ownership, scheduled deadline
  // enforced server-side) — this screen only exposes the existing endpoint.
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [cancelError, setCancelError] = useState("");

  /** Two-step confirm → cancel → silent refresh (status flips to cancelled). */
  const handleCancelOrder = useCallback(async () => {
    if (!id) return;
    setIsCancelling(true);
    setCancelError("");
    try {
      await cancelOrder(id, "Cancelled by customer");
      setConfirmCancel(false);
      await refreshOrderQuietly();
    } catch (err) {
      // ApiClientError.message carries the backend detail (e.g. the scheduled
      // cancellation deadline message) — surface it inline for the customer.
      setCancelError(
        err instanceof ApiClientError ? err.message : "Failed to cancel order",
      );
    } finally {
      setIsCancelling(false);
    }
  }, [id, refreshOrderQuietly]);

  // ── Phase 58 (Workstream B) — refund request self-service ──
  // Owner-only backend endpoints: GET /refunds/refundable/{id},
  // POST /refunds?order_id=... (idempotent), GET /refunds/order/{id}.
  // The refundable check requires a SUCCEEDED payment; the 72h deadline and
  // all other eligibility rules are enforced server-side and surfaced verbatim.
  const [refundInfo, setRefundInfo] = useState<{
    refundable: RefundableAmount;
    refunds: OrderRefund[];
  } | null>(null);
  const [refundFormOpen, setRefundFormOpen] = useState(false);
  const [refundReason, setRefundReason] = useState<RefundReason | "">("");
  const [refundNote, setRefundNote] = useState("");
  const [refundAmount, setRefundAmount] = useState(""); // PKR, up to 2 decimals
  const [refundSubmitting, setRefundSubmitting] = useState(false);
  const [refundError, setRefundError] = useState("");
  const [refundSuccess, setRefundSuccess] = useState("");
  const [refundCheckError, setRefundCheckError] = useState("");

  /** Load refundability + refund history for terminal orders (silent). */
  const loadRefundInfo = useCallback(async () => {
    if (!id || !order) return;
    if (order.status !== "completed" && order.status !== "cancelled") {
      setRefundInfo(null);
      return;
    }
    try {
      const [refundable, refunds] = await Promise.all([
        getRefundableAmount(id),
        getOrderRefunds(id),
      ]);
      setRefundInfo({ refundable, refunds });
      setRefundCheckError("");
    } catch (err) {
      setRefundInfo(null);
      setRefundCheckError(
        err instanceof ApiClientError
          ? err.message
          : "Refund eligibility unavailable",
      );
    }
  }, [id, order?.status]);

  useEffect(() => {
    void loadRefundInfo();
  }, [loadRefundInfo]);

  /** Open the refund form (re-checking eligibility when not loaded yet). */
  const openRefundForm = useCallback(() => {
    setRefundError("");
    setRefundSuccess("");
    // For cash/pay-at-counter orders where no payment was collected, explain
    // clearly instead of the generic "no refundable amount" message.
    const isCashOrder = order?.payment_method === "cash";
    const noRefundMsg = isCashOrder
      ? "No payment was collected for this order. No refund is required."
      : "This order has no refundable amount left.";
    if (refundInfo) {
      if (refundInfo.refundable.refundable_amount <= 0) {
        setRefundCheckError(noRefundMsg);
        return;
      }
      setRefundCheckError("");
      setRefundAmount((refundInfo.refundable.refundable_amount / 100).toFixed(2));
      setRefundFormOpen(true);
      return;
    }
    // Eligibility not loaded yet — fetch now; backend errors surface verbatim.
    void (async () => {
      if (!id) return;
      try {
        const [refundable, refunds] = await Promise.all([
          getRefundableAmount(id),
          getOrderRefunds(id),
        ]);
        setRefundInfo({ refundable, refunds });
        if (refundable.refundable_amount <= 0) {
          setRefundCheckError(noRefundMsg);
        } else {
          setRefundCheckError("");
          setRefundAmount((refundable.refundable_amount / 100).toFixed(2));
          setRefundFormOpen(true);
        }
      } catch (err) {
        setRefundCheckError(
          err instanceof ApiClientError
            ? err.message
            : "Unable to check refund eligibility",
        );
      }
    })();
  }, [id, refundInfo, order?.payment_method]);

  /** Submit the refund request — backend is authoritative for eligibility. */
  const handleSubmitRefund = useCallback(async () => {
    if (!id || !refundReason) return;
    const rupees = Number(refundAmount);
    const paisa = Math.round(rupees * 100);
    const maxPaisa = refundInfo?.refundable.refundable_amount ?? 0;
    if (!Number.isFinite(rupees) || rupees <= 0 || paisa <= 0) {
      setRefundError("Enter an amount greater than zero.");
      return;
    }
    if (maxPaisa > 0 && paisa > maxPaisa) {
      setRefundError(
        `Amount exceeds the refundable maximum (${formatPrice(maxPaisa)}).`,
      );
      return;
    }
    setRefundSubmitting(true);
    setRefundError("");
    try {
      await requestRefund(id, {
        amount: paisa,
        reason: refundReason,
        reason_note: refundNote.trim() || undefined,
        // Stable per-order key: retrying the same request is idempotent
        // server-side and can never create a duplicate refund.
        idempotency_key: `refund-req-${id}`,
      });
      setRefundFormOpen(false);
      setRefundReason("");
      setRefundNote("");
      setRefundSuccess(
        "Refund request submitted for review. The money will be returned to your account after admin approval.",
      );
      await loadRefundInfo();
    } catch (err) {
      // Backend messages (no succeeded payment, past the refund deadline,
      // already refunded, etc.) are surfaced verbatim.
      setRefundError(
        err instanceof ApiClientError
          ? err.message
          : "Failed to submit refund request",
      );
    } finally {
      setRefundSubmitting(false);
    }
  }, [id, refundReason, refundNote, refundAmount, refundInfo, loadRefundInfo]);

  // ── Phase 58 (Workstream E2) — per-item cancel for PENDING orders ──
  // Backend: POST /orders/{id}/partial-cancel — owner-only, pending-only;
  // removing the final remaining item cancels the whole order; the total is
  // recalculated and inventory released server-side. Errors surface inline.
  const [cancelItemTarget, setCancelItemTarget] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [isCancellingItem, setIsCancellingItem] = useState(false);
  const [cancelItemError, setCancelItemError] = useState("");

  const handleCancelItem = useCallback(async () => {
    if (!id || !cancelItemTarget) return;
    setIsCancellingItem(true);
    setCancelItemError("");
    try {
      await partialCancelItem(id, cancelItemTarget.id, "Item cancelled by customer");
      setCancelItemTarget(null);
      await refreshOrderQuietly();
      await loadRefundInfo(); // order totals/refundability may have changed
    } catch (err) {
      setCancelItemError(
        err instanceof ApiClientError ? err.message : "Failed to cancel item",
      );
    } finally {
      setIsCancellingItem(false);
    }
  }, [id, cancelItemTarget, refreshOrderQuietly, loadRefundInfo]);

  // Stop polling once the order reaches a terminal state.
  useEffect(() => {
    if (order && TERMINAL_ORDER_STATUSES.includes(order.status) && pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, [order]);

  // Focus-aware REST polling (Phase 22): refresh the order every 15 s while this
  // screen is focused and the order is still active. Cleanup runs on blur,
  // unmount, and terminal-status transitions — single timer, no duplicates.
  useFocusEffect(
    useCallback(() => {
      if (!id) return;
      if (order && TERMINAL_ORDER_STATUSES.includes(order.status)) return;

      pollTimerRef.current = setInterval(refreshOrderQuietly, ORDER_POLL_INTERVAL_MS);
      return () => {
        if (pollTimerRef.current) {
          clearInterval(pollTimerRef.current);
          pollTimerRef.current = null;
        }
      };
    }, [id, order?.status, refreshOrderQuietly]),
  );

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

  const isTerminal = order.status === "completed" || order.status === "cancelled";

  return (
    <SafeAreaView edges={["bottom"]} style={[styles.screen, { backgroundColor: bgSec }]}>
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
          {selectedCafeteria?.id === order.cafeteria_id && (
            <Text style={[styles.orderDate, { color: tcMuted }]}>{selectedCafeteria.name}</Text>
          )}
        </View>

        {/* ── Status Timeline ── */}
        <OrderStatusTimeline
          currentStatus={order.status}
          theme={resolvedTheme as "light" | "dark"}
          preparationStartedAt={order.preparation_started_at}
          readyAt={order.ready_at}
          rejectionReason={order.rejection_reason}
          rejectionNote={order.rejection_note}
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
              <Text style={[styles.qrBannerSub, { color: tcMuted }]}>Available when collecting</Text>
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
              {/* Phase 58 (Workstream E2) — per-item cancel, pending orders
                  only. Backend enforces ownership + pending status. */}
              {order.status === "pending" && order.items.length > 1 && (
                <Pressable
                  hitSlop={6}
                  style={styles.itemCancelBtn}
                  onPress={() => {
                    setCancelItemTarget({ id: item.id, name: item.item_name });
                    setCancelItemError("");
                  }}
                >
                  <Text
                    style={[
                      styles.itemCancelText,
                      { color: functionalColor(resolvedTheme, "error") },
                    ]}
                  >
                    Cancel item
                  </Text>
                </Pressable>
              )}
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

        {/* ── Per-item cancel confirmation (Phase 58, Workstream E2) ── */}
        {cancelItemTarget && (
          <View
            style={[
              styles.cancelCard,
              { backgroundColor: bg, borderColor: bc, marginBottom: 16 },
            ]}
          >
            <Text style={[styles.cancelTitle, { color: tc }]}>
              Remove “{cancelItemTarget.name}” from this order?
            </Text>
            <Text style={[styles.refundHint, { color: tcMuted }]}>
              The item is removed and its cost is deducted from the order total.
              The whole order is cancelled only when it was the last remaining
              item.
            </Text>
            <View style={styles.cancelActions}>
              <Pressable
                style={[
                  styles.cancelBtn,
                  { backgroundColor: functionalColor(resolvedTheme, "error") },
                ]}
                onPress={handleCancelItem}
                disabled={isCancellingItem}
              >
                {isCancellingItem ? (
                  <ActivityIndicator size="small" color="#ffffff" />
                ) : (
                  <Text style={styles.cancelBtnText}>Remove item</Text>
                )}
              </Pressable>
              <Pressable
                style={[
                  styles.cancelBtn,
                  styles.cancelBtnKeep,
                  { borderColor: bc },
                ]}
                onPress={() => {
                  setCancelItemTarget(null);
                  setCancelItemError("");
                }}
                disabled={isCancellingItem}
              >
                <Text style={[styles.cancelBtnText, { color: tc }]}>Keep item</Text>
              </Pressable>
            </View>
            {cancelItemError !== "" && (
              <Text
                style={[
                  styles.cancelError,
                  { color: functionalColor(resolvedTheme, "error") },
                ]}
              >
                {cancelItemError}
              </Text>
            )}
          </View>
        )}

        {/* ── Payment Info ── */}
        <View style={[styles.infoRow, { backgroundColor: bg, borderColor: bc }]}>
          <Ionicons
            name={order.payment_method === "cash" ? "cash-outline" : "card-outline"}
            size={18}
            color={tcMuted}
          />
          <Text style={[styles.infoLabel, { color: tcMuted }]}>Payment</Text>
          <Text style={[styles.infoValue, { color: tc }]}>
            {order.payment_method === "cash"
              ? "Pay at Counter"
              : `Online${payment ? ` · ${payment.status}` : " · pending"}`}
          </Text>
        </View>

        <View style={[styles.infoRow, { backgroundColor: bg, borderColor: bc }]}>
          <Ionicons name={order.order_type === "scheduled" ? "calendar-outline" : "flash-outline"} size={18} color={tcMuted} />
          <Text style={[styles.infoLabel, { color: tcMuted }]}>Collection</Text>
          <Text style={[styles.infoValue, { color: tc }]}>
            {order.order_type === "scheduled"
              ? `Scheduled${order.scheduled_collection_time ? ` · ${order.scheduled_collection_time}` : ""}`
              : "Immediate"}
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

        {/* ── Cancel (pending only; server enforces ownership + scheduled deadline) ── */}
        {order.status === "pending" && (
          <View style={[styles.cancelCard, { backgroundColor: bg, borderColor: bc }]}>
            {confirmCancel ? (
              <>
                <Text style={[styles.cancelTitle, { color: tc }]}>Cancel entire order?</Text>
                <Text style={[styles.cancelSubtitle, { color: tcMuted }]}>
                  This will cancel all items in the order.
                  {order.payment_method === "cash"
                    ? " No payment was collected."
                    : " Any paid amount can be refunded from the order details."}
                </Text>
                <View style={styles.cancelActions}>
                  <Pressable
                    style={[
                      styles.cancelBtn,
                      { backgroundColor: functionalColor(resolvedTheme, "error") },
                    ]}
                    onPress={handleCancelOrder}
                    disabled={isCancelling}
                  >
                    {isCancelling ? (
                      <ActivityIndicator size="small" color="#ffffff" />
                    ) : (
                      <Text style={styles.cancelBtnText}>Yes, cancel</Text>
                    )}
                  </Pressable>
                  <Pressable
                    style={[styles.cancelBtn, styles.cancelBtnKeep, { borderColor: bc }]}
                    onPress={() => {
                      setConfirmCancel(false);
                      setCancelError("");
                    }}
                    disabled={isCancelling}
                  >
                    <Text style={[styles.cancelBtnText, { color: tc }]}>Keep order</Text>
                  </Pressable>
                </View>
              </>
            ) : (
              <Pressable
                style={styles.cancelRow}
                onPress={() => {
                  setConfirmCancel(true);
                  setCancelError("");
                }}
              >
                <Ionicons
                  name="close-circle-outline"
                  size={18}
                  color={functionalColor(resolvedTheme, "error")}
                />
                <Text
                  style={[
                    styles.cancelLabel,
                    { color: functionalColor(resolvedTheme, "error") },
                  ]}
                >
                  Cancel Order
                </Text>
              </Pressable>
            )}
            {cancelError !== "" && (
              <Text
                style={[
                  styles.cancelError,
                  { color: functionalColor(resolvedTheme, "error") },
                ]}
              >
                {cancelError}
              </Text>
            )}
          </View>
        )}

        {/* ── Refunds (Phase 58, Workstream B) ──
            Online payments only: a cash order collects nothing at the
            counter, so a Refunds panel there is pure noise — there is no
            money to return. */}
        {isTerminal && order.payment_method === "online" && (
          <View style={[styles.refundCard, { backgroundColor: bg, borderColor: bc }]}>
            <Text style={[styles.refundTitle, { color: tc }]}>Refunds</Text>

            {refundInfo && refundInfo.refunds.length > 0 && (
              <View style={{ marginBottom: 10, gap: 6 }}>
                {refundInfo.refunds.map((r) => {
                  const cfg = REFUND_STATUS_CONFIG[r.status] ?? {
                    label: r.status,
                    colorKey: "info" as const,
                  };
                  return (
                    <View
                      key={r.id}
                      style={[styles.refundRow, { borderColor: bcSub }]}
                    >
                      <View style={{ flex: 1 }}>
                        <Text style={[styles.refundRowAmount, { color: tc }]}>
                          {formatPrice(r.amount)}
                        </Text>
                        <Text style={[styles.refundRowMeta, { color: tcMuted }]}>
                          {REFUND_REASONS.find((x) => x.value === r.reason)?.label ??
                            r.reason.replace(/_/g, " ")}{" "}
                          · {formatDate(r.created_at)}
                        </Text>
                      </View>
                      <Text
                        style={[
                          styles.refundStatus,
                          {
                            color: functionalColor(resolvedTheme, cfg.colorKey),
                          },
                        ]}
                      >
                        {cfg.label}
                      </Text>
                    </View>
                  );
                })}
                <Text style={[styles.refundHint, { color: tcMuted }]}>
                  Refund requests are reviewed by an admin; approved money is
                  returned to the original payment method.
                </Text>
              </View>
            )}

            {/* Failed refund → point the user to a real support channel. There
                is no in-app support route or configured support email yet, so
                this is guidance rather than a navigation button (avoids a dead
                route). Does not imply a retry will succeed. */}
            {refundInfo &&
              refundInfo.refunds.some((r) => r.status === "failed") && (
                <View
                  style={[
                    styles.supportBox,
                    { borderColor: functionalColor(resolvedTheme, "error") + "40" },
                  ]}
                >
                  <Ionicons
                    name="help-buoy-outline"
                    size={16}
                    color={functionalColor(resolvedTheme, "error")}
                  />
                  <Text style={[styles.supportBoxText, { color: tcMuted }]}>
                    This refund failed and is reviewed by an admin. Please
                    contact the cafeteria service desk or university
                    administration for assistance.
                  </Text>
                </View>
              )}

            {refundSuccess !== "" && (
              <View
                style={[
                  styles.refundNoteBox,
                  {
                    backgroundColor:
                      functionalColor(resolvedTheme, "success") + "15",
                    borderColor:
                      functionalColor(resolvedTheme, "success") + "40",
                  },
                ]}
              >
                <Text
                  style={[
                    styles.refundNoteText,
                    { color: functionalColor(resolvedTheme, "success") },
                  ]}
                >
                  {refundSuccess}
                </Text>
              </View>
            )}
            {refundCheckError !== "" && (
              <View
                style={[
                  styles.refundNoteBox,
                  {
                    backgroundColor:
                      functionalColor(resolvedTheme, "error") + "10",
                    borderColor:
                      functionalColor(resolvedTheme, "error") + "40",
                  },
                ]}
              >
                <Text
                  style={[
                    styles.refundNoteText,
                    { color: functionalColor(resolvedTheme, "error") },
                  ]}
                >
                  {refundCheckError}
                </Text>
              </View>
            )}

            {refundFormOpen ? (
              <View style={{ gap: 10 }}>
                <Text style={[styles.refundLabel, { color: tcSec }]}>Reason</Text>
                <View style={styles.refundChips}>
                  {REFUND_REASONS.map((r) => {
                    const active = refundReason === r.value;
                    return (
                      <Pressable
                        key={r.value}
                        onPress={() => setRefundReason(r.value)}
                        style={[
                          styles.refundChip,
                          {
                            borderColor: active ? brand : bc,
                            backgroundColor: active ? brand + "15" : bgSec,
                          },
                        ]}
                      >
                        <Text
                          style={[
                            styles.refundChipText,
                            { color: active ? brand : tcSec },
                          ]}
                        >
                          {r.label}
                        </Text>
                      </Pressable>
                    );
                  })}
                </View>

                <Text style={[styles.refundLabel, { color: tcSec }]}>
                  Amount (PKR)
                </Text>
                <TextInput
                  value={refundAmount}
                  onChangeText={setRefundAmount}
                  keyboardType="decimal-pad"
                  placeholder="0.00"
                  placeholderTextColor={tcMuted}
                  style={[
                    styles.refundInput,
                    { borderColor: bc, backgroundColor: bgSec, color: tc },
                  ]}
                />
                {refundInfo && (
                  <Text style={[styles.refundHint, { color: tcMuted }]}>
                    Refundable now: {formatPrice(refundInfo.refundable.refundable_amount)}{" "}
                    · paid {formatPrice(refundInfo.refundable.paid_amount)}{" "}
                    · already refunded {formatPrice(refundInfo.refundable.total_refunded)}
                  </Text>
                )}

                <Text style={[styles.refundLabel, { color: tcSec }]}>
                  Note (optional)
                </Text>
                <TextInput
                  value={refundNote}
                  onChangeText={(t) => setRefundNote(t.slice(0, 500))}
                  placeholder="Additional detail (max 500 characters)"
                  placeholderTextColor={tcMuted}
                  multiline
                  style={[
                    styles.refundInput,
                    styles.refundInputMultiline,
                    { borderColor: bc, backgroundColor: bgSec, color: tc },
                  ]}
                />

                {refundError !== "" && (
                  <Text
                    style={[
                      styles.cancelError,
                      { color: functionalColor(resolvedTheme, "error") },
                    ]}
                  >
                    {refundError}
                  </Text>
                )}

                <View style={styles.cancelActions}>
                  <Pressable
                    style={[
                      styles.cancelBtn,
                      { backgroundColor: brand },
                    ]}
                    onPress={handleSubmitRefund}
                    disabled={refundSubmitting || !refundReason}
                  >
                    {refundSubmitting ? (
                      <ActivityIndicator size="small" color="#ffffff" />
                    ) : (
                      <Text style={styles.cancelBtnText}>Submit request</Text>
                    )}
                  </Pressable>
                  <Pressable
                    style={[
                      styles.cancelBtn,
                      styles.cancelBtnKeep,
                      { borderColor: bc },
                    ]}
                    onPress={() => {
                      setRefundFormOpen(false);
                      setRefundError("");
                    }}
                    disabled={refundSubmitting}
                  >
                    <Text style={[styles.cancelBtnText, { color: tc }]}>
                      Cancel
                    </Text>
                  </Pressable>
                </View>
              </View>
            ) : refundInfo && refundInfo.refundable.refundable_amount === 0 ? (
              <Text style={{ color: tcMuted }}>No refundable payment was collected for this order.</Text>
            ) : (
              <Pressable
                style={[styles.refundButton, { borderColor: brand }]}
                onPress={openRefundForm}
                disabled={refundSubmitting}
              >
                <Ionicons name="return-down-back-outline" size={18} color={brand} />
                <Text style={[styles.refundButtonText, { color: brand }]}>
                  Request refund
                </Text>
              </Pressable>
            )}
          </View>
        )}

        <View style={{ height: 64 }} />
      </ScrollView>
    </SafeAreaView>
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
    alignItems: "flex-start",
    gap: 8,
    marginTop: 12,
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    backgroundColor: "#fef2f2",
  },
  cancelledText: { fontSize: 13, fontWeight: "600" },
  cancelledReason: { fontSize: 12, lineHeight: 17, marginTop: 2 },

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

  // Cancel order (pending only)
  cancelCard: {
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    marginTop: 4,
    gap: 8,
  },
  cancelRow: { flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 2 },
  cancelLabel: { fontSize: 14, fontWeight: "600" },
  cancelTitle: { fontSize: 15, fontWeight: "600" },
  cancelSubtitle: { fontSize: 13, marginTop: 4, marginBottom: 12 },
  cancelActions: { flexDirection: "row", gap: 10 },
  cancelBtn: {
    flex: 1,
    height: 40,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
  },
  cancelBtnKeep: { borderWidth: 1, backgroundColor: "transparent" },
  cancelBtnText: { fontSize: 14, fontWeight: "600", color: "#ffffff" },
  cancelError: { fontSize: 13 },

  // Per-item cancel (Phase 58, Workstream E2)
  itemCancelBtn: { marginLeft: 8, paddingVertical: 2, paddingHorizontal: 4 },
  itemCancelText: { fontSize: 12, fontWeight: "600" },

  // Refunds (Phase 58, Workstream B)
  refundCard: {
    padding: 14,
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 16,
    gap: 8,
  },
  refundTitle: { fontSize: 15, fontWeight: "700" },
  refundRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    borderBottomWidth: 1,
    paddingBottom: 6,
  },
  refundRowAmount: { fontSize: 13, fontWeight: "600" },
  refundRowMeta: { fontSize: 11, marginTop: 2 },
  refundStatus: { fontSize: 12, fontWeight: "600" },
  refundNoteBox: {
    borderWidth: 1,
    borderRadius: 8,
    padding: 10,
  },
  refundNoteText: { fontSize: 12, lineHeight: 17 },
  refundHint: { fontSize: 11, lineHeight: 16 },
  supportBox: {
    flexDirection: "row",
    gap: 8,
    alignItems: "flex-start",
    borderWidth: 1,
    borderRadius: 8,
    padding: 10,
    marginTop: 10,
  },
  supportBoxText: { flex: 1, fontSize: 12, lineHeight: 17 },
  refundLabel: { fontSize: 13, fontWeight: "600" },
  refundChips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  refundChip: {
    borderWidth: 1,
    borderRadius: 16,
    paddingVertical: 6,
    paddingHorizontal: 12,
  },
  refundChipText: { fontSize: 12, fontWeight: "500" },
  refundInput: {
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
  },
  refundInputMultiline: { minHeight: 64, textAlignVertical: "top" },
  refundButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    borderWidth: 1,
    borderRadius: 10,
    paddingVertical: 12,
  },
  refundButtonText: { fontSize: 14, fontWeight: "600" },
});
