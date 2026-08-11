/**
 * Movie / TV show detail page. Media type and slug come from the URL query
 * string (?type=movie&slug=...), set by titleDetailUrl() in utils.js.
 */

import { apiGet, apiPut, apiDelete, ApiError } from "../api.js";
import { getCurrentUser, isLoggedIn } from "../auth.js";
import { renderChrome } from "../components/navbar.js";
import { createTitleCard } from "../components/title-card.js";
import { showToast } from "../components/toast.js";
import { formatRating, formatRuntime, releaseYear, resolveImageUrl } from "../utils.js";

const els = {};
let currentTitle = null;

function getParams() {
  const params = new URLSearchParams(window.location.search);
  return { type: params.get("type") === "tv" ? "tv" : "movie", slug: params.get("slug") };
}

function renderPoster(path, imgEl, fallbackEl, label) {
  const url = resolveImageUrl(path);
  if (url) {
    imgEl.src = url;
    imgEl.hidden = false;
    fallbackEl.hidden = true;
  } else {
    imgEl.hidden = true;
    fallbackEl.hidden = false;
    fallbackEl.textContent = label;
  }
}

function renderTitle(title, type) {
  currentTitle = title;
  document.getElementById("page-title").textContent = `${title.title} — MovieRoulette`;

  els.title.textContent = title.title;
  els.tagline.textContent = title.tagline || "";
  els.overview.textContent = title.overview || "No synopsis available yet.";

  const metaParts = [releaseYear(title.release_date)];
  if (type === "movie" && title.runtime_minutes) {
    metaParts.push(formatRuntime(title.runtime_minutes));
  }
  if (type === "tv" && title.number_of_seasons) {
    metaParts.push(`${title.number_of_seasons} season${title.number_of_seasons === 1 ? "" : "s"}`);
  }
  metaParts.push(`★ ${formatRating(title.vote_average)}`);
  els.meta.textContent = metaParts.join("  ·  ");

  els.genres.innerHTML = title.genres
    .map((g) => `<span class="badge">${g.name}</span>`)
    .join("");

  renderPoster(title.poster_path, els.poster, els.posterFallback, title.title);

  const backdropUrl = resolveImageUrl(title.backdrop_path);
  if (backdropUrl) {
    els.backdrop.style.backgroundImage = `url(${backdropUrl})`;
    els.backdrop.style.backgroundSize = "cover";
    els.backdrop.style.backgroundPosition = "center";
  }

  renderCast(title.credits || []);
  renderAvailability(title.availability || []);

  els.skeleton.hidden = true;
  els.content.hidden = false;
}

function renderCast(credits) {
  const castCredits = credits.filter((c) => c.department === "cast").slice(0, 12);
  if (castCredits.length === 0) {
    els.castSection.hidden = true;
    return;
  }
  els.castSection.hidden = false;
  els.castRail.innerHTML = castCredits
    .map((c) => {
      const photoUrl = resolveImageUrl(c.person.profile_path);
      const photo = photoUrl
        ? `<img class="cast-card__photo" src="${photoUrl}" alt="" loading="lazy" />`
        : `<div class="cast-card__photo-fallback">${escapeHtml(c.person.name)}</div>`;
      return `
        <div class="cast-card">
          ${photo}
          <p class="cast-card__name">${escapeHtml(c.person.name)}</p>
          ${c.character_name ? `<p class="cast-card__role">as ${escapeHtml(c.character_name)}</p>` : ""}
        </div>
      `;
    })
    .join("");
}

function renderAvailability(availability) {
  if (availability.length === 0) {
    els.availabilitySection.hidden = true;
    return;
  }
  els.availabilitySection.hidden = false;
  els.availabilityList.innerHTML = availability
    .map((a) => {
      const inner = escapeHtml(a.streaming_service.name);
      return a.watch_url
        ? `<a class="badge" href="${a.watch_url}" target="_blank" rel="noopener">${inner}</a>`
        : `<span class="badge">${inner}</span>`;
    })
    .join("");
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

async function renderSimilarTitles(type, slug) {
  try {
    const endpoint = type === "tv" ? `/tv-shows/${slug}/similar` : `/movies/${slug}/similar`;
    const similar = await apiGet(endpoint);
    if (similar.length === 0) {
      els.similarSection.hidden = true;
      return;
    }
    els.similarSection.hidden = false;
    els.similarGrid.innerHTML = "";
    const fragment = document.createDocumentFragment();
    similar.forEach((title) => fragment.appendChild(createTitleCard(title)));
    els.similarGrid.appendChild(fragment);
  } catch (err) {
    // Similar titles are a nice-to-have enhancement, not core to the page —
    // a failure here shouldn't disrupt the rest of a working detail page,
    // so it's swallowed (with a log) rather than surfaced as a toast.
    els.similarSection.hidden = true;
    console.error(err);
  }
}

function setupToggle(button, addFn, removeFn, addedMessage, removedMessage) {
  button.addEventListener("click", async () => {
    if (!isLoggedIn()) {
      window.location.href = `/pages/auth.html?next=${encodeURIComponent(window.location.pathname + window.location.search)}`;
      return;
    }
    const isPressed = button.getAttribute("aria-pressed") === "true";
    button.disabled = true;
    try {
      if (isPressed) {
        await removeFn(currentTitle.id);
        button.setAttribute("aria-pressed", "false");
        showToast(removedMessage, "info");
      } else {
        await addFn(currentTitle.id);
        button.setAttribute("aria-pressed", "true");
        showToast(addedMessage, "success");
      }
    } catch (err) {
      showToast("Something went wrong. Please try again.", "error");
      console.error(err);
    } finally {
      button.disabled = false;
    }
  });
}

function setupStarRating() {
  const wrap = els.ratingWidgetWrap;
  const container = els.starRating;
  wrap.hidden = !isLoggedIn();
  if (!isLoggedIn()) return;

  // Five stars mapped to the API's 1-10 score scale (each star = 2 points),
  // since a 10-star row reads as visual noise while 1-10 int precision on
  // the backend still allows a future half-star UI without a schema change.
  container.innerHTML = Array.from({ length: 5 })
    .map(
      (_, i) => `
        <button type="button" data-value="${(i + 1) * 2}" role="radio" aria-checked="false" aria-label="${i + 1} of 5 stars">
          <svg viewBox="0 0 20 20"><path d="M10 1l2.6 5.9 6.4.6-4.8 4.3 1.4 6.2L10 14.9 4.4 18l1.4-6.2L1 7.5l6.4-.6z"/></svg>
        </button>
      `
    )
    .join("");

  container.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const score = Number(btn.dataset.value);
      try {
        await apiPut(`/ratings/${currentTitle.id}`, { score });
        container.querySelectorAll("button").forEach((b) => {
          const filled = Number(b.dataset.value) <= score;
          b.classList.toggle("is-filled", filled);
          b.setAttribute("aria-checked", String(filled));
        });
        showToast(`Rated ${score}/10`, "success");
      } catch (err) {
        showToast("Couldn't save your rating.", "error");
        console.error(err);
      }
    });
  });
}

async function init() {
  await renderChrome();

  els.skeleton = document.getElementById("detail-skeleton");
  els.content = document.getElementById("detail-content");
  els.error = document.getElementById("detail-error");
  els.backdrop = document.getElementById("detail-backdrop");
  els.poster = document.getElementById("detail-poster");
  els.posterFallback = document.getElementById("detail-poster-fallback");
  els.title = document.getElementById("detail-title");
  els.tagline = document.getElementById("detail-tagline");
  els.meta = document.getElementById("detail-meta");
  els.genres = document.getElementById("detail-genres");
  els.overview = document.getElementById("detail-overview");
  els.castSection = document.getElementById("cast-section");
  els.castRail = document.getElementById("cast-rail");
  els.availabilitySection = document.getElementById("availability-section");
  els.availabilityList = document.getElementById("availability-list");
  els.similarSection = document.getElementById("similar-section");
  els.similarGrid = document.getElementById("similar-grid");
  els.favoriteToggle = document.getElementById("favorite-toggle");
  els.watchLaterToggle = document.getElementById("watchlater-toggle");
  els.ratingWidgetWrap = document.getElementById("rating-widget-wrap");
  els.starRating = document.getElementById("star-rating");

  const { type, slug } = getParams();
  if (!slug) {
    els.skeleton.hidden = true;
    els.error.hidden = false;
    return;
  }

  try {
    const endpoint = type === "tv" ? `/tv-shows/${slug}` : `/movies/${slug}`;
    const title = await apiGet(endpoint);
    renderTitle(title, type);

    setupToggle(
      els.favoriteToggle,
      (id) => apiPut(`/favorites/${id}`),
      (id) => apiDelete(`/favorites/${id}`),
      "Added to favorites",
      "Removed from favorites"
    );
    setupToggle(
      els.watchLaterToggle,
      (id) => apiPut(`/watch-later/${id}`),
      (id) => apiDelete(`/watch-later/${id}`),
      "Added to watch later",
      "Removed from watch later"
    );
    setupStarRating();
    renderSimilarTitles(type, slug);
  } catch (err) {
    els.skeleton.hidden = true;
    if (err instanceof ApiError && err.status === 404) {
      els.error.hidden = false;
    } else {
      showToast("Something went wrong loading this title.", "error");
      console.error(err);
    }
  }
}

init();
