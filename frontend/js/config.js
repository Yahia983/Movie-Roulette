/**
 * Deployment-specific configuration. This is the ONE file you edit when
 * deploying the frontend somewhere other than localhost or behind
 * `frontend/nginx.conf`'s same-origin API proxy (see docs/DEPLOYMENT.md).
 *
 * Why this exists as a separate, tiny file rather than inline in api.js:
 * this project has no build step (see docs/FRONTEND.md), so there's no
 * way to inject an environment variable at build time the way a bundled
 * app would. This file is the low-tech equivalent — a plain JS module you
 * edit by hand and commit, read by api.js at runtime.
 *
 * Leave this as `null` for:
 *   - Local development (auto-detects http://localhost:8000/api/v1)
 *   - A same-origin deployment where a reverse proxy (like
 *     frontend/nginx.conf) forwards /api/v1/* to the backend — e.g. the
 *     docker-compose.yml setup in this repo.
 *
 * Set this to your backend's full public URL for:
 *   - Two separately-hosted services with different domains (e.g. Railway,
 *     where the frontend and backend each get their own
 *     *.up.railway.app URL and there's no shared reverse proxy between
 *     them). The backend's CORS_ALLOWED_ORIGINS must include this
 *     frontend's own URL for cross-origin requests to succeed — see
 *     docs/DEPLOYMENT.md.
 *
 * Example:
 *   export const API_BASE_URL_OVERRIDE = "https://movieroulette-backend-production.up.railway.app/api/v1";
 */
export const API_BASE_URL_OVERRIDE = null;
