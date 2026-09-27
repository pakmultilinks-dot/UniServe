/**
 * QuantityStepper — Compact ± control for food items.
 *
 * Design spec:
 * - borderRadius 10
 * - borderWidth 1
 * - height 48
 * - 48x48 touch targets
 * - Disabled state for unavailable / max
 */
import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTheme } from "../../contexts/ThemeContext";
import { textColor, bgColor, borderColor, brandGreen } from "../../theme";

interface QuantityStepperProps {
  quantity: number;
  min?: number;
  max?: number;
  onIncrement: () => void;
  onDecrement: () => void;
  disabled?: boolean;
  size?: "sm" | "md" | "lg";
}

export function QuantityStepper({
  quantity,
  min = 1,
  max = 10,
  onIncrement,
  onDecrement,
  disabled = false,
  size = "md",
}: QuantityStepperProps) {
  const { resolvedTheme } = useTheme();
  const tc = textColor(resolvedTheme, "primary");
  const tcMuted = textColor(resolvedTheme, "muted");
  const bc = borderColor(resolvedTheme, "default");

  const isAtMin = quantity <= min;
  const isAtMax = quantity >= max;
  const dim = size === "sm" ? 32 : size === "lg" ? 48 : 40;
  const fontSize = size === "sm" ? 14 : size === "lg" ? 18 : 16;

  return (
    <View
      style={[
        styles.container,
        { borderColor: bc, height: dim },
        size === "lg" && styles.containerLg,
      ]}
    >
      <TouchableOpacity
        style={[styles.btn, { width: dim, height: dim }]}
        onPress={onDecrement}
        disabled={disabled || isAtMin}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        accessibilityLabel="Decrease quantity"
      >
        <Ionicons
          name={isAtMin ? "remove-circle-outline" : "remove-circle"}
          size={fontSize + 4}
          color={isAtMin ? tcMuted : brandGreen(resolvedTheme)}
        />
      </TouchableOpacity>

      <Text
        style={[
          styles.value,
          { color: tc, fontSize },
        ]}
        accessibilityLabel={`Quantity: ${quantity}`}
      >
        {quantity}
      </Text>

      <TouchableOpacity
        style={[styles.btn, { width: dim, height: dim }]}
        onPress={onIncrement}
        disabled={disabled || isAtMax}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        accessibilityLabel="Increase quantity"
      >
        <Ionicons
          name={isAtMax ? "add-circle-outline" : "add-circle"}
          size={fontSize + 4}
          color={isAtMax ? tcMuted : brandGreen(resolvedTheme)}
        />
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 10,
    borderWidth: 1,
  },
  containerLg: {
    height: 48,
  },
  btn: {
    alignItems: "center",
    justifyContent: "center",
  },
  value: {
    fontWeight: "600",
    minWidth: 32,
    textAlign: "center",
  },
});
