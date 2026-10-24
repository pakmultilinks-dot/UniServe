import React from "react";
import { render, screen, fireEvent } from "@testing-library/react-native";
import FoodCard from "../components/FoodCard";
jest.mock("@expo/vector-icons", () => ({ Ionicons: "Ionicons" }));
jest.mock("../components/FoodImage", () => "FoodImage");
jest.mock("../contexts/ThemeContext", () => ({ useTheme: () => ({ resolvedTheme: "light" }) }));
it("adds the named product using its accessible native action", () => {
  const add = jest.fn(); render(<FoodCard name="Chicken Biryani" price={22000} onAdd={add} />);
  fireEvent.press(screen.getByRole("button", { name: "Add Chicken Biryani to cart" }));
  expect(add).toHaveBeenCalledTimes(1);
});
it("exposes distinct increment and decrement actions for the selected product", () => {
  const increase = jest.fn(), decrease = jest.fn();
  render(<FoodCard name="Chicken Biryani" price={22000} quantity={1} onIncrement={increase} onDecrement={decrease} />);
  fireEvent.press(screen.getByRole("button", { name: "Increase Chicken Biryani quantity" }));
  fireEvent.press(screen.getByRole("button", { name: "Decrease Chicken Biryani quantity" }));
  expect(increase).toHaveBeenCalledTimes(1); expect(decrease).toHaveBeenCalledTimes(1);
});
it("does not submit an unavailable product", () => {
  const add = jest.fn(); render(<FoodCard name="Chicken Biryani" price={22000} isAvailable={false} onAdd={add} />);
  fireEvent.press(screen.getByRole("button", { name: "Add Chicken Biryani to cart" }));
  expect(add).not.toHaveBeenCalled();
});
