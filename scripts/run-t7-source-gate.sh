#!/bin/sh

set -eu

server_root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
agent_root=${CHATRAW_AGENT_ROOT:-/Users/massif/ChatRaw-Agent}
linkdb_root=${CHATRAW_LINKDB_ROOT:-/Users/massif/ChatRaw-LinkDB}
plugin_root=${CHATRAW_AGENT_PLUGIN_ROOT:-/Users/massif/ChatRaw-LinkDB-Agent-Plugin/chatraw-linkdb-agent}

server_port=${T7_SOURCE_SERVER_PORT:-51141}
agent_port=${T7_SOURCE_AGENT_PORT:-8766}
linkdb_port=${T7_SOURCE_LINKDB_PORT:-8765}
model_port=${T7_SOURCE_MODEL_PORT:-51142}
runtime_root=$(mktemp -d "${TMPDIR:-/tmp}/chatraw-t7-source.XXXXXX")
server_data="$runtime_root/server"
agent_data="$runtime_root/agent"
linkdb_data="$runtime_root/linkdb"
acceptance_state="$runtime_root/acceptance-state.json"
linkdb_state="$runtime_root/linkdb-state.json"
pairing_code="t7-source-pairing-code-0123456789abcdef"
server_pid=""
agent_pid=""
linkdb_pid=""
model_pid=""

cleanup() {
    if [ -n "$agent_pid" ]; then
        kill "$agent_pid" >/dev/null 2>&1 || true
        wait "$agent_pid" 2>/dev/null || true
    fi
    if [ -n "$server_pid" ]; then
        kill "$server_pid" >/dev/null 2>&1 || true
        wait "$server_pid" 2>/dev/null || true
    fi
    if [ -n "$linkdb_pid" ]; then
        kill "$linkdb_pid" >/dev/null 2>&1 || true
        wait "$linkdb_pid" 2>/dev/null || true
    fi
    if [ -n "$model_pid" ]; then
        kill "$model_pid" >/dev/null 2>&1 || true
        wait "$model_pid" 2>/dev/null || true
    fi
    case "$runtime_root" in
        */chatraw-t7-source.*) rm -rf -- "$runtime_root" ;;
        *) echo "Refusing to remove unexpected path: $runtime_root" >&2 ;;
    esac
}
trap cleanup EXIT INT TERM

server_python=${CHATRAW_SERVER_PYTHON:-"$server_root/.venv/bin/python"}
agent_python=${CHATRAW_AGENT_PYTHON:-"$agent_root/.venv/bin/python"}
linkdb_python=${CHATRAW_LINKDB_PYTHON:-"$linkdb_root/.venv/bin/python"}

for executable in "$server_python" "$agent_python" "$linkdb_python"; do
    if ! command -v "$executable" >/dev/null 2>&1 && [ ! -x "$executable" ]; then
        echo "Python runtime not found: $executable" >&2
        exit 1
    fi
done
for path in "$agent_root" "$linkdb_root" "$plugin_root"; do
    if [ ! -e "$path" ]; then
        echo "Required T7 repository path is missing: $path" >&2
        exit 1
    fi
done

mkdir -p "$server_data" "$agent_data" "$linkdb_data"
chmod 700 "$server_data" "$agent_data" "$linkdb_data"

wait_for_url() {
    python_runtime=$1
    url=$2
    log_file=$3
    attempt=0
    while [ "$attempt" -lt 90 ]; do
        if "$python_runtime" -c \
            "import sys,urllib.request; urllib.request.urlopen(sys.argv[1],timeout=1)" \
            "$url" >/dev/null 2>&1; then
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    echo "Timed out waiting for $url" >&2
    sed -n '1,260p' "$log_file" >&2
    return 1
}

require_process() {
    pid=$1
    log_file=$2
    sleep 1
    if ! kill -0 "$pid" 2>/dev/null; then
        echo "Process $pid exited during startup" >&2
        sed -n '1,260p' "$log_file" >&2
        return 1
    fi
}

start_linkdb() {
    "$linkdb_python" "$agent_root/scripts/t7-linkdb-fixture.py" \
        --linkdb-root "$linkdb_root" \
        --data-dir "$linkdb_data" \
        --host 127.0.0.1 \
        --port "$linkdb_port" \
        --state-file "$linkdb_state" \
        >"$linkdb_data/linkdb.log" 2>&1 &
    linkdb_pid=$!
}

linkdb_token() {
    "$linkdb_python" -c \
        "import json,sys; print(json.load(open(sys.argv[1], encoding='utf-8'))['agent_token'])" \
        "$linkdb_state"
}

start_server() {
    DATA_DIR="$server_data" \
    PORT="$server_port" \
    CHATRAW_LOOPBACK_DEV=1 \
    "$server_python" "$server_root/backend/main.py" \
        >"$server_data/server.log" 2>&1 &
    server_pid=$!
}

start_model() {
    "$server_python" "$server_root/scripts/t7-model-fixture.py" \
        --host 127.0.0.1 \
        --port "$model_port" \
        >"$server_data/model.log" 2>&1 &
    model_pid=$!
}

start_agent() {
    CHATRAW_AGENT_DB_PATH="$agent_data/agent.sqlite3" \
    CHATRAW_AGENT_MODULE_DB_PATH="$agent_data/module.sqlite3" \
    CHATRAW_AGENT_MODULE_HOST_BASE_URL="http://127.0.0.1:$server_port" \
    CHATRAW_AGENT_MODULE_PAIRING_CODE="$pairing_code" \
    CHATRAW_AGENT_MODULE_INSTANCE_ID="chatraw-agent-source-t7" \
    CHATRAW_AGENT_MODULE_QUIET=1 \
    CHATRAW_AGENT_LINKDB_BASE_URL="http://127.0.0.1:$linkdb_port" \
    CHATRAW_AGENT_LINKDB_TOKEN="$(linkdb_token)" \
    PYTHONPATH="$agent_root" \
    "$agent_python" -m uvicorn chatraw_agent.api:app \
        --host 127.0.0.1 \
        --port "$agent_port" \
        >"$agent_data/agent.log" 2>&1 &
    agent_pid=$!
}

wait_for_customer_call() {
    plate=$1
    calls_file="$linkdb_data/customer-calls.jsonl"
    attempt=0
    while [ "$attempt" -lt 120 ]; do
        if [ -f "$calls_file" ] && grep -F "$plate" "$calls_file" >/dev/null 2>&1; then
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 0.1
    done
    echo "Timed out waiting for real LinkDB customer call for $plate" >&2
    [ ! -f "$calls_file" ] || sed -n '1,120p' "$calls_file" >&2
    return 1
}

"$server_python" "$server_root/scripts/prepare-server-secrets.py" \
    --data-dir "$server_data" \
    --quiet
setup_token=$(sed -n '1p' "$server_data/secrets/setup-token")

start_linkdb
require_process "$linkdb_pid" "$linkdb_data/linkdb.log"
wait_for_url "$linkdb_python" \
    "http://127.0.0.1:$linkdb_port/health" \
    "$linkdb_data/linkdb.log"

start_server
require_process "$server_pid" "$server_data/server.log"
wait_for_url "$server_python" \
    "http://127.0.0.1:$server_port/health" \
    "$server_data/server.log"

start_model
require_process "$model_pid" "$server_data/model.log"
wait_for_url "$server_python" \
    "http://127.0.0.1:$model_port/health" \
    "$server_data/model.log"

start_agent
require_process "$agent_pid" "$agent_data/agent.log"
wait_for_url "$agent_python" \
    "http://127.0.0.1:$agent_port/v1/health" \
    "$agent_data/agent.log"

"$server_python" "$server_root/scripts/t7-agent-acceptance.py" bootstrap \
    --server-base-url "http://127.0.0.1:$server_port" \
    --module-base-url "http://127.0.0.1:$agent_port" \
    --setup-token "$setup_token" \
    --pairing-code "$pairing_code" \
    --plugin-dir "$plugin_root" \
    --model-base-url "http://127.0.0.1:$model_port" \
    --state-file "$acceptance_state"

if [ "${T7_SOURCE_HOLD_AFTER_BOOTSTRAP:-0}" = "1" ]; then
    echo "T7 browser fixture ready at http://127.0.0.1:$server_port"
    while :; do
        sleep 30
    done
fi

"$server_python" "$server_root/scripts/t7-agent-acceptance.py" start-recovery \
    --server-base-url "http://127.0.0.1:$server_port" \
    --state-file "$acceptance_state"
wait_for_customer_call "苏A99999"

kill "$agent_pid"
wait "$agent_pid" 2>/dev/null || true
agent_pid=""
start_agent
require_process "$agent_pid" "$agent_data/agent.log"
wait_for_url "$agent_python" \
    "http://127.0.0.1:$agent_port/v1/health" \
    "$agent_data/agent.log"

kill "$server_pid"
wait "$server_pid" 2>/dev/null || true
server_pid=""
start_server
require_process "$server_pid" "$server_data/server.log"
wait_for_url "$server_python" \
    "http://127.0.0.1:$server_port/health" \
    "$server_data/server.log"

"$server_python" "$server_root/scripts/t7-agent-acceptance.py" resume \
    --server-base-url "http://127.0.0.1:$server_port" \
    --state-file "$acceptance_state"

kill "$agent_pid"
wait "$agent_pid" 2>/dev/null || true
agent_pid=""
"$server_python" "$server_root/scripts/t7-agent-acceptance.py" agent-offline \
    --server-base-url "http://127.0.0.1:$server_port" \
    --state-file "$acceptance_state"

start_agent
require_process "$agent_pid" "$agent_data/agent.log"
wait_for_url "$agent_python" \
    "http://127.0.0.1:$agent_port/v1/health" \
    "$agent_data/agent.log"

kill "$linkdb_pid"
wait "$linkdb_pid" 2>/dev/null || true
linkdb_pid=""
"$server_python" "$server_root/scripts/t7-agent-acceptance.py" linkdb-offline \
    --server-base-url "http://127.0.0.1:$server_port" \
    --state-file "$acceptance_state"

"$agent_python" -c \
    "import json,sys
customer_path,private_path=sys.argv[1:]
for line in open(customer_path, encoding='utf-8'):
    item=json.loads(line)
    assert item['authorized'] is True
    assert item['principal_present'] is False
    assert 'token' not in item
private_calls=[json.loads(line) for line in open(private_path, encoding='utf-8')]
assert private_calls
for item in private_calls:
    assert item['principal_present'] is True
    assert item['authorization_present'] is True
    assert set(item) == {'path','principal_present','authorization_present'}
print('T7 private LinkDB call audit passed')" \
    "$linkdb_data/customer-calls.jsonl" \
    "$linkdb_data/private-agent-calls.jsonl"

echo "T7 source cross-repository gate passed"
