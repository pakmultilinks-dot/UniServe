const mockExpoConfig: { current: { extra?: Record<string, unknown> } } = {
  current: { extra: {} },
};

jest.mock("expo-constants", () => ({
  get expoConfig() {
    return mockExpoConfig.current;
  },
}));

const ORIGINAL_ENV = process.env.EXPO_PUBLIC_API_BASE_URL;

// config.ts computes API_BASE_URL once at import time, so each test
// loads a fresh module instance after setting the env/channel it needs.
function loadConfig() {
  jest.resetModules();
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  return require("../config") as typeof import("../config");
}

afterEach(() => {
  if (ORIGINAL_ENV === undefined) {
    delete process.env.EXPO_PUBLIC_API_BASE_URL;
  } else {
    process.env.EXPO_PUBLIC_API_BASE_URL = ORIGINAL_ENV;
  }
  mockExpoConfig.current = { extra: {} };
});

describe("API base URL selection (src/config.ts)", () => {
  it("defaults to localhost in development when EXPO_PUBLIC_API_BASE_URL is unset", () => {
    delete process.env.EXPO_PUBLIC_API_BASE_URL;

    const { API_BASE_URL, APP_ENV } = loadConfig();

    expect(APP_ENV).toBe("development");
    expect(API_BASE_URL).toBe("http://localhost:8000/api/v1");
  });

  it("uses EXPO_PUBLIC_API_BASE_URL when set (physical-device LAN target)", () => {
    process.env.EXPO_PUBLIC_API_BASE_URL = "http://192.168.18.79:8000/api/v1";

    const { API_BASE_URL, APP_ENV } = loadConfig();

    expect(APP_ENV).toBe("development");
    expect(API_BASE_URL).toBe("http://192.168.18.79:8000/api/v1");
  });

  it("falls back to production host without a build-time override", () => {
    delete process.env.EXPO_PUBLIC_API_BASE_URL;
    mockExpoConfig.current = { extra: { eas: { channel: "production" } } };
    const { API_BASE_URL, APP_ENV } = loadConfig();
    expect(APP_ENV).toBe("production");
    expect(API_BASE_URL).toBe("https://uniserve-api.onrender.com/api/v1");
  });

  it("honors API overrides in production release builds", () => {
    process.env.EXPO_PUBLIC_API_BASE_URL = "http://192.168.18.79:8000/api/v1";
    mockExpoConfig.current = { extra: { eas: { channel: "production" } } };
    const { API_BASE_URL, APP_ENV } = loadConfig();
    expect(APP_ENV).toBe("production");
    expect(API_BASE_URL).toBe("http://192.168.18.79:8000/api/v1");
  });

  it("honors HTTPS API overrides in staging builds", () => {
    process.env.EXPO_PUBLIC_API_BASE_URL = "https://staging.example.test/api/v1";
    mockExpoConfig.current = { extra: { eas: { channel: "staging" } } };
    const { APP_ENV, API_BASE_URL, assertApiConfigured } = loadConfig();
    expect(APP_ENV).toBe("staging");
    expect(API_BASE_URL).toBe("https://staging.example.test/api/v1");
    expect(assertApiConfigured).not.toThrow();
  });
});
