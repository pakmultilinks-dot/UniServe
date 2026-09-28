import React from "react";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";

import { useTheme } from "../../src/contexts/ThemeContext";
import { bgColor, textColor, colors } from "../../src/theme";

const HERO_IMAGE =
  "https://images.unsplash.com/photo-1629203849820-fdd70d49c38e?auto=format&fit=crop&w=1100&q=90";

export default function OnboardingScreen() {
  const router = useRouter();
  const { resolvedTheme } = useTheme();
  const background = bgColor(resolvedTheme, "secondary");
  const text = textColor(resolvedTheme, "primary");
  const muted = textColor(resolvedTheme, "muted");

  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: background }]}>
      <View style={styles.heroFrame}>
        <Image source={{ uri: HERO_IMAGE }} style={styles.heroImage} resizeMode="cover" />
        <View style={styles.heroFade} />
      </View>

      <View style={styles.content}>
        <Text style={[styles.title, { color: text }]}>Campus Food{`\n`}Made Easy</Text>
        <Text style={[styles.subtitle, { color: muted }]}>
          Order meals, snacks, and drinks from your university cafe in seconds.
        </Text>

        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Get started"
          onPress={() => router.push("/login")}
          style={({ pressed }) => [styles.button, pressed && styles.buttonPressed]}
        >
          <Text style={styles.buttonText}>Get Started</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
  },
  heroFrame: {
    flex: 1,
    minHeight: 360,
    marginHorizontal: 12,
    borderRadius: 32,
    overflow: "hidden",
    backgroundColor: colors.gold[100],
  },
  heroImage: {
    width: "100%",
    height: "100%",
  },
  heroFade: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    height: 150,
    backgroundColor: "rgba(255, 250, 239, 0.52)",
  },
  content: {
    paddingHorizontal: 24,
    paddingTop: 20,
    paddingBottom: 16,
  },
  title: {
    fontSize: 42,
    lineHeight: 46,
    fontWeight: "800",
    letterSpacing: 0,
  },
  subtitle: {
    maxWidth: 300,
    fontSize: 14,
    lineHeight: 20,
    marginTop: 12,
  },
  button: {
    height: 56,
    borderRadius: 28,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 24,
    backgroundColor: colors.gold[500],
  },
  buttonPressed: {
    opacity: 0.82,
    transform: [{ scale: 0.99 }],
  },
  buttonText: {
    color: colors.neutral[900],
    fontSize: 15,
    fontWeight: "700",
  },
});
