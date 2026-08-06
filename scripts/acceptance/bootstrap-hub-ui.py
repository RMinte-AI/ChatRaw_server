#!/usr/bin/env python3
"""Create an isolated nine-card hub fixture for real-browser acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
MODULES = (
    (Path("/Users/jay/ChatRaw-Finance/module_manifest.json"), Path("/Users/jay/ChatRaw-Finance/companion-plugin/toll-station-finance")),
    (Path("/Users/jay/数据填写/ChatRaw-SmartSpreadsheetAutofill-Module/contracts/module_manifest.json"), Path("/Users/jay/数据填写/ChatRaw-SmartSpreadsheetAutofill-Plugin")),
    (Path("/Users/jay/ChatRaw-Knowledge/module_manifest.json"), Path("/Users/jay/ChatRaw-Knowledge/plugin")),
    (Path("/Users/jay/ChatRaw-VehicleExemption/module_manifest.json"), Path("/Users/jay/ChatRaw-VehicleExemption/companion-plugin")),
    (Path("/Users/jay/ChatRaw-MobilePaymentReconciliation/module_manifest.json"), Path("/Users/jay/ChatRaw-MobilePaymentReconciliation/companion-plugin/toll-mobile-payment-reconciliation")),
    (Path("/Users/jay/ChatRaw-AIInspection/module_manifest.json"), Path("/Users/jay/ChatRaw-AIInspection/companion-plugin/toll-station-ai-inspection")),
    (Path("/Users/jay/ChatRaw-EnforcementVideoRenamer/module_manifest.json"), Path("/Users/jay/ChatRaw-EnforcementVideoRenamer/companion-plugin/toll-station-hub-video-renamer")),
    (Path("/Users/jay/ChatRaw-VehicleCaseReport/module_manifest.json"), Path("/Users/jay/ChatRaw-VehicleCaseReport/plugin/toll-vehicle-case-report")),
    (Path("/Users/jay/ChatRaw-Handwriting/module_manifest.json"), Path("/Users/jay/ChatRaw-Handwriting/plugin/chatraw-document-handwriting")),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = args.data_dir.resolve()
    if data_dir.exists() and any(data_dir.iterdir()):
        raise SystemExit("fixture data directory must be empty")
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["DATA_DIR"] = str(data_dir)
    os.environ["CHATRAW_TEST_MODE"] = "1"
    os.environ["CHATRAW_LOOPBACK_DEV"] = "1"

    from backend import main as server
    from backend.module_protocol import (
        canonical_json,
        digest_json,
        permission_digest,
        validate_manifest,
    )

    setup_token = server.SETUP_SECRET_FILE.read_text(encoding="utf-8").strip()
    admin = server.auth_service.create_first_admin(
        setup_token,
        "acceptance-admin",
        "Acceptance-password-2026",
    )
    admin_principal = server.Principal(
        admin["id"],
        admin["username"],
        admin["role"],
    )
    server.auth_service.create_user(
        admin_principal,
        "acceptance-member",
        "Member-password-2026",
        "member",
    )

    installed_root = Path(server.PLUGINS_INSTALLED_DIR)
    installed_root.mkdir(parents=True, exist_ok=True)
    plugin_config: dict[str, dict[str, bool]] = {}
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    for index, (manifest_path, plugin_source) in enumerate(MODULES, start=1):
        manifest = validate_manifest(json.loads(manifest_path.read_text(encoding="utf-8")))
        integration = manifest["frontend_integration"]
        plugin_id = integration["id"]
        shutil.copytree(plugin_source, installed_root / plugin_id)
        plugin_config[plugin_id] = {"enabled": True}

        manifest_digest = digest_json(manifest)
        permissions = permission_digest(manifest)
        registration_id = str(uuid.uuid4())
        with server.db.connection(write=True) as connection:
            connection.execute(
                """
                INSERT INTO module_registrations (
                    id, module_id, instance_id, base_url,
                    module_name, module_description,
                    module_version, protocol_version,
                    manifest_json, manifest_digest, permission_digest,
                    reviewed_manifest_digest, reviewed_permission_digest,
                    reviewed_module_version, credential_digest,
                    lifecycle_state, health_status, ready_status, config_status,
                    config_revision, created_by_user_id, reviewed_by_user_id,
                    created_at, updated_at, last_checked_at, enabled_once
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    'enabled', 'healthy', 'ready', 'configured',
                    'browser-fixture', ?, ?, ?, ?, ?, 1
                )
                """,
                (
                    registration_id,
                    manifest["module_id"],
                    f"browser-fixture-{index}",
                    f"http://127.0.0.1:{18700 + index}",
                    manifest["name"],
                    manifest["description"],
                    manifest["module_version"],
                    manifest["protocol_version"],
                    canonical_json(manifest),
                    manifest_digest,
                    permissions,
                    manifest_digest,
                    permissions,
                    manifest["module_version"],
                    hashlib.sha256(f"fixture-{index}".encode()).hexdigest(),
                    admin["id"],
                    admin["id"],
                    now,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO module_feature_suites (
                    registration_id, integration_mode, integration_id,
                    integration_version_range, dependency_status, checked_at
                ) VALUES (?, 'plugin', ?, ?, 'ready', ?)
                """,
                (
                    registration_id,
                    plugin_id,
                    integration["version_range"],
                    now,
                ),
            )

    hermes_source = ROOT / "Plugins/Plugin_market/hermes"
    shutil.copytree(hermes_source, installed_root / "hermes")
    plugin_config["hermes"] = {
        "enabled": True,
        "settings_values": {
            "baseUrl": "http://127.0.0.1:8642/v1",
            "model": "hermes-agent",
            "apiMode": "runs",
            "requestTimeoutSeconds": 180,
        },
    }
    server.save_plugin_config({"plugins": plugin_config, "api_keys": {}})
    print("username=acceptance-admin")
    print("password=Acceptance-password-2026")
    print("member_username=acceptance-member")
    print("member_password=Member-password-2026")
    print(f"data_dir={data_dir}")


if __name__ == "__main__":
    main()
