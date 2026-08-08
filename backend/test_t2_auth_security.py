import asyncio
import base64
import io
import json
import ipaddress
import stat
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import main
from backend.auth import AuthError, AuthService, ensure_setup_secret


ORIGIN = "http://testserver"
ADMIN_PASSWORD = "Admin-password-2026"
MEMBER_PASSWORD = "Member-password-2026"
OTHER_PASSWORD = "Other-password-2026"
VALID_LOGIN_BACKGROUND = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def write_headers():
    return {"Origin": ORIGIN, "Sec-Fetch-Site": "same-origin"}


def create_zip(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content, attributes in entries:
            info = zipfile.ZipInfo(name)
            if attributes is not None:
                info.create_system = 3
                info.external_attr = attributes << 16
            archive.writestr(info, content)
    return buffer.getvalue()


class T2AuthSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.setup_token = main.SETUP_SECRET_FILE.read_text(
            encoding="utf-8"
        ).strip()
        cls.public_client = TestClient(main.app)
        response = cls.public_client.post(
            "/api/setup/admin",
            headers=write_headers(),
            json={
                "setup_token": cls.setup_token,
                "username": "admin",
                "password": ADMIN_PASSWORD,
            },
        )
        assert response.status_code == 200, response.text
        cls.admin = cls.login("admin", ADMIN_PASSWORD)
        cls.member_id = main.auth_service.create_user(
            cls.admin_principal(),
            "member-a",
            MEMBER_PASSWORD,
            "member",
        )["id"]
        cls.other_id = main.auth_service.create_user(
            cls.admin_principal(),
            "member-b",
            OTHER_PASSWORD,
            "member",
        )["id"]

    @classmethod
    def admin_principal(cls):
        return main.auth_service.authenticate(
            cls.admin.cookies.get(main.SESSION_COOKIE)
        )

    @staticmethod
    def login(username, password):
        client = TestClient(main.app)
        response = client.post(
            "/api/auth/login",
            headers=write_headers(),
            json={"username": username, "password": password},
        )
        assert response.status_code == 200, response.text
        return client

    def setUp(self):
        with main.db.connection(write=True) as connection:
            for table in (
                "chat_skill_activations",
                "chat_compactions",
                "messages",
                "document_chunks",
                "chats",
                "documents",
            ):
                connection.execute(f"DELETE FROM {table}")
        main.save_plugin_config({"plugins": {}, "api_keys": {}})
        main.save_skill_config(main.default_skill_config())
        for path in (
            Path(main.PLUGINS_INSTALLED_DIR),
            Path(main.SKILLS_INSTALLED_DIR),
        ):
            if path.exists():
                for child in path.iterdir():
                    if child.is_dir() and not child.is_symlink():
                        import shutil
                        shutil.rmtree(child)
                    else:
                        child.unlink()
            path.mkdir(parents=True, exist_ok=True)

    def member_client(self):
        return self.login("member-a", MEMBER_PASSWORD)

    def other_client(self):
        return self.login("member-b", OTHER_PASSWORD)

    def test_setup_token_is_consumed_and_not_stored_in_plaintext(self):
        self.assertFalse(main.SETUP_SECRET_FILE.exists())
        with main.db.connection() as connection:
            row = connection.execute(
                "SELECT token_digest, consumed_at FROM setup_state"
            ).fetchone()
            self.assertIsNotNone(row["consumed_at"])
            self.assertNotEqual(row["token_digest"], self.setup_token)
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM users").fetchone()[0],
                3,
            )
        response = self.public_client.post(
            "/api/setup/admin",
            headers=write_headers(),
            json={
                "setup_token": self.setup_token,
                "username": "second-admin",
                "password": ADMIN_PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 409)

    def test_login_cookie_is_opaque_httponly_lax_and_fixed_path(self):
        client = TestClient(main.app)
        response = client.post(
            "/api/auth/login",
            headers=write_headers(),
            json={"username": "member-a", "password": MEMBER_PASSWORD},
        )
        self.assertEqual(response.status_code, 200)
        cookie = response.headers["set-cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=lax", cookie)
        self.assertIn("Path=/", cookie)
        token = client.cookies.get(main.SESSION_COOKIE)
        self.assertGreaterEqual(len(token), 64)
        self.assertNotIn(token, response.text)
        with main.db.connection() as connection:
            row = connection.execute(
                """
                SELECT token_digest FROM sessions
                WHERE user_id = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (self.member_id,),
            ).fetchone()
        self.assertEqual(len(row["token_digest"]), 64)
        self.assertNotEqual(row["token_digest"], token)

    def test_auth_and_user_errors_include_stable_localization_codes(self):
        invalid_login = self.public_client.post(
            "/api/auth/login",
            headers=write_headers(),
            json={"username": "member-a", "password": "wrong-password"},
        )
        self.assertEqual(invalid_login.status_code, 401)
        self.assertEqual(invalid_login.json()["code"], "invalid_credentials")

        invalid_body = self.public_client.post(
            "/api/auth/login",
            headers={**write_headers(), "Content-Type": "application/json"},
            content="{",
        )
        self.assertEqual(invalid_body.status_code, 400)
        self.assertEqual(invalid_body.json()["code"], "invalid_request")

        short_password = self.admin.post(
            "/api/admin/users",
            headers=write_headers(),
            json={
                "username": "localized-user",
                "password": "too-short",
                "role": "member",
            },
        )
        self.assertEqual(short_password.status_code, 400)
        self.assertEqual(
            short_password.json()["code"],
            "invalid_password_length",
        )

        duplicate = self.admin.post(
            "/api/admin/users",
            headers=write_headers(),
            json={
                "username": "member-a",
                "password": MEMBER_PASSWORD,
                "role": "member",
            },
        )
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.json()["code"], "username_in_use")

    def test_password_hashes_use_argon2id(self):
        with main.db.connection() as connection:
            hashes = [
                row["password_hash"]
                for row in connection.execute(
                    "SELECT password_hash FROM users"
                )
            ]
        self.assertTrue(hashes)
        self.assertTrue(all(value.startswith("$argon2id$") for value in hashes))

    def test_anonymous_route_enumeration_is_default_deny(self):
        public = main.PUBLIC_EXACT_PATHS
        self.assertIn("/brand-mark.svg", public)
        self.assertIn("/landing-field.svg", public)
        self.assertEqual(self.public_client.get("/brand-mark.svg").status_code, 200)
        self.assertEqual(self.public_client.get("/landing-field.svg").status_code, 200)
        checked = set()
        for route in main.app.routes:
            methods = getattr(route, "methods", None)
            if not methods:
                path = route.path or "/"
                response = self.public_client.get(path)
                self.assertEqual(response.status_code, 401, path)
                continue
            path = route.path
            path = path.replace("{chat_id}", "missing")
            path = path.replace("{doc_id}", "missing")
            path = path.replace("{model_id}", "missing")
            path = path.replace("{skill_name}", "missing")
            path = path.replace("{plugin_id}", "missing")
            path = path.replace("{plugin_folder}", "missing")
            path = path.replace("{user_id}", "missing")
            path = path.replace("{run_id:path}", "missing")
            path = path.replace("{filename:path}", "missing")
            path = path.replace("{path:path}", "missing")
            for method in methods - {"HEAD", "OPTIONS"}:
                key = (method, path)
                if key in checked:
                    continue
                checked.add(key)
                headers = write_headers() if method in main.STATE_CHANGING_METHODS else {}
                response = self.public_client.request(
                    method,
                    path,
                    headers=headers,
                )
                if route.path in public or route.path.startswith("/fonts/"):
                    self.assertNotEqual(response.status_code, 401, key)
                else:
                    self.assertEqual(response.status_code, 401, key)
        self.assertGreater(len(checked), 50)

    def test_origin_and_https_controls(self):
        client = self.member_client()
        response = client.post("/api/chats")
        self.assertEqual(response.status_code, 403)
        response = client.post(
            "/api/chats",
            headers={"Origin": "https://attacker.example"},
        )
        self.assertEqual(response.status_code, 403)
        response = client.post("/api/chats", headers=write_headers())
        self.assertEqual(response.status_code, 200)

    def test_module_bridge_source_check_is_cidr_bound(self):
        request = SimpleNamespace(
            client=SimpleNamespace(host="172.30.0.8")
        )
        with (
            patch.object(main, "CONTAINERIZED", True),
            patch.object(
                main.module_address_policy,
                "bridge_networks",
                [ipaddress.ip_network("172.30.0.0/24")],
            ),
        ):
            self.assertTrue(main._is_module_bridge_request(request))
            request.client.host = "172.31.0.8"
            self.assertFalse(main._is_module_bridge_request(request))
            request.client.host = "not-an-ip"
            self.assertFalse(main._is_module_bridge_request(request))
        with patch.object(main, "CONTAINERIZED", False):
            request.client.host = "172.30.0.8"
            self.assertFalse(main._is_module_bridge_request(request))

    def test_member_management_matrix_is_403(self):
        client = self.member_client()
        cases = [
            ("GET", "/api/admin/users"),
            ("GET", "/api/admin/audit"),
            ("POST", "/api/settings"),
            ("POST", "/api/models"),
            ("POST", "/api/models/verify"),
            ("DELETE", "/api/models/default-chat"),
            ("POST", "/api/skills/install"),
            ("POST", "/api/skills/upload"),
            ("POST", "/api/skills/example/toggle"),
            ("POST", "/api/skills/example/trust"),
            ("DELETE", "/api/skills/example"),
            ("GET", "/api/plugins/market"),
            ("POST", "/api/plugins/install"),
            ("POST", "/api/plugins/upload"),
            ("POST", "/api/plugins/example/toggle"),
            ("POST", "/api/plugins/example/settings"),
            ("DELETE", "/api/plugins/example"),
            ("GET", "/api/plugins/api-keys"),
            ("POST", "/api/plugins/api-key"),
        ]
        for method, path in cases:
            with self.subTest(method=method, path=path):
                headers = (
                    write_headers()
                    if method in main.STATE_CHANGING_METHODS
                    else {}
                )
                response = client.request(method, path, headers=headers)
                self.assertEqual(response.status_code, 403, response.text)

    def test_shared_chat_and_document_owner_rules(self):
        member = self.member_client()
        other = self.other_client()
        chat_response = member.post("/api/chats", headers=write_headers())
        self.assertEqual(chat_response.status_code, 200)
        chat_id = chat_response.json()["id"]
        self.assertIn(
            chat_id,
            {chat["id"] for chat in other.get("/api/chats").json()},
        )
        self.assertEqual(
            other.get(f"/api/chats/{chat_id}/messages").status_code,
            200,
        )
        self.assertEqual(
            other.patch(
                f"/api/chats/{chat_id}",
                headers=write_headers(),
                json={"title": "not allowed"},
            ).status_code,
            403,
        )
        self.assertEqual(
            other.delete(
                f"/api/chats/{chat_id}",
                headers=write_headers(),
            ).status_code,
            403,
        )
        self.assertEqual(
            member.patch(
                f"/api/chats/{chat_id}",
                headers=write_headers(),
                json={"title": "owned"},
            ).status_code,
            200,
        )

        doc_id = main.db.save_document(
            "shared.txt",
            "content",
            uploader_user_id=self.member_id,
        )
        self.assertIn(
            doc_id,
            {doc["id"] for doc in other.get("/api/documents").json()},
        )
        self.assertEqual(
            other.delete(
                f"/api/documents/{doc_id}",
                headers=write_headers(),
            ).status_code,
            403,
        )
        self.assertEqual(
            member.delete(
                f"/api/documents/{doc_id}",
                headers=write_headers(),
            ).status_code,
            200,
        )
        self.assertEqual(
            member.delete(
                f"/api/chats/{chat_id}",
                headers=write_headers(),
            ).status_code,
            200,
        )

    def test_agent_chat_history_is_private_per_user(self):
        member = self.member_client()
        other = self.other_client()
        response = member.post(
            "/api/agent/chats",
            headers=write_headers(),
        )
        self.assertEqual(response.status_code, 200, response.text)
        chat_id = response.json()["id"]

        self.assertIn(
            chat_id,
            {item["id"] for item in member.get("/api/agent/chats").json()},
        )
        self.assertNotIn(
            chat_id,
            {item["id"] for item in other.get("/api/agent/chats").json()},
        )
        self.assertNotIn(
            chat_id,
            {item["id"] for item in other.get("/api/chats").json()},
        )
        for method in ("get", "patch", "delete"):
            request = getattr(other, method)
            kwargs = {"headers": write_headers()} if method != "get" else {}
            if method == "patch":
                kwargs["json"] = {"title": "forbidden"}
            self.assertEqual(
                request(f"/api/agent/chats/{chat_id}" + (
                    "/messages" if method == "get" else ""
                ), **kwargs).status_code,
                404,
            )
        self.assertEqual(
            other.get(f"/api/chats/{chat_id}/messages").status_code,
            404,
        )
        self.assertEqual(
            other.patch(
                f"/api/chats/{chat_id}",
                headers=write_headers(),
                json={"title": "classic route"},
            ).status_code,
            404,
        )
        self.assertEqual(
            other.delete(
                f"/api/chats/{chat_id}",
                headers=write_headers(),
            ).status_code,
            404,
        )
        self.assertEqual(
            other.post(
                "/api/chat",
                headers=write_headers(),
                json={"chat_id": chat_id, "message": "cross-route"},
            ).status_code,
            404,
        )

        renamed = member.patch(
            f"/api/agent/chats/{chat_id}",
            headers=write_headers(),
            json={"title": "我的 Agent 会话"},
        )
        self.assertEqual(renamed.status_code, 200, renamed.text)
        self.assertEqual(
            member.delete(
                f"/api/agent/chats/{chat_id}",
                headers=write_headers(),
            ).status_code,
            200,
        )

    def test_agent_chat_clear_is_private_and_reports_counts(self):
        member = self.member_client()
        other = self.other_client()
        member_chat_ids = {
            member.post(
                "/api/agent/chats",
                headers=write_headers(),
            ).json()["id"]
            for _index in range(2)
        }
        other_chat_id = other.post(
            "/api/agent/chats",
            headers=write_headers(),
        ).json()["id"]
        classic_chat_id = member.post(
            "/api/chats",
            headers=write_headers(),
        ).json()["id"]
        first_member_chat_id = next(iter(member_chat_ids))
        message = main.db.add_message(
            first_member_chat_id,
            "user",
            "delete dependent records",
            author_user_id=self.member_id,
        )
        with main.db.connection(write=True) as connection:
            connection.execute(
                """
                INSERT INTO chat_compactions (
                    chat_id, summary, boundary_message_id,
                    boundary_created_at, updated_at
                ) VALUES (?, 'summary', ?, '2026-01-01', '2026-01-01')
                """,
                (first_member_chat_id, message.id),
            )
            connection.execute(
                """
                INSERT INTO chat_skill_activations (
                    id, chat_id, message_id, skill_name, created_at
                ) VALUES (?, ?, ?, 'test-skill', '2026-01-01')
                """,
                (
                    f"clear-skill-{first_member_chat_id}",
                    first_member_chat_id,
                    message.id,
                ),
            )
        main._context_compaction_locks[first_member_chat_id] = asyncio.Lock()

        cleared = member.delete(
            "/api/agent/chats",
            headers=write_headers(),
        )

        self.assertEqual(cleared.status_code, 200, cleared.text)
        self.assertEqual(
            cleared.json(),
            {
                "success": True,
                "deleted_count": len(member_chat_ids),
                "retained_count": 0,
            },
        )
        self.assertEqual(member.get("/api/agent/chats").json(), [])
        self.assertNotIn(
            first_member_chat_id,
            main._context_compaction_locks,
        )
        self.assertIn(
            classic_chat_id,
            {item["id"] for item in member.get("/api/chats").json()},
        )
        self.assertIn(
            other_chat_id,
            {item["id"] for item in other.get("/api/agent/chats").json()},
        )
        self.assertTrue(
            any(
                item["actor_user_id"] == self.member_id
                and item["action"] == "agent_chat.clear"
                and item["outcome"] == "success"
                and item["details"]["deleted_count"] == 2
                and item["details"]["retained_count"] == 0
                for item in main.auth_service.list_audit()
            )
        )
        with main.db.connection() as connection:
            for table in (
                "messages",
                "chat_compactions",
                "chat_skill_activations",
            ):
                self.assertEqual(
                    connection.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE chat_id = ?",
                        (first_member_chat_id,),
                    ).fetchone()[0],
                    0,
                )

    def test_agent_chat_clear_retains_active_generation_and_is_idempotent(self):
        member = self.member_client()
        retained = member.post(
            "/api/agent/chats",
            headers=write_headers(),
        ).json()
        deleted = member.post(
            "/api/agent/chats",
            headers=write_headers(),
        ).json()
        main._active_chat_generations.add(retained["id"])
        try:
            cleared = member.delete(
                "/api/agent/chats",
                headers=write_headers(),
            )
            self.assertEqual(cleared.status_code, 200, cleared.text)
            self.assertEqual(
                cleared.json(),
                {
                    "success": True,
                    "deleted_count": 1,
                    "retained_count": 1,
                },
            )
            remaining = {
                item["id"] for item in member.get("/api/agent/chats").json()
            }
            self.assertEqual(remaining, {retained["id"]})
            self.assertNotIn(deleted["id"], remaining)
            blocked_single_delete = member.delete(
                f"/api/agent/chats/{retained['id']}",
                headers=write_headers(),
            )
            self.assertEqual(
                blocked_single_delete.status_code,
                409,
                blocked_single_delete.text,
            )
        finally:
            main._active_chat_generations.discard(retained["id"])

        cleared = member.delete(
            "/api/agent/chats",
            headers=write_headers(),
        )
        self.assertEqual(
            cleared.json(),
            {"success": True, "deleted_count": 1, "retained_count": 0},
        )
        empty = member.delete(
            "/api/agent/chats",
            headers=write_headers(),
        )
        self.assertEqual(
            empty.json(),
            {"success": True, "deleted_count": 0, "retained_count": 0},
        )

    def test_feature_catalog_has_localized_host_categories_and_no_fallback_cards(self):
        catalog = self.member_client().get("/api/module-feature-catalog")
        self.assertEqual(catalog.status_code, 200, catalog.text)
        payload = catalog.json()
        self.assertEqual(
            [item["title"] for item in payload["categories"]],
            [
                {"en": "Data Hub", "zh": "数据中枢"},
                {"en": "Knowledge Hub", "zh": "知识中枢"},
                {"en": "Operations Hub", "zh": "业务中枢"},
            ],
        )
        self.assertEqual(payload["schema_version"], "2")
        self.assertEqual(payload["cards"], [])

    def test_dark_setting_is_normalized_and_public_identity_is_minimal(self):
        settings = self.admin.get("/api/settings").json()
        settings["ui_settings"]["theme_mode"] = "dark"
        settings["ui_settings"]["login_background_data"] = VALID_LOGIN_BACKGROUND
        settings["ui_settings"]["login_background_action"] = "replace"
        saved = self.admin.post(
            "/api/settings",
            headers=write_headers(),
            json=settings,
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(
            self.admin.get("/api/settings").json()["ui_settings"][
                "theme_mode"
            ],
            "light",
        )
        self.assertEqual(
            self.admin.get("/api/settings").json()["ui_settings"][
                "login_background_data"
            ],
            "",
        )
        identity = self.public_client.get("/api/settings/logo")
        self.assertEqual(identity.status_code, 200, identity.text)
        self.assertEqual(
            set(identity.json()),
            {"logo_data", "logo_text", "login_background_data"},
        )
        self.assertEqual(
            identity.json()["login_background_data"],
            VALID_LOGIN_BACKGROUND,
        )

        preserve = main.db.get_settings()
        preserve.ui_settings.login_background_data = ""
        preserve.ui_settings.login_background_action = "preserve"
        asyncio.run(main.save_settings(preserve))
        self.assertEqual(
            main.db.get_settings().ui_settings.login_background_data,
            VALID_LOGIN_BACKGROUND,
        )

        clear = main.db.get_settings()
        clear.ui_settings.login_background_action = "clear"
        asyncio.run(main.save_settings(clear))
        self.assertEqual(
            main.db.get_settings().ui_settings.login_background_data,
            "",
        )

    def test_login_background_rejects_untrusted_or_unbounded_data(self):
        with self.assertRaises(ValueError):
            main.UISettings(
                login_background_data="https://example.test/background.jpg"
            )

        oversized_bytes = (
            b"\x89PNG\r\n\x1a\n"
            + b"x" * main.LOGIN_BACKGROUND_MAX_BYTES
        )
        with self.assertRaises(ValueError):
            main.UISettings(
                login_background_data=(
                    "data:image/png;base64,"
                    + base64.b64encode(oversized_bytes).decode("ascii")
                )
            )

        missing = main.db.get_settings()
        missing.ui_settings.login_background_data = ""
        missing.ui_settings.login_background_action = "replace"
        with self.assertRaises(HTTPException) as error:
            asyncio.run(main.save_settings(missing))
        self.assertEqual(error.exception.status_code, 422)

    def test_feature_catalog_is_derived_from_registered_manifest(self):
        class CatalogRegistry:
            def list(self):
                return [{"id": "registration-1", "module_id": "example.module"}]

            def get(self, _registration_id):
                return {
                    "manifest": {
                        "frontend_integration": {
                            "mode": "plugin",
                            "id": "example-plugin",
                            "version_range": ">=1.0.0,<2.0.0",
                            "workspace_panel_id": "example-panel",
                            "catalog": {
                                "category_id": "data-hub",
                                "order": 5,
                                "title": {"en": "Example", "zh": "示例"},
                                "description": {
                                    "en": "Example feature",
                                    "zh": "示例功能",
                                },
                                "icon": "ri-pulse-line",
                            },
                        }
                    }
                }

            def feature_status(self, _module_id):
                return {
                    "available": True,
                    "visible": True,
                    "state": "available",
                    "reason": None,
                }

        original_registry = main.module_registry
        main.module_registry = CatalogRegistry()
        try:
            response = self.member_client().get("/api/module-feature-catalog")
        finally:
            main.module_registry = original_registry
        self.assertEqual(response.status_code, 200, response.text)
        card = response.json()["cards"][0]
        self.assertEqual(card["module_id"], "example.module")
        self.assertEqual(card["plugin_id"], "example-plugin")
        self.assertEqual(card["panel_id"], "example-panel")
        self.assertTrue(card["service_ready"])
        self.assertIsNone(card["service_reason"])
        self.assertFalse(card["runtime_ready"])
        self.assertFalse(card["available"])
    def test_legacy_resources_are_shared_but_admin_managed(self):
        member = self.member_client()
        legacy_chat = main.db.create_chat("legacy")
        legacy_doc = main.db.save_document("legacy.txt", "content")
        self.assertIn(
            legacy_chat.id,
            {item["id"] for item in member.get("/api/chats").json()},
        )
        self.assertIn(
            legacy_doc,
            {item["id"] for item in member.get("/api/documents").json()},
        )
        self.assertEqual(
            member.delete(
                f"/api/chats/{legacy_chat.id}",
                headers=write_headers(),
            ).status_code,
            403,
        )
        self.assertEqual(
            member.delete(
                f"/api/documents/{legacy_doc}",
                headers=write_headers(),
            ).status_code,
            403,
        )
        self.assertEqual(
            self.admin.delete(
                f"/api/chats/{legacy_chat.id}",
                headers=write_headers(),
            ).status_code,
            200,
        )
        self.assertEqual(
            self.admin.delete(
                f"/api/documents/{legacy_doc}",
                headers=write_headers(),
            ).status_code,
            200,
        )

    def test_member_can_chat_and_use_enabled_extensions(self):
        member = self.member_client()
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
                        "content": "reply",
                        "thinking": "",
                        "references": [],
                    }
                ),
            ):
                response = member.post(
                    "/api/chat",
                    headers=write_headers(),
                    json={"message": "hello"},
                )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["content"], "reply")
        finally:
            settings.chat_settings.stream = previous_stream
            main.db.save_settings(settings)

        plugin_dir = Path(main.PLUGINS_INSTALLED_DIR) / "runtime-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "main.js").write_text("window.runtimePlugin=true;")
        (plugin_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "id": "runtime-plugin",
                    "name": {"en": "Runtime"},
                    "main": "main.js",
                    "settings": [
                        {
                            "id": "public",
                            "type": "string",
                            "exposure": "runtime",
                        },
                        {"id": "adminOnly", "type": "string"},
                    ],
                }
            )
        )
        main.save_plugin_config(
            {
                "plugins": {
                    "runtime-plugin": {
                        "enabled": True,
                        "settings_values": {
                            "public": "visible",
                            "adminOnly": "hidden",
                        },
                    }
                },
                "api_keys": {},
            }
        )
        plugins = member.get("/api/plugins").json()
        self.assertEqual(len(plugins), 1)
        serialized = json.dumps(plugins)
        self.assertIn("visible", serialized)
        self.assertNotIn("adminOnly", serialized)
        self.assertNotIn("hidden", serialized)
        self.assertEqual(
            member.get("/api/plugins/runtime-plugin/main.js").status_code,
            200,
        )

    def test_session_revocation_for_logout_password_reset_and_disable(self):
        member = self.member_client()
        self.assertEqual(member.get("/api/me").status_code, 200)
        self.assertEqual(
            member.post("/api/auth/logout", headers=write_headers()).status_code,
            200,
        )
        self.assertEqual(member.get("/api/me").status_code, 401)

        member = self.member_client()
        self.assertEqual(
            self.admin.post(
                f"/api/admin/users/{self.member_id}/reset-password",
                headers=write_headers(),
                json={"new_password": "Member-reset-password-2026"},
            ).status_code,
            200,
        )
        self.assertEqual(member.get("/api/me").status_code, 401)
        self.assertEqual(
            self.public_client.post(
                "/api/auth/login",
                headers=write_headers(),
                json={"username": "member-a", "password": MEMBER_PASSWORD},
            ).status_code,
            401,
        )
        main.auth_service.reset_password(
            self.admin_principal(),
            self.member_id,
            MEMBER_PASSWORD,
        )
        member = self.member_client()
        self.assertEqual(
            self.admin.post(
                f"/api/admin/users/{self.member_id}/disable",
                headers=write_headers(),
            ).status_code,
            200,
        )
        self.assertEqual(member.get("/api/me").status_code, 401)
        main.auth_service.set_user_enabled(
            self.admin_principal(),
            self.member_id,
            True,
        )

    def test_change_password_revokes_all_sessions(self):
        first = self.other_client()
        second = self.other_client()
        response = first.post(
            "/api/me/password",
            headers=write_headers(),
            json={
                "current_password": OTHER_PASSWORD,
                "new_password": "Other-new-password-2026",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(first.get("/api/me").status_code, 401)
        self.assertEqual(second.get("/api/me").status_code, 401)
        main.auth_service.reset_password(
            self.admin_principal(),
            self.other_id,
            OTHER_PASSWORD,
        )

    def test_last_active_admin_cannot_be_disabled(self):
        response = self.admin.post(
            f"/api/admin/users/{self.admin_principal().id}/disable",
            headers=write_headers(),
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.admin.get("/api/me").status_code, 200)

    def test_model_and_plugin_secrets_are_never_returned(self):
        model_secret = "model-secret-raw-value"
        plugin_secret = "plugin-secret-raw-value"
        config = main.db.get_model_by_id("default-chat")
        config.api_key = model_secret
        main.db.save_model_config(config)
        main.save_plugin_config(
            {"plugins": {}, "api_keys": {"example": plugin_secret}}
        )
        model_response = self.admin.get("/api/models")
        key_response = self.admin.get("/api/plugins/api-keys")
        audit_response = self.admin.get("/api/admin/audit")
        combined = (
            model_response.text + key_response.text + audit_response.text
        )
        self.assertNotIn(model_secret, combined)
        self.assertNotIn(plugin_secret, combined)
        returned_model = next(
            item
            for item in model_response.json()
            if item["id"] == "default-chat"
        )
        self.assertTrue(returned_model["api_key_configured"])
        self.assertEqual(
            key_response.json()["api_keys"]["example"],
            {"configured": True},
        )
        with main.db.connection() as connection:
            session = connection.execute(
                "SELECT token_digest FROM sessions LIMIT 1"
            ).fetchone()
            self.assertIsNotNone(session)
            self.assertEqual(len(session["token_digest"]), 64)
            self.assertNotIn(
                self.admin.cookies.get(main.SESSION_COOKIE),
                session["token_digest"],
            )

    def test_secret_updates_have_preserve_replace_and_clear_semantics(self):
        model = main.db.get_model_by_id("default-chat")
        model.api_key = "original-model-secret"
        main.db.save_model_config(model)
        base_payload = main.public_model_config(model)
        base_payload.pop("api_key_configured")
        for action, supplied, expected in (
            ("preserve", None, "original-model-secret"),
            ("replace", "replacement-model-secret", "replacement-model-secret"),
            ("clear", None, ""),
        ):
            payload = dict(base_payload)
            payload["api_key_action"] = action
            if supplied is not None:
                payload["api_key"] = supplied
            response = self.admin.post(
                "/api/models",
                headers=write_headers(),
                json=payload,
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn(supplied or "original-model-secret", response.text)
            self.assertEqual(
                main.db.get_model_by_id("default-chat").api_key,
                expected,
            )

        main.save_plugin_config(
            {"plugins": {}, "api_keys": {"service": "original-plugin-secret"}}
        )
        for action, supplied, expected in (
            ("preserve", "", "original-plugin-secret"),
            ("replace", "replacement-plugin-secret", "replacement-plugin-secret"),
            ("clear", "", None),
        ):
            response = self.admin.post(
                "/api/plugins/api-key",
                headers=write_headers(),
                json={
                    "service_id": "service",
                    "action": action,
                    "api_key": supplied,
                },
            )
            self.assertEqual(response.status_code, 200)
            value = main.load_plugin_config()["api_keys"].get("service")
            self.assertEqual(value, expected)

    def test_proxy_policy_rejects_unapproved_metadata_and_oversize(self):
        for url in (
            "http://169.254.169.254/latest/meta-data",
            "http://127.0.0.1/admin",
            "https://api.tavily.com.evil.example/search",
        ):
            with self.subTest(url=url):
                with self.assertRaises(main.HTTPException) as error:
                    asyncio.run(
                        main.proxy_request(
                            main.ProxyRequest(
                                service_id="tavily",
                                url=url,
                                method="POST",
                            )
                        )
                    )
                self.assertEqual(error.exception.status_code, 403)

        plugin_dir = Path(main.PLUGINS_INSTALLED_DIR) / "tavily-search"
        plugin_dir.mkdir()
        (plugin_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "id": "tavily-search",
                    "main": "main.js",
                    "proxy": [{"id": "tavily"}],
                }
            )
        )
        (plugin_dir / "main.js").write_text("")
        main.save_plugin_config(
            {
                "plugins": {"tavily-search": {"enabled": True}},
                "api_keys": {},
            }
        )
        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(
                main.proxy_request(
                    main.ProxyRequest(
                        service_id="tavily",
                        url="https://api.tavily.com/search",
                        method="POST",
                        body={"value": "x" * (main.MAX_PROXY_REQUEST_SIZE + 1)},
                    )
                )
            )
        self.assertEqual(error.exception.status_code, 413)

    def test_proxy_blocks_redirects_and_redacts_reflected_secrets(self):
        plugin_dir = Path(main.PLUGINS_INSTALLED_DIR) / "tavily-search"
        plugin_dir.mkdir()
        (plugin_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "id": "tavily-search",
                    "main": "main.js",
                    "proxy": [{"id": "tavily"}],
                }
            )
        )
        (plugin_dir / "main.js").write_text("")
        secret = "proxy-reflection-secret"
        main.save_plugin_config(
            {
                "plugins": {"tavily-search": {"enabled": True}},
                "api_keys": {"tavily": secret},
            }
        )

        class Content:
            async def read(self, size):
                del size
                return json.dumps({"echo": secret}).encode()

        class Response:
            status = 302
            content = Content()

        class Context:
            async def __aenter__(self):
                return Response()

            async def __aexit__(self, *args):
                del args

        class Session:
            def __init__(self):
                self.allow_redirects = None

            def request(self, **kwargs):
                self.allow_redirects = kwargs["allow_redirects"]
                return Context()

        session = Session()
        with patch(
            "backend.main.get_http_session",
            new=AsyncMock(return_value=session),
        ):
            response = asyncio.run(
                main.proxy_request(
                    main.ProxyRequest(
                        service_id="tavily",
                        url="https://api.tavily.com/search",
                        method="POST",
                        body={"query": "test"},
                    )
                )
            )
        self.assertFalse(session.allow_redirects)
        self.assertEqual(response.status_code, 502)
        self.assertNotIn(secret, response.body.decode())
        self.assertNotIn(
            secret,
            main._hermes_upstream_error(500, secret).message,
        )

    def test_hermes_approval_is_bound_to_initiating_user(self):
        plugin_dir = Path(main.PLUGINS_INSTALLED_DIR) / main.HERMES_PLUGIN_ID
        plugin_dir.mkdir()
        (plugin_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "id": main.HERMES_PLUGIN_ID,
                    "main": "main.js",
                }
            )
        )
        (plugin_dir / "main.js").write_text("")
        main.save_plugin_config(
            {
                "plugins": {
                    main.HERMES_PLUGIN_ID: {
                        "enabled": True,
                        "settings_values": {},
                    }
                },
                "api_keys": {},
            }
        )
        run_id = "member-owned-run"
        main.register_active_hermes_run(
            run_id,
            "shared-chat",
            {
                "base_url": main.HERMES_DEFAULT_BASE_URL,
                "model": main.HERMES_DEFAULT_MODEL,
                "api_mode": main.HERMES_API_MODE_RUNS,
            },
            self.member_id,
        )
        main.update_active_hermes_run(
            run_id,
            pending_approval={"choices": ["once", "deny"]},
        )
        response = self.other_client().post(
            f"/api/hermes/runs/{run_id}/approval",
            headers=write_headers(),
            json={
                "chat_id": "shared-chat",
                "choice": "once",
                "resolve_all": False,
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("initiator", response.json()["error"])

    def test_plugin_zip_rejects_traversal_symlink_and_preserves_existing(self):
        manifest = json.dumps(
            {"id": "safe-plugin", "main": "main.js"}
        )
        safe = create_zip(
            [
                ("safe-plugin/manifest.json", manifest, None),
                ("safe-plugin/main.js", "window.safe=true;", None),
            ]
        )
        with tempfile.TemporaryDirectory(prefix="chatraw-t2-plugin-") as temp:
            staged_manifest, source = main.stage_plugin_archive(
                safe,
                Path(temp),
            )
            self.assertEqual(staged_manifest["id"], "safe-plugin")
            main.atomic_install_plugin("safe-plugin", source)
        installed_main = (
            Path(main.PLUGINS_INSTALLED_DIR) / "safe-plugin" / "main.js"
        )
        self.assertEqual(installed_main.read_text(), "window.safe=true;")

        bad_archives = [
            create_zip(
                [
                    ("../escape", "bad", None),
                    ("manifest.json", manifest, None),
                    ("main.js", "bad", None),
                ]
            ),
            create_zip(
                [
                    ("manifest.json", manifest, None),
                    ("main.js", "bad", None),
                    ("link", "target", stat.S_IFLNK | 0o777),
                ]
            ),
        ]
        for archive in bad_archives:
            with self.subTest():
                with tempfile.TemporaryDirectory(
                    prefix="chatraw-t2-plugin-bad-"
                ) as temp:
                    with self.assertRaises(main.PluginArchiveError):
                        main.stage_plugin_archive(archive, Path(temp))
                self.assertEqual(
                    installed_main.read_text(),
                    "window.safe=true;",
                )

    def test_concurrent_setup_creates_exactly_one_admin(self):
        with tempfile.TemporaryDirectory(prefix="chatraw-t2-setup-") as temp:
            root = Path(temp)
            database = main.Database(str(root / "chatraw.db"))
            secret_file = root / "secrets" / "setup-token"
            token = ensure_setup_secret(secret_file)
            service = AuthService(database.db_path, secret_file)
            barrier = threading.Barrier(4)
            results = []

            def create(index):
                barrier.wait()
                try:
                    service.create_first_admin(
                        token,
                        f"admin-{index}",
                        f"Concurrent-password-{index}-2026",
                    )
                    results.append("success")
                except AuthError:
                    results.append("denied")

            threads = [
                threading.Thread(target=create, args=(index,))
                for index in range(4)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(results.count("success"), 1)
            with database.connection() as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM users WHERE role = 'admin'"
                    ).fetchone()[0],
                    1,
                )

    def test_audit_covers_login_users_denials_and_shared_deletes(self):
        member = self.member_client()
        chat = member.post("/api/chats", headers=write_headers()).json()
        member.delete(
            f"/api/chats/{chat['id']}",
            headers=write_headers(),
        )
        member.get("/api/admin/users")
        actions = {
            item["action"]
            for item in self.admin.get("/api/admin/audit").json()["items"]
        }
        self.assertIn("auth.login", actions)
        self.assertIn("admin.user.create", actions)
        self.assertIn("rbac.denied", actions)
        self.assertIn("chat.delete", actions)


if __name__ == "__main__":
    unittest.main()
