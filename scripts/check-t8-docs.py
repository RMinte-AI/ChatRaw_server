#!/usr/bin/env python3
"""Check T8 documentation, links, contracts, and public/private boundaries."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    ROOT / "AGENTS.md",
    ROOT / "README.md",
    ROOT / "docs" / "user-guide.md",
    ROOT / "docs" / "admin-guide.md",
    ROOT / "docs" / "plugin-developer-guide.md",
    ROOT / "docs" / "plugin-workspace-ui-guide.md",
    ROOT / "docs" / "module-developer-guide.md",
    ROOT / "docs" / "resident-module-integration-guide.md",
    ROOT / "docs" / "human-ai-development-guide.md",
    ROOT / "docs" / "deployment" / "server-and-modules.md",
    ROOT / "docs" / "release" / "release-process.md",
    ROOT / "docs" / "release" / "acceptance-status.md",
    ROOT / "docs" / "api" / "openapi.json",
    ROOT / "backend" / "contracts" / "module-manifest-v1.schema.json",
    ROOT / "backend" / "contracts" / "module-management-v1.schema.json",
    ROOT / "backend" / "contracts" / "module-task-v1.schema.json",
    ROOT / "backend" / "contracts" / "module-conformance-fixture-v1.schema.json",
    ROOT / "backend" / "contracts" / "module-plugin-sdk-v1.json",
    ROOT / "backend" / "contracts" / "plugin-ui-sdk-v1.json",
    ROOT / "backend" / "contracts" / "resident-integration-v1.schema.json",
    ROOT / "backend" / "contracts" / "resident-integration-sdk-v1.json",
    ROOT / "examples" / "reference-module" / "manifest.example.json",
    ROOT / "examples" / "reference-module" / "manifest.resident.example.json",
    ROOT / "examples" / "reference-module" / "conformance-fixture.json",
    ROOT / "ResidentIntegrations" / "reference-module-workbench" / "integration.json",
    ROOT / "ResidentIntegrations" / "reference-module-workbench" / "main.js",
]
PUBLIC_MODULE_FILES = [
    ROOT / "docs" / "plugin-workspace-ui-guide.md",
    ROOT / "docs" / "module-developer-guide.md",
    ROOT / "docs" / "resident-module-integration-guide.md",
    ROOT / "docs" / "human-ai-development-guide.md",
    ROOT / "backend" / "contracts" / "module-manifest-v1.schema.json",
    ROOT / "backend" / "contracts" / "module-management-v1.schema.json",
    ROOT / "backend" / "contracts" / "module-task-v1.schema.json",
    ROOT / "backend" / "contracts" / "module-conformance-fixture-v1.schema.json",
    ROOT / "backend" / "contracts" / "module-plugin-sdk-v1.json",
    ROOT / "backend" / "contracts" / "plugin-ui-sdk-v1.json",
    ROOT / "backend" / "contracts" / "resident-integration-v1.schema.json",
    ROOT / "backend" / "contracts" / "resident-integration-sdk-v1.json",
    ROOT / "examples" / "reference-module" / "manifest.example.json",
    ROOT / "examples" / "reference-module" / "manifest.resident.example.json",
    ROOT / "examples" / "reference-module" / "conformance-fixture.json",
    ROOT / "examples" / "reference-module" / "app.py",
    ROOT / "ResidentIntegrations" / "reference-module-workbench" / "integration.json",
    ROOT / "ResidentIntegrations" / "reference-module-workbench" / "main.js",
]
PRIVATE_MARKERS = [
    "/agent/resolve",
    "/agent/capability-detail",
    "/agent/invoke",
    "/agent/explain",
    "X-ChatRaw-Principal",
    "CHATRAW_AGENT_LINKDB_TOKEN",
]
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _check_links(path: Path) -> list[str]:
    errors = []
    text = path.read_text(encoding="utf-8")
    for target in LINK_PATTERN.findall(text):
        target = target.strip()
        if (
            not target
            or target.startswith(("#", "http://", "https://", "mailto:"))
        ):
            continue
        relative = target.split("#", 1)[0]
        if not relative:
            continue
        resolved = (path.parent / relative).resolve()
        if not resolved.exists():
            errors.append(f"{path.relative_to(ROOT)}: missing link target {target}")
    return errors


def main() -> int:
    errors = []
    for path in REQUIRED:
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"required documentation artifact is missing: {path}")

    for path in REQUIRED:
        if path.suffix == ".md" and path.is_file():
            errors.extend(_check_links(path))

    for path in PUBLIC_MODULE_FILES:
        text = path.read_text(encoding="utf-8")
        for marker in PRIVATE_MARKERS:
            if marker in text:
                errors.append(
                    f"private Agent protocol marker {marker!r} appears in "
                    f"{path.relative_to(ROOT)}"
                )

    for path in (
        ROOT / "README.md",
        ROOT / "docs" / "admin-guide.md",
        ROOT / "docs" / "human-ai-development-guide.md",
    ):
        if "PENDING_ONSITE" not in path.read_text(encoding="utf-8"):
            errors.append(f"{path.relative_to(ROOT)} lacks PENDING_ONSITE boundary")

    schema_paths = sorted(
        (ROOT / "backend" / "contracts").glob("*.schema.json")
    )
    schema_paths.extend(
        [
            ROOT / "backend" / "contracts" / "module-plugin-sdk-v1.json",
            ROOT / "backend" / "contracts" / "plugin-ui-sdk-v1.json",
            ROOT / "backend" / "contracts" / "resident-integration-sdk-v1.json",
        ]
    )
    for path in schema_paths:
        try:
            Draft202012Validator.check_schema(
                json.loads(path.read_text(encoding="utf-8"))
            )
        except Exception as error:
            errors.append(f"{path.relative_to(ROOT)} is invalid: {error}")

    openapi_path = ROOT / "docs" / "api" / "openapi.json"
    if openapi_path.is_file():
        openapi = json.loads(openapi_path.read_text(encoding="utf-8"))
        required_paths = {
            "/api/setup/admin",
            "/api/auth/login",
            "/api/module-tasks",
            "/api/admin/modules",
            "/api/resident-integrations",
        }
        missing_paths = required_paths - set(openapi.get("paths", {}))
        if missing_paths:
            errors.append(
                "OpenAPI snapshot lacks required paths: "
                + ", ".join(sorted(missing_paths))
            )

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(
        "T8 documentation and public contract boundary passed "
        f"({len(REQUIRED)} required artifacts)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
