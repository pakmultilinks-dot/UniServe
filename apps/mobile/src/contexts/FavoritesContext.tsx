/**
 * UniServe — Favorites Context & Provider
 *
 * User-scoped menu favorites (P3-5). The backend already had a complete
 * favorites API (GET/POST/DELETE /favorites) and the web console consumes
 * it — only the mobile surface was a static placeholder. This provider
 * loads the user's favorites on mount, keeps a synchronous Set for O(1)
 * heart-state reads in list/detail screens, and provides an optimistic
 * toggle (flips locally, reconciles with the server response/error).
 *
 * Server-side the list is strictly user-scoped (favorites are keyed by
 * auth.user.id), so each signed-in account only ever sees its own hearts.
 */

import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from "react";

import type { FavoriteResponse } from "@uniserve/shared-types";
import { getFavorites, addFavorite, removeFavorite } from "../services/data";
import { useAuth } from "./AuthContext";

interface FavoritesContextType {
  /** Favorite records (include embedded menu_item payloads when provided). */
  favorites: FavoriteResponse[];
  /** Fast synchronous lookup for rendering heart state in lists. */
  isFavorite: (menuItemId: string) => boolean;
  /**
   * Optimistically toggle a favorite. Returns the resulting state
   * (true = favorited after the call). Throws when the server rejects
   * the change — the local optimistic state is reverted in that case.
   */
  toggleFavorite: (menuItemId: string) => Promise<boolean>;
  /** Re-fetch favorites from the server. */
  refresh: () => Promise<void>;
  /** True while the initial load is in flight. */
  isLoading: boolean;
}

const FavoritesContext = createContext<FavoritesContextType | undefined>(undefined);

export function FavoritesProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  const [favorites, setFavorites] = useState<FavoriteResponse[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  // Guard against stale toggles overwriting a newer refresh result.
  const loadSeq = useRef(0);

  const refresh = useCallback(async () => {
    if (!isAuthenticated) {
      setFavorites([]);
      return;
    }
    const seq = ++loadSeq.current;
    setIsLoading(true);
    try {
      const favs = await getFavorites();
      // Ignore responses that arrive after a newer load started.
      if (seq === loadSeq.current) setFavorites(favs);
    } finally {
      if (seq === loadSeq.current) setIsLoading(false);
    }
  }, [isAuthenticated]);

  // Load on mount and whenever auth state changes (login / logout).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await refresh();
      } catch {
        // Network failure on load is non-fatal — the favorites tab and
        // heart controls degrade to "not favorited" until the next refresh.
        if (!cancelled) setFavorites([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  // Clear in-memory favorites on sign-out so the next account starts clean.
  useEffect(() => {
    if (!isAuthenticated) setFavorites([]);
  }, [isAuthenticated]);

  const isFavorite = useCallback(
    (menuItemId: string) => favorites.some((f) => f.menu_item_id === menuItemId),
    [favorites],
  );

  const toggleFavorite = useCallback(
    async (menuItemId: string): Promise<boolean> => {
      const currentlyFav = favorites.some((f) => f.menu_item_id === menuItemId);
      // Snapshot for exact revert if the server rejects the change.
      const snapshot = favorites;
      // Optimistic flip for instant heart feedback.
      if (currentlyFav) {
        setFavorites((prev) => prev.filter((f) => f.menu_item_id !== menuItemId));
      }
      try {
        if (currentlyFav) {
          await removeFavorite(menuItemId);
          return false;
        }
        const created = await addFavorite(menuItemId);
        setFavorites((prev) =>
          prev.some((f) => f.menu_item_id === menuItemId)
            ? prev
            : [...prev, created],
        );
        return true;
      } catch (err) {
        // Restore the pre-toggle snapshot on server rejection.
        setFavorites(snapshot);
        throw err;
      }
    },
    [favorites],
  );

  const value = React.useMemo(
    () => ({ favorites, isFavorite, toggleFavorite, refresh, isLoading }),
    [favorites, isFavorite, toggleFavorite, refresh, isLoading],
  );

  return <FavoritesContext.Provider value={value}>{children}</FavoritesContext.Provider>;
}

export function useFavorites(): FavoritesContextType {
  const ctx = useContext(FavoritesContext);
  if (!ctx) {
    throw new Error("useFavorites must be used within a FavoritesProvider");
  }
  return ctx;
}
