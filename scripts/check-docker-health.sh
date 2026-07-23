#!/bin/sh

set -eu

image=${1:-chatraw:test}
container_name="chatraw-t0-smoke-$$"

cleanup() {
    docker rm -f "$container_name" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

docker run -d \
    --name "$container_name" \
    --tmpfs /app/data:rw,noexec,nosuid,size=64m \
    -e DATA_DIR=/app/data \
    -e PORT=51111 \
    "$image" >/dev/null

attempt=0
while [ "$attempt" -lt 30 ]; do
    if docker exec "$container_name" python -c \
        "import json, urllib.request; health=json.load(urllib.request.urlopen('http://127.0.0.1:51111/health', timeout=2)); ready=json.load(urllib.request.urlopen('http://127.0.0.1:51111/ready', timeout=2)); assert health.get('status') == 'healthy'; assert ready.get('status') == 'ready'" \
        >/dev/null 2>&1; then
        echo "Docker image $image passed real HTTP /health and /ready checks"
        exit 0
    fi

    if [ "$(docker inspect -f '{{.State.Running}}' "$container_name" 2>/dev/null || true)" != "true" ]; then
        break
    fi

    attempt=$((attempt + 1))
    sleep 1
done

docker logs "$container_name" >&2 || true
echo "Docker image $image did not become healthy" >&2
exit 1
