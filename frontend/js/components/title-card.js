/**
 * Renders a single title card — the atomic unit of every browse grid, rail,
 * and library list in the app. One function, reused everywhere a title
 * needs to appear as a clickable poster, so a future visual tweak (e.g.
 * adding a "watched" checkmark) happens in one place.
 */

import { formatRating, releaseYear, resolveImageUrl, titleDetailUrl } from "../utils.js";

/**
 * @param {object} title - a TitleSummary from the API
 * @param {object} [options]
 * @param {boolean} [options.showRemove] - show a "remove" button instead of nothing extra
 * @param {(titleId: number) => void} [options.onRemove]
 */
export function createTitleCard(title, options = {}) {
  const card = document.createElement("a");
  card.className = "title-card";
  card.href = titleDetailUrl(title);

  const posterUrl = resolveImageUrl(title.poster_path);

  const posterWrap = document.createElement("div");
  posterWrap.className = "title-card__poster-wrap";

  if (posterUrl) {
    const img = document.createElement("img");
    img.className = "title-card__poster";
    img.src = posterUrl;
    img.alt = "";
    img.loading = "lazy";
    posterWrap.appendChild(img);
  } else {
    const fallback = document.createElement("div");
    fallback.className = "title-card__poster-fallback";
    fallback.textContent = title.title;
    posterWrap.appendChild(fallback);
  }

  if (title.vote_average) {
    const ratingBadge = document.createElement("span");
    const isLow = title.vote_average < 5;
    ratingBadge.className = `badge badge--rating title-card__rating${isLow ? " badge--low" : ""}`;
    ratingBadge.textContent = `★ ${formatRating(title.vote_average)}`;
    posterWrap.appendChild(ratingBadge);
  }

  card.appendChild(posterWrap);

  const body = document.createElement("div");
  body.className = "title-card__body";

  const heading = document.createElement("p");
  heading.className = "title-card__title";
  heading.textContent = title.title;
  body.appendChild(heading);

  const meta = document.createElement("p");
  meta.className = "title-card__meta";
  meta.textContent = releaseYear(title.release_date);
  body.appendChild(meta);

  card.appendChild(body);

  if (options.showRemove) {
    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "btn btn--ghost btn--sm";
    removeBtn.textContent = "Remove";
    removeBtn.style.width = "100%";
    removeBtn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      options.onRemove?.(title.id);
    });
    body.appendChild(removeBtn);
  }

  return card;
}

/** A placeholder card shown while a grid's data is loading. */
export function createSkeletonCard() {
  const card = document.createElement("div");
  card.className = "skeleton-card";
  card.innerHTML = `
    <div class="skeleton skeleton-card__poster"></div>
    <div class="skeleton skeleton-card__line" style="width: 85%"></div>
    <div class="skeleton skeleton-card__line" style="width: 40%"></div>
  `;
  return card;
}

/** Render a grid of title cards into `container`, replacing its contents. */
export function renderTitleGrid(container, titles, options = {}) {
  container.innerHTML = "";
  if (titles.length === 0) {
    container.appendChild(renderEmptyState(options.emptyMessage || "Nothing here yet."));
    return;
  }
  const fragment = document.createDocumentFragment();
  titles.forEach((title) => fragment.appendChild(createTitleCard(title, options)));
  container.appendChild(fragment);
}

export function renderSkeletonGrid(container, count = 12) {
  container.innerHTML = "";
  const fragment = document.createDocumentFragment();
  for (let i = 0; i < count; i++) fragment.appendChild(createSkeletonCard());
  container.appendChild(fragment);
}

export function renderEmptyState(message, icon = "🎬") {
  const wrap = document.createElement("div");
  wrap.className = "empty-state";
  wrap.innerHTML = `
    <div class="empty-state__icon" aria-hidden="true">${icon}</div>
    <h3>Nothing to show</h3>
    <p>${message}</p>
  `;
  return wrap;
}
