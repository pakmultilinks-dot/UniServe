/**
 * UniServe — LguSeal Component (React Native)
 *
 * Renders the existing UniServe institutional mark (shared with the web app) for
 * consistent branding across web and mobile. Falls back to the drawn
 * shield if the image asset is unavailable.
 */

import React, { useState } from "react";
import { Image, View, Text, StyleSheet } from "react-native";
import { colors } from "../theme/colors";

interface LguSealProps {
  size?: "sm" | "md" | "lg";
}

const SIZES = {
  sm: { container: 40, text: 12, barWidth: 18, barHeight: 4, bookWidth: 10, bookHeight: 6 },
  md: { container: 60, text: 18, barWidth: 26, barHeight: 5, bookWidth: 14, bookHeight: 8 },
  lg: { container: 80, text: 24, barWidth: 34, barHeight: 7, bookWidth: 18, bookHeight: 10 },
} as const;

// Rasterized from the existing web SVG mark; never a UI reference screenshot.
const LGU_LOGO = require("../../assets/lgu-logo.jpg");

export function LguSeal({ size = "md" }: LguSealProps) {
  const s = SIZES[size];
  const [imageFailed, setImageFailed] = useState(false);

  if (!imageFailed) {
    return (
      <Image
        source={LGU_LOGO}
        style={{
          width: s.container,
          height: s.container,
          borderRadius: s.container * 0.15,
        }}
        resizeMode="cover"
        accessibilityLabel="UniServe — Lahore Garrison University"
        onError={() => setImageFailed(true)}
      />
    );
  }

  // Fallback: drawn shield (only if the bundled asset is missing).
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
      <View style={[styles.shieldBody, { flex: 1 }]}>
        <View
          style={[
            styles.goldBar,
            {
              width: s.barWidth,
              height: s.barHeight,
            },
          ]}
        />
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
