#!/bin/sh

set -eu

server_root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
agent_root=${CHATRAW_AGENT_ROOT:-/Users/massif/ChatRaw-Agent}
linkdb_root=${CHATRAW_LINKDB_ROOT:-/Users/massif/ChatRaw-LinkDB}
plugin_root=${CHATRAW_AGENT_PLUGIN_ROOT:-/Users/massif/ChatRaw-LinkDB-Agent-Plugin/chatraw-linkdb-agent}

suffix=$$
server_project="chatraw-t7-server-$suffix"
agent_project="chatraw-t7-agent-$suffix"
linkdb_project="chatraw-t7-linkdb-$suffix"
server_port=${T7_COMPOSE_SERVER_PORT:-51151}
private_network="chatraw-agent-linkdb-t7-$suffix"
agent_volume="chatraw-agent-data-t7-$suffix"
linkdb_volume="chatraw-linkdb-data-t7-$suffix"
state_dir=$(mktemp -d "${TMPDIR:-/tmp}/chatraw-t7-compose.XXXXXX")
acceptance_state="$state_dir/acceptance-state.json"
pairing_code="t7-compose-pairing-code-0123456789abcdef"
server_compose="$server_root/docker-compose.yml"
agent_compose="$agent_root/compose.yml"
linkdb_compose="$agent_root/compose.t7-acceptance.yml"

cleanup() {
    docker compose -p "$server_project" -f "$server_compose" \
        down --volumes --rmi local --remove-orphans >/dev/null 2>&1 || true
    docker compose -p "$agent_project" -f "$agent_compose" \
        down --volumes --rmi local --remove-orphans >/dev/null 2>&1 || true
    docker compose -p "$linkdb_project" -f "$linkdb_compose" \
        down --volumes --rmi local --remove-orphans >/dev/null 2>&1 || true
    docker network rm "$private_network" >/dev/null 2>&1 || true
    case "$state_dir" in
        */chatraw-t7-compose.*) rm -rf -- "$state_dir" ;;
        *) echo "Refusing to remove unexpected path: $state_dir" >&2 ;;
    esac
}
trap cleanup EXIT INT TERM

python_bin=${PYTHON_BIN:-"$server_root/.venv/bin/python"}
if [ ! -x "$python_bin" ]; then
    echo "Server Python runtime not found: $python_bin" >&2
    exit 1
fi

for path in "$agent_root" "$linkdb_root" "$plugin_root"; do
    if [ ! -e "$path" ]; then
        echo "Required T7 repository path is missing: $path" >&2
        exit 1
    fi
done

export CHATRAW_PORT="$server_port"
export CHATRAW_LOOPBACK_DEV=1
export CHATRAW_AGENT_MODULE_PAIRING_CODE="$pairing_code"
export CHATRAW_AGENT_MODULE_HOST_BASE_URL="http://chatraw-server:51111"
export CHATRAW_AGENT_LINKDB_BASE_URL="http://chatraw-linkdb:8765"
export CHATRAW_AGENT_LINKDB_NETWORK="$private_network"
export CHATRAW_AGENT_DATA_VOLUME="$agent_volume"
export CHATRAW_T7_LINKDB_VOLUME="$linkdb_volume"
export CHATRAW_T7_STATE_DIR="$state_dir"
export CHATRAW_LINKDB_ROOT="$linkdb_root"

"$server_root/scripts/create-module-network.sh"
docker network create --driver bridge --internal "$private_network" \
    >/dev/null

docker compose -f "$server_compose" config --format json |
    "$python_bin" "$server_root/scripts/validate-compose-contract.py" server
docker compose -f "$agent_compose" config --format json |
    "$python_bin" "$server_root/scripts/validate-t7-compose-contract.py" agent
docker compose -f "$linkdb_compose" config --format json |
    "$python_bin" "$server_root/scripts/validate-t7-compose-contract.py" \
        linkdb-fixture

wait_for_url() {
    url=$1
    attempt=0
    while [ "$attempt" -lt 120 ]; do
        if "$python_bin" -c \
            "import sys,urllib.request; urllib.request.urlopen(sys.argv[1],timeout=1)" \
            "$url" >/dev/null 2>&1; then
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    echo "Timed out waiting for $url" >&2
    docker compose -p "$server_project" -f "$server_compose" logs \
        --no-color >&2 || true
    return 1
}

wait_for_healthy() {
    project=$1
    compose_file=$2
    service=$3
    attempt=0
    while [ "$attempt" -lt 120 ]; do
        container=$(
            docker compose -p "$project" -f "$compose_file" \
                ps -q "$service"
        )
        if [ -n "$container" ]; then
            health=$(
                docker inspect \
                    --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
                    "$container"
            )
            if [ "$health" = "healthy" ]; then
                return 0
            fi
            if [ "$health" = "exited" ] || [ "$health" = "dead" ]; then
                docker compose -p "$project" -f "$compose_file" logs \
                    --no-color "$service" >&2 || true
                return 1
            fi
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    echo "Timed out waiting for healthy service: $service" >&2
    docker compose -p "$project" -f "$compose_file" logs \
        --no-color "$service" >&2 || true
    return 1
}

docker compose -p "$linkdb_project" -f "$linkdb_compose" \
    up -d --build
wait_for_healthy "$linkdb_project" "$linkdb_compose" t7-linkdb

linkdb_token=$(
    "$python_bin" -c \
        "import json,sys; print(json.load(open(sys.argv[1], encoding='utf-8'))['agent_token'])" \
        "$state_dir/linkdb-state.json"
)
export CHATRAW_AGENT_LINKDB_TOKEN="$linkdb_token"

docker compose -p "$agent_project" -f "$agent_compose" \
    up -d --build
docker compose -p "$server_project" -f "$server_compose" \
    up -d --build
wait_for_healthy "$agent_project" "$agent_compose" chatraw-agent
wait_for_url "http://127.0.0.1:$server_port/health"

setup_token=$(
    docker compose -p "$server_project" -f "$server_compose" \
        exec -T chatraw \
        python -c \
        "from pathlib import Path; print(Path('/app/data/secrets/setup-token').read_text().strip())"
)

"$python_bin" "$server_root/scripts/t7-agent-acceptance.py" bootstrap \
    --server-base-url "http://127.0.0.1:$server_port" \
    --module-base-url "http://chatraw-agent:8766" \
    --setup-token "$setup_token" \
    --pairing-code "$pairing_code" \
    --plugin-dir "$plugin_root" \
    --state-file "$acceptance_state"

agent_container=$(
    docker compose -p "$agent_project" -f "$agent_compose" \
        ps -q chatraw-agent
)
linkdb_container=$(
    docker compose -p "$linkdb_project" -f "$linkdb_compose" \
        ps -q t7-linkdb
)
for container in "$agent_container" "$linkdb_container"; do
    port_bindings=$(
        docker inspect \
            --format '{{json .HostConfig.PortBindings}}' \
            "$container"
    )
    if [ "$port_bindings" != "{}" ] && [ "$port_bindings" != "null" ]; then
        echo "Private T7 service publishes host ports: $port_bindings" >&2
        exit 1
    fi
done

docker compose -p "$server_project" -f "$server_compose" \
    exec -T chatraw python -c \
    "import urllib.error,urllib.request
try:
    urllib.request.urlopen('http://chatraw-linkdb:8765/health',timeout=2)
except urllib.error.URLError:
    raise SystemExit(0)
raise SystemExit('ChatRaw Server unexpectedly reached private LinkDB')"

docker compose -p "$server_project" -f "$server_compose" \
    exec -T chatraw python -c \
    "import urllib.error,urllib.request
request=urllib.request.Request(
    'http://chatraw-agent:8766/chatraw-module/v1/manifest',
    headers={'Authorization':'Bearer invalid-t7-credential'})
try:
    urllib.request.urlopen(request,timeout=3)
except urllib.error.HTTPError as error:
    raise SystemExit(0 if error.code == 401 else 1)
raise SystemExit('Agent accepted an invalid module credential')"

docker compose -p "$agent_project" -f "$agent_compose" \
    exec -T chatraw-agent python -c \
    "import urllib.request
urllib.request.urlopen('http://chatraw-server:51111/health',timeout=3)
urllib.request.urlopen('http://chatraw-linkdb:8765/ready',timeout=3)"

docker compose -p "$linkdb_project" -f "$linkdb_compose" \
    exec -T t7-linkdb python -c \
    "import urllib.error,urllib.request
try:
    urllib.request.urlopen('http://chatraw-server:51111/health',timeout=2)
except urllib.error.URLError:
    raise SystemExit(0)
raise SystemExit('Private LinkDB unexpectedly reached ChatRaw Server')"

"$python_bin" "$server_root/scripts/t7-agent-acceptance.py" \
    start-recovery \
    --server-base-url "http://127.0.0.1:$server_port" \
    --state-file "$acceptance_state"

attempt=0
while [ "$attempt" -lt 120 ]; do
    if docker compose -p "$linkdb_project" -f "$linkdb_compose" \
        exec -T t7-linkdb python -c \
        "from pathlib import Path; raise SystemExit(0 if '苏A99999' in Path('/data/customer-calls.jsonl').read_text(encoding='utf-8') else 1)" \
        >/dev/null 2>&1; then
        break
    fi
    attempt=$((attempt + 1))
    sleep 0.1
done
if [ "$attempt" -ge 120 ]; then
    echo "Timed out waiting for Compose recovery call" >&2
    exit 1
fi

docker compose -p "$agent_project" -f "$agent_compose" \
    stop -t 0 chatraw-agent
docker compose -p "$agent_project" -f "$agent_compose" \
    up -d chatraw-agent
wait_for_healthy "$agent_project" "$agent_compose" chatraw-agent
docker compose -p "$server_project" -f "$server_compose" \
    restart chatraw
wait_for_url "http://127.0.0.1:$server_port/health"

"$python_bin" "$server_root/scripts/t7-agent-acceptance.py" resume \
    --server-base-url "http://127.0.0.1:$server_port" \
    --state-file "$acceptance_state"

docker compose -p "$agent_project" -f "$agent_compose" \
    stop chatraw-agent
"$python_bin" "$server_root/scripts/t7-agent-acceptance.py" agent-offline \
    --server-base-url "http://127.0.0.1:$server_port" \
    --state-file "$acceptance_state"

docker compose -p "$agent_project" -f "$agent_compose" \
    up -d chatraw-agent
wait_for_healthy "$agent_project" "$agent_compose" chatraw-agent

docker compose -p "$linkdb_project" -f "$linkdb_compose" \
    exec -T t7-linkdb python -c \
    "import json
from pathlib import Path
customer=[json.loads(line) for line in Path('/data/customer-calls.jsonl').read_text(encoding='utf-8').splitlines()]
private=[json.loads(line) for line in Path('/data/private-agent-calls.jsonl').read_text(encoding='utf-8').splitlines()]
assert customer and private
assert all(item['authorized'] is True and item['principal_present'] is False for item in customer)
assert all(item['principal_present'] is True and item['authorization_present'] is True for item in private)
assert all(set(item) == {'path','principal_present','authorization_present'} for item in private)"

docker compose -p "$linkdb_project" -f "$linkdb_compose" \
    stop t7-linkdb
"$python_bin" "$server_root/scripts/t7-agent-acceptance.py" linkdb-offline \
    --server-base-url "http://127.0.0.1:$server_port" \
    --state-file "$acceptance_state"

echo "T7 Compose cross-repository and dual-network gate passed"
