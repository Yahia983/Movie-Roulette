/**
 * The single HTTP chokepoint for the whole frontend.
 *
 * Why everything funnels through here: every feature needs consistent base
 * URL handling, JSON parsing, error surfacing, and — once a user is logged
 * in — an auth header and automatic access-token refresh on a 401. Putting
 * that in one place means individual pages never touch `fetch` directly and
 * can't each get token handling subtly wrong.
 */

import { getAccessToken, getRefreshToken, setTokens, clearTokens } from "./auth-storage.js";
import { API_BASE_URL_OVERRIDE } from "./config.js";

const API_BASE_URL =
  API_BASE_URL_OVERRIDE ||
  (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? "http://localhost:8000/api/v1"
    : "/api/v1");

export class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

let refreshInFlight = null;

/**
 * Attempt to exchange the stored refresh token for a new access token.
 * Deduplicated via `refreshInFlight` so concurrent 401s (e.g. several
 * requests firing at once) trigger exactly one refresh call, not one each.
 */
async function refreshAccessToken() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  if (!refreshInFlight) {
    refreshInFlight = fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) setTokens(data.access_token, data.refresh_token);
        else clearTokens();
        return data;
      })
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

/**
 * Core request function. All exported helpers (apiGet, apiPost, ...) call
 * through this so retry-on-401 logic exists in exactly one place.
 */
async function request(path, { method = "GET", body, auth = true, isRetry = false } = {}) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const token = auth ? getAccessToken() : null;
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  // A 401 on an authenticated request gets exactly one silent retry after a
  // token refresh — this is what lets a session survive past the access
  // token's short expiry without the user noticing.
  if (response.status === 401 && auth && token && !isRetry) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return request(path, { method, body, auth, isRetry: true });
    }
  }

  if (response.status === 204) return null;

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const message =
      (isJson && data && (data.detail || data.message)) || `Request to ${path} failed`;
    throw new ApiError(typeof message === "string" ? message : JSON.stringify(message), response.status, data);
  }

  return data;
}

export const apiGet = (path, opts) => request(path, { ...opts, method: "GET" });
export const apiPost = (path, body, opts) => request(path, { ...opts, method: "POST", body });
export const apiPut = (path, body, opts) => request(path, { ...opts, method: "PUT", body });
export const apiPatch = (path, body, opts) => request(path, { ...opts, method: "PATCH", body });
export const apiDelete = (path, opts) => request(path, { ...opts, method: "DELETE" });

/** Build a query string from a plain object, dropping null/undefined/empty values. */
export function toQueryString(params) {
  const usp = new URLSearchParams();
  for (const [key, value] of Object.entries(params || {})) {
    if (value === null || value === undefined || value === "") continue;
    if (Array.isArray(value)) {
      value.forEach((v) => usp.append(key, v));
    } else {
      usp.append(key, value);
    }
  }
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}
