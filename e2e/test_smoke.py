"""Every page loads cleanly: no console errors, no page errors, and the
expected root content is present. This is the automated replacement for the
ad-hoc Playwright scripts used during interactive development of the
frontend phase.
"""

import pytest

from conftest import FRONTEND_BASE_URL

PAGES = [
    ("home", "/index.html"),
    ("browse_movies", "/pages/browse.html?type=movie"),
    ("browse_tv", "/pages/browse.html?type=tv"),
    ("roulette", "/pages/roulette.html"),
    ("auth_login", "/pages/auth.html"),
    ("auth_register", "/pages/auth.html?mode=register"),
]


@pytest.mark.parametrize("name,path", PAGES, ids=[p[0] for p in PAGES])
def test_page_loads_without_errors(page, console_errors, name, path):
    page.goto(f"{FRONTEND_BASE_URL}{path}", wait_until="networkidle")
    page.wait_for_timeout(400)
    assert console_errors == [], f"{name} produced console errors: {console_errors}"


def test_home_page_has_expected_headline(page, console_errors):
    page.goto(f"{FRONTEND_BASE_URL}/index.html", wait_until="networkidle")
    assert page.locator("h1").inner_text() == "Stop scrolling.\nStart watching."
    assert console_errors == []


def test_home_page_rails_render_seeded_titles(page, console_errors):
    page.goto(f"{FRONTEND_BASE_URL}/index.html", wait_until="networkidle")
    page.wait_for_selector("#trending-movies-rail .title-card", timeout=5000)
    cards = page.locator("#trending-movies-rail .title-card")
    assert cards.count() >= 1
    assert console_errors == []


def test_browse_page_shows_results_count(page, console_errors):
    page.goto(f"{FRONTEND_BASE_URL}/pages/browse.html?type=movie", wait_until="networkidle")
    page.wait_for_timeout(400)
    results_text = page.locator("#results-count").inner_text()
    assert "result" in results_text
    assert console_errors == []


def test_title_detail_page_loads_seeded_movie(page, console_errors):
    page.goto(
        f"{FRONTEND_BASE_URL}/pages/title.html?type=movie&slug=the-last-signal-2019",
        wait_until="networkidle",
    )
    page.wait_for_timeout(400)
    assert page.locator("#detail-title").inner_text() == "The Last Signal"
    assert console_errors == []


def test_title_detail_page_shows_error_state_for_unknown_slug(page, console_errors):
    page.goto(
        f"{FRONTEND_BASE_URL}/pages/title.html?type=movie&slug=does-not-exist",
        wait_until="networkidle",
    )
    page.wait_for_timeout(400)
    assert page.locator("#detail-error").is_visible()
    # Deliberately not asserting `console_errors == []` here: a 404 response
    # from a request the app *correctly* expects to fail (this slug doesn't
    # exist, on purpose) is still logged by the browser itself as a
    # "Failed to load resource" console entry — that's an unavoidable
    # Chrome behavior for any non-2xx fetch response, not a sign of broken
    # error handling. What actually matters, and what's asserted above, is
    # that the app catches it and renders the error state correctly.


def test_roulette_page_has_spin_button(page, console_errors):
    page.goto(f"{FRONTEND_BASE_URL}/pages/roulette.html", wait_until="networkidle")
    assert page.locator("#spin-button").is_visible()
    assert console_errors == []
