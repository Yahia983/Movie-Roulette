/**
 * The roulette engine page — the app's signature interaction.
 *
 * Visual mechanic: a strip of "mystery" cards races past a fixed center
 * marker and decelerates onto the real winning card (returned by the
 * backend's single spin call), then confetti fires. The backend picks the
 * winner up front — the animation is a reveal, not a live randomizer — so
 * the reel's filler cards are generic placeholders and only the final card
 * carries real data.
 */

import { apiGet, apiPost, apiPut, toQueryString } from "../api.js";
import { isLoggedIn } from "../auth.js";
import { fireConfetti } from "../components/confetti.js";
import { renderChrome } from "../components/navbar.js";
import { showToast } from "../components/toast.js";
import { formatRating, releaseYear, resolveImageUrl, titleDetailUrl } from "../utils.js";

const FILLER_CARD_COUNT = 22;
const CARD_WIDTH = 160;
const CARD_GAP = 16; // must match --space-sm used as the reel's gap

const PRESETS = [
  { label: "🎲 Everything", filters: {} },
  { label: "💎 Hidden Gems", filters: { hidden_gems: true } },
  { label: "🏆 Oscar Winners", filters: { oscar_winners: true } },
  { label: "⚡ Quick Watch", filters: { max_runtime_minutes: 90 } },
  { label: "🎭 Comedy", genreName: "Comedy" },
  { label: "💥 Action", genreName: "Action" },
  { label: "🚀 Science Fiction", genreName: "Science Fiction" },
  { label: "📽️ Documentaries", genreName: "Documentary" },
];

const els = {};
let allGenres = [];
let isSpinning = false;

function currentFilters() {
  const mediaType = document.querySelector('input[name="media-type"]:checked')?.value || null;
  const genreIds = [...els.genreGroup.querySelectorAll("input:checked")].map((cb) => Number(cb.value));
  const minRating = Number(els.minRating.value);
  const maxRuntime = Number(els.maxRuntime.value);
  const decade = els.decade.value ? Number(els.decade.value) : null;

  return {
    media_type: mediaType || undefined,
    genre_ids: genreIds.length ? genreIds : undefined,
    min_rating: minRating > 0 ? minRating : undefined,
    max_runtime_minutes: maxRuntime < 240 ? maxRuntime : undefined,
    decade: decade || undefined,
    hidden_gems: els.hiddenGemsActive || undefined,
    oscar_winners: els.oscarWinnersActive || undefined,
  };
}

async function loadGenres() {
  allGenres = await apiGet("/genres");
  els.genreGroup.innerHTML = allGenres
    .map((g) => `<label class="chip"><input type="checkbox" value="${g.id}" /> ${g.name}</label>`)
    .join("");
}

function applyPreset(preset) {
  // Reset toggle-only state each time so presets don't stack unexpectedly.
  els.hiddenGemsActive = false;
  els.oscarWinnersActive = false;
  els.genreGroup.querySelectorAll("input").forEach((cb) => (cb.checked = false));
  els.maxRuntime.value = 240;
  els.maxRuntimeValue.textContent = "Any";

  if (preset.filters?.hidden_gems) els.hiddenGemsActive = true;
  if (preset.filters?.oscar_winners) els.oscarWinnersActive = true;
  if (preset.filters?.max_runtime_minutes) {
    els.maxRuntime.value = preset.filters.max_runtime_minutes;
    els.maxRuntimeValue.textContent = `${preset.filters.max_runtime_minutes}m`;
  }
  if (preset.genreName) {
    const genre = allGenres.find((g) => g.name.toLowerCase() === preset.genreName.toLowerCase());
    if (genre) {
      const cb = els.genreGroup.querySelector(`input[value="${genre.id}"]`);
      if (cb) cb.checked = true;
    }
  }
}

function renderPresets() {
  els.presetRow.innerHTML = PRESETS.map((p, i) => `<button type="button" class="chip" data-preset="${i}">${p.label}</button>`).join("");
  els.presetRow.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => applyPreset(PRESETS[Number(btn.dataset.preset)]));
  });
}

function buildFillerCard() {
  const card = document.createElement("div");
  card.className = "roulette-reel__card";
  card.style.background =
    "linear-gradient(135deg, var(--color-card), var(--color-bg-secondary))";
  card.style.display = "flex";
  card.style.alignItems = "center";
  card.style.justifyContent = "center";
  card.style.fontSize = "2rem";
  card.textContent = "🎬";
  return card;
}

function buildWinnerCard(title) {
  const card = document.createElement("div");
  card.className = "roulette-reel__card roulette-reel__card--winner";
  const posterUrl = resolveImageUrl(title.poster_path);
  if (posterUrl) {
    const img = document.createElement("img");
    img.src = posterUrl;
    img.alt = "";
    card.appendChild(img);
  } else {
    card.style.display = "flex";
    card.style.alignItems = "center";
    card.style.justifyContent = "center";
    card.style.padding = "0.75rem";
    card.style.textAlign = "center";
    card.style.fontWeight = "700";
    card.style.fontSize = "var(--font-size-sm)";
    card.textContent = title.title;
  }
  return card;
}

async function spin() {
  if (isSpinning) return;

  const filters = currentFilters();
  isSpinning = true;
  els.spinButton.disabled = true;
  els.result.classList.remove("is-visible");

  let response;
  try {
    response = await apiPost("/roulette/spin", { filters }, { auth: isLoggedIn() });
  } catch (err) {
    showToast("Couldn't spin the roulette. Please try again.", "error");
    console.error(err);
    isSpinning = false;
    els.spinButton.disabled = false;
    return;
  }

  els.candidateCount.textContent = `${response.candidate_count} title${response.candidate_count === 1 ? "" : "s"} matched your filters`;

  if (!response.result) {
    showToast("Nothing matched those filters — try loosening them up.", "info");
    isSpinning = false;
    els.spinButton.disabled = false;
    return;
  }

  await runReelAnimation(response.result);
  showResult(response.result);
  fireConfetti();

  isSpinning = false;
  els.spinButton.disabled = false;
}

function runReelAnimation(winner) {
  return new Promise((resolve) => {
    const reel = els.reel;
    reel.classList.remove("is-spinning");
    reel.style.transition = "none";
    reel.innerHTML = "";

    const fragment = document.createDocumentFragment();
    for (let i = 0; i < FILLER_CARD_COUNT; i++) fragment.appendChild(buildFillerCard());
    const winnerCard = buildWinnerCard(winner);
    fragment.appendChild(winnerCard);
    // A few trailing filler cards so the strip doesn't visibly end right
    // after the winner while it's still decelerating past center.
    for (let i = 0; i < 4; i++) fragment.appendChild(buildFillerCard());
    reel.appendChild(fragment);

    // Start scrolled far to the right of center, so the spin has real
    // distance to cover before decelerating onto the winner.
    const startOffset = (FILLER_CARD_COUNT - 2) * (CARD_WIDTH + CARD_GAP);
    reel.style.transform = `translate(calc(-50% + ${startOffset}px), -50%)`;

    // Force layout so the transform above actually applies before we
    // animate away from it on the next frame.
    // eslint-disable-next-line no-unused-expressions
    reel.offsetHeight;

    requestAnimationFrame(() => {
      reel.classList.add("is-spinning");
      reel.style.transform = "translate(-50%, -50%)";
    });

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.setTimeout(resolve, reducedMotion ? 450 : 3300);
  });
}

function showResult(title) {
  const posterUrl = resolveImageUrl(title.poster_path);
  els.resultPoster.src = posterUrl || "";
  els.resultPoster.style.display = posterUrl ? "block" : "none";
  els.resultTitle.textContent = title.title;
  els.resultMeta.textContent = `${title.media_type === "tv_show" ? "TV Show" : "Movie"}  ·  ${releaseYear(title.release_date)}  ·  ★ ${formatRating(title.vote_average)}`;
  els.resultOverview.textContent = "";
  els.resultGenres.innerHTML = title.genres.map((g) => `<span class="badge">${g.name}</span>`).join("");
  els.resultViewBtn.href = titleDetailUrl(title);
  els.result.classList.add("is-visible");
  els.result.dataset.titleId = title.id;
  els.result.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function bindControls() {
  els.spinButton.addEventListener("click", spin);
  els.spinAgainBtn.addEventListener("click", spin);

  els.minRating.addEventListener("input", () => {
    els.minRatingValue.textContent = Number(els.minRating.value) > 0 ? `${els.minRating.value}+` : "Any";
  });
  els.maxRuntime.addEventListener("input", () => {
    els.maxRuntimeValue.textContent = Number(els.maxRuntime.value) < 240 ? `${els.maxRuntime.value}m` : "Any";
  });

  els.resultWatchLaterBtn.addEventListener("click", async () => {
    if (!isLoggedIn()) {
      window.location.href = "/pages/auth.html?next=/pages/roulette.html";
      return;
    }
    try {
      await apiPut(`/watch-later/${els.result.dataset.titleId}`);
      showToast("Added to watch later", "success");
    } catch (err) {
      showToast("Couldn't add to watch later.", "error");
      console.error(err);
    }
  });
}

async function init() {
  await renderChrome();

  els.presetRow = document.getElementById("preset-row");
  els.genreGroup = document.getElementById("roulette-genre-group");
  els.minRating = document.getElementById("roulette-min-rating");
  els.minRatingValue = document.getElementById("roulette-rating-value");
  els.maxRuntime = document.getElementById("roulette-max-runtime");
  els.maxRuntimeValue = document.getElementById("roulette-runtime-value");
  els.decade = document.getElementById("roulette-decade");
  els.reel = document.getElementById("reel");
  els.spinButton = document.getElementById("spin-button");
  els.candidateCount = document.getElementById("candidate-count");
  els.result = document.getElementById("roulette-result");
  els.resultPoster = document.getElementById("result-poster");
  els.resultTitle = document.getElementById("result-title");
  els.resultMeta = document.getElementById("result-meta");
  els.resultOverview = document.getElementById("result-overview");
  els.resultGenres = document.getElementById("result-genres");
  els.resultViewBtn = document.getElementById("result-view-btn");
  els.resultWatchLaterBtn = document.getElementById("result-watchlater-btn");
  els.spinAgainBtn = document.getElementById("spin-again-btn");
  els.hiddenGemsActive = false;
  els.oscarWinnersActive = false;

  renderPresets();
  bindControls();

  // Fill the reel with placeholder cards at rest so the wheel doesn't look
  // empty before the first spin.
  const fragment = document.createDocumentFragment();
  for (let i = 0; i < FILLER_CARD_COUNT; i++) fragment.appendChild(buildFillerCard());
  els.reel.appendChild(fragment);

  await loadGenres();
}

init();
