/**
 * UniServe — Button Component (React Native)
 */

import React from "react";
import {
  TouchableOpacity,
  Text,
  StyleSheet,
  ActivityIndicator,
  ViewStyle,
  TextStyle,
} from "react-native";
import { colors } from "../../theme/colors";

type ButtonVariant = "primary" | "secondary" | "gold" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps {
  title: string;
  onPress: () => void;
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  disabled?: boolean;
  fullWidth?: boolean;
  style?: ViewStyle;
  textStyle?: TextStyle;
}

const VARIANT_STYLES: Record<ButtonVariant, { bg: string; text: string; border?: string }> = {
  primary: { bg: colors.gold[500], text: colors.neutral[900] },
  secondary: { bg: "transparent", text: colors.brand[800], border: colors.gold[600] },
  gold: { bg: colors.gold[500], text: colors.neutral[900] },
  ghost: { bg: "transparent", text: colors.neutral[600] },
  danger: { bg: colors.error, text: "#ffffff" },
};

const SIZE_STYLES: Record<ButtonSize, { paddingV: number; paddingH: number; fontSize: number; borderRadius: number }> = {
  sm: { paddingV: 8, paddingH: 16, fontSize: 14, borderRadius: 22 },
  md: { paddingV: 11, paddingH: 24, fontSize: 15, borderRadius: 24 },
  lg: { paddingV: 13, paddingH: 32, fontSize: 16, borderRadius: 28 },
};

export function Button({
  title,
  onPress,
  variant = "primary",
  size = "md",
  loading = false,
  disabled = false,
  fullWidth = false,
  style,
  textStyle,
}: ButtonProps) {
  const v = VARIANT_STYLES[variant];
  const s = SIZE_STYLES[size];
  const isDisabled = disabled || loading;

  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={isDisabled}
      activeOpacity={0.7}
      style={[
        styles.base,
        {
          backgroundColor: isDisabled && variant !== "ghost" ? colors.neutral[300] : v.bg,
          paddingVertical: s.paddingV,
          paddingHorizontal: s.paddingH,
          borderRadius: s.borderRadius,
          borderWidth: v.border ? 1.5 : 0,
          borderColor: v.border ?? "transparent",
          opacity: isDisabled ? 0.7 : 1,
          width: fullWidth ? "100%" : undefined,
        },
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator size="small" color={v.text} />
      ) : (
        <Text
          style={[
            {
              color: v.text,
              fontSize: s.fontSize,
              fontWeight: "600",
              textAlign: "center",
            },
            textStyle,
          ]}
        >
          {title}
        </Text>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  base: {
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
  },
});
