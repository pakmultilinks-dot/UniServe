/**
 * UniServe — Profile Screen
 *
 * User profile info organized into sections: Account, Security, Support.
 * Uses Ionicons for all icons, no emojis.
 */
import React, { useState, useEffect } from "react";
import { View, Text, ScrollView, StyleSheet, Pressable } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { useAuth } from "../../../src/contexts/AuthContext";
import { useTheme } from "../../../src/contexts/ThemeContext";
import { SafeAreaView } from "react-native-safe-area-context";

import { BottomSheet, Button, ConfirmDialog, PasswordInput, Toast } from "../../../src/components/ui";
import { SecureStorage } from "../../../src/services/secure-storage";
import * as authApi from "../../../src/services/auth";
import { textColor, bgColor, borderColor, brandGreen, brandText, functionalColor } from "../../../src/theme";

// ── Helpers ──

function formatRole(role?: string): string {
  if (!role) return "Student";
  return role
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

// ── Section Row ──

interface SectionRowProps {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  value?: string;
  onPress?: () => void;
  color?: string;
  isLast?: boolean;
  theme: "light" | "dark";
}

function SectionRow({ icon, label, value, onPress, color, isLast, theme }: SectionRowProps) {
  const tc = textColor(theme, "primary");
  const tcMuted = textColor(theme, "muted");
  const bc = borderColor(theme, "subtle");

  const row = (
    <View style={[styles.row, !isLast && { borderBottomColor: bc, borderBottomWidth: StyleSheet.hairlineWidth }]}>
      <Ionicons name={icon} size={20} color={color ?? tcMuted} />
      <Text style={[styles.rowLabel, { color: color ?? tc }]}>{label}</Text>
      <View style={styles.rowRight}>
        {value && <Text style={[styles.rowValue, { color: tcMuted }]}>{value}</Text>}
        {onPress && (
          <Ionicons name="chevron-forward" size={16} color={tcMuted} style={{ opacity: 0.5 }} />
        )}
      </View>
    </View>
  );

  if (onPress) {
    return <Pressable onPress={onPress}>{row}</Pressable>;
  }
  return row;
}

// ── Screen ──

export default function ProfileScreen() {
  const { user, logout, logoutAll } = useAuth();
  const { resolvedTheme, themePreference, setThemePreference } = useTheme();
  const theme = resolvedTheme as "light" | "dark";

  const brand = brandGreen(resolvedTheme);
  const brandTxt = brandText(resolvedTheme);
  const tc = textColor(resolvedTheme, "primary");
  const tcMuted = textColor(resolvedTheme, "muted");
  const bg = bgColor(resolvedTheme, "primary");
  const bc = borderColor(resolvedTheme, "default");

  const initials = [user?.first_name?.[0], user?.last_name?.[0]]
    .filter(Boolean)
    .join("")
    .toUpperCase() || "?";

  // P3-1: Expo web never surfaces Alert.alert (no dialog, no callback), so
  // sign-out controls were inert in the browser. ConfirmDialog is a plain RN
  // Modal — it renders on native and web with the same button callbacks.
  const [signOutDialog, setSignOutDialog] = useState<"none" | "single" | "all">("none");

  const handleLogout = () => {
    setSignOutDialog("single");
  };

  const handleLogoutAll = () => {
    setSignOutDialog("all");
  };

  const closeDialog = () => setSignOutDialog("none");

  // Phase 58 — Workstream F: change-password self-service (POST /auth/password/change).
  const [passwordSheet, setPasswordSheet] = useState(false);
  const [themeSheetVisible, setThemeSheetVisible] = useState(false);
  const [pwdCurrent, setPwdCurrent] = useState("");
  const [pwdNew, setPwdNew] = useState("");
  const [pwdConfirm, setPwdConfirm] = useState("");
  const [pwdSubmitting, setPwdSubmitting] = useState(false);
  const [pwdError, setPwdError] = useState("");

  // Phase 58 — Workstream G: PIN self-service. The backend exposes no
  // pin_enabled flag in any response, so these forms never claim a PIN is
  // currently active — server error/success messages are surfaced verbatim.
  const [pinSheet, setPinSheet] = useState(false);
  // Local PIN-enabled flag (backend exposes no pin_enabled field). Stored in
  // secure storage so the row can show On/Off.
  const [pinEnabled, setPinEnabled] = useState<boolean | null>(null);

  useEffect(() => {
    SecureStorage.getItemAsync("uniserve_pin_enabled").then((v) => {
      setPinEnabled(v === "1");
    });
  }, []);
  const [pinMode, setPinMode] = useState<"enable" | "change" | "disable">("enable");
  const [pinCurrentPassword, setPinCurrentPassword] = useState("");
  const [pinCurrent, setPinCurrent] = useState("");
  const [pinNew, setPinNew] = useState("");
  const [pinConfirm, setPinConfirm] = useState("");
  const [pinSubmitting, setPinSubmitting] = useState(false);
  const [pinError, setPinError] = useState("");
  const [pinSuccess, setPinSuccess] = useState("");
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "info" } | null>(null);

  const PIN_DIGITS = /^\d{4}$/;

  const openPasswordSheet = () => {
    setPwdCurrent(""); setPwdNew(""); setPwdConfirm("");
    setPwdError("");
    setPasswordSheet(true);
  };

  const openPinSheet = () => {
    setPinMode("enable");
    setPinCurrentPassword(""); setPinCurrent(""); setPinNew(""); setPinConfirm("");
    setPinError(""); setPinSuccess("");
    setPinSheet(true);
  };

  const resetPinForm = () => {
    setPinMode("enable");
    setPinCurrentPassword(""); setPinCurrent(""); setPinNew(""); setPinConfirm("");
    setPinError(""); setPinSuccess("");
  };

  const handleChangePassword = async () => {
    if (!pwdCurrent) { setPwdError("Enter your current password."); return; }
    if (
      pwdNew.length < 8 ||
      !/[A-Z]/.test(pwdNew) ||
      !/[a-z]/.test(pwdNew) ||
      !/\d/.test(pwdNew)
    ) {
      setPwdError("New password must be at least 8 characters and include an uppercase letter, a lowercase letter, and a digit.");
      return;
    }
    if (pwdNew !== pwdConfirm) { setPwdError("New passwords do not match."); return; }
    setPwdError("");
    setPwdSubmitting(true);
    try {
      const res = await authApi.changePassword({
        current_password: pwdCurrent,
        new_password: pwdNew,
      });
      setPasswordSheet(false);
      setPwdCurrent(""); setPwdNew(""); setPwdConfirm("");
      setToast({ message: res.message || "Password changed", type: "success" });
    } catch (err) {
      setPwdError(err instanceof Error ? err.message : "Could not change password.");
    } finally {
      setPwdSubmitting(false);
    }
  };

  const handlePinSubmit = async () => {
    setPinError("");
    setPinSuccess("");
    if (pinMode === "enable") {
      if (!pinCurrentPassword) { setPinError("Enter your current password."); return; }
      if (!PIN_DIGITS.test(pinNew)) { setPinError("PIN must be exactly 4 digits."); return; }
      if (pinNew !== pinConfirm) { setPinError("PINs do not match."); return; }
      setPinSubmitting(true);
      try {
        const res = await authApi.enablePin({
          current_password: pinCurrentPassword,
          pin: pinNew,
          confirm_pin: pinConfirm,
        });
        setPinSheet(false);
        resetPinForm();
        await SecureStorage.setItemAsync("uniserve_pin_enabled", "1");
        setPinEnabled(true);
        setToast({ message: res.message || "PIN enabled", type: "success" });
      } catch (err) {
        setPinError(err instanceof Error ? err.message : "Could not enable PIN.");
      } finally {
        setPinSubmitting(false);
      }
    } else if (pinMode === "change") {
      if (!PIN_DIGITS.test(pinCurrent)) { setPinError("Current PIN must be exactly 4 digits."); return; }
      if (!PIN_DIGITS.test(pinNew)) { setPinError("New PIN must be exactly 4 digits."); return; }
      if (pinNew !== pinConfirm) { setPinError("PINs do not match."); return; }
      setPinSubmitting(true);
      try {
        const res = await authApi.changePin({
          current_pin: pinCurrent,
          new_pin: pinNew,
          confirm_pin: pinConfirm,
        });
        setPinSheet(false);
        resetPinForm();
        setToast({ message: res.message || "PIN changed", type: "success" });
      } catch (err) {
        setPinError(err instanceof Error ? err.message : "Could not change PIN.");
      } finally {
        setPinSubmitting(false);
      }
    } else {
      if (!pinCurrentPassword) { setPinError("Enter your current password."); return; }
      setPinSubmitting(true);
      try {
        const res = await authApi.disablePin({ current_password: pinCurrentPassword });
        setPinSheet(false);
        resetPinForm();
        await SecureStorage.deleteItemAsync("uniserve_pin_enabled");
        setPinEnabled(false);
        setToast({ message: res.message || "PIN disabled", type: "success" });
      } catch (err) {
        setPinError(err instanceof Error ? err.message : "Could not disable PIN.");
      } finally {
        setPinSubmitting(false);
      }
    }
  };

  return (
    <>
      <ConfirmDialog
        visible={signOutDialog === "single"}
        title="Sign Out"
        message="Are you sure you want to sign out?"
        confirmLabel="Sign Out"
        cancelLabel="Cancel"
        destructive
        onCancel={closeDialog}
        onConfirm={() => {
          closeDialog();
          logout();
        }}
      />
      <ConfirmDialog
        visible={signOutDialog === "all"}
        title="Sign Out All Devices"
        message="This will sign you out from all devices."
        confirmLabel="Sign Out All"
        cancelLabel="Cancel"
        destructive
        onCancel={closeDialog}
        onConfirm={() => {
          closeDialog();
          logoutAll();
        }}
      />
    <SafeAreaView edges={["top"]} style={[styles.screen, { backgroundColor: bg }]}>
    <ScrollView
      style={{ flex: 1 }}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      {/* ── Profile Header ── */}
      <View style={styles.header}>
        <View style={[styles.avatar, { backgroundColor: brand }]}>
          <Text style={styles.avatarText}>{initials}</Text>
        </View>
        <Text style={[styles.name, { color: tc }]}>
          {user?.first_name} {user?.last_name}
        </Text>
        <Text style={[styles.email, { color: tcMuted }]}>{user?.university_email}</Text>
        <View style={styles.badgeRow}>
          <View style={[styles.roleBadge, { backgroundColor: brand + "15" }]}>
            <Text style={[styles.roleText, { color: brandTxt }]}>
              {formatRole(user?.role)}
            </Text>
          </View>
          {user?.email_verified && (
            <View style={[styles.verifiedBadge, { backgroundColor: functionalColor(resolvedTheme, "success") + "15" }]}>
              <Ionicons name="checkmark-circle" size={12} color={functionalColor(resolvedTheme, "success")} />
              <Text style={[styles.verifiedText, { color: functionalColor(resolvedTheme, "success") }]}>
                Verified
              </Text>
            </View>
          )}
        </View>
      </View>

      {/* ── Account Section ── */}
      <View style={[styles.section, { backgroundColor: bg, borderColor: bc }]}>
        <Text style={[styles.sectionTitle, { color: tcMuted }]}>ACCOUNT</Text>
        <SectionRow icon="person-outline" label="University ID" value={user?.university_id ?? "—"} isLast theme={theme} />
      </View>

      {/* ── Appearance Section — single row opening a picker ── */}
      <View style={[styles.section, { backgroundColor: bg, borderColor: bc }]}>
        <Text style={[styles.sectionTitle, { color: tcMuted }]}>APPEARANCE</Text>
        <SectionRow
          icon="contrast-outline"
          label="Theme"
          value={themePreference === "system" ? "System" : themePreference === "light" ? "Light" : "Dark"}
          onPress={() => setThemeSheetVisible(true)}
          isLast
          theme={theme}
        />
      </View>

      {/* ── Security Section ── */}
      <View style={[styles.section, { backgroundColor: bg, borderColor: bc }]}>
        <Text style={[styles.sectionTitle, { color: tcMuted }]}>SECURITY</Text>
        <SectionRow
          icon="lock-closed-outline"
          label="Change Password"
          onPress={openPasswordSheet}
          theme={theme}
        />
        <SectionRow
          icon="key-outline"
          label="PIN Login"
          value={pinEnabled === null ? undefined : pinEnabled ? "On" : "Off"}
          onPress={openPinSheet}
          theme={theme}
        />
        <SectionRow
          icon="phone-portrait-outline"
          label="Sign Out All Devices"
          onPress={handleLogoutAll}
          isLast
          theme={theme}
        />
      </View>

      {/* ── Logout ── */}
      <Pressable style={[styles.logoutBtn, { borderColor: functionalColor(resolvedTheme, "error") + "30" }]} onPress={handleLogout}>
        <Ionicons name="log-out-outline" size={18} color={functionalColor(resolvedTheme, "error")} />
        <Text style={[styles.logoutText, { color: functionalColor(resolvedTheme, "error") }]}>Sign Out</Text>
      </Pressable>

      {/* ── About ── */}
      <View style={[styles.section, { backgroundColor: bg, borderColor: bc }]}>
        <Text style={[styles.sectionTitle, { color: tcMuted }]}>ABOUT</Text>
          <SectionRow icon="information-circle-outline" label="App version" value="v0.1.4" isLast theme={theme} />
      </View>

      {/* ── Footer ── */}
      <View style={styles.footer}>
        <Text style={[styles.footerText, { color: tcMuted }]}>Lahore Garrison University</Text>
      </View>
      </ScrollView>
      </SafeAreaView>

      {/* Theme picker sheet */}
      <BottomSheet
        visible={themeSheetVisible}
        onClose={() => setThemeSheetVisible(false)}
        title="Choose Theme"
      >
        {(["system", "light", "dark"] as const).map((option) => (
          <Pressable
            key={option}
            onPress={() => {
              setThemePreference(option);
              setThemeSheetVisible(false);
            }}
          >
            <View style={[styles.row, { borderBottomColor: borderColor(theme, "subtle"), borderBottomWidth: StyleSheet.hairlineWidth }]}>
              <Ionicons
                name={option === "system" ? "phone-portrait-outline" : option === "light" ? "sunny-outline" : "moon-outline"}
                size={20}
                color={tcMuted}
              />
              <Text style={[styles.rowLabel, { color: tc }]}>
                {option === "system" ? "System default" : option === "light" ? "Light" : "Dark"}
              </Text>
              <View style={styles.rowRight}>
                {themePreference === option && <Ionicons name="checkmark-circle" size={20} color={brand} />}
              </View>
            </View>
          </Pressable>
        ))}
      </BottomSheet>

      {/* Phase 58 — Change Password sheet */}
      <BottomSheet
        visible={passwordSheet}
        onClose={() => setPasswordSheet(false)}
        title="Change Password"
        maxHeight={640}
      >
        <Text style={[styles.sheetHelper, { color: tcMuted }]}>
          Your new password must be at least 8 characters and include an uppercase letter, a lowercase letter, and a digit.
        </Text>
        <PasswordInput
          label="Current password"
          placeholder="Enter your current password"
          value={pwdCurrent}
          onChangeText={(text: string) => { setPwdCurrent(text); setPwdError(""); }}
          autoComplete="current-password"
        />
        <PasswordInput
          label="New password"
          placeholder="Enter a new password"
          value={pwdNew}
          onChangeText={(text: string) => { setPwdNew(text); setPwdError(""); }}
          autoComplete="new-password"
        />
        <PasswordInput
          label="Confirm new password"
          placeholder="Re-enter the new password"
          value={pwdConfirm}
          onChangeText={(text: string) => { setPwdConfirm(text); setPwdError(""); }}
          autoComplete="new-password"
        />
        {pwdError ? (
          <Text style={[styles.sheetError, { color: functionalColor(resolvedTheme, "error") }]}>{pwdError}</Text>
        ) : null}
        <Button
          title={pwdSubmitting ? "Updating..." : "Update Password"}
          onPress={handleChangePassword}
          loading={pwdSubmitting}
          disabled={pwdSubmitting}
          fullWidth
        />
        <Button title="Cancel" variant="ghost" onPress={() => setPasswordSheet(false)} fullWidth />
      </BottomSheet>

      {/* Phase 58 — PIN Login sheet */}
      <BottomSheet
        visible={pinSheet}
        onClose={() => setPinSheet(false)}
        title="PIN Login"
        maxHeight={520}
      >
        <Text style={[styles.sheetHelper, { color: tcMuted }]}>
          Set a 4-digit PIN to sign in quickly on this device.
        </Text>
        <View style={styles.pinModeRow}>
          {(["enable", "change", "disable"] as const).map((m) => (
            <Pressable
              key={m}
              onPress={() => { setPinMode(m); setPinError(""); setPinSuccess(""); }}
              style={[
                styles.pinModeChip,
                { borderColor: bc },
                pinMode === m && { backgroundColor: brand + "20", borderColor: brand },
              ]}
            >
              <Text
                style={[
                  styles.pinModeChipText,
                  { color: pinMode === m ? brand : tcMuted },
                ]}
              >
                {m === "enable" ? "Enable" : m === "change" ? "Change" : "Disable"}
              </Text>
            </Pressable>
          ))}
        </View>
        {pinMode === "enable" ? (
          <>
            <PasswordInput
              label="Current password"
              placeholder="Enter your current password"
              value={pinCurrentPassword}
              onChangeText={(text: string) => { setPinCurrentPassword(text); setPinError(""); }}
              autoComplete="current-password"
            />
            <PasswordInput
              label="New PIN (4 digits)"
              placeholder="Enter a 4-digit PIN"
              value={pinNew}
              onChangeText={(text: string) => { setPinNew(text); setPinError(""); }}
              keyboardType="number-pad"
              maxLength={4}
            />
            <PasswordInput
              label="Confirm new PIN"
              placeholder="Re-enter the new PIN"
              value={pinConfirm}
              onChangeText={(text: string) => { setPinConfirm(text); setPinError(""); }}
              keyboardType="number-pad"
              maxLength={4}
            />
          </>
        ) : pinMode === "change" ? (
          <>
            <PasswordInput
              label="Current PIN"
              placeholder="Enter your current PIN"
              value={pinCurrent}
              onChangeText={(text: string) => { setPinCurrent(text); setPinError(""); }}
              keyboardType="number-pad"
              maxLength={4}
            />
            <PasswordInput
              label="New PIN (4 digits)"
              placeholder="Enter a new 4-digit PIN"
              value={pinNew}
              onChangeText={(text: string) => { setPinNew(text); setPinError(""); }}
              keyboardType="number-pad"
              maxLength={4}
            />
            <PasswordInput
              label="Confirm new PIN"
              placeholder="Re-enter the new PIN"
              value={pinConfirm}
              onChangeText={(text: string) => { setPinConfirm(text); setPinError(""); }}
              keyboardType="number-pad"
              maxLength={4}
            />
          </>
        ) : (
          <PasswordInput
            label="Current password"
            placeholder="Enter your current password"
            value={pinCurrentPassword}
            onChangeText={(text: string) => { setPinCurrentPassword(text); setPinError(""); }}
            autoComplete="current-password"
          />
        )}
        {pinError ? (
          <Text style={[styles.sheetError, { color: functionalColor(resolvedTheme, "error") }]}>{pinError}</Text>
        ) : null}
        {pinSuccess ? (
          <Text style={[styles.sheetError, { color: functionalColor(resolvedTheme, "success") }]}>{pinSuccess}</Text>
        ) : null}
        <Button
          title={
            pinSubmitting
              ? "Working..."
              : pinMode === "enable"
                ? "Enable PIN"
                : pinMode === "change"
                  ? "Change PIN"
                  : "Disable PIN"
          }
          onPress={handlePinSubmit}
          loading={pinSubmitting}
          disabled={pinSubmitting}
          variant={pinMode === "disable" ? "danger" : "primary"}
          fullWidth
        />
        <Button title="Cancel" variant="ghost" onPress={() => setPinSheet(false)} fullWidth />
      </BottomSheet>

      <Toast
        message={toast?.message ?? ""}
        type={toast?.type ?? "success"}
        visible={toast !== null}
        onDismiss={() => setToast(null)}
      />
    </>
  );
}

// ── Styles ──

const styles = StyleSheet.create({
  screen: { flex: 1 },
  // 160 clears the fixed tab bar (56 + bottom inset) with generous room so
  // the Sign Out button and footer are never hiding behind the nav.
  content: { padding: 16, paddingBottom: 160 },

  // Header
  header: { alignItems: "center", marginBottom: 16, paddingVertical: 8 },
  avatar: {
    width: 72,
    height: 72,
    borderRadius: 36,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 12,
  },
  avatarText: { fontSize: 26, fontWeight: "700", color: "#ffffff" },
  name: { fontSize: 20, fontWeight: "700" },
  email: { fontSize: 14, marginTop: 4 },
  roleBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  roleText: { fontSize: 11, fontWeight: "700", letterSpacing: 0.5 },
  badgeRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    marginTop: 8,
  },
  verifiedBadge: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
    gap: 4,
  },
  verifiedText: { fontSize: 11, fontWeight: "700", letterSpacing: 0.5 },

  // Sections
  section: {
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 16,
    overflow: "hidden",
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.8,
    paddingHorizontal: 14,
    paddingTop: 12,
    paddingBottom: 6,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingHorizontal: 14,
    paddingVertical: 13,
  },
  rowLabel: { fontSize: 15, flex: 1 },
  rowRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  rowValue: { fontSize: 13 },

  // Logout
  logoutBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    padding: 14,
    borderRadius: 10,
    borderWidth: 1,
    marginTop: 8,
    marginBottom: 16,
  },
  logoutText: { fontSize: 15, fontWeight: "600" },

  // Footer
  footer: { alignItems: "center", gap: 4 },
  footerText: { fontSize: 12 },
  footerVersion: { fontSize: 11 },

  // Phase 58 — security sheets
  sheetHelper: { fontSize: 12, lineHeight: 17, marginBottom: 12 },
  sheetError: { fontSize: 13, marginBottom: 10, lineHeight: 18 },
  pinModeRow: { flexDirection: "row", gap: 8, marginBottom: 14 },
  pinModeChip: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderRadius: 18,
    paddingVertical: 8,
  },
  pinModeChipText: { fontSize: 13, fontWeight: "600" },
});
