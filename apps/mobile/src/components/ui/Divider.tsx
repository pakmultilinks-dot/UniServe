/**
 * Divider — Subtle horizontal line divider.
 */
import React from "react";
import { View, StyleSheet } from "react-native";
import { useTheme } from "../../contexts/ThemeContext";
import { borderColor } from "../../theme";

interface DividerProps {
  variant?: "default" | "inset";
  spacing?: number;
}

export function Divider({ variant = "default", spacing = 0 }: DividerProps) {
  const { resolvedTheme } = useTheme();
  const bc = borderColor(resolvedTheme, "default");

  return (
    <View
      style={[
        styles.divider,
        { backgroundColor: bc },
        variant === "inset" && { marginLeft: 56 },
        spacing > 0 && { marginVertical: spacing },
      ]}
    />
  );
}

const styles = StyleSheet.create({
  divider: {
    height: StyleSheet.hairlineWidth,
    width: "100%",
  },
});
