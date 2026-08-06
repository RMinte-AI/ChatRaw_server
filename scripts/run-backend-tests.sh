#!/bin/sh

set -eu

test_root_dir=$(mktemp -d "${TMPDIR:-/tmp}/chatraw-tests.XXXXXX")

cleanup() {
    case "$test_root_dir" in
        */chatraw-tests.*) rm -rf -- "$test_root_dir" ;;
        *) echo "refusing to remove unexpected test path: $test_root_dir" >&2 ;;
    esac
}
trap cleanup EXIT INT TERM

export CHATRAW_TEST_MODE=1

python_bin=${PYTHON_BIN:-python}
if [ -x ".venv/bin/python" ] && [ -z "${PYTHON_BIN:-}" ]; then
    python_bin=".venv/bin/python"
fi

general_data_dir="$test_root_dir/general"
auth_data_dir="$test_root_dir/auth-security"
mkdir -p "$general_data_dir" "$auth_data_dir"

# test_t2_auth_security creates the first administrator at class setup. Pytest
# imports every test module during collection, and several legacy suites bind
# backend.main to their own process-global DATA_DIR. Keep this setup-sensitive
# suite in a fresh interpreter and database so full-suite order cannot consume
# its one-time setup token before the class starts.
DATA_DIR="$general_data_dir" "$python_bin" -m pytest -q backend \
    --ignore=backend/test_t2_auth_security.py "$@"
DATA_DIR="$auth_data_dir" "$python_bin" -m pytest -q \
    backend/test_t2_auth_security.py "$@"
