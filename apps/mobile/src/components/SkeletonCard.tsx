/**
 * SkeletonCard — Loading skeleton for food cards.
 *
 * Design spec: Square image placeholder (bgTertiary, borderRadius 12),
 * 2-3 text lines (bgTertiary, borderRadius 4, height 12-14px).
 */

import React, { useEffect, useRef } from "react";
import { View, StyleSheet, Animated } from "react-native";
import { useTheme } from "../contexts/ThemeContext";
import { bgColor } from "../theme";

export default function SkeletonCard() {
  const { resolvedTheme } = useTheme();
  const bg3 = bgColor(resolvedTheme, "tertiary");
  const opacity = useRef(new Animated.Value(0.4)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, {
          toValue: 1,
          duration: 600,
          useNativeDriver: true,
        }),
        Animated.timing(opacity, {
          toValue: 0.4,
          duration: 600,
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, []);

  return (
    <View style={[styles.card, { borderColor: bgColor(resolvedTheme, "tertiary") }]}>
      <Animated.View style={[styles.image, { backgroundColor: bg3, opacity }]} />
      <View style={styles.content}>
        <Animated.View style={[styles.line, { backgroundColor: bg3, opacity, width: "70%" }]} />
        <Animated.View style={[styles.line, { backgroundColor: bg3, opacity, width: "40%" }]} />
        <View style={styles.priceRow}>
          <Animated.View style={[styles.line, { backgroundColor: bg3, opacity, width: 60 }]} />
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 12,
    overflow: "hidden",
    borderWidth: 1,
  },
  image: {
    width: "100%",
    aspectRatio: 1,
  },
  content: {
    padding: 10,
    gap: 6,
  },
  line: {
    height: 12,
    borderRadius: 4,
  },
  priceRow: {
    marginTop: 4,
  },
});
