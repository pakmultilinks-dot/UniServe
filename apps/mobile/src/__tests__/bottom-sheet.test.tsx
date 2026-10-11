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
import { ScrollView, Text } from "react-native";
import { render } from "@testing-library/react-native";

jest.mock("../contexts/ThemeContext", () => ({
  useTheme: () => ({ resolvedTheme: "light" }),
}));

import { BottomSheet } from "../components/ui/BottomSheet";

describe("BottomSheet content clipping", () => {
  it("renders its children when visible", () => {
    const { getByText } = render(
      <BottomSheet visible onClose={jest.fn()} title="Select Cafeteria">
        <Text>Main Cafeteria</Text>
      </BottomSheet>,
    );

    expect(getByText("Main Cafeteria")).toBeTruthy();
  });

  it("keeps capped content scrollable rather than clipped", () => {
    const { UNSAFE_queryAllByType } = render(
      <BottomSheet visible onClose={jest.fn()} title="Change Password">
        <Text>Overflowing content</Text>
      </BottomSheet>,
    );

    expect(UNSAFE_queryAllByType(ScrollView).length).toBeGreaterThan(0);
  });

  it("renders nothing while closed", () => {
    const { queryByText } = render(
      <BottomSheet visible={false} onClose={jest.fn()} title="PIN Login">
        <Text>Hidden content</Text>
      </BottomSheet>,
    );

    expect(queryByText("Hidden content")).toBeNull();
  });
});
