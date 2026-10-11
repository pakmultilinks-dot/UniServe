/**
 * ConfirmDialog — cross-platform confirmation dialog (P3-1).
 *
 * Why not Alert.alert?
 *   On Expo web, Alert.alert never surfaces a dialog and its button
 *   callbacks never fire, so "Sign Out" / "Sign Out All Devices" were
 *   completely inert in the browser (Phase 42 P3-1). This component uses
 *   a plain RN Modal, which renders identically on native devices and the
 *   web build, so both platforms share one confirmation flow.
 *
 * Design:
 *   - Centered card on a translucent scrim
 *   - Optional destructive styling for the confirm button (warm brand
 *     palette — no red-only reliance; the brand-destructive token is used)
 *   - Buttons: Cancel (secondary) left, Confirm (primary/destructive) right
 */
import React from "react";
import { Modal, View, Text, Pressable, StyleSheet } from "react-native";
import { useTheme } from "../../contexts/ThemeContext";
import { textColor, bgColor, borderColor, brandGreen } from "../../theme";

export interface ConfirmDialogProps {
  visible: boolean;
  title: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Destructive confirm (e.g. sign out) — uses the functional error color. */
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  visible,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  destructive = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const { resolvedTheme } = useTheme();
  const tc = (v: "primary" | "secondary" | "muted") => textColor(resolvedTheme, v);
  const bg = bgColor(resolvedTheme, "primary");
  const bgSec = bgColor(resolvedTheme, "secondary");
  const bc = borderColor(resolvedTheme, "default");
  const brand = brandGreen(resolvedTheme);
  // Warm functional error tone — matches the existing error tokens.
  const danger = "#b3412f";

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onCancel}
      statusBarTranslucent
    >
      <Pressable style={styles.scrim} onPress={onCancel}>
        <Pressable
          style={[styles.card, { backgroundColor: bg, borderColor: bc }]}
          onPress={() => {/* absorb taps on the card itself */}}
        >
          <Text style={[styles.title, { color: tc("primary") }]}>{title}</Text>
          {message ? (
            <Text style={[styles.message, { color: tc("secondary") }]}>{message}</Text>
          ) : null}

          <View style={styles.buttonRow}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={cancelLabel}
              onPress={onCancel}
              style={({ pressed }) => [
                styles.button,
                styles.cancelButton,
                { backgroundColor: bgSec, borderColor: bc },
                pressed && styles.pressed,
              ]}
            >
              <Text style={[styles.buttonText, { color: tc("primary") }]}>{cancelLabel}</Text>
            </Pressable>

            <Pressable
              accessibilityRole="button"
              accessibilityLabel={confirmLabel}
              onPress={onConfirm}
              style={({ pressed }) => [
                styles.button,
                styles.confirmButton,
                { backgroundColor: destructive ? danger : brand },
                pressed && styles.pressed,
              ]}
            >
              <Text style={[styles.buttonText, styles.confirmButtonText]}>
                {confirmLabel}
              </Text>
            </Pressable>
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  scrim: {
    flex: 1,
    backgroundColor: "rgba(33, 23, 15, 0.45)",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 32,
  },
  card: {
    width: "100%",
    maxWidth: 360,
    borderRadius: 16,
    borderWidth: 1,
    padding: 20,
  },
  title: {
    fontSize: 17,
    fontWeight: "600",
    marginBottom: 8,
  },
  message: {
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 20,
  },
  buttonRow: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 10,
  },
  button: {
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 10,
    borderWidth: 1,
    minWidth: 96,
    alignItems: "center",
  },
  cancelButton: {
    // secondary surface + border supplied inline
  },
  confirmButton: {
    // solid brand/destructive fill supplied inline
  },
  buttonText: {
    fontSize: 14,
    fontWeight: "600",
  },
  confirmButtonText: {
    color: "#fffdf8",
  },
  pressed: {
    opacity: 0.82,
  },
});
