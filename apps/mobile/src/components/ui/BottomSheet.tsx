/**
 * BottomSheet — Modal bottom sheet with backdrop.
 *
 * Design spec:
 * - Dim background subtly
 * - Rounded top corners 20-24
 * - Drag indicator
 * - Close by backdrop
 * - Smooth spring animation
 */
import React, { useEffect } from "react";
import {
  View,
  Text,
  StyleSheet,
  Modal,
  ScrollView,
  TouchableWithoutFeedback,
  Dimensions,
  Animated,
  PanResponder,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTheme } from "../../contexts/ThemeContext";
import { bgColor, textColor, borderColor, brandGreen } from "../../theme";

const { height: SCREEN_HEIGHT } = Dimensions.get("window");

interface BottomSheetProps {
  visible: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  maxHeight?: number;
}

export function BottomSheet({
  visible,
  onClose,
  title,
  children,
  maxHeight = SCREEN_HEIGHT * 0.5,
}: BottomSheetProps) {
  const { resolvedTheme } = useTheme();
  const bg = bgColor(resolvedTheme, "primary");
  const tc = textColor(resolvedTheme, "primary");
  const tcMuted = textColor(resolvedTheme, "muted");
  const brand = brandGreen(resolvedTheme);
  const bc = borderColor(resolvedTheme, "default");

  const translateY = React.useRef(new Animated.Value(SCREEN_HEIGHT)).current;
  const backdropOpacity = React.useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (visible) {
      Animated.parallel([
        Animated.spring(translateY, {
          toValue: 0,
          useNativeDriver: true,
          damping: 20,
          stiffness: 200,
        }),
        Animated.timing(backdropOpacity, {
          toValue: 1,
          duration: 200,
          useNativeDriver: true,
        }),
      ]).start();
    } else {
      Animated.parallel([
        Animated.timing(translateY, {
          toValue: SCREEN_HEIGHT,
          duration: 200,
          useNativeDriver: true,
        }),
        Animated.timing(backdropOpacity, {
          toValue: 0,
          duration: 200,
          useNativeDriver: true,
        }),
      ]).start();
    }
  }, [visible]);

  const panResponder = React.useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => false,
      onMoveShouldSetPanResponder: (_, gestureState) =>
        gestureState.dy > 5,
      onPanResponderRelease: (_, gestureState) => {
        if (gestureState.dy > 50) {
          onClose();
        }
      },
    }),
  ).current;

  if (!visible) return null;

  return (
    <Modal transparent visible={visible} onRequestClose={onClose} animationType="none">
      <View style={styles.overlay}>
        <TouchableWithoutFeedback onPress={onClose}>
          <Animated.View
            style={[styles.backdrop, { opacity: backdropOpacity }]}
          />
        </TouchableWithoutFeedback>
        <Animated.View
          style={[
            styles.sheet,
            {
              backgroundColor: bg,
              borderTopColor: bc,
              maxHeight,
              transform: [{ translateY }],
            },
          ]}
          {...panResponder.panHandlers}
        >
          {/* Drag indicator */}
          <View style={styles.dragIndicator}>
            <View style={[styles.dragBar, { backgroundColor: bc }]} />
          </View>

          {/* Header */}
          {title && (
            <View style={styles.header}>
              <Text style={[styles.title, { color: tc }]}>{title}</Text>
              <TouchableWithoutFeedback onPress={onClose}>
                <Ionicons name="close" size={22} color={tcMuted} />
              </TouchableWithoutFeedback>
            </View>
          )}

          {/* Content — scrollable so rows past maxHeight stay reachable
              instead of being clipped by the sheet's fixed cap. The cap and
              the horizontal padding both live on `styles.content`: a
              ScrollView applies its own padding once, so repeating
              paddingHorizontal on contentContainerStyle would inset the
              sheet body twice. */}
          <ScrollView
            style={styles.content}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            {children}
          </ScrollView>
        </Animated.View>
      </View>
    </Modal>
  );
}

/** Reusable bottom sheet row */
export function BottomSheetRow({
  label,
  subtitle,
  selected,
  onPress,
  icon,
}: {
  label: string;
  subtitle?: string;
  selected?: boolean;
  onPress: () => void;
  icon?: string;
}) {
  const { resolvedTheme } = useTheme();
  const tc = textColor(resolvedTheme, "primary");
  const tcMuted = textColor(resolvedTheme, "muted");
  const brand = brandGreen(resolvedTheme);

  return (
    <TouchableWithoutFeedback onPress={onPress}>
      <View style={styles.row}>
        {icon && (
          <Ionicons
            name={icon as any}
            size={20}
            color={selected ? brand : tcMuted}
            style={styles.rowIcon}
          />
        )}
        <View style={styles.rowText}>
          <Text style={[styles.rowLabel, { color: tc }]}>{label}</Text>
          {subtitle && (
            <Text style={[styles.rowSubtitle, { color: tcMuted }]}>{subtitle}</Text>
          )}
        </View>
        {selected && (
          <Ionicons name="checkmark-circle" size={22} color={brand} />
        )}
      </View>
    </TouchableWithoutFeedback>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    justifyContent: "flex-end",
  },
  backdrop: {
    // RN 0.86 removed StyleSheet.absoluteFillObject — inline its exact
    // historical definition to preserve identical layout semantics.
    position: "absolute",
    left: 0,
    right: 0,
    top: 0,
    bottom: 0,
    backgroundColor: "rgba(0,0,0,0.4)",
  },
  sheet: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    borderTopWidth: StyleSheet.hairlineWidth,
    paddingTop: 8,
    paddingBottom: 32,
  },
  dragIndicator: {
    alignItems: "center",
    paddingVertical: 8,
  },
  dragBar: {
    width: 36,
    height: 4,
    borderRadius: 2,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 20,
    paddingVertical: 12,
  },
  title: {
    fontSize: 17,
    fontWeight: "600",
  },
  content: {
    paddingHorizontal: 20,
    maxHeight: SCREEN_HEIGHT * 0.4,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 14,
    paddingHorizontal: 4,
  },
  rowIcon: {
    marginRight: 12,
  },
  rowText: {
    flex: 1,
  },
  rowLabel: {
    fontSize: 15,
    fontWeight: "500",
  },
  rowSubtitle: {
    fontSize: 13,
    marginTop: 2,
  },
});
