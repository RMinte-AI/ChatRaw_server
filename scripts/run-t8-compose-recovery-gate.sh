#!/bin/sh

set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
suffix=$$
source_project="chatraw-t8-recovery-source-$suffix"
restored_project="chatraw-t8-recovery-restored-$suffix"
source_port=${T8_COMPOSE_SOURCE_PORT:-51161}
restored_port=${T8_COMPOSE_RESTORED_PORT:-51162}
state_dir=$(mktemp -d "${TMPDIR:-/tmp}/chatraw-t8-compose-recovery.XXXXXX")
state_file="$state_dir/state.json"
backup_root="$state_dir/backups"
compose_file="$root/docker-compose.yml"
python_bin=${PYTHON_BIN:-"$root/.venv/bin/python"}

export CHATRAW_LOOPBACK_DEV=1

cleanup() {
    CHATRAW_PORT="$source_port" docker compose \
        -p "$source_project" -f "$compose_file" \
        down --volumes --rmi local --remove-orphans >/dev/null 2>&1 || true
    CHATRAW_PORT="$restored_port" docker compose \
        -p "$restored_project" -f "$compose_file" \
        down --volumes --rmi local --remove-orphans >/dev/null 2>&1 || true
    case "$state_dir" in
        */chatraw-t8-compose-recovery.*) rm -rf -- "$state_dir" ;;
        *) echo "Refusing to remove unexpected path: $state_dir" >&2 ;;
    esac
}
trap cleanup EXIT INT TERM

mkdir -p "$backup_root"
"$root/scripts/create-module-network.sh"

wait_for_ready() {
    url=$1
    project=$2
    port=$3
    attempt=0
    while [ "$attempt" -lt 120 ]; do
        if "$python_bin" -c \
            "import json,sys,urllib.request; assert json.load(urllib.request.urlopen(sys.argv[1],timeout=1))['status']=='ready'" \
            "$url/ready" >/dev/null 2>&1; then
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    CHATRAW_PORT="$port" docker compose \
        -p "$project" -f "$compose_file" logs --no-color >&2 || true
    echo "Timed out waiting for $url/ready" >&2
    return 1
}

CHATRAW_PORT="$source_port" docker compose \
    -p "$source_project" -f "$compose_file" up -d --build
wait_for_ready "http://127.0.0.1:$source_port" \
    "$source_project" "$source_port"

setup_token=$(
    CHATRAW_PORT="$source_port" docker compose \
        -p "$source_project" -f "$compose_file" \
        exec -T chatraw python -c \
        "from pathlib import Path; print(Path('/app/data/secrets/setup-token').read_text().strip())"
)

"$python_bin" "$root/scripts/t8-compose-recovery-client.py" bootstrap \
    --base-url "http://127.0.0.1:$source_port" \
    --setup-token "$setup_token" \
    --state-file "$state_file"

CHATRAW_PORT="$source_port" docker compose \
    -p "$source_project" -f "$compose_file" stop chatraw
CHATRAW_PORT="$source_port" docker compose \
    -p "$source_project" -f "$compose_file" run --rm --no-deps \
    -v "$backup_root:/backup" \
    chatraw python /app/server_data.py backup \
    --data-dir /app/data \
    --backup-dir /backup/chatraw \
    --confirm-source-quiesced
CHATRAW_PORT="$source_port" docker compose \
    -p "$source_project" -f "$compose_file" run --rm --no-deps \
    -v "$backup_root:/backup:ro" \
    chatraw python /app/server_data.py verify \
    --backup-dir /backup/chatraw

CHATRAW_PORT="$restored_port" docker compose \
    -p "$restored_project" -f "$compose_file" run --rm --no-deps \
    -v "$backup_root:/backup:ro" \
    chatraw python /app/server_data.py restore \
    --backup-dir /backup/chatraw \
    --data-dir /app/data \
    --confirm-destination-quiesced \
    --allow-empty-destination
CHATRAW_PORT="$restored_port" docker compose \
    -p "$restored_project" -f "$compose_file" up -d
wait_for_ready "http://127.0.0.1:$restored_port" \
    "$restored_project" "$restored_port"

"$python_bin" "$root/scripts/t8-compose-recovery-client.py" verify \
    --base-url "http://127.0.0.1:$restored_port" \
    --state-file "$state_file"

echo "T8 Compose fresh install, backup verification, and restore gate passed"
