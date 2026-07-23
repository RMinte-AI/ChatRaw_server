#!/usr/bin/env python3
"""Module Protocol v1 offline and management-surface conformance checks."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.module_protocol import (  # noqa: E402
    ModuleProtocolError,
    permission_digest,
    protocol_is_compatible,
    validate_config_view,
    validate_manifest,
)


CONTRACT_DIR = REPOSITORY_ROOT / "backend" / "contracts"
REFERENCE_MANIFEST = (
    REPOSITORY_ROOT / "examples" / "reference-module" / "manifest.example.json"
)


class ConformanceError(RuntimeError):
    pass


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConformanceError(f"cannot read JSON from {path}: {error}") from error


def _validate_manifest_file(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    manifest = validate_manifest(json.loads(raw), raw_size=len(raw))
    if not protocol_is_compatible(manifest["protocol_version"]):
        raise ConformanceError(
            "manifest protocol_version is not supported by this Server"
        )
    return {
        "manifest": str(path.resolve()),
        "module_id": manifest["module_id"],
        "module_version": manifest["module_version"],
        "protocol_version": manifest["protocol_version"],
        "permission_digest": permission_digest(manifest),
        "actions": [action["action_id"] for action in manifest["actions"]],
    }


def check_contracts(manifests: list[Path]) -> dict[str, Any]:
    schema_files = sorted(CONTRACT_DIR.glob("module-*.schema.json"))
    if not schema_files:
        raise ConformanceError("no Module Protocol schemas were found")
    checked_schemas = []
    for path in schema_files:
        schema = _load_json(path)
        Draft202012Validator.check_schema(schema)
        checked_schemas.append(path.name)
    checked_manifests = [
        _validate_manifest_file(path) for path in (manifests or [REFERENCE_MANIFEST])
    ]
    return {
        "success": True,
        "schemas": checked_schemas,
        "manifests": checked_manifests,
    }


def _request_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    token: str | None = None,
    payload: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read(512 * 1024 + 1)
            if len(body) > 512 * 1024:
                raise ConformanceError(f"{path} response is too large")
            return response.status, json.loads(body)
    except urllib.error.HTTPError as error:
        body = error.read(64 * 1024)
        raise ConformanceError(
            f"{path} returned HTTP {error.code}: "
            f"{body.decode('utf-8', errors='replace')}"
        ) from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise ConformanceError(f"{path} request failed: {error}") from error


def probe_module(base_url: str, pairing_code: str) -> dict[str, Any]:
    _, identity = _request_json(
        base_url,
        "/chatraw-module/v1/pair",
        method="POST",
        payload={
            "pairing_code": pairing_code,
            "host": {
                "product": "ChatRaw Server",
                "module_protocol": "1.0.0",
            },
        },
    )
    if (
        not isinstance(identity, dict)
        or set(identity) != {"module_id", "instance_id", "access_token"}
        or not all(isinstance(value, str) and value for value in identity.values())
        or len(identity["access_token"]) < 32
    ):
        raise ConformanceError("pairing response does not match Module Protocol v1")
    token = identity["access_token"]

    _, raw_manifest = _request_json(
        base_url,
        "/chatraw-module/v1/manifest",
        token=token,
    )
    manifest = validate_manifest(raw_manifest)
    if manifest["module_id"] != identity["module_id"]:
        raise ConformanceError("pairing and manifest module_id values differ")
    if not protocol_is_compatible(manifest["protocol_version"]):
        raise ConformanceError("module protocol version is not compatible")

    _, health = _request_json(
        base_url,
        "/chatraw-module/v1/health",
        token=token,
    )
    if health != {"status": "healthy"}:
        raise ConformanceError("health response must be {'status':'healthy'}")

    _, ready = _request_json(
        base_url,
        "/chatraw-module/v1/ready",
        token=token,
    )
    if (
        not isinstance(ready, dict)
        or set(ready) != {"ready", "reasons"}
        or not isinstance(ready["ready"], bool)
        or not isinstance(ready["reasons"], list)
        or not all(isinstance(reason, str) for reason in ready["reasons"])
    ):
        raise ConformanceError("ready response does not match Module Protocol v1")

    _, config = _request_json(
        base_url,
        "/chatraw-module/v1/config",
        token=token,
    )
    validate_config_view(manifest["config_schema"], config)
    return {
        "success": True,
        "module_id": manifest["module_id"],
        "instance_id": identity["instance_id"],
        "module_version": manifest["module_version"],
        "protocol_version": manifest["protocol_version"],
        "permission_digest": permission_digest(manifest),
        "healthy": True,
        "ready": ready["ready"],
        "configured": config["configured"],
        "note": "The one-time pairing code was consumed by this probe.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Module Protocol v1 contracts and modules"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    contracts = commands.add_parser(
        "contracts",
        help="validate committed schemas and one or more manifest files",
    )
    contracts.add_argument(
        "--manifest",
        type=Path,
        action="append",
        default=[],
    )

    manifest = commands.add_parser(
        "manifest",
        help="validate one manifest without contacting a module",
    )
    manifest.add_argument("path", type=Path)

    probe = commands.add_parser(
        "probe",
        help="consume a fresh pairing code and check the management surface",
    )
    probe.add_argument("--base-url", required=True)
    probe.add_argument("--pairing-code", required=True)

    arguments = parser.parse_args()
    try:
        if arguments.command == "contracts":
            result = check_contracts(arguments.manifest)
        elif arguments.command == "manifest":
            result = {"success": True, **_validate_manifest_file(arguments.path)}
        else:
            result = probe_module(arguments.base_url, arguments.pairing_code)
    except (
        ConformanceError,
        ModuleProtocolError,
        OSError,
        json.JSONDecodeError,
        ValueError,
    ) as error:
        print(
            json.dumps(
                {"success": False, "error": str(error)},
                ensure_ascii=False,
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
