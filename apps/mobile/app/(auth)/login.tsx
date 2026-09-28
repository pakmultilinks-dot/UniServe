/**
 * UniServe — Login Screen
 *
 * Institutional but modern login with:
 * - LGU seal, brand wordmark, proper subtitle
 * - Email + password form with 48px height inputs
 * - Forgot password link → actual route
 * - Register link
 * - Proper footer: "Lahore Garrison University"
 * - Theme-aware, dark mode ready
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
import { Ionicons } from "@expo/vector-icons";

import { useAuth } from "../../src/contexts/AuthContext";
import { useTheme } from "../../src/contexts/ThemeContext";
import { Button } from "../../src/components/ui";
import { PasswordInput, LguInput } from "../../src/components/ui/Input";
import { colors, textColor, bgColor, borderColor, functionalColor } from "../../src/theme";

export default function LoginScreen() {
  const router = useRouter();
  const { login } = useAuth();
  const { resolvedTheme } = useTheme();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const bg = bgColor(resolvedTheme, "secondary");
  const bgPrimary = bgColor(resolvedTheme, "primary");
  const tc = textColor(resolvedTheme, "primary");
  const tcSec = textColor(resolvedTheme, "secondary");
  const tcMuted = textColor(resolvedTheme, "muted");
  const bc = borderColor(resolvedTheme, "default");
  const brand = colors.brand[700];

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
      style={[styles.screen, { backgroundColor: bg }]}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={[styles.wordmark, { color: tc }]}>Welcome Back!</Text>
        <Text style={[styles.subtitle, { color: tcMuted }]}>
          Sign in to order meals, snacks, and drinks on campus.
        </Text>

        {/* Form */}
        <View style={styles.form}>
          {error ? (
            <View style={[styles.errorBox, { backgroundColor: functionalColor(resolvedTheme, "error") + "10", borderColor: functionalColor(resolvedTheme, "error") + "40" }]}>
              <Ionicons name="alert-circle" size={16} color={functionalColor(resolvedTheme, "error")} />
              <Text style={[styles.errorText, { color: functionalColor(resolvedTheme, "error") }]}>
                {error}
              </Text>
            </View>
          ) : null}

          <LguInput
            label="LGU Student Email"
            placeholder="student@lgu.edu.pk"
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

          {/* Forgot password */}
          <TouchableOpacity
            onPress={() => router.push("/forgot-password")}
            style={styles.forgotRow}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          >
            <Text style={[styles.forgotLink, { color: brand }]}>Forgot password?</Text>
          </TouchableOpacity>

          <View style={{ height: 12 }} />

          <Button
            title={isLoading ? "Signing in..." : "Log In"}
            onPress={handleLogin}
            loading={isLoading}
            disabled={isLoading}
            fullWidth
          />
        </View>

        {/* Register */}
        <View style={styles.registerRow}>
          <Text style={{ color: tcSec, fontSize: 14 }}>Don&apos;t have an account? </Text>
          <TouchableOpacity onPress={() => router.push("/register")}>
            <Text style={[styles.registerLink, { color: brand }]}>Register</Text>
          </TouchableOpacity>
        </View>

        {/* Footer */}
        <Text style={[styles.footer, { color: tcMuted }]}>
          Lahore Garrison University
        </Text>
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
    paddingHorizontal: 24,
    paddingTop: 140,
    paddingBottom: 32,
  },
  wordmark: {
    fontSize: 28,
    fontWeight: "700",
    textAlign: "center",
    letterSpacing: 0,
  },
  subtitle: {
    fontSize: 14,
    textAlign: "center",
    marginTop: 4,
    marginBottom: 42,
    fontStyle: "italic",
  },
  form: {
    marginBottom: 8,
  },
  errorBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    borderRadius: 10,
    padding: 12,
    marginBottom: 16,
    borderWidth: 1,
  },
  errorText: {
    fontSize: 14,
    flex: 1,
  },
  forgotRow: {
    alignItems: "flex-end",
    marginTop: 4,
  },
  forgotLink: {
    fontSize: 14,
    fontWeight: "500",
  },
  registerRow: {
    flexDirection: "row",
    marginTop: 24,
    alignItems: "center",
    justifyContent: "center",
  },
  registerLink: {
    fontSize: 14,
    fontWeight: "600",
  },
  footer: {
    fontSize: 12,
    marginTop: "auto",
    textAlign: "center",
  },
});
