/**
 * UniServe — Status Chip Component (React Native)
 */

import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { colors } from "../../theme/colors";

type StatusType = "pending" | "confirmed" | "preparing" | "ready" | "picked_up" | "completed" | "cancelled" | "no_show";

const STATUS_COLORS: Record<StatusType, { bg: string; text: string }> = {
  pending: { bg: "#fef9c3", text: "#854d0e" },
  confirmed: { bg: "#dbeafe", text: "#1e40af" },
  preparing: { bg: "#dbeafe", text: "#1e40af" },
  ready: { bg: "#dcfce7", text: "#166534" },
  picked_up: { bg: "#e0e7ff", text: "#3730a3" },
  completed: { bg: colors.neutral[100], text: colors.neutral[600] },
  cancelled: { bg: "#fee2e2", text: "#991b1b" },
  no_show: { bg: "#fef3c7", text: "#92400e" },
};

interface StatusChipProps {
  status: StatusType;
}

export function StatusChip({ status }: StatusChipProps) {
  const colors_ = STATUS_COLORS[status] ?? STATUS_COLORS.pending;

  return (
    <View style={[styles.chip, { backgroundColor: colors_.bg }]}>
      <Text style={[styles.text, { color: colors_.text }]}>
        {status.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase())}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  chip: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    alignSelf: "flex-start",
  },
  text: {
    fontSize: 12,
    fontWeight: "600",
    textTransform: "capitalize",
  },
});
