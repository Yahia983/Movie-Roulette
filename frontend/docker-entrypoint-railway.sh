#!/bin/sh
# Substitutes ${PORT} into the nginx config template and starts nginx.
#
# Deliberately NOT using nginx's built-in automatic template envsubst
# (the official image's docker-entrypoint.d/20-envsubst-on-templates.sh,
# which runs on *every* environment variable found in the template) —
# that mechanism would also try to substitute nginx's own runtime
# variables if any template ever added one (e.g. $host, $remote_addr),
# silently corrupting the config. Explicitly limiting substitution to
# just '$PORT' via `envsubst '$PORT'` avoids that entire class of bug.
set -e

: "${PORT:=8080}"
export PORT

envsubst '$PORT' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

exec nginx -g "daemon off;"
