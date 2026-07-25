import asyncio
import hashlib
import json
import tempfile
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import main
from backend.auth import AuthError, AuthService, ensure_setup_secret
from backend.module_tasks import ModuleTaskError, ModuleTaskService


ORIGIN = "http://testserver"
ADMIN_PASSWORD = "Admin-password-2026"
MEMBER_PASSWORD = "Member-password-2026"


class UserManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            prefix="chatraw-user-management-"
        )
        root = Path(self.temp.name)
        self.database = main.Database(str(root / "chatraw.db"))
        secret_file = root / "secrets" / "setup-token"
        setup_token = ensure_setup_secret(secret_file)
        self.service = AuthService(self.database.db_path, secret_file)
        admin = self.service.create_first_admin(
            setup_token,
            "admin",
            ADMIN_PASSWORD,
        )
        self.admin_id = admin["id"]
        self.admin_principal, self.admin_token = self.service.login(
            "admin",
            ADMIN_PASSWORD,
        )
        member = self.service.create_user(
            self.admin_principal,
            "member",
            MEMBER_PASSWORD,
            "member",
        )
        self.member_id = member["id"]

        self.original_auth_service = main.auth_service
        main.auth_service = self.service
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()
        main.auth_service = self.original_auth_service
        self.temp.cleanup()

    @staticmethod
    def _headers(token):
        return {
            "Origin": ORIGIN,
            "Cookie": f"{main.SESSION_COOKIE}={token}",
        }

    def _create_user(self, username, role, password=None):
        password = password or f"{username}-password-2026"
        user = self.service.create_user(
            self.admin_principal,
            username,
            password,
            role,
        )
        return user, password

    def _user_row(self, user_id):
        with self.database.connection() as connection:
            return connection.execute(
                """
                SELECT id, username, role, enabled, updated_at
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()

    def _session_row(self, token):
        with self.database.connection() as connection:
            return connection.execute(
                """
                SELECT user_id, revoked_at
                FROM sessions
                WHERE token_digest = ?
                """,
                (hashlib.sha256(token.encode("utf-8")).hexdigest(),),
            ).fetchone()

    def _insert_capability(self, creator_user_id, label):
        task_id = f"task-{label}-{uuid.uuid4()}"
        token = f"capability-{label}-{uuid.uuid4()}"
        token_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = "2026-07-25T00:00:00Z"
        with self.database.connection(write=True) as connection:
            connection.execute(
                """
                INSERT INTO module_tasks (
                    id, registration_id, module_id, module_version,
                    action_id, action_version, action_contract_json,
                    config_revision, creator_user_id, chat_id,
                    idempotency_key, request_digest, state,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    f"registration-{label}",
                    "com.example.user-management",
                    "1.0.0",
                    "test.read",
                    "1.0.0",
                    "{}",
                    "revision-1",
                    creator_user_id,
                    f"idempotency-{label}-{uuid.uuid4()}",
                    f"digest-{uuid.uuid4()}",
                    "running",
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO module_capability_tokens (
                    token_digest, task_id, registration_id, capability,
                    scope_json, use_count, max_uses, created_at,
                    expires_at, revoked_at
                ) VALUES (?, ?, ?, 'chat.read', ?, 0, NULL, ?, ?, NULL)
                """,
                (
                    token_digest,
                    task_id,
                    f"registration-{label}",
                    json.dumps({"chat_id": f"chat-{label}"}),
                    now,
                    "2099-01-01T00:00:00Z",
                ),
            )
        return token, token_digest

    def _capability_row(self, token_digest):
        with self.database.connection() as connection:
            return connection.execute(
                """
                SELECT use_count, revoked_at
                FROM module_capability_tokens
                WHERE token_digest = ?
                """,
                (token_digest,),
            ).fetchone()

    def test_role_api_has_strict_body_and_member_is_forbidden(self):
        _, member_token = self.service.login("member", MEMBER_PASSWORD)
        path = f"/api/admin/users/{self.member_id}/role"

        forbidden = self.client.put(
            path,
            headers=self._headers(member_token),
            json={"role": "admin"},
        )
        self.assertEqual(forbidden.status_code, 403)

        for payload in (
            {},
            {"role": "owner"},
            {"role": "member", "unexpected": True},
        ):
            with self.subTest(payload=payload):
                response = self.client.put(
                    path,
                    headers=self._headers(self.admin_token),
                    json=payload,
                )
                self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self._user_row(self.member_id)["role"], "member")

    def test_member_promotion_revokes_sessions_but_not_capabilities(self):
        _, member_token = self.service.login("member", MEMBER_PASSWORD)
        _, capability_digest = self._insert_capability(
            self.member_id,
            "promotion",
        )

        response = self.client.put(
            f"/api/admin/users/{self.member_id}/role",
            headers=self._headers(self.admin_token),
            json={"role": "admin"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"success": True})
        self.assertEqual(self._user_row(self.member_id)["role"], "admin")
        self.assertIsNotNone(self._session_row(member_token)["revoked_at"])
        self.assertIsNone(
            self._capability_row(capability_digest)["revoked_at"]
        )
        self.assertIsNone(self.service.authenticate(member_token))

    def test_admin_demotion_revokes_sessions_and_capabilities(self):
        user, password = self._create_user("target-admin", "admin")
        _, target_token = self.service.login(user["username"], password)
        _, capability_digest = self._insert_capability(
            user["id"],
            "demotion",
        )

        response = self.client.put(
            f"/api/admin/users/{user['id']}/role",
            headers=self._headers(self.admin_token),
            json={"role": "member"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self._user_row(user["id"])["role"], "member")
        self.assertIsNotNone(self._session_row(target_token)["revoked_at"])
        self.assertIsNotNone(
            self._capability_row(capability_digest)["revoked_at"]
        )

    def test_disabled_target_can_change_role_without_being_reenabled(self):
        self.service.set_user_enabled(
            self.admin_principal,
            self.member_id,
            False,
        )

        response = self.client.put(
            f"/api/admin/users/{self.member_id}/role",
            headers=self._headers(self.admin_token),
            json={"role": "admin"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        row = self._user_row(self.member_id)
        self.assertEqual(row["role"], "admin")
        self.assertEqual(row["enabled"], 0)

    def test_same_role_is_idempotent_and_preserves_session_and_timestamp(self):
        _, member_token = self.service.login("member", MEMBER_PASSWORD)
        before = self._user_row(self.member_id)

        response = self.client.put(
            f"/api/admin/users/{self.member_id}/role",
            headers=self._headers(self.admin_token),
            json={"role": "member"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        after = self._user_row(self.member_id)
        self.assertEqual(after["updated_at"], before["updated_at"])
        self.assertIsNone(self._session_row(member_token)["revoked_at"])
        self.assertEqual(
            self.service.authenticate(member_token).id,
            self.member_id,
        )
        audit = next(
            item
            for item in self.service.list_audit()
            if item["action"] == "admin.user.role.update"
        )
        self.assertEqual(
            audit["details"],
            {
                "old_role": "member",
                "new_role": "member",
                "changed": False,
            },
        )

    def test_self_role_reset_and_disable_are_rejected_and_audited(self):
        requests = (
            (
                "put",
                f"/api/admin/users/{self.admin_id}/role",
                {"role": "member"},
                "admin.user.role.update",
            ),
            (
                "post",
                f"/api/admin/users/{self.admin_id}/reset-password",
                {"new_password": "New-admin-password-2026"},
                "admin.user.reset_password",
            ),
            (
                "post",
                f"/api/admin/users/{self.admin_id}/disable",
                None,
                "admin.user.disable",
            ),
        )
        for method, path, payload, action in requests:
            with self.subTest(action=action):
                response = getattr(self.client, method)(
                    path,
                    headers=self._headers(self.admin_token),
                    json=payload,
                )
                self.assertEqual(response.status_code, 409, response.text)
                self.assertEqual(
                    response.json()["code"],
                    "self_user_management_forbidden",
                )

        denied_actions = {
            item["action"]
            for item in self.service.list_audit()
            if item["outcome"] == "denied"
        }
        self.assertTrue(
            {
                "admin.user.role.update",
                "admin.user.reset_password",
                "admin.user.disable",
            }.issubset(denied_actions)
        )

    def test_last_enabled_admin_remains_protected(self):
        role_response = self.client.put(
            f"/api/admin/users/{self.admin_id}/role",
            headers=self._headers(self.admin_token),
            json={"role": "member"},
        )
        disable_response = self.client.post(
            f"/api/admin/users/{self.admin_id}/disable",
            headers=self._headers(self.admin_token),
        )

        self.assertEqual(role_response.status_code, 409)
        self.assertEqual(disable_response.status_code, 409)
        with self.database.connection() as connection:
            enabled_admins = connection.execute(
                """
                SELECT COUNT(*) FROM users
                WHERE role = 'admin' AND enabled = 1
                """
            ).fetchone()[0]
        self.assertEqual(enabled_admins, 1)

    def test_stale_demoted_or_disabled_actor_is_rechecked_and_denied(self):
        for state in ("demoted", "disabled"):
            with self.subTest(state=state):
                user, password = self._create_user(
                    f"stale-{state}",
                    "admin",
                )
                stale_principal, _ = self.service.login(
                    user["username"],
                    password,
                )
                with self.database.connection(write=True) as connection:
                    if state == "demoted":
                        connection.execute(
                            "UPDATE users SET role = 'member' WHERE id = ?",
                            (user["id"],),
                        )
                    else:
                        connection.execute(
                            "UPDATE users SET enabled = 0 WHERE id = ?",
                            (user["id"],),
                        )

                with self.assertRaises(AuthError) as raised:
                    self.service.create_user(
                        stale_principal,
                        f"forbidden-{state}",
                        "Forbidden-password-2026",
                        "member",
                    )
                self.assertEqual(raised.exception.status_code, 403)
                self.assertEqual(
                    raised.exception.code,
                    "administrator_required",
                )
                self.assertFalse(
                    any(
                        item["username"] == f"forbidden-{state}"
                        for item in self.service.list_users()
                    )
                )

                denial = next(
                    item
                    for item in self.service.list_audit()
                    if item["actor_user_id"] == user["id"]
                    and item["action"] == "admin.user.create"
                    and item["outcome"] == "denied"
                )
                self.assertEqual(
                    denial["details"]["reason"],
                    "actor_not_active_admin",
                )

    def test_concurrent_admin_changes_leave_one_enabled_administrator(self):
        other, password = self._create_user("concurrent-admin", "admin")
        other_principal, _ = self.service.login(other["username"], password)
        barrier = threading.Barrier(2)

        def demote_other():
            barrier.wait()
            self.service.set_user_role(
                self.admin_principal,
                other["id"],
                "member",
            )

        def disable_first():
            barrier.wait()
            self.service.set_user_enabled(
                other_principal,
                self.admin_id,
                False,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(demote_other),
                executor.submit(disable_first),
            ]
            outcomes = []
            for future in futures:
                try:
                    future.result()
                    outcomes.append("success")
                except AuthError as error:
                    outcomes.append(error.code)

        self.assertEqual(outcomes.count("success"), 1)
        self.assertEqual(outcomes.count("administrator_required"), 1)
        with self.database.connection() as connection:
            enabled_admins = connection.execute(
                """
                SELECT COUNT(*) FROM users
                WHERE role = 'admin' AND enabled = 1
                """
            ).fetchone()[0]
        self.assertEqual(enabled_admins, 1)

    def test_disabled_creator_fails_closed_in_preflight_and_consume(self):
        token, token_digest = self._insert_capability(
            self.member_id,
            "disabled-creator",
        )
        with self.database.connection(write=True) as connection:
            connection.execute(
                "UPDATE users SET enabled = 0 WHERE id = ?",
                (self.member_id,),
            )

        task_service = ModuleTaskService(
            self.database.db_path,
            busy_timeout_ms=self.database.busy_timeout_ms,
            registry=SimpleNamespace(
                capability_base_url="http://127.0.0.1:51111"
            ),
            audit=lambda *_args: None,
        )
        with self.assertRaises(ModuleTaskError) as consumed:
            task_service._consume_capability(token, "chat.read")
        self.assertEqual(consumed.exception.status_code, 401)

        with self.assertRaises(ModuleTaskError) as preflight:
            asyncio.run(
                task_service._preflight_capability(token, "chat.read")
            )
        self.assertEqual(preflight.exception.status_code, 401)
        self.assertEqual(self._capability_row(token_digest)["use_count"], 0)
        self.assertIsNone(
            self._capability_row(token_digest)["revoked_at"]
        )

    def test_capability_revoke_failure_rolls_back_role_and_sessions(self):
        user, password = self._create_user("rollback-admin", "admin")
        _, target_token = self.service.login(user["username"], password)
        _, capability_digest = self._insert_capability(
            user["id"],
            "rollback",
        )

        with patch.object(
            self.service,
            "_revoke_user_capabilities",
            side_effect=RuntimeError("injected capability revoke failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "injected capability revoke failure",
            ):
                self.service.set_user_role(
                    self.admin_principal,
                    user["id"],
                    "member",
                )

        self.assertEqual(self._user_row(user["id"])["role"], "admin")
        self.assertIsNone(self._session_row(target_token)["revoked_at"])
        self.assertIsNone(
            self._capability_row(capability_digest)["revoked_at"]
        )
        self.assertFalse(
            any(
                item["action"] == "admin.user.role.update"
                and item["target_id"] == user["id"]
                and item["outcome"] == "success"
                for item in self.service.list_audit()
            )
        )
