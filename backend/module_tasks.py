"""Durable ChatRaw shadow records and gateway for Module Protocol v1 tasks."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import quote

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

try:
    from .db_runtime import database_connection
    from .module_registry import (
        ModuleRegistry,
        ModuleRegistryError,
        ModuleTransportError,
    )
    from .module_task_protocol import (
        ACTIVE_TASK_STATES,
        CAPABILITY_TOKEN_TTL_SECONDS,
        HOST_CAPABILITIES,
        MAX_CAPABILITY_TOKEN_TTL_SECONDS,
        MAX_ARTIFACT_BYTES,
        MAX_EVENT_BYTES,
        MAX_INPUT_RESOURCES,
        MAX_TASK_LIST_LIMIT,
        MAX_TASK_RESPONSE_BYTES,
        PUBLIC_TASK_STATES,
        TERMINAL_TASK_STATES,
        ModuleTaskProtocolError,
        digest_task_request,
        validate_artifact_metadata,
        validate_idempotency_key,
        validate_resource_metadata,
        validate_task_event,
        validate_task_input,
        validate_task_summary,
    )
except ImportError:
    from db_runtime import database_connection
    from module_registry import (
        ModuleRegistry,
        ModuleRegistryError,
        ModuleTransportError,
    )
    from module_task_protocol import (
        ACTIVE_TASK_STATES,
        CAPABILITY_TOKEN_TTL_SECONDS,
        HOST_CAPABILITIES,
        MAX_CAPABILITY_TOKEN_TTL_SECONDS,
        MAX_ARTIFACT_BYTES,
        MAX_EVENT_BYTES,
        MAX_INPUT_RESOURCES,
        MAX_TASK_LIST_LIMIT,
        MAX_TASK_RESPONSE_BYTES,
        PUBLIC_TASK_STATES,
        TERMINAL_TASK_STATES,
        ModuleTaskProtocolError,
        digest_task_request,
        validate_artifact_metadata,
        validate_idempotency_key,
        validate_resource_metadata,
        validate_task_event,
        validate_task_input,
        validate_task_summary,
    )


TASKS_PATH = "/chatraw-module/v1/tasks"
SAFE_ARTIFACT_MEDIA_TYPES = {
    "application/json",
    "application/octet-stream",
    "application/pdf",
    (
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet"
    ),
    (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    ),
    "image/jpeg",
    "image/png",
    "text/csv",
    "text/markdown",
    "text/plain",
}
DEFAULT_TASK_INPUT_RESOURCE_BYTES = 100 * 1024 * 1024
TASK_INPUT_RESOURCE_TTL_SECONDS = 24 * 60 * 60
MAX_MODEL_CHAT_REQUEST_BYTES = 1024 * 1024
MAX_MODEL_STRUCTURED_REQUEST_BYTES = 256 * 1024
MAX_MODEL_STRUCTURED_SCHEMA_BYTES = 192 * 1024
MAX_MODEL_CHAT_REQUESTS = 65
MAX_CHAT_HISTORY_MESSAGES = 40
MAX_CHAT_HISTORY_CHARACTERS = 200_000
MAX_ACTIVE_SKILLS_PER_TASK = 5
MAX_ACTIVE_RULES_PER_TASK = 10
_CONTENT_RANGE = re.compile(r"^bytes (\d+)-(\d+)/(\d+)$")
LOCAL_ACTIVE_TASK_STATES = ACTIVE_TASK_STATES | {"submitting"}
logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class ModuleTaskError(RuntimeError):
    def __init__(
        self,
        code: str,
        public_message: str,
        *,
        status_code: int = 400,
    ):
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message
        self.status_code = status_code


class ModuleTaskService:
    def __init__(
        self,
        db_path: str,
        *,
        busy_timeout_ms: int,
        registry: ModuleRegistry,
        audit: Callable[..., None],
        chat_generation_active: Callable[[str], bool] | None = None,
        model_invoke: Callable[[str], Awaitable[str]] | None = None,
        model_invoke_v2: (
            Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]
            | None
        ) = None,
        model_chat_completion: (
            Callable[[dict[str, Any]], Awaitable[dict[str, Any]]] | None
        ) = None,
        chat_auto_title: (
            Callable[[str, str, str], Awaitable[Any]] | None
        ) = None,
        capability_base_url: str | None = None,
        resource_dir: str | Path | None = None,
        max_input_resource_bytes: int | None = None,
    ):
        self.db_path = db_path
        self.busy_timeout_ms = busy_timeout_ms
        self.registry = registry
        self.audit = audit
        self.chat_generation_active = chat_generation_active or (lambda _chat_id: False)
        self.model_invoke = model_invoke
        self.model_invoke_v2 = model_invoke_v2
        self.model_chat_completion = model_chat_completion
        self.chat_auto_title = chat_auto_title
        self.capability_base_url = (
            capability_base_url
            or getattr(
                registry,
                "capability_base_url",
                "http://127.0.0.1:51111",
            )
        ).rstrip("/")
        self.resource_dir = Path(
            resource_dir
            or (Path(db_path).resolve().parent / "module-task-resources")
        )
        self.resource_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.resource_dir.chmod(0o700)
        configured_limit = os.environ.get(
            "CHATRAW_MODULE_TASK_RESOURCE_MAX_BYTES"
        )
        if max_input_resource_bytes is not None:
            limit = max_input_resource_bytes
        elif configured_limit is None:
            limit = DEFAULT_TASK_INPUT_RESOURCE_BYTES
        else:
            try:
                limit = int(configured_limit)
            except ValueError:
                raise RuntimeError(
                    "CHATRAW_MODULE_TASK_RESOURCE_MAX_BYTES "
                    "must be a positive integer"
                ) from None
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or limit < 1
        ):
            raise RuntimeError(
                "CHATRAW_MODULE_TASK_RESOURCE_MAX_BYTES "
                "must be a positive integer"
            )
        self.max_input_resource_bytes = limit
        self.cleanup_input_resources()

    def _connection(self, *, write: bool = False, immediate: bool = False):
        return database_connection(
            self.db_path,
            busy_timeout_ms=self.busy_timeout_ms,
            write=write,
            immediate=immediate,
        )

    @staticmethod
    def _action(target: dict[str, Any], action_id: str) -> dict[str, Any]:
        for action in target["manifest"]["actions"]:
            if action["action_id"] == action_id:
                return action
        raise ModuleTaskError(
            "module_action_not_found",
            "Module action was not found",
            status_code=404,
        )

    @staticmethod
    def _require_action_role(action: dict[str, Any], role: str) -> None:
        if action["minimum_role"] == "admin" and role != "admin":
            raise ModuleTaskError(
                "module_action_forbidden",
                "Administrator permission is required for this action",
                status_code=403,
            )

    def _task_row(self, task_id: str, *, visible: bool = True):
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT module_tasks.*, users.enabled AS creator_enabled
                FROM module_tasks
                JOIN users ON users.id = module_tasks.creator_user_id
                WHERE module_tasks.id = ?
                """,
                (task_id,),
            ).fetchone()
        if row is None or (visible and not row["visible"]):
            raise ModuleTaskError(
                "task_not_found",
                "Task was not found",
                status_code=404,
            )
        return row

    def _artifact_rows(self, task_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT artifact_ref, filename, media_type, size,
                       expires_at, created_at
                FROM module_task_artifacts
                WHERE task_id = ?
                ORDER BY created_at, artifact_ref
                """,
                (task_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _resource_rows(self, task_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT resource_ref, filename, media_type, size, expires_at
                FROM module_task_output_resources
                WHERE task_id = ?
                ORDER BY created_at, resource_ref
                """,
                (task_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _public_task(
        self,
        row: Any,
        *,
        principal_user_id: str,
        principal_role: str,
        remote: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "task_id": row["id"],
            "module_id": row["module_id"],
            "module_version": row["module_version"],
            "action_id": row["action_id"],
            "action_version": row["action_version"],
            "config_revision": row["config_revision"],
            "chat_id": row["chat_id"],
            "state": row["state"],
            "status_sync": row["status_sync"],
            "outcome_code": row["outcome_code"],
            "last_event_id": row["last_cursor"],
            "created_at": row["created_at"],
            "accepted_at": row["accepted_at"],
            "updated_at": row["updated_at"],
            "terminal_at": row["terminal_at"],
            "user_message_id": row["user_message_id"],
            "assistant_message_id": row["assistant_message_id"],
            "is_creator": row["creator_user_id"] == principal_user_id,
            "can_control": (
                row["creator_user_id"] == principal_user_id
                or principal_role == "admin"
            ),
            "artifacts": self._artifact_rows(row["id"]),
            "resources": self._resource_rows(row["id"]),
        }
        if remote is not None and "result" in remote:
            payload["result"] = remote["result"]
        return payload

    def _validate_create_payload(
        self,
        payload: Any,
    ) -> tuple[
        str,
        str,
        dict[str, Any],
        str | None,
        str | None,
        list[str],
        list[str],
    ]:
        if not isinstance(payload, dict):
            raise ModuleTaskError(
                "invalid_task_request",
                "Task request must be an object",
            )
        allowed = {
            "module_id",
            "action_id",
            "input",
            "chat_id",
            "user_message",
            "resource_ids",
            "active_skill_ids",
        }
        required = {"module_id", "action_id", "input"}
        if set(payload) - allowed or not required.issubset(payload):
            raise ModuleTaskError(
                "invalid_task_request",
                "Task request fields are invalid",
            )
        module_id = payload["module_id"]
        action_id = payload["action_id"]
        if (
            not isinstance(module_id, str)
            or not module_id
            or not isinstance(action_id, str)
            or not action_id
        ):
            raise ModuleTaskError(
                "invalid_task_request",
                "Module and action identifiers are required",
            )
        chat_id = payload.get("chat_id")
        user_message = payload.get("user_message")
        if chat_id is not None and (
            not isinstance(chat_id, str) or not chat_id
        ):
            raise ModuleTaskError(
                "invalid_task_request",
                "chat_id is invalid",
            )
        if chat_id is not None and (
            not isinstance(user_message, str)
            or not user_message.strip()
            or len(user_message.encode("utf-8")) > 128 * 1024
        ):
            raise ModuleTaskError(
                "invalid_task_request",
                "Chat-bound tasks require a user_message",
            )
        if chat_id is None and user_message is not None:
            raise ModuleTaskError(
                "invalid_task_request",
                "user_message requires chat_id",
            )
        resource_ids = payload.get("resource_ids", [])
        if (
            not isinstance(resource_ids, list)
            or len(resource_ids) > MAX_INPUT_RESOURCES
            or not all(
                isinstance(resource_id, str) and resource_id
                for resource_id in resource_ids
            )
            or len(set(resource_ids)) != len(resource_ids)
        ):
            raise ModuleTaskError(
                "invalid_task_request",
                "resource_ids are invalid",
            )
        active_skill_ids = payload.get("active_skill_ids", [])
        if (
            not isinstance(active_skill_ids, list)
            or len(active_skill_ids) > MAX_ACTIVE_SKILLS_PER_TASK
            or not all(
                isinstance(skill_id, str)
                and 1 <= len(skill_id) <= 128
                for skill_id in active_skill_ids
            )
            or len(set(active_skill_ids)) != len(active_skill_ids)
        ):
            raise ModuleTaskError(
                "invalid_task_request",
                "active_skill_ids are invalid",
            )
        return (
            module_id,
            action_id,
            payload["input"],
            chat_id,
            user_message,
            resource_ids,
            active_skill_ids,
        )

    @staticmethod
    def _validate_resource_filename(value: Any) -> str:
        if (
            not isinstance(value, str)
            or not 1 <= len(value) <= 255
            or "/" in value
            or "\\" in value
            or any(
                ord(character) < 0x20 or ord(character) == 0x7F
                for character in value
            )
        ):
            raise ModuleTaskError(
                "invalid_resource_filename",
                "Resource filename is invalid",
            )
        return value

    @staticmethod
    def _validate_resource_media_type(value: Any) -> str:
        if (
            not isinstance(value, str)
            or not 1 <= len(value) <= 127
            or "/" not in value
            or ";" in value
            or any(
                ord(character) < 0x21 or ord(character) > 0x7E
                for character in value
            )
        ):
            raise ModuleTaskError(
                "invalid_resource_media_type",
                "Resource media type is invalid",
            )
        return value.lower()

    async def upload_input_resource(
        self,
        upload: Any,
        *,
        creator_user_id: str,
    ) -> dict[str, Any]:
        self.cleanup_input_resources()
        filename = self._validate_resource_filename(upload.filename)
        media_type = self._validate_resource_media_type(upload.content_type)
        resource_id = str(uuid.uuid4())
        storage_name = secrets.token_hex(32)
        destination = self.resource_dir / storage_name
        partial = self.resource_dir / f".{storage_name}.part"
        digest = hashlib.sha256()
        size = 0
        try:
            descriptor = os.open(
                partial,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            with os.fdopen(descriptor, "wb") as output:
                while True:
                    chunk = await upload.read(64 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > self.max_input_resource_bytes:
                        raise ModuleTaskError(
                            "task_resource_too_large",
                            "Task resource exceeds the size limit",
                            status_code=413,
                        )
                    digest.update(chunk)
                    output.write(chunk)
            partial.replace(destination)
        except (OSError, ModuleTaskError):
            partial.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()
        created_at = _utc_now()
        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(seconds=TASK_INPUT_RESOURCE_TTL_SECONDS)
        ).isoformat().replace("+00:00", "Z")
        try:
            with self._connection(write=True) as connection:
                connection.execute(
                    """
                    INSERT INTO module_task_input_resources (
                        resource_id, creator_user_id, filename, media_type,
                        size, sha256, storage_name, created_at, expires_at,
                        bound_task_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        resource_id,
                        creator_user_id,
                        filename,
                        media_type,
                        size,
                        digest.hexdigest(),
                        storage_name,
                        created_at,
                        expires_at,
                    ),
                )
        except sqlite3.Error:
            destination.unlink(missing_ok=True)
            raise
        return {
            "resource_id": resource_id,
            "filename": filename,
            "media_type": media_type,
            "size": size,
            "sha256": digest.hexdigest(),
            "expires_at": expires_at,
        }

    def cleanup_input_resources(self) -> int:
        now = _utc_now()
        with self._connection(write=True, immediate=True) as connection:
            rows = connection.execute(
                """
                SELECT resource_id, storage_name
                FROM module_task_input_resources
                WHERE expires_at IS NOT NULL AND expires_at <= ?
                """,
                (now,),
            ).fetchall()
            for row in rows:
                (self.resource_dir / row["storage_name"]).unlink(
                    missing_ok=True
                )
            connection.executemany(
                """
                DELETE FROM module_task_input_resources
                WHERE resource_id = ?
                  AND expires_at IS NOT NULL
                  AND expires_at <= ?
                """,
                [(row["resource_id"], now) for row in rows],
            )
        return len(rows)

    def _reactivate_input_resources(self, task_id: str) -> None:
        with self._connection(write=True) as connection:
            connection.execute(
                """
                UPDATE module_task_input_resources
                SET expires_at = NULL
                WHERE bound_task_id = ?
                  AND EXISTS (
                      SELECT 1 FROM module_tasks
                      WHERE id = ? AND visible = 0
                  )
                """,
                (task_id, task_id),
            )

    def _schedule_input_resource_cleanup(
        self,
        task_id: str,
        *,
        now: str | None = None,
    ) -> None:
        cleanup_at = (
            _parse_utc(now) if now else datetime.now(timezone.utc)
        ) + timedelta(seconds=TASK_INPUT_RESOURCE_TTL_SECONDS)
        with self._connection(write=True) as connection:
            connection.execute(
                """
                UPDATE module_task_input_resources
                SET expires_at = ?
                WHERE bound_task_id = ? AND expires_at IS NULL
                """,
                (
                    cleanup_at.isoformat().replace("+00:00", "Z"),
                    task_id,
                ),
            )

    def _validate_local_references(
        self,
        *,
        chat_id: str | None,
        resource_ids: list[str],
        principal_user_id: str,
    ) -> bool:
        has_uploaded_resource = False
        with self._connection() as connection:
            if chat_id is not None:
                chat = connection.execute(
                    "SELECT 1 FROM chats WHERE id = ?",
                    (chat_id,),
                ).fetchone()
                if chat is None:
                    raise ModuleTaskError(
                        "chat_not_found",
                        "Chat was not found",
                        status_code=404,
                    )
            for resource_id in resource_ids:
                resource = connection.execute(
                    "SELECT 1 FROM documents WHERE id = ?",
                    (resource_id,),
                ).fetchone()
                if resource is not None:
                    continue
                resource = connection.execute(
                    """
                    SELECT creator_user_id, expires_at
                    FROM module_task_input_resources
                    WHERE resource_id = ?
                    """,
                    (resource_id,),
                ).fetchone()
                if resource is None:
                    raise ModuleTaskError(
                        "resource_not_found",
                        "A task resource was not found",
                        status_code=404,
                    )
                has_uploaded_resource = True
                if resource["creator_user_id"] != principal_user_id:
                    raise ModuleTaskError(
                        "resource_access_forbidden",
                        "A task resource is not available to this user",
                        status_code=403,
                    )
                if (
                    resource["expires_at"] is not None
                    and _parse_utc(resource["expires_at"])
                    <= datetime.now(timezone.utc)
                ):
                    raise ModuleTaskError(
                        "resource_expired",
                        "A task resource has expired",
                        status_code=410,
                    )
        return has_uploaded_resource

    def _resolve_skill_snapshots(
        self,
        *,
        skill_ids: list[str],
        principal_user_id: str,
        module_id: str,
    ) -> list[dict[str, Any]]:
        snapshots = []
        with self._connection() as connection:
            for skill_id in skill_ids:
                row = connection.execute(
                    """
                    SELECT skills.id, skills.name, skills.description,
                           skills.active_version_id,
                           versions.content_sha256,
                           versions.commit_sha
                    FROM agent_skills AS skills
                    JOIN agent_skill_versions AS versions
                      ON versions.id = skills.active_version_id
                    WHERE skills.id = ?
                      AND skills.owner_user_id = ?
                      AND skills.target_module_id = ?
                      AND skills.enabled = 1
                    """,
                    (skill_id, principal_user_id, module_id),
                ).fetchone()
                if row is None:
                    raise ModuleTaskError(
                        "agent_skill_unavailable",
                        "An active Agent skill is unavailable",
                        status_code=404,
                    )
                snapshots.append(
                    {
                        "skill_id": row["id"],
                        "version_id": row["active_version_id"],
                        "name": row["name"],
                        "description": row["description"],
                        "content_sha256": row["content_sha256"],
                        "commit": row["commit_sha"],
                    }
                )
        return snapshots

    def _resolve_rule_snapshots(
        self,
        *,
        principal_user_id: str,
        module_id: str,
    ) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT documents.id AS document_id,
                       documents.name,
                       versions.id AS compiled_version_id,
                       versions.source_version_id,
                       versions.specification_version,
                       versions.content_sha256,
                       documents.scope AS scope_snapshot
                FROM agent_rule_documents AS documents
                JOIN agent_compiled_rule_versions AS versions
                  ON versions.id =
                     documents.active_compiled_version_id
                WHERE documents.target_module_id = ?
                  AND documents.deleted_at IS NULL
                  AND (
                    documents.scope = 'system_default'
                    OR (
                      documents.scope = 'personal'
                      AND documents.owner_user_id = ?
                    )
                  )
                  AND versions.status = 'valid'
                ORDER BY
                  CASE documents.scope
                    WHEN 'system_default' THEN 0
                    ELSE 1
                  END,
                  documents.updated_at,
                  documents.id
                LIMIT ?
                """,
                (
                    module_id,
                    principal_user_id,
                    MAX_ACTIVE_RULES_PER_TASK + 1,
                ),
            ).fetchall()
        if len(rows) > MAX_ACTIVE_RULES_PER_TASK:
            raise ModuleTaskError(
                "too_many_active_rules",
                "Too many active Agent rules",
                status_code=409,
            )
        return [dict(row) for row in rows]

    def _has_active_chat_task(
        self,
        connection: Any,
        chat_id: str,
        *,
        excluding_task_id: str | None = None,
    ) -> bool:
        placeholders = ",".join("?" for _state in LOCAL_ACTIVE_TASK_STATES)
        parameters: list[Any] = [
            chat_id,
            *sorted(LOCAL_ACTIVE_TASK_STATES),
        ]
        exclusion = ""
        if excluding_task_id is not None:
            exclusion = " AND id != ?"
            parameters.append(excluding_task_id)
        row = connection.execute(
            f"""
            SELECT 1 FROM module_tasks
            WHERE chat_id = ? AND state IN ({placeholders}){exclusion}
            LIMIT 1
            """,
            parameters,
        ).fetchone()
        return row is not None

    def has_active_chat_task(self, chat_id: str) -> bool:
        with self._connection() as connection:
            return self._has_active_chat_task(connection, chat_id)

    def has_active_resource_task(self, resource_id: str) -> bool:
        placeholders = ",".join(
            "?" for _state in LOCAL_ACTIVE_TASK_STATES
        )
        with self._connection() as connection:
            row = connection.execute(
                f"""
                SELECT 1
                FROM module_task_resource_refs AS refs
                JOIN module_tasks AS tasks ON tasks.id = refs.task_id
                WHERE refs.resource_id = ?
                  AND tasks.state IN ({placeholders})
                LIMIT 1
                """,
                (resource_id, *sorted(LOCAL_ACTIVE_TASK_STATES)),
            ).fetchone()
        return row is not None

    def has_active_registration_tasks(self, registration_id: str) -> bool:
        placeholders = ",".join(
            "?" for _state in LOCAL_ACTIVE_TASK_STATES
        )
        with self._connection() as connection:
            row = connection.execute(
                f"""
                SELECT 1 FROM module_tasks
                WHERE registration_id = ? AND state IN ({placeholders})
                LIMIT 1
                """,
                (registration_id, *sorted(LOCAL_ACTIVE_TASK_STATES)),
            ).fetchone()
        return row is not None

    def _prepare_provisional(
        self,
        *,
        target: dict[str, Any],
        action: dict[str, Any],
        creator_user_id: str,
        idempotency_key: str,
        request_digest: str,
        chat_id: str | None,
        resource_ids: list[str],
        skill_snapshots: list[dict[str, Any]],
        rule_snapshots: list[dict[str, Any]],
    ):
        now = _utc_now()
        with self._connection(write=True, immediate=True) as connection:
            existing = connection.execute(
                """
                SELECT * FROM module_tasks
                WHERE creator_user_id = ? AND idempotency_key = ?
                """,
                (creator_user_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing["request_digest"] != request_digest:
                    raise ModuleTaskError(
                        "idempotency_conflict",
                        "Idempotency-Key was already used for another request",
                        status_code=409,
                    )
                return existing
            if chat_id is not None:
                chat = connection.execute(
                    "SELECT 1 FROM chats WHERE id = ?",
                    (chat_id,),
                ).fetchone()
                if chat is None:
                    raise ModuleTaskError(
                        "chat_not_found",
                        "Chat not found",
                        status_code=404,
                    )
            if chat_id is not None and (
                self.chat_generation_active(chat_id)
                or self._has_active_chat_task(connection, chat_id)
            ):
                raise ModuleTaskError(
                    "chat_generation_conflict",
                    "This chat already has an active generation",
                    status_code=409,
                )
            task_id = str(uuid.uuid4())
            connection.execute(
                """
                INSERT INTO module_tasks (
                    id, registration_id, module_id, module_version,
                    action_id, action_version, action_contract_json,
                    config_revision,
                    creator_user_id, chat_id, idempotency_key,
                    request_digest, state, visible, status_sync,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'submitting',
                          0, 'current', ?, ?)
                """,
                (
                    task_id,
                    target["registration_id"],
                    target["module_id"],
                    target["module_version"],
                    action["action_id"],
                    action["action_version"],
                    json.dumps(
                        action,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    target["config_revision"],
                    creator_user_id,
                    chat_id,
                    idempotency_key,
                    request_digest,
                    now,
                    now,
                ),
            )
            connection.executemany(
                """
                INSERT INTO module_task_resource_refs (task_id, resource_id)
                VALUES (?, ?)
                """,
                [(task_id, resource_id) for resource_id in resource_ids],
            )
            connection.executemany(
                """
                INSERT INTO module_task_skill_activations (
                    task_id, ordinal, skill_id, version_id, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        task_id,
                        ordinal,
                        snapshot["skill_id"],
                        snapshot["version_id"],
                        now,
                    )
                    for ordinal, snapshot in enumerate(skill_snapshots)
                ],
            )
            connection.executemany(
                """
                INSERT INTO module_task_rule_activations (
                    task_id, ordinal, document_id,
                    compiled_version_id, scope_snapshot, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        task_id,
                        ordinal,
                        snapshot["document_id"],
                        snapshot["compiled_version_id"],
                        snapshot["scope_snapshot"],
                        now,
                    )
                    for ordinal, snapshot in enumerate(rule_snapshots)
                ],
            )
            for resource_id in resource_ids:
                uploaded = connection.execute(
                    """
                    SELECT bound_task_id
                    FROM module_task_input_resources
                    WHERE resource_id = ?
                    """,
                    (resource_id,),
                ).fetchone()
                if uploaded is None:
                    continue
                if uploaded["bound_task_id"] is not None:
                    raise ModuleTaskError(
                        "resource_already_bound",
                        "A task resource is already bound to a task",
                        status_code=409,
                    )
                connection.execute(
                    """
                    UPDATE module_task_input_resources
                    SET bound_task_id = ?, expires_at = NULL
                    WHERE resource_id = ? AND bound_task_id IS NULL
                    """,
                    (task_id, resource_id),
                )
            return connection.execute(
                "SELECT * FROM module_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()

    def _issue_capabilities(
        self,
        *,
        row: Any,
        target: dict[str, Any],
        action: dict[str, Any],
        chat_id: str | None,
        resource_ids: list[str],
        task_input: dict[str, Any],
        skill_snapshots: list[dict[str, Any]],
        rule_snapshots: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        allowed = set(target["granted_capabilities"]) & HOST_CAPABILITIES
        requested_deadline = task_input.get("request_deadline_seconds")
        if requested_deadline is None:
            requested_deadline = (
                action.get("input_schema", {})
                .get("properties", {})
                .get("request_deadline_seconds", {})
                .get("default")
            )
        if (
            not isinstance(requested_deadline, int)
            or isinstance(requested_deadline, bool)
            or not 1 <= requested_deadline <= 2 * 60 * 60
        ):
            requested_deadline = CAPABILITY_TOKEN_TTL_SECONDS
        capability_ttl = min(
            MAX_CAPABILITY_TOKEN_TTL_SECONDS,
            max(
                CAPABILITY_TOKEN_TTL_SECONDS,
                requested_deadline + 60,
            ),
        )
        expires = datetime.now(timezone.utc) + timedelta(
            seconds=capability_ttl
        )
        expires_at = expires.isoformat().replace("+00:00", "Z")
        issued = []
        scopes: dict[str, tuple[dict[str, Any], int | None]] = {}
        if "chat.read" in allowed and chat_id is not None:
            scopes["chat.read"] = ({"chat_id": chat_id}, None)
        if "principal.read" in allowed:
            scopes["principal.read"] = ({}, 16)
        with self._connection() as connection:
            uploaded_ids = {
                item["resource_id"]
                for item in connection.execute(
                    """
                    SELECT resource_id
                    FROM module_task_input_resources
                    WHERE bound_task_id = ?
                    """,
                    (row["id"],),
                ).fetchall()
            }
        document_ids = set(resource_ids) - uploaded_ids
        if "resource.read" in allowed and document_ids:
            scopes["resource.read"] = (
                {"resource_ids": sorted(document_ids)},
                None,
            )
        if "resource.stream" in allowed and uploaded_ids:
            scopes["resource.stream"] = (
                {"resource_ids": sorted(uploaded_ids)},
                None,
            )
        if "model.invoke" in allowed:
            scopes["model.invoke"] = (
                {"model_type": "chat"},
                8,
            )
        if "model.invoke.v2" in allowed:
            scopes["model.invoke.v2"] = (
                {
                    "model_type": "chat",
                    "structured_output": "json_schema",
                },
                8,
            )
        if "model.chat.completions" in allowed:
            scopes["model.chat.completions"] = (
                {
                    "profiles": [
                        "agent-runtime",
                        "agent-compiler",
                        "agent-polisher",
                    ],
                    "supports_stream": True,
                },
                MAX_MODEL_CHAT_REQUESTS,
            )
        if "skill.read" in allowed and skill_snapshots:
            scopes["skill.read"] = (
                {
                    "skill_ids": [
                        snapshot["skill_id"]
                        for snapshot in skill_snapshots
                    ]
                },
                max(16, len(skill_snapshots) * 4),
            )
        if "rule.read" in allowed and rule_snapshots:
            scopes["rule.read"] = (
                {
                    "document_ids": [
                        snapshot["document_id"]
                        for snapshot in rule_snapshots
                    ]
                },
                max(16, len(rule_snapshots) * 4),
            )
        with self._connection(write=True, immediate=True) as connection:
            connection.execute(
                """
                UPDATE module_capability_tokens
                SET revoked_at = ?
                WHERE task_id = ? AND revoked_at IS NULL
                """,
                (_utc_now(), row["id"]),
            )
            for capability, (scope, max_uses) in scopes.items():
                token = secrets.token_urlsafe(48)
                connection.execute(
                    """
                    INSERT INTO module_capability_tokens (
                        token_digest, task_id, registration_id, capability,
                        scope_json, use_count, max_uses, created_at,
                        expires_at, revoked_at
                    ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, NULL)
                    """,
                    (
                        _token_digest(token),
                        row["id"],
                        row["registration_id"],
                        capability,
                        json.dumps(scope, separators=(",", ":"), sort_keys=True),
                        max_uses,
                        _utc_now(),
                        expires_at,
                    ),
                )
                issued.append(
                    {
                        "capability": capability,
                        "endpoint": self._capability_endpoint(capability),
                        "token": token,
                        "scope": scope,
                        "expires_at": expires_at,
                    }
                )
        return issued

    def _capability_endpoint(self, capability: str) -> str:
        paths = {
            "chat.read": "/api/module-capabilities/v1/chat",
            "principal.read": (
                "/api/module-capabilities/v1/principal"
            ),
            "resource.read": (
                "/api/module-capabilities/v1/resources/{resource_id}"
            ),
            "resource.stream": (
                "/api/module-capabilities/v1/resource-stream/{resource_id}"
            ),
            "model.invoke": "/api/module-capabilities/v1/model/invoke",
            "model.invoke.v2": (
                "/api/module-capabilities/v1/model/invoke-v2"
            ),
            "model.chat.completions": (
                "/api/module-capabilities/v1/openai"
            ),
            "skill.read": (
                "/api/module-capabilities/v1/skills/{skill_id}"
            ),
            "rule.read": (
                "/api/module-capabilities/v1/rules/{document_id}"
            ),
        }
        return f"{self.capability_base_url}{paths[capability]}"

    @staticmethod
    def _module_error(error: Exception) -> ModuleTaskError:
        if isinstance(error, ModuleTaskError):
            return error
        if isinstance(error, ModuleTaskProtocolError):
            return ModuleTaskError(
                error.code,
                error.public_message,
                status_code=error.status_code,
            )
        if isinstance(error, ModuleRegistryError):
            return ModuleTaskError(
                error.code,
                error.public_message,
                status_code=error.status_code,
            )
        return ModuleTaskError(
            "module_task_failed",
            "Module task operation failed",
            status_code=500,
        )

    def _validate_summary_for_row(
        self,
        row: Any,
        action: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            summary = validate_task_summary(
                payload,
                expected_task_id=row["id"],
                expected_action_id=row["action_id"],
                expected_action_version=row["action_version"],
                expected_config_revision=row["config_revision"],
                output_schema=action["output_schema"],
            )
        except ModuleTaskProtocolError as error:
            raise self._module_error(error) from error
        if summary.get("chat_projection") is not None and not action[
            "supports_chat_projection"
        ]:
            raise ModuleTaskError(
                "unexpected_chat_projection",
                "Module returned an undeclared chat projection",
                status_code=502,
            )
        if summary.get("artifacts") and not action["supports_artifacts"]:
            raise ModuleTaskError(
                "unexpected_artifact",
                "Module returned undeclared artifacts",
                status_code=502,
            )
        if summary.get("resources") and not action.get(
            "supports_resources",
            False,
        ):
            raise ModuleTaskError(
                "unexpected_resource",
                "Module returned undeclared resources",
                status_code=502,
            )
        return summary

    def _finalize_acceptance(
        self,
        *,
        row: Any,
        summary: dict[str, Any],
        user_message: str | None,
    ) -> None:
        now = _utc_now()
        with self._connection(write=True, immediate=True) as connection:
            current = connection.execute(
                "SELECT * FROM module_tasks WHERE id = ?",
                (row["id"],),
            ).fetchone()
            if current is None:
                raise ModuleTaskError(
                    "task_not_found",
                    "Task was not found",
                    status_code=404,
                )
            if current["visible"]:
                return
            self._store_resources(
                connection,
                current["id"],
                summary.get("resources", []),
            )
            user_message_id = None
            if current["chat_id"] is not None:
                chat = connection.execute(
                    "SELECT 1 FROM chats WHERE id = ?",
                    (current["chat_id"],),
                ).fetchone()
                if chat is None:
                    raise ModuleTaskError(
                        "chat_not_found",
                        "Chat was deleted before the task was accepted",
                        status_code=409,
                    )
                next_sequence = connection.execute(
                    """
                    SELECT COALESCE(MAX(sequence), 0) + 1
                    FROM messages WHERE chat_id = ?
                    """,
                    (current["chat_id"],),
                ).fetchone()[0]
                user_message_id = str(uuid.uuid4())
                connection.execute(
                    """
                    INSERT INTO messages (
                        id, chat_id, role, content, created_at,
                        author_user_id, sequence
                    ) VALUES (?, ?, 'user', ?, ?, ?, ?)
                    """,
                    (
                        user_message_id,
                        current["chat_id"],
                        user_message,
                        now,
                        current["creator_user_id"],
                        next_sequence,
                    ),
                )
                connection.execute(
                    "UPDATE chats SET updated_at = ? WHERE id = ?",
                    (now, current["chat_id"]),
                )
            terminal_at = now if summary["state"] in TERMINAL_TASK_STATES else None
            connection.execute(
                """
                UPDATE module_tasks
                SET state = ?, visible = 1, status_sync = 'current',
                    outcome_code = ?, last_cursor = ?,
                    user_message_id = ?, accepted_at = ?,
                    updated_at = ?, terminal_at = ?
                WHERE id = ?
                """,
                (
                    summary["state"],
                    summary.get("outcome_code"),
                    summary["last_event_id"],
                    user_message_id,
                    now,
                    now,
                    terminal_at,
                    current["id"],
                ),
            )

    async def create(
        self,
        *,
        payload: Any,
        idempotency_key: str,
        principal_user_id: str,
        principal_role: str,
    ) -> tuple[dict[str, Any], bool]:
        try:
            idempotency_key = validate_idempotency_key(idempotency_key)
            (
                module_id,
                action_id,
                task_input,
                chat_id,
                user_message,
                resource_ids,
                active_skill_ids,
            ) = self._validate_create_payload(payload)
            target = self.registry.task_target(module_id=module_id)
            action = self._action(target, action_id)
            self._require_action_role(action, principal_role)
            task_input = validate_task_input(task_input, action["input_schema"])
            has_uploaded_resource = self._validate_local_references(
                chat_id=chat_id,
                resource_ids=resource_ids,
                principal_user_id=principal_user_id,
            )
            if has_uploaded_resource and not action.get(
                "supports_resources",
                False,
            ):
                raise ModuleTaskError(
                    "task_resources_not_supported",
                    "This action does not support task resources",
                    status_code=409,
                )
            if active_skill_ids and not action.get(
                "supports_skills",
                False,
            ):
                raise ModuleTaskError(
                    "agent_skills_not_supported",
                    "This action does not support Agent skills",
                    status_code=409,
                )
            skill_snapshots = self._resolve_skill_snapshots(
                skill_ids=active_skill_ids,
                principal_user_id=principal_user_id,
                module_id=module_id,
            )
            rule_snapshots = (
                self._resolve_rule_snapshots(
                    principal_user_id=principal_user_id,
                    module_id=module_id,
                )
                if action.get("supports_rules", False)
                else []
            )
        except (
            ModuleRegistryError,
            ModuleTaskProtocolError,
            ModuleTaskError,
        ) as error:
            raise self._module_error(error) from error

        digest_payload = {
            "module_id": module_id,
            "action_id": action_id,
            "input": task_input,
            "chat_id": chat_id,
            "user_message": user_message,
            "resource_ids": sorted(resource_ids),
            "active_skills": [
                {
                    "skill_id": snapshot["skill_id"],
                    "version_id": snapshot["version_id"],
                    "content_sha256": snapshot["content_sha256"],
                }
                for snapshot in skill_snapshots
            ],
            "active_rules": [
                {
                    "document_id": snapshot["document_id"],
                    "compiled_version_id": snapshot[
                        "compiled_version_id"
                    ],
                    "content_sha256": snapshot["content_sha256"],
                }
                for snapshot in rule_snapshots
            ],
        }
        request_digest = digest_task_request(digest_payload)
        row = self._prepare_provisional(
            target=target,
            action=action,
            creator_user_id=principal_user_id,
            idempotency_key=idempotency_key,
            request_digest=request_digest,
            chat_id=chat_id,
            resource_ids=resource_ids,
            skill_snapshots=skill_snapshots,
            rule_snapshots=rule_snapshots,
        )
        was_visible = bool(row["visible"])
        if was_visible:
            task = await self.get(
                row["id"],
                principal_user_id=principal_user_id,
                principal_role=principal_role,
            )
            return task, False
        self._reactivate_input_resources(row["id"])
        capabilities = self._issue_capabilities(
            row=row,
            target=target,
            action=action,
            chat_id=chat_id,
            resource_ids=resource_ids,
            task_input=task_input,
            skill_snapshots=skill_snapshots,
            rule_snapshots=rule_snapshots,
        )
        module_payload = {
            "task_id": row["id"],
            "request_digest": request_digest,
            "action_id": action["action_id"],
            "action_version": action["action_version"],
            "config_revision": target["config_revision"],
            "input": task_input,
            "active_skills": skill_snapshots,
            "active_rules": [
                {
                    "document_id": snapshot["document_id"],
                    "compiled_version_id": snapshot[
                        "compiled_version_id"
                    ],
                    "source_version_id": snapshot[
                        "source_version_id"
                    ],
                    "name": snapshot["name"],
                    "specification_version": snapshot[
                        "specification_version"
                    ],
                    "content_sha256": snapshot["content_sha256"],
                }
                for snapshot in rule_snapshots
            ],
            "host_capabilities": capabilities,
        }
        try:
            status, response = await self.registry.client.request_json(
                target["base_url"],
                TASKS_PATH,
                method="POST",
                token=target["credential"],
                payload=module_payload,
                max_bytes=MAX_TASK_RESPONSE_BYTES,
            )
            if 400 <= status < 500:
                with self._connection(write=True) as connection:
                    connection.execute(
                        """
                        UPDATE module_tasks
                        SET state = 'abandoned', updated_at = ?
                        WHERE id = ? AND visible = 0
                        """,
                        (_utc_now(), row["id"]),
                    )
                self._schedule_input_resource_cleanup(row["id"])
            if status == 409:
                raise ModuleTaskError(
                    "module_task_conflict",
                    "Module rejected a conflicting task request",
                    status_code=409,
                )
            if status != 202:
                raise ModuleTaskError(
                    "module_task_rejected",
                    "Module rejected the task request",
                    status_code=502,
                )
            summary = self._validate_summary_for_row(row, action, response)
            self._finalize_acceptance(
                row=row,
                summary=summary,
                user_message=user_message,
            )
            self._register_artifacts(row["id"], summary.get("artifacts", []))
            await self._apply_projection(row["id"], action, summary)
            if summary["state"] in TERMINAL_TASK_STATES:
                self.revoke_task_capabilities(row["id"])
                self._schedule_input_resource_cleanup(row["id"])
        except (
            ModuleRegistryError,
            ModuleTaskProtocolError,
            ModuleTaskError,
        ) as error:
            if not isinstance(error, ModuleTransportError):
                self.revoke_task_capabilities(row["id"])
                self._schedule_input_resource_cleanup(row["id"])
            raise self._module_error(error) from error
        self.audit(
            principal_user_id,
            "module.task.create",
            "module_task",
            row["id"],
            "success",
            {
                "module_id": module_id,
                "action_id": action_id,
                "chat_bound": chat_id is not None,
            },
        )
        task = self._public_task(
            self._task_row(row["id"]),
            principal_user_id=principal_user_id,
            principal_role=principal_role,
            remote=summary,
        )
        return task, True

    def _target_and_action_for_row(
        self,
        row: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        try:
            target = self.registry.task_target(
                registration_id=row["registration_id"],
                require_enabled=False,
            )
        except (ModuleRegistryError, ModuleTaskError) as error:
            raise self._module_error(error) from error
        try:
            action = json.loads(row["action_contract_json"])
        except (TypeError, json.JSONDecodeError):
            raise ModuleTaskError(
                "task_contract_unavailable",
                "The task's original action contract is unavailable",
                status_code=500,
            ) from None
        if (
            target["module_id"] != row["module_id"]
            or action.get("action_id") != row["action_id"]
            or action.get("action_version") != row["action_version"]
        ):
            raise ModuleTaskError(
                "task_contract_unavailable",
                "The task's original action contract is unavailable",
                status_code=500,
            )
        return target, action

    def _register_artifacts(
        self,
        task_id: str,
        artifacts: list[dict[str, Any]],
    ) -> None:
        if not artifacts:
            return
        with self._connection(write=True, immediate=True) as connection:
            for artifact in artifacts:
                try:
                    validate_artifact_metadata(artifact)
                except ModuleTaskProtocolError as error:
                    raise self._module_error(error) from error
                if artifact["media_type"] not in SAFE_ARTIFACT_MEDIA_TYPES:
                    raise ModuleTaskError(
                        "artifact_type_not_allowed",
                        "Artifact type is not allowed",
                        status_code=502,
                    )
                existing = connection.execute(
                    """
                    SELECT artifact_ref, filename, media_type, size, expires_at
                    FROM module_task_artifacts
                    WHERE task_id = ? AND artifact_id = ?
                    """,
                    (task_id, artifact["artifact_id"]),
                ).fetchone()
                metadata = (
                    artifact["filename"],
                    artifact["media_type"],
                    artifact["size"],
                    artifact["expires_at"],
                )
                if existing is not None:
                    if tuple(existing[key] for key in (
                        "filename",
                        "media_type",
                        "size",
                        "expires_at",
                    )) != metadata:
                        raise ModuleTaskError(
                            "artifact_identity_conflict",
                            "Artifact metadata changed unexpectedly",
                            status_code=502,
                        )
                    continue
                connection.execute(
                    """
                    INSERT INTO module_task_artifacts (
                        artifact_ref, task_id, artifact_id, filename,
                        media_type, size, expires_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        task_id,
                        artifact["artifact_id"],
                        *metadata,
                        _utc_now(),
                    ),
                )

    def _register_resources(
        self,
        task_id: str,
        resources: list[dict[str, Any]],
    ) -> None:
        if not resources:
            return
        with self._connection(write=True, immediate=True) as connection:
            self._store_resources(connection, task_id, resources)

    def _store_resources(
        self,
        connection: Any,
        task_id: str,
        resources: list[dict[str, Any]],
    ) -> None:
        for resource in resources:
            try:
                validate_resource_metadata(resource)
            except ModuleTaskProtocolError as error:
                raise self._module_error(error) from error
            self._validate_resource_media_type(resource["media_type"])
            existing = connection.execute(
                """
                SELECT filename, media_type, size, expires_at
                FROM module_task_output_resources
                WHERE task_id = ? AND resource_id = ?
                """,
                (task_id, resource["resource_id"]),
            ).fetchone()
            metadata = (
                resource["filename"],
                resource["media_type"],
                resource["size"],
                resource.get("expires_at"),
            )
            if existing is not None:
                if tuple(
                    existing[key]
                    for key in (
                        "filename",
                        "media_type",
                        "size",
                        "expires_at",
                    )
                ) != metadata:
                    raise ModuleTaskError(
                        "resource_identity_conflict",
                        "Resource metadata changed unexpectedly",
                        status_code=502,
                    )
                continue
            connection.execute(
                """
                INSERT INTO module_task_output_resources (
                    resource_ref, task_id, resource_id, filename,
                    media_type, size, expires_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    task_id,
                    resource["resource_id"],
                    *metadata,
                    _utc_now(),
                ),
            )

    @staticmethod
    def _transition_allowed(old: str, new: str) -> bool:
        if old == new:
            return True
        if old in TERMINAL_TASK_STATES:
            return False
        if new in TERMINAL_TASK_STATES:
            return True
        transitions = {
            "submitting": PUBLIC_TASK_STATES,
            "queued": {"running", "waiting_approval", "cancel_requested"},
            "running": {"waiting_approval", "cancel_requested"},
            "waiting_approval": {"running", "cancel_requested"},
            "cancel_requested": {"running"},
        }
        return new in transitions.get(old, set())

    def _update_summary(
        self,
        task_id: str,
        summary: dict[str, Any],
    ) -> None:
        now = _utc_now()
        with self._connection(write=True, immediate=True) as connection:
            row = connection.execute(
                "SELECT state FROM module_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            if row is None:
                raise ModuleTaskError(
                    "task_not_found",
                    "Task was not found",
                    status_code=404,
                )
            if not self._transition_allowed(row["state"], summary["state"]):
                raise ModuleTaskError(
                    "invalid_task_transition",
                    "Module returned an invalid task transition",
                    status_code=502,
                )
            self._store_resources(
                connection,
                task_id,
                summary.get("resources", []),
            )
            terminal_at = (
                now if summary["state"] in TERMINAL_TASK_STATES else None
            )
            connection.execute(
                """
                UPDATE module_tasks
                SET state = ?, status_sync = 'current', outcome_code = ?,
                    last_cursor = MAX(last_cursor, ?), updated_at = ?,
                    terminal_at = COALESCE(terminal_at, ?),
                    projection_state = CASE
                        WHEN ? IN ('failed', 'cancelled') THEN 'suppressed'
                        ELSE projection_state
                    END
                WHERE id = ?
                """,
                (
                    summary["state"],
                    summary.get("outcome_code"),
                    summary["last_event_id"],
                    now,
                    terminal_at,
                    summary["state"],
                    task_id,
                ),
            )
        if summary["state"] in TERMINAL_TASK_STATES:
            self.revoke_task_capabilities(task_id)
            self._schedule_input_resource_cleanup(task_id, now=now)

    async def _apply_projection(
        self,
        task_id: str,
        action: dict[str, Any],
        summary: dict[str, Any],
    ) -> None:
        if summary["state"] in {"failed", "cancelled"}:
            with self._connection(write=True) as connection:
                connection.execute(
                    """
                    UPDATE module_tasks SET projection_state = 'suppressed'
                    WHERE id = ? AND projection_state = 'pending'
                    """,
                    (task_id,),
                )
            return
        projection = summary.get("chat_projection")
        if (
            summary["state"] != "succeeded"
            or not action["supports_chat_projection"]
            or projection is None
        ):
            return
        now = _utc_now()
        title_context = None
        with self._connection(write=True, immediate=True) as connection:
            row = connection.execute(
                """
                SELECT
                    chat_id,
                    user_message_id,
                    assistant_message_id,
                    projection_state
                FROM module_tasks WHERE id = ?
                """,
                (task_id,),
            ).fetchone()
            if (
                row is None
                or row["chat_id"] is None
                or row["assistant_message_id"] is not None
                or row["projection_state"] != "pending"
            ):
                return
            chat = connection.execute(
                "SELECT 1 FROM chats WHERE id = ?",
                (row["chat_id"],),
            ).fetchone()
            if chat is None:
                connection.execute(
                    """
                    UPDATE module_tasks SET projection_state = 'suppressed'
                    WHERE id = ?
                    """,
                    (task_id,),
                )
                return
            sequence = connection.execute(
                """
                SELECT COALESCE(MAX(sequence), 0) + 1
                FROM messages WHERE chat_id = ?
                """,
                (row["chat_id"],),
            ).fetchone()[0]
            message_id = str(uuid.uuid4())
            connection.execute(
                """
                INSERT INTO messages (
                    id, chat_id, role, content, created_at,
                    author_user_id, sequence
                ) VALUES (?, ?, 'assistant', ?, ?, NULL, ?)
                """,
                (
                    message_id,
                    row["chat_id"],
                    projection,
                    now,
                    sequence,
                ),
            )
            connection.execute(
                "UPDATE chats SET updated_at = ? WHERE id = ?",
                (now, row["chat_id"]),
            )
            connection.execute(
                """
                UPDATE module_tasks
                SET assistant_message_id = ?, projection_state = 'projected',
                    updated_at = ?
                WHERE id = ?
                """,
                (message_id, now, task_id),
            )
            user_message = connection.execute(
                "SELECT content FROM messages WHERE id = ?",
                (row["user_message_id"],),
            ).fetchone()
            if user_message is not None:
                title_context = (
                    row["chat_id"],
                    user_message["content"],
                    projection,
                )

        if title_context is not None and self.chat_auto_title is not None:
            try:
                await self.chat_auto_title(*title_context)
            except Exception:
                logger.warning(
                    "Chat auto-title callback failed for task %s",
                    task_id,
                    exc_info=True,
                )

    async def reconcile(self, task_id: str) -> dict[str, Any] | None:
        row = self._task_row(task_id)
        if (
            row["state"] in TERMINAL_TASK_STATES
            and row["status_sync"] == "unreachable"
        ):
            return None
        try:
            target, action = self._target_and_action_for_row(row)
            status, payload = await self.registry.client.request_json(
                target["base_url"],
                f"{TASKS_PATH}/{quote(task_id, safe='')}",
                token=target["credential"],
                max_bytes=MAX_TASK_RESPONSE_BYTES,
            )
            if status != 200:
                raise ModuleTaskError(
                    "module_task_unavailable",
                    "Module task is unavailable",
                    status_code=502,
                )
            summary = self._validate_summary_for_row(row, action, payload)
            self._update_summary(task_id, summary)
            self._register_artifacts(task_id, summary.get("artifacts", []))
            await self._apply_projection(task_id, action, summary)
            return summary
        except ModuleTransportError:
            self._fail_stream(
                task_id,
                outcome_code="module_unreachable",
            )
            return None
        except (ModuleRegistryError, ModuleTaskError) as error:
            converted = self._module_error(error)
            self._fail_stream(
                task_id,
                outcome_code=converted.code,
            )
            return None

    async def get(
        self,
        task_id: str,
        *,
        principal_user_id: str,
        principal_role: str,
    ) -> dict[str, Any]:
        row = self._task_row(task_id)
        remote = await self.reconcile(task_id)
        row = self._task_row(task_id)
        return self._public_task(
            row,
            principal_user_id=principal_user_id,
            principal_role=principal_role,
            remote=remote,
        )

    async def list(
        self,
        *,
        principal_user_id: str,
        principal_role: str,
        limit: int = 50,
        state: str | None = None,
        chat_id: str | None = None,
        module_id: str | None = None,
        action_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= MAX_TASK_LIST_LIMIT:
            raise ModuleTaskError(
                "invalid_task_limit",
                "Task list limit is invalid",
            )
        if state is not None and state not in PUBLIC_TASK_STATES:
            raise ModuleTaskError(
                "invalid_task_state",
                "Task state filter is invalid",
            )
        for name, value in (
            ("module_id", module_id),
            ("action_id", action_id),
        ):
            if value is not None and (
                not isinstance(value, str)
                or not value
                or len(value) > 128
            ):
                raise ModuleTaskError(
                    "invalid_task_filter",
                    f"Task {name} filter is invalid",
                )
        clauses = ["visible = 1"]
        parameters: list[Any] = []
        if state is not None:
            clauses.append("state = ?")
            parameters.append(state)
        if chat_id is not None:
            clauses.append("chat_id = ?")
            parameters.append(chat_id)
        if module_id is not None:
            clauses.append("module_id = ?")
            parameters.append(module_id)
        if action_id is not None:
            clauses.append("action_id = ?")
            parameters.append(action_id)
        parameters.append(limit)
        with self._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM module_tasks
                WHERE {' AND '.join(clauses)}
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                parameters,
            ).fetchall()
        results = []
        for row in rows:
            remote = None
            if row["state"] not in TERMINAL_TASK_STATES:
                remote = await self.reconcile(row["id"])
            current = self._task_row(row["id"])
            results.append(
                self._public_task(
                    current,
                    principal_user_id=principal_user_id,
                    principal_role=principal_role,
                    remote=remote,
                )
            )
        return results

    async def reconcile_chat(self, chat_id: str) -> None:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT id FROM module_tasks
                WHERE chat_id = ? AND visible = 1
                  AND (
                      state NOT IN ('succeeded','failed','cancelled')
                      OR projection_state = 'pending'
                  )
                ORDER BY created_at, id
                """,
                (chat_id,),
            ).fetchall()
        for row in rows:
            await self.reconcile(row["id"])

    def _apply_event(self, task_id: str, event: dict[str, Any]) -> None:
        data = event["data"]
        now = _utc_now()
        with self._connection(write=True, immediate=True) as connection:
            row = connection.execute(
                """
                SELECT state, last_cursor, outcome_code
                FROM module_tasks WHERE id = ?
                """,
                (task_id,),
            ).fetchone()
            if row is None:
                raise ModuleTaskError(
                    "task_not_found",
                    "Task was not found",
                    status_code=404,
                )
            try:
                validate_task_event(
                    event,
                    previous_event_id=row["last_cursor"],
                )
            except ModuleTaskProtocolError as error:
                raise self._module_error(error) from error
            next_state = row["state"]
            outcome_code = None
            if event["event"] in {"task.status", "task.terminal"}:
                next_state = data["state"]
                outcome_code = data.get("outcome_code")
                if not self._transition_allowed(row["state"], next_state):
                    raise ModuleTaskError(
                        "invalid_task_transition",
                        "Module returned an invalid task transition",
                        status_code=502,
                    )
            terminal_at = (
                now if next_state in TERMINAL_TASK_STATES else None
            )
            connection.execute(
                """
                UPDATE module_tasks
                SET state = ?, status_sync = 'current',
                    outcome_code = COALESCE(?, outcome_code),
                    last_cursor = ?, updated_at = ?,
                    terminal_at = COALESCE(terminal_at, ?),
                    projection_state = CASE
                        WHEN ? IN ('failed','cancelled') THEN 'suppressed'
                        ELSE projection_state
                    END
                WHERE id = ?
                """,
                (
                    next_state,
                    outcome_code,
                    event["id"],
                    now,
                    terminal_at,
                    next_state,
                    task_id,
                ),
            )
        if event["event"] == "artifact.added":
            self._register_artifacts(task_id, [data])
        if next_state in TERMINAL_TASK_STATES:
            self.revoke_task_capabilities(task_id)
            self._schedule_input_resource_cleanup(task_id, now=now)

    def _fail_stream(
        self,
        task_id: str,
        *,
        outcome_code: str,
    ) -> dict[str, Any]:
        now = _utc_now()
        with self._connection(write=True, immediate=True) as connection:
            row = connection.execute(
                """
                SELECT state, last_cursor, outcome_code
                FROM module_tasks WHERE id = ?
                """,
                (task_id,),
            ).fetchone()
            if row is None:
                raise ModuleTaskError(
                    "task_not_found",
                    "Task was not found",
                    status_code=404,
                )
            if row["state"] in TERMINAL_TASK_STATES:
                event_id = max(1, row["last_cursor"])
                final_state = row["state"]
                final_code = (
                    row["outcome_code"]
                    if row["outcome_code"] is not None
                    else outcome_code
                )
            else:
                event_id = max(1, row["last_cursor"] + 1)
                final_state = "failed"
                final_code = outcome_code
                connection.execute(
                    """
                    UPDATE module_tasks
                    SET state = 'failed', status_sync = 'unreachable',
                        outcome_code = ?, last_cursor = ?,
                        updated_at = ?, terminal_at = ?,
                        projection_state = 'suppressed'
                    WHERE id = ?
                    """,
                    (
                        final_code,
                        event_id,
                        now,
                        now,
                        task_id,
                    ),
                )
        self.revoke_task_capabilities(task_id)
        self._schedule_input_resource_cleanup(task_id, now=now)
        return {
            "id": event_id,
            "event": "task.terminal",
            "data": {
                "state": final_state,
                **(
                    {"outcome_code": final_code}
                    if final_state == "failed"
                    else {}
                ),
            },
        }

    async def stream_events(self, task_id: str, *, last_event_id: int):
        if not isinstance(last_event_id, int) or last_event_id < 0:
            raise ModuleTaskError(
                "invalid_event_cursor",
                "Last-Event-ID is invalid",
            )

        def known_terminal_event() -> tuple[bool, dict[str, Any] | None]:
            current = self._task_row(task_id)
            if current["state"] not in TERMINAL_TASK_STATES:
                return False, None
            if last_event_id >= max(1, current["last_cursor"]):
                return True, None
            data = {"state": current["state"]}
            if current["outcome_code"] is not None:
                data["outcome_code"] = current["outcome_code"]
            return (
                True,
                {
                    "id": max(1, current["last_cursor"]),
                    "event": "task.terminal",
                    "data": data,
                },
            )

        stream_cursor = last_event_id
        try:
            row = self._task_row(task_id)
            target, _action = self._target_and_action_for_row(row)
            async for event in self.registry.client.iter_sse(
                target["base_url"],
                f"{TASKS_PATH}/{quote(task_id, safe='')}/events",
                token=target["credential"],
                last_event_id=last_event_id,
                max_event_bytes=MAX_EVENT_BYTES,
            ):
                if event is None:
                    yield None
                    continue
                try:
                    validate_task_event(
                        event,
                        previous_event_id=stream_cursor,
                    )
                except ModuleTaskProtocolError as error:
                    raise self._module_error(error) from error
                stream_cursor = event["id"]
                current = self._task_row(task_id)
                is_new_event = event["id"] > current["last_cursor"]
                if is_new_event:
                    self._apply_event(task_id, event)
                terminal = (
                    event["event"] == "task.terminal"
                    or event["data"].get("state")
                    in TERMINAL_TASK_STATES
                )
                if terminal and is_new_event:
                    summary = await self.reconcile(task_id)
                    if summary is not None:
                        _target, action = self._target_and_action_for_row(
                            self._task_row(task_id)
                        )
                        await self._apply_projection(task_id, action, summary)
                yield event
        except ModuleTransportError:
            terminal, fallback = known_terminal_event()
            if terminal:
                if fallback is not None:
                    yield fallback
                return
            yield self._fail_stream(
                task_id,
                outcome_code="module_unreachable",
            )
            return
        except (ModuleRegistryError, ModuleTaskProtocolError) as error:
            terminal, fallback = known_terminal_event()
            if terminal:
                if fallback is not None:
                    yield fallback
                return
            converted = self._module_error(error)
            yield self._fail_stream(
                task_id,
                outcome_code=converted.code,
            )
            return
        except ModuleTaskError as error:
            terminal, fallback = known_terminal_event()
            if terminal:
                if fallback is not None:
                    yield fallback
                return
            yield self._fail_stream(
                task_id,
                outcome_code=error.code,
            )
            return

    def _require_control(
        self,
        row: Any,
        *,
        principal_user_id: str,
        principal_role: str,
    ) -> None:
        if (
            row["creator_user_id"] != principal_user_id
            and principal_role != "admin"
        ):
            raise ModuleTaskError(
                "task_control_forbidden",
                "Only the task creator or an administrator can control this task",
                status_code=403,
            )

    async def cancel(
        self,
        task_id: str,
        *,
        principal_user_id: str,
        principal_role: str,
    ) -> dict[str, Any]:
        row = self._task_row(task_id)
        self._require_control(
            row,
            principal_user_id=principal_user_id,
            principal_role=principal_role,
        )
        target, action = self._target_and_action_for_row(row)
        if not action["supports_cancel"]:
            raise ModuleTaskError(
                "task_cancel_unsupported",
                "This action does not support cancellation",
                status_code=409,
            )
        if row["state"] in TERMINAL_TASK_STATES:
            return self._public_task(
                row,
                principal_user_id=principal_user_id,
                principal_role=principal_role,
            )
        try:
            status, payload = await self.registry.client.request_json(
                target["base_url"],
                f"{TASKS_PATH}/{quote(task_id, safe='')}/cancel",
                method="POST",
                token=target["credential"],
                payload={},
                max_bytes=MAX_TASK_RESPONSE_BYTES,
            )
            if status not in {200, 202}:
                if status == 409:
                    raise ModuleTaskError(
                        "task_cancel_rejected",
                        "Module rejected cancellation",
                        status_code=409,
                    )
                raise ModuleTaskError(
                    "task_cancel_rejected",
                    "Module rejected cancellation",
                    status_code=502,
                )
            summary = self._validate_summary_for_row(row, action, payload)
            self._update_summary(task_id, summary)
        except ModuleTransportError:
            with self._connection(write=True) as connection:
                connection.execute(
                    """
                    UPDATE module_tasks
                    SET state = 'cancel_requested', status_sync = 'unreachable',
                        updated_at = ?
                    WHERE id = ? AND state NOT IN ('succeeded','failed','cancelled')
                    """,
                    (_utc_now(), task_id),
                )
        self.audit(
            principal_user_id,
            "module.task.cancel",
            "module_task",
            task_id,
            "success",
            {},
        )
        return self._public_task(
            self._task_row(task_id),
            principal_user_id=principal_user_id,
            principal_role=principal_role,
        )

    async def resolve_approval(
        self,
        task_id: str,
        approval_id: str,
        *,
        decision: str,
        principal_user_id: str,
        principal_role: str,
    ) -> dict[str, Any]:
        if (
            not isinstance(approval_id, str)
            or not approval_id
            or decision not in {"approve", "deny"}
        ):
            raise ModuleTaskError(
                "invalid_approval",
                "Approval request is invalid",
            )
        row = self._task_row(task_id)
        self._require_control(
            row,
            principal_user_id=principal_user_id,
            principal_role=principal_role,
        )
        with self._connection() as connection:
            recorded = connection.execute(
                """
                SELECT decision FROM module_task_approval_audit
                WHERE task_id = ? AND approval_id = ?
                """,
                (task_id, approval_id),
            ).fetchone()
        if recorded is not None:
            if recorded["decision"] != decision:
                raise ModuleTaskError(
                    "approval_conflict",
                    "Approval was already resolved differently",
                    status_code=409,
                )
            return self._public_task(
                row,
                principal_user_id=principal_user_id,
                principal_role=principal_role,
            )
        if row["state"] in TERMINAL_TASK_STATES:
            raise ModuleTaskError(
                "approval_terminal",
                "A terminal task cannot accept a new approval decision",
                status_code=409,
            )
        target, action = self._target_and_action_for_row(row)
        if not action["supports_approval"]:
            raise ModuleTaskError(
                "task_approval_unsupported",
                "This action does not support approval",
                status_code=409,
            )
        try:
            status, payload = await self.registry.client.request_json(
                target["base_url"],
                (
                    f"{TASKS_PATH}/{quote(task_id, safe='')}/approvals/"
                    f"{quote(approval_id, safe='')}"
                ),
                method="POST",
                token=target["credential"],
                payload={"decision": decision},
                max_bytes=MAX_TASK_RESPONSE_BYTES,
            )
        except ModuleRegistryError as error:
            raise self._module_error(error) from error
        if status == 409:
            raise ModuleTaskError(
                "approval_conflict",
                "Approval was already resolved differently",
                status_code=409,
            )
        if status in {404, 410}:
            raise ModuleTaskError(
                "approval_expired",
                "Approval is no longer available",
                status_code=409,
            )
        if status != 200:
            raise ModuleTaskError(
                "approval_rejected",
                "Module rejected the approval decision",
                status_code=502,
            )
        summary = self._validate_summary_for_row(row, action, payload)
        self._update_summary(task_id, summary)
        with self._connection(write=True, immediate=True) as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO module_task_approval_audit (
                        task_id, approval_id, decision,
                        actor_user_id, resolved_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        approval_id,
                        decision,
                        principal_user_id,
                        _utc_now(),
                    ),
                )
            except sqlite3.IntegrityError:
                recorded = connection.execute(
                    """
                    SELECT decision FROM module_task_approval_audit
                    WHERE task_id = ? AND approval_id = ?
                    """,
                    (task_id, approval_id),
                ).fetchone()
                if recorded is None or recorded["decision"] != decision:
                    raise ModuleTaskError(
                        "approval_conflict",
                        "Approval was already resolved differently",
                        status_code=409,
                    ) from None
        self.audit(
            principal_user_id,
            "module.task.approval",
            "module_task",
            task_id,
            "success",
            {"approval_id": approval_id, "decision": decision},
        )
        return self._public_task(
            self._task_row(task_id),
            principal_user_id=principal_user_id,
            principal_role=principal_role,
        )

    async def artifact(
        self,
        task_id: str,
        artifact_ref: str,
    ) -> dict[str, Any]:
        row = self._task_row(task_id)
        with self._connection() as connection:
            artifact = connection.execute(
                """
                SELECT * FROM module_task_artifacts
                WHERE task_id = ? AND artifact_ref = ?
                """,
                (task_id, artifact_ref),
            ).fetchone()
        if artifact is None:
            raise ModuleTaskError(
                "artifact_not_found",
                "Artifact was not found",
                status_code=404,
            )
        if artifact["expires_at"] is not None and _parse_utc(
            artifact["expires_at"]
        ) <= datetime.now(timezone.utc):
            raise ModuleTaskError(
                "artifact_expired",
                "Artifact has expired",
                status_code=410,
            )
        target, action = self._target_and_action_for_row(row)
        if not action["supports_artifacts"]:
            raise ModuleTaskError(
                "artifact_not_supported",
                "This action does not support artifacts",
                status_code=409,
            )
        try:
            status, headers, body = await self.registry.client.request_bytes(
                target["base_url"],
                (
                    f"{TASKS_PATH}/{quote(task_id, safe='')}/artifacts/"
                    f"{quote(artifact['artifact_id'], safe='')}"
                ),
                token=target["credential"],
                max_bytes=min(MAX_ARTIFACT_BYTES, artifact["size"]),
            )
        except ModuleRegistryError as error:
            raise self._module_error(error) from error
        content_type = headers.get("content-type", "").split(";", 1)[0].strip()
        if (
            status != 200
            or len(body) != artifact["size"]
            or content_type != artifact["media_type"]
        ):
            raise ModuleTaskError(
                "invalid_artifact_response",
                "Module returned an invalid artifact",
                status_code=502,
            )
        return {
            "body": body,
            "filename": artifact["filename"],
            "media_type": artifact["media_type"],
        }

    @staticmethod
    def _expected_resource_range(
        range_header: str | None,
        size: int,
    ) -> tuple[int, int] | None:
        if range_header is None:
            return None
        raw = range_header.removeprefix("bytes=")
        start_text, end_text = raw.split("-", 1)
        if start_text:
            start = int(start_text)
            if start >= size:
                return None
            end = int(end_text) if end_text else size - 1
            return start, min(end, size - 1)
        suffix = int(end_text)
        if suffix == 0 or size == 0:
            return None
        return max(0, size - suffix), size - 1

    @asynccontextmanager
    async def task_resource_stream(
        self,
        task_id: str,
        resource_ref: str,
        *,
        principal_user_id: str,
        principal_role: str,
        method: str,
        range_header: str | None,
    ):
        row = self._task_row(task_id)
        if (
            row["creator_user_id"] != principal_user_id
            and principal_role != "admin"
        ):
            raise ModuleTaskError(
                "task_resource_forbidden",
                "Task resource is not available to this user",
                status_code=403,
            )
        with self._connection() as connection:
            resource = connection.execute(
                """
                SELECT * FROM module_task_output_resources
                WHERE task_id = ? AND resource_ref = ?
                """,
                (task_id, resource_ref),
            ).fetchone()
        if resource is None:
            raise ModuleTaskError(
                "task_resource_not_found",
                "Task resource was not found",
                status_code=404,
            )
        if resource["expires_at"] is not None and _parse_utc(
            resource["expires_at"]
        ) <= datetime.now(timezone.utc):
            raise ModuleTaskError(
                "task_resource_expired",
                "Task resource has expired",
                status_code=410,
            )
        target, action = self._target_and_action_for_row(row)
        if not action.get("supports_resources", False):
            raise ModuleTaskError(
                "task_resource_not_supported",
                "This action does not support task resources",
                status_code=409,
            )
        path = (
            f"{TASKS_PATH}/{quote(task_id, safe='')}/resources/"
            f"{quote(resource['resource_id'], safe='')}"
        )
        expected_range = self._expected_resource_range(
            range_header,
            resource["size"],
        )
        try:
            async with self.registry.client.stream_bytes(
                target["base_url"],
                path,
                method=method,
                token=target["credential"],
                range_header=range_header,
            ) as response:
                headers = {
                    key.lower(): value
                    for key, value in response.headers.items()
                    if key.lower()
                    in {
                        "accept-ranges",
                        "content-encoding",
                        "content-length",
                        "content-range",
                        "content-type",
                    }
                }
                if range_header is None:
                    expected_status = 200
                elif expected_range is None:
                    expected_status = 416
                else:
                    expected_status = 206
                if response.status != expected_status:
                    raise ModuleTaskError(
                        "invalid_task_resource_response",
                        "Module returned an invalid task resource status",
                        status_code=502,
                    )
                if response.status == 416:
                    if headers.get("content-range") != (
                        f"bytes */{resource['size']}"
                    ):
                        raise ModuleTaskError(
                            "invalid_task_resource_response",
                            "Module returned an invalid unsatisfied range",
                            status_code=502,
                        )
                else:
                    content_type = headers.get(
                        "content-type",
                        "",
                    ).split(";", 1)[0].strip().lower()
                    if content_type != resource["media_type"].lower():
                        raise ModuleTaskError(
                            "invalid_task_resource_response",
                            "Module returned an invalid task resource type",
                            status_code=502,
                        )
                    if headers.get("content-encoding", "identity") != "identity":
                        raise ModuleTaskError(
                            "invalid_task_resource_response",
                            "Module returned an encoded task resource",
                            status_code=502,
                        )
                    try:
                        content_length = int(headers["content-length"])
                    except (KeyError, ValueError):
                        raise ModuleTaskError(
                            "invalid_task_resource_response",
                            "Module returned an invalid task resource length",
                            status_code=502,
                        ) from None
                    if response.status == 200:
                        valid_length = content_length == resource["size"]
                    else:
                        match = _CONTENT_RANGE.fullmatch(
                            headers.get("content-range", "")
                        )
                        valid_length = bool(
                            match
                            and expected_range is not None
                            and (
                                int(match.group(1)),
                                int(match.group(2)),
                            )
                            == expected_range
                            and int(match.group(3)) == resource["size"]
                            and content_length
                            == expected_range[1] - expected_range[0] + 1
                        )
                    if not valid_length:
                        raise ModuleTaskError(
                            "invalid_task_resource_response",
                            "Module returned an invalid task resource length",
                            status_code=502,
                        )
                yield {
                    "status": response.status,
                    "headers": headers,
                    "body": response.content,
                    "filename": resource["filename"],
                    "media_type": resource["media_type"],
                    "size": resource["size"],
                }
        except ModuleRegistryError as error:
            raise self._module_error(error) from error

    def revoke_task_capabilities(self, task_id: str) -> None:
        with self._connection(write=True) as connection:
            connection.execute(
                """
                UPDATE module_capability_tokens
                SET revoked_at = COALESCE(revoked_at, ?)
                WHERE task_id = ?
                """,
                (_utc_now(), task_id),
            )

    def revoke_user_capabilities(self, user_id: str) -> None:
        with self._connection(write=True) as connection:
            connection.execute(
                """
                UPDATE module_capability_tokens
                SET revoked_at = COALESCE(revoked_at, ?)
                WHERE task_id IN (
                    SELECT id FROM module_tasks WHERE creator_user_id = ?
                )
                """,
                (_utc_now(), user_id),
            )

    def revoke_registration_capabilities(self, registration_id: str) -> None:
        with self._connection(write=True) as connection:
            connection.execute(
                """
                UPDATE module_capability_tokens
                SET revoked_at = COALESCE(revoked_at, ?)
                WHERE registration_id = ?
                """,
                (_utc_now(), registration_id),
            )

    def force_disconnect(self, registration_id: str) -> None:
        self.revoke_registration_capabilities(registration_id)
        with self._connection(write=True) as connection:
            connection.execute(
                """
                UPDATE module_tasks
                SET status_sync = 'unreachable', updated_at = ?
                WHERE registration_id = ?
                  AND state NOT IN ('succeeded','failed','cancelled')
                """,
                (_utc_now(), registration_id),
            )

    def _consume_capability(
        self,
        token: str,
        capability: str,
    ) -> tuple[Any, dict[str, Any]]:
        if not isinstance(token, str) or len(token) > 4096:
            raise ModuleTaskError(
                "capability_token_invalid",
                "Capability token is invalid",
                status_code=401,
            )
        digest = _token_digest(token)
        now = datetime.now(timezone.utc)
        with self._connection(write=True, immediate=True) as connection:
            row = connection.execute(
                """
                SELECT tokens.*, tasks.state, tasks.status_sync,
                       tasks.module_id, tasks.creator_user_id,
                       users.enabled AS creator_enabled
                FROM module_capability_tokens AS tokens
                JOIN module_tasks AS tasks ON tasks.id = tokens.task_id
                JOIN users ON users.id = tasks.creator_user_id
                WHERE tokens.token_digest = ?
                """,
                (digest,),
            ).fetchone()
            if (
                row is None
                or row["capability"] != capability
                or row["revoked_at"] is not None
                or _parse_utc(row["expires_at"]) <= now
                or row["state"] in TERMINAL_TASK_STATES
                or row["status_sync"] != "current"
                or not row["creator_enabled"]
                or (
                    row["max_uses"] is not None
                    and row["use_count"] >= row["max_uses"]
                )
            ):
                raise ModuleTaskError(
                    "capability_token_invalid",
                    "Capability token is invalid or expired",
                    status_code=401,
                )
            connection.execute(
                """
                UPDATE module_capability_tokens
                SET use_count = use_count + 1
                WHERE token_digest = ?
                """,
                (digest,),
            )
        return row, json.loads(row["scope_json"])

    async def _preflight_capability(
        self,
        token: str,
        capability: str,
    ) -> None:
        if not isinstance(token, str) or len(token) > 4096:
            raise ModuleTaskError(
                "capability_token_invalid",
                "Capability token is invalid",
                status_code=401,
            )
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT tokens.task_id, tokens.capability, tokens.revoked_at,
                       tokens.expires_at, users.enabled AS creator_enabled
                FROM module_capability_tokens AS tokens
                JOIN module_tasks AS tasks ON tasks.id = tokens.task_id
                JOIN users ON users.id = tasks.creator_user_id
                WHERE tokens.token_digest = ?
                """,
                (_token_digest(token),),
            ).fetchone()
        if (
            row is None
            or row["capability"] != capability
            or row["revoked_at"] is not None
            or _parse_utc(row["expires_at"]) <= datetime.now(timezone.utc)
            or not row["creator_enabled"]
        ):
            raise ModuleTaskError(
                "capability_token_invalid",
                "Capability token is invalid or expired",
                status_code=401,
            )
        await self.reconcile(row["task_id"])

    @staticmethod
    def _conversation_context(
        connection: sqlite3.Connection,
        *,
        chat_id: str,
        current_task_id: str,
    ) -> dict[str, Any]:
        current_task = connection.execute(
            """
            SELECT id, module_id, action_id, state, user_message_id
            FROM module_tasks
            WHERE id = ? AND chat_id = ? AND visible = 1
            """,
            (current_task_id, chat_id),
        ).fetchone()
        if current_task is None:
            raise ModuleTaskError(
                "chat_history_unavailable",
                "Current chat task is unavailable",
                status_code=502,
            )

        recent_messages = connection.execute(
            """
            SELECT id, role, content, sequence, rowid
            FROM (
                SELECT id, role, content, sequence, rowid
                FROM messages
                WHERE chat_id = ?
                ORDER BY sequence DESC, rowid DESC
                LIMIT ?
            )
            ORDER BY sequence, rowid
            """,
            (chat_id, MAX_CHAT_HISTORY_MESSAGES + 2),
        ).fetchall()
        message_by_id = {
            message["id"]: message
            for message in recent_messages
        }
        recent_ids = list(message_by_id)
        placeholders = ",".join("?" for _value in recent_ids)
        task_rows = connection.execute(
            f"""
            SELECT id, module_id, action_id, state, outcome_code,
                   user_message_id, assistant_message_id
            FROM module_tasks
            WHERE chat_id = ? AND visible = 1
              AND (
                  id = ?
                  OR user_message_id IN ({placeholders})
                  OR assistant_message_id IN ({placeholders})
              )
            """,
            (
                chat_id,
                current_task_id,
                *recent_ids,
                *recent_ids,
            ),
        ).fetchall()

        linked_ids = {
            message_id
            for task in task_rows
            for message_id in (
                task["user_message_id"],
                task["assistant_message_id"],
            )
            if message_id is not None
        }
        missing_ids = sorted(linked_ids - set(message_by_id))
        if missing_ids:
            missing_placeholders = ",".join("?" for _value in missing_ids)
            partner_messages = connection.execute(
                f"""
                SELECT id, role, content, sequence, rowid
                FROM messages
                WHERE chat_id = ? AND id IN ({missing_placeholders})
                """,
                (chat_id, *missing_ids),
            ).fetchall()
            message_by_id.update(
                {
                    message["id"]: message
                    for message in partner_messages
                }
            )

        task_by_message_id = {
            message_id: task
            for task in task_rows
            for message_id in (
                task["user_message_id"],
                task["assistant_message_id"],
            )
            if message_id is not None
        }
        ordered_messages = sorted(
            message_by_id.values(),
            key=lambda message: (
                message["sequence"],
                message["rowid"],
            ),
        )
        units: list[tuple[tuple[int, int], dict[str, Any]]] = []
        seen_tasks: set[str] = set()
        consumed_ordinary: set[str] = set()

        for index, message in enumerate(ordered_messages):
            task = task_by_message_id.get(message["id"])
            if task is not None:
                if (
                    task["id"] == current_task_id
                    or task["id"] in seen_tasks
                ):
                    continue
                seen_tasks.add(task["id"])
                user_message = message_by_id.get(task["user_message_id"])
                assistant_message = message_by_id.get(
                    task["assistant_message_id"]
                )
                valid_user = (
                    user_message
                    if user_message is not None
                    and user_message["role"] == "user"
                    else None
                )
                valid_assistant = (
                    assistant_message
                    if assistant_message is not None
                    and assistant_message["role"] == "assistant"
                    else None
                )
                if task["state"] == "failed":
                    status = "failed"
                elif task["state"] == "cancelled":
                    status = "cancelled"
                elif (
                    task["state"] == "succeeded"
                    and valid_user is not None
                    and valid_assistant is not None
                ):
                    status = "complete"
                else:
                    status = "incomplete"
                task_messages = [
                    item
                    for item in (valid_user, valid_assistant)
                    if item is not None
                ]
                if not task_messages:
                    continue
                first = min(
                    task_messages,
                    key=lambda item: (item["sequence"], item["rowid"]),
                )
                units.append(
                    (
                        (first["sequence"], first["rowid"]),
                        {
                            "source": "module",
                            "status": status,
                            "task": {
                                "task_id": task["id"],
                                "module_id": task["module_id"],
                                "action_id": task["action_id"],
                                "state": task["state"],
                                "outcome_code": task["outcome_code"],
                            },
                            "user": (
                                {"content": valid_user["content"]}
                                if valid_user is not None
                                else None
                            ),
                            "assistant": (
                                {"content": valid_assistant["content"]}
                                if valid_assistant is not None
                                else None
                            ),
                        },
                    )
                )
                continue

            if (
                message["id"] == current_task["user_message_id"]
                or message["id"] in consumed_ordinary
            ):
                continue
            user_message = message if message["role"] == "user" else None
            assistant_message = (
                message if message["role"] == "assistant" else None
            )
            if user_message is not None and index + 1 < len(ordered_messages):
                following = ordered_messages[index + 1]
                if (
                    following["role"] == "assistant"
                    and following["id"] not in task_by_message_id
                    and following["id"]
                    != current_task["user_message_id"]
                ):
                    assistant_message = following
                    consumed_ordinary.add(following["id"])
            units.append(
                (
                    (message["sequence"], message["rowid"]),
                    {
                        "source": "chat",
                        "status": (
                            "complete"
                            if (
                                user_message is not None
                                and assistant_message is not None
                            )
                            else "incomplete"
                        ),
                        "task": None,
                        "user": (
                            {"content": user_message["content"]}
                            if user_message is not None
                            else None
                        ),
                        "assistant": (
                            {"content": assistant_message["content"]}
                            if assistant_message is not None
                            else None
                        ),
                    },
                )
            )

        selected_turns = []
        selected_messages = 0
        selected_characters = 0
        for _sort_key, turn in reversed(sorted(units, key=lambda item: item[0])):
            turn_messages = [
                message
                for message in (turn["user"], turn["assistant"])
                if message is not None
            ]
            next_messages = selected_messages + len(turn_messages)
            next_characters = selected_characters + sum(
                len(message["content"])
                for message in turn_messages
            )
            if (
                next_messages > MAX_CHAT_HISTORY_MESSAGES
                or next_characters > MAX_CHAT_HISTORY_CHARACTERS
            ):
                break
            selected_turns.append(turn)
            selected_messages = next_messages
            selected_characters = next_characters
        selected_turns.reverse()

        return {
            "schema_version": "1",
            "turns": selected_turns,
            "current_task": {
                "task_id": current_task["id"],
                "module_id": current_task["module_id"],
                "action_id": current_task["action_id"],
                "state": current_task["state"],
            },
        }

    async def capability_chat_read(self, token: str) -> dict[str, Any]:
        await self._preflight_capability(token, "chat.read")
        row, scope = self._consume_capability(token, "chat.read")
        chat_id = scope.get("chat_id")
        with self._connection() as connection:
            messages = connection.execute(
                """
                SELECT role, content, created_at
                FROM (
                    SELECT role, content, created_at, sequence, rowid
                    FROM messages
                    WHERE chat_id = ?
                    ORDER BY sequence DESC, rowid DESC
                    LIMIT ?
                )
                ORDER BY sequence, rowid
                """,
                (chat_id, MAX_CHAT_HISTORY_MESSAGES),
            ).fetchall()
            conversation_context = self._conversation_context(
                connection,
                chat_id=chat_id,
                current_task_id=row["task_id"],
            )
        bounded_messages = []
        character_count = 0
        for message in reversed(messages):
            content = message["content"]
            if (
                character_count + len(content)
                > MAX_CHAT_HISTORY_CHARACTERS
            ):
                break
            bounded_messages.append(dict(message))
            character_count += len(content)
        bounded_messages.reverse()
        return {
            "task_id": row["task_id"],
            "chat_id": chat_id,
            "conversation_ref": f"chatraw-chat:{chat_id}",
            "actor_ref": f"chatraw-user:{row['creator_user_id']}",
            "messages": bounded_messages,
            "conversation_context": conversation_context,
        }

    async def capability_principal_read(
        self,
        token: str,
    ) -> dict[str, Any]:
        await self._preflight_capability(token, "principal.read")
        row, _scope = self._consume_capability(token, "principal.read")
        with self._connection() as connection:
            principal = connection.execute(
                """
                SELECT users.role
                FROM module_tasks
                JOIN users ON users.id = module_tasks.creator_user_id
                WHERE module_tasks.id = ?
                """,
                (row["task_id"],),
            ).fetchone()
        if principal is None:
            raise ModuleTaskError(
                "capability_principal_unavailable",
                "Task principal is unavailable",
                status_code=404,
            )
        return {
            "task_id": row["task_id"],
            "actor_ref": f"chatraw-user:{row['creator_user_id']}",
            "role": principal["role"],
        }

    async def capability_resource_read(
        self,
        token: str,
        resource_id: str,
    ) -> dict[str, Any]:
        await self._preflight_capability(token, "resource.read")
        row, scope = self._consume_capability(token, "resource.read")
        if resource_id not in scope.get("resource_ids", []):
            raise ModuleTaskError(
                "capability_scope_denied",
                "Resource is outside the capability scope",
                status_code=403,
            )
        with self._connection() as connection:
            resource = connection.execute(
                """
                SELECT id, filename, content, created_at
                FROM documents WHERE id = ?
                """,
                (resource_id,),
            ).fetchone()
        if resource is None:
            raise ModuleTaskError(
                "resource_not_found",
                "Resource was not found",
                status_code=404,
            )
        content = resource["content"] or ""
        if len(content.encode("utf-8")) > 2 * 1024 * 1024:
            raise ModuleTaskError(
                "resource_too_large",
                "Resource exceeds the capability size limit",
                status_code=413,
            )
        return {
            "task_id": row["task_id"],
            "resource": dict(resource),
        }

    async def capability_skill_read(
        self,
        token: str,
        skill_id: str,
    ) -> dict[str, Any]:
        await self._preflight_capability(token, "skill.read")
        row, scope = self._consume_capability(token, "skill.read")
        if skill_id not in scope.get("skill_ids", []):
            raise ModuleTaskError(
                "capability_scope_denied",
                "Skill is outside the capability scope",
                status_code=403,
            )
        with self._connection() as connection:
            skill = connection.execute(
                """
                SELECT skills.id, skills.name, skills.description,
                       versions.id AS version_id,
                       versions.commit_sha, versions.content_sha256,
                       versions.source_json, versions.skill_markdown,
                       versions.resources_json
                FROM module_task_skill_activations AS activations
                JOIN agent_skills AS skills
                  ON skills.id = activations.skill_id
                JOIN agent_skill_versions AS versions
                  ON versions.id = activations.version_id
                WHERE activations.task_id = ?
                  AND activations.skill_id = ?
                """,
                (row["task_id"], skill_id),
            ).fetchone()
        if skill is None:
            raise ModuleTaskError(
                "agent_skill_unavailable",
                "Agent skill snapshot is unavailable",
                status_code=404,
            )
        return {
            "task_id": row["task_id"],
            "skill": {
                "id": skill["id"],
                "version_id": skill["version_id"],
                "name": skill["name"],
                "description": skill["description"],
                "commit": skill["commit_sha"],
                "content_sha256": skill["content_sha256"],
                "source": json.loads(skill["source_json"]),
                "skill_markdown": skill["skill_markdown"],
                "resources": json.loads(skill["resources_json"]),
            },
        }

    async def capability_rule_read(
        self,
        token: str,
        document_id: str,
    ) -> dict[str, Any]:
        await self._preflight_capability(token, "rule.read")
        row, scope = self._consume_capability(token, "rule.read")
        if document_id not in scope.get("document_ids", []):
            raise ModuleTaskError(
                "capability_scope_denied",
                "Rule is outside the capability scope",
                status_code=403,
            )
        with self._connection() as connection:
            rule = connection.execute(
                """
                SELECT documents.id AS document_id,
                       documents.name,
                       versions.id AS compiled_version_id,
                       versions.source_version_id,
                       versions.specification_version,
                       versions.content_sha256,
                       versions.compiled_json,
                       activations.scope_snapshot
                FROM module_task_rule_activations AS activations
                JOIN agent_rule_documents AS documents
                  ON documents.id = activations.document_id
                JOIN agent_compiled_rule_versions AS versions
                  ON versions.id = activations.compiled_version_id
                WHERE activations.task_id = ?
                  AND activations.document_id = ?
                  AND versions.status = 'valid'
                """,
                (row["task_id"], document_id),
            ).fetchone()
        if rule is None or not rule["compiled_json"]:
            raise ModuleTaskError(
                "agent_rule_unavailable",
                "Agent rule snapshot is unavailable",
                status_code=404,
            )
        return {
            "task_id": row["task_id"],
            "rule": {
                "document_id": rule["document_id"],
                "compiled_version_id": rule["compiled_version_id"],
                "source_version_id": rule["source_version_id"],
                "name": rule["name"],
                "specification_version": rule[
                    "specification_version"
                ],
                "content_sha256": rule["content_sha256"],
                "scope": rule["scope_snapshot"],
                "compiled_rule": json.loads(rule["compiled_json"]),
            },
        }

    async def capability_resource_stream(
        self,
        token: str,
        resource_id: str,
    ) -> dict[str, Any]:
        await self._preflight_capability(token, "resource.stream")
        row, scope = self._consume_capability(token, "resource.stream")
        if resource_id not in scope.get("resource_ids", []):
            raise ModuleTaskError(
                "capability_scope_denied",
                "Resource is outside the capability scope",
                status_code=403,
            )
        with self._connection() as connection:
            resource = connection.execute(
                """
                SELECT resource_id, filename, media_type, size, sha256,
                       storage_name
                FROM module_task_input_resources
                WHERE resource_id = ? AND bound_task_id = ?
                """,
                (resource_id, row["task_id"]),
            ).fetchone()
        if resource is None:
            raise ModuleTaskError(
                "resource_not_found",
                "Resource was not found",
                status_code=404,
            )
        if Path(resource["storage_name"]).name != resource["storage_name"]:
            raise ModuleTaskError(
                "resource_integrity_error",
                "Resource storage is inconsistent",
                status_code=500,
            )
        path = self.resource_dir / resource["storage_name"]
        try:
            stat_result = path.stat()
        except FileNotFoundError:
            raise ModuleTaskError(
                "resource_not_found",
                "Resource was not found",
                status_code=404,
            ) from None
        if not path.is_file() or stat_result.st_size != resource["size"]:
            raise ModuleTaskError(
                "resource_integrity_error",
                "Resource storage is inconsistent",
                status_code=500,
            )
        return {
            "task_id": row["task_id"],
            "resource_id": resource["resource_id"],
            "filename": resource["filename"],
            "media_type": resource["media_type"],
            "size": resource["size"],
            "sha256": resource["sha256"],
            "path": path,
        }

    async def capability_model_invoke(
        self,
        token: str,
        prompt: Any,
    ) -> dict[str, Any]:
        await self._preflight_capability(token, "model.invoke")
        row, _scope = self._consume_capability(token, "model.invoke")
        if (
            not isinstance(prompt, str)
            or not prompt
            or len(prompt.encode("utf-8")) > 64 * 1024
        ):
            raise ModuleTaskError(
                "invalid_model_request",
                "Model prompt is invalid",
            )
        if self.model_invoke is None:
            raise ModuleTaskError(
                "model_unavailable",
                "Model capability is unavailable",
                status_code=503,
            )
        result = await self.model_invoke(prompt)
        return {"task_id": row["task_id"], "content": result}

    @staticmethod
    def _validate_structured_output_schema(
        output_schema: Any,
    ) -> dict[str, Any]:
        if (
            not isinstance(output_schema, dict)
            or output_schema.get("type") != "object"
            or output_schema.get("additionalProperties") is not False
        ):
            raise ModuleTaskError(
                "invalid_model_request",
                "Structured output schema must be a closed object",
            )
        try:
            encoded = json.dumps(
                output_schema,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError):
            raise ModuleTaskError(
                "invalid_model_request",
                "Structured output schema must be valid JSON",
            ) from None
        if len(encoded) > MAX_MODEL_STRUCTURED_SCHEMA_BYTES:
            raise ModuleTaskError(
                "model_request_too_large",
                "Structured output schema exceeds the size limit",
                status_code=413,
            )
        stack: list[tuple[Any, int]] = [(output_schema, 0)]
        nodes = 0
        while stack:
            value, depth = stack.pop()
            nodes += 1
            if nodes > 6000 or depth > 24:
                raise ModuleTaskError(
                    "invalid_model_request",
                    "Structured output schema is too complex",
                )
            if isinstance(value, dict):
                if any(
                    key in value
                    for key in ("$ref", "$dynamicRef", "$recursiveRef")
                ):
                    raise ModuleTaskError(
                        "invalid_model_request",
                        "Structured output schema references are not allowed",
                    )
                stack.extend((item, depth + 1) for item in value.values())
            elif isinstance(value, list):
                stack.extend((item, depth + 1) for item in value)
        try:
            Draft202012Validator.check_schema(output_schema)
        except SchemaError:
            raise ModuleTaskError(
                "invalid_model_request",
                "Structured output schema is invalid",
            ) from None
        return output_schema

    async def capability_model_invoke_v2(
        self,
        token: str,
        prompt: Any,
        output_schema: Any,
    ) -> dict[str, Any]:
        await self._preflight_capability(token, "model.invoke.v2")
        row, _scope = self._consume_capability(token, "model.invoke.v2")
        if (
            not isinstance(prompt, str)
            or not prompt
            or len(prompt.encode("utf-8")) > 64 * 1024
        ):
            raise ModuleTaskError(
                "invalid_model_request",
                "Model prompt is invalid",
            )
        schema = self._validate_structured_output_schema(output_schema)
        try:
            request_size = len(
                json.dumps(
                    {"prompt": prompt, "output_schema": schema},
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
            )
        except (TypeError, ValueError):
            raise ModuleTaskError(
                "invalid_model_request",
                "Structured model request must be valid JSON",
            ) from None
        if request_size > MAX_MODEL_STRUCTURED_REQUEST_BYTES:
            raise ModuleTaskError(
                "model_request_too_large",
                "Structured model request exceeds the size limit",
                status_code=413,
            )
        if self.model_invoke_v2 is None:
            raise ModuleTaskError(
                "model_unavailable",
                "Structured model capability is unavailable",
                status_code=503,
            )
        result = await self.model_invoke_v2(prompt, schema)
        if not isinstance(result, dict):
            raise ModuleTaskError(
                "model_response_invalid",
                "Structured model response is invalid",
                status_code=502,
            )
        try:
            json.dumps(result, allow_nan=False)
        except (TypeError, ValueError):
            raise ModuleTaskError(
                "model_response_invalid",
                "Structured model response is not valid JSON",
                status_code=502,
            ) from None
        try:
            Draft202012Validator(schema).validate(result)
        except ValidationError:
            raise ModuleTaskError(
                "model_response_schema_invalid",
                "Structured model response does not match the schema",
                status_code=502,
            ) from None
        return {"task_id": row["task_id"], "output": result}

    @staticmethod
    def _validate_model_chat_request(
        request: Any,
        allowed_profiles: list[str],
    ) -> dict[str, Any]:
        if not isinstance(request, dict):
            raise ModuleTaskError(
                "invalid_model_request",
                "Model request must be an object",
            )
        allowed_fields = {
            "profile",
            "messages",
            "tools",
            "tool_choice",
            "response_format",
            "temperature",
            "top_p",
            "max_tokens",
            "parallel_tool_calls",
            "timeout_seconds",
        }
        if set(request) - allowed_fields:
            raise ModuleTaskError(
                "invalid_model_request",
                "Model request fields are invalid",
            )
        profile = request.get("profile")
        messages = request.get("messages")
        if (
            profile not in allowed_profiles
            or not isinstance(messages, list)
            or not 1 <= len(messages) <= 256
        ):
            raise ModuleTaskError(
                "invalid_model_request",
                "Model profile or messages are invalid",
            )
        try:
            encoded = json.dumps(
                request,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError):
            raise ModuleTaskError(
                "invalid_model_request",
                "Model request must be valid JSON",
            ) from None
        if len(encoded) > MAX_MODEL_CHAT_REQUEST_BYTES:
            raise ModuleTaskError(
                "model_request_too_large",
                "Model request exceeds the size limit",
                status_code=413,
            )
        valid_roles = {"system", "user", "assistant", "tool"}
        for message in messages:
            if (
                not isinstance(message, dict)
                or message.get("role") not in valid_roles
                or set(message)
                - {
                    "role",
                    "content",
                    "name",
                    "tool_call_id",
                    "tool_calls",
                }
            ):
                raise ModuleTaskError(
                    "invalid_model_request",
                    "Model messages are invalid",
                )
        tools = request.get("tools", [])
        if (
            not isinstance(tools, list)
            or len(tools) > 128
            or any(
                not isinstance(tool, dict)
                or tool.get("type") != "function"
                or not isinstance(tool.get("function"), dict)
                for tool in tools
            )
        ):
            raise ModuleTaskError(
                "invalid_model_request",
                "Model tools are invalid",
            )
        timeout_seconds = request.get("timeout_seconds", 300)
        if (
            not isinstance(timeout_seconds, int)
            or isinstance(timeout_seconds, bool)
            or not 180 <= timeout_seconds <= 900
        ):
            raise ModuleTaskError(
                "invalid_model_timeout",
                "Model timeout must be between 180 and 900 seconds",
            )
        max_tokens = request.get("max_tokens")
        if max_tokens is not None and (
            not isinstance(max_tokens, int)
            or isinstance(max_tokens, bool)
            or not 1 <= max_tokens <= 65536
        ):
            raise ModuleTaskError(
                "invalid_model_request",
                "Model max_tokens is invalid",
            )
        for field, minimum, maximum in (
            ("temperature", 0, 2),
            ("top_p", 0, 1),
        ):
            value = request.get(field)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not minimum <= value <= maximum
            ):
                raise ModuleTaskError(
                    "invalid_model_request",
                    f"Model {field} is invalid",
                )
        return request

    async def capability_model_chat_completion(
        self,
        token: str,
        request: Any,
    ) -> dict[str, Any]:
        await self._preflight_capability(
            token,
            "model.chat.completions",
        )
        row, scope = self._consume_capability(
            token,
            "model.chat.completions",
        )
        payload = self._validate_model_chat_request(
            request,
            scope.get("profiles", []),
        )
        if self.model_chat_completion is None:
            raise ModuleTaskError(
                "model_unavailable",
                "Model capability is unavailable",
                status_code=503,
            )
        completion = await self.model_chat_completion(payload)
        if not isinstance(completion, dict):
            raise ModuleTaskError(
                "invalid_model_response",
                "Model returned an invalid response",
                status_code=502,
            )
        return {
            "task_id": row["task_id"],
            "completion": completion,
        }

    async def capability_openai_chat_completion(
        self,
        token: str,
        request: Any,
    ) -> dict[str, Any]:
        if not isinstance(request, dict):
            raise ModuleTaskError(
                "invalid_model_request",
                "Model request must be an object",
            )
        allowed = {
            "model",
            "messages",
            "tools",
            "tool_choice",
            "response_format",
            "temperature",
            "top_p",
            "max_tokens",
            "max_completion_tokens",
            "parallel_tool_calls",
            "stream",
        }
        if set(request) - allowed or request.get("stream", False) is not False:
            raise ModuleTaskError(
                "invalid_model_request",
                "Model request fields are invalid",
            )
        if (
            "max_tokens" in request
            and "max_completion_tokens" in request
        ):
            raise ModuleTaskError(
                "invalid_model_request",
                "Only one model token limit may be supplied",
            )
        normalized = {
            key: value
            for key, value in request.items()
            if key
            not in {
                "model",
                "max_completion_tokens",
                "stream",
            }
        }
        normalized["profile"] = request.get("model")
        normalized["timeout_seconds"] = 900
        if "max_completion_tokens" in request:
            normalized["max_tokens"] = request["max_completion_tokens"]
        result = await self.capability_model_chat_completion(
            token,
            normalized,
        )
        completion = result["completion"]
        tool_calls = [
            {
                "id": item["id"],
                "type": "function",
                "function": {
                    "name": item["name"],
                    "arguments": item["arguments"],
                },
            }
            for item in completion.get("tool_calls", [])
        ]
        usage = completion.get("usage", {})
        return {
            "id": f"chatcmpl-{secrets.token_hex(12)}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": completion.get("model") or request.get("model"),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": completion.get("content"),
                        **(
                            {"tool_calls": tool_calls}
                            if tool_calls
                            else {}
                        ),
                    },
                    "finish_reason": completion.get("finish_reason")
                    or ("tool_calls" if tool_calls else "stop"),
                }
            ],
            "usage": {
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
        }

    async def prepare_openai_chat_completion_stream(
        self,
        token: str,
        request: Any,
    ) -> dict[str, Any]:
        if not isinstance(request, dict):
            raise ModuleTaskError(
                "invalid_model_request",
                "Model request must be an object",
            )
        allowed = {
            "model",
            "messages",
            "tools",
            "tool_choice",
            "response_format",
            "temperature",
            "top_p",
            "max_tokens",
            "max_completion_tokens",
            "parallel_tool_calls",
            "stream",
            "stream_options",
        }
        if set(request) - allowed or request.get("stream") is not True:
            raise ModuleTaskError(
                "invalid_model_request",
                "Model request fields are invalid",
            )
        if (
            "max_tokens" in request
            and "max_completion_tokens" in request
        ):
            raise ModuleTaskError(
                "invalid_model_request",
                "Only one model token limit may be supplied",
            )
        stream_options = request.get("stream_options")
        if stream_options is not None and (
            not isinstance(stream_options, dict)
            or set(stream_options) != {"include_usage"}
            or stream_options.get("include_usage") is not True
        ):
            raise ModuleTaskError(
                "invalid_model_request",
                "Model stream options are invalid",
            )
        normalized = {
            key: value
            for key, value in request.items()
            if key
            not in {
                "model",
                "max_completion_tokens",
                "stream",
                "stream_options",
            }
        }
        normalized["profile"] = request.get("model")
        normalized["timeout_seconds"] = 900
        if "max_completion_tokens" in request:
            normalized["max_tokens"] = request["max_completion_tokens"]

        await self._preflight_capability(
            token,
            "model.chat.completions",
        )
        row, scope = self._consume_capability(
            token,
            "model.chat.completions",
        )
        payload = self._validate_model_chat_request(
            normalized,
            scope.get("profiles", []),
        )
        if stream_options is not None:
            payload["stream_options"] = {"include_usage": True}
        return {
            "task_id": row["task_id"],
            "request": payload,
        }
