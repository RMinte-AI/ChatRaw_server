import asyncio
import copy
import hashlib
import importlib.util
import json
import logging
import os
import stat
import tempfile
import time
import unittest
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import aiohttp
from aiohttp import web
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from backend import main
from backend.module_task_protocol import (
    ModuleTaskProtocolError,
    validate_artifact_metadata,
    validate_task_event,
)
from backend.module_registry import ModuleTransportError
from backend.module_registry import ModuleAddressPolicy, ModuleHttpClient
from backend.module_tasks import ModuleTaskError, ModuleTaskService, TASKS_PATH


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = ROOT / "examples" / "reference-module"
REFERENCE_MANIFEST = json.loads(
    (REFERENCE_DIR / "manifest.example.json").read_text(encoding="utf-8")
)
ACTION = REFERENCE_MANIFEST["actions"][0]


class FakeTaskClient:
    def __init__(self):
        self.tasks = {}
        self.offline = False
        self.lose_after_accept = False
        self.reject_cancel = False
        self.reject_create = False
        self.calls = []

    @staticmethod
    def summary(task):
        payload = {
            key: copy.deepcopy(task[key])
            for key in (
                "task_id",
                "action_id",
                "action_version",
                "config_revision",
                "state",
                "last_event_id",
            )
        }
        if task.get("outcome_code"):
            payload["outcome_code"] = task["outcome_code"]
        if task["state"] == "succeeded":
            payload["result"] = copy.deepcopy(task["result"])
            if task["chat_projection"] is not None:
                payload["chat_projection"] = task["chat_projection"]
        if task.get("artifacts"):
            payload["artifacts"] = [
                {
                    key: artifact[key]
                    for key in (
                        "artifact_id",
                        "filename",
                        "media_type",
                        "size",
                        "expires_at",
                    )
                }
                for artifact in task["artifacts"].values()
            ]
        if task.get("resources"):
            payload["resources"] = []
            for resource in task["resources"].values():
                metadata = {
                    key: resource[key]
                    for key in (
                        "resource_id",
                        "filename",
                        "media_type",
                        "size",
                    )
                }
                if "expires_at" in resource:
                    metadata["expires_at"] = resource["expires_at"]
                payload["resources"].append(metadata)
        return payload

    async def request_json(
        self,
        _base_url,
        path,
        *,
        method="GET",
        token=None,
        payload=None,
        max_bytes=65536,
    ):
        del token, max_bytes
        self.calls.append((method, path, copy.deepcopy(payload)))
        if self.offline:
            raise ModuleTransportError(
                "module_unreachable",
                "Module is unreachable",
                status_code=502,
            )
        if path == TASKS_PATH and method == "POST":
            if self.reject_create:
                return 400, {"detail": "rejected"}
            task_id = payload["task_id"]
            existing = self.tasks.get(task_id)
            if existing:
                if existing["request_digest"] != payload["request_digest"]:
                    return 409, {"detail": "conflict"}
                existing["host_capabilities"] = payload["host_capabilities"]
            else:
                existing = {
                    "task_id": task_id,
                    "request_digest": payload["request_digest"],
                    "action_id": payload["action_id"],
                    "action_version": payload["action_version"],
                    "config_revision": payload["config_revision"],
                    "state": "queued",
                    "last_event_id": 0,
                    "result": None,
                    "chat_projection": None,
                    "artifacts": {},
                    "resources": {},
                    "events": [],
                    "host_capabilities": payload["host_capabilities"],
                    "active_skills": payload["active_skills"],
                    "active_rules": payload["active_rules"],
                }
                self.tasks[task_id] = existing
            if self.lose_after_accept:
                self.lose_after_accept = False
                raise ModuleTransportError(
                    "module_unreachable",
                    "Module is unreachable",
                    status_code=502,
                )
            return 202, self.summary(existing)
        parts = path.removeprefix(f"{TASKS_PATH}/").split("/")
        task = self.tasks.get(parts[0])
        if task is None:
            return 404, {"detail": "not found"}
        if len(parts) == 1 and method == "GET":
            return 200, self.summary(task)
        if parts[1:] == ["cancel"] and method == "POST":
            if self.reject_cancel:
                return 409, {"detail": "rejected"}
            if task["state"] not in {"succeeded", "failed", "cancelled"}:
                task["state"] = "cancel_requested"
            return 202, self.summary(task)
        if len(parts) == 3 and parts[1] == "approvals":
            approval = task.setdefault(
                "approval",
                {
                    "approval_id": parts[2],
                    "decision": None,
                    "expired": False,
                },
            )
            if (
                task["state"] in {"succeeded", "failed", "cancelled"}
                and approval["decision"] is None
            ):
                return 409, {"detail": "terminal"}
            if approval["expired"]:
                return 410, {"detail": "expired"}
            if (
                approval["decision"] is not None
                and approval["decision"] != payload["decision"]
            ):
                return 409, {"detail": "conflict"}
            approval["decision"] = payload["decision"]
            task["state"] = (
                "running" if payload["decision"] == "approve" else "failed"
            )
            if task["state"] == "failed":
                task["outcome_code"] = "approval_denied"
            return 200, self.summary(task)
        return 404, {"detail": "not found"}

    async def iter_sse(
        self,
        _base_url,
        path,
        *,
        token,
        last_event_id,
        max_event_bytes,
    ):
        del token, max_event_bytes
        if self.offline:
            raise ModuleTransportError(
                "module_unreachable",
                "Module is unreachable",
                status_code=502,
            )
        task_id = path.removeprefix(f"{TASKS_PATH}/").split("/")[0]
        task = self.tasks[task_id]
        yield None
        for event in task["events"]:
            if event["id"] > last_event_id:
                yield copy.deepcopy(event)

    async def request_bytes(
        self,
        _base_url,
        path,
        *,
        token,
        max_bytes,
    ):
        del token, max_bytes
        parts = path.removeprefix(f"{TASKS_PATH}/").split("/")
        artifact = self.tasks[parts[0]]["artifacts"][parts[2]]
        body = artifact["body"]
        return 200, {"content-type": artifact["media_type"]}, body

    @asynccontextmanager
    async def stream_bytes(
        self,
        _base_url,
        path,
        *,
        method,
        token,
        range_header=None,
    ):
        del token
        parts = path.removeprefix(f"{TASKS_PATH}/").split("/")
        resource = self.tasks[parts[0]]["resources"][parts[2]]
        body = resource["body"]
        status = 200
        selected = body
        headers = {
            "Content-Type": resource["media_type"],
            "Content-Length": str(len(body)),
            "Accept-Ranges": "bytes",
        }
        if range_header is not None:
            raw = range_header.removeprefix("bytes=")
            start_text, end_text = raw.split("-", 1)
            if start_text:
                start = int(start_text)
                end = int(end_text) if end_text else len(body) - 1
            else:
                suffix = int(end_text)
                start = max(0, len(body) - suffix)
                end = len(body) - 1
            if start >= len(body):
                status = 416
                selected = b""
                headers = {
                    "Content-Range": f"bytes */{len(body)}",
                    "Content-Length": "0",
                }
            else:
                status = 206
                end = min(end, len(body) - 1)
                selected = body[start : end + 1]
                headers["Content-Length"] = str(len(selected))
                headers["Content-Range"] = (
                    f"bytes {start}-{end}/{len(body)}"
                )

        class Content:
            async def iter_chunked(self, _size):
                if method != "HEAD" and selected:
                    yield selected

        yield SimpleNamespace(
            status=status,
            headers=headers,
            content=Content(),
        )

    def set_state(
        self,
        task_id,
        state,
        *,
        outcome_code=None,
        text="finished",
        artifact=False,
    ):
        task = self.tasks[task_id]
        task["state"] = state
        task["outcome_code"] = outcome_code
        task["last_event_id"] += 1
        task["events"].append(
            {
                "id": task["last_event_id"],
                "event": "task.terminal",
                "data": {
                    "state": state,
                    **(
                        {"outcome_code": outcome_code}
                        if outcome_code is not None
                        else {}
                    ),
                },
            }
        )
        if state == "succeeded":
            task["result"] = {"text": text}
            task["chat_projection"] = text
        if artifact:
            body = text.encode()
            artifact_id = "artifact-output"
            task["artifacts"][artifact_id] = {
                "artifact_id": artifact_id,
                "filename": "output.txt",
                "media_type": "text/plain",
                "size": len(body),
                "expires_at": "2099-01-01T00:00:00Z",
                "body": body,
            }

    def add_resource(
        self,
        task_id,
        body=b"resource body",
        *,
        expires_at="2099-01-01T00:00:00Z",
    ):
        resource_id = "resource-output"
        resource = {
            "resource_id": resource_id,
            "filename": "source.pdf",
            "media_type": "application/pdf",
            "size": len(body),
            "body": body,
        }
        if expires_at is not ...:
            resource["expires_at"] = expires_at
        self.tasks[task_id]["resources"][resource_id] = resource


class FakeRegistry:
    def __init__(self, client):
        self.client = client
        self.target = {
            "registration_id": "registration-reference",
            "module_id": REFERENCE_MANIFEST["module_id"],
            "module_version": REFERENCE_MANIFEST["module_version"],
            "protocol_version": REFERENCE_MANIFEST["protocol_version"],
            "base_url": "http://127.0.0.1:9999",
            "credential": "private-module-credential",
            "config_revision": "1",
            "manifest": copy.deepcopy(REFERENCE_MANIFEST),
            "granted_capabilities": [
                "chat.read",
                "principal.read",
                "resource.read",
                "resource.stream",
                "model.invoke",
                "model.invoke.v2",
                "model.chat.completions",
            ],
            "lifecycle_state": "enabled",
        }
        self.enabled = True

    def task_target(
        self,
        *,
        module_id=None,
        registration_id=None,
        require_enabled=True,
    ):
        if module_id is not None and module_id != self.target["module_id"]:
            raise ModuleTaskError("module_not_found", "not found", status_code=404)
        if (
            registration_id is not None
            and registration_id != self.target["registration_id"]
        ):
            raise ModuleTaskError("module_not_found", "not found", status_code=404)
        if require_enabled and not self.enabled:
            raise ModuleTaskError(
                "module_not_enabled",
                "Module is not accepting new tasks",
                status_code=409,
            )
        return copy.deepcopy(self.target)


class FakeUpload:
    def __init__(self, body, filename="input.pdf", media_type="application/pdf"):
        self.body = body
        self.filename = filename
        self.content_type = media_type
        self.offset = 0
        self.closed = False

    async def read(self, size):
        chunk = self.body[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk

    async def close(self):
        self.closed = True


class FakeModelStreamContent:
    def __init__(
        self,
        chunks,
        *,
        block_after_chunks=False,
        error_after_chunks=None,
    ):
        self.chunks = chunks
        self.block_after_chunks = block_after_chunks
        self.error_after_chunks = error_after_chunks
        self.cancelled = asyncio.Event()

    async def iter_any(self):
        try:
            for chunk in self.chunks:
                yield chunk
            if self.error_after_chunks is not None:
                raise self.error_after_chunks
            if self.block_after_chunks:
                await asyncio.Event().wait()
        finally:
            self.cancelled.set()


class FakeModelStreamResponse:
    def __init__(
        self,
        chunks,
        *,
        block_after_chunks=False,
        error_after_chunks=None,
    ):
        self.content = FakeModelStreamContent(
            chunks,
            block_after_chunks=block_after_chunks,
            error_after_chunks=error_after_chunks,
        )
        self.status = 200
        self.headers = {"Content-Type": "text/event-stream"}
        self.closed = False

    def close(self):
        self.closed = True


class ModuleTaskServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="chatraw-t4-service-")
        self.database = main.Database(str(Path(self.temp.name) / "chatraw.db"))
        self.creator = self._user("creator", "member")
        self.viewer = self._user("viewer", "member")
        self.admin = self._user("admin", "admin")
        self.chat = self.database.create_chat(
            "Task chat",
            owner_user_id=self.creator,
        )
        self.resource_id = self.database.save_document(
            "input.txt",
            "shared resource content",
            uploader_user_id=self.creator,
        )
        self.client = FakeTaskClient()
        self.registry = FakeRegistry(self.client)
        self.audits = []
        self.model_prompts = []
        self.structured_model_requests = []
        self.model_chat_requests = []

        async def invoke(prompt):
            self.model_prompts.append(prompt)
            return "model result"

        async def invoke_v2(prompt, output_schema):
            self.structured_model_requests.append(
                (prompt, copy.deepcopy(output_schema))
            )
            return {"status": "ok"}

        async def chat_completion(request):
            self.model_chat_requests.append(request)
            return {
                "profile": request["profile"],
                "model": "fixture-model",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-1",
                        "name": "clock_now",
                        "arguments": "{}",
                    }
                ],
                "finish_reason": "tool_calls",
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 4,
                    "total_tokens": 14,
                },
            }

        self.service = ModuleTaskService(
            self.database.db_path,
            busy_timeout_ms=self.database.busy_timeout_ms,
            registry=self.registry,
            audit=lambda *args: self.audits.append(args),
            model_invoke=invoke,
            model_invoke_v2=invoke_v2,
            model_chat_completion=chat_completion,
        )

    async def asyncTearDown(self):
        self.temp.cleanup()

    def _user(self, username, role):
        user_id = str(uuid.uuid4())
        now = "2026-07-23T00:00:00Z"
        with self.database.connection(write=True) as connection:
            connection.execute(
                """
                INSERT INTO users (
                    id, username, password_hash, role, enabled,
                    created_at, updated_at, password_changed_at
                ) VALUES (?, ?, 'hash', ?, 1, ?, ?, ?)
                """,
                (user_id, username, role, now, now, now),
            )
        return user_id

    def _payload(self, **overrides):
        payload = {
            "module_id": REFERENCE_MANIFEST["module_id"],
            "action_id": "echo.task",
            "input": {"text": "durable"},
            "chat_id": self.chat.id,
            "user_message": "Run durable task",
            "resource_ids": [self.resource_id],
        }
        payload.update(overrides)
        return payload

    async def _create(self, key="task-key", **overrides):
        return await self.service.create(
            payload=self._payload(**overrides),
            idempotency_key=key,
            principal_user_id=self.creator,
            principal_role="member",
        )

    def _chat_read_token(self, task_id):
        return next(
            item["token"]
            for item in self.client.tasks[task_id]["host_capabilities"]
            if item["capability"] == "chat.read"
        )

    async def _finish_task(
        self,
        task_id,
        state,
        *,
        outcome_code=None,
        text="finished",
    ):
        self.client.set_state(
            task_id,
            state,
            outcome_code=outcome_code,
            text=text,
        )
        return await self.service.get(
            task_id,
            principal_user_id=self.creator,
            principal_role="member",
        )

    def _personal_skill(self):
        skill_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        now = "2026-07-26T00:00:00Z"
        markdown = (
            "---\n"
            "name: personal-clock\n"
            "description: Personal clock workflow\n"
            "---\n"
            "Always use the time tool for current time."
        )
        digest = hashlib.sha256(
            ("SKILL.md\0" + markdown + "\0").encode()
        ).hexdigest()
        with self.database.connection(write=True) as connection:
            connection.execute(
                """
                INSERT INTO agent_skills (
                    id, owner_user_id, target_module_id, name,
                    description, license, enabled, active_version_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, 'personal-clock',
                          'Personal clock workflow', 'MIT', 1, ?,
                          ?, ?)
                """,
                (
                    skill_id,
                    self.creator,
                    REFERENCE_MANIFEST["module_id"],
                    version_id,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO agent_skill_versions (
                    id, skill_id, commit_sha, content_sha256,
                    source_json, skill_markdown, resources_json,
                    package_path, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, '[]', ?, ?)
                """,
                (
                    version_id,
                    skill_id,
                    "a" * 40,
                    digest,
                    '{"type":"github","commit":"'
                    + ("a" * 40)
                    + '"}',
                    markdown,
                    f"agent-personal/{self.creator}/{skill_id}/{version_id}",
                    now,
                ),
            )
        return skill_id, version_id, markdown, digest

    def _active_rule(
        self,
        *,
        scope="personal",
        owner_user_id=None,
        name="Pagination rule",
    ):
        document_id = str(uuid.uuid4())
        source_version_id = str(uuid.uuid4())
        compiled_version_id = str(uuid.uuid4())
        now = "2026-07-26T00:00:00Z"
        compiled = {
            "schema_version": "1.0",
            "title": "Pagination",
            "summary": "Fetch every page.",
            "execution_rules": [
                {
                    "id": "paginate",
                    "priority": 80,
                    "when": {"all": [], "any": [], "none": []},
                    "instructions": ["Fetch pages until empty."],
                    "tools": [],
                    "response_requirements": [],
                }
            ],
            "clarification_rules": [],
        }
        encoded = json.dumps(
            compiled,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with self.database.connection(write=True) as connection:
            connection.execute(
                """
                INSERT INTO agent_rule_documents (
                    id, owner_user_id, target_module_id, name,
                    scope,
                    current_source_version_id,
                    active_compiled_version_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    owner_user_id or self.creator,
                    REFERENCE_MANIFEST["module_id"],
                    name,
                    scope,
                    source_version_id,
                    compiled_version_id,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO agent_rule_source_versions (
                    id, document_id, version_number, source_document,
                    content_sha256, created_at
                ) VALUES (?, ?, 1, 'Fetch every page.', ?, ?)
                """,
                (
                    source_version_id,
                    document_id,
                    hashlib.sha256(b"Fetch every page.").hexdigest(),
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO agent_compiled_rule_versions (
                    id, document_id, source_version_id,
                    specification_version, status, content_sha256,
                    compiled_json, model_output, validation_errors_json,
                    created_at
                ) VALUES (?, ?, ?, 'chatraw-agent-rule-1.0',
                          'valid', ?, ?, ?, '[]', ?)
                """,
                (
                    compiled_version_id,
                    document_id,
                    source_version_id,
                    digest,
                    encoded,
                    encoded,
                    now,
                ),
            )
        return (
            document_id,
            source_version_id,
            compiled_version_id,
            compiled,
            digest,
        )

    async def test_personal_skill_is_scoped_pinned_and_read_by_capability(self):
        skill_id, version_id, markdown, digest = self._personal_skill()
        self.registry.target["manifest"]["actions"][0][
            "supports_skills"
        ] = True
        self.registry.target["granted_capabilities"].append("skill.read")

        task, created = await self._create(
            key="personal-skill",
            active_skill_ids=[skill_id],
        )

        self.assertTrue(created)
        remote = self.client.tasks[task["task_id"]]
        self.assertEqual(
            remote["active_skills"],
            [
                {
                    "skill_id": skill_id,
                    "version_id": version_id,
                    "name": "personal-clock",
                    "description": "Personal clock workflow",
                    "content_sha256": digest,
                    "commit": "a" * 40,
                }
            ],
        )
        capability = next(
            item
            for item in remote["host_capabilities"]
            if item["capability"] == "skill.read"
        )
        self.assertEqual(
            capability["scope"],
            {"skill_ids": [skill_id]},
        )
        snapshot = await self.service.capability_skill_read(
            capability["token"],
            skill_id,
        )
        self.assertEqual(snapshot["skill"]["version_id"], version_id)
        self.assertEqual(snapshot["skill"]["skill_markdown"], markdown)
        self.assertEqual(snapshot["skill"]["content_sha256"], digest)

        with self.assertRaises(ModuleTaskError) as denied:
            await self.service.capability_skill_read(
                capability["token"],
                str(uuid.uuid4()),
            )
        self.assertEqual(denied.exception.status_code, 403)

    async def test_active_rule_is_automatically_frozen_and_read_by_capability(
        self,
    ):
        (
            document_id,
            source_version_id,
            compiled_version_id,
            compiled,
            digest,
        ) = self._active_rule()
        self.registry.target["manifest"]["actions"][0][
            "supports_rules"
        ] = True
        self.registry.target["granted_capabilities"].append("rule.read")

        task, created = await self._create(key="active-rule")

        self.assertTrue(created)
        remote = self.client.tasks[task["task_id"]]
        self.assertEqual(
            remote["active_rules"],
            [
                {
                    "document_id": document_id,
                    "compiled_version_id": compiled_version_id,
                    "source_version_id": source_version_id,
                    "name": "Pagination rule",
                    "specification_version": "chatraw-agent-rule-1.0",
                    "content_sha256": digest,
                }
            ],
        )
        capability = next(
            item
            for item in remote["host_capabilities"]
            if item["capability"] == "rule.read"
        )
        self.assertEqual(
            capability["scope"],
            {"document_ids": [document_id]},
        )
        snapshot = await self.service.capability_rule_read(
            capability["token"],
            document_id,
        )
        self.assertEqual(
            snapshot["rule"]["compiled_version_id"],
            compiled_version_id,
        )
        self.assertEqual(snapshot["rule"]["compiled_rule"], compiled)
        self.assertEqual(snapshot["rule"]["scope"], "personal")

        with self.database.connection(write=True) as connection:
            connection.execute(
                """
                UPDATE agent_rule_documents
                SET active_compiled_version_id = NULL,
                    deleted_at = '2026-07-26T01:00:00Z'
                WHERE id = ?
                """,
                (document_id,),
            )
        frozen = await self.service.capability_rule_read(
            capability["token"],
            document_id,
        )
        self.assertEqual(
            frozen["rule"]["compiled_version_id"],
            compiled_version_id,
        )
        self.assertEqual(frozen["rule"]["scope"], "personal")

        self.client.set_state(task["task_id"], "succeeded")
        await self.service.get(
            task["task_id"],
            principal_user_id=self.creator,
            principal_role="member",
        )
        next_task, next_created = await self._create(
            key="after-rule-deactivation",
        )
        self.assertTrue(next_created)
        self.assertEqual(
            self.client.tasks[next_task["task_id"]]["active_rules"],
            [],
        )

    async def test_system_and_personal_rules_merge_without_public_scope_change(
        self,
    ):
        (
            system_document_id,
            _system_source_id,
            system_compiled_id,
            system_compiled,
            _system_digest,
        ) = self._active_rule(
            scope="system_default",
            owner_user_id=self.admin,
            name="System rule",
        )
        (
            personal_document_id,
            _personal_source_id,
            personal_compiled_id,
            personal_compiled,
            _personal_digest,
        ) = self._active_rule(name="Personal rule")
        self.registry.target["manifest"]["actions"][0][
            "supports_rules"
        ] = True
        self.registry.target["granted_capabilities"].append("rule.read")

        task, created = await self._create(key="merged-rules")

        self.assertTrue(created)
        remote = self.client.tasks[task["task_id"]]
        self.assertEqual(
            [
                item["document_id"]
                for item in remote["active_rules"]
            ],
            [system_document_id, personal_document_id],
        )
        self.assertTrue(
            all("scope" not in item for item in remote["active_rules"])
        )
        capability = next(
            item
            for item in remote["host_capabilities"]
            if item["capability"] == "rule.read"
        )
        system_snapshot = await self.service.capability_rule_read(
            capability["token"],
            system_document_id,
        )
        personal_snapshot = await self.service.capability_rule_read(
            capability["token"],
            personal_document_id,
        )
        self.assertEqual(
            system_snapshot["rule"]["compiled_version_id"],
            system_compiled_id,
        )
        self.assertEqual(
            system_snapshot["rule"]["compiled_rule"],
            system_compiled,
        )
        self.assertEqual(
            system_snapshot["rule"]["scope"],
            "system_default",
        )
        self.assertEqual(
            personal_snapshot["rule"]["compiled_version_id"],
            personal_compiled_id,
        )
        self.assertEqual(
            personal_snapshot["rule"]["compiled_rule"],
            personal_compiled,
        )
        self.assertEqual(personal_snapshot["rule"]["scope"], "personal")

        with self.database.connection(write=True) as connection:
            connection.execute(
                """
                UPDATE agent_rule_documents
                SET scope = 'personal'
                WHERE id = ?
                """,
                (system_document_id,),
            )
        still_frozen = await self.service.capability_rule_read(
            capability["token"],
            system_document_id,
        )
        self.assertEqual(
            still_frozen["rule"]["scope"],
            "system_default",
        )

    async def test_uploaded_resource_is_private_single_bind_and_streamed(self):
        upload = FakeUpload(b"%PDF-private")
        uploaded = await self.service.upload_input_resource(
            upload,
            creator_user_id=self.creator,
        )
        self.assertTrue(upload.closed)
        self.assertEqual(uploaded["size"], len(b"%PDF-private"))
        self.assertEqual(
            uploaded["sha256"],
            "9c747fd6ea592c2d09ae816761e81117b5fd7eff6a0eae7e30dde45bf9fb6fa9",
        )
        stored = next(self.service.resource_dir.iterdir())
        self.assertEqual(stat.S_IMODE(self.service.resource_dir.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(stored.stat().st_mode), 0o600)
        task, created = await self._create(
            key="uploaded-resource",
            chat_id=None,
            user_message=None,
            resource_ids=[uploaded["resource_id"]],
        )
        self.assertTrue(created)
        capabilities = {
            item["capability"]: item
            for item in self.client.tasks[task["task_id"]][
                "host_capabilities"
            ]
        }
        self.assertIn("resource.stream", capabilities)
        self.assertNotIn("resource.read", capabilities)
        streamed = await self.service.capability_resource_stream(
            capabilities["resource.stream"]["token"],
            uploaded["resource_id"],
        )
        self.assertEqual(streamed["path"].read_bytes(), b"%PDF-private")
        replay, replay_created = await self._create(
            key="uploaded-resource",
            chat_id=None,
            user_message=None,
            resource_ids=[uploaded["resource_id"]],
        )
        self.assertFalse(replay_created)
        self.assertEqual(replay["task_id"], task["task_id"])
        with self.assertRaises(ModuleTaskError) as reused:
            await self._create(
                key="uploaded-resource-reused",
                chat_id=None,
                user_message=None,
                resource_ids=[uploaded["resource_id"]],
            )
        self.assertEqual(reused.exception.code, "resource_already_bound")
        self.client.set_state(task["task_id"], "succeeded")
        await self.service.get(
            task["task_id"],
            principal_user_id=self.creator,
            principal_role="member",
        )
        with self.database.connection(write=True) as connection:
            scheduled = connection.execute(
                """
                SELECT expires_at, storage_name
                FROM module_task_input_resources
                WHERE resource_id = ?
                """,
                (uploaded["resource_id"],),
            ).fetchone()
            self.assertIsNotNone(scheduled["expires_at"])
            connection.execute(
                """
                UPDATE module_task_input_resources
                SET expires_at = '2000-01-01T00:00:00Z'
                WHERE resource_id = ?
                """,
                (uploaded["resource_id"],),
            )
        stored_path = self.service.resource_dir / scheduled["storage_name"]
        self.assertTrue(stored_path.exists())
        self.assertEqual(self.service.cleanup_input_resources(), 1)
        self.assertFalse(stored_path.exists())

        other_upload = await self.service.upload_input_resource(
            FakeUpload(b"other"),
            creator_user_id=self.creator,
        )
        with self.assertRaises(ModuleTaskError) as cross_user:
            await self.service.create(
                payload=self._payload(
                    chat_id=None,
                    user_message=None,
                    resource_ids=[other_upload["resource_id"]],
                ),
                idempotency_key="cross-user-resource",
                principal_user_id=self.viewer,
                principal_role="member",
            )
        self.assertEqual(cross_user.exception.code, "resource_access_forbidden")

    async def test_cleanup_keeps_tracking_row_when_file_removal_fails(self):
        uploaded = await self.service.upload_input_resource(
            FakeUpload(b"retry-cleanup"),
            creator_user_id=self.creator,
        )
        with self.database.connection(write=True) as connection:
            connection.execute(
                """
                UPDATE module_task_input_resources
                SET expires_at = '2000-01-01T00:00:00Z'
                WHERE resource_id = ?
                """,
                (uploaded["resource_id"],),
            )
        with patch.object(Path, "unlink", side_effect=OSError("denied")):
            with self.assertRaises(OSError):
                self.service.cleanup_input_resources()
        with self.database.connection() as connection:
            tracked = connection.execute(
                """
                SELECT 1 FROM module_task_input_resources
                WHERE resource_id = ?
                """,
                (uploaded["resource_id"],),
            ).fetchone()
        self.assertIsNotNone(tracked)
        self.assertEqual(self.service.cleanup_input_resources(), 1)

    async def test_uploaded_resource_requires_declared_action_support(self):
        uploaded = await self.service.upload_input_resource(
            FakeUpload(b"unsupported"),
            creator_user_id=self.creator,
        )
        self.registry.target["manifest"]["actions"][0][
            "supports_resources"
        ] = False
        with self.assertRaises(ModuleTaskError) as unsupported:
            await self._create(
                key="unsupported-upload",
                chat_id=None,
                user_message=None,
                resource_ids=[uploaded["resource_id"]],
            )
        self.assertEqual(
            unsupported.exception.code,
            "task_resources_not_supported",
        )

    async def test_one_task_can_bind_multiple_uploaded_resources(self):
        first = await self.service.upload_input_resource(
            FakeUpload(b"first"),
            creator_user_id=self.creator,
        )
        second = await self.service.upload_input_resource(
            FakeUpload(b"second"),
            creator_user_id=self.creator,
        )
        task, created = await self._create(
            key="multiple-uploaded-resources",
            chat_id=None,
            user_message=None,
            resource_ids=[first["resource_id"], second["resource_id"]],
        )
        self.assertTrue(created)
        capability = next(
            item
            for item in self.client.tasks[task["task_id"]][
                "host_capabilities"
            ]
            if item["capability"] == "resource.stream"
        )
        self.assertEqual(
            capability["scope"]["resource_ids"],
            sorted([first["resource_id"], second["resource_id"]]),
        )

    async def test_upload_limit_and_configuration_fail_explicitly(self):
        limited = ModuleTaskService(
            self.database.db_path,
            busy_timeout_ms=self.database.busy_timeout_ms,
            registry=self.registry,
            audit=lambda *_args: None,
            resource_dir=Path(self.temp.name) / "limited-resources",
            max_input_resource_bytes=4,
        )
        with self.assertRaises(ModuleTaskError) as oversized:
            await limited.upload_input_resource(
                FakeUpload(b"12345"),
                creator_user_id=self.creator,
            )
        self.assertEqual(oversized.exception.status_code, 413)
        self.assertEqual(
            list((Path(self.temp.name) / "limited-resources").iterdir()),
            [],
        )
        with patch.dict(
            os.environ,
            {"CHATRAW_MODULE_TASK_RESOURCE_MAX_BYTES": "not-an-integer"},
        ):
            with self.assertRaises(RuntimeError):
                ModuleTaskService(
                    self.database.db_path,
                    busy_timeout_ms=self.database.busy_timeout_ms,
                    registry=self.registry,
                    audit=lambda *_args: None,
                )

    async def test_retry_reactivates_provisional_input_resource(self):
        uploaded = await self.service.upload_input_resource(
            FakeUpload(b"retry"),
            creator_user_id=self.creator,
        )
        original_validate = self.service._validate_summary_for_row
        calls = 0

        def reject_first(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ModuleTaskError(
                    "invalid_module_task",
                    "invalid",
                    status_code=502,
                )
            return original_validate(*args, **kwargs)

        with patch.object(
            self.service,
            "_validate_summary_for_row",
            side_effect=reject_first,
        ):
            with self.assertRaises(ModuleTaskError):
                await self._create(
                    key="retry-upload",
                    chat_id=None,
                    user_message=None,
                    resource_ids=[uploaded["resource_id"]],
                )
            with self.database.connection() as connection:
                scheduled = connection.execute(
                    """
                    SELECT expires_at FROM module_task_input_resources
                    WHERE resource_id = ?
                    """,
                    (uploaded["resource_id"],),
                ).fetchone()
            self.assertIsNotNone(scheduled["expires_at"])
            task, created = await self._create(
                key="retry-upload",
                chat_id=None,
                user_message=None,
                resource_ids=[uploaded["resource_id"]],
            )
        self.assertTrue(created)
        with self.database.connection() as connection:
            active = connection.execute(
                """
                SELECT expires_at FROM module_task_input_resources
                WHERE bound_task_id = ?
                """,
                (task["task_id"],),
            ).fetchone()
        self.assertIsNone(active["expires_at"])

    async def test_resource_stream_preflights_terminal_task(self):
        uploaded = await self.service.upload_input_resource(
            FakeUpload(b"terminal"),
            creator_user_id=self.creator,
        )
        task, _ = await self._create(
            key="terminal-resource-stream",
            chat_id=None,
            user_message=None,
            resource_ids=[uploaded["resource_id"]],
        )
        capability = next(
            item
            for item in self.client.tasks[task["task_id"]][
                "host_capabilities"
            ]
            if item["capability"] == "resource.stream"
        )
        self.client.set_state(task["task_id"], "succeeded")
        with self.assertRaises(ModuleTaskError) as terminal:
            await self.service.capability_resource_stream(
                capability["token"],
                uploaded["resource_id"],
            )
        self.assertEqual(terminal.exception.status_code, 401)

    async def test_output_resource_is_opaque_scoped_and_ranged(self):
        task, _ = await self._create(
            key="output-resource",
            chat_id=None,
            user_message=None,
            resource_ids=[],
        )
        self.client.add_resource(
            task["task_id"],
            b"0123456789",
            expires_at=...,
        )
        self.client.set_state(task["task_id"], "succeeded")
        current = await self.service.get(
            task["task_id"],
            principal_user_id=self.creator,
            principal_role="member",
        )
        resource = current["resources"][0]
        self.assertNotEqual(resource["resource_ref"], "resource-output")
        self.assertIsNone(resource["expires_at"])
        with self.assertRaises(ModuleTaskError) as viewer:
            async with self.service.task_resource_stream(
                task["task_id"],
                resource["resource_ref"],
                principal_user_id=self.viewer,
                principal_role="member",
                method="GET",
                range_header=None,
            ):
                pass
        self.assertEqual(viewer.exception.status_code, 403)
        async with self.service.task_resource_stream(
            task["task_id"],
            resource["resource_ref"],
            principal_user_id=self.creator,
            principal_role="member",
            method="GET",
            range_header="bytes=2-5",
        ) as proxied:
            chunks = [
                chunk
                async for chunk in proxied["body"].iter_chunked(64 * 1024)
            ]
        self.assertEqual(proxied["status"], 206)
        self.assertEqual(b"".join(chunks), b"2345")
        self.assertEqual(proxied["headers"]["content-range"], "bytes 2-5/10")
        async with self.service.task_resource_stream(
            task["task_id"],
            resource["resource_ref"],
            principal_user_id=self.admin,
            principal_role="admin",
            method="HEAD",
            range_header=None,
        ) as head:
            self.assertEqual(head["status"], 200)

    async def test_output_resource_registration_is_atomic_with_terminal_state(self):
        task, _ = await self._create(
            key="atomic-output-resource",
            chat_id=None,
            user_message=None,
            resource_ids=[],
        )
        self.client.add_resource(task["task_id"], b"<html></html>")
        remote_resource = self.client.tasks[task["task_id"]]["resources"][
            "resource-output"
        ]
        remote_resource["media_type"] = "text/html"
        current = await self.service.get(
            task["task_id"],
            principal_user_id=self.creator,
            principal_role="member",
        )
        self.assertEqual(current["resources"][0]["media_type"], "text/html")
        remote_resource["filename"] = "changed.html"
        self.client.set_state(task["task_id"], "succeeded")
        await self.service.get(
            task["task_id"],
            principal_user_id=self.creator,
            principal_role="member",
        )
        with self.database.connection() as connection:
            stored = connection.execute(
                "SELECT state FROM module_tasks WHERE id = ?",
                (task["task_id"],),
            ).fetchone()
        self.assertEqual(stored["state"], "failed")

    async def test_response_loss_and_both_crash_windows_reuse_stable_task(self):
        self.client.lose_after_accept = True
        with self.assertRaises(ModuleTaskError) as lost:
            await self._create()
        self.assertEqual(lost.exception.code, "module_unreachable")
        with self.database.connection() as connection:
            provisional = connection.execute(
                "SELECT * FROM module_tasks"
            ).fetchone()
        self.assertEqual(provisional["state"], "submitting")
        self.assertFalse(provisional["visible"])
        stable_id = provisional["id"]
        self.assertIn(stable_id, self.client.tasks)
        self.assertTrue(self.service.has_active_chat_task(self.chat.id))
        self.assertTrue(
            self.service.has_active_resource_task(self.resource_id)
        )
        self.assertTrue(
            self.service.has_active_registration_tasks(
                self.registry.target["registration_id"]
            )
        )
        with self.assertRaises(ModuleTaskError) as concurrent:
            await self._create(key="parallel-while-outcome-uncertain")
        self.assertEqual(
            concurrent.exception.code,
            "chat_generation_conflict",
        )

        accepted, created = await self._create()
        self.assertTrue(created)
        self.assertEqual(accepted["task_id"], stable_id)
        replay, replay_created = await self._create()
        self.assertFalse(replay_created)
        self.assertEqual(replay["task_id"], stable_id)
        self.assertEqual(len(self.database.get_messages(self.chat.id)), 1)

        with self.assertRaises(ModuleTaskError) as conflict:
            await self._create(input={"text": "different"})
        self.assertEqual(conflict.exception.code, "idempotency_conflict")

        self.client.offline = True
        with self.assertRaises(ModuleTaskError):
            await self._create(
                key="before-module-accept",
                chat_id=None,
                user_message=None,
                resource_ids=[],
            )
        self.client.offline = False
        retried, _ = await self._create(
            key="before-module-accept",
            chat_id=None,
            user_message=None,
            resource_ids=[],
        )
        self.assertIn(retried["task_id"], self.client.tasks)

    async def test_task_creation_rechecks_chat_inside_write_transaction(self):
        validate_references = self.service._validate_local_references

        def validate_then_delete(**kwargs):
            result = validate_references(**kwargs)
            self.database.delete_chat(self.chat.id)
            return result

        with patch.object(
            self.service,
            "_validate_local_references",
            side_effect=validate_then_delete,
        ):
            with self.assertRaises(ModuleTaskError) as missing:
                await self._create(key="chat-deleted-before-task-write")

        self.assertEqual(missing.exception.code, "chat_not_found")
        with self.database.connection() as connection:
            task_count = connection.execute(
                "SELECT COUNT(*) FROM module_tasks"
            ).fetchone()[0]
        self.assertEqual(task_count, 0)

    async def test_definitive_module_rejection_creates_no_visible_task_or_message(self):
        self.client.reject_create = True
        with self.assertRaises(ModuleTaskError) as rejected:
            await self._create()
        self.assertEqual(rejected.exception.code, "module_task_rejected")
        with self.database.connection() as connection:
            task = connection.execute(
                "SELECT state, visible FROM module_tasks"
            ).fetchone()
            capability = connection.execute(
                "SELECT revoked_at FROM module_capability_tokens"
            ).fetchone()
        self.assertEqual(task["state"], "abandoned")
        self.assertFalse(task["visible"])
        self.assertIsNotNone(capability["revoked_at"])
        self.assertFalse(self.service.has_active_chat_task(self.chat.id))
        self.assertFalse(
            self.service.has_active_resource_task(self.resource_id)
        )
        self.assertEqual(self.database.get_messages(self.chat.id), [])

    async def test_task_list_filters_by_module_and_action(self):
        task, _created = await self._create(
            key="task-list-filters",
            chat_id=None,
            user_message=None,
            resource_ids=[],
        )
        matching = await self.service.list(
            principal_user_id=self.viewer,
            principal_role="member",
            module_id=REFERENCE_MANIFEST["module_id"],
            action_id="echo.task",
        )
        self.assertEqual(
            [item["task_id"] for item in matching],
            [task["task_id"]],
        )
        missing = await self.service.list(
            principal_user_id=self.viewer,
            principal_role="member",
            module_id="chatraw.missing",
        )
        self.assertEqual(missing, [])
        with self.assertRaises(ModuleTaskError) as invalid:
            await self.service.list(
                principal_user_id=self.viewer,
                principal_role="member",
                action_id="x" * 129,
            )
        self.assertEqual(invalid.exception.code, "invalid_task_filter")

    async def test_shared_read_but_only_creator_or_admin_controls(self):
        task, _ = await self._create()
        viewed = await self.service.get(
            task["task_id"],
            principal_user_id=self.viewer,
            principal_role="member",
        )
        self.assertFalse(viewed["can_control"])
        with self.assertRaises(ModuleTaskError) as denied:
            await self.service.cancel(
                task["task_id"],
                principal_user_id=self.viewer,
                principal_role="member",
            )
        self.assertEqual(denied.exception.status_code, 403)
        controlled = await self.service.cancel(
            task["task_id"],
            principal_user_id=self.admin,
            principal_role="admin",
        )
        self.assertEqual(controlled["state"], "cancel_requested")

    async def test_chat_and_resource_conflicts_and_delete_guards(self):
        task, _ = await self._create()
        with self.assertRaises(ModuleTaskError) as conflict:
            await self._create(key="second-chat-task")
        self.assertEqual(conflict.exception.status_code, 409)
        self.assertTrue(self.service.has_active_chat_task(self.chat.id))
        self.assertTrue(
            self.service.has_active_resource_task(self.resource_id)
        )
        self.client.set_state(task["task_id"], "succeeded")
        await self.service.get(
            task["task_id"],
            principal_user_id=self.creator,
            principal_role="member",
        )
        self.assertFalse(self.service.has_active_chat_task(self.chat.id))
        self.assertFalse(
            self.service.has_active_resource_task(self.resource_id)
        )

    async def test_terminal_projection_is_idempotent_and_failure_is_suppressed(self):
        self.database.update_chat_title(
            self.chat.id,
            main.DEFAULT_CHAT_TITLE,
        )
        title_calls = []

        async def auto_title(chat_id, user_message, assistant_message):
            title_calls.append((chat_id, user_message, assistant_message))
            return self.database.update_chat_title_if_default(
                chat_id,
                "Generated task title",
            )

        self.service.chat_auto_title = auto_title
        task, _ = await self._create()
        self.client.set_state(task["task_id"], "succeeded", text="projected")
        first = await self.service.get(
            task["task_id"],
            principal_user_id=self.viewer,
            principal_role="member",
        )
        second = await self.service.get(
            task["task_id"],
            principal_user_id=self.viewer,
            principal_role="member",
        )
        self.assertEqual(first["result"], {"text": "projected"})
        self.assertEqual(second["result"], {"text": "projected"})
        self.assertIsNotNone(first["user_message_id"])
        self.assertIsNotNone(first["assistant_message_id"])
        self.assertEqual(
            first["assistant_message_id"],
            second["assistant_message_id"],
        )
        messages = self.database.get_messages(self.chat.id)
        self.assertEqual([message.role for message in messages], ["user", "assistant"])
        self.assertEqual(messages[-1].content, "projected")
        self.assertEqual(
            title_calls,
            [(self.chat.id, "Run durable task", "projected")],
        )
        self.assertEqual(
            self.database.get_chats()[0].title,
            "Generated task title",
        )

        other_chat = self.database.create_chat("failure", self.creator)
        failed, _ = await self._create(
            key="failed-task",
            chat_id=other_chat.id,
            user_message="Fail safely",
            resource_ids=[],
        )
        self.client.set_state(
            failed["task_id"],
            "failed",
            outcome_code="outcome_unknown",
        )
        result = await self.service.get(
            failed["task_id"],
            principal_user_id=self.creator,
            principal_role="member",
        )
        self.assertEqual(result["outcome_code"], "outcome_unknown")
        self.assertEqual(len(self.database.get_messages(other_chat.id)), 1)

    async def test_terminal_sse_is_emitted_after_chat_projection(self):
        task, _ = await self._create()
        remote = self.client.tasks[task["task_id"]]
        remote["last_event_id"] += 1
        remote["events"].append(
            {
                "id": remote["last_event_id"],
                "event": "activity.updated",
                "data": {
                    "schema_version": "1",
                    "run_id": "11111111-1111-4111-8111-111111111111",
                    "activity_id": (
                        "22222222-2222-4222-8222-222222222222"
                    ),
                    "kind": "phase",
                    "state": "succeeded",
                    "title": "Prepared task context",
                    "detail": {"phase": "preparing"},
                },
            }
        )
        self.client.set_state(
            task["task_id"],
            "succeeded",
            text="projected before terminal",
        )
        observed = []
        async for event in self.service.stream_events(
            task["task_id"],
            last_event_id=0,
        ):
            if event is None:
                continue
            observed.append(event["event"])
            if event["event"] == "task.terminal":
                messages = self.database.get_messages(self.chat.id)
                self.assertEqual(
                    messages[-1].content,
                    "projected before terminal",
                )
        self.assertEqual(
            observed,
            ["activity.updated", "task.terminal"],
        )
        replay = [
            event
            async for event in self.service.stream_events(
                task["task_id"],
                last_event_id=0,
            )
            if event is not None
        ]
        self.assertEqual(
            [event["event"] for event in replay],
            ["activity.updated", "task.terminal"],
        )
        self.assertEqual(
            len(self.database.get_messages(self.chat.id)),
            2,
        )
        self.client.offline = True
        offline_replay = [
            event
            async for event in self.service.stream_events(
                task["task_id"],
                last_event_id=0,
            )
            if event is not None
        ]
        self.assertEqual(
            [event["event"] for event in offline_replay],
            ["task.terminal"],
        )
        self.assertEqual(offline_replay[0]["data"]["state"], "succeeded")
        self.assertEqual(
            len(self.database.get_messages(self.chat.id)),
            2,
        )

    async def test_tool_activity_call_id_keeps_task_and_tokens_active(self):
        task, _ = await self._create()
        remote = self.client.tasks[task["task_id"]]
        remote["state"] = "running"
        remote["last_event_id"] = 2
        remote["events"] = [
            {
                "id": 1,
                "event": "task.status",
                "data": {"state": "running"},
            },
            {
                "id": 2,
                "event": "activity.updated",
                "data": {
                    "schema_version": "1",
                    "run_id": "11111111-1111-4111-8111-111111111111",
                    "activity_id": (
                        "22222222-2222-4222-8222-222222222222"
                    ),
                    "kind": "tool",
                    "state": "started",
                    "title": "query_entry_transaction",
                    "detail": {
                        "tool_name": "query_entry_transaction",
                        "tool_call_id": "provider tool/call #1",
                        "arguments_preview": (
                            '{"page_number":1,"page_size":20}'
                        ),
                        "arguments_truncated": False,
                    },
                },
            },
        ]

        observed = [
            event
            async for event in self.service.stream_events(
                task["task_id"],
                last_event_id=0,
            )
            if event is not None
        ]

        self.assertEqual(
            [event["event"] for event in observed],
            ["task.status", "activity.updated"],
        )
        current = self.service._task_row(task["task_id"])
        self.assertEqual(current["state"], "running")
        self.assertEqual(current["status_sync"], "current")
        self.assertEqual(current["last_cursor"], 2)
        with self.service._connection() as connection:
            capability_rows = connection.execute(
                """
                SELECT revoked_at
                FROM module_capability_tokens
                WHERE task_id = ?
                """,
                (task["task_id"],),
            ).fetchall()
        self.assertTrue(capability_rows)
        self.assertTrue(
            all(row["revoked_at"] is None for row in capability_rows)
        )

    async def test_cancel_completion_race_allows_succeeded_terminal(self):
        task, _ = await self._create()
        first_cancel = await self.service.cancel(
            task["task_id"],
            principal_user_id=self.creator,
            principal_role="member",
        )
        repeated_cancel = await self.service.cancel(
            task["task_id"],
            principal_user_id=self.creator,
            principal_role="member",
        )
        self.assertEqual(first_cancel["state"], "cancel_requested")
        self.assertEqual(repeated_cancel["state"], "cancel_requested")
        self.client.set_state(task["task_id"], "succeeded", text="race won")
        result = await self.service.get(
            task["task_id"],
            principal_user_id=self.creator,
            principal_role="member",
        )
        self.assertEqual(result["state"], "succeeded")

        rejected_task, _ = await self._create(key="cancel-rejected")
        self.client.reject_cancel = True
        with self.assertRaises(ModuleTaskError) as rejected:
            await self.service.cancel(
                rejected_task["task_id"],
                principal_user_id=self.creator,
                principal_role="member",
            )
        self.assertEqual(rejected.exception.status_code, 409)
        self.assertEqual(
            self.service._task_row(rejected_task["task_id"])["state"],
            "queued",
        )

    async def test_approval_retry_conflict_expiry_and_terminal_guard(self):
        task, _ = await self._create()
        remote = self.client.tasks[task["task_id"]]
        remote["state"] = "waiting_approval"
        remote["approval"] = {
            "approval_id": "approval-1",
            "decision": None,
            "expired": False,
        }
        await self.service.get(
            task["task_id"],
            principal_user_id=self.creator,
            principal_role="member",
        )
        with self.assertRaises(ModuleTaskError) as unauthorized:
            await self.service.resolve_approval(
                task["task_id"],
                "approval-1",
                decision="approve",
                principal_user_id=self.viewer,
                principal_role="member",
            )
        self.assertEqual(unauthorized.exception.status_code, 403)
        approved = await self.service.resolve_approval(
            task["task_id"],
            "approval-1",
            decision="approve",
            principal_user_id=self.creator,
            principal_role="member",
        )
        self.assertEqual(approved["state"], "running")
        repeated = await self.service.resolve_approval(
            task["task_id"],
            "approval-1",
            decision="approve",
            principal_user_id=self.creator,
            principal_role="member",
        )
        self.assertEqual(repeated["state"], "running")
        with self.assertRaises(ModuleTaskError) as conflicting:
            await self.service.resolve_approval(
                task["task_id"],
                "approval-1",
                decision="deny",
                principal_user_id=self.creator,
                principal_role="member",
            )
        self.assertEqual(conflicting.exception.status_code, 409)

        remote["approval"] = {
            "approval_id": "approval-expired",
            "decision": None,
            "expired": True,
        }
        with self.assertRaises(ModuleTaskError) as expired:
            await self.service.resolve_approval(
                task["task_id"],
                "approval-expired",
                decision="approve",
                principal_user_id=self.creator,
                principal_role="member",
            )
        self.assertEqual(expired.exception.code, "approval_expired")
        self.client.set_state(task["task_id"], "cancelled")
        await self.service.get(
            task["task_id"],
            principal_user_id=self.creator,
            principal_role="member",
        )
        repeated_terminal = await self.service.resolve_approval(
            task["task_id"],
            "approval-1",
            decision="approve",
            principal_user_id=self.creator,
            principal_role="member",
        )
        self.assertEqual(repeated_terminal["state"], "cancelled")
        calls_before_terminal_approval = len(self.client.calls)
        with self.assertRaises(ModuleTaskError) as terminal:
            await self.service.resolve_approval(
                task["task_id"],
                "new-terminal-approval",
                decision="approve",
                principal_user_id=self.creator,
                principal_role="member",
            )
        self.assertEqual(terminal.exception.status_code, 409)
        self.assertEqual(len(self.client.calls), calls_before_terminal_approval)

    async def test_artifact_is_opaque_scoped_bounded_and_expiring(self):
        task, _ = await self._create()
        self.client.set_state(
            task["task_id"],
            "succeeded",
            text="artifact body",
            artifact=True,
        )
        current = await self.service.get(
            task["task_id"],
            principal_user_id=self.viewer,
            principal_role="member",
        )
        artifact = current["artifacts"][0]
        self.assertNotEqual(artifact["artifact_ref"], "artifact-output")
        downloaded = await self.service.artifact(
            task["task_id"],
            artifact["artifact_ref"],
        )
        self.assertEqual(downloaded["body"], b"artifact body")
        with self.database.connection(write=True) as connection:
            connection.execute(
                """
                UPDATE module_task_artifacts
                SET expires_at = '2000-01-01T00:00:00Z'
                WHERE artifact_ref = ?
                """,
                (artifact["artifact_ref"],),
            )
        with self.assertRaises(ModuleTaskError) as expired:
            await self.service.artifact(
                task["task_id"],
                artifact["artifact_ref"],
            )
        self.assertEqual(expired.exception.status_code, 410)

    async def test_capabilities_are_scoped_hashed_and_revoked_at_terminal(self):
        task, _ = await self._create()
        remote = self.client.tasks[task["task_id"]]
        capabilities = {
            item["capability"]: item
            for item in remote["host_capabilities"]
        }
        self.assertEqual(
            capabilities["chat.read"]["endpoint"],
            "http://127.0.0.1:51111/api/module-capabilities/v1/chat",
        )
        self.assertEqual(
            capabilities["resource.read"]["endpoint"],
            (
                "http://127.0.0.1:51111/api/module-capabilities/v1/"
                "resources/{resource_id}"
            ),
        )
        self.assertEqual(
            capabilities["model.invoke"]["endpoint"],
            (
                "http://127.0.0.1:51111/api/module-capabilities/v1/"
                "model/invoke"
            ),
        )
        self.assertEqual(
            capabilities["model.invoke.v2"]["endpoint"],
            (
                "http://127.0.0.1:51111/api/module-capabilities/v1/"
                "model/invoke-v2"
            ),
        )
        self.assertEqual(
            capabilities["model.invoke.v2"]["scope"],
            {
                "model_type": "chat",
                "structured_output": "json_schema",
            },
        )
        self.assertEqual(
            capabilities["principal.read"]["endpoint"],
            (
                "http://127.0.0.1:51111/api/module-capabilities/v1/"
                "principal"
            ),
        )
        self.assertEqual(
            capabilities["model.chat.completions"]["endpoint"],
            (
                "http://127.0.0.1:51111/api/module-capabilities/v1/"
                "openai"
            ),
        )
        self.assertTrue(
            capabilities["model.chat.completions"]["scope"][
                "supports_stream"
            ]
        )
        raw_tokens = [item["token"] for item in capabilities.values()]
        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT token_digest, capability, max_uses
                FROM module_capability_tokens WHERE task_id = ?
                """,
                (task["task_id"],),
            ).fetchall()
        stored = json.dumps([dict(row) for row in rows])
        for token in raw_tokens:
            self.assertNotIn(token, stored)
        model_capability = next(
            row
            for row in rows
            if row["capability"] == "model.chat.completions"
        )
        self.assertEqual(model_capability["max_uses"], 65)
        chat = await self.service.capability_chat_read(
            capabilities["chat.read"]["token"]
        )
        self.assertEqual(chat["chat_id"], self.chat.id)
        self.assertEqual(
            chat["conversation_ref"],
            f"chatraw-chat:{self.chat.id}",
        )
        self.assertEqual(
            chat["actor_ref"],
            f"chatraw-user:{self.creator}",
        )
        principal = await self.service.capability_principal_read(
            capabilities["principal.read"]["token"]
        )
        self.assertEqual(
            principal,
            {
                "task_id": task["task_id"],
                "actor_ref": f"chatraw-user:{self.creator}",
                "role": "member",
            },
        )
        resource = await self.service.capability_resource_read(
            capabilities["resource.read"]["token"],
            self.resource_id,
        )
        self.assertEqual(
            resource["resource"]["content"],
            "shared resource content",
        )
        with self.assertRaises(ModuleTaskError):
            await self.service.capability_resource_read(
                capabilities["resource.read"]["token"],
                "outside-scope",
            )
        model = await self.service.capability_model_invoke(
            capabilities["model.invoke"]["token"],
            "safe prompt",
        )
        self.assertEqual(model["content"], "model result")
        structured_schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["status"],
            "properties": {
                "status": {"type": "string", "enum": ["ok"]}
            },
        }
        structured = await self.service.capability_model_invoke_v2(
            capabilities["model.invoke.v2"]["token"],
            "safe structured prompt",
            structured_schema,
        )
        self.assertEqual(
            structured,
            {"task_id": task["task_id"], "output": {"status": "ok"}},
        )
        self.assertEqual(
            self.structured_model_requests,
            [("safe structured prompt", structured_schema)],
        )
        completion = (
            await self.service.capability_model_chat_completion(
                capabilities["model.chat.completions"]["token"],
                {
                    "profile": "agent-runtime",
                    "messages": [
                        {"role": "user", "content": "Use the clock"}
                    ],
                    "tools": [
                        {
                            "type": "function",
                            "function": {
                                "name": "clock_now",
                                "description": "Current time",
                                "parameters": {
                                    "type": "object",
                                    "properties": {},
                                },
                            },
                        }
                    ],
                    "timeout_seconds": 300,
                },
            )
        )
        self.assertEqual(
            completion["completion"]["tool_calls"][0]["name"],
            "clock_now",
        )
        openai = await self.service.capability_openai_chat_completion(
            capabilities["model.chat.completions"]["token"],
            {
                "model": "agent-runtime",
                "messages": [
                    {"role": "user", "content": "Use the clock"}
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "clock_now",
                            "parameters": {
                                "type": "object",
                                "properties": {},
                            },
                        },
                    }
                ],
                "max_completion_tokens": 256,
            },
        )
        self.assertEqual(openai["object"], "chat.completion")
        self.assertEqual(
            openai["choices"][0]["message"]["tool_calls"][0][
                "function"
            ]["name"],
            "clock_now",
        )
        self.assertEqual(
            self.model_chat_requests[0]["profile"],
            "agent-runtime",
        )
        self.assertEqual(
            self.model_chat_requests[1]["timeout_seconds"],
            900,
        )
        self.client.set_state(task["task_id"], "succeeded")
        with self.assertRaises(ModuleTaskError):
            await self.service.capability_chat_read(
                capabilities["chat.read"]["token"]
            )

    async def test_structured_model_rejects_unsafe_schema_and_bad_output(self):
        task, _ = await self._create(key="structured-negative")
        capability = next(
            item
            for item in self.client.tasks[task["task_id"]][
                "host_capabilities"
            ]
            if item["capability"] == "model.invoke.v2"
        )
        with self.assertRaises(ModuleTaskError) as reference_error:
            await self.service.capability_model_invoke_v2(
                capability["token"],
                "unsafe schema",
                {
                    "type": "object",
                    "additionalProperties": False,
                    "$ref": "https://example.invalid/schema.json",
                },
            )
        self.assertEqual(
            reference_error.exception.code,
            "invalid_model_request",
        )
        with self.assertRaises(ModuleTaskError) as non_json_schema_error:
            await self.service.capability_model_invoke_v2(
                capability["token"],
                "non-standard schema number",
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "value": {
                            "type": "number",
                            "enum": [float("nan")],
                        }
                    },
                },
            )
        self.assertEqual(
            non_json_schema_error.exception.code,
            "invalid_model_request",
        )
        with self.assertRaises(ModuleTaskError) as output_error:
            await self.service.capability_model_invoke_v2(
                capability["token"],
                "schema mismatch",
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["count"],
                    "properties": {"count": {"type": "integer"}},
                },
            )
        self.assertEqual(
            output_error.exception.code,
            "model_response_schema_invalid",
        )

        async def non_json_number(_prompt, _schema):
            return {"count": float("nan")}

        self.service.model_invoke_v2 = non_json_number
        with self.assertRaises(ModuleTaskError) as json_error:
            await self.service.capability_model_invoke_v2(
                capability["token"],
                "non-standard JSON number",
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["count"],
                    "properties": {"count": {"type": "number"}},
                },
            )
        self.assertEqual(
            json_error.exception.code,
            "model_response_invalid",
        )

    async def test_stream_preparation_consumes_capability_once(self):
        task, _ = await self._create()
        capability = next(
            item
            for item in self.client.tasks[task["task_id"]][
                "host_capabilities"
            ]
            if item["capability"] == "model.chat.completions"
        )
        prepared = (
            await self.service.prepare_openai_chat_completion_stream(
                capability["token"],
                {
                    "model": "agent-runtime",
                    "messages": [
                        {"role": "user", "content": "stream safely"}
                    ],
                    "stream": True,
                    "stream_options": {"include_usage": True},
                },
            )
        )
        self.assertEqual(prepared["task_id"], task["task_id"])
        self.assertEqual(
            prepared["request"]["profile"],
            "agent-runtime",
        )
        self.assertEqual(prepared["request"]["timeout_seconds"], 900)
        self.assertEqual(
            prepared["request"]["stream_options"],
            {"include_usage": True},
        )
        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT use_count
                FROM module_capability_tokens
                WHERE task_id = ?
                  AND capability = 'model.chat.completions'
                """,
                (task["task_id"],),
            ).fetchone()
        self.assertEqual(row["use_count"], 1)

        with self.assertRaises(ModuleTaskError) as private_extension:
            await self.service.prepare_openai_chat_completion_stream(
                capability["token"],
                {
                    "model": "agent-runtime",
                    "messages": [
                        {"role": "user", "content": "stream safely"}
                    ],
                    "stream": True,
                    "stream_options": {
                        "include_usage": True,
                        "continuous_usage_stats": True,
                    },
                },
            )
        self.assertEqual(
            private_extension.exception.code,
            "invalid_model_request",
        )

    async def test_capability_ttl_uses_action_deadline_default(self):
        input_schema = self.registry.target["manifest"]["actions"][0][
            "input_schema"
        ]
        input_schema["properties"]["request_deadline_seconds"] = {
            "type": "integer",
            "minimum": 180,
            "maximum": 7200,
            "default": 1800,
        }

        task, _ = await self._create()

        with self.database.connection() as connection:
            capability = connection.execute(
                """
                SELECT created_at, expires_at
                FROM module_capability_tokens
                WHERE task_id = ? AND capability = 'chat.read'
                """,
                (task["task_id"],),
            ).fetchone()
        lifetime = (
            datetime.fromisoformat(
                capability["expires_at"].replace("Z", "+00:00")
            )
            - datetime.fromisoformat(
                capability["created_at"].replace("Z", "+00:00")
            )
        ).total_seconds()
        self.assertGreaterEqual(lifetime, 1859)

    async def test_agent_office_artifact_types_are_allowed(self):
        task, _ = await self._create()
        media_types = [
            (
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            "text/markdown",
        ]

        self.service._register_artifacts(
            task["task_id"],
            [
                {
                    "artifact_id": f"artifact-office-{index}",
                    "filename": filename,
                    "media_type": media_type,
                    "size": 1,
                    "expires_at": None,
                }
                for index, (filename, media_type) in enumerate(
                    zip(
                        ["report.xlsx", "report.docx", "report.md"],
                        media_types,
                    )
                )
            ],
        )

        with self.database.connection() as connection:
            stored = connection.execute(
                """
                SELECT media_type
                FROM module_task_artifacts
                WHERE task_id = ?
                ORDER BY artifact_id
                """,
                (task["task_id"],),
            ).fetchall()
        self.assertEqual(
            {row["media_type"] for row in stored},
            set(media_types),
        )

    async def test_chat_capability_returns_only_bounded_recent_history(self):
        now = "2026-07-26T00:00:00Z"
        with self.database.connection(write=True) as connection:
            connection.executemany(
                """
                INSERT INTO messages (
                    id, chat_id, role, content, created_at,
                    author_user_id, sequence
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        str(uuid.uuid4()),
                        self.chat.id,
                        "user" if index % 2 == 0 else "assistant",
                        f"history-{index}",
                        now,
                        self.creator if index % 2 == 0 else None,
                        index + 1,
                    )
                    for index in range(50)
                ],
            )
        task, _ = await self._create()
        token = next(
            item["token"]
            for item in self.client.tasks[task["task_id"]][
                "host_capabilities"
            ]
            if item["capability"] == "chat.read"
        )

        chat = await self.service.capability_chat_read(token)

        self.assertEqual(len(chat["messages"]), 40)
        self.assertEqual(chat["messages"][0]["content"], "history-11")
        self.assertEqual(
            chat["messages"][-1]["content"],
            "Run durable task",
        )
        context = chat["conversation_context"]
        self.assertEqual(context["schema_version"], "1")
        flattened = [
            message["content"]
            for turn in context["turns"]
            for message in (turn["user"], turn["assistant"])
            if message is not None
        ]
        self.assertEqual(len(flattened), 40)
        self.assertEqual(flattened[0], "history-10")
        self.assertEqual(flattened[-1], "history-49")
        self.assertTrue(
            all(turn["status"] == "complete" for turn in context["turns"])
        )
        self.assertEqual(
            context["current_task"],
            {
                "task_id": task["task_id"],
                "module_id": REFERENCE_MANIFEST["module_id"],
                "action_id": "echo.task",
                "state": "queued",
            },
        )

    async def test_chat_capability_bounds_history_characters(self):
        now = "2026-07-26T00:00:00Z"
        with self.database.connection(write=True) as connection:
            connection.executemany(
                """
                INSERT INTO messages (
                    id, chat_id, role, content, created_at,
                    author_user_id, sequence
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        str(uuid.uuid4()),
                        self.chat.id,
                        "user" if index % 2 == 0 else "assistant",
                        str(index) + ("x" * 100_000),
                        now,
                        self.creator if index % 2 == 0 else None,
                        index + 1,
                    )
                    for index in range(3)
                ],
            )
        task, _ = await self._create()
        token = next(
            item["token"]
            for item in self.client.tasks[task["task_id"]][
                "host_capabilities"
            ]
            if item["capability"] == "chat.read"
        )

        chat = await self.service.capability_chat_read(token)

        self.assertLessEqual(
            sum(len(item["content"]) for item in chat["messages"]),
            200_000,
        )
        self.assertEqual(
            chat["messages"][-1]["content"],
            "Run durable task",
        )
        context = chat["conversation_context"]
        context_characters = sum(
            len(message["content"])
            for turn in context["turns"]
            for message in (turn["user"], turn["assistant"])
            if message is not None
        )
        self.assertLessEqual(context_characters, 200_000)
        self.assertFalse(
            any(
                turn["status"] == "complete"
                and (
                    turn["user"] is None
                    or turn["assistant"] is None
                )
                for turn in context["turns"]
            )
        )

    async def test_chat_capability_returns_structured_task_and_chat_turns(self):
        self.database.add_message(
            self.chat.id,
            "user",
            "ordinary question",
            author_user_id=self.creator,
        )
        self.database.add_message(
            self.chat.id,
            "assistant",
            "ordinary answer",
        )

        succeeded, _ = await self._create(
            key="history-succeeded",
            input={"text": "successful input"},
            user_message="successful request",
        )
        await self._finish_task(
            succeeded["task_id"],
            "succeeded",
            text="successful answer",
        )

        failed, _ = await self._create(
            key="history-failed",
            input={"text": "failed input"},
            user_message="failed request",
        )
        await self._finish_task(
            failed["task_id"],
            "failed",
            outcome_code="agent_execution_failed",
        )

        cancelled, _ = await self._create(
            key="history-cancelled",
            input={"text": "cancelled input"},
            user_message="cancelled request",
        )
        await self._finish_task(
            cancelled["task_id"],
            "cancelled",
            outcome_code="user_cancelled",
        )

        no_projection, _ = await self._create(
            key="history-no-projection",
            input={"text": "no projection input"},
            user_message="no projection request",
        )
        remote = self.client.tasks[no_projection["task_id"]]
        remote["state"] = "succeeded"
        remote["last_event_id"] += 1
        remote["result"] = {"text": "not projected"}
        remote["chat_projection"] = None
        remote["events"].append(
            {
                "id": remote["last_event_id"],
                "event": "task.terminal",
                "data": {"state": "succeeded"},
            }
        )
        await self.service.get(
            no_projection["task_id"],
            principal_user_id=self.creator,
            principal_role="member",
        )
        self.database.add_message(
            self.chat.id,
            "assistant",
            "orphan assistant",
        )
        self.database.add_message(
            self.chat.id,
            "user",
            "orphan user",
            author_user_id=self.creator,
        )

        current, _ = await self._create(
            key="history-current",
            input={"text": "authoritative current input"},
            user_message="visible current message",
        )
        chat = await self.service.capability_chat_read(
            self._chat_read_token(current["task_id"])
        )

        self.assertEqual(
            [message["content"] for message in chat["messages"]],
            [
                "ordinary question",
                "ordinary answer",
                "successful request",
                "successful answer",
                "failed request",
                "cancelled request",
                "no projection request",
                "orphan assistant",
                "orphan user",
                "visible current message",
            ],
        )
        self.assertEqual(
            chat["conversation_context"],
            {
                "schema_version": "1",
                "turns": [
                    {
                        "source": "chat",
                        "status": "complete",
                        "task": None,
                        "user": {"content": "ordinary question"},
                        "assistant": {"content": "ordinary answer"},
                    },
                    {
                        "source": "module",
                        "status": "complete",
                        "task": {
                            "task_id": succeeded["task_id"],
                            "module_id": REFERENCE_MANIFEST["module_id"],
                            "action_id": "echo.task",
                            "state": "succeeded",
                            "outcome_code": None,
                        },
                        "user": {"content": "successful request"},
                        "assistant": {"content": "successful answer"},
                    },
                    {
                        "source": "module",
                        "status": "failed",
                        "task": {
                            "task_id": failed["task_id"],
                            "module_id": REFERENCE_MANIFEST["module_id"],
                            "action_id": "echo.task",
                            "state": "failed",
                            "outcome_code": "agent_execution_failed",
                        },
                        "user": {"content": "failed request"},
                        "assistant": None,
                    },
                    {
                        "source": "module",
                        "status": "cancelled",
                        "task": {
                            "task_id": cancelled["task_id"],
                            "module_id": REFERENCE_MANIFEST["module_id"],
                            "action_id": "echo.task",
                            "state": "cancelled",
                            "outcome_code": "user_cancelled",
                        },
                        "user": {"content": "cancelled request"},
                        "assistant": None,
                    },
                    {
                        "source": "module",
                        "status": "incomplete",
                        "task": {
                            "task_id": no_projection["task_id"],
                            "module_id": REFERENCE_MANIFEST["module_id"],
                            "action_id": "echo.task",
                            "state": "succeeded",
                            "outcome_code": None,
                        },
                        "user": {"content": "no projection request"},
                        "assistant": None,
                    },
                    {
                        "source": "chat",
                        "status": "incomplete",
                        "task": None,
                        "user": None,
                        "assistant": {"content": "orphan assistant"},
                    },
                    {
                        "source": "chat",
                        "status": "incomplete",
                        "task": None,
                        "user": {"content": "orphan user"},
                        "assistant": None,
                    },
                ],
                "current_task": {
                    "task_id": current["task_id"],
                    "module_id": REFERENCE_MANIFEST["module_id"],
                    "action_id": "echo.task",
                    "state": "queued",
                },
            },
        )

    async def test_chat_capability_context_is_scoped_to_its_chat(self):
        foreign_chat = self.database.create_chat(
            "Foreign chat",
            owner_user_id=self.viewer,
        )
        self.database.add_message(
            foreign_chat.id,
            "user",
            "foreign private question",
            author_user_id=self.viewer,
        )
        self.database.add_message(
            foreign_chat.id,
            "assistant",
            "foreign private answer",
        )
        self.database.add_message(
            self.chat.id,
            "user",
            "local question",
            author_user_id=self.creator,
        )
        self.database.add_message(
            self.chat.id,
            "assistant",
            "local answer",
        )
        current, _ = await self._create(key="history-chat-scope")

        chat = await self.service.capability_chat_read(
            self._chat_read_token(current["task_id"])
        )

        self.assertEqual(
            chat["conversation_context"]["turns"],
            [
                {
                    "source": "chat",
                    "status": "complete",
                    "task": None,
                    "user": {"content": "local question"},
                    "assistant": {"content": "local answer"},
                }
            ],
        )
        serialized = json.dumps(chat, ensure_ascii=False)
        self.assertNotIn("foreign private question", serialized)
        self.assertNotIn("foreign private answer", serialized)

    async def test_unapproved_and_expired_capabilities_cannot_read_data(self):
        self.registry.target["granted_capabilities"] = []
        task, _ = await self._create()
        self.assertEqual(
            self.client.tasks[task["task_id"]]["host_capabilities"],
            [],
        )
        with self.assertRaises(ModuleTaskError):
            await self.service.capability_chat_read("unapproved-token")

        self.registry.target["granted_capabilities"] = ["model.invoke"]
        other, _ = await self._create(
            key="expiring-token-task",
            chat_id=None,
            user_message=None,
            resource_ids=[],
        )
        model_token = next(
            item["token"]
            for item in self.client.tasks[other["task_id"]][
                "host_capabilities"
            ]
            if item["capability"] == "model.invoke"
        )
        with self.database.connection(write=True) as connection:
            connection.execute(
                """
                UPDATE module_capability_tokens
                SET expires_at = '2000-01-01T00:00:00Z'
                WHERE task_id = ?
                """,
                (other["task_id"],),
            )
        with self.assertRaises(ModuleTaskError):
            await self.service.capability_model_invoke(
                model_token,
                "expired",
            )

    async def test_model_chat_timeout_has_180_second_floor(self):
        task, _ = await self._create(key="model-timeout-floor")
        token = next(
            item["token"]
            for item in self.client.tasks[task["task_id"]][
                "host_capabilities"
            ]
            if item["capability"] == "model.chat.completions"
        )
        with self.assertRaises(ModuleTaskError) as invalid:
            await self.service.capability_model_chat_completion(
                token,
                {
                    "profile": "agent-runtime",
                    "messages": [{"role": "user", "content": "hello"}],
                    "timeout_seconds": 179,
                },
            )
        self.assertEqual(
            invalid.exception.code,
            "invalid_model_timeout",
        )

    async def test_offline_becomes_durable_failure_and_draining_rejects_new(self):
        task, _ = await self._create()
        self.client.offline = True
        current = await self.service.get(
            task["task_id"],
            principal_user_id=self.viewer,
            principal_role="member",
        )
        self.assertEqual(current["state"], "failed")
        self.assertEqual(current["status_sync"], "unreachable")
        self.assertEqual(current["outcome_code"], "module_unreachable")
        self.client.offline = False
        recovered = await self.service.get(
            task["task_id"],
            principal_user_id=self.viewer,
            principal_role="member",
        )
        self.assertEqual(recovered["state"], "failed")
        self.assertEqual(recovered["outcome_code"], "module_unreachable")
        self.registry.enabled = False
        with self.assertRaises(ModuleTaskError) as draining:
            await self._create(key="draining")
        self.assertEqual(draining.exception.status_code, 409)

    async def test_stream_transport_failure_emits_and_replays_terminal(self):
        task, _ = await self._create()
        self.client.offline = True
        events = [
            event
            async for event in self.service.stream_events(
                task["task_id"],
                last_event_id=0,
            )
        ]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "task.terminal")
        self.assertEqual(events[0]["data"]["state"], "failed")
        self.assertEqual(
            events[0]["data"]["outcome_code"],
            "module_unreachable",
        )
        replay = [
            event
            async for event in self.service.stream_events(
                task["task_id"],
                last_event_id=0,
            )
        ]
        self.assertEqual(replay, events)
        exhausted = [
            event
            async for event in self.service.stream_events(
                task["task_id"],
                last_event_id=events[0]["id"],
            )
        ]
        self.assertEqual(exhausted, [])

    async def test_stream_failure_is_idempotent_after_concurrent_terminal(self):
        task, _ = await self._create()
        with self.database.connection(write=True) as connection:
            connection.execute(
                """
                UPDATE module_tasks
                SET state = 'failed', outcome_code = 'approval_denied',
                    last_cursor = 4, terminal_at = updated_at
                WHERE id = ?
                """,
                (task["task_id"],),
            )

        event = self.service._fail_stream(
            task["task_id"],
            outcome_code="module_unreachable",
        )

        self.assertEqual(event["id"], 4)
        self.assertEqual(event["data"]["state"], "failed")
        self.assertEqual(
            event["data"]["outcome_code"],
            "approval_denied",
        )

    async def test_running_task_uses_frozen_action_and_config_after_upgrade(self):
        task, _ = await self._create()
        self.registry.target["module_version"] = "1.1.0"
        self.registry.target["config_revision"] = "2"
        self.registry.target["manifest"]["actions"][0]["action_version"] = "2.0.0"
        self.client.set_state(task["task_id"], "succeeded", text="old contract")
        recovered = await self.service.get(
            task["task_id"],
            principal_user_id=self.creator,
            principal_role="member",
        )
        self.assertEqual(recovered["module_version"], "1.0.0")
        self.assertEqual(recovered["action_version"], "1.0.0")
        self.assertEqual(recovered["config_revision"], "1")
        self.assertEqual(recovered["result"], {"text": "old contract"})

    async def test_force_disconnect_and_user_disable_revoke_capabilities(self):
        task, _ = await self._create()
        capabilities = self.client.tasks[task["task_id"]]["host_capabilities"]
        token = next(
            item["token"]
            for item in capabilities
            if item["capability"] == "chat.read"
        )
        self.service.force_disconnect(self.registry.target["registration_id"])
        current = self.service._task_row(task["task_id"])
        self.assertEqual(current["status_sync"], "unreachable")
        with self.assertRaises(ModuleTaskError):
            await self.service.capability_chat_read(token)


class ModuleTaskMachineContractTests(unittest.TestCase):
    def test_task_machine_contract_is_valid_and_covers_frozen_events(self):
        contract = json.loads(
            (
                ROOT
                / "backend"
                / "contracts"
                / "module-task-v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(contract)
        self.assertEqual(
            {
                contract["$defs"][name]["properties"]["event"]["const"]
                for name in (
                    "statusEvent",
                    "progressEvent",
                    "outputDeltaEvent",
                    "outputSnapshotEvent",
                    "approvalRequestedEvent",
                    "approvalResolvedEvent",
                    "activityPhaseEvent",
                    "activityPlanEvent",
                    "activityToolEvent",
                    "artifactEvent",
                    "terminalEvent",
                )
            },
            {
                "task.status",
                "task.progress",
                "output.delta",
                "output.snapshot",
                "approval.requested",
                "approval.resolved",
                "activity.updated",
                "artifact.added",
                "task.terminal",
            },
        )
        validate_task_event(
            {
                "id": 1,
                "event": "activity.updated",
                "data": {
                    "schema_version": "1",
                    "run_id": "11111111-1111-4111-8111-111111111111",
                    "activity_id": (
                        "22222222-2222-4222-8222-222222222222"
                    ),
                    "kind": "tool",
                    "state": "succeeded",
                    "title": "Query page 1",
                    "summary": "Returned 20 rows",
                    "detail": {
                        "tool_name": "station_records",
                        "tool_call_id": "provider tool/call #1",
                        "arguments_preview": '{"page":1,"size":20}',
                        "arguments_truncated": False,
                        "result_preview": '{"row_count":20}',
                        "result_truncated": False,
                        "duration_ms": 1830,
                    },
                },
            },
            previous_event_id=0,
        )
        invalid_tool_call_id = {
            "id": 2,
            "event": "activity.updated",
            "data": {
                "schema_version": "1",
                "run_id": "11111111-1111-4111-8111-111111111111",
                "activity_id": "33333333-3333-4333-8333-333333333333",
                "kind": "tool",
                "state": "started",
                "title": "Query page 2",
                "detail": {
                    "tool_name": "station_records",
                    "tool_call_id": "x" * 513,
                    "arguments_preview": '{"page":2,"size":20}',
                    "arguments_truncated": False,
                },
            },
        }
        with self.assertRaises(ModuleTaskProtocolError):
            validate_task_event(
                invalid_tool_call_id,
                previous_event_id=1,
            )
        invalid_activity = {
            "id": 3,
            "event": "activity.updated",
            "data": {
                "schema_version": "1",
                "run_id": "11111111-1111-4111-8111-111111111111",
                "activity_id": "33333333-3333-4333-8333-333333333333",
                "kind": "tool",
                "state": "failed",
                "title": "Query page 2",
                "detail": {
                    "tool_name": "station_records",
                    "arguments_preview": '{"page":2,"size":20}',
                    "arguments_truncated": False,
                    "duration_ms": 20,
                },
            },
        }
        with self.assertRaises(ModuleTaskProtocolError):
            validate_task_event(
                invalid_activity,
                previous_event_id=2,
            )
        with self.assertRaises(ModuleTaskProtocolError):
            validate_task_event(
                {
                    "id": 1,
                    "event": "artifact.added",
                    "data": {
                        "artifact_id": "artifact-1",
                        "filename": "result.txt",
                        "media_type": "text/plain",
                        "size": 1,
                        "expires_at": None,
                        "direct_url": "http://module.internal/result.txt",
                    },
                },
                previous_event_id=0,
            )
        with self.assertRaises(ModuleTaskProtocolError):
            validate_artifact_metadata(
                {
                    "artifact_id": "artifact-1",
                    "filename": "result.txt\r\nX-Injected: true",
                    "media_type": "text/plain",
                    "size": 1,
                    "expires_at": None,
                }
            )


class ModuleArtifactTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        application = web.Application()

        async def redirect(_request):
            raise web.HTTPFound("/artifact")

        async def oversized(_request):
            return web.Response(
                body=b"x" * 33,
                content_type="text/plain",
            )

        async def resource(request):
            body = b"0123456789"
            if request.headers.get("Range") == "bytes=2-5":
                return web.Response(
                    status=206,
                    body=b"" if request.method == "HEAD" else body[2:6],
                    headers={
                        "Content-Length": "4",
                        "Content-Range": "bytes 2-5/10",
                        "Content-Type": "application/pdf",
                    },
                )
            return web.Response(
                body=b"" if request.method == "HEAD" else body,
                headers={
                    "Content-Length": str(len(body)),
                    "Content-Type": "application/pdf",
                },
            )

        async def slow_resource(_request):
            await asyncio.sleep(0.1)
            return web.Response(
                body=b"slow",
                headers={
                    "Content-Length": "4",
                    "Content-Type": "application/pdf",
                },
            )

        application.router.add_get("/redirect", redirect)
        application.router.add_get("/artifact", oversized)
        application.router.add_route("*", "/resource", resource)
        application.router.add_get("/slow-resource", slow_resource)
        self.runner = web.AppRunner(application)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await self.site.start()
        port = self.site._server.sockets[0].getsockname()[1]
        self.origin = f"http://127.0.0.1:{port}"
        self.client = ModuleHttpClient(
            ModuleAddressPolicy(),
            timeout_seconds=2,
        )

    async def asyncTearDown(self):
        await self.runner.cleanup()

    async def test_artifact_redirect_and_oversize_are_rejected(self):
        with self.assertRaises(ModuleTransportError) as redirected:
            await self.client.request_bytes(
                self.origin,
                "/redirect",
                token="module-token",
                max_bytes=64,
            )
        self.assertEqual(
            redirected.exception.code,
            "module_redirect_forbidden",
        )
        with self.assertRaises(ModuleTransportError) as oversized:
            await self.client.request_bytes(
                self.origin,
                "/artifact",
                token="module-token",
                max_bytes=32,
            )
        self.assertEqual(
            oversized.exception.code,
            "module_response_too_large",
        )

    async def test_resource_stream_forwards_method_and_single_range(self):
        async with self.client.stream_bytes(
            self.origin,
            "/resource",
            method="GET",
            token="module-token",
            range_header="bytes=2-5",
        ) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(
                await response.read(),
                b"2345",
            )
        async with self.client.stream_bytes(
            self.origin,
            "/resource",
            method="HEAD",
            token="module-token",
        ) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers["Content-Length"], "10")
        with self.assertRaises(ModuleTransportError) as redirected:
            async with self.client.stream_bytes(
                self.origin,
                "/redirect",
                method="GET",
                token="module-token",
            ):
                pass
        self.assertEqual(
            redirected.exception.code,
            "module_redirect_forbidden",
        )
        short_json_timeout_client = ModuleHttpClient(
            ModuleAddressPolicy(),
            timeout_seconds=0.05,
        )
        async with short_json_timeout_client.stream_bytes(
            self.origin,
            "/slow-resource",
            method="GET",
            token="module-token",
        ) as response:
            self.assertEqual(await response.read(), b"slow")


class StructuredModelBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_v2_uses_strict_json_schema_and_parses_one_object(self):
        captured = {}

        async def invoke(
            config,
            messages,
            max_tokens,
            temperature=0.2,
            response_format=None,
        ):
            captured.update(
                {
                    "config": config,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "response_format": response_format,
                }
            )
            return '{"status":"ok"}'

        config = SimpleNamespace(
            api_url="http://model.test/v1",
            model_id="fixture-model",
            max_output=4096,
        )
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["status"],
            "properties": {
                "status": {"type": "string", "enum": ["ok"]}
            },
        }
        with (
            patch.object(main.db, "get_model_by_type", return_value=config),
            patch.object(
                main.llm_service,
                "_call_chat_completion_raw",
                new=invoke,
            ),
        ):
            output = await main._module_host_model_invoke_v2(
                "structured prompt",
                schema,
            )

        self.assertEqual(output, {"status": "ok"})
        self.assertEqual(captured["temperature"], 0)
        self.assertEqual(captured["messages"][0]["content"], "structured prompt")
        self.assertEqual(
            captured["response_format"],
            {
                "type": "json_schema",
                "json_schema": {
                    "name": "module_output",
                    "strict": True,
                    "schema": schema,
                },
            },
        )

    async def test_v2_rejects_non_standard_json_numbers(self):
        async def invoke(
            _config,
            _messages,
            max_tokens,
            temperature=0.2,
            response_format=None,
        ):
            return '{"count":NaN}'

        config = SimpleNamespace(
            api_url="http://model.test/v1",
            model_id="fixture-model",
            max_output=4096,
        )
        with (
            patch.object(main.db, "get_model_by_type", return_value=config),
            patch.object(
                main.llm_service,
                "_call_chat_completion_raw",
                new=invoke,
            ),
        ):
            with self.assertRaises(ModuleTaskError) as error:
                await main._module_host_model_invoke_v2(
                    "structured prompt",
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["count"],
                        "properties": {"count": {"type": "number"}},
                    },
                )
        self.assertEqual(error.exception.code, "model_response_invalid")


def _load_reference_module(data_dir, pairing_code, ttl_seconds=600):
    module_name = f"chatraw_reference_t4_{uuid.uuid4().hex}"
    module_path = REFERENCE_DIR / "app.py"
    with patch.dict(
        os.environ,
        {
            "REFERENCE_MODULE_DATA_DIR": str(data_dir),
            "REFERENCE_MODULE_PAIRING_CODE": pairing_code,
            "REFERENCE_MODULE_PAIRING_TTL_SECONDS": str(ttl_seconds),
        },
    ):
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class ModuleTaskApiTests(unittest.TestCase):
    def setUp(self):
        self.client_backend = FakeTaskClient()
        self.registry = FakeRegistry(self.client_backend)
        self.original_service = main.module_task_service
        self.created_user_ids = []
        self.username_suffix = uuid.uuid4().hex[:10]
        self.admin_token, self.admin_id = self._login("admin", "admin")
        self.creator_token, self.creator_id = self._login("creator", "member")
        self.viewer_token, self.viewer_id = self._login("viewer", "member")
        self.chat = main.db.create_chat(
            "T4 API chat",
            owner_user_id=self.creator_id,
        )
        self.resource_id = main.db.save_document(
            "api-resource.txt",
            "api resource",
            uploader_user_id=self.creator_id,
        )

        async def invoke(_prompt):
            return "host model output"

        async def invoke_v2(_prompt, _output_schema):
            return {"status": "ok"}

        async def chat_completion(request):
            return {
                "profile": request["profile"],
                "model": "test-tool-model",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-clock",
                        "name": "time.now",
                        "arguments": "{}",
                    }
                ],
                "finish_reason": "tool_calls",
                "usage": {
                    "prompt_tokens": 8,
                    "completion_tokens": 4,
                    "total_tokens": 12,
                },
            }

        self.resource_temp = tempfile.TemporaryDirectory(
            prefix="chatraw-t4-api-resources-"
        )
        main.module_task_service = ModuleTaskService(
            main.db.db_path,
            busy_timeout_ms=main.db.busy_timeout_ms,
            registry=self.registry,
            audit=main.auth_service.audit,
            chat_generation_active=main._chat_generation_active,
            model_invoke=invoke,
            model_invoke_v2=invoke_v2,
            model_chat_completion=chat_completion,
            resource_dir=self.resource_temp.name,
        )
        self.client = TestClient(
            main.app,
            client=(f"t4-{self.username_suffix}.test", 50000),
        )

    def tearDown(self):
        self.client.close()
        main.module_task_service = self.original_service
        main._active_chat_generations.clear()
        with main.db.connection(write=True) as connection:
            connection.execute("DELETE FROM module_capability_tokens")
            connection.execute("DELETE FROM module_task_artifacts")
            connection.execute("DELETE FROM module_task_resource_refs")
            connection.execute("DELETE FROM module_tasks")
            connection.execute(
                "DELETE FROM document_chunks WHERE document_id = ?",
                (self.resource_id,),
            )
            connection.execute(
                "DELETE FROM documents WHERE id = ?",
                (self.resource_id,),
            )
            connection.execute(
                "DELETE FROM chat_skill_activations WHERE chat_id = ?",
                (self.chat.id,),
            )
            connection.execute(
                "DELETE FROM chat_compactions WHERE chat_id = ?",
                (self.chat.id,),
            )
            connection.execute(
                "DELETE FROM messages WHERE chat_id = ?",
                (self.chat.id,),
            )
            connection.execute(
                "DELETE FROM chats WHERE id = ?",
                (self.chat.id,),
            )
            connection.executemany(
                "DELETE FROM audit_log WHERE actor_user_id = ?",
                [(user_id,) for user_id in self.created_user_ids],
            )
            connection.executemany(
                "DELETE FROM users WHERE id = ?",
                [(user_id,) for user_id in self.created_user_ids],
            )
        self.resource_temp.cleanup()

    def _login(self, label, role):
        username = f"t4-{label}-{self.username_suffix}"
        password = "T4-api-password-2026"
        user_id = str(uuid.uuid4())
        now = "2026-07-23T00:00:00Z"
        with main.db.connection(write=True) as connection:
            connection.execute(
                """
                INSERT INTO users (
                    id, username, password_hash, role, enabled,
                    created_at, updated_at, password_changed_at
                ) VALUES (?, ?, ?, ?, 1, ?, ?, ?)
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
        self.created_user_ids.append(user_id)
        _principal, token = main.auth_service.login(username, password)
        return token, user_id

    @staticmethod
    def _headers(token, *, key=None):
        headers = {
            "Origin": "http://testserver",
            "Cookie": f"chatraw_session={token}",
        }
        if key is not None:
            headers["Idempotency-Key"] = key
        return headers

    def _payload(self):
        return {
            "module_id": REFERENCE_MANIFEST["module_id"],
            "action_id": "echo.task",
            "input": {"text": "api task"},
            "chat_id": self.chat.id,
            "user_message": "Run API task",
            "resource_ids": [self.resource_id],
        }

    def _create(self, key="api-task-key"):
        return self.client.post(
            "/api/module-tasks",
            headers=self._headers(self.creator_token, key=key),
            json=self._payload(),
        )

    def _model_capability(self, task):
        return next(
            item
            for item in self.client_backend.tasks[task["task_id"]][
                "host_capabilities"
            ]
            if item["capability"] == "model.chat.completions"
        )

    def test_auth_shared_read_control_and_browser_redaction(self):
        self.assertEqual(
            self.client.get("/api/module-tasks").status_code,
            401,
        )
        response = self._create()
        self.assertEqual(response.status_code, 202, response.text)
        task = response.json()
        serialized = response.text
        self.assertNotIn("result", task)
        self.assertNotIn("127.0.0.1", serialized)
        self.assertNotIn("private-module-credential", serialized)
        self.assertNotIn("host_capabilities", serialized)

        viewed = self.client.get(
            f"/api/module-tasks/{task['task_id']}",
            headers=self._headers(self.viewer_token),
        )
        self.assertEqual(viewed.status_code, 200, viewed.text)
        self.assertFalse(viewed.json()["can_control"])
        denied = self.client.post(
            f"/api/module-tasks/{task['task_id']}/cancel",
            headers=self._headers(self.viewer_token),
            json={},
        )
        self.assertEqual(denied.status_code, 403, denied.text)
        self.assertTrue(
            any(
                item["actor_user_id"] == self.viewer_id
                and item["action"] == "module.task.cancel"
                and item["outcome"] == "failure"
                and item["details"]["error_code"]
                == "task_control_forbidden"
                for item in main.auth_service.list_audit()
            )
        )
        admin = self.client.post(
            f"/api/module-tasks/{task['task_id']}/cancel",
            headers=self._headers(self.admin_token),
            json={},
        )
        self.assertEqual(admin.status_code, 202, admin.text)

    def test_task_resource_upload_stream_and_output_proxy(self):
        unauthenticated = self.client.post(
            "/api/module-task-resources",
            files={"file": ("source.pdf", b"%PDF-secret", "application/pdf")},
        )
        self.assertEqual(unauthenticated.status_code, 401)
        uploaded_response = self.client.post(
            "/api/module-task-resources",
            headers=self._headers(self.creator_token),
            files={"file": ("source.pdf", b"%PDF-secret", "application/pdf")},
        )
        self.assertEqual(
            uploaded_response.status_code,
            201,
            uploaded_response.text,
        )
        uploaded = uploaded_response.json()
        self.assertNotIn("creator_user_id", uploaded_response.text)
        self.assertNotIn("capability", uploaded_response.text.lower())

        payload = self._payload()
        payload.update(
            {
                "chat_id": None,
                "user_message": None,
                "resource_ids": [uploaded["resource_id"]],
            }
        )
        cross_user = self.client.post(
            "/api/module-tasks",
            headers=self._headers(self.viewer_token, key="api-cross-user"),
            json=payload,
        )
        self.assertEqual(cross_user.status_code, 403, cross_user.text)
        created = self.client.post(
            "/api/module-tasks",
            headers=self._headers(self.creator_token, key="api-uploaded"),
            json=payload,
        )
        self.assertEqual(created.status_code, 202, created.text)
        task = created.json()
        remote = self.client_backend.tasks[task["task_id"]]
        capabilities = {
            item["capability"]: item
            for item in remote["host_capabilities"]
        }
        self.assertIn("resource.stream", capabilities)
        self.assertNotIn("resource.read", capabilities)
        stream = self.client.get(
            (
                "/api/module-capabilities/v1/resource-stream/"
                f"{uploaded['resource_id']}"
            ),
            headers={
                "Authorization": (
                    f"Bearer {capabilities['resource.stream']['token']}"
                )
            },
        )
        self.assertEqual(stream.status_code, 200, stream.text)
        self.assertEqual(stream.content, b"%PDF-secret")
        self.assertEqual(
            stream.headers["x-content-sha256"],
            uploaded["sha256"],
        )
        reused = self.client.post(
            "/api/module-tasks",
            headers=self._headers(
                self.creator_token,
                key="api-uploaded-reused",
            ),
            json=payload,
        )
        self.assertEqual(reused.status_code, 409, reused.text)

        self.client_backend.add_resource(task["task_id"], b"0123456789")
        self.client_backend.set_state(task["task_id"], "succeeded")
        current = self.client.get(
            f"/api/module-tasks/{task['task_id']}",
            headers=self._headers(self.creator_token),
        )
        self.assertEqual(current.status_code, 200, current.text)
        resource = current.json()["resources"][0]
        denied = self.client.get(
            (
                f"/api/module-tasks/{task['task_id']}/resources/"
                f"{resource['resource_ref']}"
            ),
            headers=self._headers(self.viewer_token),
        )
        self.assertEqual(denied.status_code, 403, denied.text)
        ranged = self.client.get(
            (
                f"/api/module-tasks/{task['task_id']}/resources/"
                f"{resource['resource_ref']}"
            ),
            headers={
                **self._headers(self.creator_token),
                "Range": "bytes=2-5",
            },
        )
        self.assertEqual(ranged.status_code, 206, ranged.text)
        self.assertEqual(ranged.content, b"2345")
        self.assertEqual(ranged.headers["content-range"], "bytes 2-5/10")
        self.assertEqual(ranged.headers["content-security-policy"], "sandbox")
        head = self.client.head(
            (
                f"/api/module-tasks/{task['task_id']}/resources/"
                f"{resource['resource_ref']}"
            ),
            headers=self._headers(self.admin_token),
        )
        self.assertEqual(head.status_code, 200, head.text)
        self.assertEqual(head.headers["content-length"], "10")

    def test_task_resource_upload_rejects_extra_parts_and_oversize_while_parsing(self):
        headers = self._headers(self.creator_token)
        extra_file = self.client.post(
            "/api/module-task-resources",
            headers=headers,
            files=[
                ("file", ("one.pdf", b"one", "application/pdf")),
                ("other", ("two.pdf", b"two", "application/pdf")),
            ],
        )
        self.assertEqual(extra_file.status_code, 400, extra_file.text)
        extra_field = self.client.post(
            "/api/module-task-resources",
            headers=headers,
            files={"file": ("one.pdf", b"one", "application/pdf")},
            data={"note": "not allowed"},
        )
        self.assertEqual(extra_field.status_code, 400, extra_field.text)
        wrong_name = self.client.post(
            "/api/module-task-resources",
            headers=headers,
            files={"document": ("one.pdf", b"one", "application/pdf")},
        )
        self.assertEqual(wrong_name.status_code, 400, wrong_name.text)
        main.module_task_service.max_input_resource_bytes = 4
        oversized = self.client.post(
            "/api/module-task-resources",
            headers=headers,
            files={"file": ("large.pdf", b"12345", "application/pdf")},
        )
        self.assertEqual(oversized.status_code, 413, oversized.text)
        self.assertEqual(list(Path(self.resource_temp.name).iterdir()), [])

    def test_browser_cannot_supply_authority_or_internal_connection_fields(self):
        for field, value in (
            ("role", "admin"),
            ("module_url", "http://127.0.0.1:1"),
            ("connection_token", "secret"),
            ("host_token", "secret"),
        ):
            payload = self._payload()
            payload[field] = value
            response = self.client.post(
                "/api/module-tasks",
                headers=self._headers(
                    self.creator_token,
                    key=f"forbidden-{field}",
                ),
                json=payload,
            )
            with self.subTest(field=field):
                self.assertEqual(response.status_code, 400, response.text)

    def test_active_task_blocks_chat_document_delete_and_normal_generation(self):
        task = self._create().json()
        delete_chat = self.client.delete(
            f"/api/chats/{self.chat.id}",
            headers=self._headers(self.creator_token),
        )
        self.assertEqual(delete_chat.status_code, 409, delete_chat.text)
        delete_resource = self.client.delete(
            f"/api/documents/{self.resource_id}",
            headers=self._headers(self.creator_token),
        )
        self.assertEqual(
            delete_resource.status_code,
            409,
            delete_resource.text,
        )
        chat = self.client.post(
            "/api/chat",
            headers=self._headers(self.creator_token),
            json={"chat_id": self.chat.id, "message": "conflicting generation"},
        )
        self.assertEqual(chat.status_code, 409, chat.text)

        self.client_backend.set_state(task["task_id"], "succeeded")
        self.client.get(
            f"/api/module-tasks/{task['task_id']}",
            headers=self._headers(self.creator_token),
        )
        delete_resource = self.client.delete(
            f"/api/documents/{self.resource_id}",
            headers=self._headers(self.creator_token),
        )
        self.assertEqual(delete_resource.status_code, 200, delete_resource.text)
        self.resource_id = "already-deleted"

    def test_agent_chat_clear_retains_active_task_and_deletes_idle_chat(self):
        retained = main.db.create_chat(
            "Agent with active task",
            owner_user_id=self.creator_id,
            kind="hermes_agent",
        )
        deleted = main.db.create_chat(
            "Idle Agent chat",
            owner_user_id=self.creator_id,
            kind="hermes_agent",
        )
        try:
            payload = self._payload()
            payload["chat_id"] = retained.id
            created = self.client.post(
                "/api/module-tasks",
                headers=self._headers(
                    self.creator_token,
                    key="agent-clear-retain-active",
                ),
                json=payload,
            )
            self.assertEqual(created.status_code, 202, created.text)
            task = created.json()

            cleared = self.client.delete(
                "/api/agent/chats",
                headers=self._headers(self.creator_token),
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
                item["id"]
                for item in self.client.get(
                    "/api/agent/chats",
                    headers=self._headers(self.creator_token),
                ).json()
            }
            self.assertEqual(remaining, {retained.id})
            self.assertNotIn(deleted.id, remaining)

            self.client_backend.set_state(task["task_id"], "succeeded")
            reconciled = self.client.get(
                f"/api/module-tasks/{task['task_id']}",
                headers=self._headers(self.creator_token),
            )
            self.assertEqual(reconciled.status_code, 200, reconciled.text)
            cleared_after_completion = self.client.delete(
                "/api/agent/chats",
                headers=self._headers(self.creator_token),
            )
            self.assertEqual(
                cleared_after_completion.json(),
                {
                    "success": True,
                    "deleted_count": 1,
                    "retained_count": 0,
                },
            )
        finally:
            main.db.delete_chat(retained.id)
            main.db.delete_chat(deleted.id)

    def test_sse_resume_artifact_and_capability_routes(self):
        task = self._create().json()
        remote = self.client_backend.tasks[task["task_id"]]
        remote["events"] = [
            {
                "id": 1,
                "event": "task.status",
                "data": {"state": "running"},
            },
            {
                "id": 2,
                "event": "output.snapshot",
                "data": {"text": "snapshot"},
            },
        ]
        remote["last_event_id"] = 2
        events = self.client.get(
            f"/api/module-tasks/{task['task_id']}/events",
            headers={
                **self._headers(self.viewer_token),
                "Last-Event-ID": "1",
            },
        )
        self.assertEqual(events.status_code, 200, events.text)
        self.assertNotIn("id: 1\n", events.text)
        self.assertIn("id: 2\n", events.text)
        self.assertIn(": heartbeat", events.text)

        capabilities = {
            item["capability"]: item["token"]
            for item in remote["host_capabilities"]
        }
        chat = self.client.get(
            "/api/module-capabilities/v1/chat",
            headers={
                "Authorization": f"Bearer {capabilities['chat.read']}"
            },
        )
        self.assertEqual(chat.status_code, 200, chat.text)
        chat_payload = chat.json()
        self.assertEqual(
            chat_payload["conversation_context"]["schema_version"],
            "1",
        )
        self.assertEqual(
            chat_payload["conversation_context"]["current_task"][
                "task_id"
            ],
            task["task_id"],
        )
        resource = self.client.get(
            f"/api/module-capabilities/v1/resources/{self.resource_id}",
            headers={
                "Authorization": (
                    f"Bearer {capabilities['resource.read']}"
                )
            },
        )
        self.assertEqual(resource.status_code, 200, resource.text)
        model = self.client.post(
            "/api/module-capabilities/v1/model/invoke",
            headers={
                "Authorization": (
                    f"Bearer {capabilities['model.invoke']}"
                )
            },
            json={"prompt": "no API key exposure"},
        )
        self.assertEqual(model.status_code, 200, model.text)
        self.assertNotIn("api_key", model.text.lower())
        structured = self.client.post(
            "/api/module-capabilities/v1/model/invoke-v2",
            headers={
                "Authorization": (
                    f"Bearer {capabilities['model.invoke.v2']}"
                )
            },
            json={
                "prompt": "return one closed object",
                "output_schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["status"],
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["ok"],
                        }
                    },
                },
            },
        )
        self.assertEqual(structured.status_code, 200, structured.text)
        self.assertEqual(structured.json()["output"], {"status": "ok"})
        self.assertNotIn("api_key", structured.text.lower())
        unsafe_schema = self.client.post(
            "/api/module-capabilities/v1/model/invoke-v2",
            headers={
                "Authorization": (
                    f"Bearer {capabilities['model.invoke.v2']}"
                )
            },
            json={
                "prompt": "follow a remote schema",
                "output_schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "$ref": "https://example.invalid/schema.json",
                },
            },
        )
        self.assertEqual(unsafe_schema.status_code, 400, unsafe_schema.text)
        self.assertEqual(
            unsafe_schema.json()["code"],
            "invalid_model_request",
        )
        schema_mismatch = self.client.post(
            "/api/module-capabilities/v1/model/invoke-v2",
            headers={
                "Authorization": (
                    f"Bearer {capabilities['model.invoke.v2']}"
                )
            },
            json={
                "prompt": "return a count",
                "output_schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["count"],
                    "properties": {"count": {"type": "integer"}},
                },
            },
        )
        self.assertEqual(
            schema_mismatch.status_code,
            502,
            schema_mismatch.text,
        )
        self.assertEqual(
            schema_mismatch.json()["code"],
            "model_response_schema_invalid",
        )
        principal = self.client.get(
            "/api/module-capabilities/v1/principal",
            headers={
                "Authorization": (
                    f"Bearer {capabilities['principal.read']}"
                )
            },
        )
        self.assertEqual(principal.status_code, 200, principal.text)
        self.assertEqual(
            principal.json(),
            {
                "task_id": task["task_id"],
                "actor_ref": f"chatraw-user:{self.creator_id}",
                "role": "member",
            },
        )
        completion = self.client.post(
            "/api/module-capabilities/v1/model/chat-completions",
            headers={
                "Authorization": (
                    "Bearer "
                    f"{capabilities['model.chat.completions']}"
                )
            },
            json={
                "profile": "agent-runtime",
                "messages": [
                    {"role": "user", "content": "What time is it?"}
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "time.now",
                            "description": "Current time",
                            "parameters": {
                                "type": "object",
                                "properties": {},
                            },
                        },
                    }
                ],
                "timeout_seconds": 180,
            },
        )
        self.assertEqual(completion.status_code, 200, completion.text)
        self.assertEqual(
            completion.json()["completion"]["tool_calls"][0]["name"],
            "time.now",
        )
        self.assertNotIn("api_key", completion.text.lower())
        openai_completion = self.client.post(
            "/api/module-capabilities/v1/openai/chat/completions",
            headers={
                "Authorization": (
                    "Bearer "
                    f"{capabilities['model.chat.completions']}"
                )
            },
            json={
                "model": "agent-runtime",
                "messages": [
                    {"role": "user", "content": "What time is it?"}
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "time.now",
                            "description": "Current time",
                            "parameters": {
                                "type": "object",
                                "properties": {},
                            },
                        },
                    }
                ],
                "max_completion_tokens": 256,
                "stream": False,
            },
        )
        self.assertEqual(
            openai_completion.status_code,
            200,
            openai_completion.text,
        )
        self.assertEqual(
            openai_completion.json()["choices"][0]["message"][
                "tool_calls"
            ][0]["function"]["name"],
            "time.now",
        )
        self.assertNotIn("api_key", openai_completion.text.lower())
        invalid_timeout = self.client.post(
            "/api/module-capabilities/v1/model/chat-completions",
            headers={
                "Authorization": (
                    "Bearer "
                    f"{capabilities['model.chat.completions']}"
                )
            },
            json={
                "profile": "agent-runtime",
                "messages": [{"role": "user", "content": "test"}],
                "timeout_seconds": 179,
            },
        )
        self.assertEqual(
            invalid_timeout.status_code,
            400,
            invalid_timeout.text,
        )
        self.assertEqual(
            self.client.get(
                "/api/module-capabilities/v1/chat",
                headers={"Authorization": "Bearer invalid"},
            ).status_code,
            401,
        )

        self.client_backend.set_state(
            task["task_id"],
            "succeeded",
            text="download",
            artifact=True,
        )
        current = self.client.get(
            f"/api/module-tasks/{task['task_id']}",
            headers=self._headers(self.viewer_token),
        ).json()
        artifact = current["artifacts"][0]
        download = self.client.get(
            (
                f"/api/module-tasks/{task['task_id']}/artifacts/"
                f"{artifact['artifact_ref']}"
            ),
            headers=self._headers(self.viewer_token),
        )
        self.assertEqual(download.content, b"download")
        self.assertIn("attachment", download.headers["content-disposition"])
        self.assertEqual(download.headers["content-security-policy"], "sandbox")

    def test_openai_stream_is_sanitized_and_consumed_once(self):
        task = self._create(key="api-stream-safe").json()
        capability = self._model_capability(task)
        private_prompt = "PRIVATE_PROMPT_SENTINEL"
        private_answer = "PRIVATE_ANSWER_SENTINEL"
        private_reasoning = "PRIVATE_REASONING_SENTINEL"
        chunks = [
            b": upstream-heartbeat\n\n",
            (
                "data: "
                + json.dumps(
                    {
                        "id": "chatcmpl-stream",
                        "object": "chat.completion.chunk",
                        "created": 1785000000,
                        "model": "fixture-model",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "content": private_answer,
                                    "reasoning_content": private_reasoning,
                                },
                                "finish_reason": None,
                            }
                        ],
                        "vendor_trace": "PRIVATE_TRACE_SENTINEL",
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            ).encode("utf-8"),
            b"data: [DONE]\n\n",
        ]
        upstream = FakeModelStreamResponse(chunks)

        class FakeSession:
            def __init__(self):
                self.url = None
                self.payload = None
                self.headers = None

            async def post(
                inner_self,
                url,
                *,
                json,
                headers,
                timeout,
            ):
                inner_self.url = url
                inner_self.payload = json
                inner_self.headers = headers
                return upstream

        session = FakeSession()

        async def get_session():
            return session

        model_config = SimpleNamespace(
            api_url="http://private-upstream.invalid",
            model_id="fixture-model",
            max_output=4096,
            api_key="PRIVATE_API_KEY_SENTINEL",
            capability=SimpleNamespace(tools=True),
        )
        settings = SimpleNamespace(
            chat_settings=SimpleNamespace(top_p=0.9)
        )

        records = []

        class CaptureHandler(logging.Handler):
            def emit(inner_self, record):
                records.append(record)

        capture = CaptureHandler(level=logging.DEBUG)
        observed_loggers = [
            logging.getLogger(),
            main.logger,
            logging.getLogger("uvicorn.access"),
            logging.getLogger("uvicorn.error"),
            logging.getLogger("aiohttp.client"),
        ]
        for observed in observed_loggers:
            observed.addHandler(capture)
        try:
            with patch.object(
                main.db,
                "get_model_by_type",
                return_value=model_config,
            ), patch.object(
                main.db,
                "get_settings",
                return_value=settings,
            ), patch.object(
                main,
                "get_http_session",
                new=get_session,
            ):
                response = self.client.post(
                    "/api/module-capabilities/v1/openai/chat/completions",
                    headers={
                        "Authorization": f"Bearer {capability['token']}"
                    },
                    json={
                        "model": "agent-runtime",
                        "messages": [
                            {"role": "user", "content": private_prompt}
                        ],
                        "stream": True,
                        "stream_options": {"include_usage": True},
                    },
                )
        finally:
            for observed in observed_loggers:
                observed.removeHandler(capture)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(
            response.headers["content-type"].startswith(
                "text/event-stream"
            )
        )
        self.assertIn(": heartbeat\n\n", response.text)
        self.assertIn(private_answer, response.text)
        self.assertNotIn(private_reasoning, response.text)
        self.assertNotIn("PRIVATE_TRACE_SENTINEL", response.text)
        self.assertIn("data: [DONE]\n\n", response.text)
        self.assertTrue(upstream.closed)
        self.assertEqual(
            session.payload["stream_options"],
            {"include_usage": True},
        )
        self.assertEqual(
            session.url,
            "http://private-upstream.invalid/chat/completions",
        )
        self.assertEqual(
            session.headers["Authorization"],
            "Bearer PRIVATE_API_KEY_SENTINEL",
        )
        rendered_logs = "\n".join(
            record.getMessage()
            for record in records
        )
        for private_value in (
            private_prompt,
            private_answer,
            private_reasoning,
            "PRIVATE_TRACE_SENTINEL",
            "PRIVATE_API_KEY_SENTINEL",
            "http://private-upstream.invalid",
        ):
            self.assertNotIn(private_value, rendered_logs)
        with main.db.connection() as connection:
            row = connection.execute(
                """
                SELECT use_count
                FROM module_capability_tokens
                WHERE task_id = ?
                  AND capability = 'model.chat.completions'
                """,
                (task["task_id"],),
            ).fetchone()
        self.assertEqual(row["use_count"], 1)

    def test_openai_stream_openapi_contract_is_machine_validatable(self):
        operation = main.app.openapi()["paths"][
            "/api/module-capabilities/v1/openai/chat/completions"
        ]["post"]
        schema = operation["requestBody"]["content"][
            "application/json"
        ]["schema"]
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        validator.validate(
            {
                "model": "agent-runtime",
                "messages": [{"role": "user", "content": "safe"}],
                "stream": True,
                "stream_options": {"include_usage": True},
            }
        )
        for invalid in (
            {
                "model": "agent-runtime",
                "messages": [{"role": "user", "content": "safe"}],
                "stream": True,
                "stream_options": {"include_usage": False},
            },
            {
                "model": "agent-runtime",
                "messages": [{"role": "user", "content": "safe"}],
                "stream": False,
                "stream_options": {"include_usage": True},
            },
            {
                "model": "agent-runtime",
                "messages": [{"role": "user", "content": "safe"}],
                "max_tokens": 128,
                "max_completion_tokens": 128,
            },
        ):
            with self.subTest(invalid=invalid):
                self.assertFalse(validator.is_valid(invalid))
        self.assertEqual(
            operation["responses"]["200"]["content"][
                "text/event-stream"
            ]["schema"]["type"],
            "string",
        )

    def test_openai_stream_errors_before_and_after_headers(self):
        before_task = self._create(key="api-stream-before-error").json()
        before_capability = self._model_capability(before_task)

        async def fail_before_headers(_request):
            raise ModuleTaskError(
                "model_request_failed",
                "Model request failed",
                status_code=502,
            )

        with patch.object(
            main,
            "_open_module_host_model_chat_stream",
            new=fail_before_headers,
        ):
            before = self.client.post(
                "/api/module-capabilities/v1/openai/chat/completions",
                headers={
                    "Authorization": (
                        f"Bearer {before_capability['token']}"
                    )
                },
                json={
                    "model": "agent-runtime",
                    "messages": [{"role": "user", "content": "safe"}],
                    "stream": True,
                },
            )
        self.assertEqual(before.status_code, 502, before.text)
        self.assertEqual(
            before.json(),
            {
                "detail": "Model request failed",
                "code": "model_request_failed",
            },
        )

        upstream = FakeModelStreamResponse(
            [b"data: {malformed}\n\n"]
        )

        async def fail_after_headers(_request):
            return upstream

        with patch.object(
            main,
            "_open_module_host_model_chat_stream",
            new=fail_after_headers,
        ):
            after = self.client.post(
                "/api/module-capabilities/v1/openai/chat/completions",
                headers={
                    "Authorization": (
                        f"Bearer {before_capability['token']}"
                    )
                },
                json={
                    "model": "agent-runtime",
                    "messages": [{"role": "user", "content": "safe"}],
                    "stream": True,
                },
            )
        self.assertEqual(after.status_code, 200, after.text)
        self.assertEqual(
            [
                json.loads(line[6:])
                for line in after.text.splitlines()
                if line.startswith("data: {")
            ],
            [
                {
                    "error": {
                        "code": "invalid_model_stream",
                        "message": "Model returned an invalid stream",
                    }
                }
            ],
        )
        self.assertNotIn("[DONE]", after.text)
        self.assertTrue(upstream.closed)

        transport_upstream = FakeModelStreamResponse(
            [
                (
                    "data: "
                    + json.dumps(
                        {
                            "id": "chatcmpl-midstream",
                            "object": "chat.completion.chunk",
                            "created": 1785000000,
                            "model": "fixture-model",
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"content": "first"},
                                    "finish_reason": None,
                                }
                            ],
                        },
                        separators=(",", ":"),
                    )
                    + "\n\n"
                ).encode("utf-8")
            ],
            error_after_chunks=aiohttp.ClientPayloadError(
                "PRIVATE_TRANSPORT_FAILURE"
            ),
        )

        async def transport_failure(_request):
            return transport_upstream

        with patch.object(
            main,
            "_open_module_host_model_chat_stream",
            new=transport_failure,
        ):
            transport = self.client.post(
                "/api/module-capabilities/v1/openai/chat/completions",
                headers={
                    "Authorization": (
                        f"Bearer {before_capability['token']}"
                    )
                },
                json={
                    "model": "agent-runtime",
                    "messages": [{"role": "user", "content": "safe"}],
                    "stream": True,
                },
            )
        self.assertEqual(transport.status_code, 200, transport.text)
        self.assertIn('"content":"first"', transport.text)
        self.assertIn('"code":"model_stream_failed"', transport.text)
        self.assertNotIn("PRIVATE_TRANSPORT_FAILURE", transport.text)
        self.assertNotIn("[DONE]", transport.text)
        self.assertTrue(transport_upstream.closed)

    def test_openai_stream_disconnect_closes_upstream(self):
        task = self._create(key="api-stream-disconnect").json()
        capability = self._model_capability(task)
        first_chunk = (
            "data: "
            + json.dumps(
                {
                    "id": "chatcmpl-disconnect",
                    "object": "chat.completion.chunk",
                    "created": 1785000000,
                    "model": "fixture-model",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": "first"},
                            "finish_reason": None,
                        }
                    ],
                },
                separators=(",", ":"),
            )
            + "\n\n"
        ).encode("utf-8")
        upstream = FakeModelStreamResponse(
            [first_chunk],
            block_after_chunks=True,
        )

        async def exercise_disconnect():
            async def open_stream(_request):
                return upstream

            body = json.dumps(
                {
                    "model": "agent-runtime",
                    "messages": [{"role": "user", "content": "safe"}],
                    "stream": True,
                },
                separators=(",", ":"),
            ).encode("utf-8")
            disconnect = asyncio.Event()
            request_delivered = False

            async def receive():
                nonlocal request_delivered
                if not request_delivered:
                    request_delivered = True
                    return {
                        "type": "http.request",
                        "body": body,
                        "more_body": False,
                    }
                await disconnect.wait()
                return {"type": "http.disconnect"}

            async def send(message):
                if (
                    message["type"] == "http.response.body"
                    and message.get("body")
                ):
                    disconnect.set()

            scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": (
                    "/api/module-capabilities/v1/openai/"
                    "chat/completions"
                ),
                "raw_path": (
                    b"/api/module-capabilities/v1/openai/"
                    b"chat/completions"
                ),
                "query_string": b"",
                "root_path": "",
                "headers": [
                    (b"host", b"testserver"),
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (
                        b"authorization",
                        f"Bearer {capability['token']}".encode("ascii"),
                    ),
                ],
                "client": ("127.0.0.1", 50123),
                "server": ("testserver", 80),
            }
            with patch.object(
                main,
                "_open_module_host_model_chat_stream",
                new=open_stream,
            ):
                await asyncio.wait_for(
                    main.app(scope, receive, send),
                    timeout=2,
                )
            await asyncio.wait_for(
                upstream.content.cancelled.wait(),
                timeout=1,
            )

        asyncio.run(exercise_disconnect())
        self.assertTrue(upstream.closed)

    def test_openai_stream_disconnect_before_headers_cancels_open(self):
        task = self._create(key="api-stream-preheader-disconnect").json()
        capability = self._model_capability(task)
        open_started = asyncio.Event()
        open_cancelled = asyncio.Event()

        async def exercise_disconnect():
            async def open_stream(_request):
                open_started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    open_cancelled.set()

            body = json.dumps(
                {
                    "model": "agent-runtime",
                    "messages": [{"role": "user", "content": "safe"}],
                    "stream": True,
                    "stream_options": {"include_usage": True},
                },
                separators=(",", ":"),
            ).encode("utf-8")
            request_delivered = False

            async def receive():
                nonlocal request_delivered
                if not request_delivered:
                    request_delivered = True
                    return {
                        "type": "http.request",
                        "body": body,
                        "more_body": False,
                    }
                await open_started.wait()
                return {"type": "http.disconnect"}

            async def send(_message):
                sent.append(_message)

            scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": (
                    "/api/module-capabilities/v1/openai/"
                    "chat/completions"
                ),
                "raw_path": (
                    b"/api/module-capabilities/v1/openai/"
                    b"chat/completions"
                ),
                "query_string": b"",
                "root_path": "",
                "headers": [
                    (b"host", b"testserver"),
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (
                        b"authorization",
                        f"Bearer {capability['token']}".encode("ascii"),
                    ),
                ],
                "client": ("127.0.0.1", 50123),
                "server": ("testserver", 80),
            }
            sent = []
            with patch.object(
                main,
                "_open_module_host_model_chat_stream",
                new=open_stream,
            ):
                await asyncio.wait_for(
                    main.app(scope, receive, send),
                    timeout=2,
                )
            await asyncio.wait_for(
                open_cancelled.wait(),
                timeout=1,
            )
            starts = [
                message
                for message in sent
                if message["type"] == "http.response.start"
            ]
            self.assertEqual(starts[-1]["status"], 499)

        asyncio.run(exercise_disconnect())

    def test_disabling_user_revokes_capability_tokens(self):
        task = self._create().json()
        raw_token = next(
            item["token"]
            for item in self.client_backend.tasks[task["task_id"]][
                "host_capabilities"
            ]
            if item["capability"] == "chat.read"
        )
        disabled = self.client.post(
            f"/api/admin/users/{self.creator_id}/disable",
            headers=self._headers(self.admin_token),
        )
        self.assertEqual(disabled.status_code, 200, disabled.text)
        rejected = self.client.get(
            "/api/module-capabilities/v1/chat",
            headers={"Authorization": f"Bearer {raw_token}"},
        )
        self.assertEqual(rejected.status_code, 401, rejected.text)


class ReferenceTaskConformanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="chatraw-t4-reference-")
        self.pairing_code = "t4-reference-pairing-" + ("x" * 32)
        self.reference = _load_reference_module(
            self.temp.name,
            self.pairing_code,
        )
        self.client = TestClient(self.reference.app)
        self.client.__enter__()
        paired = self.client.post(
            "/chatraw-module/v1/pair",
            json={
                "pairing_code": self.pairing_code,
                "host": {
                    "product": "ChatRaw Server",
                    "module_protocol": "1.0.0",
                    "capability_base_url": "http://127.0.0.1:51111",
                },
            },
        )
        self.assertEqual(paired.status_code, 200, paired.text)
        self.token = paired.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp.cleanup()

    def _create(self, task_id=None, **task_input):
        task_id = task_id or str(uuid.uuid4())
        payload = {
            "task_id": task_id,
            "request_digest": "a" * 64,
            "action_id": "echo.task",
            "action_version": "1.0.0",
            "config_revision": "1",
            "input": {"text": "persistent", **task_input},
            "active_skills": [],
            "active_rules": [],
            "host_capabilities": [],
        }
        response = self.client.post(
            "/chatraw-module/v1/tasks",
            headers=self.headers,
            json=payload,
        )
        self.assertEqual(response.status_code, 202, response.text)
        return task_id, payload

    def _wait_state(self, task_id, expected, timeout=3):
        deadline = time.time() + timeout
        while time.time() < deadline:
            response = self.client.get(
                f"/chatraw-module/v1/tasks/{task_id}",
                headers=self.headers,
            )
            if response.json()["state"] in expected:
                return response.json()
            time.sleep(0.02)
        self.fail(f"task {task_id} did not reach {expected}")

    def test_long_task_stream_snapshot_artifact_and_cursor_compaction(self):
        task_id, payload = self._create(
            steps=30,
            delay_ms=1,
            create_artifact=True,
        )
        terminal = self._wait_state(task_id, {"succeeded"})
        self.assertEqual(terminal["result"]["text"], "Hello: persistent")
        replay = self.client.get(
            f"/chatraw-module/v1/tasks/{task_id}/events",
            headers={**self.headers, "Last-Event-ID": "0"},
        )
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertIn("event: output.snapshot", replay.text)
        first_id = int(
            next(
                line.removeprefix("id: ")
                for line in replay.text.splitlines()
                if line.startswith("id: ")
            )
        )
        self.assertGreater(first_id, 1)
        resumed = self.client.get(
            f"/chatraw-module/v1/tasks/{task_id}/events",
            headers={**self.headers, "Last-Event-ID": str(first_id)},
        )
        self.assertNotIn(f"id: {first_id}\n", resumed.text)
        artifact = terminal["artifacts"][0]
        downloaded = self.client.get(
            (
                f"/chatraw-module/v1/tasks/{task_id}/artifacts/"
                f"{artifact['artifact_id']}"
            ),
            headers=self.headers,
        )
        self.assertEqual(downloaded.content, b"Hello: persistent")

        repeated = self.client.post(
            "/chatraw-module/v1/tasks",
            headers=self.headers,
            json=payload,
        )
        self.assertEqual(repeated.status_code, 202)
        conflict = copy.deepcopy(payload)
        conflict["request_digest"] = "b" * 64
        self.assertEqual(
            self.client.post(
                "/chatraw-module/v1/tasks",
                headers=self.headers,
                json=conflict,
            ).status_code,
            409,
        )

    def test_approval_retry_conflict_cancel_and_outcome_unknown(self):
        approval_task, _ = self._create(
            steps=6,
            delay_ms=1,
            require_approval=True,
        )
        self._wait_state(approval_task, {"waiting_approval"})
        state = self.reference._read_state()
        approval_id = state["tasks"][approval_task]["approval"]["approval_id"]
        endpoint = (
            f"/chatraw-module/v1/tasks/{approval_task}/approvals/"
            f"{approval_id}"
        )
        first = self.client.post(
            endpoint,
            headers=self.headers,
            json={"decision": "approve"},
        )
        self.assertEqual(first.status_code, 200, first.text)
        with self.reference.STATE_LOCK:
            state = self.reference._read_state_unlocked()
            state["tasks"][approval_task]["approval"]["expires_at"] = (
                "2000-01-01T00:00:00Z"
            )
            self.reference._write_state_unlocked(state)
        repeated = self.client.post(
            endpoint,
            headers=self.headers,
            json={"decision": "approve"},
        )
        self.assertEqual(repeated.status_code, 200, repeated.text)
        self.assertEqual(
            self.client.post(
                endpoint,
                headers=self.headers,
                json={"decision": "deny"},
            ).status_code,
            409,
        )
        self._wait_state(approval_task, {"succeeded"})

        cancel_task, _ = self._create(steps=100, delay_ms=2)
        cancel_url = f"/chatraw-module/v1/tasks/{cancel_task}/cancel"
        self.assertIn(
            self.client.post(
                cancel_url, headers=self.headers, json={}
            ).status_code,
            {200, 202},
        )
        self.assertIn(
            self.client.post(
                cancel_url, headers=self.headers, json={}
            ).status_code,
            {200, 202},
        )
        self._wait_state(cancel_task, {"cancelled"})

        unknown_task, _ = self._create(
            steps=2,
            delay_ms=0,
            outcome_unknown=True,
        )
        unknown = self._wait_state(unknown_task, {"failed"})
        self.assertEqual(unknown["outcome_code"], "outcome_unknown")

    def test_module_restart_resumes_running_task_and_persists_events(self):
        task_id, _ = self._create(
            steps=100,
            delay_ms=10,
            create_artifact=True,
        )
        self._wait_state(task_id, {"running"})
        self.client.__exit__(None, None, None)

        restarted = _load_reference_module(
            self.temp.name,
            "different-pairing-code-" + ("y" * 32),
        )
        with TestClient(restarted.app) as client:
            headers = {"Authorization": f"Bearer {self.token}"}
            terminal = None
            deadline = time.time() + 4
            while time.time() < deadline:
                response = client.get(
                    f"/chatraw-module/v1/tasks/{task_id}",
                    headers=headers,
                )
                if response.json()["state"] == "succeeded":
                    terminal = response.json()
                    break
                time.sleep(0.02)
            self.assertIsNotNone(terminal)
            replay = client.get(
                f"/chatraw-module/v1/tasks/{task_id}/events",
                headers={**headers, "Last-Event-ID": "0"},
            )
            self.assertIn("event: task.terminal", replay.text)
            artifact_id = terminal["artifacts"][0]["artifact_id"]
            artifact_body = client.get(
                (
                    f"/chatraw-module/v1/tasks/{task_id}/artifacts/"
                    f"{artifact_id}"
                ),
                headers=headers,
            ).content
            self.assertEqual(artifact_body, b"Hello: persistent")

        restarted_again = _load_reference_module(
            self.temp.name,
            "second-restart-code-" + ("w" * 32),
        )
        with TestClient(restarted_again.app) as client:
            headers = {"Authorization": f"Bearer {self.token}"}
            recovered = client.get(
                f"/chatraw-module/v1/tasks/{task_id}",
                headers=headers,
            )
            self.assertEqual(recovered.status_code, 200, recovered.text)
            self.assertEqual(recovered.json()["state"], "succeeded")
            artifact_id = recovered.json()["artifacts"][0]["artifact_id"]
            downloaded = client.get(
                (
                    f"/chatraw-module/v1/tasks/{task_id}/artifacts/"
                    f"{artifact_id}"
                ),
                headers=headers,
            )
            self.assertEqual(downloaded.content, b"Hello: persistent")
        self.client = TestClient(self.reference.app)
        self.client.__enter__()

    def test_restart_waiting_approval_resumes_and_cancel_race_is_authoritative(self):
        task_id, _ = self._create(
            steps=8,
            delay_ms=1,
            require_approval=True,
        )
        self._wait_state(task_id, {"waiting_approval"})
        approval_id = self.reference._read_state()["tasks"][task_id][
            "approval"
        ]["approval_id"]
        self.client.__exit__(None, None, None)

        restarted = _load_reference_module(
            self.temp.name,
            "restart-approval-code-" + ("z" * 32),
        )
        with TestClient(restarted.app) as client:
            headers = {"Authorization": f"Bearer {self.token}"}
            approved = client.post(
                (
                    f"/chatraw-module/v1/tasks/{task_id}/approvals/"
                    f"{approval_id}"
                ),
                headers=headers,
                json={"decision": "approve"},
            )
            self.assertEqual(approved.status_code, 200, approved.text)
            deadline = time.time() + 3
            while time.time() < deadline:
                state = client.get(
                    f"/chatraw-module/v1/tasks/{task_id}",
                    headers=headers,
                ).json()
                if state["state"] == "succeeded":
                    break
                time.sleep(0.02)
            self.assertEqual(state["state"], "succeeded")
        self.client = TestClient(self.reference.app)
        self.client.__enter__()

        race_id, _ = self._create(
            steps=30,
            delay_ms=1,
            cancel_race_succeeds=True,
        )
        self._wait_state(race_id, {"running"})
        cancel = self.client.post(
            f"/chatraw-module/v1/tasks/{race_id}/cancel",
            headers=self.headers,
            json={},
        )
        self.assertEqual(cancel.status_code, 202, cancel.text)
        race = self._wait_state(race_id, {"succeeded", "cancelled"})
        self.assertEqual(race["state"], "succeeded")

        rejected_id, _ = self._create(
            steps=30,
            delay_ms=1,
            cancel_rejected=True,
        )
        rejected = self.client.post(
            f"/chatraw-module/v1/tasks/{rejected_id}/cancel",
            headers=self.headers,
            json={},
        )
        self.assertEqual(rejected.status_code, 409, rejected.text)

    def test_restart_waiting_approval_still_expires_authoritatively(self):
        task_id, _ = self._create(
            steps=8,
            delay_ms=1,
            require_approval=True,
        )
        self._wait_state(task_id, {"waiting_approval"})
        self.client.__exit__(None, None, None)
        with self.reference.STATE_LOCK:
            state = self.reference._read_state_unlocked()
            state["tasks"][task_id]["approval"]["expires_at"] = (
                "2000-01-01T00:00:00Z"
            )
            self.reference._write_state_unlocked(state)

        restarted = _load_reference_module(
            self.temp.name,
            "restart-expired-code-" + ("v" * 32),
        )
        with TestClient(restarted.app) as client:
            headers = {"Authorization": f"Bearer {self.token}"}
            deadline = time.time() + 3
            while time.time() < deadline:
                result = client.get(
                    f"/chatraw-module/v1/tasks/{task_id}",
                    headers=headers,
                ).json()
                if result["state"] == "failed":
                    break
                time.sleep(0.02)
            self.assertEqual(result["state"], "failed")
            self.assertEqual(result["outcome_code"], "approval_expired")
        self.client = TestClient(self.reference.app)
        self.client.__enter__()

    def test_restart_cancel_requested_converges_to_cancelled(self):
        task_id, _ = self._create(steps=100, delay_ms=10)
        self._wait_state(task_id, {"running"})
        self.client.__exit__(None, None, None)
        with self.reference.STATE_LOCK:
            state = self.reference._read_state_unlocked()
            state["tasks"][task_id]["state"] = "cancel_requested"
            self.reference._write_state_unlocked(state)

        restarted = _load_reference_module(
            self.temp.name,
            "restart-cancel-code-" + ("u" * 32),
        )
        with TestClient(restarted.app) as client:
            headers = {"Authorization": f"Bearer {self.token}"}
            deadline = time.time() + 3
            while time.time() < deadline:
                result = client.get(
                    f"/chatraw-module/v1/tasks/{task_id}",
                    headers=headers,
                ).json()
                if result["state"] == "cancelled":
                    break
                time.sleep(0.02)
            self.assertEqual(result["state"], "cancelled")
        self.client = TestClient(self.reference.app)
        self.client.__enter__()
