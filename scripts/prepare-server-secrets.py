#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

try:
    from backend.auth import ensure_setup_secret
except ImportError:
    from auth import ensure_setup_secret


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create the one-time ChatRaw Server setup token file"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
    )
    parser.add_argument("--quiet", action="store_true")
    arguments = parser.parse_args()
    secret_file = arguments.data_dir.resolve() / "secrets" / "setup-token"
    token = ensure_setup_secret(secret_file)
    if token is None:
        if not arguments.quiet:
            print(f"Setup token file already exists: {secret_file}")
        return 0
    if not arguments.quiet:
        print(f"Setup token (shown once): {token}")
        print(f"Stored in: {secret_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
