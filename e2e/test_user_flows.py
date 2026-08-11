"""End-to-end user flows: the actual paths a person takes through the app,
each exercising both frontend and backend together. These are slower and
more expensive than a unit test — that trade-off is deliberate here, since
this is exactly the layer that catches integration bugs neither side's own
test suite can (see docs/FRONTEND.md and docs/FEATURES.md for examples of
bugs specifically caught this way during development).
"""

from conftest import FRONTEND_BASE_URL


def test_register_login_logout_cycle(page, console_errors, registered_user):
    # registered_user fixture already completed register + login and landed
    # on the home page — verify the logged-in state is reflected in the nav.
    page.wait_for_selector("#site-header:has-text('" + registered_user["username"] + "')")
    assert registered_user["username"] in page.locator("#site-header").inner_text()

    page.click("#nav-logout")
    page.wait_for_url("**/index.html")
    page.wait_for_timeout(300)
    assert "Log in" in page.locator("#site-header").inner_text()
    assert console_errors == []


def test_login_with_wrong_password_shows_error(page, console_errors, registered_user):
    page.click("#nav-logout")
    page.wait_for_url("**/index.html")

    page.goto(f"{FRONTEND_BASE_URL}/pages/auth.html", wait_until="networkidle")
    page.fill("#identifier-input", registered_user["username"])
    page.fill("#password-input", "definitely-the-wrong-password")
    page.click("#submit-btn")
    page.wait_for_timeout(500)

    assert page.locator("#form-error").is_visible()
    assert page.url.endswith("/pages/auth.html")


def test_favorite_and_watch_later_toggle_from_detail_page(page, console_errors, registered_user):
    page.goto(
        f"{FRONTEND_BASE_URL}/pages/title.html?type=movie&slug=the-last-signal-2019",
        wait_until="networkidle",
    )
    page.wait_for_timeout(400)

    favorite_btn = page.locator("#favorite-toggle")
    assert favorite_btn.get_attribute("aria-pressed") == "false"
    favorite_btn.click()
    page.wait_for_timeout(400)
    assert favorite_btn.get_attribute("aria-pressed") == "true"

    watch_later_btn = page.locator("#watchlater-toggle")
    watch_later_btn.click()
    page.wait_for_timeout(400)
    assert watch_later_btn.get_attribute("aria-pressed") == "true"

    # Confirm it actually shows up in the library, not just the button state.
    page.goto(f"{FRONTEND_BASE_URL}/pages/library.html?tab=favorites", wait_until="networkidle")
    page.wait_for_timeout(400)
    assert page.locator(".title-card", has_text="The Last Signal").is_visible()
    assert console_errors == []


def test_rating_a_title_updates_star_display(page, console_errors, registered_user):
    page.goto(
        f"{FRONTEND_BASE_URL}/pages/title.html?type=movie&slug=the-last-signal-2019",
        wait_until="networkidle",
    )
    page.wait_for_timeout(400)

    page.click('#star-rating button[data-value="8"]')
    page.wait_for_timeout(400)

    filled_stars = page.locator("#star-rating button.is-filled")
    assert filled_stars.count() == 4  # 8/10 -> 4 of 5 stars, per the 2-points-per-star mapping
    assert console_errors == []


def test_create_collection_and_view_it(page, console_errors, registered_user):
    page.goto(f"{FRONTEND_BASE_URL}/pages/library.html?tab=collections", wait_until="networkidle")
    page.wait_for_timeout(400)

    page.click("#new-collection-btn")
    page.fill("#collection-name-input", "E2E Test Collection")
    page.click('#new-collection-form button[type="submit"]')
    page.wait_for_timeout(500)

    assert page.locator(".collection-card", has_text="E2E Test Collection").is_visible()
    assert console_errors == []


def test_roulette_spin_reveals_a_result(page, console_errors):
    page.goto(f"{FRONTEND_BASE_URL}/pages/roulette.html", wait_until="networkidle")
    page.wait_for_timeout(300)

    page.click("#spin-button")
    # The spin animation takes ~3.2s (see roulette.css); give it real time
    # to settle rather than racing it, since the result only renders after.
    page.wait_for_selector("#roulette-result.is-visible", timeout=6000)

    assert page.locator("#result-title").inner_text() != ""
    assert console_errors == []


def test_roulette_spin_works_when_logged_out(page, console_errors):
    """The roulette engine must be usable with no account — this is called
    out explicitly in the product spec ("no signup wall")."""
    page.goto(f"{FRONTEND_BASE_URL}/pages/roulette.html", wait_until="networkidle")
    assert "Log in" in page.locator("#site-header").inner_text()

    page.click("#spin-button")
    page.wait_for_selector("#roulette-result.is-visible", timeout=6000)
    assert page.locator("#result-title").inner_text() != ""
    assert console_errors == []


def test_browse_search_filters_results(page, console_errors):
    page.goto(f"{FRONTEND_BASE_URL}/pages/browse.html?type=movie", wait_until="networkidle")
    page.wait_for_timeout(400)

    page.fill("#search-input", "zzzz-no-such-movie-zzzz")
    page.wait_for_timeout(600)  # search is debounced 350ms client-side

    assert "0 results" in page.locator("#results-count").inner_text()
    assert page.locator(".empty-state").is_visible()
    assert console_errors == []


def test_protected_page_redirects_to_login_when_logged_out(page, console_errors):
    page.goto(f"{FRONTEND_BASE_URL}/pages/library.html", wait_until="networkidle")
    page.wait_for_url("**/pages/auth.html*")
    assert "auth.html" in page.url
