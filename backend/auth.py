import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

try:
    from .db_runtime import database_connection
except ImportError:
    from db_runtime import database_connection


SESSION_COOKIE = "chatraw_session"
SESSION_TTL_DAYS = 30
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 64
PASSWORD_MIN_LENGTH = 12


class AuthError(RuntimeError):
    def __init__(
        self,
        message: str,
        status_code: int = 400,
        *,
        code: str = "authentication_failed",
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


@dataclass(frozen=True)
class Principal:
    id: str
    username: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def validate_username(username: Any) -> str:
    if not isinstance(username, str):
        raise AuthError("username must be a string", code="invalid_username_type")
    username = username.strip()
    if not USERNAME_MIN_LENGTH <= len(username) <= USERNAME_MAX_LENGTH:
        raise AuthError(
            f"username must be {USERNAME_MIN_LENGTH}-{USERNAME_MAX_LENGTH} characters",
            code="invalid_username_length",
        )
    if not all(character.isalnum() or character in "._-" for character in username):
        raise AuthError(
            "username contains unsupported characters",
            code="invalid_username_characters",
        )
    return username


def validate_password(password: Any) -> str:
    if not isinstance(password, str) or len(password) < PASSWORD_MIN_LENGTH:
        raise AuthError(
            f"password must be at least {PASSWORD_MIN_LENGTH} characters",
            code="invalid_password_length",
        )
    if len(password) > 1024:
        raise AuthError("password is too long", code="invalid_password_too_long")
    return password


class AuthService:
    def __init__(
        self,
        db_path: str,
        setup_secret_file: Path,
        *,
        busy_timeout_ms: int = 5_000,
        password_hasher: Optional[PasswordHasher] = None,
    ):
        self.db_path = db_path
        self.setup_secret_file = setup_secret_file.resolve()
        self.busy_timeout_ms = busy_timeout_ms
        self.password_hasher = password_hasher or PasswordHasher()
        self.initialize_setup_secret()

    def connection(self, *, write: bool = False, immediate: bool = False):
        return database_connection(
            self.db_path,
            busy_timeout_ms=self.busy_timeout_ms,
            write=write,
            immediate=immediate,
        )

    def initialize_setup_secret(self) -> None:
        with self.connection() as connection:
            user_count = connection.execute(
                "SELECT COUNT(*) FROM users"
            ).fetchone()[0]
            setup = connection.execute(
                "SELECT token_digest, consumed_at FROM setup_state WHERE singleton = 1"
            ).fetchone()
        if user_count:
            return
        if setup is not None:
            if setup["consumed_at"] is not None:
                return
            if not self.setup_secret_file.is_file():
                raise RuntimeError("unconsumed setup secret file is missing")
            mode = self.setup_secret_file.stat().st_mode & 0o777
            if mode != 0o600:
                raise RuntimeError("setup secret file permissions must be 0600")
            token = self.setup_secret_file.read_text(encoding="utf-8").strip()
            if not hmac.compare_digest(
                setup["token_digest"],
                token_digest(token),
            ):
                raise RuntimeError("setup secret file does not match setup state")
            return
        if not self.setup_secret_file.is_file():
            raise RuntimeError(
                "setup secret is missing; run scripts/prepare-server-secrets.py"
            )
        mode = self.setup_secret_file.stat().st_mode & 0o777
        if mode != 0o600:
            raise RuntimeError("setup secret file permissions must be 0600")
        token = self.setup_secret_file.read_text(encoding="utf-8").strip()
        if len(token) < 43:
            raise RuntimeError("setup token is not high entropy")
        with self.connection(write=True, immediate=True) as connection:
            existing = connection.execute(
                "SELECT 1 FROM setup_state WHERE singleton = 1"
            ).fetchone()
            users = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            if existing is None and not users:
                connection.execute(
                    """
                    INSERT INTO setup_state
                        (singleton, token_digest, created_at, consumed_at)
                    VALUES (1, ?, ?, NULL)
                    """,
                    (token_digest(token), utc_now()),
                )

    def setup_status(self) -> dict[str, bool]:
        with self.connection() as connection:
            admin_exists = connection.execute(
                """
                SELECT 1 FROM users
                WHERE role = 'admin' AND enabled = 1
                LIMIT 1
                """
            ).fetchone() is not None
        return {"setup_required": not admin_exists}

    def create_first_admin(
        self,
        setup_token: str,
        username: Any,
        password: Any,
    ) -> dict[str, str]:
        username = validate_username(username)
        password = validate_password(password)
        password_hash = self.password_hasher.hash(password)
        now = utc_now()
        user_id = str(uuid.uuid4())
        with self.connection(write=True, immediate=True) as connection:
            state = connection.execute(
                """
                SELECT token_digest, consumed_at
                FROM setup_state
                WHERE singleton = 1
                """
            ).fetchone()
            admin_exists = connection.execute(
                "SELECT 1 FROM users WHERE role = 'admin' LIMIT 1"
            ).fetchone()
            valid_token = (
                state is not None
                and state["consumed_at"] is None
                and hmac.compare_digest(
                    state["token_digest"],
                    token_digest(setup_token or ""),
                )
            )
            if admin_exists or not valid_token:
                self._audit(
                    connection,
                    None,
                    "setup.admin.create",
                    "user",
                    None,
                    "denied",
                    {"reason": "setup_unavailable"},
                )
                raise AuthError(
                    "setup is unavailable",
                    409,
                    code="setup_unavailable",
                )
            try:
                connection.execute(
                    """
                    INSERT INTO users
                        (id, username, password_hash, role, enabled,
                         created_at, updated_at, password_changed_at)
                    VALUES (?, ?, ?, 'admin', 1, ?, ?, ?)
                    """,
                    (user_id, username, password_hash, now, now, now),
                )
            except sqlite3.IntegrityError as error:
                raise AuthError(
                    "username is already in use",
                    409,
                    code="username_in_use",
                ) from error
            connection.execute(
                "UPDATE setup_state SET consumed_at = ? WHERE singleton = 1",
                (now,),
            )
            self._audit(
                connection,
                user_id,
                "setup.admin.create",
                "user",
                user_id,
                "success",
                {"role": "admin"},
            )
        try:
            self.setup_secret_file.unlink(missing_ok=True)
        except OSError:
            pass
        return {"id": user_id, "username": username, "role": "admin"}

    def login(self, username: Any, password: Any) -> tuple[Principal, str]:
        normalized = validate_username(username)
        if not isinstance(password, str):
            password = ""
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT id, username, password_hash, role, enabled
                FROM users
                WHERE username = ? COLLATE NOCASE
                """,
                (normalized,),
            ).fetchone()
        valid = False
        if row is not None:
            try:
                valid = self.password_hasher.verify(row["password_hash"], password)
            except (VerifyMismatchError, InvalidHashError):
                valid = False
        if row is None or not valid or not row["enabled"]:
            self.audit(
                None,
                "auth.login",
                "user",
                row["id"] if row is not None else None,
                "denied",
                {"username": normalized},
            )
            raise AuthError(
                "invalid username or password",
                401,
                code="invalid_credentials",
            )
        if self.password_hasher.check_needs_rehash(row["password_hash"]):
            with self.connection(write=True) as connection:
                connection.execute(
                    "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                    (self.password_hasher.hash(password), utc_now(), row["id"]),
                )
        token = secrets.token_urlsafe(48)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=SESSION_TTL_DAYS)
        with self.connection(write=True) as connection:
            connection.execute(
                """
                INSERT INTO sessions
                    (token_digest, user_id, created_at, expires_at, revoked_at)
                VALUES (?, ?, ?, ?, NULL)
                """,
                (
                    token_digest(token),
                    row["id"],
                    now.isoformat().replace("+00:00", "Z"),
                    expires_at.isoformat().replace("+00:00", "Z"),
                ),
            )
            self._audit(
                connection,
                row["id"],
                "auth.login",
                "session",
                None,
                "success",
                {},
            )
        return Principal(row["id"], row["username"], row["role"]), token

    def authenticate(self, token: Optional[str]) -> Optional[Principal]:
        if not token:
            return None
        now = utc_now()
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT users.id, users.username, users.role
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token_digest = ?
                  AND sessions.revoked_at IS NULL
                  AND sessions.expires_at > ?
                  AND users.enabled = 1
                """,
                (token_digest(token), now),
            ).fetchone()
        if row is None:
            return None
        return Principal(row["id"], row["username"], row["role"])

    def logout(self, token: Optional[str], actor: Principal) -> None:
        if not token:
            return
        with self.connection(write=True) as connection:
            connection.execute(
                """
                UPDATE sessions
                SET revoked_at = ?
                WHERE token_digest = ? AND revoked_at IS NULL
                """,
                (utc_now(), token_digest(token)),
            )
            self._audit(
                connection,
                actor.id,
                "auth.logout",
                "session",
                None,
                "success",
                {},
            )

    def change_password(
        self,
        actor: Principal,
        current_password: Any,
        new_password: Any,
    ) -> None:
        new_password = validate_password(new_password)
        with self.connection() as connection:
            row = connection.execute(
                "SELECT password_hash FROM users WHERE id = ?",
                (actor.id,),
            ).fetchone()
        try:
            valid = row is not None and self.password_hasher.verify(
                row["password_hash"], current_password
            )
        except (VerifyMismatchError, InvalidHashError):
            valid = False
        if not valid:
            raise AuthError(
                "current password is incorrect",
                403,
                code="current_password_incorrect",
            )
        now = utc_now()
        with self.connection(write=True, immediate=True) as connection:
            connection.execute(
                """
                UPDATE users
                SET password_hash = ?, password_changed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (self.password_hasher.hash(new_password), now, now, actor.id),
            )
            self._revoke_user_sessions(connection, actor.id, now)
            self._audit(
                connection,
                actor.id,
                "auth.password.change",
                "user",
                actor.id,
                "success",
                {},
            )

    def list_users(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT id, username, role, enabled, created_at, updated_at
                FROM users
                ORDER BY username COLLATE NOCASE
                """
            ).fetchall()
        result = []
        for row in rows:
            user = dict(row)
            user["enabled"] = bool(user["enabled"])
            result.append(user)
        return result

    def create_user(
        self,
        actor: Principal,
        username: Any,
        password: Any,
        role: Any,
    ) -> dict[str, Any]:
        username = validate_username(username)
        password = validate_password(password)
        if role not in {"admin", "member"}:
            raise AuthError(
                "role must be admin or member",
                code="invalid_role",
            )
        user_id = str(uuid.uuid4())
        now = utc_now()
        password_hash = self.password_hasher.hash(password)
        denial: Optional[AuthError] = None
        with self.connection(write=True, immediate=True) as connection:
            denial = self._active_admin_denial(connection, actor)
            if denial is None:
                try:
                    connection.execute(
                        """
                        INSERT INTO users
                            (id, username, password_hash, role, enabled,
                             created_at, updated_at, password_changed_at)
                        VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                        """,
                        (
                            user_id,
                            username,
                            password_hash,
                            role,
                            now,
                            now,
                            now,
                        ),
                    )
                except sqlite3.IntegrityError as error:
                    raise AuthError(
                        "username is already in use",
                        409,
                        code="username_in_use",
                    ) from error
                self._audit(
                    connection,
                    actor.id,
                    "admin.user.create",
                    "user",
                    user_id,
                    "success",
                    {"role": role},
                )
        if denial is not None:
            self._raise_audited_denial(
                actor,
                "admin.user.create",
                user_id,
                denial,
                {"reason": "actor_not_active_admin"},
            )
        return {
            "id": user_id,
            "username": username,
            "role": role,
            "enabled": True,
            "created_at": now,
            "updated_at": now,
        }

    def set_user_enabled(
        self,
        actor: Principal,
        user_id: str,
        enabled: bool,
    ) -> None:
        now = utc_now()
        action = "admin.user.enable" if enabled else "admin.user.disable"
        denial: Optional[AuthError] = None
        denial_details: dict[str, Any] = {}
        with self.connection(write=True, immediate=True) as connection:
            denial = self._active_admin_denial(connection, actor)
            if denial is not None:
                denial_details = {"reason": "actor_not_active_admin"}
            else:
                row = connection.execute(
                    "SELECT id, role, enabled FROM users WHERE id = ?",
                    (user_id,),
                ).fetchone()
                if row is None:
                    raise AuthError("user not found", 404, code="user_not_found")
                if not enabled and user_id == actor.id:
                    denial = AuthError(
                        "administrators cannot disable their own account",
                        409,
                        code="self_user_management_forbidden",
                    )
                    denial_details = {"reason": "self_disable"}
                elif not enabled and row["role"] == "admin" and row["enabled"]:
                    active_admins = connection.execute(
                        """
                        SELECT COUNT(*) FROM users
                        WHERE role = 'admin' AND enabled = 1
                        """
                    ).fetchone()[0]
                    if active_admins <= 1:
                        denial = AuthError(
                            "cannot disable the last active admin",
                            409,
                            code="last_active_admin",
                        )
                        denial_details = {"reason": "last_active_admin"}
                if denial is None:
                    connection.execute(
                        "UPDATE users SET enabled = ?, updated_at = ? WHERE id = ?",
                        (1 if enabled else 0, now, user_id),
                    )
                    if not enabled:
                        self._revoke_user_sessions(connection, user_id, now)
                        self._revoke_user_capabilities(connection, user_id, now)
                    self._audit(
                        connection,
                        actor.id,
                        action,
                        "user",
                        user_id,
                        "success",
                        {},
                    )
        if denial is not None:
            self._raise_audited_denial(
                actor,
                action,
                user_id,
                denial,
                denial_details,
            )

    def set_user_role(
        self,
        actor: Principal,
        user_id: str,
        role: Any,
    ) -> None:
        if role not in {"admin", "member"}:
            raise AuthError(
                "role must be admin or member",
                code="invalid_role",
            )
        now = utc_now()
        denial: Optional[AuthError] = None
        denial_details: dict[str, Any] = {}
        with self.connection(write=True, immediate=True) as connection:
            denial = self._active_admin_denial(connection, actor)
            if denial is not None:
                denial_details = {"reason": "actor_not_active_admin"}
            else:
                row = connection.execute(
                    "SELECT id, role, enabled FROM users WHERE id = ?",
                    (user_id,),
                ).fetchone()
                if row is None:
                    raise AuthError("user not found", 404, code="user_not_found")
                old_role = row["role"]
                if old_role == role:
                    self._audit(
                        connection,
                        actor.id,
                        "admin.user.role.update",
                        "user",
                        user_id,
                        "success",
                        {
                            "old_role": old_role,
                            "new_role": role,
                            "changed": False,
                        },
                    )
                else:
                    if user_id == actor.id:
                        denial = AuthError(
                            "administrators cannot change their own role",
                            409,
                            code="self_user_management_forbidden",
                        )
                        denial_details = {
                            "reason": "self_role_change",
                            "old_role": old_role,
                            "new_role": role,
                        }
                    elif old_role == "admin" and role == "member" and row["enabled"]:
                        active_admins = connection.execute(
                            """
                            SELECT COUNT(*) FROM users
                            WHERE role = 'admin' AND enabled = 1
                            """
                        ).fetchone()[0]
                        if active_admins <= 1:
                            denial = AuthError(
                                "cannot demote the last active admin",
                                409,
                                code="last_active_admin",
                            )
                            denial_details = {
                                "reason": "last_active_admin",
                                "old_role": old_role,
                                "new_role": role,
                            }
                    if denial is None:
                        connection.execute(
                            "UPDATE users SET role = ?, updated_at = ? WHERE id = ?",
                            (role, now, user_id),
                        )
                        self._revoke_user_sessions(connection, user_id, now)
                        if old_role == "admin" and role == "member":
                            self._revoke_user_capabilities(
                                connection,
                                user_id,
                                now,
                            )
                        self._audit(
                            connection,
                            actor.id,
                            "admin.user.role.update",
                            "user",
                            user_id,
                            "success",
                            {
                                "old_role": old_role,
                                "new_role": role,
                                "changed": True,
                            },
                        )
        if denial is not None:
            self._raise_audited_denial(
                actor,
                "admin.user.role.update",
                user_id,
                denial,
                denial_details,
            )

    def reset_password(
        self,
        actor: Principal,
        user_id: str,
        password: Any,
    ) -> None:
        password = validate_password(password)
        now = utc_now()
        password_hash = self.password_hasher.hash(password)
        denial: Optional[AuthError] = None
        denial_details: dict[str, Any] = {}
        with self.connection(write=True, immediate=True) as connection:
            denial = self._active_admin_denial(connection, actor)
            if denial is not None:
                denial_details = {"reason": "actor_not_active_admin"}
            else:
                exists = connection.execute(
                    "SELECT 1 FROM users WHERE id = ?",
                    (user_id,),
                ).fetchone()
                if exists is None:
                    raise AuthError("user not found", 404, code="user_not_found")
                if user_id == actor.id:
                    denial = AuthError(
                        "administrators must change their own password in Account",
                        409,
                        code="self_user_management_forbidden",
                    )
                    denial_details = {"reason": "self_password_reset"}
                else:
                    connection.execute(
                        """
                        UPDATE users
                        SET password_hash = ?, password_changed_at = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (password_hash, now, now, user_id),
                    )
                    self._revoke_user_sessions(connection, user_id, now)
                    self._audit(
                        connection,
                        actor.id,
                        "admin.user.reset_password",
                        "user",
                        user_id,
                        "success",
                        {},
                    )
        if denial is not None:
            self._raise_audited_denial(
                actor,
                "admin.user.reset_password",
                user_id,
                denial,
                denial_details,
            )

    def audit(
        self,
        actor_user_id: Optional[str],
        action: str,
        target_type: str,
        target_id: Optional[str],
        outcome: str,
        details: dict[str, Any],
    ) -> None:
        with self.connection(write=True) as connection:
            self._audit(
                connection,
                actor_user_id,
                action,
                target_type,
                target_id,
                outcome,
                details,
            )

    def list_audit(self, limit: int = 200) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT audit_log.id, audit_log.actor_user_id,
                       users.username AS actor_username,
                       audit_log.action, audit_log.target_type,
                       audit_log.target_id, audit_log.outcome,
                       audit_log.details_json, audit_log.created_at
                FROM audit_log
                LEFT JOIN users ON users.id = audit_log.actor_user_id
                ORDER BY audit_log.created_at DESC, audit_log.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["details"] = json.loads(item.pop("details_json"))
            result.append(item)
        return result

    @staticmethod
    def _revoke_user_sessions(connection, user_id: str, now: str) -> None:
        connection.execute(
            """
            UPDATE sessions SET revoked_at = ?
            WHERE user_id = ? AND revoked_at IS NULL
            """,
            (now, user_id),
        )

    @staticmethod
    def _revoke_user_capabilities(connection, user_id: str, now: str) -> None:
        connection.execute(
            """
            UPDATE module_capability_tokens
            SET revoked_at = COALESCE(revoked_at, ?)
            WHERE task_id IN (
                SELECT id FROM module_tasks WHERE creator_user_id = ?
            )
            """,
            (now, user_id),
        )

    @staticmethod
    def _active_admin_denial(
        connection,
        actor: Principal,
    ) -> Optional[AuthError]:
        row = connection.execute(
            "SELECT role, enabled FROM users WHERE id = ?",
            (actor.id,),
        ).fetchone()
        if row is None or row["role"] != "admin" or not row["enabled"]:
            return AuthError(
                "administrator permission required",
                403,
                code="administrator_required",
            )
        return None

    def _raise_audited_denial(
        self,
        actor: Principal,
        action: str,
        user_id: Optional[str],
        error: AuthError,
        details: dict[str, Any],
    ) -> None:
        self.audit(
            actor.id,
            action,
            "user",
            user_id,
            "denied",
            details,
        )
        raise error

    @staticmethod
    def _audit(
        connection,
        actor_user_id: Optional[str],
        action: str,
        target_type: str,
        target_id: Optional[str],
        outcome: str,
        details: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO audit_log
                (id, actor_user_id, action, target_type, target_id,
                 outcome, details_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                actor_user_id,
                action,
                target_type,
                target_id,
                outcome,
                json.dumps(details, ensure_ascii=False, separators=(",", ":")),
                utc_now(),
            ),
        )


def ensure_setup_secret(secret_file: Path) -> Optional[str]:
    secret_file = secret_file.resolve()
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    if secret_file.exists():
        mode = secret_file.stat().st_mode & 0o777
        if mode != 0o600:
            os.chmod(secret_file, 0o600)
        return None
    token = secrets.token_urlsafe(48)
    descriptor = os.open(
        secret_file,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as file_handle:
        file_handle.write(token + "\n")
    return token
