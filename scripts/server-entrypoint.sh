#!/bin/sh

set -eu

python /app/scripts/prepare-server-secrets.py \
    --data-dir "${DATA_DIR:-/app/data}" \
    --quiet

exec python /app/main.py
