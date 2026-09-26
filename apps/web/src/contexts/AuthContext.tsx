/**
 * UniServe — Web Auth Context & Provider
 *
 * Client-side authentication state management using React Context.
 *
 * Token storage strategy (XSS mitigation):
 *   - Access token: kept in module-scope memory only (never DOM-persisted)
 *   - Refresh token: stored in sessionStorage (cleared on tab close)
 *   - On page load: attempt silent refresh from stored refresh token
 *   - On 401 from ApiClient: automatic refresh + retry, then onAuthFailure
 */

"use client";

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
} from "react";

import type { User, UserRole } from "@uniserve/shared-types";
import * as authApi from "@/lib/api";

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  hasRole: (role: UserRole | UserRole[]) => boolean;
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

  // Register the onAuthFailure callback so ApiClient can trigger logout
  useEffect(() => {
    authApi.setOnAuthFailure(() => {
      setUser(null);
    });
  }, []);

  // On mount: attempt silent refresh if we have a refresh token stored
  useEffect(() => {
    let cancelled = false;

    async function trySilentRefresh() {
      try {
        const refreshedUser = await authApi.getCurrentUser();
        if (!cancelled) {
          setUser(refreshedUser);
        }
      } catch {
        // No valid session — user must log in
        if (!cancelled) {
          setUser(null);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    trySilentRefresh();
    return () => { cancelled = true; };
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await authApi.login({
        university_email: email,
        password,
      });
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
      // Continue with local logout even if server call fails
    }
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const updatedUser = await authApi.getCurrentUser();
      setUser(updatedUser);
    } catch {
      setUser(null);
    }
  }, []);

  const hasRole = useCallback(
    (roles: UserRole | UserRole[]) => {
      if (!user) return false;
      const roleArray = Array.isArray(roles) ? roles : [roles];
      return roleArray.includes(user.role);
    },
    [user],
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
