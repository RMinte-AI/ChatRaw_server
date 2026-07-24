#!/bin/sh

set -eu

server_port=${T6_SOURCE_SERVER_PORT:-51121}
module_port=${T6_SOURCE_MODULE_PORT:-8765}
server_data=$(mktemp -d "${TMPDIR:-/tmp}/chatraw-t6-source-server.XXXXXX")
module_data=$(mktemp -d "${TMPDIR:-/tmp}/chatraw-t6-source-module.XXXXXX")
state_file="$server_data/acceptance-state.json"
pairing_code="t6-source-pairing-code-0123456789abcdef"
server_pid=""
module_pid=""

cleanup() {
    if [ -n "$server_pid" ]; then
        kill "$server_pid" >/dev/null 2>&1 || true
        wait "$server_pid" 2>/dev/null || true
    fi
    if [ -n "$module_pid" ]; then
        kill "$module_pid" >/dev/null 2>&1 || true
        wait "$module_pid" 2>/dev/null || true
    fi
    case "$server_data" in
        */chatraw-t6-source-server.*) rm -rf -- "$server_data" ;;
        *) echo "Refusing to remove unexpected path: $server_data" >&2 ;;
    esac
    case "$module_data" in
        */chatraw-t6-source-module.*) rm -rf -- "$module_data" ;;
        *) echo "Refusing to remove unexpected path: $module_data" >&2 ;;
    esac
}
trap cleanup EXIT INT TERM

python_bin=${PYTHON_BIN:-python}
if [ -x ".venv/bin/python" ] && [ -z "${PYTHON_BIN:-}" ]; then
    python_bin=".venv/bin/python"
fi

start_module() {
    REFERENCE_MODULE_DATA_DIR="$module_data" \
    REFERENCE_MODULE_PAIRING_CODE="$pairing_code" \
    REFERENCE_MODULE_INSTANCE_ID="chatraw-reference-source" \
    "$python_bin" -m uvicorn \
        --app-dir examples/reference-module \
        app:app \
        --host 127.0.0.1 \
        --port "$module_port" \
        >"$module_data/module.log" 2>&1 &
    module_pid=$!
}

start_server() {
    DATA_DIR="$server_data" \
    PORT="$server_port" \
    CHATRAW_LOOPBACK_DEV=1 \
    "$python_bin" backend/main.py \
        >"$server_data/server.log" 2>&1 &
    server_pid=$!
}

require_process() {
    pid=$1
    log_file=$2
    sleep 1
    if ! kill -0 "$pid" 2>/dev/null; then
        echo "Process $pid exited during startup" >&2
        sed -n '1,240p' "$log_file" >&2
        return 1
    fi
}

wait_for_url() {
    url=$1
    attempt=0
    while [ "$attempt" -lt 60 ]; do
        if "$python_bin" -c \
            "import sys,urllib.request; urllib.request.urlopen(sys.argv[1],timeout=1)" \
            "$url" >/dev/null 2>&1; then
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    echo "Timed out waiting for $url" >&2
    if [ -f "$server_data/server.log" ]; then
        sed -n '1,240p' "$server_data/server.log" >&2
    fi
    if [ -f "$module_data/module.log" ]; then
        sed -n '1,240p' "$module_data/module.log" >&2
    fi
    return 1
}

wait_for_tcp() {
    host=$1
    port=$2
    attempt=0
    while [ "$attempt" -lt 60 ]; do
        if "$python_bin" -c \
            "import socket,sys; socket.create_connection((sys.argv[1],int(sys.argv[2])),1).close()" \
            "$host" "$port" >/dev/null 2>&1; then
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    echo "Timed out waiting for $host:$port" >&2
    return 1
}

"$python_bin" scripts/prepare-server-secrets.py \
    --data-dir "$server_data" \
    --quiet
setup_token=$(sed -n '1p' "$server_data/secrets/setup-token")

start_module
start_server
require_process "$module_pid" "$module_data/module.log"
require_process "$server_pid" "$server_data/server.log"
wait_for_url "http://127.0.0.1:$server_port/health"
wait_for_tcp 127.0.0.1 "$module_port"

"$python_bin" scripts/t6-deployment-acceptance.py bootstrap \
    --server-base-url "http://127.0.0.1:$server_port" \
    --module-base-url "http://127.0.0.1:$module_port" \
    --module-probe-base-url "http://127.0.0.1:$module_port" \
    --setup-token "$setup_token" \
    --pairing-code "$pairing_code" \
    --state-file "$state_file"

kill "$module_pid"
wait "$module_pid" 2>/dev/null || true
module_pid=""
start_module
require_process "$module_pid" "$module_data/module.log"
wait_for_tcp 127.0.0.1 "$module_port"

kill "$server_pid"
wait "$server_pid" 2>/dev/null || true
server_pid=""
start_server
require_process "$server_pid" "$server_data/server.log"
wait_for_url "http://127.0.0.1:$server_port/health"

"$python_bin" scripts/t6-deployment-acceptance.py resume \
    --server-base-url "http://127.0.0.1:$server_port" \
    --module-base-url "http://127.0.0.1:$module_port" \
    --module-probe-base-url "http://127.0.0.1:$module_port" \
    --state-file "$state_file"

echo "T6 source deployment gate passed"
