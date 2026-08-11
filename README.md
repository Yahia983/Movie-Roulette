# MovieRoulette

**Never wonder what to watch again.**

An intelligent movie and TV discovery platform: instant search, smart
filters, favorites and collections, and a customizable roulette engine that
picks something to watch for you.

> **Status: Project complete (all phases).** Database schema,
> authentication, the core CRUD/browse API, a full vanilla-JS frontend, a
> TMDB catalog ingestion pipeline, a V2 recommendation engine, a real
> PostgreSQL integration test tier, an end-to-end browser test suite with
> automated accessibility scanning, and Lighthouse-verified performance are
> all implemented and tested. See
> [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md),
> [`docs/DATABASE.md`](docs/DATABASE.md),
> [`docs/FRONTEND.md`](docs/FRONTEND.md),
> [`docs/FEATURES.md`](docs/FEATURES.md),
> [`docs/DEVOPS.md`](docs/DEVOPS.md),
> [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md),
> [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md),
> [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md), and
> [`docs/RAILWAY.md`](docs/RAILWAY.md).

## Tech stack

| Layer    | Technology |
|----------|------------|
| Backend  | Python, FastAPI (async), SQLAlchemy 2.0, Alembic, Pydantic, PostgreSQL, Redis, JWT |
| Frontend | HTML5, CSS3 (Grid/Flexbox/custom properties), modern JS (ES6 modules) |
| DevOps   | Docker, Docker Compose, GitHub Actions, Black, Ruff, Mypy, Pytest, pre-commit |

## Project structure

```
movieroulette/
├── backend/
│   ├── app/
│   │   ├── core/        # config, security, logging, cache
│   │   ├── db/           # engine/session, declarative base
│   │   ├── models/       # SQLAlchemy ORM models (added in the backend phase)
│   │   ├── schemas/      # Pydantic request/response schemas (added next)
│   │   ├── api/v1/       # routers, versioned
│   │   ├── services/     # business logic, framework-agnostic
│   │   └── middleware/   # cross-cutting request handling (rate limiting, ...)
│   ├── alembic/          # database migrations
│   ├── tests/
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── Dockerfile
├── frontend/
│   ├── css/               # design tokens + base styles
│   ├── js/                # ES6 modules
│   └── index.html
├── docs/
├── docker-compose.yml
└── .github/workflows/
```

## Getting started (Docker — recommended)

```bash
cp backend/.env.example backend/.env
# edit backend/.env and set a real SECRET_KEY for anything beyond local dev

docker compose up --build
```

- API: <http://localhost:8000> (docs at `/docs`, health at `/api/v1/health`)
- Frontend: <http://localhost:3000>
- Postgres: `localhost:5432`
- Redis: `localhost:6379`

## Getting started (local, without Docker)

Requires Python 3.12+, a running PostgreSQL instance, and a running Redis
instance.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

cp .env.example .env  # then edit DATABASE_URL / REDIS_URL to match your local services

uvicorn app.main:app --reload
```

Serve `frontend/` with any static file server (e.g. `python -m http.server
3000` from inside `frontend/`) — it's a fully static app with no build step.
The frontend expects the API at `http://localhost:8000/api/v1` when served
from `localhost`, and at `/api/v1` (same-origin) otherwise — see
`frontend/js/api.js`. Open `http://localhost:3000/index.html` once both are
running.

## Development workflow

```bash
# Formatting & linting
black backend/
ruff check backend/ --fix

# Type checking
mypy backend/app

# Tests
cd backend && pytest

# Install git hooks (runs the above automatically on commit)
pre-commit install
```

## API surface (backend phase)

All endpoints are under `/api/v1`. Full interactive docs at `/docs` once the
server is running.

| Area | Endpoints |
|------|-----------|
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh` |
| Users | `GET/PATCH /users/me` |
| Genres | `GET /genres` |
| Movies | `GET /movies` (browse/search/filter), `GET /movies/{slug}` |
| TV shows | `GET /tv-shows`, `GET /tv-shows/{slug}` |
| Favorites | `GET /favorites`, `PUT/DELETE /favorites/{title_id}` |
| Watch later | `GET /watch-later`, `PUT/DELETE /watch-later/{title_id}` |
| Ratings | `PUT/DELETE /ratings/{title_id}` |
| History | `GET /history` (recently viewed) |
| Collections | `POST/GET /collections`, `GET/PATCH/DELETE /collections/{id}`, `PUT/DELETE /collections/{id}/items/{title_id}` |
| Roulette | `POST /roulette/spin` (works logged-in or anonymous) |
| Recommendations | `GET /movies\|tv-shows/{slug}/similar`, `GET /recommendations/for-you` |
| Health | `GET /health`, `GET /health/ready` |

## Frontend pages

| Page | Path | Notes |
|------|------|-------|
| Home | `/index.html` | Hero + trending/top-rated/popular rails |
| Browse | `/pages/browse.html?type=movie\|tv` | Search, filters, infinite scroll |
| Title detail | `/pages/title.html?type=movie\|tv&slug=...` | Favorite/watch-later/rate |
| Roulette | `/pages/roulette.html` | The signature spin-and-reveal feature |
| Auth | `/pages/auth.html?mode=login\|register` | One page, toggled form |
| My Library | `/pages/library.html?tab=favorites\|watchlater\|collections` | Requires login |

See [`docs/FRONTEND.md`](docs/FRONTEND.md) for the architecture and design
decisions behind these.

## Seeding sample data

```bash
cd backend
python scripts/seed_dev_data.py  # requires the schema to already be migrated
```

## Syncing real catalog data from TMDB

The seed script (above) creates two placeholder titles for local dev. To
populate the catalog with real movies/TV shows, cast, and streaming
availability from [The Movie Database](https://www.themoviedb.org):

```bash
# Get a free API key at https://www.themoviedb.org/settings/api,
# then add it to backend/.env:
#   TMDB_API_KEY=your-key-here

cd backend
python scripts/sync_tmdb.py --media-type movie --pages 5
python scripts/sync_tmdb.py --media-type tv --pages 5
```

Each TMDB "page" is 20 titles; each title costs one extra API call for full
details (credits + streaming availability), so mind TMDB's rate limits on
large syncs. See [`docs/FEATURES.md`](docs/FEATURES.md) for how the
ingestion pipeline is structured (and how it's tested without any network
access).

## Database migrations

```bash
cd backend
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

## Roadmap

- [x] **Foundation** — project scaffolding, config, DB/cache wiring, Docker, CI, health checks
- [x] **Backend** — database schema, ORM models, auth, core CRUD API, roulette engine (V1)
- [x] **Frontend** — design system, six pages (home, browse, title detail, roulette, auth, library), all wired to the live API
- [x] **Features** — TMDB ingestion pipeline (cast/streaming data), recommendation engine V2 (similar titles + personalized "for you")
- [x] **Testing & DevOps** — Postgres integration tier, end-to-end browser tests, automated accessibility scans, Lighthouse performance audits, production-hardened nginx config

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the reasoning behind
current decisions.
