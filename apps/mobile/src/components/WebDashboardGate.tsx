/**
 * UniServe — Web Dashboard Gate (Phase 53)
 *
 * Shown to university admins, cafeteria managers, and cafeteria staff who
 * sign in on the mobile app. Their operational dashboard lives on the web
 * console; the mobile app is intentionally a student/faculty ordering app.
 *
 * Security model preserved:
 * - The session is NOT silently destroyed — the user chooses when to sign
 *   out (the existing Sign Out action, with the existing ConfirmDialog).
 * - No admin data, dashboards, reports, refunds, or management surfaces are
 *   mounted here. Backend RBAC remains the enforcement boundary regardless.
 */
import React, { useState } from "react";
import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { bgColor, brandGreen, functionalColor, textColor } from "../theme";
import { Button, ConfirmDialog } from "./ui";

const ROLE_LABELS: Record<string, string> = {
  university_admin: "University Admin",
  cafeteria_manager: "Cafeteria Manager",
  cafeteria_staff: "Cafeteria Staff",
};

export default function WebDashboardGate() {
  const { resolvedTheme } = useTheme();
  const { user, logout } = useAuth();
  const [confirmVisible, setConfirmVisible] = useState(false);

  const bg = bgColor(resolvedTheme, "primary");
  const tc = textColor(resolvedTheme, "primary");
  const tcMuted = textColor(resolvedTheme, "muted");
  const brand = brandGreen(resolvedTheme);

  const roleLabel = user ? ROLE_LABELS[user.role] ?? user.role : "";

  return (
    <View style={[styles.screen, { backgroundColor: bg }]}>
      <View style={[styles.iconContainer, { backgroundColor: brand + "15" }]}>
        <Ionicons name="desktop-outline" size={56} color={brand} />
      </View>

      <Text style={[styles.title, { color: tc }]}>Use the Web Dashboard</Text>
      <Text style={[styles.body, { color: tcMuted }]}>
        This account is managed through the UniServe web dashboard. Sign in on a
        computer to manage orders, menus, refunds, and reports.
      </Text>

      {user && (
        <Text style={[styles.signedInAs, { color: tcMuted }]}>
          Signed in as {user.first_name} {user.last_name} ({roleLabel})
        </Text>
      )}

      <View style={styles.buttonContainer}>
        <Button
          title="Sign Out"
          onPress={() => setConfirmVisible(true)}
          variant="secondary"
        />
      </View>

      <ConfirmDialog
        visible={confirmVisible}
        title="Sign Out"
        message="Are you sure you want to sign out?"
        confirmLabel="Sign Out"
        onCancel={() => setConfirmVisible(false)}
        onConfirm={() => {
          setConfirmVisible(false);
          logout();
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 32,
  },
  iconContainer: {
    width: 96,
    height: 96,
    borderRadius: 48,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 20,
  },
  title: {
    fontSize: 22,
    fontWeight: "700",
    textAlign: "center",
    marginBottom: 12,
  },
  body: {
    fontSize: 14,
    lineHeight: 21,
    textAlign: "center",
  },
  signedInAs: {
    fontSize: 12,
    marginTop: 16,
    textAlign: "center",
  },
  buttonContainer: {
    marginTop: 28,
    minWidth: 200,
  },
});
