/**
 * SectionHeader — Section title with optional "See all" action.
 *
 * Typography: 18px/700 for title, 14px/500 for action
 */
import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { useTheme } from "../../contexts/ThemeContext";
import { textColor, brandGreen } from "../../theme";

interface SectionHeaderProps {
  title: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function SectionHeader({ title, actionLabel, onAction }: SectionHeaderProps) {
  const { resolvedTheme } = useTheme();
  const tc = textColor(resolvedTheme, "primary");

  return (
    <View style={styles.container}>
      <Text style={[styles.title, { color: tc }]}>{title}</Text>
      {actionLabel && onAction && (
        <TouchableOpacity onPress={onAction} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
          <Text style={[styles.action, { color: brandGreen(resolvedTheme) }]}>
            {actionLabel}
          </Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 20,
    paddingVertical: 12,
  },
  title: {
    fontSize: 18,
    fontWeight: "700",
    letterSpacing: -0.2,
  },
  action: {
    fontSize: 14,
    fontWeight: "500",
  },
});
