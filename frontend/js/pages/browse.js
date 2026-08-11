/**
 * Browse page: tabbed movie/TV search with sidebar filters and infinite
 * scroll. State lives in the URL's query string (not just in memory) so a
 * filtered view is shareable/bookmarkable and survives a page refresh —
 * the URL is the single source of truth, re-parsed on load and rewritten
 * (via replaceState) whenever a filter changes.
 */

import { apiGet, toQueryString } from "../api.js";
import { renderChrome } from "../components/navbar.js";
import { renderSkeletonGrid, renderTitleGrid } from "../components/title-card.js";
import { debounce } from "../utils.js";

const els = {};
let state = {
  type: "movie",
  search: "",
  sortBy: "popularity",
  minRating: 0,
  genreIds: [],
  page: 1,
};
let totalResults = 0;
let isLoading = false;
let allGenres = [];

function readStateFromUrl() {
  const params = new URLSearchParams(window.location.search);
  state.type = params.get("type") === "tv" ? "tv" : "movie";
  state.search = params.get("search") || "";
  state.sortBy = params.get("sort_by") || "popularity";
  state.minRating = Number(params.get("min_rating") || 0);
  state.genreIds = (params.getAll("genre_ids") || []).map(Number).filter(Boolean);
}

function writeStateToUrl() {
  const params = new URLSearchParams();
  params.set("type", state.type);
  if (state.search) params.set("search", state.search);
  if (state.sortBy !== "popularity") params.set("sort_by", state.sortBy);
  if (state.minRating > 0) params.set("min_rating", state.minRating);
  state.genreIds.forEach((id) => params.append("genre_ids", id));
  window.history.replaceState(null, "", `${window.location.pathname}?${params.toString()}`);
}

function syncControlsToState() {
  els.tabMovie.setAttribute("aria-selected", String(state.type === "movie"));
  els.tabTv.setAttribute("aria-selected", String(state.type === "tv"));
  els.search.value = state.search;
  els.sort.value = state.sortBy;
  els.minRatingInput.value = state.minRating;
  els.minRatingValue.textContent = state.minRating > 0 ? `${state.minRating}+` : "Any";
  els.genreGroup.querySelectorAll("input[type=checkbox]").forEach((cb) => {
    cb.checked = state.genreIds.includes(Number(cb.value));
  });
}

async function loadGenres() {
  allGenres = await apiGet("/genres");
  els.genreGroup.innerHTML = allGenres
    .map(
      (g) => `
        <label class="chip">
          <input type="checkbox" value="${g.id}" />
          ${g.name}
        </label>
      `
    )
    .join("");
  els.genreGroup.querySelectorAll("input[type=checkbox]").forEach((cb) => {
    cb.addEventListener("change", () => {
      const id = Number(cb.value);
      state.genreIds = cb.checked
        ? [...state.genreIds, id]
        : state.genreIds.filter((existing) => existing !== id);
      resetAndLoad();
    });
  });
}

function buildQueryParams() {
  return {
    search: state.search || undefined,
    sort_by: state.sortBy,
    min_rating: state.minRating > 0 ? state.minRating : undefined,
    genre_ids: state.genreIds.length ? state.genreIds : undefined,
    page: state.page,
    page_size: 24,
  };
}

async function loadPage() {
  if (isLoading) return;
  isLoading = true;
  // The spinner is explicitly shown by the infinite-scroll observer right
  // before it calls loadPage() for page > 1 (see setupInfiniteScroll) — and
  // explicitly hidden here in `finally`, always, regardless of page number.
  // Driving visibility from both ends (rather than solely from `page === 1`
  // at the top of this function) means a stale intermediate render can never
  // leave it visibly stuck.
  if (state.page === 1) renderSkeletonGrid(els.grid, 12);

  try {
    const endpoint = state.type === "tv" ? "/tv-shows" : "/movies";
    const data = await apiGet(`${endpoint}${toQueryString(buildQueryParams())}`);
    totalResults = data.total;

    if (state.page === 1) {
      renderTitleGrid(els.grid, data.items, {
        emptyMessage: "Try a different search or fewer filters.",
      });
    } else {
      const fragment = document.createDocumentFragment();
      const { createTitleCard } = await import("../components/title-card.js");
      data.items.forEach((title) => fragment.appendChild(createTitleCard(title)));
      els.grid.appendChild(fragment);
    }

    els.resultsCount.textContent = `${totalResults} result${totalResults === 1 ? "" : "s"}`;
    els.sentinel.dataset.hasNext = String(data.has_next);
  } catch (err) {
    console.error(err);
    els.resultsCount.textContent = "Couldn't load results.";
  } finally {
    isLoading = false;
    els.loadMoreSpinner.hidden = true;
  }}

function resetAndLoad() {
  state.page = 1;
  writeStateToUrl();
  loadPage();
}

function setupInfiniteScroll() {
  const observer = new IntersectionObserver(
    (entries) => {
      const entry = entries[0];
      if (entry.isIntersecting && els.sentinel.dataset.hasNext === "true" && !isLoading) {
        state.page += 1;
        els.loadMoreSpinner.hidden = false;
        loadPage();
      }
    },
    { rootMargin: "600px" }
  );
  observer.observe(els.sentinel);
}

function bindControls() {
  els.tabMovie.addEventListener("click", () => {
    state.type = "movie";
    syncControlsToState();
    resetAndLoad();
  });
  els.tabTv.addEventListener("click", () => {
    state.type = "tv";
    syncControlsToState();
    resetAndLoad();
  });

  els.search.addEventListener(
    "input",
    debounce(() => {
      state.search = els.search.value.trim();
      resetAndLoad();
    }, 350)
  );

  els.sort.addEventListener("change", () => {
    state.sortBy = els.sort.value;
    resetAndLoad();
  });

  els.minRatingInput.addEventListener("input", () => {
    state.minRating = Number(els.minRatingInput.value);
    els.minRatingValue.textContent = state.minRating > 0 ? `${state.minRating}+` : "Any";
  });
  els.minRatingInput.addEventListener("change", resetAndLoad);

  els.clearFiltersBtn.addEventListener("click", () => {
    state = { ...state, search: "", sortBy: "popularity", minRating: 0, genreIds: [] };
    syncControlsToState();
    resetAndLoad();
  });
}

async function init() {
  await renderChrome();

  els.tabMovie = document.getElementById("tab-movie");
  els.tabTv = document.getElementById("tab-tv");
  els.search = document.getElementById("search-input");
  els.sort = document.getElementById("sort-select");
  els.minRatingInput = document.getElementById("min-rating-input");
  els.minRatingValue = document.getElementById("min-rating-value");
  els.genreGroup = document.getElementById("genre-filter-group");
  els.clearFiltersBtn = document.getElementById("clear-filters-btn");
  els.grid = document.getElementById("results-grid");
  els.resultsCount = document.getElementById("results-count");
  els.sentinel = document.getElementById("load-more-sentinel");
  els.loadMoreSpinner = document.getElementById("load-more-spinner");

  readStateFromUrl();
  syncControlsToState();
  bindControls();
  setupInfiniteScroll();

  await loadGenres();
  syncControlsToState();
  await loadPage();
}

init();
