import os
import importlib
import shutil
import sys
import tempfile
from pathlib import Path


_SUITE_DATA_DIR = Path(tempfile.mkdtemp(prefix="chatraw-pytest-suite-")).resolve()
os.environ["DATA_DIR"] = str(_SUITE_DATA_DIR)
os.environ["CHATRAW_TEST_MODE"] = "1"

# Import before test-module collection. Several legacy unittest modules set
# their own DATA_DIR at import time; the suite-level directory must remain the
# single authoritative location for the shared backend.main module.
importlib.import_module("backend.main")


def _is_system_temporary(path: Path) -> bool:
    temp_root = Path(tempfile.gettempdir()).resolve()
    try:
        path.resolve().relative_to(temp_root)
        return True
    except ValueError:
        return False


def pytest_runtest_setup(item):
    del item
    main_module = sys.modules.get("backend.main") or sys.modules.get("main")
    if main_module is None:
        return

    data_dir = Path(main_module.DATA_DIR).resolve()
    if not _is_system_temporary(data_dir):
        raise RuntimeError(
            f"backend tests must use a temporary DATA_DIR, got: {data_dir}"
        )


def pytest_sessionfinish(session, exitstatus):
    del session, exitstatus
    shutil.rmtree(_SUITE_DATA_DIR, ignore_errors=True)
