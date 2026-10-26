/**
 * Phase 3 — BottomSheet content clipping regression.
 *
 * The sheet caps its content at a fixed fraction of the window
 * (`maxHeight: SCREEN_HEIGHT * 0.4`). With a plain View wrapper that cap
 * silently clipped anything taller: on Android the default overflow is
 * `hidden`, so the Profile "Change Password"/"PIN Login" submit buttons
 * could be cut off with no way to reach them. The content is now a
 * ScrollView, so capped content stays reachable instead of disappearing.
 */

import React from "react";
import { ScrollView, Text, KeyboardAvoidingView, StyleSheet } from "react-native";
import { render } from "@testing-library/react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

jest.mock("../contexts/ThemeContext", () => ({
  useTheme: () => ({ resolvedTheme: "light" }),
}));

import { BottomSheet } from "../components/ui/BottomSheet";

// BottomSheet reads useSafeAreaInsets() for its bottom padding, so the
// render must be wrapped in a SafeAreaProvider. In jest the native
// onInsetsChange event never fires, so initialMetrics is required —
// without it the provider renders no children at all.
const renderSheet = (ui: React.ReactElement) =>
  render(ui, {
    wrapper: ({ children }) => (
      <SafeAreaProvider
        initialMetrics={{
          insets: { top: 47, left: 0, right: 0, bottom: 34 },
          frame: { x: 0, y: 0, width: 390, height: 844 },
        }}
      >
        {children}
      </SafeAreaProvider>
    ),
  });

describe("BottomSheet content clipping", () => {
  it("renders its children when visible", () => {
    const { getByText } = renderSheet(
      <BottomSheet visible onClose={jest.fn()} title="Select Cafeteria">
        <Text>Main Cafeteria</Text>
      </BottomSheet>,
    );

    expect(getByText("Main Cafeteria")).toBeTruthy();
  });

  it("keeps capped content scrollable rather than clipped", () => {
    const { UNSAFE_queryAllByType } = renderSheet(
      <BottomSheet visible onClose={jest.fn()} title="Change Password">
        <Text>Overflowing content</Text>
      </BottomSheet>,
    );

    expect(UNSAFE_queryAllByType(ScrollView).length).toBeGreaterThan(0);
  });

  it("lets the body shrink inside the sheet and adjusts for the keyboard", () => {
    const { UNSAFE_getByType } = renderSheet(
      <BottomSheet visible onClose={jest.fn()} title="PIN Login" maxHeight={520}>
        <Text>Enable PIN</Text>
      </BottomSheet>,
    );
    const body = UNSAFE_getByType(ScrollView);
    expect(StyleSheet.flatten(body.props.style).flexShrink).toBe(1);
    expect(StyleSheet.flatten(body.props.style).maxHeight).toBeUndefined();
    expect(UNSAFE_getByType(KeyboardAvoidingView).props.behavior).toBeTruthy();
    expect(body.props.automaticallyAdjustKeyboardInsets).toBe(true);
  });

  it("renders nothing while closed", () => {
    const { queryByText } = renderSheet(
      <BottomSheet visible={false} onClose={jest.fn()} title="PIN Login">
        <Text>Hidden content</Text>
      </BottomSheet>,
    );

    expect(queryByText("Hidden content")).toBeNull();
  });
});
