# End-to-end tests

Real browser tests against the real frontend and real backend — no mocking
on either side. This is what verifies the two halves of the stack actually
work together, which neither `backend/tests` (mocks nothing but never
touches a browser) nor manual testing (works, but isn't repeatable/CI-safe)
can do on its own.

## Setup

```bash
cd e2e
pip install -r requirements.txt
playwright install chromium
```

## Running

Both servers must be running first:

```bash
# Terminal 1 — backend
cd backend && uvicorn app.main:app --port 8000

# Terminal 2 — frontend
cd frontend && python -m http.server 3000

# Terminal 3 — the tests themselves
cd e2e && pytest
```

Run a single file or test:

```bash
pytest test_user_flows.py
pytest test_user_flows.py::test_roulette_spin_reveals_a_result
```

## What's covered

- `test_smoke.py` — every page loads with a clean browser console
- `test_user_flows.py` — real user journeys: register/login/logout,
  favoriting, rating, collections, the roulette spin (both logged-in and
  anonymous), search filtering, auth-gated redirects
- `test_accessibility.py` — automated WCAG scans via axe-core on every
  major page, plus targeted checks (image alt text, form labels, visible
  focus)

## What this is NOT a substitute for

axe-core catches a real but partial subset of accessibility issues
(contrast, missing labels, ARIA misuse, landmark structure). It does not
replace actual keyboard-only navigation testing or a real screen reader
pass — both are still worth doing manually before a real launch.
