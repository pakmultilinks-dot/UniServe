/**
 * ErrorState — Contained error display with retry action.
 *
 * Design spec: "Show a contained error state. Do not throw a full-screen
 * technical stack trace."
 */
import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTheme } from "../../contexts/ThemeContext";
import { textColor, functionalColor } from "../../theme";
import { Button } from "./Button";

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
}

export function ErrorState({
  title = "Something went wrong",
  message = "Please try again",
  onRetry,
}: ErrorStateProps) {
  const { resolvedTheme } = useTheme();
  const tc = textColor(resolvedTheme, "primary");
  const tcMuted = textColor(resolvedTheme, "muted");

  return (
    <View style={styles.container}>
      <Ionicons
        name="alert-circle-outline"
        size={48}
        color={functionalColor(resolvedTheme, "error")}
      />
      <Text style={[styles.title, { color: tc }]}>{title}</Text>
      <Text style={[styles.message, { color: tcMuted }]}>{message}</Text>
      {onRetry && (
        <View style={styles.buttonContainer}>
          <Button title="Try again" onPress={onRetry} variant="secondary" size="sm" />
        </View>
      )}
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
  title: {
    fontSize: 16,
    fontWeight: "600",
    marginTop: 12,
    textAlign: "center",
  },
  message: {
    fontSize: 14,
    marginTop: 6,
    textAlign: "center",
    lineHeight: 20,
  },
  buttonContainer: {
    marginTop: 16,
  },
});
