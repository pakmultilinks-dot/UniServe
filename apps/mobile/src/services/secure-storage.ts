/**
 * UniServe — Platform-aware Secure Storage
 *
 * On native (iOS/Android): uses expo-secure-store (encrypted keychain/SharedPreferences).
 * On web: uses localStorage (not encrypted, but functional for development/verification).
 *
 * This shim allows the app to run on Expo Web without crashing.
 */

import { Platform } from "react-native";

// Native implementation
import * as ExpoSecureStore from "expo-secure-store";

const isWeb = Platform.OS === "web";

export const SecureStorage = {
  async getItemAsync(key: string): Promise<string | null> {
    if (isWeb) {
      try {
        return localStorage.getItem(key);
      } catch {
        return null;
      }
    }
    return ExpoSecureStore.getItemAsync(key);
  },

  async setItemAsync(key: string, value: string): Promise<void> {
    if (isWeb) {
      try {
        localStorage.setItem(key, value);
      } catch {
        // Storage full or unavailable
      }
      return;
    }
    return ExpoSecureStore.setItemAsync(key, value);
  },

  async deleteItemAsync(key: string): Promise<void> {
    if (isWeb) {
      try {
        localStorage.removeItem(key);
      } catch {
        // Ignore
      }
      return;
    }
    return ExpoSecureStore.deleteItemAsync(key);
  },
};
