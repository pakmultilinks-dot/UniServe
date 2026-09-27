/**
 * UniServe — Empty State Component (React Native)
 *
 * Redesigned per UI_MOBILE_REDESIGN.md spec:
 * - Ionicons icon (48px, textMuted color)
 * - Title 18px/600
 * - Description 14px/400
 * - Theme-aware via useTheme
 */

import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTheme } from "../../contexts/ThemeContext";
import { textColor } from "../../theme";

type IoniconName = keyof typeof Ionicons.glyphMap;

interface EmptyStateProps {
  icon?: IoniconName;
  emoji?: string;
  title: string;
  description?: string;
}

export function EmptyState({ icon = "document-text-outline", emoji, title, description }: EmptyStateProps) {
  const { resolvedTheme } = useTheme();
  const tc = (variant: "primary" | "secondary" | "muted") => textColor(resolvedTheme, variant);

  // If emoji is passed, render it as text for backward compatibility
  // Otherwise use Ionicons
  return (
    <View style={styles.container}>
      {emoji ? (
        <Text style={styles.emoji}>{emoji}</Text>
      ) : (
        <Ionicons name={icon} size={48} color={tc("muted")} style={styles.icon} />
      )}
      <Text style={[styles.title, { color: tc("primary") }]}>{title}</Text>
      {description && <Text style={[styles.description, { color: tc("muted") }]}>{description}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: "center",
    justifyContent: "center",
    padding: 32,
    marginVertical: 16,
  },
  icon: {
    marginBottom: 12,
  },
  emoji: {
    fontSize: 48,
    marginBottom: 12,
  },
  title: {
    fontSize: 18,
    fontWeight: "600",
    textAlign: "center",
  },
  description: {
    fontSize: 14,
    fontWeight: "400",
    textAlign: "center",
    marginTop: 6,
    lineHeight: 20,
  },
});
