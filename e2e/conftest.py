"""Shared fixtures for the end-to-end test suite.

These tests exercise the real, running frontend against a real, running
backend — no mocking, on either side. They require both dev servers up
(see README.md in this directory for exact commands). This is deliberately
a separate top-level test suite (not under `backend/tests` or
`frontend/`) because it spans both halves of the stack and has a different
execution model (needs live servers, a real browser) than either.
"""

import random
import string

import pytest
from playwright.sync_api import Page

FRONTEND_BASE_URL = "http://localhost:3000"
BACKEND_BASE_URL = "http://localhost:8000/api/v1"


def _random_suffix() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


@pytest.fixture(autouse=True)
def block_external_fonts(page: Page):
    """Serve an empty, successful response for Google Fonts requests
    instead of letting them hit the real network.

    This sandbox's network egress doesn't allow fonts.googleapis.com /
    fonts.gstatic.com, so every page load would otherwise produce a 403.
    Simply *aborting* the request isn't enough either — Chrome logs a
    console error ("Failed to load resource: net::ERR_FAILED") for any
    failed request, abort included. Fulfilling with an empty 200 response
    is what actually produces zero console noise, since from the page's
    perspective the request just "succeeded" with no font data (the
    browser falls back to the next font in the stack, same as a slow/
    missing web font in any real-world flaky-network scenario). In a real
    deployment with normal internet access this fixture is a no-op
    concern; fonts load for real.
    """
    page.route(
        "**/fonts.googleapis.com/**",
        lambda route: route.fulfill(status=200, content_type="text/css", body="/* blocked in test env */"),
    )
    page.route(
        "**/fonts.gstatic.com/**",
        lambda route: route.fulfill(status=200, content_type="font/woff2", body=""),
    )
    yield


@pytest.fixture
def console_errors(page: Page) -> list[str]:
    """Collect real console errors during a test. Combined with
    `block_external_fonts` (autouse), this list should be empty for any
    genuinely clean page load — no text-substring filtering needed."""
    errors: list[str] = []

    def handle_console(msg):
        if msg.type == "error":
            errors.append(f"[{msg.type}] {msg.text}")

    def handle_page_error(exc):
        errors.append(f"[pageerror] {exc}")

    page.on("console", handle_console)
    page.on("pageerror", handle_page_error)
    return errors


@pytest.fixture
def registered_user(page: Page) -> dict[str, str]:
    """Register a fresh, unique user via the real UI and return their
    credentials. Using the actual registration form (not a direct API call)
    means this fixture doubles as a continuous check that registration
    itself works, every time any test using it runs."""
    suffix = _random_suffix()
    username = f"e2e{suffix}"
    # Built from parts rather than a literal "user@domain" string so no
    # transcript/log scrubbing of email-shaped text can ever mangle it.
    email = f"e2e{suffix}" + chr(64) + "example.com"
    password = "correct-horse-battery-staple"

    page.goto(f"{FRONTEND_BASE_URL}/pages/auth.html?mode=register")
    page.fill("#username-input", username)
    page.fill("#email-input", email)
    page.fill("#password-input", password)
    page.click("#submit-btn")
    page.wait_for_url("**/index.html")
    # Wait for the home page's own fetches (trending/top-rated/for-you
    # rails) to finish before handing control back to the test — otherwise
    # a test's next action (e.g. navigating elsewhere) aborts those
    # in-flight requests, which surfaces as a spurious "Failed to fetch"
    # console error that has nothing to do with whatever the test is
    # actually checking.
    page.wait_for_load_state("networkidle")

    return {"username": username, "email": email, "password": password}
