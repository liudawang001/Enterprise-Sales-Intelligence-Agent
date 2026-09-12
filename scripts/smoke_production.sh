#!/usr/bin/env sh
set -eu

base_url="${SMOKE_BASE_URL:-http://127.0.0.1:8080}"
curl --fail --silent --show-error "$base_url/health/live"
curl --fail --silent --show-error "$base_url/health/ready"
curl --fail --silent --show-error "$base_url/health/dependencies"
echo "Production health smoke passed"
