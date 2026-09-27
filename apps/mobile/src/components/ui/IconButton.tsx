/**
 * IconButton — Accessible icon-only button with proper touch target.
 *
 * Minimum 44x44 touch target per accessibility spec.
 */
import React from "react";
import { TouchableOpacity, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTheme } from "../../contexts/ThemeContext";
import { textColor } from "../../theme";

type IoniconName = keyof typeof Ionicons.glyphMap;

interface IconButtonProps {
  icon: IoniconName;
  size?: number;
  color?: string;
  onPress: () => void;
  disabled?: boolean;
  accessibilityLabel: string;
}

export function IconButton({
  icon,
  size = 24,
  color,
  onPress,
  disabled = false,
  accessibilityLabel,
}: IconButtonProps) {
  const { resolvedTheme } = useTheme();
  const tc = textColor(resolvedTheme, "primary");

  return (
    <TouchableOpacity
      style={styles.container}
      onPress={onPress}
      disabled={disabled}
      hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
      accessibilityLabel={accessibilityLabel}
      accessibilityRole="button"
    >
      <Ionicons
        name={icon}
        size={size}
        color={disabled ? textColor(resolvedTheme, "muted") : (color ?? tc)}
      />
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: {
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
  },
});
