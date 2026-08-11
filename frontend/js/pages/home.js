/**
 * Home page: renders the shared chrome, then populates three rails
 * (trending movies, top-rated movies, popular TV) from the browse API.
 */

import { apiGet, toQueryString } from "../api.js";
import { isLoggedIn } from "../auth.js";
import { renderChrome } from "../components/navbar.js";
import { renderSkeletonGrid, renderTitleGrid } from "../components/title-card.js";

async function loadRail(containerId, path, params) {
  const container = document.getElementById(containerId);
  renderSkeletonGrid(container, 6);
  try {
    const data = await apiGet(`${path}${toQueryString(params)}`);
    renderTitleGrid(container, data.items, {
      emptyMessage: "No titles here yet — check back once the catalog is populated.",
    });
  } catch (err) {
    container.innerHTML = "";
    container.appendChild(
      Object.assign(document.createElement("p"), {
        className: "empty-state",
        textContent: "Couldn't load this right now. Try refreshing.",
      })
    );
    console.error(err);
  }
}

async function loadForYouRail() {
  if (!isLoggedIn()) return;

  const section = document.getElementById("for-you-section");
  const container = document.getElementById("for-you-rail");

  try {
    const recommendations = await apiGet("/recommendations/for-you?limit=12");
    if (recommendations.length === 0) return;
    section.hidden = false;
    renderTitleGrid(container, recommendations);
  } catch (err) {
    // Personalized recommendations are an enhancement on top of the
    // always-available rails below — a failure here just means the
    // section stays hidden, not a broken homepage.
    console.error(err);
  }
}

async function init() {
  await renderChrome();

  await Promise.all([
    loadForYouRail(),
    loadRail("trending-movies-rail", "/movies", { sort_by: "popularity", page_size: 12 }),
    loadRail("top-rated-movies-rail", "/movies", { sort_by: "rating", page_size: 12 }),
    loadRail("popular-tv-rail", "/tv-shows", { sort_by: "popularity", page_size: 12 }),
  ]);
}

init();
