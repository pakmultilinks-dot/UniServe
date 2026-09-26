/**
 * UniServe — Home Screen (Authenticated)
 *
 * Minimal home screen after login. Shows user greeting
 * and sign-out button. Feature screens in future phases.
 */
import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";

import { useAuth } from "../../src/contexts/AuthContext";

export default function HomeScreen() {
  const { user, logout } = useAuth();

  return (
    <View style={styles.container}>
      <Text style={styles.greeting}>
        Welcome, {user?.first_name ?? "User"}!
      </Text>
      <Text style={styles.role}>Role: {user?.role ?? "unknown"}</Text>

      <View style={styles.placeholder}>
        <Text style={styles.placeholderText}>
          Dashboard features coming in future phases.
        </Text>
      </View>

      <TouchableOpacity style={styles.signOutButton} onPress={() => logout()}>
        <Text style={styles.signOutText}>Sign Out</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 24,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#f9fafb",
  },
  greeting: {
    fontSize: 22,
    fontWeight: "bold",
    color: "#111827",
  },
  role: {
    fontSize: 14,
    color: "#6b7280",
    marginTop: 4,
    marginBottom: 24,
  },
  placeholder: {
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 12,
    padding: 20,
    width: "100%",
    maxWidth: 400,
    alignItems: "center",
    marginBottom: 24,
  },
  placeholderText: {
    color: "#9ca3af",
    fontSize: 14,
  },
  signOutButton: {
    padding: 12,
  },
  signOutText: {
    color: "#dc2626",
    fontSize: 16,
  },
});
