# Frontend container for platforms that deploy each service as its own
# Docker build with a dynamically-assigned port (Railway, and similar
# PaaS platforms) — as opposed to docker-compose.yml's approach, which
# mounts frontend/ into a stock nginx image with a config that expects a
# fixed port and proxies /api/v1 to a same-network "backend" host.
#
# This image is self-contained: it doesn't proxy API calls (Railway
# deploys the frontend and backend as separately-addressed services with
# no shared network path suitable for a reverse proxy), so cross-origin
# calls to the backend's own public URL are used instead — see
# js/config.js for where that URL is configured.
FROM nginx:1.27-alpine

COPY . /usr/share/nginx/html
COPY nginx.railway.conf.template /etc/nginx/templates/default.conf.template
COPY docker-entrypoint-railway.sh /docker-entrypoint-railway.sh
RUN chmod +x /docker-entrypoint-railway.sh \
    && rm -f /usr/share/nginx/html/nginx.conf \
    && rm -f /usr/share/nginx/html/nginx.railway.conf.template \
    && rm -f /usr/share/nginx/html/Dockerfile \
    && rm -f /usr/share/nginx/html/docker-entrypoint-railway.sh

EXPOSE 8080

ENTRYPOINT ["/docker-entrypoint-railway.sh"]
