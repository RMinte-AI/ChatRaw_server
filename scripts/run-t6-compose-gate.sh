#!/bin/sh

set -eu

suffix=$$
server_project="chatraw-t6-server-$suffix"
module_project="chatraw-t6-module-$suffix"
server_port=${T6_COMPOSE_SERVER_PORT:-51131}
pairing_code="t6-compose-pairing-code-0123456789abcdef"
state_dir=$(mktemp -d "${TMPDIR:-/tmp}/chatraw-t6-compose.XXXXXX")
state_file="$state_dir/acceptance-state.json"
server_compose="docker-compose.yml"
module_compose="examples/reference-module/compose.yml"

cleanup() {
    docker compose -p "$server_project" -f "$server_compose" \
        down --volumes --rmi local --remove-orphans >/dev/null 2>&1 || true
    docker compose -p "$module_project" -f "$module_compose" \
        down --volumes --rmi local --remove-orphans >/dev/null 2>&1 || true
    case "$state_dir" in
        */chatraw-t6-compose.*) rm -rf -- "$state_dir" ;;
        *) echo "Refusing to remove unexpected path: $state_dir" >&2 ;;
    esac
}
trap cleanup EXIT INT TERM

python_bin=${PYTHON_BIN:-python3}
if [ -x ".venv/bin/python" ] && [ -z "${PYTHON_BIN:-}" ]; then
    python_bin=".venv/bin/python"
fi

wait_for_url() {
    url=$1
    attempt=0
    while [ "$attempt" -lt 90 ]; do
        if "$python_bin" -c \
            "import sys,urllib.request; urllib.request.urlopen(sys.argv[1],timeout=1)" \
            "$url" >/dev/null 2>&1; then
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    echo "Timed out waiting for $url" >&2
    return 1
}

export CHATRAW_PORT="$server_port"
export CHATRAW_LOOPBACK_DEV=1
export REFERENCE_MODULE_PAIRING_CODE="$pairing_code"

./scripts/create-module-network.sh
./scripts/check-compose-contract.sh

docker compose -p "$module_project" -f "$module_compose" \
    up -d --build
docker compose -p "$server_project" -f "$server_compose" \
    up -d --build
wait_for_url "http://127.0.0.1:$server_port/health"

setup_token=$(
    docker compose -p "$server_project" -f "$server_compose" \
        exec -T chatraw \
        python -c \
        "from pathlib import Path; print(Path('/app/data/secrets/setup-token').read_text().strip())"
)

"$python_bin" scripts/t6-deployment-acceptance.py bootstrap \
    --server-base-url "http://127.0.0.1:$server_port" \
    --module-base-url "http://chatraw-reference-module:8765" \
    --setup-token "$setup_token" \
    --pairing-code "$pairing_code" \
    --state-file "$state_file"

module_container=$(
    docker compose -p "$module_project" -f "$module_compose" \
        ps -q reference-module
)
private_container=$(
    docker compose -p "$module_project" -f "$module_compose" \
        ps -q reference-private
)
for container in "$module_container" "$private_container"; do
    port_bindings=$(
        docker inspect \
            --format '{{json .HostConfig.PortBindings}}' \
            "$container"
    )
    if [ "$port_bindings" != "{}" ] && [ "$port_bindings" != "null" ]; then
        echo "Module container unexpectedly publishes a host port: $port_bindings" >&2
        exit 1
    fi
done

"$python_bin" -c \
    "import urllib.error,urllib.request
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
try:
    opener.open('http://chatraw-reference-module:8765/',timeout=2)
except urllib.error.URLError:
    raise SystemExit(0)
raise SystemExit('module service name was unexpectedly reachable from the host')"

docker compose -p "$server_project" -f "$server_compose" \
    exec -T chatraw python -c \
    "import urllib.error,urllib.request
request=urllib.request.Request(
    'http://chatraw-reference-module:8765/chatraw-module/v1/manifest',
    headers={'Authorization':'Bearer invalid-t6-credential'})
try:
    urllib.request.urlopen(request,timeout=3)
except urllib.error.HTTPError as error:
    raise SystemExit(0 if error.code == 401 else 1)
raise SystemExit(1)"

docker compose -p "$server_project" -f "$server_compose" \
    exec -T chatraw python -c \
    "import urllib.error,urllib.request
try:
    urllib.request.urlopen('http://reference-private:9090/health',timeout=2)
except urllib.error.URLError:
    raise SystemExit(0)
raise SystemExit(1)"

docker compose -p "$module_project" -f "$module_compose" \
    restart reference-module
docker compose -p "$server_project" -f "$server_compose" \
    restart chatraw
wait_for_url "http://127.0.0.1:$server_port/health"
"$python_bin" scripts/t6-deployment-acceptance.py resume \
    --server-base-url "http://127.0.0.1:$server_port" \
    --module-base-url "http://chatraw-reference-module:8765" \
    --state-file "$state_file"

docker compose -p "$server_project" -f "$server_compose" down
docker compose -p "$module_project" -f "$module_compose" down
docker compose -p "$module_project" -f "$module_compose" up -d
docker compose -p "$server_project" -f "$server_compose" up -d
wait_for_url "http://127.0.0.1:$server_port/health"
"$python_bin" scripts/t6-deployment-acceptance.py resume \
    --server-base-url "http://127.0.0.1:$server_port" \
    --module-base-url "http://chatraw-reference-module:8765" \
    --state-file "$state_file"

echo "T6 Compose deployment, isolation, and volume-retention gate passed"
