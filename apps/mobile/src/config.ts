/**
 * UniServe — Application Configuration
 *
 * Environment-specific configuration for the mobile app.
 */

import Constants from "expo-constants";

const ENV = {
  development: {
    API_BASE_URL: "http://localhost:8000/api/v1",
  },
  staging: {
    API_BASE_URL: "https://staging-api.uniserve.app/api/v1",
  },
  production: {
    API_BASE_URL: "https://api.uniserve.app/api/v1",
  },
};

type Environment = keyof typeof ENV;

const getEnvironment = (): Environment => {
  const releaseChannel = Constants.expoConfig?.extra?.eas?.channel;

  if (releaseChannel === "production") return "production";
  if (releaseChannel === "staging") return "staging";
  return "development";
};

const environment = getEnvironment();

export const API_BASE_URL = ENV[environment].API_BASE_URL;
export const APP_ENV = environment;
