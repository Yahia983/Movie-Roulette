/**
 * Small, pure, dependency-free helpers reused across pages: formatting and
 * timing utilities. Kept as plain functions (no classes/state) so any page
 * can import just what it needs.
 */

/** Debounce a function — used on the search input so every keystroke
 * doesn't trigger an API call. */
export function debounce(fn, delayMs = 300) {
  let timeoutId;
  return (...args) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn(...args), delayMs);
  };
}

/** "2019-06-14" -> "2019". Titles are commonly browsed/compared by year. */
export function releaseYear(isoDate) {
  if (!isoDate) return "—";
  return isoDate.slice(0, 4);
}

/** 118 -> "1h 58m". Runtime is stored in minutes; users think in hours. */
export function formatRuntime(minutes) {
  if (!minutes) return null;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
}

/** 7.83 -> "7.8" — one decimal place is the convention users expect from
 * every rating surface (IMDb, Letterboxd, etc.). */
export function formatRating(value) {
  if (value === null || value === undefined) return "—";
  return value.toFixed(1);
}

/** Resolve a poster/backdrop path to a usable <img src>.
 *
 * The backend currently stores raw catalog paths (e.g. from a future TMDB
 * sync) without a configured image CDN base yet — this is the one place
 * that decision gets made, so wiring up a real image host later is a
 * one-function change instead of a find-and-replace across every template.
 */
export function resolveImageUrl(path, kind = "poster") {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  // No image backend wired up yet (see docs/ARCHITECTURE.md, "what's not
  // built yet") — callers should treat a null return as "show the fallback".
  return null;
}

export function titleDetailUrl(title) {
  const type = title.media_type === "tv_show" ? "tv" : "movie";
  return `/pages/title.html?type=${type}&slug=${encodeURIComponent(title.slug)}`;
}
