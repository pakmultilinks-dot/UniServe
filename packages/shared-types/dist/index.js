"use strict";
/**
 * UniServe — Shared Type Definitions & API Client
 *
 * Types shared across mobile, web, and API applications.
 * Derived from the backend Pydantic schemas (authoritative source).
 *
 * IMPORTANT: The backend is the authoritative source for business rules.
 * This file mirrors the backend's public contract for frontend consumption.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.ApiClient = exports.ApiClientError = void 0;
/**
 * Typed API error with HTTP status and optional error code.
 */
class ApiClientError extends Error {
    constructor(status, message, code) {
        super(message);
        this.status = status;
        this.code = code;
        this.name = "ApiClientError";
    }
}
exports.ApiClientError = ApiClientError;
/**
 * Typed HTTP client with automatic auth header injection,
 * request timeout, token refresh on 401, and typed responses.
 */
class ApiClient {
    constructor(baseUrl, tokenProvider, onAuthFailure) {
        this.refreshPromise = null;
        this.baseUrl = baseUrl;
        this.tokenProvider = tokenProvider;
        this.onAuthFailure = onAuthFailure;
    }
    async request(method, endpoint, options) {
        const { body, timeout = 60000 } = options ?? {};
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);
        try {
            const headers = {
                "Content-Type": "application/json",
            };
            const token = this.tokenProvider.getAccessToken();
            if (token) {
                headers["Authorization"] = `Bearer ${token}`;
            }
            // Manual redirect handling: React Native's fetch may drop the
            // Authorization header on 307 redirects (FastAPI trailing-slash
            // redirects). We follow redirects manually, preserving headers.
            let url = `${this.baseUrl}${endpoint}`;
            let response = null;
            let redirectCount = 0;
            const maxRedirects = 5;
            while (redirectCount <= maxRedirects) {
                response = await fetch(url, {
                    method,
                    headers,
                    body: body != null ? JSON.stringify(body) : undefined,
                    signal: controller.signal,
                    // Prevent automatic redirect following so we can preserve headers
                    redirect: "manual",
                });
                // Handle redirects manually (301, 302, 303, 307, 308)
                if (response.status >= 300 && response.status < 400) {
                    const location = response.headers.get("location");
                    if (!location)
                        break;
                    // Resolve relative URLs
                    url = location.startsWith("http") ? location : new URL(location, url).href;
                    redirectCount++;
                    // For 303, change method to GET (per spec)
                    if (response.status === 303 && method !== "GET" && method !== "HEAD") {
                        method = "GET";
                    }
                    continue;
                }
                // Browsers (Chrome/Electron) return an OPAQUE REDIRECT for
                // redirect:"manual" on cross-origin requests: status 0 with no
                // readable Location header. Retry once with redirect:"follow" so
                // the FastAPI trailing-slash 307 is actually followed — same-host
                // HTTPS redirects preserve the Authorization header in practice.
                if (response.status === 0) {
                    response = await fetch(url, {
                        method,
                        headers,
                        body: body != null ? JSON.stringify(body) : undefined,
                        signal: controller.signal,
                        redirect: "follow",
                    });
                }
                break;
            }
            if (!response) {
                throw new ApiClientError(0, "Network error: no response received");
            }
            if (redirectCount > maxRedirects) {
                throw new ApiClientError(0, "Network error: too many redirects");
            }
            // Attempt token refresh on 401 when a refresh token is available.
            // This covers both expired-access-token (token was sent) and
            // absent-access-token (e.g. page reload) scenarios.
            if (response.status === 401 && this.tokenProvider.getRefreshToken()) {
                const newToken = await this.handleTokenRefresh();
                if (newToken) {
                    headers["Authorization"] = `Bearer ${newToken}`;
                    response = await fetch(`${this.baseUrl}${endpoint}`, {
                        method,
                        headers,
                        body: body != null ? JSON.stringify(body) : undefined,
                        signal: controller.signal,
                    });
                }
                else {
                    // Refresh failed — clear auth and notify
                    this.tokenProvider.clearTokens();
                    this.onAuthFailure?.();
                    throw new ApiClientError(401, "Session expired. Please log in again.");
                }
            }
            return await this.handleResponse(response);
        }
        catch (err) {
            if (err instanceof ApiClientError)
                throw err;
            if (err instanceof DOMException && err.name === "AbortError") {
                throw new ApiClientError(408, "Request timed out");
            }
            throw new ApiClientError(0, `Network error: ${err.message ?? "unknown"}`);
        }
        finally {
            clearTimeout(timeoutId);
        }
    }
    // ---- HTTP verb shortcuts ----
    get(endpoint) {
        return this.request("GET", endpoint);
    }
    post(endpoint, body) {
        return this.request("POST", endpoint, { body });
    }
    put(endpoint, body) {
        return this.request("PUT", endpoint, { body });
    }
    patch(endpoint, body) {
        return this.request("PATCH", endpoint, { body });
    }
    delete(endpoint) {
        return this.request("DELETE", endpoint);
    }
    /**
     * Upload a raw binary body (e.g. an image File/Blob) with an explicit
     * Content-Type header. Used for menu-item image uploads, where the API
     * expects the image bytes directly rather than a JSON envelope — the
     * deployment does not ship multipart support (python-multipart), so
     * single-file uploads ride the raw request body.
     *
     * Auth, token-refresh-on-401, timeout and error semantics mirror request().
     */
    async uploadBinary(method, endpoint, body, contentType, options) {
        const { timeout = 30000 } = options ?? {};
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);
        try {
            const headers = {
                "Content-Type": contentType,
            };
            const token = this.tokenProvider.getAccessToken();
            if (token) {
                headers["Authorization"] = `Bearer ${token}`;
            }
            let response = await fetch(`${this.baseUrl}${endpoint}`, {
                method,
                headers,
                body,
                signal: controller.signal,
            });
            if (response.status === 401 && this.tokenProvider.getRefreshToken()) {
                const newToken = await this.handleTokenRefresh();
                if (newToken) {
                    headers["Authorization"] = `Bearer ${newToken}`;
                    response = await fetch(`${this.baseUrl}${endpoint}`, {
                        method,
                        headers,
                        body,
                        signal: controller.signal,
                    });
                }
                else {
                    this.tokenProvider.clearTokens();
                    this.onAuthFailure?.();
                    throw new ApiClientError(401, "Session expired. Please log in again.");
                }
            }
            return await this.handleResponse(response);
        }
        catch (err) {
            if (err instanceof ApiClientError)
                throw err;
            if (err instanceof DOMException && err.name === "AbortError") {
                throw new ApiClientError(408, "Request timed out");
            }
            throw new ApiClientError(0, `Network error: ${err.message ?? "unknown"}`);
        }
        finally {
            clearTimeout(timeoutId);
        }
    }
    // ---- Internal helpers ----
    async handleResponse(response) {
        if (response.status === 204)
            return undefined;
        const data = await response.json().catch(() => null);
        if (!response.ok) {
            const detail = data?.detail;
            const code = data?.code;
            throw new ApiClientError(response.status, detail ?? `API error: ${response.status}`, code);
        }
        return data;
    }
    /**
     * Deduplicates concurrent refresh requests.
     */
    async handleTokenRefresh() {
        const refreshToken = this.tokenProvider.getRefreshToken();
        if (!refreshToken)
            return null;
        if (this.refreshPromise)
            return this.refreshPromise;
        this.refreshPromise = (async () => {
            try {
                const response = await fetch(`${this.baseUrl}/auth/refresh`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ refresh_token: refreshToken }),
                });
                if (!response.ok)
                    return null;
                const data = (await response.json());
                this.tokenProvider.setTokens(data.access_token, data.refresh_token);
                return data.access_token;
            }
            catch {
                return null;
            }
            finally {
                this.refreshPromise = null;
            }
        })();
        return this.refreshPromise;
    }
}
exports.ApiClient = ApiClient;
