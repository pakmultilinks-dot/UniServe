import React from "react";
import { Text, AppState, type AppStateStatus } from "react-native";
import { render, screen, act, waitFor } from "@testing-library/react-native";
import { CartProvider, useCart } from "../contexts/CartContext";
import { getCafeterias } from "../services/data";
let mockAuthenticated = true;
jest.mock("../contexts/AuthContext", () => ({ useAuth: () => ({ isAuthenticated: mockAuthenticated }) }));
jest.mock("../services/secure-storage", () => ({ SecureStorage: { getItemAsync: jest.fn(async () => null), setItemAsync: jest.fn(async () => {}) } }));
jest.mock("../services/data", () => ({ getCafeterias: jest.fn(), getCart: jest.fn(async () => ({ items: [] })) }));
let state: ReturnType<typeof useCart>;
function Reader() {
  const value = useCart();
  React.useEffect(() => { state = value; }, [value]);
  return <Text testID="state">{JSON.stringify({ error: value.cafeteriasError, loading: value.isCafeteriaLoading, selected: value.selectedCafeteria?.id, cafeterias: value.cafeterias.length })}</Text>;
}
const read = () => JSON.parse(screen.getByTestId("state").props.children);
const request = getCafeterias as jest.Mock;
beforeEach(() => { jest.clearAllMocks(); mockAuthenticated = true;
  request.mockReset();
  jest.spyOn(AppState, "addEventListener").mockReturnValue({ remove: jest.fn() }); });
it("recovers a failed first load through one shared retry and clears the stale error", async () => {
  request.mockRejectedValueOnce(new Error("offline"));
  render(<CartProvider><Reader /></CartProvider>);
  await waitFor(() => expect(read().error).toContain("Unable to connect"));
  request.mockResolvedValueOnce([{ id: "caf", name: "Student Cafeteria" }]);
  await act(async () => { await state.refreshCafeterias(); });
  expect(read()).toEqual({ error: "", loading: false, selected: "caf", cafeterias: 1 });
});
it("shares simultaneous retries rather than showing conflicting request results", async () => {
  let resolve!: (value: unknown) => void;
  request.mockReturnValueOnce(new Promise((done) => { resolve = done; }));
  render(<CartProvider><Reader /></CartProvider>);
  let a!: Promise<unknown>, b!: Promise<unknown>;
  act(() => { a = state.refreshCafeterias(); b = state.refreshCafeterias(); });
  expect(a).toBe(b); expect(request).toHaveBeenCalledTimes(1);
  await act(async () => { resolve([{ id: "caf" }]); await a; });
  expect(read().selected).toBe("caf"); expect(read().error).toBe("");
});
it("does not restore an old session's selection after logout", async () => {
  let resolve!: (value: unknown) => void;
  request.mockReturnValueOnce(new Promise((done) => { resolve = done; }));
  const view = render(<CartProvider><Reader /></CartProvider>);
  mockAuthenticated = false;
  view.rerender(<CartProvider><Reader /></CartProvider>);
  await act(async () => { resolve([{ id: "old-session-caf" }]); });
  expect(read().selected).toBeUndefined(); expect(read().cafeterias).toBe(0);
});

it("refreshes a failed cafeteria load when the app returns to the foreground", async () => {
  let foreground: ((state: AppStateStatus) => void) | undefined;
  jest.spyOn(AppState, "addEventListener").mockImplementation((_event, listener) => {
    foreground = listener;
    return { remove: jest.fn() };
  });
  request.mockRejectedValueOnce(new Error("offline"));
  render(<CartProvider><Reader /></CartProvider>);
  await waitFor(() => expect(read().error).toContain("Unable to connect"));
  request.mockResolvedValueOnce([{ id: "restored" }]);
  await act(async () => { foreground?.("active"); });
  await waitFor(() => expect(read().selected).toBe("restored"));
  expect(read().error).toBe("");
});
