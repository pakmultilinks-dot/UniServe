/**
 * UniServe — LguSeal Component (React Native)
 *
 * SVG-free LGU shield logo rendered with basic React Native shapes.
 */

import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { colors } from "../theme/colors";

interface LguSealProps {
  size?: "sm" | "md" | "lg";
}

const SIZES = {
  sm: { container: 40, text: 12, barWidth: 18, barHeight: 4, bookWidth: 10, bookHeight: 6 },
  md: { container: 60, text: 18, barWidth: 26, barHeight: 5, bookWidth: 14, bookHeight: 8 },
  lg: { container: 80, text: 24, barWidth: 34, barHeight: 7, bookWidth: 18, bookHeight: 10 },
} as const;

export function LguSeal({ size = "md" }: LguSealProps) {
  const s = SIZES[size];

  return (
    <View
      style={[
        styles.shield,
        {
          width: s.container,
          height: s.container,
          borderRadius: s.container * 0.15,
        },
      ]}
    >
      {/* Shield top section */}
      <View style={[styles.shieldBody, { flex: 1 }]}>
        {/* Gold bar */}
        <View
          style={[
            styles.goldBar,
            {
              width: s.barWidth,
              height: s.barHeight,
            },
          ]}
        />
        {/* Book icon */}
        <View
          style={[
            styles.book,
            {
              width: s.bookWidth,
              height: s.bookHeight,
            },
          ]}
        />
      </View>

      {/* LGU text at bottom */}
      <Text style={[styles.lguText, { fontSize: s.text }]}>LGU</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  shield: {
    backgroundColor: colors.brand[700],
    justifyContent: "center",
    alignItems: "center",
    overflow: "hidden",
  },
  shieldBody: {
    width: "100%",
    justifyContent: "center",
    alignItems: "center",
    paddingTop: 6,
  },
  goldBar: {
    backgroundColor: colors.gold[500],
    borderRadius: 2,
    marginBottom: 4,
  },
  book: {
    backgroundColor: "#ffffff",
    borderRadius: 1,
    opacity: 0.9,
  },
  lguText: {
    color: colors.gold[500],
    fontWeight: "800",
    letterSpacing: 2,
    paddingBottom: 4,
  },
});
