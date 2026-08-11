/**
 * User-session logic: register, login, logout, and fetching/caching the
 * current user. Pages call these functions rather than hitting api.js's
 * /auth or /users endpoints directly, so "what does it mean to be logged
 * in" stays defined in one place.
 */

import { apiGet, apiPost, ApiError } from "./api.js";
import { clearTokens, isLoggedIn as hasTokens, setTokens } from "./auth-storage.js";

let cachedUser = null;
let cachedUserPromise = null;

export async function register({ email, username, password }) {
  return apiPost("/auth/register", { email, username, password }, { auth: false });
}

export async function login({ identifier, password }) {
  const tokens = await apiPost("/auth/login", { identifier, password }, { auth: false });
  setTokens(tokens.access_token, tokens.refresh_token);
  cachedUser = null;
  cachedUserPromise = null;
  return tokens;
}

export function logout() {
  clearTokens();
  cachedUser = null;
  cachedUserPromise = null;
}

export function isLoggedIn() {
  return hasTokens();
}

/**
 * Fetch (and memoize for the lifetime of the page) the current user.
 * Memoized because the navbar, and often the page itself, both need "who is
 * logged in" on every page load — without caching that's a duplicate
 * request every time.
 */
export async function getCurrentUser() {
  if (!hasTokens()) return null;
  if (cachedUser) return cachedUser;
  if (cachedUserPromise) return cachedUserPromise;

  cachedUserPromise = apiGet("/users/me")
    .then((user) => {
      cachedUser = user;
      return user;
    })
    .catch((err) => {
      if (err instanceof ApiError && err.status === 401) {
        clearTokens();
      }
      return null;
    })
    .finally(() => {
      cachedUserPromise = null;
    });

  return cachedUserPromise;
}

/**
 * Redirect to the login page if not authenticated, preserving the current
 * URL so login can return the user where they were headed. Pages that
 * require auth (favorites, collections, account) call this at the top of
 * their init function.
 */
export function requireAuth() {
  if (!hasTokens()) {
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.href = `/pages/auth.html?next=${next}`;
    return false;
  }
  return true;
}
