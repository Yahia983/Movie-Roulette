# Frontend Guide

## Stack and constraints

Vanilla HTML5/CSS3/ES6 modules, no build step, no framework — per the
project spec. Six pages share one design system and a small set of JS
modules; there is no client-side router, since each page is a real,
separately-served HTML file (`index.html` + `pages/*.html`).

## File layout

```
frontend/
├── css/
│   ├── variables.css   — design tokens (color, type, spacing, motion)
│   ├── base.css        — reset + global element styles
│   ├── layout.css       — header/footer/rails/grid structural patterns
│   ├── components.css   — buttons, cards, forms, badges, toasts, skeletons
│   └── roulette.css     — the roulette page's reel/spin/confetti mechanics
├── js/
│   ├── api.js            — the one HTTP chokepoint (see below)
│   ├── auth.js            — session logic (login/register/logout/current user)
│   ├── auth-storage.js    — token persistence, split out to avoid a circular import
│   ├── utils.js            — formatting/debounce helpers
│   ├── components/
│   │   ├── navbar.js        — shared header/footer, injected into every page
│   │   ├── title-card.js     — the one place a "title card" is rendered
│   │   ├── toast.js           — notification system
│   │   └── confetti.js         — the roulette payoff effect
│   └── pages/               — one file per page, each page's own `init()`
└── index.html, pages/*.html
```

## Why a few things were built the way they were

**Everything HTTP-related funnels through `api.js`.** Every page needs
consistent base-URL resolution, JSON handling, and — once a user is logged
in — an auth header and silent access-token refresh on a 401. Concurrent
401s are deduplicated (`refreshInFlight`) so several requests firing at once
trigger exactly one refresh call, not one each.

**The navbar is JS-injected, not copy-pasted HTML.** It needs to react to
auth state (Login/Sign up vs. the user's name + Log out) and highlight the
current page. Six copies of that logic would be six places to keep in sync;
instead every page just has an empty `<div id="site-header">` and calls
`renderChrome()`.

**Browse page state lives in the URL**, not just in memory — `state` is
read from `location.search` on load and written back via
`history.replaceState` on every filter change. This makes a filtered view
shareable and survives a refresh, and it's why `browse.js` reads more like
a small state machine than an event-handler grab-bag.

**The roulette reel animates a reveal, not a live randomizer.** The backend
picks the winner in one API call; the frontend's job is to make that
selection feel exciting, not to simulate randomness client-side. The reel
is filled with generic placeholder cards and the real winning card is
appended at a fixed position, then a CSS transition (`cubic-bezier` ease
matching the brief's "ease in, ease out") carries the strip from a far-right
starting offset to center. Confetti fires only after the transition
settles, and respects `prefers-reduced-motion` (fires almost instantly, no
particles).

**Favorite/watch-later state isn't pre-checked from the API on page load.**
The backend doesn't expose a "is title X favorited by me" lookup for a
single title — only a paginated list of all of a user's favorites — so
checking status on every detail-page view would mean fetching that whole
list just to answer one boolean. The toggle buttons are optimistic instead:
they always start unpressed and update immediately on click. A follow-up
backend endpoint (`GET /favorites/{title_id}/status` or similar) would let
detail pages show correct initial state; noted here rather than worked
around with an expensive client-side scan.

## Real bugs found via browser testing (and their fixes)

These were caught by actually loading pages in Playwright and clicking
through flows — not by reading the code — which is why they're documented:

- **`[hidden]` silently did nothing on `<img>`/`<svg>` elements.** The CSS
  cascade always lets an author-origin rule (`img, svg { display: block }`
  in `base.css`) override a user-agent rule (`[hidden] { display: none }`),
  *regardless of specificity* — author beats UA unconditionally for normal
  declarations. Fixed with an explicit `[hidden] { display: none !important; }`
  rule. Any future component that toggles `.hidden` on an image or SVG
  depends on this.
- **Grid auto-placement scrambled the title-detail hero layout.** The
  poster `<img>` and its text fallback `<div>` were separate direct
  children of a 2-column grid alongside the info block — 3 children into 2
  columns auto-wraps the 3rd into column 1 of a new row, squeezing the
  title/metadata into the 220px poster column. Fixed by wrapping the
  poster + fallback in one container so the grid only ever sees 2 children.
- **Empty-state text was left-aligned despite `text-align: center`.** A
  global `p { max-width: 70ch }` rule caps a paragraph's box width without
  centering the box itself — `text-align` only centers *text inside* a box.
  Fixed with `margin-left/right: auto` scoped to `.empty-state p`.
- **A tab strip's styles only existed on one page.** `.browse-tabs`/
  `.browse-tab` were defined in `browse.html`'s inline `<style>`, so
  `library.html`, which reuses the same class names for its own tab strip,
  rendered unstyled default buttons. Moved into shared `components.css`.

## Known gaps going into the next phase

- No real poster/backdrop images yet — `resolveImageUrl()` in `utils.js` is
  the single place a real image CDN base gets wired in once one exists;
  every card/detail page already has a text fallback in the meantime.
- No pre-check of favorite/watch-later status on page load (see above).
- No automated test suite for the frontend (Playwright was used
  interactively for verification during development, not wired into CI).
