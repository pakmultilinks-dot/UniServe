/**
 * UniServe — Reset Password Screen
 *
 * New password form after email verification.
 * Requires token from deep link or email link.
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
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { LguSeal } from "../../src/components/LguSeal";
import { LguInput, PasswordInput } from "../../src/components/ui/Input";
import { Button } from "../../src/components/ui/Button";
import { useTheme } from "../../src/contexts/ThemeContext";
import { bgColor, textColor, brandGreen, functionalColor } from "../../src/theme";
import * as authApi from "../../src/services/auth";

export default function ResetPasswordScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ token?: string; email?: string }>();
  const { resolvedTheme } = useTheme();

  const bg = bgColor(resolvedTheme, "primary");
  const tc = textColor(resolvedTheme, "primary");
  const tcSec = textColor(resolvedTheme, "secondary");
  const brand = brandGreen(resolvedTheme);

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  const token = params.token ?? "";
  const email = params.email ?? "";

  const passwordsMatch = password === confirmPassword;
  const isFormValid =
    password.length >= 8 &&
    passwordsMatch &&
    token;

  const handleSubmit = async () => {
    if (!isFormValid) return;
    setLoading(true);
    setError("");
    try {
      await authApi.resetPassword({
        token,
        new_password: password,
        confirm_password: confirmPassword,
      });
      setSuccess(true);
    } catch (e: any) {
      setError(e?.message || "Failed to reset password. The link may have expired.");
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <View style={[styles.container, { backgroundColor: bg }]}>
        <View style={styles.centerContent}>
          <View style={[styles.successIcon, { backgroundColor: functionalColor(resolvedTheme, "success") + "15" }]}>
            <Ionicons name="checkmark-circle" size={64} color={functionalColor(resolvedTheme, "success")} />
          </View>
          <Text style={[styles.title, { color: tc }]}>Password Reset</Text>
          <Text style={[styles.subtitle, { color: tcSec }]}>
            Your password has been updated successfully. You can now log in with your new password.
          </Text>
          <View style={styles.buttonContainer}>
            <Button
              title="Go to Login"
              onPress={() => router.replace("/login")}
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
          <Text style={[styles.title, { color: tc }]}>New Password</Text>
          <Text style={[styles.subtitle, { color: tcSec }]}>
            Create a strong password for your account.
          </Text>
        </View>

        <PasswordInput
          label="New Password"
          placeholder="At least 8 characters"
          value={password}
          onChangeText={setPassword}
          autoCapitalize="none"
          error={
            password.length > 0 && password.length < 8
              ? "Password must be at least 8 characters"
              : undefined
          }
        />

        <PasswordInput
          label="Confirm Password"
          placeholder="Re-enter your password"
          value={confirmPassword}
          onChangeText={setConfirmPassword}
          autoCapitalize="none"
          error={
            confirmPassword.length > 0 && !passwordsMatch
              ? "Passwords do not match"
              : error
          }
        />

        <View style={styles.buttonContainer}>
          <Button
            title="Reset Password"
            onPress={handleSubmit}
            loading={loading}
            disabled={!isFormValid || loading}
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
  successIcon: {
    width: 100,
    height: 100,
    borderRadius: 50,
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
  buttonContainer: {
    marginTop: 8,
  },
  footer: {
    marginTop: 16,
    alignItems: "center",
  },
});
