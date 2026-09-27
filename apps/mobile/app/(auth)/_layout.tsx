/**
 * UniServe — Auth Route Group Layout
 *
 * Stack navigator for authentication screens.
 * Headers shown for verify-email, forgot-password, reset-password.
 */
import React from "react";
import { Stack } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { TouchableOpacity } from "react-native";
import { useTheme } from "../../src/contexts/ThemeContext";
import { textColor, bgColor, brandGreen } from "../../src/theme";

function BackButton({ onPress }: { onPress: () => void }) {
  const { resolvedTheme } = useTheme();
  return (
    <TouchableOpacity
      onPress={onPress}
      hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
      style={{ paddingLeft: 4, minWidth: 44, minHeight: 44, justifyContent: "center" }}
    >
      <Ionicons name="chevron-back" size={24} color={textColor(resolvedTheme, "primary")} />
    </TouchableOpacity>
  );
}

export default function AuthLayout() {
  const { resolvedTheme } = useTheme();
  const bg = bgColor(resolvedTheme, "primary");
  const tc = textColor(resolvedTheme, "primary");
  const brand = brandGreen(resolvedTheme);

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        animation: "slide_from_right",
      }}
    >
      <Stack.Screen name="login" />
      <Stack.Screen name="register" />
      <Stack.Screen
        name="verify-email"
        options={{
          headerShown: true,
          title: "Verify Email",
          headerStyle: { backgroundColor: bg },
          headerTintColor: brand,
          headerTitleStyle: { fontWeight: "600", fontSize: 16, color: tc },
          headerShadowVisible: false,
          headerLeft: ({ onPress }) => <BackButton onPress={onPress!} />,
        }}
      />
      <Stack.Screen
        name="forgot-password"
        options={{
          headerShown: true,
          title: "Forgot Password",
          headerStyle: { backgroundColor: bg },
          headerTintColor: brand,
          headerTitleStyle: { fontWeight: "600", fontSize: 16, color: tc },
          headerShadowVisible: false,
          headerLeft: ({ onPress }) => <BackButton onPress={onPress!} />,
        }}
      />
      <Stack.Screen
        name="reset-password"
        options={{
          headerShown: true,
          title: "Reset Password",
          headerStyle: { backgroundColor: bg },
          headerTintColor: brand,
          headerTitleStyle: { fontWeight: "600", fontSize: 16, color: tc },
          headerShadowVisible: false,
          headerLeft: ({ onPress }) => <BackButton onPress={onPress!} />,
        }}
      />
    </Stack>
  );
}

