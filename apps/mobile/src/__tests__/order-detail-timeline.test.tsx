import React from "react";
import { render, screen } from "@testing-library/react-native";
import type { Order } from "@uniserve/shared-types";
import OrderDetailScreen from "../../app/(app)/order/[id]";

let mockOrder: Order;
jest.mock("expo-router", () => ({
  useLocalSearchParams: () => ({ id: "qa-order" }),
  useRouter: () => ({ push: jest.fn(), back: jest.fn() }),
  useFocusEffect: jest.fn(),
}));
jest.mock("@expo/vector-icons", () => ({ Ionicons: "Ionicons" }));
jest.mock("../contexts/ThemeContext", () => ({ useTheme: () => ({ resolvedTheme: "light" }) }));
jest.mock("../contexts/CartContext", () => ({ useCart: () => ({ selectedCafeteria: null }) }));
jest.mock("../services/api", () => ({ ApiClientError: class extends Error {} }));
jest.mock("../services/data", () => ({
  getOrder: jest.fn(async () => mockOrder),
  getRefundableAmount: jest.fn(async () => ({ paid_amount: 0, refundable_amount: 0 })),
  getOrderRefunds: jest.fn(async () => []),
}));

beforeEach(() => {
  mockOrder = {
    id: "qa-order", order_number: 27, collection_token: "qa-token",
    user_id: "qa-student", cafeteria_id: "qa-cafe",
    status: "cancelled", payment_method: "cash",
    order_type: "scheduled", total_amount: 35000, currency: "PKR",
    order_date: "2026-10-23", inventory_reserved: false, items: [],
    updated_at: "2026-10-23T07:42:00Z",
    created_at: "2026-10-23T07:42:00Z", rejection_reason: "other",
    rejection_note: "QA rejection before preparation",
  };
});

it("shows Cancelled as terminal status with Pending only as history", async () => {
  mockOrder.confirmed_at = "2026-10-23T07:42:01Z";
  render(<OrderDetailScreen />);
  await screen.findByText("This order was cancelled");
  expect(screen.getByText("Cancelled")).toBeTruthy();
  expect(screen.getByText("Pending")).toBeTruthy();
  expect(screen.queryByText("Preparing")).toBeNull();
  expect(screen.queryByText("Ready for Pickup")).toBeNull();
  expect(screen.queryByText("Completed")).toBeNull();
  expect(screen.getByText("QA rejection before preparation")).toBeTruthy();
});

it("preserves actual preparation history on cancellation", async () => {
  mockOrder.confirmed_at = "2026-10-23T07:42:01Z";
  mockOrder.preparation_started_at = "2026-10-23T07:43:00Z";
  render(<OrderDetailScreen />);
  await screen.findByText("This order was cancelled");
  expect(screen.getByText("Cancelled")).toBeTruthy();
  expect(screen.getByText("Preparing")).toBeTruthy();
  expect(screen.queryByText("Ready for Pickup")).toBeNull();
  expect(screen.queryByText("Completed")).toBeNull();
});

it("preserves a reached Ready stage without inventing completion", async () => {
  mockOrder.ready_at = "2026-10-23T07:44:00Z";
  render(<OrderDetailScreen />);
  await screen.findByText("This order was cancelled");
  expect(screen.getByText("Cancelled")).toBeTruthy();
  expect(screen.getByText("Ready for Pickup")).toBeTruthy();
  expect(screen.queryByText("Completed")).toBeNull();
});

it("keeps all ordinary completion stages and removes pickup action", async () => {
  mockOrder.status = "completed";
  render(<OrderDetailScreen />);
  await screen.findByText("Completed");
  expect(screen.getByText("Preparing")).toBeTruthy();
  expect(screen.getByText("Ready for Pickup")).toBeTruthy();
  expect(screen.queryByText("Show Pickup QR Code")).toBeNull();
});
