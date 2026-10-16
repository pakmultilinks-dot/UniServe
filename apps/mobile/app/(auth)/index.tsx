/**
 * UniServe — Onboarding / Landing Screen
 *
 * Premium full-screen landing page inspired by modern food-delivery apps.
 * Full-bleed hero image, bold title, subtitle, and Get Started CTA.
 */
import React from "react";
import {
  Image,
  ImageBackground,
  Pressable,
  StyleSheet,
  Text,
  View,
  Dimensions,
} from "react-native";
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { LinearGradient } from "expo-linear-gradient";

import { useTheme } from "../../src/contexts/ThemeContext";
import { textColor, colors } from "../../src/theme";

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get("window");

// Appetizing campus food hero: biryani-style spread
const HERO_IMAGE =
  "https://images.unsplash.com/photo-1585937421612-70a008356fbe?auto=format&fit=crop&w=1200&q=90";

export default function OnboardingScreen() {
  const router = useRouter();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  return (
    <View style={styles.screen}>
      <ImageBackground
        source={{ uri: HERO_IMAGE }}
        style={styles.hero}
        resizeMode="cover"
      >
        {/* Soft gradient fade from transparent (top) to background (bottom) */}
        <LinearGradient
          colors={[
            "transparent",
            isDark ? "rgba(20,14,8,0.35)" : "rgba(255,253,248,0.25)",
            isDark ? "#14100a" : "#fffdf8",
          ]}
          locations={[0.35, 0.62, 0.88]}
          style={styles.gradient}
        />

        <SafeAreaView style={styles.content} edges={["bottom"]}>
          <View style={styles.textBlock}>
            <Text
              style={[
                styles.brand,
                { color: isDark ? colors.gold[300] : colors.gold[700] },
              ]}
            >
              UniServe
            </Text>
            <Text
              style={[
                styles.title,
                { color: textColor(resolvedTheme, "primary") },
              ]}
            >
              Campus Food{"\n"}Made Easy
            </Text>
            <Text
              style={[
                styles.subtitle,
                { color: textColor(resolvedTheme, "secondary") },
              ]}
            >
              Order your favorite meals in seconds, made for speed and
              simplicity.
            </Text>
          </View>

          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Get started"
            onPress={() => router.push("/register")}
            style={({ pressed }) => [
              styles.button,
              pressed && styles.buttonPressed,
            ]}
          >
            <Text style={styles.buttonText}>Get Started</Text>
          </Pressable>

          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Log in"
            onPress={() => router.push("/login")}
            style={styles.loginLink}
          >
            <Text
              style={[
                styles.loginLinkText,
                { color: textColor(resolvedTheme, "primary") },
              ]}
            >
              Already have an account? <Text style={styles.loginLinkBold}>Log in</Text>
            </Text>
          </Pressable>

          <Text
            style={[styles.footer, { color: textColor(resolvedTheme, "muted") }]}
          >
            Lahore Garrison University
          </Text>
        </SafeAreaView>
      </ImageBackground>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: "#fffdf8",
  },
  hero: {
    flex: 1,
    width: SCREEN_WIDTH,
    height: SCREEN_HEIGHT,
  },
  gradient: {
    ...StyleSheet.absoluteFill,
  },
  content: {
    flex: 1,
    justifyContent: "flex-end",
    paddingHorizontal: 28,
    paddingBottom: 36,
  },
  textBlock: {
    marginBottom: 28,
  },
  brand: {
    fontSize: 14,
    fontWeight: "800",
    letterSpacing: 3,
    textTransform: "uppercase",
    marginBottom: 10,
  },
  title: {
    fontSize: 48,
    lineHeight: 52,
    fontWeight: "900",
    letterSpacing: -0.5,
  },
  subtitle: {
    fontSize: 15,
    lineHeight: 22,
    marginTop: 12,
    maxWidth: 300,
  },
  button: {
    height: 58,
    borderRadius: 29,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#d4a95c",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 4,
  },
  buttonPressed: {
    opacity: 0.88,
    transform: [{ scale: 0.98 }],
  },
  buttonText: {
    color: "#1a1208",
    fontSize: 17,
    fontWeight: "700",
    letterSpacing: 0.3,
  },
  footer: {
    textAlign: "center",
    fontSize: 12,
    marginTop: 16,
    fontWeight: "500",
  },
  loginLink: {
    alignItems: "center",
    paddingVertical: 12,
    marginTop: 4,
  },
  loginLinkText: {
    fontSize: 14,
    fontWeight: "500",
  },
  loginLinkBold: {
    fontWeight: "700",
    textDecorationLine: "underline",
  },
});
