# Deploying to Railway

Railway-specific steps. See [`DEPLOYMENT.md`](DEPLOYMENT.md) for the
general/platform-agnostic deployment guide this supplements.

## What you need before starting

- A GitHub repo with this project pushed to it
- A Railway account, with this repo connected
- A TMDB API key if you want real catalog data (get one free at
  themoviedb.org → Settings → API) — optional, the app runs fine with just
  the two seed titles otherwise

## 1. Create the project and databases

In a new Railway project:

1. **"+ New" → "Database" → "Add PostgreSQL"** — no configuration needed,
   Railway provisions it and exposes connection variables automatically.
2. **"+ New" → "Database" → "Add Redis"** — same, no configuration needed.

## 2. Deploy the backend

1. **"+ New" → "GitHub Repo"**, select this repo.
2. In the new service's **Settings → Root Directory**, set it to `backend`.
   Railway will find `backend/railway.toml` and `backend/Dockerfile`
   automatically and build from those.
3. In **Settings → Networking**, click **"Generate Domain"** to get a
   public URL (something like `movieroulette-backend-production.up.railway.app`).
   Note this URL — you'll need it in step 4.
4. In **Variables**, add:

   | Variable | Value |
   |----------|-------|
   | `SECRET_KEY` | Generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"` — don't skip this, the app refuses to start in production with the dev default |
   | `ENVIRONMENT` | `production` |
   | `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` — reference the Postgres service Railway just created (type `${{` and Railway will autocomplete available service variables) |
   | `DATABASE_URL_SYNC` | Same as above, but replace `postgresql://` with `postgresql+psycopg2://` at the start — Alembic's migration runner needs the sync driver. If Railway's reference variable doesn't let you edit the string directly, just paste the resolved value with the scheme swapped. |
   | `REDIS_URL` | `${{Redis.REDIS_URL}}` |
   | `CORS_ALLOWED_ORIGINS` | `["https://YOUR-FRONTEND-URL.up.railway.app"]` — you'll get this exact URL in step 3 of the next section; come back and fill this in after |
   | `TMDB_API_KEY` | Your TMDB key, if syncing real data |

5. Railway auto-deploys on save. Once it's live, run the migration once
   (Railway's web shell, under the service's **"..." menu → "Shell"**, or
   via the Railway CLI: `railway run --service backend alembic upgrade head`):

   ```bash
   alembic upgrade head
   python scripts/seed_dev_data.py   # optional: 2 placeholder titles
   # or, with TMDB_API_KEY set:
   python scripts/sync_tmdb.py --media-type movie --pages 5
   python scripts/sync_tmdb.py --media-type tv --pages 5
   ```

6. Confirm it's actually up: `curl https://YOUR-BACKEND-URL.up.railway.app/api/v1/health`
   should return `{"status":"ok"}`.

## 3. Deploy the frontend

1. **"+ New" → "GitHub Repo"**, same repo again.
2. **Settings → Root Directory** → `frontend`. Railway finds
   `frontend/railway.toml` and `frontend/Dockerfile` automatically.
3. **Settings → Networking → "Generate Domain"** — this is your site's
   public URL.
4. **Before this works**, edit `frontend/js/config.js` in your repo:

   ```js
   export const API_BASE_URL_OVERRIDE = "https://YOUR-BACKEND-URL.up.railway.app/api/v1";
   ```

   Commit and push — Railway auto-deploys frontend changes too. This step
   is required: the frontend and backend are two separately-addressed
   Railway services with no shared domain for a same-origin API call to
   work, so `config.js` is what tells the frontend where to actually find
   the backend. See that file's comments for the full reasoning.

5. Go back to the **backend** service's `CORS_ALLOWED_ORIGINS` variable
   (step 2.4 above) and set it to this frontend URL now that you have it:
   `["https://YOUR-FRONTEND-URL.up.railway.app"]`. Without this, the
   browser will block every API call with a CORS error even though the
   backend itself is reachable.

## 4. Verify

Visit your frontend URL. You should see the home page load with the
seeded (or synced) titles. Try the roulette spin, registering an account,
and favoriting a title to confirm the full stack — frontend, backend,
Postgres, and Redis — is actually wired together correctly.

## Custom domain

Railway supports adding your own domain per-service under **Settings →
Networking → Custom Domain**. If you do this for the frontend, remember to
add that domain to the backend's `CORS_ALLOWED_ORIGINS` too.

## Troubleshooting

See [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) for general issues. Railway-specific ones:

- **Build fails with no obvious error**: check the Root Directory setting
  — if it's not set to `backend`/`frontend` respectively, Railway tries to
  build from the repo root and won't find the right Dockerfile.
- **Backend deploys but health check fails**: check `DATABASE_URL` and
  `REDIS_URL` are actually resolving (Railway's variable reference syntax
  `${{ServiceName.VARIABLE}}` is case-sensitive and must match the exact
  service name shown in your project).
- **Frontend loads but every action fails / CORS errors in the browser
  console**: almost always `CORS_ALLOWED_ORIGINS` on the backend not
  matching the frontend's actual URL exactly (including `https://`, no
  trailing slash), or `config.js` not pointing at the right backend URL.
