/**
 * Renders the shared site header/footer chrome into every page.
 *
 * Why JS-injected rather than duplicated markup in each HTML file: the nav
 * needs to react to auth state (Login link vs. account menu) and highlight
 * the current page — copy-pasting that logic into six HTML files would
 * mean six places to keep in sync. Each page just includes an empty
 * `<div id="site-header"></div>` / `<div id="site-footer"></div>` and calls
 * `renderChrome()`.
 */

import { getCurrentUser, isLoggedIn, logout } from "../auth.js";

const NAV_LINKS = [
  { href: "/index.html", label: "Home", match: ["/", "/index.html"] },
  { href: "/pages/browse.html?type=movie", label: "Movies", match: ["/pages/browse.html"] },
  { href: "/pages/roulette.html", label: "Roulette", match: ["/pages/roulette.html"] },
  { href: "/pages/library.html", label: "My Library", match: ["/pages/library.html"], authOnly: true },
];

function isCurrentPage(link) {
  const path = window.location.pathname;
  return link.match.some((m) => path === m || path.endsWith(m));
}

async function renderHeader() {
  const root = document.getElementById("site-header");
  if (!root) return;

  const loggedIn = isLoggedIn();
  const user = loggedIn ? await getCurrentUser() : null;

  const links = NAV_LINKS.filter((l) => !l.authOnly || loggedIn)
    .map(
      (l) =>
        `<li><a href="${l.href}"${isCurrentPage(l) ? ' aria-current="page"' : ""}>${l.label}</a></li>`
    )
    .join("");

  const actions = user
    ? `
      <span class="btn btn--ghost btn--sm" style="cursor:default;">Hi, ${escapeHtml(user.display_name || user.username)}</span>
      <button type="button" class="btn btn--secondary btn--sm" id="nav-logout">Log out</button>
    `
    : `
      <a class="btn btn--secondary btn--sm" href="/pages/auth.html">Log in</a>
      <a class="btn btn--primary btn--sm" href="/pages/auth.html?mode=register">Sign up</a>
    `;

  root.innerHTML = `
    <header class="site-header">
      <div class="site-header__brand">
        <span class="site-header__brand-mark" aria-hidden="true"></span>
        MovieRoulette
      </div>
      <nav aria-label="Primary">
        <ul class="site-header__nav">${links}</ul>
      </nav>
      <div class="site-header__actions">${actions}</div>
    </header>
  `;

  document.getElementById("nav-logout")?.addEventListener("click", () => {
    logout();
    window.location.href = "/index.html";
  });
}

function renderFooter() {
  const root = document.getElementById("site-footer");
  if (!root) return;
  root.innerHTML = `
    <footer class="site-footer">
      <div class="container">
        <span>© ${new Date().getFullYear()} MovieRoulette. Never wonder what to watch again.</span>
        <span>Built with FastAPI &amp; vanilla JS.</span>
      </div>
    </footer>
  `;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

export async function renderChrome() {
  await renderHeader();
  renderFooter();
}
