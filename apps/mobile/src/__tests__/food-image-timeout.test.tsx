import React from "react";
import { act, fireEvent, render, screen } from "@testing-library/react-native";
import FoodImage from "../components/FoodImage";

jest.mock("@expo/vector-icons", () => ({ Ionicons: "Ionicons" }));

describe("FoodImage — screenshot regression", () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  it("keeps a successfully loaded photo after the timeout period", () => {
    render(<FoodImage uri="https://images.example.invalid/loaded.jpg" />);
    fireEvent(screen.getByTestId("food-image"), "loadEnd");
    act(() => { jest.advanceTimersByTime(12001); });
    expect(screen.getByTestId("food-image")).toBeTruthy();
    expect(screen.queryByTestId("food-image-fallback")).toBeNull();
    expect(screen.queryByTestId("food-image-loading")).toBeNull();
  });

  it("falls back instead of spinning forever when a food image never loads", () => {
    render(<FoodImage uri="https://images.example.invalid/something.jpg" category="main_course" />);
    expect(screen.getByTestId("food-image-loading")).toBeTruthy();

    act(() => {
      jest.advanceTimersByTime(12001);
    });

    expect(screen.getByTestId("food-image-fallback")).toBeTruthy();
    expect(screen.queryByTestId("food-image-loading")).toBeNull();
  });

  it("retries loading when a reused card changes to a different food photo", () => {
    const view = render(<FoodImage uri="https://images.example.invalid/old.jpg" category="main_course" />);
    act(() => {
      jest.advanceTimersByTime(12001);
    });
    expect(screen.getByTestId("food-image-fallback")).toBeTruthy();

    view.rerender(<FoodImage uri="https://images.example.invalid/new.jpg" category="main_course" />);
    expect(screen.getByTestId("food-image-loading")).toBeTruthy();
    expect(screen.queryByTestId("food-image-fallback")).toBeNull();
  });
});
