#!/bin/sh

set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
agent_root=${CHATRAW_AGENT_ROOT:-/Users/massif/ChatRaw-Agent}
linkdb_root=${CHATRAW_LINKDB_ROOT:-/Users/massif/ChatRaw-LinkDB}
plugin_root=${CHATRAW_AGENT_PLUGIN_ROOT:-/Users/massif/ChatRaw-LinkDB-Agent-Plugin}
python_bin=${PYTHON_BIN:-"$root/.venv/bin/python"}
agent_python=${CHATRAW_AGENT_PYTHON:-python3.13}

cd "$root"

"$python_bin" scripts/check-t8-docs.py
"$python_bin" scripts/export-openapi.py --check
"$python_bin" scripts/module-conformance.py contracts \
    --manifest examples/reference-module/manifest.example.json \
    --manifest "$agent_root/chatraw_agent/module_manifest.json"
./scripts/run-backend-tests.sh -p no:cacheprovider
npm run check:frontend
"$python_bin" scripts/t8-data-recovery-acceptance.py

(
    cd "$agent_root"
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=".:$linkdb_root" \
        "$agent_python" -m pytest -q -p no:cacheprovider
)

(
    cd "$plugin_root"
    node --check chatraw-linkdb-agent/main.js
    node --test tests/plugin-contract.test.mjs
    unzip -t chatraw-linkdb-agent.zip
    "$python_bin" -c \
        "import sys,zipfile
from pathlib import Path
root=Path(sys.argv[1])
with zipfile.ZipFile(root/'chatraw-linkdb-agent.zip') as archive:
    for name in ('manifest.json','main.js','icon.png'):
        assert archive.read('chatraw-linkdb-agent/'+name) == (root/'chatraw-linkdb-agent'/name).read_bytes()" \
        "$plugin_root"
)

./scripts/run-t6-source-gate.sh
./scripts/run-t6-compose-gate.sh
./scripts/run-t7-source-gate.sh
./scripts/run-t7-compose-gate.sh
./scripts/run-t8-compose-recovery-gate.sh

echo "T8 local engineering release gate passed"
echo "Customer and production acceptance remain PENDING_ONSITE"
