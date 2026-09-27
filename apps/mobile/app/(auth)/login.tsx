/**
 * UniServe — Login Screen
 *
 * LGU-branded login with proper theming, password visibility toggle,
 * and error/success states.
 */
import React, { useState } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { useRouter } from "expo-router";

import { useAuth } from "../../src/contexts/AuthContext";
import { useTheme } from "../../src/contexts/ThemeContext";
import { LguSeal } from "../../src/components/LguSeal";
import { Button } from "../../src/components/ui";
import { PasswordInput, LguInput } from "../../src/components/ui/Input";
import { colors, textColor, bgColor, borderColor } from "../../src/theme";

export default function LoginScreen() {
  const router = useRouter();
  const { login } = useAuth();
  const { resolvedTheme } = useTheme();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const tc = (variant: "primary" | "secondary" | "muted") => textColor(resolvedTheme, variant);
  const bg = (variant: "primary" | "secondary" | "tertiary") => bgColor(resolvedTheme, variant);
  const bc = (variant: "default" | "subtle") => borderColor(resolvedTheme, variant);

  const handleLogin = async () => {
    if (!email.trim() || !password) {
      setError("Please enter both email and password");
      return;
    }
    setError("");
    setIsLoading(true);
    try {
      await login(email.trim(), password);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Login failed";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={[styles.screen, { backgroundColor: bg("secondary") }]}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.container}>
          {/* LGU Seal */}
          <LguSeal size="lg" />

          {/* Brand */}
          <Text style={[styles.title, { color: tc("primary") }]}>UniServe</Text>
          <Text style={[styles.subtitle, { color: tc("muted") }]}>
            University Cafeteria Platform
          </Text>

          {/* Form Card */}
          <View style={[styles.card, { backgroundColor: bg("primary"), borderColor: bc("default") }]}>
            {error ? (
              <View style={styles.errorBox}>
                <Text style={styles.errorText}>⚠ {error}</Text>
              </View>
            ) : null}

            <LguInput
              label="University Email"
              placeholder="you@lgu.edu.pk"
              value={email}
              onChangeText={(text: string) => { setEmail(text); setError(""); }}
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
              autoComplete="email"
            />

            <PasswordInput
              label="Password"
              placeholder="Enter your password"
              value={password}
              onChangeText={(text: string) => { setPassword(text); setError(""); }}
              autoComplete="password"
            />

            <Button
              title={isLoading ? "Signing in..." : "Sign In"}
              onPress={handleLogin}
              loading={isLoading}
              disabled={isLoading}
              fullWidth
            />

            {/* Links */}
            <View style={styles.links}>
              <TouchableOpacity onPress={() => router.push("/login")}>
                <Text style={[styles.link, { color: colors.brand[700] }]}>Forgot password?</Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* Register link */}
          <View style={styles.registerRow}>
            <Text style={{ color: tc("secondary"), fontSize: 14 }}>Don&apos;t have an account? </Text>
            <TouchableOpacity onPress={() => router.push("/register")}>
              <Text style={[styles.registerLink, { color: colors.brand[700] }]}>Register</Text>
            </TouchableOpacity>
          </View>

          {/* Footer */}
          <Text style={[styles.footer, { color: tc("muted") }]}>
            Larino Technological University
          </Text>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: "center",
    padding: 24,
  },
  container: {
    alignItems: "center",
  },
  title: {
    fontSize: 28,
    fontWeight: "700",
    marginTop: 16,
    letterSpacing: -0.5,
  },
  subtitle: {
    fontSize: 14,
    marginTop: 4,
    marginBottom: 32,
  },
  card: {
    width: "100%",
    borderRadius: 12,
    borderWidth: 1,
    padding: 24,
  },
  errorBox: {
    backgroundColor: "#fef2f2",
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: "#fecaca",
  },
  errorText: {
    color: "#991b1b",
    fontSize: 14,
  },
  links: {
    marginTop: 16,
    alignItems: "center",
  },
  link: {
    fontSize: 14,
    fontWeight: "500",
  },
  registerRow: {
    flexDirection: "row",
    marginTop: 24,
    alignItems: "center",
  },
  registerLink: {
    fontSize: 14,
    fontWeight: "600",
  },
  footer: {
    fontSize: 12,
    marginTop: 32,
    textAlign: "center",
  },
});
