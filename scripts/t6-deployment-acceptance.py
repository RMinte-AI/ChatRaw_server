#!/usr/bin/env python3
"""Black-box acceptance shared by source and Compose deployments."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from io import BytesIO
from pathlib import Path


TERMINAL_STATES = {"succeeded", "failed", "cancelled"}


class AcceptanceError(RuntimeError):
    pass


class Client:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies)
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        payload=None,
        headers=None,
        expected=(200,),
        body: bytes | None = None,
    ):
        request_headers = {
            "Origin": self.base_url,
            **(headers or {}),
        }
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            headers=request_headers,
            method=method,
        )
        try:
            response = self.opener.open(request, timeout=20)
            raw = response.read()
            status = response.status
            response_headers = response.headers
        except urllib.error.HTTPError as error:
            raw = error.read()
            status = error.code
            response_headers = error.headers
        if status not in expected:
            raise AcceptanceError(
                f"{method} {path} returned {status}: "
                f"{raw.decode('utf-8', errors='replace')}"
            )
        media_type = response_headers.get_content_type()
        if media_type == "application/json":
            return json.loads(raw or b"{}")
        return raw

    def open_stream(self, path: str):
        request = urllib.request.Request(
            self.base_url + path,
            headers={"Origin": self.base_url},
        )
        return self.opener.open(request, timeout=30)


def _plugin_archive(plugin_dir: Path) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path in sorted(plugin_dir.iterdir()):
            if path.is_file():
                archive.write(path, f"{plugin_dir.name}/{path.name}")
    return buffer.getvalue()


def _upload_plugin(client: Client, plugin_dir: Path) -> None:
    boundary = f"chatraw-t6-{uuid.uuid4().hex}"
    archive = _plugin_archive(plugin_dir)
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; '
        'filename="reference-module-companion.zip"\r\n'
        "Content-Type: application/zip\r\n\r\n"
    ).encode("ascii")
    body += archive + f"\r\n--{boundary}--\r\n".encode("ascii")
    result = client.request(
        "POST",
        "/api/plugins/upload",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        body=body,
    )
    if result.get("plugin_id") != "reference-module-companion":
        raise AcceptanceError("Reference companion plugin was not installed")


def _wait_task(client: Client, task_id: str, expected, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        task = client.request("GET", f"/api/module-tasks/{task_id}")
        if task["state"] in expected:
            return task
        time.sleep(0.1)
    raise AcceptanceError(
        f"Task {task_id} did not reach {sorted(expected)}"
    )


def _consume_sse(
    client: Client,
    task_id: str,
    *,
    approve: bool = False,
) -> set[str]:
    event_types: set[str] = set()
    current_event = None
    current_data = None
    with client.open_stream(
        f"/api/module-tasks/{task_id}/events"
    ) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").rstrip("\r\n")
            if line.startswith("event: "):
                current_event = line[7:]
            elif line.startswith("data: "):
                current_data = json.loads(line[6:])
            elif not line and current_event:
                event_types.add(current_event)
                if current_event == "approval.requested" and approve:
                    client.request(
                        "POST",
                        (
                            f"/api/module-tasks/{task_id}/approvals/"
                            f"{current_data['approval_id']}"
                        ),
                        payload={"decision": "approve"},
                    )
                if current_event == "task.terminal":
                    break
                current_event = None
                current_data = None
    return event_types


def _create_task(client: Client, text: str, **options):
    return client.request(
        "POST",
        "/api/module-tasks",
        payload={
            "module_id": "chatraw.reference.echo",
            "action_id": "echo.task",
            "input": {"text": text, **options},
        },
        headers={"Idempotency-Key": f"t6-{uuid.uuid4().hex}"},
        expected=(200, 202),
    )


def _assert_bad_module_credential(module_base_url: str) -> None:
    request = urllib.request.Request(
        module_base_url.rstrip("/") + "/chatraw-module/v1/manifest",
        headers={"Authorization": "Bearer invalid-t6-credential"},
    )
    try:
        urllib.request.urlopen(request, timeout=5)
    except urllib.error.HTTPError as error:
        if error.code == 401:
            return
        raise
    raise AcceptanceError("Module accepted an invalid credential")


def bootstrap(arguments) -> None:
    print("T6 bootstrap: setup and login", flush=True)
    client = Client(arguments.server_base_url)
    client.request(
        "POST",
        "/api/setup/admin",
        payload={
            "setup_token": arguments.setup_token,
            "username": arguments.username,
            "password": arguments.password,
        },
    )
    client.request(
        "POST",
        "/api/auth/login",
        payload={
            "username": arguments.username,
            "password": arguments.password,
        },
    )
    deployment = client.request("GET", "/api/admin/deployment-status")
    if deployment["mode"] == "compose":
        rejected = client.request(
            "POST",
            "/api/admin/modules/pair",
            payload={
                "base_url": "http://127.0.0.1:8765",
                "pairing_code": arguments.pairing_code,
            },
            expected=(400,),
        )
        if (
            rejected.get("code")
            != "module_loopback_unreachable_from_container"
        ):
            raise AcceptanceError(
                "Compose did not reject a loopback module address clearly"
            )
        saved_model = client.request(
            "POST",
            "/api/models",
            payload={
                "id": "",
                "name": "T6 legacy loopback model",
                "api_url": "http://127.0.0.1:1234/v1",
                "model_id": "t6-model",
                "context_length": 8192,
                "max_output": 4096,
                "type": "chat",
                "capability": {
                    "vision": False,
                    "reasoning": False,
                    "tools": False,
                },
                "api_key_action": "preserve",
            },
        )
        deployment = client.request(
            "GET",
            "/api/admin/deployment-status",
        )
        if not any(
            warning["code"]
            == "model_loopback_unreachable_from_container"
            for warning in deployment["warnings"]
        ):
            raise AcceptanceError(
                "Compose did not provide the loopback model repair prompt"
            )
        models = client.request("GET", "/api/models")
        stored_model = next(
            item for item in models if item["id"] == saved_model["id"]
        )
        if stored_model["api_url"] != "http://127.0.0.1:1234/v1":
            raise AcceptanceError(
                "Compose silently rewrote the loopback model address"
            )
        print(
            "T6 bootstrap: Compose loopback repair policy verified",
            flush=True,
        )
    _upload_plugin(client, arguments.plugin_dir)
    print("T6 bootstrap: plugin installed", flush=True)
    paired = client.request(
        "POST",
        "/api/admin/modules/pair",
        payload={
            "base_url": arguments.module_base_url,
            "pairing_code": arguments.pairing_code,
        },
        expected=(201,),
    )
    registration_id = paired["id"]
    print("T6 bootstrap: module paired", flush=True)
    client.request(
        "POST",
        f"/api/admin/modules/{registration_id}/approve",
        payload={
            "manifest_digest": paired["manifest_digest"],
            "approved_capabilities": paired[
                "requested_host_capabilities"
            ],
        },
    )
    config = client.request(
        "GET",
        f"/api/admin/modules/{registration_id}/config",
    )
    client.request(
        "PUT",
        f"/api/admin/modules/{registration_id}/config",
        payload={
            "revision": config["revision"],
            "values": {"greeting": "T6", "uppercase": False},
            "secrets": {"service_key": {"action": "keep"}},
        },
    )
    checked = client.request(
        "POST",
        f"/api/admin/modules/{registration_id}/check",
    )
    if (
        checked["health_status"] != "healthy"
        or checked["ready_status"] != "ready"
    ):
        raise AcceptanceError("Reference module is not healthy and ready")
    client.request(
        "POST",
        f"/api/admin/modules/{registration_id}/enable",
    )
    print("T6 bootstrap: module configured and enabled", flush=True)

    artifact_task = _create_task(
        client,
        "artifact",
        steps=12,
        delay_ms=5,
        create_artifact=True,
    )
    events = _consume_sse(client, artifact_task["task_id"])
    print("T6 bootstrap: artifact task SSE completed", flush=True)
    required_events = {
        "task.status",
        "task.progress",
        "output.delta",
        "task.terminal",
    }
    if not required_events.issubset(events):
        raise AcceptanceError(
            f"SSE event coverage is incomplete: {sorted(events)}"
        )
    artifact_task = _wait_task(
        client,
        artifact_task["task_id"],
        {"succeeded"},
    )
    artifact = artifact_task["artifacts"][0]
    downloaded = client.request(
        "GET",
        (
            f"/api/module-tasks/{artifact_task['task_id']}/artifacts/"
            f"{artifact['artifact_ref']}"
        ),
    )
    if downloaded != b"T6: artifact":
        raise AcceptanceError("Artifact content did not round-trip")

    approval_task = _create_task(
        client,
        "approval",
        steps=8,
        delay_ms=5,
        require_approval=True,
    )
    approval_events = _consume_sse(
        client,
        approval_task["task_id"],
        approve=True,
    )
    print("T6 bootstrap: approval task completed", flush=True)
    if not {
        "approval.requested",
        "approval.resolved",
        "task.terminal",
    }.issubset(approval_events):
        raise AcceptanceError("Approval did not round-trip through SSE")
    _wait_task(client, approval_task["task_id"], {"succeeded"})

    cancel_task = _create_task(
        client,
        "cancel",
        steps=200,
        delay_ms=20,
    )
    client.request(
        "POST",
        f"/api/module-tasks/{cancel_task['task_id']}/cancel",
        payload={},
        expected=(202,),
    )
    _wait_task(client, cancel_task["task_id"], {"cancelled", "succeeded"})
    print("T6 bootstrap: cancellation completed", flush=True)

    if arguments.module_probe_base_url:
        _assert_bad_module_credential(arguments.module_probe_base_url)
    arguments.state_file.write_text(
        json.dumps(
            {
                "registration_id": registration_id,
                "artifact_task_id": artifact_task["task_id"],
                "artifact_ref": artifact["artifact_ref"],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    print("T6 bootstrap acceptance passed")


def resume(arguments) -> None:
    print("T6 resume: login and recovery checks", flush=True)
    state = json.loads(arguments.state_file.read_text(encoding="utf-8"))
    client = Client(arguments.server_base_url)
    client.request(
        "POST",
        "/api/auth/login",
        payload={
            "username": arguments.username,
            "password": arguments.password,
        },
    )
    checked = client.request(
        "POST",
        f"/api/admin/modules/{state['registration_id']}/check",
    )
    if (
        checked["health_status"] != "healthy"
        or checked["ready_status"] != "ready"
        or checked["lifecycle_state"] != "enabled"
    ):
        raise AcceptanceError("Module registration did not survive restart")
    task = client.request(
        "GET",
        f"/api/module-tasks/{state['artifact_task_id']}",
    )
    if task["state"] != "succeeded":
        raise AcceptanceError("Task did not survive restart")
    downloaded = client.request(
        "GET",
        (
            f"/api/module-tasks/{state['artifact_task_id']}/artifacts/"
            f"{state['artifact_ref']}"
        ),
    )
    if downloaded != b"T6: artifact":
        raise AcceptanceError("Artifact did not survive restart")
    if arguments.module_probe_base_url:
        _assert_bad_module_credential(arguments.module_probe_base_url)
    print("T6 restart recovery acceptance passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("bootstrap", "resume"))
    parser.add_argument("--server-base-url", required=True)
    parser.add_argument("--module-base-url", required=True)
    parser.add_argument("--module-probe-base-url", default="")
    parser.add_argument("--setup-token", default="")
    parser.add_argument("--pairing-code", default="")
    parser.add_argument("--username", default="t6-admin")
    parser.add_argument("--password", default="T6-acceptance-password-2026")
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument(
        "--plugin-dir",
        type=Path,
        default=Path(
            "Plugins/Plugin_market/reference-module-companion"
        ),
    )
    arguments = parser.parse_args()
    if arguments.phase == "bootstrap":
        if not arguments.setup_token or not arguments.pairing_code:
            parser.error("bootstrap requires setup and pairing tokens")
        bootstrap(arguments)
    else:
        resume(arguments)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
