/**
 * UniServe — Verify Email Screen
 *
 * 6-digit OTP verification with segmented input, countdown timer,
 * and resend functionality. Institutional but modern design.
 */
import React, { useState, useEffect, useRef } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { LguSeal } from "../../src/components/LguSeal";
import { Button } from "../../src/components/ui/Button";
import { useTheme } from "../../src/contexts/ThemeContext";
import { bgColor, textColor, brandGreen, functionalColor } from "../../src/theme";
import * as authApi from "../../src/services/auth";

const OTP_LENGTH = 6;
const RESEND_COOLDOWN = 60;

export default function VerifyEmailScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ user_id?: string; email?: string }>();
  const { resolvedTheme } = useTheme();

  const bg = bgColor(resolvedTheme, "primary");
  const bgSec = bgColor(resolvedTheme, "secondary");
  const tc = textColor(resolvedTheme, "primary");
  const tcSec = textColor(resolvedTheme, "secondary");
  const tcMuted = textColor(resolvedTheme, "muted");
  const brand = brandGreen(resolvedTheme);

  const userId = params.user_id ?? "";
  const email = params.email ?? "";
  const [otp, setOtp] = useState<string[]>(Array(OTP_LENGTH).fill(""));
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [countdown, setCountdown] = useState(RESEND_COOLDOWN);
  const [canResend, setCanResend] = useState(false);
  const inputs = useRef<(TextInput | null)[]>([]);

  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    } else {
      setCanResend(true);
    }
  }, [countdown]);

  const handleChange = (text: string, index: number) => {
    if (text.length > 1) text = text.slice(-1);
    const newOtp = [...otp];
    newOtp[index] = text;
    setOtp(newOtp);
    setError("");

    if (text && index < OTP_LENGTH - 1) {
      inputs.current[index + 1]?.focus();
    }

    if (newOtp.every((d) => d !== "") && newOtp.join("").length === OTP_LENGTH) {
      handleVerify(newOtp.join(""));
    }
  };

  const handleKeyPress = (key: string, index: number) => {
    if (key === "Backspace" && !otp[index] && index > 0) {
      inputs.current[index - 1]?.focus();
      const newOtp = [...otp];
      newOtp[index - 1] = "";
      setOtp(newOtp);
    }
  };

  const handleVerify = async (code: string) => {
    setLoading(true);
    try {
      await authApi.verifyOtp({ user_id: userId, otp: code, purpose: "email_verification" });
      setSuccess(true);
    } catch (e: any) {
      setError(e?.message || "Invalid verification code");
      setOtp(Array(OTP_LENGTH).fill(""));
      inputs.current[0]?.focus();
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    try {
      await authApi.resendOtp({ user_id: userId, purpose: "email_verification" });
      setCountdown(RESEND_COOLDOWN);
      setCanResend(false);
    } catch (e: any) {
      setError(e?.message || "Failed to resend code");
    }
  };

  if (success) {
    return (
      <View style={[styles.container, { backgroundColor: bg }]}>
        <View style={styles.centerContent}>
          <View style={[styles.successIcon, { backgroundColor: functionalColor(resolvedTheme, "success") + "15" }]}>
            <Ionicons name="checkmark-circle" size={64} color={functionalColor(resolvedTheme, "success")} />
          </View>
          <Text style={[styles.successTitle, { color: tc }]}>Email Verified</Text>
          <Text style={[styles.successSubtitle, { color: tcSec }]}>
            Your email has been verified successfully.
          </Text>
          <View style={styles.buttonContainer}>
            <Button
              title="Continue to Login"
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
        {/* Header */}
        <View style={styles.header}>
          <LguSeal size="md" />
          <Text style={[styles.title, { color: tc }]}>Check Your Email</Text>
          <Text style={[styles.subtitle, { color: tcSec }]}>
            We sent a 6-digit verification code to
          </Text>
          {/* Guard the email line: an empty `email` param otherwise renders a
              stray empty <Text> node (React Native "Text strings must be
              rendered within a <Text>" dev warning). */}
          {email ? (
            <Text style={[styles.email, { color: brand }]}>{email}</Text>
          ) : null}
        </View>

        {/* OTP Input */}
        <View style={styles.otpContainer}>
          {otp.map((digit, index) => (
            <TextInput
              key={index}
              ref={(ref) => { inputs.current[index] = ref; }}
              style={[
                styles.otpBox,
                {
                  borderColor: error
                    ? functionalColor(resolvedTheme, "error")
                    : digit
                    ? brand
                    : resolvedTheme === "dark"
                    ? colors.dark.borderDefault
                    : colors.light.borderDefault,
                  backgroundColor: bgSec,
                  color: tc,
                },
              ]}
              value={digit}
              onChangeText={(text) => handleChange(text, index)}
              onKeyPress={({ nativeEvent }) => handleKeyPress(nativeEvent.key, index)}
              keyboardType="number-pad"
              maxLength={1}
              selectTextOnFocus
              autoFocus={index === 0}
            />
          ))}
        </View>

        {error ? (
          <View style={styles.errorRow}>
            <Ionicons name="alert-circle" size={16} color={functionalColor(resolvedTheme, "error")} />
            <Text style={[styles.errorText, { color: functionalColor(resolvedTheme, "error") }]}>
              {error}
            </Text>
          </View>
        ) : null}

        {/* Loading */}
        {loading && (
          <View style={styles.loadingContainer}>
            <Text style={[styles.loadingText, { color: tcMuted }]}>Verifying...</Text>
          </View>
        )}

        {/* Resend */}
        <View style={styles.resendContainer}>
          <Text style={[styles.resendLabel, { color: tcMuted }]}>Didn't receive the code? </Text>
          {canResend ? (
            <TouchableOpacity onPress={handleResend}>
              <Text style={[styles.resendLink, { color: brand }]}>Resend</Text>
            </TouchableOpacity>
          ) : (
            <Text style={[styles.countdown, { color: tcMuted }]}>Resend in {countdown}s</Text>
          )}
        </View>

        {/* Manual verify button */}
        <View style={styles.buttonContainer}>
          <Button
            title="Verify"
            onPress={() => handleVerify(otp.join(""))}
            loading={loading}
            disabled={otp.join("").length !== OTP_LENGTH || loading}
            fullWidth
          />
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

import { colors } from "../../src/theme/colors";

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
    lineHeight: 20,
  },
  email: {
    fontSize: 15,
    fontWeight: "600",
    marginTop: 4,
  },
  otpContainer: {
    flexDirection: "row",
    justifyContent: "center",
    gap: 10,
    marginBottom: 16,
  },
  otpBox: {
    width: 48,
    height: 56,
    borderWidth: 1.5,
    borderRadius: 10,
    textAlign: "center",
    fontSize: 22,
    fontWeight: "700",
  },
  errorRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    marginBottom: 16,
  },
  errorText: {
    fontSize: 13,
    fontWeight: "500",
  },
  loadingContainer: {
    alignItems: "center",
    marginVertical: 16,
  },
  loadingText: {
    fontSize: 14,
  },
  resendContainer: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    marginVertical: 24,
  },
  resendLabel: {
    fontSize: 14,
  },
  resendLink: {
    fontSize: 14,
    fontWeight: "600",
  },
  countdown: {
    fontSize: 14,
  },
  buttonContainer: {
    marginTop: 16,
  },
  successIcon: {
    width: 100,
    height: 100,
    borderRadius: 50,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 20,
  },
  successTitle: {
    fontSize: 22,
    fontWeight: "700",
    marginBottom: 8,
  },
  successSubtitle: {
    fontSize: 15,
    textAlign: "center",
    lineHeight: 20,
  },
});
