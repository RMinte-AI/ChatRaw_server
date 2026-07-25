import copy
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import AsyncMock, patch

from aiohttp import web
from fastapi.testclient import TestClient

from backend import main
from backend.module_protocol import (
    MAX_MANIFEST_BYTES,
    ModuleProtocolError,
    digest_json,
    validate_config_update,
    validate_config_view,
    validate_manifest,
)
from backend.module_registry import (
    CONFIG_PATH,
    DISCONNECT_PATH,
    HEALTH_PATH,
    MANIFEST_PATH,
    PAIR_PATH,
    PURGE_PATH,
    READY_PATH,
    ModuleAddressPolicy,
    ModuleHttpClient,
    ModuleRegistry,
    ModuleRegistryError,
)


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = ROOT / "examples" / "reference-module"
REFERENCE_MANIFEST = json.loads(
    (REFERENCE_DIR / "manifest.example.json").read_text(encoding="utf-8")
)
REFERENCE_RESIDENT_MANIFEST = json.loads(
    (
        REFERENCE_DIR / "manifest.resident.example.json"
    ).read_text(encoding="utf-8")
)


class FakeAddressPolicy:
    def normalize(self, raw_url):
        if not isinstance(raw_url, str) or not raw_url.startswith("http://"):
            raise ModuleRegistryError(
                "module_address_not_allowed",
                "Module address is not allowed",
            )
        return raw_url.rstrip("/")


class FakeModuleClient:
    def __init__(self, manifest=None):
        self.address_policy = FakeAddressPolicy()
        self.manifest = copy.deepcopy(manifest or REFERENCE_MANIFEST)
        self.module_id = self.manifest["module_id"]
        self.instance_id = str(uuid.uuid4())
        self.token = "module-token-" + ("x" * 48)
        self.pairing_code = "pairing-code-" + ("x" * 24)
        self.pairing_available = True
        self.offline = False
        self.ready_override = None
        self.config = {
            "revision": "1",
            "values": {"greeting": "Hello", "uppercase": False},
            "secret_configured": {"service_key": False},
            "configured": True,
            "missing_required": [],
        }
        self.secret_digest = None
        self.calls = []

    async def request_json(
        self,
        base_url,
        path,
        *,
        method="GET",
        token=None,
        payload=None,
        max_bytes=65536,
    ):
        del base_url, max_bytes
        self.calls.append((method, path, copy.deepcopy(payload)))
        if self.offline:
            raise ModuleRegistryError(
                "module_unreachable",
                "Module is unreachable",
                status_code=502,
            )
        if path == PAIR_PATH:
            if (
                not self.pairing_available
                or payload.get("pairing_code") != self.pairing_code
            ):
                return 400, {"detail": "Pairing rejected"}
            self.pairing_available = False
            return 200, {
                "module_id": self.module_id,
                "instance_id": self.instance_id,
                "access_token": self.token,
            }
        if token != self.token:
            return 401, {"detail": "Authentication required"}
        if path == MANIFEST_PATH:
            return 200, copy.deepcopy(self.manifest)
        if path == HEALTH_PATH:
            return 200, {"status": "healthy"}
        if path == READY_PATH:
            ready = (
                self.config["configured"]
                if self.ready_override is None
                else self.ready_override
            )
            return 200, {
                "ready": ready,
                "reasons": (
                    []
                    if ready
                    else ["configuration_missing"]
                ),
            }
        if path == CONFIG_PATH and method == "GET":
            return 200, copy.deepcopy(self.config)
        if path == CONFIG_PATH and method == "PUT":
            if payload["revision"] != self.config["revision"]:
                return 409, {"detail": "Revision conflict"}
            for name, update in payload["secrets"].items():
                if name != "service_key":
                    return 400, {"detail": "Invalid secret"}
                if update["action"] == "replace":
                    self.secret_digest = hashlib.sha256(
                        update["value"].encode("utf-8")
                    ).hexdigest()
                elif update["action"] == "clear":
                    self.secret_digest = None
            revision = str(int(self.config["revision"]) + 1)
            self.config = {
                "revision": revision,
                "values": copy.deepcopy(payload["values"]),
                "secret_configured": {
                    "service_key": bool(self.secret_digest)
                },
                "configured": bool(
                    payload["values"].get("greeting", "").strip()
                ),
                "missing_required": (
                    []
                    if payload["values"].get("greeting", "").strip()
                    else ["greeting"]
                ),
            }
            return 200, copy.deepcopy(self.config)
        if path == DISCONNECT_PATH:
            return 200, {
                "disconnected": True,
                "data_preserved": True,
            }
        if path == PURGE_PATH:
            self.config = {
                "revision": str(int(self.config["revision"]) + 1),
                "values": {"greeting": "", "uppercase": False},
                "secret_configured": {"service_key": False},
                "configured": False,
                "missing_required": ["greeting"],
            }
            self.secret_digest = None
            return 200, {"purged": True}
        return 404, {"detail": "Not found"}


class ModuleManifestConformanceTests(unittest.TestCase):
    def test_reference_manifest_matches_machine_schema(self):
        manifest = validate_manifest(REFERENCE_MANIFEST)
        self.assertEqual(manifest["schema_version"], "1")
        self.assertEqual(manifest["actions"][0]["action_id"], "echo.task")
        self.assertTrue(manifest["actions"][0]["supports_stream"])

    def test_manifest_rejects_executable_ui_and_unknown_fields(self):
        for mutation in (
            lambda item: item.update({"html": "<p>unsafe</p>"}),
            lambda item: item.update({"description": "<script>x</script>"}),
        ):
            manifest = copy.deepcopy(REFERENCE_MANIFEST)
            mutation(manifest)
            with self.assertRaises(ModuleProtocolError):
                validate_manifest(manifest)

    def test_manifest_rejects_duplicate_actions_and_oversize(self):
        manifest = copy.deepcopy(REFERENCE_MANIFEST)
        manifest["actions"].append(copy.deepcopy(manifest["actions"][0]))
        with self.assertRaises(ModuleProtocolError) as duplicate:
            validate_manifest(manifest)
        self.assertEqual(duplicate.exception.code, "duplicate_action")
        with self.assertRaises(ModuleProtocolError) as oversized:
            validate_manifest(
                REFERENCE_MANIFEST,
                raw_size=MAX_MANIFEST_BYTES + 1,
            )
        self.assertEqual(oversized.exception.code, "manifest_too_large")

    def test_manifest_rejects_unsafe_or_unrenderable_schemas(self):
        manifests = []
        remote_reference = copy.deepcopy(REFERENCE_MANIFEST)
        remote_reference["actions"][0]["input_schema"] = {
            "$ref": "http://169.254.169.254/latest/meta-data"
        }
        manifests.append(remote_reference)
        regex_schema = copy.deepcopy(REFERENCE_MANIFEST)
        regex_schema["actions"][0]["input_schema"]["properties"]["text"][
            "pattern"
        ] = "(a+)+$"
        manifests.append(regex_schema)
        nested_config = copy.deepcopy(REFERENCE_MANIFEST)
        nested_config["config_schema"]["properties"]["greeting"] = {
            "type": "object",
            "additionalProperties": False,
            "properties": {},
        }
        manifests.append(nested_config)
        secret_default = copy.deepcopy(REFERENCE_MANIFEST)
        secret_default["config_schema"]["properties"]["service_key"][
            "default"
        ] = "must-not-be-exposed"
        manifests.append(secret_default)

        for manifest in manifests:
            with self.subTest(manifest=manifest):
                with self.assertRaises(ModuleProtocolError):
                    validate_manifest(manifest)

    def test_manifest_rejects_schema_depth_attack(self):
        manifest = copy.deepcopy(REFERENCE_MANIFEST)
        nested = {"type": "object"}
        cursor = nested
        for _ in range(30):
            child = {"type": "object"}
            cursor["properties"] = {"next": child}
            cursor = child
        manifest["config_schema"] = nested
        with self.assertRaises(ModuleProtocolError) as context:
            validate_manifest(manifest)
        self.assertEqual(context.exception.code, "json_too_deep")

    def test_config_view_enforces_schema_and_secret_state(self):
        schema = REFERENCE_MANIFEST["config_schema"]
        valid = {
            "revision": "1",
            "values": {"greeting": "Hello", "uppercase": False},
            "secret_configured": {"service_key": False},
            "configured": True,
            "missing_required": [],
        }
        validate_config_view(schema, valid)

        invalid_views = []
        wrong_type = copy.deepcopy(valid)
        wrong_type["values"]["uppercase"] = "false"
        invalid_views.append(wrong_type)
        missing_secret_state = copy.deepcopy(valid)
        missing_secret_state["secret_configured"] = {}
        invalid_views.append(missing_secret_state)
        empty_revision = copy.deepcopy(valid)
        empty_revision["revision"] = ""
        invalid_views.append(empty_revision)
        inconsistent_missing = copy.deepcopy(valid)
        inconsistent_missing["missing_required"] = ["greeting"]
        invalid_views.append(inconsistent_missing)

        for view in invalid_views:
            with self.subTest(view=view):
                with self.assertRaises(ModuleProtocolError):
                    validate_config_view(schema, view)

        constrained_schema = copy.deepcopy(schema)
        constrained_schema["properties"]["service_key"]["minLength"] = 8
        with self.assertRaises(ModuleProtocolError):
            validate_config_update(
                constrained_schema,
                {
                    "revision": "1",
                    "values": {
                        "greeting": "Hello",
                        "uppercase": False,
                    },
                    "secrets": {
                        "service_key": {
                            "action": "replace",
                            "value": "short",
                        }
                    },
                },
            )


class ModuleAddressPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def test_loopback_allowed_metadata_and_public_denied(self):
        policy = ModuleAddressPolicy()
        origin, addresses = await policy.validate_and_resolve(
            "http://127.0.0.1:8765"
        )
        self.assertEqual(origin, "http://127.0.0.1:8765")
        self.assertEqual(addresses, ["127.0.0.1"])
        for address in (
            "http://169.254.169.254",
            "http://8.8.8.8",
            "http://[::]",
        ):
            with self.assertRaises(ModuleRegistryError):
                await policy.validate_and_resolve(address)

    async def test_explicit_public_origin_requires_https(self):
        https_origin = "https://8.8.8.8"
        policy = ModuleAddressPolicy(allowed_origins={https_origin})
        origin, _addresses = await policy.validate_and_resolve(https_origin)
        self.assertEqual(origin, https_origin)
        http_policy = ModuleAddressPolicy(
            allowed_origins={"http://8.8.8.8"}
        )
        with self.assertRaises(ModuleRegistryError):
            await http_policy.validate_and_resolve("http://8.8.8.8")


class ModuleHttpTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        app = web.Application()
        async def redirect_handler(_request):
            raise web.HTTPFound(READY_PATH)

        async def oversized_handler(_request):
            return web.json_response(
                {"payload": "x" * (MAX_MANIFEST_BYTES + 1)}
            )

        async def invalid_handler(_request):
            return web.Response(
                text="<html>not json</html>",
                content_type="text/html",
            )

        app.router.add_get(HEALTH_PATH, redirect_handler)
        app.router.add_get(MANIFEST_PATH, oversized_handler)
        app.router.add_get(READY_PATH, invalid_handler)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await self.site.start()
        port = self.site._server.sockets[0].getsockname()[1]
        self.base_url = f"http://127.0.0.1:{port}"
        self.client = ModuleHttpClient(ModuleAddressPolicy())

    async def asyncTearDown(self):
        await self.runner.cleanup()

    async def test_redirect_invalid_content_type_and_oversize_are_rejected(self):
        with self.assertRaises(ModuleRegistryError) as redirected:
            await self.client.request_json(
                self.base_url,
                HEALTH_PATH,
            )
        self.assertEqual(
            redirected.exception.code,
            "module_redirect_forbidden",
        )
        with self.assertRaises(ModuleRegistryError) as invalid:
            await self.client.request_json(
                self.base_url,
                READY_PATH,
            )
        self.assertEqual(
            invalid.exception.code,
            "invalid_module_response",
        )
        with self.assertRaises(ModuleRegistryError) as oversized:
            await self.client.request_json(
                self.base_url,
                MANIFEST_PATH,
                max_bytes=MAX_MANIFEST_BYTES,
            )
        self.assertEqual(
            oversized.exception.code,
            "module_response_too_large",
        )


class ModuleRegistryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = Path(
            tempfile.mkdtemp(prefix="chatraw-t3-registry-")
        )
        with main.db.connection(write=True) as connection:
            connection.execute("DELETE FROM module_capability_grants")
            connection.execute("DELETE FROM module_feature_suites")
            connection.execute("DELETE FROM module_registrations")
        self.fake = FakeModuleClient()
        self.plugin = None
        self.resident = None
        self.audit_events = []
        self.registry = ModuleRegistry(
            main.db.db_path,
            self.temp_dir / "credentials",
            busy_timeout_ms=main.db.busy_timeout_ms,
            client=self.fake,
            plugin_lookup=lambda _plugin_id: self.plugin,
            resident_integration_lookup=lambda _integration_id: self.resident,
            audit=lambda *args: self.audit_events.append(args),
        )
        self.actor = self._ensure_actor("t3-registry-admin", "admin")

    async def asyncTearDown(self):
        with main.db.connection(write=True) as connection:
            connection.execute("DELETE FROM module_capability_grants")
            connection.execute("DELETE FROM module_feature_suites")
            connection.execute("DELETE FROM module_registrations")
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @staticmethod
    def _ensure_actor(username, role):
        user_id = str(uuid.uuid4())
        now = "2026-07-23T00:00:00Z"
        with main.db.connection(write=True) as connection:
            connection.execute(
                """
                INSERT INTO users (
                    id, username, password_hash, role, enabled,
                    created_at, updated_at, password_changed_at
                )
                VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET role = excluded.role,
                    enabled = 1
                """,
                (
                    user_id,
                    username,
                    main.auth_service.password_hasher.hash(
                        "T3-registry-password-2026"
                    ),
                    role,
                    now,
                    now,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT id FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        return row["id"]

    async def _pair(self):
        return await self.registry.pair(
            base_url="http://127.0.0.1:8765",
            pairing_code=self.fake.pairing_code,
            actor_user_id=self.actor,
        )

    async def _approved_ready(self):
        paired = await self._pair()
        self.registry.approve(
            paired["id"],
            manifest_digest=paired["manifest_digest"],
            approved_capabilities=paired["requested_host_capabilities"],
            actor_user_id=self.actor,
        )
        self.plugin = {
            "id": "reference-module-companion",
            "version": "1.0.0",
            "enabled": True,
        }
        await self.registry.check(
            paired["id"],
            actor_user_id=self.actor,
        )
        return self.registry.get(paired["id"])

    async def test_pair_stores_restricted_connection_and_redacts_response(self):
        paired = await self._pair()
        reviews = {
            item["capability"]: item
            for item in paired["capability_reviews"]
        }
        self.assertEqual(reviews["chat.read"]["risk"], "medium")
        self.assertEqual(reviews["resource.read"]["risk"], "medium")
        self.assertEqual(reviews["resource.stream"]["risk"], "medium")
        self.assertEqual(reviews["model.invoke"]["risk"], "high")
        self.assertTrue(
            all(
                item["effective_for_tasks"]
                for item in reviews.values()
            )
        )
        serialized = json.dumps(paired)
        self.assertNotIn("127.0.0.1", serialized)
        self.assertNotIn(self.fake.token, serialized)
        self.assertNotIn("credential", serialized)
        with main.db.connection() as connection:
            row = connection.execute(
                "SELECT * FROM module_registrations WHERE id = ?",
                (paired["id"],),
            ).fetchone()
        self.assertEqual(row["base_url"], "http://127.0.0.1:8765")
        self.assertEqual(
            row["credential_digest"],
            hashlib.sha256(self.fake.token.encode("utf-8")).hexdigest(),
        )
        self.assertNotIn(self.fake.token, json.dumps(dict(row)))
        credential_path = (
            self.temp_dir
            / "credentials"
            / f"{paired['id']}.token"
        )
        self.assertEqual(credential_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(
            credential_path.read_text(encoding="utf-8"),
            self.fake.token,
        )

    async def test_optional_resource_support_defaults_to_false(self):
        self.fake.manifest["actions"][0].pop("supports_resources", None)
        paired = await self._pair()
        self.assertFalse(paired["actions"][0]["supports_resources"])

    async def test_pair_code_is_single_use_and_identity_must_match(self):
        await self._pair()
        with self.assertRaises(ModuleRegistryError) as repeated:
            await self.registry.pair(
                base_url="http://127.0.0.1:8765",
                pairing_code=self.fake.pairing_code,
                actor_user_id=self.actor,
            )
        self.assertEqual(repeated.exception.code, "pairing_rejected")

        mismatch_fake = FakeModuleClient()
        mismatch_fake.module_id = "chatraw.reference.other"
        mismatch_registry = ModuleRegistry(
            main.db.db_path,
            self.temp_dir / "mismatch",
            busy_timeout_ms=main.db.busy_timeout_ms,
            client=mismatch_fake,
            plugin_lookup=lambda _plugin_id: None,
            audit=lambda *_args: None,
        )
        with self.assertRaises(ModuleRegistryError) as mismatch:
            await mismatch_registry.pair(
                base_url="http://127.0.0.1:8766",
                pairing_code=mismatch_fake.pairing_code,
                actor_user_id=self.actor,
            )
        self.assertEqual(
            mismatch.exception.code,
            "module_identity_mismatch",
        )

    async def test_protocol_incompatible_is_visible_and_cannot_be_approved(self):
        self.fake.manifest["protocol_version"] = "2.0.0"
        paired = await self._pair()
        self.assertEqual(paired["health_status"], "incompatible")
        self.assertEqual(paired["lifecycle_state"], "pending_review")
        with self.assertRaises(ModuleRegistryError) as approval:
            self.registry.approve(
                paired["id"],
                manifest_digest=paired["manifest_digest"],
                approved_capabilities=[],
                actor_user_id=self.actor,
            )
        self.assertEqual(approval.exception.code, "module_incompatible")

    async def test_feature_suite_lifecycle_and_plugin_states(self):
        paired = await self._pair()
        approved = self.registry.approve(
            paired["id"],
            manifest_digest=paired["manifest_digest"],
            approved_capabilities=paired["requested_host_capabilities"],
            actor_user_id=self.actor,
        )
        self.assertTrue(approved["reviewed"])
        checked = await self.registry.check(
            paired["id"],
            actor_user_id=self.actor,
        )
        self.assertEqual(
            checked["feature_suite"]["status"],
            "plugin_missing",
        )
        self.assertFalse(checked["can_enable"])

        self.plugin = {
            "id": "reference-module-companion",
            "version": "0.9.0",
            "enabled": True,
        }
        incompatible = await self.registry.check(
            paired["id"],
            actor_user_id=self.actor,
        )
        self.assertEqual(
            incompatible["feature_suite"]["status"],
            "plugin_incompatible",
        )
        self.plugin["version"] = "1.0.0"
        self.plugin["enabled"] = False
        disabled = await self.registry.check(
            paired["id"],
            actor_user_id=self.actor,
        )
        self.assertEqual(
            disabled["feature_suite"]["status"],
            "plugin_disabled",
        )
        self.plugin["enabled"] = True
        ready = await self.registry.check(
            paired["id"],
            actor_user_id=self.actor,
        )
        self.assertTrue(ready["can_enable"])
        enabled = await self.registry.enable(
            paired["id"],
            actor_user_id=self.actor,
        )
        self.assertEqual(enabled["lifecycle_state"], "enabled")
        draining = self.registry.drain(
            paired["id"],
            actor_user_id=self.actor,
        )
        self.assertEqual(draining["lifecycle_state"], "draining")
        final = self.registry.disable(
            paired["id"],
            actor_user_id=self.actor,
        )
        self.assertEqual(final["lifecycle_state"], "disabled")

    async def test_resident_integration_is_a_build_time_enable_gate(self):
        self.fake.manifest = copy.deepcopy(REFERENCE_RESIDENT_MANIFEST)
        paired = await self._pair()
        self.registry.approve(
            paired["id"],
            manifest_digest=paired["manifest_digest"],
            approved_capabilities=paired["requested_host_capabilities"],
            actor_user_id=self.actor,
        )
        missing = await self.registry.check(
            paired["id"],
            actor_user_id=self.actor,
        )
        self.assertEqual(
            missing["frontend_integration"]["status"],
            "resident_missing",
        )
        self.assertFalse(missing["can_enable"])

        self.resident = {
            "id": "reference-module-workbench",
            "version": "2.0.0",
            "module_id": "chatraw.reference.echo",
            "minimum_role": "member",
            "required_actions": [
                {
                    "action_id": "echo.task",
                    "version_range": ">=1.0.0,<2.0.0",
                }
            ],
        }
        incompatible = await self.registry.check(
            paired["id"],
            actor_user_id=self.actor,
        )
        self.assertEqual(
            incompatible["frontend_integration"]["status"],
            "resident_incompatible",
        )

        self.resident["version"] = "1.0.0"
        ready = await self.registry.check(
            paired["id"],
            actor_user_id=self.actor,
        )
        self.assertEqual(
            ready["frontend_integration"]["status"],
            "ready",
        )
        hidden_before_enable = self.registry.feature_status(
            ready["module_id"]
        )
        self.assertFalse(hidden_before_enable["visible"])
        self.assertEqual(hidden_before_enable["state"], "hidden")
        enabled = await self.registry.enable(
            paired["id"],
            actor_user_id=self.actor,
        )
        feature = self.registry.feature_status(enabled["module_id"])
        self.assertTrue(feature["visible"])
        self.assertTrue(feature["available"])
        self.assertEqual(feature["frontend_integration"]["mode"], "resident")
        self.assertIsNone(feature["companion_plugin"])

        self.resident = None
        unavailable = self.registry.feature_status(enabled["module_id"])
        self.assertTrue(unavailable["visible"])
        self.assertFalse(unavailable["available"])
        self.assertEqual(
            unavailable["reason"]["code"],
            "resident_missing",
        )
        with self.assertRaises(ModuleRegistryError) as blocked:
            self.registry.task_target(module_id=enabled["module_id"])
        self.assertEqual(blocked.exception.code, "resident_missing")

    async def test_resident_required_action_or_role_mismatch_is_incompatible(
        self,
    ):
        self.fake.manifest = copy.deepcopy(REFERENCE_RESIDENT_MANIFEST)
        self.resident = {
            "id": "reference-module-workbench",
            "version": "1.0.0",
            "module_id": "chatraw.reference.echo",
            "minimum_role": "member",
            "required_actions": [
                {
                    "action_id": "missing.action",
                    "version_range": ">=1.0.0,<2.0.0",
                }
            ],
        }
        paired = await self._pair()
        checked = await self.registry.check(
            paired["id"],
            actor_user_id=self.actor,
        )
        self.assertEqual(
            checked["frontend_integration"]["status"],
            "resident_incompatible",
        )

        self.resident["required_actions"][0]["action_id"] = "echo.task"
        self.fake.manifest["actions"][0]["minimum_role"] = "admin"
        checked = await self.registry.refresh(
            paired["id"],
            actor_user_id=self.actor,
        )
        self.assertEqual(
            checked["frontend_integration"]["status"],
            "resident_incompatible",
        )

    async def test_product_visibility_and_runtime_plugin_gate(self):
        ready = await self._approved_ready()
        before_enable = self.registry.feature_status(
            ready["module_id"]
        )
        self.assertEqual(before_enable["state"], "hidden")
        self.assertFalse(before_enable["visible"])

        enabled = await self.registry.enable(
            ready["id"],
            actor_user_id=self.actor,
        )
        available = self.registry.feature_status(
            enabled["module_id"]
        )
        self.assertEqual(available["state"], "available")
        self.assertTrue(available["visible"])
        self.assertTrue(available["available"])

        self.plugin["enabled"] = False
        unavailable = self.registry.feature_status(
            enabled["module_id"]
        )
        self.assertEqual(unavailable["state"], "unavailable")
        self.assertTrue(unavailable["visible"])
        self.assertFalse(unavailable["available"])
        self.assertEqual(
            unavailable["reason"]["code"],
            "plugin_disabled",
        )
        with self.assertRaises(ModuleRegistryError) as blocked:
            self.registry.task_target(module_id=enabled["module_id"])
        self.assertEqual(blocked.exception.code, "plugin_disabled")

    async def test_patch_stays_enabled_but_new_permission_requires_review(self):
        ready = await self._approved_ready()
        await self.registry.enable(
            ready["id"],
            actor_user_id=self.actor,
        )
        self.fake.manifest["module_version"] = "1.0.1"
        self.fake.calls.clear()
        patched = await self.registry.refresh(
            ready["id"],
            actor_user_id=self.actor,
        )
        self.assertEqual(patched["lifecycle_state"], "enabled")
        self.assertTrue(patched["reviewed"])
        self.assertEqual(patched["health_status"], "healthy")
        self.assertEqual(patched["ready_status"], "ready")
        self.assertEqual(patched["config_status"], "configured")
        self.assertIsNone(patched["recent_fault"])
        self.assertEqual(
            [(method, path) for method, path, _payload in self.fake.calls],
            [
                ("GET", MANIFEST_PATH),
                ("GET", HEALTH_PATH),
                ("GET", READY_PATH),
                ("GET", CONFIG_PATH),
            ],
        )

        self.fake.manifest["module_version"] = "1.1.0"
        self.fake.manifest["requested_host_capabilities"] = [
            "chat.context.read"
        ]
        changed = await self.registry.refresh(
            ready["id"],
            actor_user_id=self.actor,
        )
        self.assertEqual(changed["lifecycle_state"], "pending_review")
        self.assertFalse(changed["reviewed"])
        self.assertEqual(changed["granted_host_capabilities"], [])

    async def test_config_schema_change_requires_review(self):
        ready = await self._approved_ready()
        await self.registry.enable(
            ready["id"],
            actor_user_id=self.actor,
        )
        self.fake.manifest["module_version"] = "1.0.1"
        self.fake.manifest["config_schema"]["properties"][
            "second_service_key"
        ] = {
            "type": "string",
            "x-chatraw-secret": True,
        }

        changed = await self.registry.refresh(
            ready["id"],
            actor_user_id=self.actor,
        )

        self.assertEqual(changed["lifecycle_state"], "pending_review")
        self.assertFalse(changed["reviewed"])
        self.assertEqual(changed["granted_host_capabilities"], [])

    async def test_config_revision_and_secret_tri_state(self):
        paired = await self._pair()
        config = await self.registry.get_config(paired["id"])
        raw_secret = "reference-service-secret"
        replaced = await self.registry.update_config(
            paired["id"],
            {
                "revision": config["revision"],
                "values": {
                    "greeting": "Welcome",
                    "uppercase": True,
                },
                "secrets": {
                    "service_key": {
                        "action": "replace",
                        "value": raw_secret,
                    }
                },
            },
            actor_user_id=self.actor,
        )
        self.assertTrue(replaced["secret_configured"]["service_key"])
        self.assertNotIn(raw_secret, json.dumps(replaced))
        self.assertNotEqual(self.fake.secret_digest, raw_secret)
        with main.db.connection() as connection:
            stored = connection.execute(
                "SELECT * FROM module_registrations WHERE id = ?",
                (paired["id"],),
            ).fetchone()
        stored_text = json.dumps(dict(stored))
        self.assertNotIn(raw_secret, stored_text)
        self.assertNotIn("Welcome", stored_text)
        self.assertEqual(stored["health_status"], "healthy")
        self.assertEqual(stored["ready_status"], "ready")
        self.assertEqual(stored["config_status"], "configured")
        self.assertEqual(
            [
                (method, path)
                for method, path, _payload in self.fake.calls[-4:]
            ],
            [
                ("PUT", CONFIG_PATH),
                ("GET", HEALTH_PATH),
                ("GET", READY_PATH),
                ("GET", CONFIG_PATH),
            ],
        )

        with self.assertRaises(ModuleRegistryError) as conflict:
            await self.registry.update_config(
                paired["id"],
                {
                    "revision": config["revision"],
                    "values": {
                        "greeting": "Stale",
                        "uppercase": False,
                    },
                    "secrets": {
                        "service_key": {"action": "keep"}
                    },
                },
                actor_user_id=self.actor,
            )
        self.assertEqual(
            conflict.exception.code,
            "config_revision_conflict",
        )
        cleared = await self.registry.update_config(
            paired["id"],
            {
                "revision": replaced["revision"],
                "values": {
                    "greeting": "Welcome",
                    "uppercase": True,
                },
                "secrets": {
                    "service_key": {"action": "clear"}
                },
            },
            actor_user_id=self.actor,
        )
        self.assertFalse(cleared["secret_configured"]["service_key"])

    async def test_config_update_refreshes_not_ready_and_ready_state(self):
        paired = await self._pair()
        self.fake.ready_override = False
        waiting = await self.registry.update_config(
            paired["id"],
            {
                "revision": "1",
                "values": {
                    "greeting": "Waiting for dependency",
                    "uppercase": False,
                },
                "secrets": {
                    "service_key": {"action": "keep"}
                },
            },
            actor_user_id=self.actor,
        )
        self.assertTrue(waiting["configured"])
        module = self.registry.get(paired["id"])
        self.assertEqual(module["health_status"], "healthy")
        self.assertEqual(module["ready_status"], "not_ready")
        self.assertEqual(module["config_status"], "configured")

        self.fake.ready_override = True
        configured = await self.registry.update_config(
            paired["id"],
            {
                "revision": waiting["revision"],
                "values": {
                    "greeting": "Ready again",
                    "uppercase": False,
                },
                "secrets": {
                    "service_key": {"action": "keep"}
                },
            },
            actor_user_id=self.actor,
        )
        self.assertTrue(configured["configured"])
        module = self.registry.get(paired["id"])
        self.assertEqual(module["health_status"], "healthy")
        self.assertEqual(module["ready_status"], "ready")
        self.assertEqual(module["config_status"], "configured")

    async def test_offline_check_and_disconnect_preserves_remote_data(self):
        paired = await self._pair()
        self.fake.offline = True
        checked = await self.registry.check(
            paired["id"],
            actor_user_id=self.actor,
        )
        self.assertEqual(checked["health_status"], "unreachable")
        disconnected = await self.registry.disconnect(
            paired["id"],
            confirmation=paired["module_id"],
            actor_user_id=self.actor,
        )
        self.assertTrue(disconnected["module_data_preserved"])
        self.assertFalse(disconnected["remote_notified"])
        with self.assertRaises(ModuleRegistryError):
            self.registry.get(paired["id"])

    async def test_disconnect_survives_missing_local_credential(self):
        paired = await self._pair()
        credential_path = (
            self.temp_dir
            / "credentials"
            / f"{paired['id']}.token"
        )
        credential_path.unlink()
        disconnected = await self.registry.disconnect(
            paired["id"],
            confirmation=paired["module_id"],
            actor_user_id=self.actor,
        )
        self.assertTrue(disconnected["module_data_preserved"])
        self.assertFalse(disconnected["remote_notified"])
        with self.assertRaises(ModuleRegistryError):
            self.registry.get(paired["id"])

    async def test_malformed_config_response_is_incompatible(self):
        paired = await self._pair()
        self.fake.config["values"]["uppercase"] = "false"
        checked = await self.registry.check(
            paired["id"],
            actor_user_id=self.actor,
        )
        self.assertEqual(checked["health_status"], "incompatible")
        self.assertEqual(checked["ready_status"], "unknown")
        self.assertEqual(checked["config_status"], "unknown")

    async def test_purge_requires_support_and_independent_confirmation(self):
        paired = await self._pair()
        with self.assertRaises(ModuleRegistryError):
            await self.registry.purge_data(
                paired["id"],
                confirmation=paired["module_id"],
                actor_user_id=self.actor,
            )
        result = await self.registry.purge_data(
            paired["id"],
            confirmation=f"PURGE {paired['module_id']}",
            actor_user_id=self.actor,
        )
        self.assertEqual(result, {"purged": True})
        module = self.registry.get(paired["id"])
        self.assertEqual(module["lifecycle_state"], "disabled")
        self.assertEqual(module["config_status"], "missing")


class ModuleAdminApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(
            tempfile.mkdtemp(prefix="chatraw-t3-api-")
        )
        with main.db.connection(write=True) as connection:
            connection.execute("DELETE FROM module_capability_grants")
            connection.execute("DELETE FROM module_feature_suites")
            connection.execute("DELETE FROM module_registrations")
        self.fake = FakeModuleClient()
        self.plugin = None
        self.registry = ModuleRegistry(
            main.db.db_path,
            self.temp_dir / "credentials",
            busy_timeout_ms=main.db.busy_timeout_ms,
            client=self.fake,
            plugin_lookup=lambda _plugin_id: self.plugin,
            audit=main.auth_service.audit,
        )
        self.original_registry = main.module_registry
        main.module_registry = self.registry
        self.admin_cookie = self._login_user("t3-api-admin", "admin")
        self.member_cookie = self._login_user("t3-api-member", "member")
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()
        main.module_registry = self.original_registry
        with main.db.connection(write=True) as connection:
            connection.execute("DELETE FROM module_capability_grants")
            connection.execute("DELETE FROM module_feature_suites")
            connection.execute("DELETE FROM module_registrations")
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @staticmethod
    def _login_user(username, role):
        password = "T3-api-password-2026"
        now = "2026-07-23T00:00:00Z"
        user_id = str(uuid.uuid4())
        with main.db.connection(write=True) as connection:
            connection.execute(
                """
                INSERT INTO users (
                    id, username, password_hash, role, enabled,
                    created_at, updated_at, password_changed_at
                )
                VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    password_hash = excluded.password_hash,
                    role = excluded.role, enabled = 1,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    username,
                    main.auth_service.password_hasher.hash(password),
                    role,
                    now,
                    now,
                    now,
                ),
            )
        _principal, token = main.auth_service.login(username, password)
        return token

    def _headers(self, token):
        return {
            "Origin": "http://testserver",
            "Cookie": f"chatraw_session={token}",
        }

    def test_admin_pair_response_is_redacted_and_member_matrix_is_403(self):
        response = self.client.post(
            "/api/admin/modules/pair",
            headers=self._headers(self.admin_cookie),
            json={
                "base_url": "http://127.0.0.1:8765",
                "pairing_code": self.fake.pairing_code,
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        module = response.json()
        serialized = response.text
        self.assertNotIn("127.0.0.1", serialized)
        self.assertNotIn(self.fake.token, serialized)
        registration_id = module["id"]

        requests = [
            ("GET", "/api/admin/modules", None),
            ("GET", f"/api/admin/modules/{registration_id}", None),
            ("POST", "/api/admin/modules/pair", {}),
            (
                "POST",
                f"/api/admin/modules/{registration_id}/approve",
                {},
            ),
            (
                "POST",
                f"/api/admin/modules/{registration_id}/refresh",
                None,
            ),
            (
                "POST",
                f"/api/admin/modules/{registration_id}/check",
                None,
            ),
            (
                "GET",
                f"/api/admin/modules/{registration_id}/config",
                None,
            ),
            (
                "PUT",
                f"/api/admin/modules/{registration_id}/config",
                {},
            ),
            (
                "POST",
                f"/api/admin/modules/{registration_id}/enable",
                None,
            ),
            (
                "POST",
                f"/api/admin/modules/{registration_id}/drain",
                None,
            ),
            (
                "POST",
                f"/api/admin/modules/{registration_id}/disable",
                None,
            ),
            (
                "POST",
                f"/api/admin/modules/{registration_id}/disconnect",
                {},
            ),
            (
                "POST",
                f"/api/admin/modules/{registration_id}/purge-data",
                {},
            ),
        ]
        for method, path, payload in requests:
            member = self.client.request(
                method,
                path,
                headers=self._headers(self.member_cookie),
                json=payload,
            )
            with self.subTest(method=method, path=path):
                self.assertEqual(member.status_code, 403, member.text)

    def test_anonymous_module_management_is_401_and_core_ready_is_independent(self):
        self.assertEqual(
            self.client.get("/api/admin/modules").status_code,
            401,
        )
        self.fake.offline = True
        ready = self.client.get("/ready")
        self.assertEqual(ready.status_code, 200, ready.text)
        self.assertEqual(ready.json()["status"], "ready")

    def test_member_feature_status_is_safe_and_anonymous_is_rejected(self):
        paired = self.client.post(
            "/api/admin/modules/pair",
            headers=self._headers(self.admin_cookie),
            json={
                "base_url": "http://127.0.0.1:8765",
                "pairing_code": self.fake.pairing_code,
            },
        ).json()
        response = self.client.get(
            f"/api/module-features/{paired['module_id']}",
            headers=self._headers(self.member_cookie),
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["state"], "hidden")
        self.assertTrue(
            response.json()["actions"][0]["supports_resources"]
        )
        self.assertNotIn("base_url", response.text)
        self.assertNotIn("credential", response.text)
        self.assertNotIn("sha256", response.text)
        self.assertNotIn("trust", response.text)
        self.assertEqual(
            self.client.get(
                f"/api/module-features/{paired['module_id']}"
            ).status_code,
            401,
        )
        missing = self.client.get(
            "/api/module-features/chatraw.missing",
            headers=self._headers(self.member_cookie),
        )
        self.assertEqual(missing.status_code, 200, missing.text)
        self.assertEqual(missing.json()["state"], "hidden")

    def test_resident_catalog_is_authenticated_and_source_safe(self):
        anonymous = self.client.get("/api/resident-integrations")
        self.assertEqual(anonymous.status_code, 401)
        response = self.client.get(
            "/api/resident-integrations",
            headers=self._headers(self.member_cookie),
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["sdk_version"], "1.0.0")
        self.assertRegex(response.json()["bundle_version"], "^[0-9a-f]{64}$")
        self.assertEqual(
            response.json()["built_integration_ids"],
            ["reference-module-workbench"],
        )
        integration = response.json()["integrations"][0]
        self.assertEqual(
            integration["id"],
            "reference-module-workbench",
        )
        self.assertNotIn("main", integration)
        self.assertNotIn("styles", integration)
        self.assertNotIn("required_actions", integration)

    def test_resident_catalog_hides_admin_metadata_but_keeps_build_integrity_ids(
        self,
    ):
        original_catalog = main.resident_integration_catalog
        member_descriptor = copy.deepcopy(original_catalog.list()[0])

        class Catalog:
            bundle_version = "b" * 64

            @staticmethod
            def list():
                member = copy.deepcopy(member_descriptor)
                admin = copy.deepcopy(member)
                admin["id"] = "admin-only-resident"
                admin["minimum_role"] = "admin"
                return [member, admin]

        try:
            main.resident_integration_catalog = Catalog()
            response = self.client.get(
                "/api/resident-integrations",
                headers=self._headers(self.member_cookie),
            )
        finally:
            main.resident_integration_catalog = original_catalog
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json()["built_integration_ids"],
            ["admin-only-resident", "reference-module-workbench"],
        )
        self.assertEqual(
            [
                integration["id"]
                for integration in response.json()["integrations"]
            ],
            ["reference-module-workbench"],
        )

    def test_module_offline_does_not_affect_existing_chat(self):
        self.fake.offline = True
        settings = main.db.get_settings()
        previous_stream = settings.chat_settings.stream
        settings.chat_settings.stream = False
        main.db.save_settings(settings)
        try:
            with patch.object(
                main.llm_service,
                "chat_non_stream",
                new=AsyncMock(
                    return_value={
                        "content": "core chat still works",
                        "thinking": "",
                        "references": [],
                    }
                ),
            ):
                response = self.client.post(
                    "/api/chat",
                    headers=self._headers(self.member_cookie),
                    json={"message": "hello"},
                )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(
                response.json()["content"],
                "core chat still works",
            )
        finally:
            settings.chat_settings.stream = previous_stream
            main.db.save_settings(settings)


def _load_reference_module(data_dir, pairing_code, ttl_seconds):
    module_name = f"chatraw_reference_module_{uuid.uuid4().hex}"
    module_path = REFERENCE_DIR / "app.py"
    with patch.dict(
        os.environ,
        {
            "REFERENCE_MODULE_DATA_DIR": str(data_dir),
            "REFERENCE_MODULE_PAIRING_CODE": pairing_code,
            "REFERENCE_MODULE_PAIRING_TTL_SECONDS": str(ttl_seconds),
        },
        clear=False,
    ):
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    return module


class ReferenceModuleConformanceTests(unittest.TestCase):
    def test_reference_module_requires_pairing_code_and_never_prints_it(self):
        module_path = REFERENCE_DIR / "app.py"
        module_name = f"chatraw_reference_module_{uuid.uuid4().hex}"
        with patch.dict(
            os.environ,
            {"REFERENCE_MODULE_DATA_DIR": tempfile.gettempdir()},
            clear=True,
        ):
            spec = importlib.util.spec_from_file_location(
                module_name,
                module_path,
            )
            module = importlib.util.module_from_spec(spec)
            with self.assertRaisesRegex(
                RuntimeError,
                "REFERENCE_MODULE_PAIRING_CODE",
            ):
                spec.loader.exec_module(module)

        pairing_code = "reference-pairing-code-" + ("x" * 24)
        with tempfile.TemporaryDirectory(
            prefix="chatraw-reference-module-"
        ) as temp:
            output = io.StringIO()
            with redirect_stdout(output):
                _load_reference_module(temp, pairing_code, 600)
            self.assertNotIn(pairing_code, output.getvalue())

    def test_reference_module_pair_config_disconnect_and_purge(self):
        pairing_code = "reference-pairing-code-" + ("x" * 24)
        with tempfile.TemporaryDirectory(
            prefix="chatraw-reference-module-"
        ) as temp:
            reference = _load_reference_module(temp, pairing_code, 600)
            with TestClient(reference.app) as client:
                paired = client.post(
                    PAIR_PATH,
                    json={
                        "pairing_code": pairing_code,
                        "host": {
                            "product": "ChatRaw Server",
                            "module_protocol": "1.0.0",
                            "capability_base_url": "http://127.0.0.1:51111",
                        },
                    },
                )
                self.assertEqual(paired.status_code, 200, paired.text)
                token = paired.json()["access_token"]
                auth = {"Authorization": f"Bearer {token}"}
                repeated = client.post(
                    PAIR_PATH,
                    json={
                        "pairing_code": pairing_code,
                        "host": {
                            "product": "ChatRaw Server",
                            "module_protocol": "1.0.0",
                            "capability_base_url": "http://127.0.0.1:51111",
                        },
                    },
                )
                self.assertEqual(repeated.status_code, 400)
                manifest = client.get(MANIFEST_PATH, headers=auth)
                self.assertEqual(manifest.status_code, 200)
                validate_manifest(manifest.json())
                config = client.get(CONFIG_PATH, headers=auth).json()
                raw_secret = "reference-module-private-secret"
                updated = client.put(
                    CONFIG_PATH,
                    headers=auth,
                    json={
                        "revision": config["revision"],
                        "values": {
                            "greeting": "Hi",
                            "uppercase": True,
                        },
                        "secrets": {
                            "service_key": {
                                "action": "replace",
                                "value": raw_secret,
                            }
                        },
                    },
                )
                self.assertEqual(updated.status_code, 200, updated.text)
                self.assertNotIn(raw_secret, updated.text)
                state_text = reference.STATE_FILE.read_text(encoding="utf-8")
                self.assertNotIn(raw_secret, state_text)
                stale = client.put(
                    CONFIG_PATH,
                    headers=auth,
                    json={
                        "revision": config["revision"],
                        "values": {
                            "greeting": "Stale",
                            "uppercase": False,
                        },
                        "secrets": {
                            "service_key": {"action": "keep"}
                        },
                    },
                )
                self.assertEqual(stale.status_code, 409)
                purged = client.post(
                    PURGE_PATH,
                    headers=auth,
                    json={
                        "confirmation": "PURGE chatraw.reference.echo"
                    },
                )
                self.assertEqual(purged.json(), {"purged": True})
                disconnected = client.post(
                    DISCONNECT_PATH,
                    headers=auth,
                    json={"preserve_data": True},
                )
                self.assertEqual(disconnected.status_code, 200)
                self.assertTrue(reference.STATE_FILE.exists())
                self.assertEqual(
                    client.get(HEALTH_PATH, headers=auth).status_code,
                    401,
                )

    def test_reference_module_rejects_expired_pairing_code(self):
        pairing_code = "expired-pairing-code-" + ("x" * 24)
        with tempfile.TemporaryDirectory(
            prefix="chatraw-reference-expired-"
        ) as temp:
            reference = _load_reference_module(temp, pairing_code, -1)
            time.sleep(0.01)
            with TestClient(reference.app) as client:
                response = client.post(
                    PAIR_PATH,
                    json={
                        "pairing_code": pairing_code,
                        "host": {
                            "product": "ChatRaw Server",
                            "module_protocol": "1.0.0",
                            "capability_base_url": "http://127.0.0.1:51111",
                        },
                    },
                )
            self.assertEqual(response.status_code, 400)

    def test_reference_module_pairing_code_stays_consumed_after_restart(self):
        pairing_code = "restart-pairing-code-" + ("x" * 24)
        with tempfile.TemporaryDirectory(
            prefix="chatraw-reference-restart-"
        ) as temp:
            first = _load_reference_module(temp, pairing_code, 600)
            payload = {
                "pairing_code": pairing_code,
                "host": {
                    "product": "ChatRaw Server",
                    "module_protocol": "1.0.0",
                    "capability_base_url": "http://127.0.0.1:51111",
                },
            }
            with TestClient(first.app) as client:
                self.assertEqual(
                    client.post(PAIR_PATH, json=payload).status_code,
                    200,
                )
            restarted = _load_reference_module(temp, pairing_code, 600)
            with TestClient(restarted.app) as client:
                self.assertEqual(
                    client.post(PAIR_PATH, json=payload).status_code,
                    400,
                )

    def test_reference_module_has_no_chatraw_runtime_dependency(self):
        source = (REFERENCE_DIR / "app.py").read_text(encoding="utf-8")
        self.assertNotIn("from backend", source)
        self.assertNotIn("import backend", source)
        pairing_code = "independent-pairing-code-" + ("x" * 24)
        with tempfile.TemporaryDirectory(
            prefix="chatraw-reference-independent-"
        ) as temp:
            reference = _load_reference_module(temp, pairing_code, 600)
            route_paths = {route.path for route in reference.app.routes}
        self.assertEqual(
            {
                PAIR_PATH,
                MANIFEST_PATH,
                HEALTH_PATH,
                READY_PATH,
                CONFIG_PATH,
                DISCONNECT_PATH,
                PURGE_PATH,
                "/chatraw-module/v1/tasks",
                "/chatraw-module/v1/tasks/{task_id}",
                "/chatraw-module/v1/tasks/{task_id}/events",
                "/chatraw-module/v1/tasks/{task_id}/cancel",
                (
                    "/chatraw-module/v1/tasks/{task_id}/approvals/"
                    "{approval_id}"
                ),
                (
                    "/chatraw-module/v1/tasks/{task_id}/artifacts/"
                    "{artifact_id}"
                ),
                (
                    "/chatraw-module/v1/tasks/{task_id}/resources/"
                    "{resource_id}"
                ),
            },
            route_paths,
        )
