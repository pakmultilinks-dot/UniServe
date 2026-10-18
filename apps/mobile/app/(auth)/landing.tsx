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
        {/* Dark scrim from the top so white text stays readable over any
            photo, then a soft fade into the page background at the bottom. */}
        <LinearGradient
          colors={[
            "rgba(10,7,3,0.82)",
            "rgba(10,7,3,0.55)",
            "rgba(10,7,3,0.35)",
            isDark ? "#14100a" : "#fffdf8",
          ]}
          locations={[0, 0.35, 0.62, 0.92]}
          style={styles.gradient}
        />

        <SafeAreaView style={styles.content} edges={["top", "bottom"]}>
          <View style={styles.logoWrap}>
            <Image
              source={require("../../assets/lgu-logo.jpg")}
              style={styles.logo}
              resizeMode="contain"
              accessibilityLabel="Lahore Garrison University logo"
            />
          </View>

          <View style={styles.textBlock}>
            <Text style={styles.brand}>UniServe</Text>
            <Text style={styles.title}>
              Campus Food{"\n"}Made Easy
            </Text>
            <Text style={styles.subtitle}>
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
            <Text style={styles.loginLinkText}>
              Already have an account? <Text style={styles.loginLinkBold}>Log in</Text>
            </Text>
          </Pressable>

          <Text style={styles.footer}>Lahore Garrison University</Text>
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
  logoWrap: {
    position: "absolute",
    top: 56,
    alignSelf: "center",
  },
  logo: {
    width: 96,
    height: 96,
    borderRadius: 48,
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
    color: "#e8c07a",
  },
  title: {
    fontSize: 48,
    lineHeight: 52,
    fontWeight: "900",
    letterSpacing: -0.5,
    color: "#ffffff",
    textShadowColor: "rgba(0,0,0,0.45)",
    textShadowOffset: { width: 0, height: 2 },
    textShadowRadius: 8,
  },
  subtitle: {
    fontSize: 15,
    lineHeight: 22,
    marginTop: 12,
    maxWidth: 300,
    color: "rgba(255,255,255,0.92)",
    textShadowColor: "rgba(0,0,0,0.4)",
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 6,
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
    color: "rgba(255,255,255,0.75)",
  },
  loginLink: {
    alignItems: "center",
    paddingVertical: 12,
    marginTop: 4,
  },
  loginLinkText: {
    fontSize: 14,
    fontWeight: "500",
    color: "rgba(255,255,255,0.92)",
  },
  loginLinkBold: {
    fontWeight: "700",
    textDecorationLine: "underline",
  },
});
