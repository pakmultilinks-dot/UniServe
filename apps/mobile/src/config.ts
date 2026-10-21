/**
 * UniServe — Application Configuration
 *
 * Environment-specific configuration for the mobile app.
 */

import Constants from "expo-constants";

const ENV = {
  development: {
    // EXPO_PUBLIC_API_BASE_URL (inlined by Metro at bundle time) lets
    // physical-device testing target the laptop's LAN address, e.g.
    // http://192.168.100.5:8000/api/v1, without changing this default.
    API_BASE_URL:
      process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1",
  },
  staging: {
    API_BASE_URL: "https://staging-api.uniserve.app/api/v1",
  },
  production: {
    API_BASE_URL: "https://uniserve-api.onrender.com/api/v1",
  },
};

type Environment = keyof typeof ENV;

const getEnvironment = (): Environment => {
  const releaseChannel = Constants.expoConfig?.extra?.eas?.channel;

  if (releaseChannel === "production") return "production";
  if (releaseChannel === "staging") return "staging";
  // Release builds without an EAS channel (e.g., GitHub Actions APK builds)
  // are production. __DEV__ is false in release bundles.
  if (typeof __DEV__ !== "undefined" && !__DEV__) return "production";
  return "development";
};

const environment = getEnvironment();

// Expo inlines this value at bundle time. Respect it for release APKs too.
// Previously the override applied only to development builds.
const configuredApiUrl = process.env.EXPO_PUBLIC_API_BASE_URL?.trim();
export const API_BASE_URL = configuredApiUrl || ENV[environment].API_BASE_URL;
export const APP_ENV = environment;

/**
 * Placeholder production hostnames must be replaced with the real API
 * origin before any release build. Failing loudly here is deliberate:
 * silently pointing the app at a fake domain would make every request
 * fail in a way that looks like a backend outage.
 */
const PLACEHOLDER_HOSTS = ["staging-api.uniserve.app", "api.uniserve.app"];
export function assertApiConfigured(): void {
  if (PLACEHOLDER_HOSTS.some((h) => API_BASE_URL.includes(h))) {
    throw new Error(
      `API_BASE_URL is still the placeholder (${API_BASE_URL}). ` +
        "Set EXPO_PUBLIC_API_BASE_URL or configure the production origin before release."
    );
  }
}

/**
 * Host-independent menu-image URL resolver (Phase 48).
 *
 * The API persists image references as `/api/v1/static/food/<file>` —
 * no scheme, no host — so one database value works on localhost, a
 * laptop's LAN IP, and production. Rendering attaches the configured
 * origin at read time. Absolute http(s) URLs pass through untouched.
 */
export function resolveApiImageUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  if (/^https?:\/\//i.test(url)) return url;
  const origin = API_BASE_URL.replace(/\/api\/v1\/?$/, "");
  if (url.startsWith("/")) return `${origin}${url}`;
  return `${origin}/api/v1/static/food/${url}`;
}
