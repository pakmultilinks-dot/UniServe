/**
 * UniServe — Register Screen
 *
 * LGU-branded registration with two-column name layout,
 * university ID field, and proper theming.
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

  const tc = (variant: "primary" | "secondary" | "muted") => textColor(resolvedTheme, variant);
  const bg = (variant: "primary" | "secondary" | "tertiary") => bgColor(resolvedTheme, variant);
  const bc = (variant: "default" | "subtle") => borderColor(resolvedTheme, variant);

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
      // Navigate to login with success message
      router.replace("/login");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Registration failed";
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
          <LguSeal size="md" />

          {/* Brand */}
          <Text style={[styles.title, { color: tc("primary") }]}>Create Account</Text>
          <Text style={[styles.subtitle, { color: tc("muted") }]}>
            University-only registration
          </Text>

          {/* Form Card */}
          <View style={[styles.card, { backgroundColor: bg("primary"), borderColor: bc("default") }]}>
            {error ? (
              <View style={styles.errorBox}>
                <Text style={styles.errorText}>⚠ {error}</Text>
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

            <Button
              title={isLoading ? "Creating Account..." : "Register"}
              onPress={handleRegister}
              loading={isLoading}
              disabled={isLoading}
              fullWidth
            />
          </View>

          {/* Login link */}
          <View style={styles.loginRow}>
            <Text style={{ color: tc("secondary"), fontSize: 14 }}>Already have an account? </Text>
            <TouchableOpacity onPress={() => router.replace("/login")}>
              <Text style={[styles.loginLink, { color: colors.brand[700] }]}>Sign in</Text>
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
    fontSize: 24,
    fontWeight: "700",
    marginTop: 12,
  },
  subtitle: {
    fontSize: 14,
    marginTop: 4,
    marginBottom: 24,
  },
  card: {
    width: "100%",
    borderRadius: 12,
    borderWidth: 1,
    padding: 24,
  },
  row: {
    flexDirection: "row",
    gap: 8,
  },
  halfField: {
    flex: 1,
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
  loginRow: {
    flexDirection: "row",
    marginTop: 20,
    alignItems: "center",
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
