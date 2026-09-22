/**
 * UniServe — Web Auth Context & Provider
 *
 * Client-side authentication state management using React Context.
 * Stores tokens in localStorage for persistence across page refreshes.
 */

"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";

import type { User, AuthState, UserRole } from "../types/auth";
import * as authApi from "../lib/auth";

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
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Load stored user on mount
  useEffect(() => {
    try {
      const storedUser = localStorage.getItem(USER_KEY);
      const storedToken = localStorage.getItem(ACCESS_TOKEN_KEY);
      if (storedUser && storedToken) {
        setUser(JSON.parse(storedUser));
      }
    } catch {
      localStorage.removeItem(ACCESS_TOKEN_KEY);
      localStorage.removeItem(REFRESH_TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const storeAuth = useCallback((user: User, tokens: { access_token: string; refresh_token: string }) => {
    localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }, []);

  const clearAuth = useCallback(() => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setUser(null);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await authApi.login({
        university_email: email,
        password,
      });
      storeAuth(response.user, response.tokens);
      setUser(response.user);
    },
    [storeAuth]
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
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (token) {
      try {
        await authApi.logout(token);
      } catch {
        // Continue with local logout
      }
    }
    clearAuth();
  }, [clearAuth]);

  const refreshUser = useCallback(async () => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (token) {
      try {
        const updatedUser = await authApi.getCurrentUser(token);
        localStorage.setItem(USER_KEY, JSON.stringify(updatedUser));
        setUser(updatedUser);
      } catch {
        clearAuth();
      }
    }
  }, [clearAuth]);

  const hasRole = useCallback(
    (roles: UserRole | UserRole[]) => {
      if (!user) return false;
      const roleArray = Array.isArray(roles) ? roles : [roles];
      return roleArray.includes(user.role);
    },
    [user]
  );

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    hasRole,
    login,
    register,
    logout,
    refreshUser,
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
