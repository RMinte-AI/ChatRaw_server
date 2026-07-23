#!/bin/sh

set -eu

python_bin=${PYTHON_BIN:-python3}
docker compose \
    -f docker-compose.yml \
    config \
    --format json |
    "$python_bin" scripts/validate-compose-contract.py server

docker compose \
    -f examples/reference-module/compose.yml \
    config \
    --format json |
    "$python_bin" scripts/validate-compose-contract.py module
