#!/bin/sh

set -eu

test_data_dir=$(mktemp -d "${TMPDIR:-/tmp}/chatraw-tests.XXXXXX")

cleanup() {
    case "$test_data_dir" in
        */chatraw-tests.*) rm -rf -- "$test_data_dir" ;;
        *) echo "refusing to remove unexpected test path: $test_data_dir" >&2 ;;
    esac
}
trap cleanup EXIT INT TERM

export DATA_DIR="$test_data_dir"
export CHATRAW_TEST_MODE=1

python_bin=${PYTHON_BIN:-python}
if [ -x ".venv/bin/python" ] && [ -z "${PYTHON_BIN:-}" ]; then
    python_bin=".venv/bin/python"
fi

"$python_bin" -m pytest -q backend "$@"
