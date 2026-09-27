/**
 * UniServe — Profile Screen
 *
 * User profile info, settings, and logout.
 */
import React from "react";
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, Alert } from "react-native";

import { useAuth } from "../../../src/contexts/AuthContext";
import { useTheme } from "../../../src/contexts/ThemeContext";
import { LguSeal } from "../../../src/components/LguSeal";
import { Card } from "../../../src/components/ui";
import { textColor, bgColor, borderColor, brandGreen } from "../../../src/theme";
import { Ionicons } from "@expo/vector-icons";

export default function ProfileScreen() {
  const { user, logout, logoutAll } = useAuth();
  const { resolvedTheme } = useTheme();

  const tc = (variant: "primary" | "secondary" | "muted") => textColor(resolvedTheme, variant);
  const bg = (variant: "primary" | "secondary" | "tertiary") => bgColor(resolvedTheme, variant);
  const bc = (variant: "default" | "subtle") => borderColor(resolvedTheme, variant);

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

  // Get initials
  const initials = [user?.first_name?.[0], user?.last_name?.[0]]
    .filter(Boolean)
    .join("")
    .toUpperCase() || "?";

  return (
    <ScrollView
      style={[styles.screen, { backgroundColor: bg("secondary") }]}
      contentContainerStyle={styles.content}
    >
      {/* Profile Header */}
      <View style={styles.header}>
        <View style={[styles.avatar, { backgroundColor: brandGreen(resolvedTheme) }]}>
          <Text style={styles.avatarText}>{initials}</Text>
        </View>
        <Text style={[styles.name, { color: tc("primary") }]}>
          {user?.first_name} {user?.last_name}
        </Text>
        <Text style={[styles.email, { color: tc("muted") }]}>{user?.university_email}</Text>
        <View style={[styles.roleBadge, { backgroundColor: brandGreen(resolvedTheme) + "20" }]}>
          <Text style={[styles.roleText, { color: brandGreen(resolvedTheme) }]}>
            {user?.role?.replace("_", " ").toUpperCase() ?? "USER"}
          </Text>
        </View>
      </View>

      {/* Info Card */}
      <Card style={{ backgroundColor: bg("primary"), borderColor: bc("default") }}>
        <InfoRow label="University ID" value={user?.university_id ?? "—"} tc={tc} bc={bc} />
        <InfoRow label="Email Verified" value={user?.email_verified ? "Yes ✓" : "No"} tc={tc} bc={bc} isLast />
      </Card>

      {/* Actions */}
      <Card style={{ backgroundColor: bg("primary"), borderColor: bc("default") }}>
        <TouchableOpacity style={[styles.actionBtn, { borderBottomColor: bc("subtle") }]} onPress={handleLogoutAll}>
          <Text style={{ color: tc("primary"), fontSize: 15 }}>Sign Out All Devices</Text>
        </TouchableOpacity>
      </Card>

      {/* Logout */}
      <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
        <Text style={styles.logoutText}>Sign Out</Text>
      </TouchableOpacity>

      {/* Footer */}
      <View style={styles.footer}>
        <LguSeal size="sm" />
        <Text style={[styles.footerText, { color: tc("muted") }]}>
          UniServe v0.1.0
        </Text>
      </View>
    </ScrollView>
  );
}

function InfoRow({
  label,
  value,
  tc,
  bc,
  isLast = false,
}: {
  label: string;
  value: string;
  tc: (v: "primary" | "secondary" | "muted") => string;
  bc: (v: "default" | "subtle") => string;
  isLast?: boolean;
}) {
  return (
    <View style={[styles.infoRow, !isLast && { borderBottomColor: bc("subtle"), borderBottomWidth: StyleSheet.hairlineWidth }]}>
      <Text style={{ color: tc("muted"), fontSize: 13, flex: 1 }}>{label}</Text>
      <Text style={{ color: tc("primary"), fontSize: 14, fontWeight: "500" }}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
  },
  content: {
    padding: 16,
    paddingBottom: 32,
  },
  header: {
    alignItems: "center",
    marginBottom: 24,
    paddingVertical: 20,
  },
  avatar: {
    width: 72,
    height: 72,
    borderRadius: 36,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 12,
  },
  avatarText: {
    fontSize: 28,
    fontWeight: "700",
    color: "#ffffff",
  },
  name: {
    fontSize: 22,
    fontWeight: "700",
  },
  email: {
    fontSize: 14,
    marginTop: 4,
  },
  roleBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
    marginTop: 8,
  },
  roleText: {
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.5,
  },
  infoRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 12,
  },
  actionBtn: {
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  logoutBtn: {
    marginTop: 24,
    padding: 14,
    borderRadius: 8,
    backgroundColor: "#fef2f2",
    borderWidth: 1,
    borderColor: "#fecaca",
    alignItems: "center",
  },
  logoutText: {
    color: "#991b1b",
    fontSize: 14,
    fontWeight: "600",
  },
  footer: {
    alignItems: "center",
    marginTop: 32,
    gap: 8,
  },
  footerText: {
    fontSize: 12,
  },
});
