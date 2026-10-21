/**
 * UniServe — Register Screen
 *
 * Institutional registration with proper theming, university-only
 * messaging, two-column name, university ID, and proper footer.
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
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { useAuth } from "../../src/contexts/AuthContext";
import { useTheme } from "../../src/contexts/ThemeContext";
import { LguSeal } from "../../src/components/LguSeal";
import { Button } from "../../src/components/ui";
import { PasswordInput, LguInput } from "../../src/components/ui/Input";
import { colors, textColor, bgColor, borderColor, functionalColor } from "../../src/theme";

export default function RegisterScreen() {
  const router = useRouter();
  const { register } = useAuth();
  const { resolvedTheme } = useTheme();

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [universityId, setUniversityId] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const bg = bgColor(resolvedTheme, "secondary");
  const tc = textColor(resolvedTheme, "primary");
  const tcSec = textColor(resolvedTheme, "secondary");
  const tcMuted = textColor(resolvedTheme, "muted");
  const brand = colors.brand[700];

  const handleRegister = async () => {
    if (!firstName.trim() || !lastName.trim() || !email.trim() || !password) {
      setError("Please fill in all required fields");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    setError("");
    setIsLoading(true);
    try {
      const result = await register({
        firstName: firstName.trim(),
        lastName: lastName.trim(),
        universityId: universityId.trim() || email.split("@")[0],
        email: email.trim(),
        password,
      });
      // Navigate to verify-email after registration
      router.replace(`/verify-email?user_id=${encodeURIComponent(result.userId)}&email=${encodeURIComponent(email.trim())}`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Registration failed";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: bg }]} edges={["top", "bottom"]}>
    <KeyboardAvoidingView
      style={[styles.screen, { backgroundColor: bg }]}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        {/* Seal */}
        <View style={styles.sealRow}>
          <LguSeal size="md" />
        </View>

        {/* Brand */}
        <Text style={[styles.wordmark, { color: tc }]}>Create Account</Text>
        <Text style={[styles.subtitle, { color: tcMuted }]}>
          University-only registration
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

          {/* Name Row */}
          <View style={styles.row}>
            <View style={styles.halfField}>
              <LguInput
                label="First Name"
                placeholder="First name"
                value={firstName}
                onChangeText={(text: string) => { setFirstName(text); setError(""); }}
                autoCapitalize="words"
              />
            </View>
            <View style={styles.halfField}>
              <LguInput
                label="Last Name"
                placeholder="Last name"
                value={lastName}
                onChangeText={(text: string) => { setLastName(text); setError(""); }}
                autoCapitalize="words"
              />
            </View>
          </View>

          <LguInput
            label="University ID"
            placeholder="e.g., 2024-00001"
            value={universityId}
            onChangeText={setUniversityId}
            autoCapitalize="none"
            hint="Your university student/staff ID"
          />

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
            placeholder="Min 8 characters"
            value={password}
            onChangeText={(text: string) => { setPassword(text); setError(""); }}
            autoComplete="new-password"
          />

          <PasswordInput
            label="Confirm Password"
            placeholder="Re-enter password"
            value={confirmPassword}
            onChangeText={(text: string) => { setConfirmPassword(text); setError(""); }}
            autoComplete="new-password"
          />

          <View style={{ height: 4 }} />

          <Button
            title={isLoading ? "Creating Account..." : "Create Account"}
            onPress={handleRegister}
            loading={isLoading}
            disabled={isLoading}
            fullWidth
          />
        </View>

        {/* Login link */}
        <View style={styles.loginRow}>
          <Text style={{ color: tcSec, fontSize: 14 }}>Already have an account? </Text>
          <TouchableOpacity onPress={() => router.replace("/login")}>
            <Text style={[styles.loginLink, { color: brand }]}>Sign in</Text>
          </TouchableOpacity>
        </View>

        {/* Footer */}
        <Text style={[styles.footer, { color: tcMuted }]}>
          Lahore Garrison University
        </Text>
      </ScrollView>
    </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: 24,
    paddingTop: 24,
    paddingBottom: 32,
  },
  sealRow: {
    alignItems: "center",
    marginBottom: 4,
  },
  wordmark: {
    fontSize: 24,
    fontWeight: "700",
    textAlign: "center",
    letterSpacing: -0.3,
  },
  subtitle: {
    fontSize: 14,
    textAlign: "center",
    marginTop: 4,
    marginBottom: 18,
  },
  form: {
    marginBottom: 8,
  },
  row: {
    flexDirection: "row",
    gap: 8,
  },
  halfField: {
    flex: 1,
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
  loginRow: {
    flexDirection: "row",
    marginTop: 20,
    alignItems: "center",
    justifyContent: "center",
  },
  loginLink: {
    fontSize: 14,
    fontWeight: "600",
  },
  footer: {
    fontSize: 12,
    marginTop: 24,
    textAlign: "center",
  },
});
