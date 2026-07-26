#!/usr/bin/env python3
"""Module Protocol v1 offline and management-surface conformance checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from jsonschema import Draft202012Validator


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.module_protocol import (  # noqa: E402
    ModuleProtocolError,
    canonical_json,
    permission_digest,
    protocol_is_compatible,
    validate_config_view,
    validate_manifest,
)
from backend.module_task_protocol import (  # noqa: E402
    validate_task_event,
    validate_task_summary,
)


CONTRACT_DIR = REPOSITORY_ROOT / "backend" / "contracts"
REFERENCE_MANIFEST = (
    REPOSITORY_ROOT / "examples" / "reference-module" / "manifest.example.json"
)
REFERENCE_RESIDENT_MANIFEST = (
    REPOSITORY_ROOT
    / "examples"
    / "reference-module"
    / "manifest.resident.example.json"
)
REFERENCE_FIXTURE = (
    REPOSITORY_ROOT / "examples" / "reference-module" / "conformance-fixture.json"
)
FIXTURE_SCHEMA = (
    CONTRACT_DIR / "module-conformance-fixture-v1.schema.json"
)


class ConformanceError(RuntimeError):
    pass


class CapabilityStub:
    def __init__(self, requested_base_url: str):
        if requested_base_url == "auto":
            host = "127.0.0.1"
            port = 0
        else:
            parsed = urlsplit(requested_base_url)
            if (
                parsed.scheme != "http"
                or parsed.hostname not in {"127.0.0.1", "localhost"}
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
                or parsed.path not in {"", "/"}
            ):
                raise ConformanceError(
                    "task-probe capability stub requires auto or a loopback "
                    "HTTP origin"
                )
            host = parsed.hostname
            try:
                port = parsed.port or 80
            except ValueError:
                raise ConformanceError(
                    "task-probe capability stub port is invalid"
                ) from None
        self._lock = threading.Lock()
        self._tokens: dict[str, dict[str, Any]] = {}
        self._calls: dict[str, set[str]] = {}
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format: str, *args: Any) -> None:
                del args

            def _send_json(
                self,
                status: int,
                payload: dict[str, Any],
            ) -> None:
                body = json.dumps(
                    payload,
                    separators=(",", ":"),
                ).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_stream_resource(self) -> None:
                body = b"conformance stream"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.send_header(
                    "X-Content-SHA256",
                    hashlib.sha256(body).hexdigest(),
                )
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(body)

            def _authorization(self) -> dict[str, Any] | None:
                authorization = self.headers.get("Authorization", "")
                if not authorization.startswith("Bearer "):
                    return None
                token = authorization[7:]
                with owner._lock:
                    registration = owner._tokens.get(token)
                return registration

            def do_GET(self) -> None:  # noqa: N802
                registration = self._authorization()
                if registration is None:
                    self._send_json(401, {"detail": "Unauthorized"})
                    return
                capability = registration["capability"]
                task_id = registration["task_id"]
                scope = registration["scope"]
                if (
                    capability == "chat.read"
                    and self.path == "/api/module-capabilities/v1/chat"
                ):
                    response = {
                        "task_id": task_id,
                        "chat_id": scope["chat_id"],
                        "conversation_ref": (
                            f"chatraw-chat:{scope['chat_id']}"
                        ),
                        "actor_ref": "chatraw-user:conformance-user",
                        "messages": [
                            {
                                "role": "user",
                                "content": "conformance message",
                                "created_at": "2026-01-01T00:00:00Z",
                            }
                        ],
                    }
                elif (
                    capability == "resource.read"
                    and self.path.startswith(
                        "/api/module-capabilities/v1/resources/"
                    )
                ):
                    resource_id = unquote(self.path.rsplit("/", 1)[-1])
                    if resource_id not in scope["resource_ids"]:
                        self._send_json(
                            403,
                            {"detail": "Resource outside scope"},
                        )
                        return
                    response = {
                        "task_id": task_id,
                        "resource": {
                            "id": resource_id,
                            "filename": "conformance.txt",
                            "content": "conformance resource",
                            "created_at": "2026-01-01T00:00:00Z",
                        },
                    }
                elif (
                    capability == "resource.stream"
                    and self.path.startswith(
                        "/api/module-capabilities/v1/resource-stream/"
                    )
                ):
                    resource_id = unquote(self.path.rsplit("/", 1)[-1])
                    if resource_id not in scope["resource_ids"]:
                        self._send_json(
                            403,
                            {"detail": "Resource outside scope"},
                        )
                        return
                    owner._record_call(task_id, capability)
                    self._send_stream_resource()
                    return
                else:
                    self._send_json(403, {"detail": "Capability denied"})
                    return
                owner._record_call(task_id, capability)
                self._send_json(200, response)

            def do_POST(self) -> None:  # noqa: N802
                registration = self._authorization()
                if (
                    registration is None
                    or registration["capability"] != "model.invoke"
                    or self.path
                    != "/api/module-capabilities/v1/model/invoke"
                ):
                    self._send_json(403, {"detail": "Capability denied"})
                    return
                try:
                    content_length = int(
                        self.headers.get("Content-Length", "0")
                    )
                    if not 0 < content_length <= 64 * 1024:
                        raise ValueError
                    payload = json.loads(self.rfile.read(content_length))
                except (ValueError, json.JSONDecodeError):
                    self._send_json(400, {"detail": "Invalid request"})
                    return
                if (
                    not isinstance(payload, dict)
                    or set(payload) != {"prompt"}
                    or not isinstance(payload["prompt"], str)
                    or not payload["prompt"]
                ):
                    self._send_json(400, {"detail": "Invalid request"})
                    return
                task_id = registration["task_id"]
                owner._record_call(task_id, "model.invoke")
                self._send_json(
                    200,
                    {
                        "task_id": task_id,
                        "content": "conformance model response",
                    },
                )

        try:
            self._server = ThreadingHTTPServer((host, port), Handler)
        except OSError as error:
            raise ConformanceError(
                f"cannot start capability stub: {error}"
            ) from error
        actual_port = self._server.server_address[1]
        advertised_host = (
            "127.0.0.1"
            if requested_base_url == "auto"
            else urlsplit(requested_base_url).hostname
        )
        self.base_url = f"http://{advertised_host}:{actual_port}"
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="module-capability-conformance-stub",
            daemon=True,
        )

    def __enter__(self) -> "CapabilityStub":
        self._thread.start()
        return self

    def __exit__(self, *_args: Any) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def _record_call(self, task_id: str, capability: str) -> None:
        with self._lock:
            self._calls.setdefault(task_id, set()).add(capability)

    def issue(
        self,
        task_id: str,
        capabilities: list[str],
    ) -> list[dict[str, Any]]:
        scopes = {
            "chat.read": {"chat_id": "conformance-chat"},
            "resource.read": {
                "resource_ids": ["conformance-resource"]
            },
            "resource.stream": {
                "resource_ids": ["conformance-stream-resource"]
            },
            "model.invoke": {"model_type": "chat"},
        }
        paths = {
            "chat.read": "/api/module-capabilities/v1/chat",
            "resource.read": (
                "/api/module-capabilities/v1/resources/{resource_id}"
            ),
            "resource.stream": (
                "/api/module-capabilities/v1/resource-stream/{resource_id}"
            ),
            "model.invoke": "/api/module-capabilities/v1/model/invoke",
        }
        expires_at = (
            datetime.now(timezone.utc) + timedelta(minutes=5)
        ).isoformat().replace("+00:00", "Z")
        envelopes = []
        for capability in capabilities:
            if capability not in scopes:
                raise ConformanceError(
                    f"unsupported fixture Host Capability: {capability}"
                )
            token = secrets.token_urlsafe(48)
            registration = {
                "task_id": task_id,
                "capability": capability,
                "scope": scopes[capability],
            }
            with self._lock:
                self._tokens[token] = registration
            envelopes.append(
                {
                    "capability": capability,
                    "endpoint": self.base_url + paths[capability],
                    "token": token,
                    "scope": scopes[capability],
                    "expires_at": expires_at,
                }
            )
        return envelopes

    def assert_used(
        self,
        task_id: str,
        expected: list[str],
    ) -> None:
        with self._lock:
            actual = self._calls.get(task_id, set()).copy()
        if actual != set(expected):
            raise ConformanceError(
                "Host Capability calls differ for task "
                f"{task_id}: expected {sorted(expected)}, "
                f"received {sorted(actual)}"
            )


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
    schema_files = sorted(CONTRACT_DIR.glob("*.schema.json"))
    if not schema_files:
        raise ConformanceError("no Module Protocol schemas were found")
    checked_schemas = []
    for path in schema_files:
        schema = _load_json(path)
        Draft202012Validator.check_schema(schema)
        checked_schemas.append(path.name)
    checked_manifests = [
        _validate_manifest_file(path)
        for path in (
            manifests
            or [REFERENCE_MANIFEST, REFERENCE_RESIDENT_MANIFEST]
        )
    ]
    fixture = _load_json(REFERENCE_FIXTURE)
    fixture_errors = list(
        Draft202012Validator(_load_json(FIXTURE_SCHEMA)).iter_errors(
            fixture
        )
    )
    if fixture_errors:
        raise ConformanceError(
            "reference conformance fixture does not match its schema"
        )
    return {
        "success": True,
        "schemas": checked_schemas,
        "manifests": checked_manifests,
        "fixtures": [str(REFERENCE_FIXTURE.resolve())],
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


def _pair_and_inspect(
    base_url: str,
    pairing_code: str,
    capability_base_url: str,
) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]:
    _, identity = _request_json(
        base_url,
        "/chatraw-module/v1/pair",
        method="POST",
        payload={
            "pairing_code": pairing_code,
            "host": {
                "product": "ChatRaw Server",
                "module_protocol": "1.0.0",
                "capability_base_url": capability_base_url,
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
    result = {
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
    return token, manifest, config, result


def probe_module(
    base_url: str,
    pairing_code: str,
    capability_base_url: str,
) -> dict[str, Any]:
    return _pair_and_inspect(
        base_url,
        pairing_code,
        capability_base_url,
    )[3]


def _request_bytes(
    base_url: str,
    path: str,
    *,
    token: str,
    max_bytes: int,
    method: str = "GET",
    range_header: str | None = None,
) -> tuple[int, dict[str, str], bytes]:
    headers = {
        "Accept": "application/octet-stream",
        "Authorization": f"Bearer {token}",
    }
    if range_header is not None:
        headers["Range"] = range_header
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise ConformanceError(
                    f"{path} response exceeds declared size"
                )
            return (
                response.status,
                {
                    name.lower(): value
                    for name, value in response.headers.items()
                },
                body,
            )
    except (urllib.error.URLError, TimeoutError) as error:
        raise ConformanceError(f"{path} request failed: {error}") from error


def _stream_task_case(
    base_url: str,
    token: str,
    task_id: str,
    case: dict[str, Any],
) -> list[dict[str, Any]]:
    path = f"/chatraw-module/v1/tasks/{task_id}/events"
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        headers={
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {token}",
            "Last-Event-ID": "0",
        },
    )
    events: list[dict[str, Any]] = []
    previous_id = 0
    fields: dict[str, str] = {}
    deadline = time.monotonic() + case.get("timeout_seconds", 30)
    try:
        with urllib.request.urlopen(
            request,
            timeout=case.get("timeout_seconds", 30),
        ) as response:
            while time.monotonic() < deadline:
                raw_line = response.readline()
                if not raw_line:
                    break
                line = raw_line.decode("utf-8").rstrip("\r\n")
                if line.startswith(":"):
                    continue
                if line:
                    name, separator, value = line.partition(":")
                    if separator:
                        fields[name] = value.lstrip()
                    continue
                if not fields:
                    continue
                try:
                    event = {
                        "id": int(fields["id"]),
                        "event": fields["event"],
                        "data": json.loads(fields["data"]),
                    }
                except (KeyError, ValueError, json.JSONDecodeError) as error:
                    raise ConformanceError(
                        f"{case['name']} returned malformed SSE"
                    ) from error
                fields = {}
                validate_task_event(
                    event,
                    previous_event_id=previous_id,
                )
                previous_id = event["id"]
                events.append(event)
                if (
                    event["event"] == "approval.requested"
                    and case["control"] in {"approve", "deny"}
                ):
                    _request_json(
                        base_url,
                        (
                            f"/chatraw-module/v1/tasks/{task_id}/approvals/"
                            f"{event['data']['approval_id']}"
                        ),
                        method="POST",
                        token=token,
                        payload={"decision": case["control"]},
                    )
                if event["event"] == "task.terminal":
                    return events
    except (urllib.error.URLError, TimeoutError) as error:
        raise ConformanceError(
            f"{case['name']} event stream failed: {error}"
        ) from error
    raise ConformanceError(
        f"{case['name']} event stream ended without task.terminal"
    )


def probe_tasks(
    base_url: str,
    pairing_code: str,
    capability_base_url: str,
    fixture_path: Path,
) -> dict[str, Any]:
    fixture = _load_json(fixture_path)
    errors = list(
        Draft202012Validator(_load_json(FIXTURE_SCHEMA)).iter_errors(
            fixture
        )
    )
    if errors:
        raise ConformanceError(
            "conformance fixture does not match Module Protocol v1"
        )
    with CapabilityStub(capability_base_url) as capability_stub:
        token, manifest, config, management = _pair_and_inspect(
            base_url,
            pairing_code,
            capability_stub.base_url,
        )
        fixture_capabilities = {
            capability
            for case in fixture["cases"]
            for capability in case.get("host_capabilities", [])
        }
        declared_capabilities = set(
            manifest["requested_host_capabilities"]
        )
        if fixture_capabilities != declared_capabilities:
            raise ConformanceError(
                "fixture Host Capability coverage must exactly match the "
                "manifest declaration"
            )
        actions = {
            action["action_id"]: action
            for action in manifest["actions"]
        }
        results = []
        for case in fixture["cases"]:
            action = actions.get(case["action_id"])
            if action is None:
                raise ConformanceError(
                    f"{case['name']} references an undeclared action"
                )
            task_id = str(uuid.uuid4())
            digest = hashlib.sha256(
                canonical_json(
                    {
                        "action_id": case["action_id"],
                        "input": case["input"],
                    }
                ).encode("utf-8")
            ).hexdigest()
            expected_capabilities = case.get("host_capabilities", [])
            status, summary = _request_json(
                base_url,
                "/chatraw-module/v1/tasks",
                method="POST",
                token=token,
                payload={
                    "task_id": task_id,
                    "request_digest": digest,
                    "action_id": case["action_id"],
                    "action_version": action["action_version"],
                    "config_revision": config["revision"],
                    "input": case["input"],
                    "active_skills": [],
                    "active_rules": [],
                    "host_capabilities": capability_stub.issue(
                        task_id,
                        expected_capabilities,
                    ),
                },
            )
            if status not in {200, 202}:
                raise ConformanceError(
                    f"{case['name']} task creation returned HTTP {status}"
                )
            validate_task_summary(
                summary,
                expected_task_id=task_id,
                expected_action_id=case["action_id"],
                expected_action_version=action["action_version"],
                expected_config_revision=config["revision"],
                output_schema=action["output_schema"],
            )
            if case["control"] == "cancel":
                _request_json(
                    base_url,
                    f"/chatraw-module/v1/tasks/{task_id}/cancel",
                    method="POST",
                    token=token,
                    payload={},
                )
            events = _stream_task_case(
                base_url,
                token,
                task_id,
                case,
            )
            _, final = _request_json(
                base_url,
                f"/chatraw-module/v1/tasks/{task_id}",
                token=token,
            )
            validate_task_summary(
                final,
                expected_task_id=task_id,
                expected_action_id=case["action_id"],
                expected_action_version=action["action_version"],
                expected_config_revision=config["revision"],
                output_schema=action["output_schema"],
            )
            if final["state"] != case["expected_terminal_state"]:
                raise ConformanceError(
                    f"{case['name']} ended in {final['state']}"
                )
            event_types = {event["event"] for event in events}
            missing = set(case["expected_events"]) - event_types
            if missing:
                raise ConformanceError(
                    f"{case['name']} missed events: {sorted(missing)}"
                )
            capability_stub.assert_used(
                task_id,
                expected_capabilities,
            )
            artifacts = final.get("artifacts", [])
            if case.get("expect_artifact"):
                if not artifacts:
                    raise ConformanceError(
                        f"{case['name']} did not produce an artifact"
                    )
                artifact = artifacts[0]
                artifact_status, headers, body = _request_bytes(
                    base_url,
                    (
                        f"/chatraw-module/v1/tasks/{task_id}/artifacts/"
                        f"{artifact['artifact_id']}"
                    ),
                    token=token,
                    max_bytes=artifact["size"],
                )
                content_type = headers.get(
                    "content-type", ""
                ).split(";", 1)[0]
                if (
                    artifact_status != 200
                    or len(body) != artifact["size"]
                    or content_type != artifact["media_type"]
                ):
                    raise ConformanceError(
                        f"{case['name']} returned an invalid artifact"
                    )
            resources = final.get("resources", [])
            if case.get("expect_resource"):
                if not resources:
                    raise ConformanceError(
                        f"{case['name']} did not produce a resource"
                    )
                resource = resources[0]
                resource_path = (
                    f"/chatraw-module/v1/tasks/{task_id}/resources/"
                    f"{resource['resource_id']}"
                )
                resource_status, headers, body = _request_bytes(
                    base_url,
                    resource_path,
                    token=token,
                    max_bytes=resource["size"],
                )
                content_type = headers.get(
                    "content-type", ""
                ).split(";", 1)[0]
                if (
                    resource_status != 200
                    or len(body) != resource["size"]
                    or content_type != resource["media_type"]
                    or headers.get("accept-ranges") != "bytes"
                ):
                    raise ConformanceError(
                        f"{case['name']} returned an invalid resource"
                    )
                head_status, head_headers, head_body = _request_bytes(
                    base_url,
                    resource_path,
                    token=token,
                    max_bytes=resource["size"],
                    method="HEAD",
                )
                if (
                    head_status != 200
                    or head_body
                    or head_headers.get("content-length")
                    != str(resource["size"])
                    or head_headers.get("accept-ranges") != "bytes"
                ):
                    raise ConformanceError(
                        f"{case['name']} returned invalid resource HEAD "
                        "metadata"
                    )
                if resource["size"] > 0:
                    range_status, range_headers, range_body = _request_bytes(
                        base_url,
                        resource_path,
                        token=token,
                        max_bytes=1,
                        range_header="bytes=0-0",
                    )
                    if (
                        range_status != 206
                        or len(range_body) != 1
                        or range_headers.get("content-length") != "1"
                        or range_headers.get("content-range")
                        != f"bytes 0-0/{resource['size']}"
                    ):
                        raise ConformanceError(
                            f"{case['name']} returned an invalid resource "
                            "Range response"
                        )
            results.append(
                {
                    "name": case["name"],
                    "task_id": task_id,
                    "state": final["state"],
                    "events": sorted(event_types),
                    "artifacts": len(artifacts),
                    "resources": len(resources),
                    "host_capabilities": expected_capabilities,
                }
            )
        return {
            **management,
            "fixture": str(fixture_path.resolve()),
            "capability_stub": capability_stub.base_url,
            "task_cases": results,
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
    probe.add_argument(
        "--capability-base-url",
        default="http://127.0.0.1:51111",
    )
    task_probe = commands.add_parser(
        "task-probe",
        help="consume a fresh pairing code and check management plus tasks",
    )
    task_probe.add_argument("--base-url", required=True)
    task_probe.add_argument("--pairing-code", required=True)
    task_probe.add_argument(
        "--capability-base-url",
        default="auto",
        help=(
            "auto, or a free loopback HTTP origin where task-probe may "
            "start its callback stub"
        ),
    )
    task_probe.add_argument("--fixture", type=Path, required=True)

    arguments = parser.parse_args()
    try:
        if arguments.command == "contracts":
            result = check_contracts(arguments.manifest)
        elif arguments.command == "manifest":
            result = {"success": True, **_validate_manifest_file(arguments.path)}
        elif arguments.command == "probe":
            result = probe_module(
                arguments.base_url,
                arguments.pairing_code,
                arguments.capability_base_url,
            )
        else:
            result = probe_tasks(
                arguments.base_url,
                arguments.pairing_code,
                arguments.capability_base_url,
                arguments.fixture,
            )
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
