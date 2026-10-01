/**
 * UniServe — Profile Screen
 *
 * User profile info organized into sections: Account, Security, Support.
 * Uses Ionicons for all icons, no emojis.
 */
import React from "react";
import { View, Text, ScrollView, StyleSheet, Pressable, Alert } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { useAuth } from "../../../src/contexts/AuthContext";
import { useTheme } from "../../../src/contexts/ThemeContext";
import { textColor, bgColor, borderColor, brandGreen, functionalColor } from "../../../src/theme";

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
        <Ionicons name="chevron-forward" size={16} color={tcMuted} style={{ opacity: 0.5 }} />
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
  const { resolvedTheme } = useTheme();
  const theme = resolvedTheme as "light" | "dark";

  const brand = brandGreen(resolvedTheme);
  const tc = textColor(resolvedTheme, "primary");
  const tcMuted = textColor(resolvedTheme, "muted");
  const bg = bgColor(resolvedTheme, "primary");
  const bgSec = bgColor(resolvedTheme, "secondary");
  const bc = borderColor(resolvedTheme, "default");

  const initials = [user?.first_name?.[0], user?.last_name?.[0]]
    .filter(Boolean)
    .join("")
    .toUpperCase() || "?";

  const handleLogout = () => {
    Alert.alert("Sign Out", "Are you sure you want to sign out?", [
      { text: "Cancel", style: "cancel" },
      { text: "Sign Out", style: "destructive", onPress: logout },
    ]);
  };

  const handleLogoutAll = () => {
    Alert.alert("Sign Out All Devices", "This will sign you out from all devices.", [
      { text: "Cancel", style: "cancel" },
      { text: "Sign Out All", style: "destructive", onPress: logoutAll },
    ]);
  };

  return (
    <ScrollView
      style={[styles.screen, { backgroundColor: bgSec }]}
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
        <View style={[styles.roleBadge, { backgroundColor: brand + "15" }]}>
          <Text style={[styles.roleText, { color: brand }]}>
            {formatRole(user?.role)}
          </Text>
        </View>
      </View>

      {/* ── Account Section ── */}
      <View style={[styles.section, { backgroundColor: bg, borderColor: bc }]}>
        <Text style={[styles.sectionTitle, { color: tcMuted }]}>ACCOUNT</Text>
        <SectionRow icon="person-outline" label="University ID" value={user?.university_id ?? "—"} theme={theme} />
        <SectionRow
          icon={user?.email_verified ? "checkmark-circle-outline" : "alert-circle-outline"}
          label="Email Verified"
          value={user?.email_verified ? "Verified" : "Not verified"}
          color={user?.email_verified ? functionalColor(resolvedTheme, "success") : functionalColor(resolvedTheme, "error")}
          theme={theme}
        />
        <SectionRow icon="school-outline" label="Category" value={user?.category ?? "—"} isLast theme={theme} />
      </View>

      {/* ── Security Section ── */}
      <View style={[styles.section, { backgroundColor: bg, borderColor: bc }]}>
        <Text style={[styles.sectionTitle, { color: tcMuted }]}>SECURITY</Text>
        {/* "Change Password" was removed — it was a no-op stub with no UI.
            The change-password API and client service exist; wiring the
            screen is deferred to a future feature phase. */}
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

      {/* ── Footer ── */}
      <View style={styles.footer}>
        <Text style={[styles.footerText, { color: tcMuted }]}>Lahore Garrison University</Text>
        <Text style={[styles.footerVersion, { color: tcMuted }]}>UniServe v0.1.0</Text>
      </View>
    </ScrollView>
  );
}

// ── Styles ──

const styles = StyleSheet.create({
  screen: { flex: 1 },
  content: { padding: 16, paddingBottom: 40 },

  // Header
  header: { alignItems: "center", marginBottom: 24, paddingVertical: 16 },
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
    marginTop: 8,
  },
  roleText: { fontSize: 11, fontWeight: "700", letterSpacing: 0.5 },

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
});
