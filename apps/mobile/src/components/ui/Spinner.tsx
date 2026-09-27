/**
 * UniServe — Spinner Component (React Native)
 */

import React from "react";
import { View, ActivityIndicator, StyleSheet, Text } from "react-native";
import { colors } from "../../theme/colors";

interface SpinnerProps {
  size?: "small" | "large";
  color?: string;
  label?: string;
}

export function Spinner({ size = "large", color = colors.brand[700], label }: SpinnerProps) {
  return (
    <View style={styles.container}>
      <ActivityIndicator size={size} color={color} />
      {label && <Text style={styles.label}>{label}</Text>}
    </View>
  );
}

export function PageSpinner({ label = "Loading..." }: { label?: string }) {
  return (
    <View style={styles.pageContainer}>
      <ActivityIndicator size="large" color={colors.brand[700]} />
      <Text style={styles.label}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: "center",
    justifyContent: "center",
    padding: 16,
  },
  pageContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },
  label: {
    fontSize: 14,
    color: colors.neutral[500],
    marginTop: 12,
  },
});
