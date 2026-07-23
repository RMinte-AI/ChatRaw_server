#!/usr/bin/env python3
"""Export or verify the deterministic ChatRaw Server OpenAPI snapshot."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPOSITORY_ROOT / "docs" / "api" / "openapi.json"


def _render_openapi() -> str:
    with tempfile.TemporaryDirectory(prefix="chatraw-openapi-") as temp:
        os.environ["DATA_DIR"] = temp
        os.environ["CHATRAW_TEST_MODE"] = "1"
        sys.path.insert(0, str(REPOSITORY_ROOT))
        from backend.main import app

        schema = app.openapi()
    return json.dumps(
        schema,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export or check the committed ChatRaw OpenAPI snapshot"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    rendered = _render_openapi()
    output = arguments.output.resolve()

    if arguments.check:
        if not output.is_file():
            print(f"OpenAPI snapshot is missing: {output}", file=sys.stderr)
            return 1
        if output.read_text(encoding="utf-8") != rendered:
            print(
                "OpenAPI snapshot is stale; run "
                "scripts/export-openapi.py without --check",
                file=sys.stderr,
            )
            return 1
        print(f"OpenAPI snapshot is current: {output}")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"Wrote OpenAPI snapshot: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
