/**
 * UniServe — Forgot Password Screen
 *
 * Simple email input to request a password reset link.
 * Institutional but modern design.
 */
import React, { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { LguSeal } from "../../src/components/LguSeal";
import { LguInput } from "../../src/components/ui/Input";
import { Button } from "../../src/components/ui/Button";
import { useTheme } from "../../src/contexts/ThemeContext";
import { bgColor, textColor, brandGreen, functionalColor } from "../../src/theme";
import * as authApi from "../../src/services/auth";

export default function ForgotPasswordScreen() {
  const router = useRouter();
  const { resolvedTheme } = useTheme();

  const bg = bgColor(resolvedTheme, "primary");
  const bgSec = bgColor(resolvedTheme, "secondary");
  const tc = textColor(resolvedTheme, "primary");
  const tcSec = textColor(resolvedTheme, "secondary");
  const brand = brandGreen(resolvedTheme);

  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const isValidEmail = email.trim().includes("@") && email.trim().includes(".");

  const handleSubmit = async () => {
    if (!isValidEmail) return;
    setLoading(true);
    setError("");
    try {
      await authApi.requestPasswordReset({ university_email: email.trim() });
      setSent(true);
    } catch (e: any) {
      // Show success even if email doesn't exist (security best practice)
      setSent(true);
    } finally {
      setLoading(false);
    }
  };

  if (sent) {
    return (
      <View style={[styles.container, { backgroundColor: bg }]}>
        <View style={styles.centerContent}>
          <View style={[styles.iconCircle, { backgroundColor: brand + "15" }]}>
            <Ionicons name="mail-open-outline" size={48} color={brand} />
          </View>
          <Text style={[styles.title, { color: tc }]}>Check Your Email</Text>
          <Text style={[styles.subtitle, { color: tcSec }]}>
            If an account exists with <Text style={{ fontWeight: "600" }}>{email.trim()}</Text>,
            we've sent instructions to reset your password.
          </Text>
          <Text style={[styles.hint, { color: tcSec }]}>
            Didn't receive it? Check your spam folder or try again.
          </Text>
          <View style={styles.buttonGroup}>
            <Button
              title="Back to Login"
              onPress={() => router.replace("/login")}
              fullWidth
            />
            <View style={{ height: 12 }} />
            <Button
              title="Try Again"
              onPress={() => { setSent(false); setEmail(""); }}
              variant="ghost"
              fullWidth
            />
          </View>
        </View>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={[styles.container, { backgroundColor: bg }]}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.header}>
          <LguSeal size="md" />
          <Text style={[styles.title, { color: tc }]}>Forgot Password?</Text>
          <Text style={[styles.subtitle, { color: tcSec }]}>
            Enter your university email address and we'll send you a link to reset your password.
          </Text>
        </View>

        <LguInput
          label="University Email"
          placeholder="you@lgu.edu.pk"
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          autoCapitalize="none"
          autoCorrect={false}
          autoComplete="email"
          error={error}
        />

        <View style={styles.buttonContainer}>
          <Button
            title="Send Reset Link"
            onPress={handleSubmit}
            loading={loading}
            disabled={!isValidEmail || loading}
            fullWidth
          />
        </View>

        <View style={styles.footer}>
          <Button
            title="Back to Login"
            onPress={() => router.back()}
            variant="ghost"
            fullWidth
          />
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: 24,
    paddingTop: 40,
    paddingBottom: 32,
  },
  centerContent: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 24,
  },
  header: {
    alignItems: "center",
    marginBottom: 40,
  },
  iconCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 20,
  },
  title: {
    fontSize: 22,
    fontWeight: "700",
    marginTop: 20,
    letterSpacing: -0.3,
  },
  subtitle: {
    fontSize: 15,
    marginTop: 8,
    textAlign: "center",
    lineHeight: 22,
    paddingHorizontal: 12,
  },
  hint: {
    fontSize: 13,
    marginTop: 12,
    textAlign: "center",
  },
  buttonContainer: {
    marginTop: 8,
  },
  footer: {
    marginTop: 16,
    alignItems: "center",
  },
  buttonGroup: {
    marginTop: 24,
    width: "100%",
  },
});
