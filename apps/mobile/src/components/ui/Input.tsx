/**
 * UniServe — Input Component (React Native)
 */

import React, { useState } from "react";
import {
  View,
  TextInput,
  Text,
  TouchableOpacity,
  StyleSheet,
  TextInputProps,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors } from "../../theme/colors";

interface LguInputProps extends TextInputProps {
  label?: string;
  error?: string;
  hint?: string;
  rightIcon?: React.ReactNode;
}

export function LguInput({
  label,
  error,
  hint,
  rightIcon,
  style,
  ...props
}: LguInputProps) {
  return (
    <View style={styles.wrapper}>
      {label && <Text style={styles.label}>{label}</Text>}
      <View style={[styles.inputContainer, error ? styles.inputError : null]}>
        <TextInput
          style={[styles.input, style]}
          placeholderTextColor={colors.neutral[400]}
          {...props}
        />
        {rightIcon && <View style={styles.iconContainer}>{rightIcon}</View>}
      </View>
      {error && <Text style={styles.errorText}>{error}</Text>}
      {hint && !error && <Text style={styles.hintText}>{hint}</Text>}
    </View>
  );
}

interface PasswordInputProps extends Omit<LguInputProps, "secureTextEntry"> {
  showToggle?: boolean;
}

export function PasswordInput({ showToggle = true, ...props }: PasswordInputProps) {
  const [visible, setVisible] = useState(false);

  return (
    <LguInput
      {...props}
      /* Android keeps rendering the old mask when secureTextEntry flips on a
         mounted TextInput — the field only re-masks after blur. Remounting
         the input on toggle forces the new secure state to apply instantly.
         (`key` on a sibling wrapper would not help; it must wrap the
         TextInput itself.) */
      key={visible ? "pwd-visible" : "pwd-masked"}
      secureTextEntry={!visible}
      rightIcon={
        showToggle ? (
          <TouchableOpacity onPress={() => setVisible(!visible)} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
            <Ionicons name={visible ? "eye-off-outline" : "eye-outline"} size={20} color={colors.neutral[500]} />
          </TouchableOpacity>
        ) : undefined
      }
    />
  );
}

const styles = StyleSheet.create({
  wrapper: {
    marginBottom: 16,
  },
  label: {
    fontSize: 14,
    fontWeight: "500",
    color: colors.neutral[700],
    marginBottom: 6,
  },
  inputContainer: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.neutral[0],
    borderWidth: 1,
    borderColor: colors.neutral[300],
    borderRadius: 24,
    minHeight: 44,
  },
  inputError: {
    borderColor: colors.error,
  },
  input: {
    flex: 1,
    paddingVertical: 10,
    paddingHorizontal: 14,
    fontSize: 16,
    color: colors.neutral[900],
  },
  iconContainer: {
    paddingRight: 14,
  },

  errorText: {
    fontSize: 12,
    color: colors.error,
    marginTop: 4,
  },
  hintText: {
    fontSize: 12,
    color: colors.neutral[500],
    marginTop: 4,
  },
});
