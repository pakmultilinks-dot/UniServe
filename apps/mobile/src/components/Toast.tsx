/**
 * Toast — Slide-in notification for "Added to cart" etc.
 *
 * Animates from top, auto-dismisses after 2 seconds.
 */

import React, { useEffect, useRef, useCallback } from "react";
import { View, Text, StyleSheet, Animated, Pressable } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTheme } from "../contexts/ThemeContext";
import { textColor, bgColor, brandGreen, functionalColor } from "../theme";

interface ToastProps {
  message: string;
  type?: "success" | "error" | "info";
  visible: boolean;
  onDismiss: () => void;
}

export default function Toast({ message, type = "success", visible, onDismiss }: ToastProps) {
  const { resolvedTheme } = useTheme();
  const tc = (v: "primary" | "secondary" | "muted") => textColor(resolvedTheme, v);
  const brand = brandGreen(resolvedTheme);
  const successColor = functionalColor(resolvedTheme, "success");
  const errorColor = functionalColor(resolvedTheme, "error");

  const translateY = useRef(new Animated.Value(-80)).current;

  const iconColor = type === "success" ? successColor : type === "error" ? errorColor : functionalColor(resolvedTheme, "info");
  const iconName = type === "success" ? "checkmark-circle" : type === "error" ? "alert-circle" : "information-circle";

  useEffect(() => {
    if (visible) {
      Animated.spring(translateY, {
        toValue: 0,
        friction: 8,
        tension: 100,
        useNativeDriver: true,
      }).start();
      const timer = setTimeout(onDismiss, 2000);
      return () => clearTimeout(timer);
    } else {
      Animated.timing(translateY, {
        toValue: -80,
        duration: 200,
        useNativeDriver: true,
      }).start();
    }
  }, [visible]);

  if (!visible) return null;

  return (
    <Animated.View
      style={[
        styles.container,
        { transform: [{ translateY }], backgroundColor: bgColor(resolvedTheme, "primary") },
      ]}
    >
      <Ionicons name={iconName} size={20} color={iconColor} />
      <Text style={[styles.message, { color: tc("primary") }]} numberOfLines={1}>
        {message}
      </Text>
      <Pressable onPress={onDismiss} hitSlop={8}>
        <Ionicons name="close" size={16} color={tc("muted")} />
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: "absolute",
    top: 60,
    left: 16,
    right: 16,
    height: 48,
    borderRadius: 12,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 14,
    gap: 10,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 8,
    zIndex: 999,
  },
  message: {
    flex: 1,
    fontSize: 14,
    fontWeight: "500",
    lineHeight: 18,
  },
});
