/**
 * SearchBar — Instant search input for menu items.
 *
 * Follows the design spec: height 44, borderRadius 12, bgSecondary background,
 * no border, 15px font, search icon + clear button.
 */

import React from "react";
import { View, TextInput, StyleSheet, Pressable } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTheme } from "../contexts/ThemeContext";
import { textColor, bgColor } from "../theme";

interface SearchBarProps {
  value: string;
  onChangeText: (text: string) => void;
  placeholder?: string;
  resultCount?: number;
}

export default function SearchBar({
  value,
  onChangeText,
  placeholder = "Search menu...",
  resultCount,
}: SearchBarProps) {
  const { resolvedTheme } = useTheme();
  const tc = (v: "primary" | "secondary" | "muted") => textColor(resolvedTheme, v);
  const bg = (v: "primary" | "secondary" | "tertiary") => bgColor(resolvedTheme, v);

  return (
    <View style={styles.wrapper}>
      <View style={[styles.container, { backgroundColor: bg("secondary") }]}>
        <Ionicons name="search" size={18} color={tc("muted")} style={styles.icon} />
        <TextInput
          style={[styles.input, { color: tc("primary") }]}
          value={value}
          onChangeText={onChangeText}
          placeholder={placeholder}
          placeholderTextColor={tc("muted")}
          returnKeyType="search"
          autoCapitalize="none"
          autoCorrect={false}
        />
        {value.length > 0 && (
          <Pressable
            onPress={() => onChangeText("")}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            style={styles.clearBtn}
          >
            <Ionicons name="close-circle" size={18} color={tc("muted")} />
          </Pressable>
        )}
      </View>
      {resultCount !== undefined && value.length > 0 && (
        <View style={styles.resultCount}>
          <View style={[styles.resultDot, { backgroundColor: tc("muted") }]} />
          <View style={[styles.resultLine, { backgroundColor: bg("tertiary") }]} />
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    paddingHorizontal: 20,
  },
  container: {
    height: 44,
    borderRadius: 12,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 14,
  },
  icon: {
    marginRight: 10,
  },
  input: {
    flex: 1,
    fontSize: 15,
    fontWeight: "400",
    lineHeight: 20,
    padding: 0,
  },
  clearBtn: {
    marginLeft: 8,
  },
  resultCount: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 6,
    paddingHorizontal: 2,
  },
  resultDot: {
    width: 4,
    height: 4,
    borderRadius: 2,
    marginRight: 6,
  },
  resultLine: {
    height: 1,
    flex: 1,
    borderRadius: 1,
  },
});
