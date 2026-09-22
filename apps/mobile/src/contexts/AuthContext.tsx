/**
 * UniServe — Auth Context & Provider
 *
 * Manages authentication state across the mobile app.
 * Handles token storage, refresh, and user state.
 */

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import * as SecureStore from "expo-secure-store";

import type { User, AuthState, TokenPair } from "../types/auth";
import * as authApi from "../services/auth";

// Token storage keys
const ACCESS_TOKEN_KEY = "uniserve_access_token";
const REFRESH_TOKEN_KEY = "uniserve_refresh_token";
const USER_KEY = "uniserve_user";

interface AuthContextType extends AuthState {
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

  // ---- Token Storage ----

  const storeTokens = useCallback(async (tokens: TokenPair) => {
    await SecureStore.setItemAsync(ACCESS_TOKEN_KEY, tokens.access_token);
    await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, tokens.refresh_token);
    setAccessToken(tokens.access_token);
  }, []);

  const clearTokens = useCallback(async () => {
    await SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY);
    await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
    await SecureStore.deleteItemAsync(USER_KEY);
    setAccessToken(null);
    setUser(null);
  }, []);

  const loadStoredAuth = useCallback(async () => {
    try {
      const token = await SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
      const userJson = await SecureStore.getItemAsync(USER_KEY);

      if (token && userJson) {
        setAccessToken(token);
        setUser(JSON.parse(userJson));
      }
    } catch {
      await clearTokens();
    } finally {
      setIsLoading(false);
    }
  }, [clearTokens]);

  // Load stored auth on mount
  useEffect(() => {
    loadStoredAuth();
  }, [loadStoredAuth]);

  // ---- Auth Actions ----

  const setTokens = useCallback(
    async (tokens: TokenPair) => {
      await storeTokens(tokens);
    },
    [storeTokens]
  );

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await authApi.login({
        university_email: email,
        password,
      });
      await storeTokens(response.tokens);
      await SecureStore.setItemAsync(USER_KEY, JSON.stringify(response.user));
      setUser(response.user);
    },
    [storeTokens]
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
    []
  );

  const logout = useCallback(async () => {
    if (accessToken) {
      try {
        await authApi.logout(accessToken);
      } catch {
        // Logout locally even if server call fails
      }
    }
    await clearTokens();
  }, [accessToken, clearTokens]);

  const logoutAll = useCallback(async () => {
    if (accessToken) {
      try {
        await authApi.logoutAll(accessToken);
      } catch {
        // Logout locally even if server call fails
      }
    }
    await clearTokens();
  }, [accessToken, clearTokens]);

  const refreshUser = useCallback(async () => {
    if (accessToken) {
      try {
        const updatedUser = await authApi.getCurrentUser(accessToken);
        await SecureStore.setItemAsync(USER_KEY, JSON.stringify(updatedUser));
        setUser(updatedUser);
      } catch {
        await clearTokens();
      }
    }
  }, [accessToken, clearTokens]);

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
