/**
 * "My Library" page: favorites, watch-later, and collections, as tabs
 * within one page rather than three separate pages — these are all small,
 * closely related "things I've saved" views, and a shared tab strip keeps
 * a user from bouncing between top-level nav items to compare them.
 */

import { apiDelete, apiGet, apiPost, apiPut } from "../api.js";
import { requireAuth } from "../auth.js";
import { renderChrome } from "../components/navbar.js";
import { showToast } from "../components/toast.js";
import { createTitleCard, renderEmptyState } from "../components/title-card.js";

const els = {};
let activeTab = "favorites";
let currentCollectionId = null;

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function setActiveTab(tab) {
  activeTab = tab;
  els.tabFavorites.setAttribute("aria-selected", String(tab === "favorites"));
  els.tabWatchLater.setAttribute("aria-selected", String(tab === "watchlater"));
  els.tabCollections.setAttribute("aria-selected", String(tab === "collections"));

  els.panelFavorites.hidden = tab !== "favorites";
  els.panelWatchLater.hidden = tab !== "watchlater";
  els.panelCollections.hidden = tab !== "collections";

  const params = new URLSearchParams(window.location.search);
  params.set("tab", tab);
  window.history.replaceState(null, "", `${window.location.pathname}?${params.toString()}`);

  if (tab === "favorites") loadFavorites();
  if (tab === "watchlater") loadWatchLater();
  if (tab === "collections") loadCollectionsList();
}

async function loadFavorites() {
  els.favoritesGrid.innerHTML = "";
  try {
    const data = await apiGet("/favorites?page_size=100");
    const titles = data.items.map((item) => item.title);
    renderList(els.favoritesGrid, titles, "You haven't favorited anything yet.", async (id) => {
      await apiDelete(`/favorites/${id}`);
      showToast("Removed from favorites", "info");
      loadFavorites();
    });
  } catch (err) {
    console.error(err);
    showToast("Couldn't load your favorites.", "error");
  }
}

async function loadWatchLater() {
  els.watchLaterGrid.innerHTML = "";
  try {
    const data = await apiGet("/watch-later?page_size=100");
    const titles = data.items.map((item) => item.title);
    renderList(els.watchLaterGrid, titles, "Your watch-later list is empty.", async (id) => {
      await apiDelete(`/watch-later/${id}`);
      showToast("Removed from watch later", "info");
      loadWatchLater();
    });
  } catch (err) {
    console.error(err);
    showToast("Couldn't load your watch-later list.", "error");
  }
}

function renderList(container, titles, emptyMessage, onRemove) {
  container.innerHTML = "";
  if (titles.length === 0) {
    container.appendChild(renderEmptyState(emptyMessage));
    return;
  }
  const fragment = document.createDocumentFragment();
  titles.forEach((title) =>
    fragment.appendChild(createTitleCard(title, { showRemove: true, onRemove }))
  );
  container.appendChild(fragment);
}

async function loadCollectionsList() {
  els.collectionDetailView.hidden = true;
  els.collectionsListView.hidden = false;
  els.collectionsGrid.innerHTML = "";

  try {
    const data = await apiGet("/collections?page_size=100");
    if (data.items.length === 0) {
      els.collectionsGrid.appendChild(renderEmptyState("Create your first collection to start curating."));
      return;
    }
    const fragment = document.createDocumentFragment();
    data.items.forEach((collection) => {
      const card = document.createElement("button");
      card.type = "button";
      card.className = "collection-card";
      card.innerHTML = `
        <h3>${escapeHtml(collection.name)}</h3>
        <p>${collection.description ? escapeHtml(collection.description) : "No description"}</p>
      `;
      card.addEventListener("click", () => openCollection(collection.id));
      fragment.appendChild(card);
    });
    els.collectionsGrid.appendChild(fragment);
  } catch (err) {
    console.error(err);
    showToast("Couldn't load your collections.", "error");
  }
}

async function openCollection(collectionId) {
  currentCollectionId = collectionId;
  els.collectionsListView.hidden = true;
  els.collectionDetailView.hidden = false;
  els.collectionItemsGrid.innerHTML = "";

  try {
    const collection = await apiGet(`/collections/${collectionId}`);
    els.collectionDetailName.textContent = collection.name;
    els.collectionDetailDescription.textContent = collection.description || "";
    const titles = collection.items.map((item) => item.title);
    renderList(els.collectionItemsGrid, titles, "This collection is empty. Add titles from any detail page.", async (titleId) => {
      await apiDelete(`/collections/${collectionId}/items/${titleId}`);
      showToast("Removed from collection", "info");
      openCollection(collectionId);
    });
  } catch (err) {
    console.error(err);
    showToast("Couldn't load that collection.", "error");
    loadCollectionsList();
  }
}

function bindCollectionsUi() {
  els.newCollectionBtn.addEventListener("click", () => {
    els.newCollectionForm.reset();
    els.newCollectionDialog.showModal();
  });
  els.cancelNewCollectionBtn.addEventListener("click", () => els.newCollectionDialog.close());

  els.newCollectionForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = document.getElementById("collection-name-input").value.trim();
    const description = document.getElementById("collection-description-input").value.trim();
    if (!name) return;

    try {
      await apiPost("/collections", { name, description: description || null });
      els.newCollectionDialog.close();
      showToast("Collection created", "success");
      loadCollectionsList();
    } catch (err) {
      console.error(err);
      showToast("Couldn't create the collection.", "error");
    }
  });

  els.backToCollectionsBtn.addEventListener("click", loadCollectionsList);

  els.deleteCollectionBtn.addEventListener("click", async () => {
    if (currentCollectionId === null) return;
    if (!window.confirm("Delete this collection? This can't be undone.")) return;
    try {
      await apiDelete(`/collections/${currentCollectionId}`);
      showToast("Collection deleted", "info");
      loadCollectionsList();
    } catch (err) {
      console.error(err);
      showToast("Couldn't delete the collection.", "error");
    }
  });
}

async function init() {
  if (!requireAuth()) return;

  await renderChrome();

  els.tabFavorites = document.getElementById("tab-favorites");
  els.tabWatchLater = document.getElementById("tab-watchlater");
  els.tabCollections = document.getElementById("tab-collections");
  els.panelFavorites = document.getElementById("panel-favorites");
  els.panelWatchLater = document.getElementById("panel-watchlater");
  els.panelCollections = document.getElementById("panel-collections");
  els.favoritesGrid = document.getElementById("favorites-grid");
  els.watchLaterGrid = document.getElementById("watchlater-grid");
  els.collectionsGrid = document.getElementById("collections-grid");
  els.collectionsListView = document.getElementById("collections-list-view");
  els.collectionDetailView = document.getElementById("collection-detail-view");
  els.collectionDetailName = document.getElementById("collection-detail-name");
  els.collectionDetailDescription = document.getElementById("collection-detail-description");
  els.collectionItemsGrid = document.getElementById("collection-items-grid");
  els.newCollectionBtn = document.getElementById("new-collection-btn");
  els.newCollectionDialog = document.getElementById("new-collection-dialog");
  els.newCollectionForm = document.getElementById("new-collection-form");
  els.cancelNewCollectionBtn = document.getElementById("cancel-new-collection-btn");
  els.backToCollectionsBtn = document.getElementById("back-to-collections-btn");
  els.deleteCollectionBtn = document.getElementById("delete-collection-btn");

  els.tabFavorites.addEventListener("click", () => setActiveTab("favorites"));
  els.tabWatchLater.addEventListener("click", () => setActiveTab("watchlater"));
  els.tabCollections.addEventListener("click", () => setActiveTab("collections"));

  bindCollectionsUi();

  const params = new URLSearchParams(window.location.search);
  const initialTab = params.get("tab");
  setActiveTab(["favorites", "watchlater", "collections"].includes(initialTab) ? initialTab : "favorites");
}

init();
