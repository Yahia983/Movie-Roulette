/**
 * Token persistence, isolated in its own tiny module.
 *
 * Why separate from auth.js: api.js needs to read/write tokens (for the
 * refresh-on-401 flow) without importing the higher-level auth.js — which
 * itself imports api.js for login/register calls. Splitting storage out
 * breaks that circular dependency cleanly.
 */

const ACCESS_TOKEN_KEY = "mr_access_token";
const REFRESH_TOKEN_KEY = "mr_refresh_token";

export function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setTokens(accessToken, refreshToken) {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  if (refreshToken) localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export function isLoggedIn() {
  return Boolean(getAccessToken());
}
