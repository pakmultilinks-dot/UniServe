/**
 * UniServe — Register Screen Placeholder
 *
 * Basic registration form. Full implementation in future phases.
 */
import React, { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert } from "react-native";
import { useRouter } from "expo-router";

import { useAuth } from "../../src/contexts/AuthContext";

export default function RegisterScreen() {
  const router = useRouter();
  const { register } = useAuth();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleRegister = async () => {
    if (!firstName || !lastName || !email || !password) {
      Alert.alert("Error", "Please fill in all fields");
      return;
    }
    if (password.length < 8) {
      Alert.alert("Error", "Password must be at least 8 characters");
      return;
    }
    setIsLoading(true);
    try {
      await register({
        firstName,
        lastName,
        universityId: email.split("@")[0],
        email,
        password,
      });
      Alert.alert(
        "Registration Successful",
        "Please check your email for a verification code.",
      );
      router.replace("/login");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Registration failed";
      Alert.alert("Registration Failed", message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Create Account</Text>

      <View style={styles.form}>
        <View style={styles.row}>
          <TextInput
            style={[styles.input, styles.halfInput]}
            placeholder="First Name"
            value={firstName}
            onChangeText={setFirstName}
          />
          <TextInput
            style={[styles.input, styles.halfInput]}
            placeholder="Last Name"
            value={lastName}
            onChangeText={setLastName}
          />
        </View>
        <TextInput
          style={styles.input}
          placeholder="University Email"
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          autoCapitalize="none"
          autoCorrect={false}
        />
        <TextInput
          style={styles.input}
          placeholder="Password (min 8 chars)"
          value={password}
          onChangeText={setPassword}
          secureTextEntry
        />
        <TouchableOpacity
          style={[styles.button, isLoading && styles.buttonDisabled]}
          onPress={handleRegister}
          disabled={isLoading}
        >
          <Text style={styles.buttonText}>
            {isLoading ? "Creating Account…" : "Register"}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity onPress={() => router.replace("/login")}>
          <Text style={styles.link}>
            Already have an account? Sign in
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
    backgroundColor: "#f9fafb",
  },
  title: {
    fontSize: 24,
    fontWeight: "bold",
    color: "#111827",
    marginBottom: 24,
  },
  form: {
    width: "100%",
    maxWidth: 360,
  },
  row: {
    flexDirection: "row",
    gap: 8,
  },
  input: {
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    marginBottom: 12,
  },
  halfInput: {
    flex: 1,
  },
  button: {
    backgroundColor: "#2563eb",
    borderRadius: 8,
    padding: 14,
    alignItems: "center",
    marginTop: 4,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
  },
  link: {
    color: "#2563eb",
    textAlign: "center",
    marginTop: 16,
    fontSize: 14,
  },
});
