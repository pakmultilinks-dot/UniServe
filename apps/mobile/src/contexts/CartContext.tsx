/**
 * UniServe — Cart Context (Mobile)
 *
 * Manages the active cart state for food ordering.
 * Tracks selected cafeteria, cart items, totals, and provides
 * add/update/remove operations with optimistic UI updates.
 */

import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from "react";
import type { CartResponse, CartItemResponse, Cafeteria } from "@uniserve/shared-types";
import { SecureStorage } from "../services/secure-storage";
import { useAuth } from "./AuthContext";
import {
  getCart,
  addCartItem as apiAddCartItem,
  updateCartItemQuantity as apiUpdateCartItem,
  removeCartItem as apiRemoveCartItem,
  getCafeterias,
} from "../services/data";

interface CartContextValue {
  /** Currently selected cafeteria */
  selectedCafeteria: Cafeteria | null;
  /** Whether we're still determining the default cafeteria */
  isCafeteriaLoading: boolean;
  /** Select a cafeteria and load its cart */
  selectCafeteria: (cafeteria: Cafeteria) => void;
  /** The current cart (null if not loaded or no cafeteria selected) */
  cart: CartResponse | null;
  /** Whether cart is currently loading */
  isCartLoading: boolean;
  /** Last cart API error, if loading failed */
  cartError: string | null;
  /** Number of distinct items in the cart */
  cartItemCount: number;
  /** Total amount in paisa */
  cartTotal: number;
  /** Add an item to the cart */
  addToCart: (menuItemId: string, quantity?: number) => Promise<void>;
  /** Update quantity of a cart item */
  updateQuantity: (cartItemId: string, quantity: number) => Promise<void>;
  /** Remove an item from the cart */
  removeFromCart: (cartItemId: string) => Promise<void>;
  /** Refresh the cart from the API */
  refreshCart: () => Promise<void>;
}

const CartContext = createContext<CartContextValue | null>(null);

export function useCart(): CartContextValue {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used within CartProvider");
  return ctx;
}

export function CartProvider({ children }: { children: React.ReactNode }) {
  // Persisted tokens are read asynchronously on launch; every fetch below
  // must wait for auth to settle or it fires unauthenticated and 401s.
  // isAuthenticated (not just authReady) so a signed-out session never
  // fetches cafeterias/cart at all.
  const { isAuthenticated } = useAuth();
  const [selectedCafeteria, setSelectedCafeteria] = useState<Cafeteria | null>(null);
  const [isCafeteriaLoading, setIsCafeteriaLoading] = useState(true);
  const [cart, setCart] = useState<CartResponse | null>(null);
  const [isCartLoading, setIsCartLoading] = useState(false);
  const [cartError, setCartError] = useState<string | null>(null);

  // Prevent concurrent cart operations
  const cartLockRef = useRef(false);

  /* The user's last choice survives app restarts — without this the app
     silently reset to the first cafeteria on every launch, discarding the
     selection the user made on the home screen. */
  const CAFETERIA_STORAGE_KEY = "uniserve_selected_cafeteria";

  /** Auto-select the remembered cafeteria (or the first one) once signed in */
  useEffect(() => {
    if (!isAuthenticated) return;
    (async () => {
      try {
        const cafeterias = await getCafeterias();
        if (cafeterias.length > 0) {
          let preferredId: string | null = null;
          try {
            preferredId = await SecureStorage.getItemAsync(CAFETERIA_STORAGE_KEY);
          } catch {
            // Storage unavailable — fall back to the first cafeteria
          }
          // The stored id may reference a cafeteria that was removed or
          // deactivated — only honour it when it is still in the list.
          const remembered = preferredId
            ? cafeterias.find((c) => c.id === preferredId)
            : undefined;
          setSelectedCafeteria(remembered ?? cafeterias[0]);
        }
      } catch {
        // Silent — cafeteria selection will be manual
      } finally {
        setIsCafeteriaLoading(false);
      }
    })();
  }, [isAuthenticated]);

  /** Load cart when cafeteria is selected */
  const loadCart = useCallback(async (cafeteriaId: string) => {
    setIsCartLoading(true);
    try {
      const cartData = await getCart(cafeteriaId);
      setCart(cartData);
      setCartError(null);
    } catch (error) {
      setCart(null);
      setCartError(error instanceof Error ? error.message : "Failed to load cart");
    } finally {
      setIsCartLoading(false);
    }
  }, []);

  React.useEffect(() => {
    if (selectedCafeteria) {
      loadCart(selectedCafeteria.id);
    }
  }, [selectedCafeteria, loadCart]);

  const selectCafeteria = useCallback((cafeteria: Cafeteria) => {
    setSelectedCafeteria(cafeteria);
    // Remember the choice across launches (best-effort — a storage failure
    // must never block the selection itself).
    SecureStorage.setItemAsync(CAFETERIA_STORAGE_KEY, cafeteria.id).catch(() => {});
  }, []);

  const refreshCart = useCallback(async () => {
    if (selectedCafeteria) {
      await loadCart(selectedCafeteria.id);
    }
  }, [selectedCafeteria, loadCart]);

  const addToCart = useCallback(
    async (menuItemId: string, quantity: number = 1) => {
      // Fail loudly: a silent return here made the + button look broken
      // ("no changes occur") with no toast and no console output.
      if (!selectedCafeteria) {
        throw new Error("Select a cafeteria first");
      }
      if (cartLockRef.current) {
        throw new Error("Still updating the cart — try again in a second");
      }
      cartLockRef.current = true;
      try {
        await apiAddCartItem(selectedCafeteria.id, menuItemId, quantity);
        await loadCart(selectedCafeteria.id);
      } finally {
        cartLockRef.current = false;
      }
    },
    [selectedCafeteria, loadCart],
  );

  const updateQuantity = useCallback(
    async (cartItemId: string, quantity: number) => {
      if (!selectedCafeteria) {
        throw new Error("Select a cafeteria first");
      }
      if (cartLockRef.current) {
        throw new Error("Still updating the cart — try again in a second");
      }
      cartLockRef.current = true;
      try {
        if (quantity <= 0) {
          await apiRemoveCartItem(selectedCafeteria.id, cartItemId);
        } else {
          await apiUpdateCartItem(selectedCafeteria.id, cartItemId, quantity);
        }
        await loadCart(selectedCafeteria.id);
      } finally {
        cartLockRef.current = false;
      }
    },
    [selectedCafeteria, loadCart],
  );

  const removeFromCart = useCallback(
    async (cartItemId: string) => {
      if (!selectedCafeteria) {
        throw new Error("Select a cafeteria first");
      }
      if (cartLockRef.current) {
        throw new Error("Still updating the cart — try again in a second");
      }
      cartLockRef.current = true;
      try {
        await apiRemoveCartItem(selectedCafeteria.id, cartItemId);
        await loadCart(selectedCafeteria.id);
      } finally {
        cartLockRef.current = false;
      }
    },
    [selectedCafeteria, loadCart],
  );

  const value: CartContextValue = {
    selectedCafeteria,
    isCafeteriaLoading,
    selectCafeteria,
    cart,
    isCartLoading,
    cartError,
    cartItemCount: cart?.item_count ?? 0,
    cartTotal: cart?.total_amount ?? 0,
    addToCart,
    updateQuantity,
    removeFromCart,
    refreshCart,
  };

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}
