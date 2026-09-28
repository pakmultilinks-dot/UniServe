/**
 * UniServe — Order Pickup QR Screen
 *
 * Shows a large QR-like card with the order number for pickup scanning.
 * Since we can't install a QR library, this shows a stylized order card
 * that cafeteria staff can use to verify the order number.
 */
import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import { useLocalSearchParams } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import QRCode from "react-native-qrcode-svg";

import { useTheme } from "../../../../src/contexts/ThemeContext";
import { getOrder } from "../../../../src/services/data";
import { textColor, bgColor, brandGreen } from "../../../../src/theme";
import type { Order } from "@uniserve/shared-types";

// ── Screen ──

export default function OrderQRScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { resolvedTheme } = useTheme();

  const brand = brandGreen(resolvedTheme);
  const tc = textColor(resolvedTheme, "primary");
  const tcSec = textColor(resolvedTheme, "secondary");
  const tcMuted = textColor(resolvedTheme, "muted");
  const bg = bgColor(resolvedTheme, "primary");

  const [order, setOrder] = useState<Order | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    (async () => {
      try {
        const data = await getOrder(id);
        setOrder(data);
      } catch {
        // Silently fail — we'll show loading
      } finally {
        setIsLoading(false);
      }
    })();
  }, [id]);

  if (isLoading) {
    return (
      <View style={[styles.screen, { backgroundColor: bg }]}>
        <ActivityIndicator size="large" color={brand} />
      </View>
    );
  }

  if (!order) {
    return (
      <View style={[styles.screen, { backgroundColor: bg }]}>
        <Text style={{ color: tc }}>Order not found</Text>
      </View>
    );
  }

  return (
    <View style={[styles.screen, { backgroundColor: bg }]}>
      {/* QR Card */}
      <View style={[styles.qrCard, { backgroundColor: "#FFFFFF" }]}>
        {/* Header */}
        <View style={styles.qrHeader}>
          <Ionicons name="restaurant" size={24} color="#4b3421" />
          <Text style={styles.qrBrand}>UniServe</Text>
        </View>

        {/* Large Order Number */}
        <View style={styles.orderNumberContainer}>
          <Text style={styles.orderNumberLarge}>#{order.order_number}</Text>
        </View>

        {order.status === "completed" || order.status === "cancelled" ? (
          <View style={styles.invalidQr}>
            <Ionicons name="close-circle-outline" size={48} color="#95816b" />
            <Text style={styles.invalidQrText}>This collection code is no longer valid.</Text>
          </View>
        ) : (
          <View style={styles.qrPlaceholder}>
            <QRCode
              value={order.collection_token}
              size={180}
              color="#4b3421"
              backgroundColor="#FFFFFF"
            />
          </View>
        )}

        {/* Status */}
        <View style={styles.qrStatus}>
          <Ionicons
            name={order.status === "ready" ? "checkmark-circle" : order.status === "completed" || order.status === "cancelled" ? "close-circle" : "time-outline"}
            size={16}
            color={order.status === "ready" ? "#8c6935" : order.status === "completed" || order.status === "cancelled" ? "#95816b" : "#95816b"}
          />
          <Text style={styles.qrStatusText}>
            {order.status === "ready" ? "Ready for Pickup" : order.status === "completed" ? "Collected" : order.status.charAt(0).toUpperCase() + order.status.slice(1)}
          </Text>
        </View>
      </View>

      {/* Instructions */}
      <View style={styles.instructions}>
        <Ionicons name="information-circle-outline" size={18} color={tcMuted} />
        <Text style={[styles.instructionText, { color: tcMuted }]}>
          Show this screen to the cafeteria staff when collecting your order.
        </Text>
      </View>
    </View>
  );
}

// ── Styles ──

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },

  // QR Card
  qrCard: {
    width: 280,
    borderRadius: 20,
    padding: 24,
    alignItems: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 8,
  },
  qrHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 20,
  },
  qrBrand: {
    fontSize: 18,
    fontWeight: "700",
    color: "#4b3421",
  },

  orderNumberContainer: {
    marginBottom: 20,
  },
  orderNumberLarge: {
    fontSize: 32,
    fontWeight: "800",
    color: "#4b3421",
    letterSpacing: 1,
  },

  // QR placeholder
  qrPlaceholder: {
    marginBottom: 16,
  },
  invalidQr: {
    width: 180,
    height: 180,
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
  },
  invalidQrText: {
    color: "#95816b",
    fontSize: 13,
    textAlign: "center",
  },

  // Status
  qrStatus: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  qrStatusText: {
    fontSize: 13,
    fontWeight: "600",
    color: "#374151",
  },

  // Instructions
  instructions: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: 24,
    paddingHorizontal: 16,
  },
  instructionText: {
    fontSize: 13,
    textAlign: "center",
    lineHeight: 18,
    flex: 1,
  },
});
