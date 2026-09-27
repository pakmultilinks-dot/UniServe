/**
 * UniServe — Empty State Component (React Native)
 */

import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { colors } from "../../theme/colors";

interface EmptyStateProps {
  emoji?: string;
  title: string;
  description?: string;
}

export function EmptyState({ emoji = "📭", title, description }: EmptyStateProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.emoji}>{emoji}</Text>
      <Text style={styles.title}>{title}</Text>
      {description && <Text style={styles.description}>{description}</Text>}
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
  emoji: {
    fontSize: 40,
    marginBottom: 12,
  },
  title: {
    fontSize: 16,
    fontWeight: "600",
    color: colors.neutral[700],
    textAlign: "center",
  },
  description: {
    fontSize: 14,
    color: colors.neutral[500],
    textAlign: "center",
    marginTop: 6,
    lineHeight: 20,
  },
});
