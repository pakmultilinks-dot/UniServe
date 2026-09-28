/**
 * UniServe — Mobile API Client
 *
 * Uses the shared ApiClient from @uniserve/shared-types.
 * Mobile-specific TokenProvider stores tokens in expo-secure-store
 * (encrypted keychain on iOS, encrypted SharedPreferences on Android).
 */

import { SecureStorage } from "./secure-storage";

import { API_BASE_URL } from "../config";
import {
  ApiClient,
  type TokenProvider,
} from "@uniserve/shared-types";

// ---- SecureStore Token Provider ----

const ACCESS_TOKEN_KEY = "uniserve_access_token";
const REFRESH_TOKEN_KEY = "uniserve_refresh_token";

const secureStoreTokenProvider: TokenProvider = {
  getAccessToken: () => {
    // SecureStore is async, but TokenProvider requires sync access.
    // We cache the token in a module-scope variable for synchronous reads.
    return inMemoryAccessToken;
  },
  getRefreshToken: () => inMemoryRefreshToken,
  setTokens: (accessToken: string, refreshToken: string) => {
    inMemoryAccessToken = accessToken;
    inMemoryRefreshToken = refreshToken;
    // Persist asynchronously — will be available on next read
    SecureStorage.setItemAsync(ACCESS_TOKEN_KEY, accessToken);
    SecureStorage.setItemAsync(REFRESH_TOKEN_KEY, refreshToken);
  },
  clearTokens: () => {
    inMemoryAccessToken = null;
    inMemoryRefreshToken = null;
    SecureStorage.deleteItemAsync(ACCESS_TOKEN_KEY);
    SecureStorage.deleteItemAsync(REFRESH_TOKEN_KEY);
  },
};

// Module-scope cache for synchronous TokenProvider reads
let inMemoryAccessToken: string | null = null;
let inMemoryRefreshToken: string | null = null;

/**
 * Load persisted tokens into memory on startup.
 * Call this once at app launch (in AuthContext or _layout).
 */
export async function loadPersistedTokens(): Promise<void> {
  const accessToken = await SecureStorage.getItemAsync(ACCESS_TOKEN_KEY);
  const refreshToken = await SecureStorage.getItemAsync(REFRESH_TOKEN_KEY);
  if (accessToken) inMemoryAccessToken = accessToken;
  if (refreshToken) inMemoryRefreshToken = refreshToken;
}

// Export for direct use by AuthContext (token persistence)
export { secureStoreTokenProvider };

// ---- Client Initialization ----

let onAuthFailureCallback: (() => void) | null = null;

export function setOnAuthFailure(callback: () => void): void {
  onAuthFailureCallback = callback;
}

export const apiClient = new ApiClient(
  API_BASE_URL,
  secureStoreTokenProvider,
  () => onAuthFailureCallback?.(),
);

// Re-export shared types for convenience
export { ApiClientError } from "@uniserve/shared-types";
