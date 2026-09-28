/**
 * UniServe — Auth Context & Provider
 *
 * Manages authentication state across the mobile app.
 * Uses shared ApiClient with SecureStore-backed TokenProvider.
 * Handles token persistence, refresh, and user state.
 */

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { SecureStorage } from "../services/secure-storage";

import type { User, TokenPair } from "@uniserve/shared-types";
import * as authApi from "../services/auth";
import { loadPersistedTokens, secureStoreTokenProvider, setOnAuthFailure } from "../services/api";

const USER_KEY = "uniserve_user";

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isEmailVerified: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: {
    firstName: string;
    lastName: string;
    universityId: string;
    email: string;
    password: string;
  }) => Promise<{ userId: string; email: string }>;
  logout: () => Promise<void>;
  logoutAll: () => Promise<void>;
  refreshUser: () => Promise<void>;
  setTokens: (tokens: TokenPair) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [accessToken, setAccessToken] = useState<string | null>(null);

  // Register onAuthFailure to clear user state when token refresh fails
  useEffect(() => {
    setOnAuthFailure(() => {
      setAccessToken(null);
      setUser(null);
    });
  }, []);

  // Load persisted tokens and user on mount
  useEffect(() => {
    let cancelled = false;

    async function loadStoredAuth() {
      try {
        await loadPersistedTokens();

        // Sync the in-memory token cache into React state so isAuthenticated evaluates correctly
        const storedToken = secureStoreTokenProvider.getAccessToken();
        if (storedToken) setAccessToken(storedToken);

        const userJson = await SecureStorage.getItemAsync(USER_KEY);

        if (userJson) {
          setUser(JSON.parse(userJson));
        }
      } catch {
        // Corrupted storage — clear everything
        await SecureStorage.deleteItemAsync(USER_KEY);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    loadStoredAuth();
    return () => { cancelled = true; };
  }, []);

  // ---- Token helpers ----

  const clearTokens = useCallback(async () => {
    secureStoreTokenProvider.clearTokens();
    await SecureStorage.deleteItemAsync(USER_KEY);
    setAccessToken(null);
    setUser(null);
  }, []);

  // ---- Auth Actions ----

  const setTokens = useCallback(
    async (tokens: TokenPair) => {
      secureStoreTokenProvider.setTokens(tokens.access_token, tokens.refresh_token);
      setAccessToken(tokens.access_token);
    },
    [],
  );

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await authApi.login({
        university_email: email,
        password,
      });
      // Persist tokens to SecureStore + in-memory cache so ApiClient can
      // inject Authorization headers on subsequent requests
      secureStoreTokenProvider.setTokens(
        response.tokens.access_token,
        response.tokens.refresh_token,
      );
      setAccessToken(response.tokens.access_token);
      await SecureStorage.setItemAsync(USER_KEY, JSON.stringify(response.user));
      setUser(response.user);
    },
    [],
  );

  const register = useCallback(
    async (data: {
      firstName: string;
      lastName: string;
      universityId: string;
      email: string;
      password: string;
    }) => {
      const response = await authApi.register({
        first_name: data.firstName,
        last_name: data.lastName,
        university_id: data.universityId,
        university_email: data.email,
        password: data.password,
      });
      return {
        userId: response.user_id,
        email: response.university_email,
      };
    },
    [],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // Logout locally even if server call fails
    }
    await clearTokens();
  }, [clearTokens]);

  const logoutAll = useCallback(async () => {
    try {
      await authApi.logoutAll();
    } catch {
      // Logout locally even if server call fails
    }
    await clearTokens();
  }, [clearTokens]);

  const refreshUser = useCallback(async () => {
    try {
      const updatedUser = await authApi.getCurrentUser();
      await SecureStorage.setItemAsync(USER_KEY, JSON.stringify(updatedUser));
      setUser(updatedUser);
    } catch {
      await clearTokens();
    }
  }, [clearTokens]);

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user && !!accessToken,
    isLoading,
    isEmailVerified: user?.email_verified ?? false,
    login,
    register,
    logout,
    logoutAll,
    refreshUser,
    setTokens,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
