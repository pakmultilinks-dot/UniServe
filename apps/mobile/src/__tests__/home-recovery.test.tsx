import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react-native";
import HomeScreen from "../../app/(app)/(tabs)";
import { getTodaysMenu } from "../services/data";
const mockCafe = { id: "c1", name: "Student Cafeteria", operational_status: "open" };
let mockCart: Record<string, unknown>;
jest.mock("expo-router", () => ({ useRouter: () => ({ push: jest.fn() }), useFocusEffect: jest.fn() }));
jest.mock("@expo/vector-icons", () => ({ Ionicons: "Ionicons" }));
jest.mock("../contexts/AuthContext", () => ({ useAuth: () => ({ user: { first_name: "Test" } }) }));
jest.mock("../contexts/ThemeContext", () => ({ useTheme: () => ({ resolvedTheme: "light" }) }));
jest.mock("../contexts/CartContext", () => ({ useCart: () => mockCart }));
jest.mock("../contexts/FavoritesContext", () => ({ useFavorites: () => ({ isFavorite: () => false }) }));
jest.mock("../contexts/NotificationsContext", () => ({ useNotifications: () => ({ unreadCount: 0, refreshUnreadCount: jest.fn() }) }));
jest.mock("../services/data", () => ({ getTodaysMenu: jest.fn() }));
jest.mock("../components/ui/BottomSheet", () => {
  const React = require("react"); const { View, Text, Pressable } = require("react-native");
  return {
    BottomSheet: ({ visible, children }: { visible: boolean; children: React.ReactNode }) => visible ? <View>{children}</View> : null,
    BottomSheetRow: ({ label, onPress }: { label: string; onPress: () => void }) => <Pressable testID="choose-cafeteria" onPress={onPress}><Text>{label}</Text></Pressable>,
  };
});
jest.mock("../components/ui", () => {
  const React = require("react"); const { Text, TextInput, Pressable } = require("react-native");
  return {
    FoodCard: ({ name }: { name: string }) => <Text>{name}</Text>,
    SearchBar: (props: object) => <TextInput testID="search" {...props} />,
    CategoryChips: ({ onSelect }: { onSelect: (category: string) => void }) => <Pressable testID="breakfast" onPress={() => onSelect("breakfast")}><Text>Breakfast</Text></Pressable>,
    EmptyState: ({ title }: { title: string }) => <Text>{title}</Text>,
    CartBar: () => null, Toast: () => null, SkeletonCard: () => <Text>Loading menu</Text>,
  };
});
const menu = getTodaysMenu as jest.Mock;
beforeEach(() => {
  jest.clearAllMocks();
  mockCart = { selectedCafeteria: mockCafe, cafeterias: [mockCafe], cafeteriasError: "", isCafeteriaLoading: false, refreshCafeterias: jest.fn(), selectCafeteria: jest.fn(), cartItemCount: 0 };
  menu.mockResolvedValue({ items: [{ menu_item: { id: "food", name: "Chicken Biryani", category: "main_course", is_available: true }, is_available_today: true }] });
});
it("shows cafeteria failure and removes it once the shared retry recovers", async () => {
  mockCart = { ...mockCart, selectedCafeteria: null, cafeterias: [], cafeteriasError: "Unable to connect. Check your connection and try again." };
  const view = render(<HomeScreen />);
  await screen.findByText("Unable to connect. Check your connection and try again.");
  mockCart = { ...mockCart, selectedCafeteria: mockCafe, cafeterias: [mockCafe], cafeteriasError: "" };
  view.rerender(<HomeScreen />);
  await screen.findByText("Chicken Biryani", {}, { timeout: 10000 });
  expect(screen.queryByText("Unable to connect")).toBeNull();
});
it("filters search/categories locally without extra network requests", async () => {
  render(<HomeScreen />); await screen.findByText("Chicken Biryani", {}, { timeout: 10000 });
  fireEvent.changeText(screen.getByTestId("search"), "nothing-matches");
  await screen.findByText("No items found");
  fireEvent.changeText(screen.getByTestId("search"), "chicken");
  await screen.findByText("Chicken Biryani", {}, { timeout: 10000 });
  fireEvent.press(screen.getByTestId("breakfast"));
  await waitFor(() => expect(screen.queryByText("Chicken Biryani")).toBeNull());
  expect(menu).toHaveBeenCalledTimes(1);
});

it("ignores a delayed menu response from the previous cafeteria", async () => {
  let resolveOld!: (value: unknown) => void;
  menu.mockReturnValueOnce(new Promise((resolve) => { resolveOld = resolve; }))
    .mockResolvedValueOnce({ items: [{ menu_item: { id: "new-food", name: "New Cafe Meal", category: "main_course", is_available: true }, is_available_today: true }] });
  const view = render(<HomeScreen />);
  mockCart = { ...mockCart, selectedCafeteria: { ...mockCafe, id: "c2" } };
  view.rerender(<HomeScreen />);
  await screen.findByText("New Cafe Meal");
  await act(async () => { resolveOld({ items: [{ menu_item: { id: "old-food", name: "Stale Meal" } }] }); });
  expect(screen.queryByText("Stale Meal")).toBeNull();
  expect(screen.getByText("New Cafe Meal")).toBeTruthy();
});

it("keeps the loaded menu when the already-selected cafeteria is chosen again", async () => {
  render(<HomeScreen />); await screen.findByText("Chicken Biryani", {}, { timeout: 10000 });
  fireEvent.press(screen.getByLabelText("Current cafeteria: Student Cafeteria. Tap to change."));
  fireEvent.press(screen.getByTestId("choose-cafeteria"));
  expect(screen.getByText("Chicken Biryani")).toBeTruthy();
  expect(screen.queryByText("Loading menu")).toBeNull();
  expect(menu).toHaveBeenCalledTimes(1);
});
