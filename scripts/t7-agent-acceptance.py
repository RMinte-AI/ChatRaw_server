#!/usr/bin/env python3
"""Cross-repository black-box acceptance for Agent as a real module."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from io import BytesIO
from pathlib import Path


TERMINAL_STATES = {"succeeded", "failed", "cancelled"}
MODULE_ID = "chatraw.agent"
ACTION_ID = "agent.chat"


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
            response = self.opener.open(request, timeout=30)
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
        if response_headers.get_content_type() == "application/json":
            return json.loads(raw or b"{}")
        return raw


def _login(base_url: str, username: str, password: str) -> Client:
    client = Client(base_url)
    client.request(
        "POST",
        "/api/auth/login",
        payload={"username": username, "password": password},
    )
    return client


def _plugin_archive(
    plugin_dir: Path,
    *,
    version: str | None = None,
) -> bytes:
    buffer = BytesIO()
    manifest = json.loads(
        (plugin_dir / "manifest.json").read_text(encoding="utf-8")
    )
    if version is not None:
        manifest["version"] = version
    with zipfile.ZipFile(buffer, "w") as archive:
        root = plugin_dir.name
        for path in sorted(plugin_dir.iterdir()):
            if not path.is_file():
                continue
            if path.name == "manifest.json":
                archive.writestr(
                    f"{root}/manifest.json",
                    json.dumps(manifest, ensure_ascii=False),
                )
            else:
                archive.write(path, f"{root}/{path.name}")
    return buffer.getvalue()


def _upload_plugin(
    client: Client,
    plugin_dir: Path,
    *,
    version: str | None = None,
) -> None:
    boundary = f"chatraw-t7-{uuid.uuid4().hex}"
    archive = _plugin_archive(plugin_dir, version=version)
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; '
        'filename="chatraw-linkdb-agent.zip"\r\n'
        "Content-Type: application/zip\r\n\r\n"
    ).encode("ascii")
    body += archive + f"\r\n--{boundary}--\r\n".encode("ascii")
    result = client.request(
        "POST",
        "/api/plugins/upload",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}"
        },
        body=body,
    )
    if result.get("plugin_id") != "chatraw-linkdb-agent":
        raise AcceptanceError("Agent companion plugin was not installed")


def _wait_task(
    client: Client,
    task_id: str,
    *,
    expected=TERMINAL_STATES,
    timeout: float = 40,
):
    deadline = time.time() + timeout
    while time.time() < deadline:
        task = client.request("GET", f"/api/module-tasks/{task_id}")
        if task["state"] in expected:
            return task
        time.sleep(0.1)
    raise AcceptanceError(
        f"Task {task_id} did not reach {sorted(expected)}"
    )


def _start_task(
    client: Client,
    chat_id: str,
    message: str,
):
    return client.request(
        "POST",
        "/api/module-tasks",
        payload={
            "module_id": MODULE_ID,
            "action_id": ACTION_ID,
            "input": {
                "message": message,
                "polish": False,
                "model_timeout_seconds": 180,
                "tool_timeout_seconds": 120,
                "request_deadline_seconds": 300,
                "max_agent_turns": 12,
                "max_plan_steps": 8,
                "max_tool_calls": 32,
                "max_parallel_tools": 2,
            },
            "chat_id": chat_id,
            "user_message": message,
        },
        headers={"Idempotency-Key": f"t7-{uuid.uuid4().hex}"},
        expected=(200, 202),
    )


def _assert_no_private_data(payload) -> None:
    encoded = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in (
        "fixture-secret-must-not-leak",
        "t7-customer-fixture-token",
        "linkdb_token",
        "linkdb_base_url",
        "/agent/resolve",
        "/agent/invoke",
        "authorization",
        "bearer ",
    ):
        if forbidden in encoded:
            raise AcceptanceError(
                f"Public response leaked private marker: {forbidden}"
            )


def bootstrap(arguments) -> None:
    admin = Client(arguments.server_base_url)
    admin.request(
        "POST",
        "/api/setup/admin",
        payload={
            "setup_token": arguments.setup_token,
            "username": "t7admin",
            "password": "t7-admin-password-strong-2026",
        },
    )
    admin.request(
        "POST",
        "/api/auth/login",
        payload={
            "username": "t7admin",
            "password": "t7-admin-password-strong-2026",
        },
    )
    admin.request(
        "POST",
        "/api/models",
        payload={
            "id": "default-chat",
            "name": "T7 deterministic chat model",
            "api_url": arguments.model_base_url.rstrip("/") + "/v1",
            "model_id": "t7-model",
            "context_length": 32768,
            "max_output": 4096,
            "type": "chat",
            "capability": {
                "vision": False,
                "reasoning": False,
                "tools": True,
            },
            "api_key_action": "clear",
        },
    )
    paired = admin.request(
        "POST",
        "/api/admin/modules/pair",
        payload={
            "base_url": arguments.module_base_url,
            "pairing_code": arguments.pairing_code,
        },
        expected=(201,),
    )
    if paired["feature_suite"]["status"] != "plugin_missing":
        raise AcceptanceError("Missing companion plugin was not diagnosed")
    registration_id = paired["id"]
    admin.request(
        "POST",
        f"/api/admin/modules/{registration_id}/approve",
        payload={
            "manifest_digest": paired["manifest_digest"],
            "approved_capabilities": [
                "chat.read",
                "model.chat.completions",
                "skill.read",
                "rule.read",
                "resource.stream",
            ],
        },
    )

    _upload_plugin(admin, arguments.plugin_dir, version="1.0.0")
    incompatible = admin.request(
        "POST",
        f"/api/admin/modules/{registration_id}/check",
    )
    if incompatible["feature_suite"]["status"] != "plugin_incompatible":
        raise AcceptanceError(
            "Incompatible companion plugin was not diagnosed"
        )
    _upload_plugin(admin, arguments.plugin_dir)
    config = admin.request(
        "GET",
        f"/api/admin/modules/{registration_id}/config",
    )
    admin.request(
        "PUT",
        f"/api/admin/modules/{registration_id}/config",
        payload={
            "revision": config["revision"],
            "values": {},
            "secrets": {},
        },
    )
    checked = admin.request(
        "POST",
        f"/api/admin/modules/{registration_id}/check",
    )
    if (
        checked["health_status"] != "healthy"
        or checked["ready_status"] != "ready"
        or checked["feature_suite"]["status"] != "ready"
    ):
        raise AcceptanceError("Agent feature suite is not ready")
    admin.request(
        "POST",
        f"/api/admin/modules/{registration_id}/enable",
    )

    members = {}
    for suffix in ("one", "two"):
        username = f"t7member{suffix}"
        password = f"t7-member-{suffix}-password-2026"
        created = admin.request(
            "POST",
            "/api/admin/users",
            payload={
                "username": username,
                "password": password,
                "role": "member",
            },
        )
        members[suffix] = {
            "username": username,
            "password": password,
            "id": created["user"]["id"],
        }
    member_one = _login(
        arguments.server_base_url,
        members["one"]["username"],
        members["one"]["password"],
    )
    member_two = _login(
        arguments.server_base_url,
        members["two"]["username"],
        members["two"]["password"],
    )
    chat = member_one.request("POST", "/api/chats")
    first = _wait_task(
        member_one,
        _start_task(
            member_one,
            chat["id"],
            (
                "查询苏A12345在 2026-07-02 00:00:00 至 "
                "2026-07-03 00:00:00 的出口流水"
            ),
        )["task_id"],
    )
    if (
        first["state"] != "succeeded"
        or not isinstance(first.get("result"), dict)
        or "12.5" not in first["result"].get("answer", "")
    ):
        raise AcceptanceError(
            "Native Tool Calling did not reach real LinkDB: "
            + json.dumps(first, ensure_ascii=False, sort_keys=True)
        )
    second = _wait_task(
        member_two,
        _start_task(
            member_two,
            chat["id"],
            "刚才两条流水的总金额是多少？",
        )["task_id"],
    )
    if (
        second["state"] != "succeeded"
        or not isinstance(second.get("result"), dict)
        or "30.5" not in second["result"].get("answer", "")
    ):
        raise AcceptanceError(
            "Server-backed Agent chat history did not continue: "
            + json.dumps(second, ensure_ascii=False, sort_keys=True)
        )
    artifact_task = _wait_task(
        member_one,
        _start_task(
            member_one,
            chat["id"],
            "T7_CREATE_DOCX_ARTIFACT",
        )["task_id"],
    )
    artifacts = artifact_task.get("artifacts")
    if (
        artifact_task["state"] != "succeeded"
        or not isinstance(artifacts, list)
        or len(artifacts) != 1
        or artifacts[0].get("filename") != "t7-report.docx"
        or artifacts[0].get("media_type")
        != (
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        )
    ):
        raise AcceptanceError(
            "DOCX artifact did not reach Server: "
            + json.dumps(
                artifact_task,
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    downloaded_artifact = member_one.request(
        "GET",
        (
            f"/api/module-tasks/{artifact_task['task_id']}/artifacts/"
            f"{artifacts[0]['artifact_ref']}"
        ),
    )
    if not downloaded_artifact.startswith(b"PK"):
        raise AcceptanceError("DOCX artifact download is invalid")
    shared_view = member_one.request(
        "GET",
        f"/api/module-tasks/{second['task_id']}",
    )
    if shared_view["is_creator"] or shared_view["can_control"]:
        raise AcceptanceError("Shared task control permissions are incorrect")
    if member_one.request(
        "GET",
        "/api/admin/modules",
        expected=(403,),
    ).get("detail") is None:
        raise AcceptanceError("Member module administration was not denied")
    if member_one.request(
        "POST",
        f"/api/admin/modules/{registration_id}/disable",
        payload={},
        expected=(403,),
    ).get("detail") is None:
        raise AcceptanceError("Member module disable was not denied")

    messages = member_two.request(
        "GET",
        f"/api/chats/{chat['id']}/messages",
    )
    _assert_no_private_data(
        {
            "first": first,
            "second": second,
            "messages": messages,
            "feature": member_two.request(
                "GET",
                f"/api/module-features/{MODULE_ID}",
            ),
        }
    )
    audit = admin.request("GET", "/api/admin/audit?limit=500")["items"]
    task_creators = {
        item["actor_user_id"]
        for item in audit
        if item["action"] == "module.task.create"
        and item["outcome"] == "success"
    }
    if not {members["one"]["id"], members["two"]["id"]}.issubset(
        task_creators
    ):
        raise AcceptanceError("Agent task actors were not audited")

    recovery_chat = member_one.request("POST", "/api/chats")
    state = {
        "registration_id": registration_id,
        "members": members,
        "shared_chat_id": chat["id"],
        "recovery_chat_id": recovery_chat["id"],
        "first_task_id": first["task_id"],
        "second_task_id": second["task_id"],
        "artifact_task_id": artifact_task["task_id"],
    }
    arguments.state_file.write_text(
        json.dumps(state, ensure_ascii=False),
        encoding="utf-8",
    )
    os.chmod(arguments.state_file, 0o600)
    print("T7 bootstrap passed", flush=True)


def start_recovery(arguments) -> None:
    state = json.loads(arguments.state_file.read_text(encoding="utf-8"))
    member = _login(
        arguments.server_base_url,
        state["members"]["one"]["username"],
        state["members"]["one"]["password"],
    )
    task = _start_task(
        member,
        state["recovery_chat_id"],
        (
            "查询苏A99999在 2026-07-02 00:00:00 至 "
            "2026-07-03 00:00:00 的出口流水"
        ),
    )
    state["recovery_task_id"] = task["task_id"]
    arguments.state_file.write_text(
        json.dumps(state, ensure_ascii=False),
        encoding="utf-8",
    )
    os.chmod(arguments.state_file, 0o600)
    print("T7 recovery task started", flush=True)


def resume(arguments) -> None:
    state = json.loads(arguments.state_file.read_text(encoding="utf-8"))
    member = _login(
        arguments.server_base_url,
        state["members"]["one"]["username"],
        state["members"]["one"]["password"],
    )
    task = _wait_task(
        member,
        state["recovery_task_id"],
        timeout=60,
    )
    if task["state"] != "succeeded" or "苏A99999" not in task[
        "result"
    ]["answer"]:
        raise AcceptanceError("Agent task did not recover after restart")
    events = member.request(
        "GET",
        f"/api/module-tasks/{task['task_id']}/events",
        headers={"Last-Event-ID": "0"},
    ).decode("utf-8")
    event_ids = [
        int(line[4:])
        for line in events.splitlines()
        if line.startswith("id: ")
    ]
    if not event_ids or event_ids != sorted(set(event_ids)):
        raise AcceptanceError("Recovered Agent event cursors are invalid")
    _assert_no_private_data({"task": task, "events": events})
    print("T7 restart recovery passed", flush=True)


def agent_offline(arguments) -> None:
    state = json.loads(arguments.state_file.read_text(encoding="utf-8"))
    admin = _login(
        arguments.server_base_url,
        "t7admin",
        "t7-admin-password-strong-2026",
    )
    checked = admin.request(
        "POST",
        f"/api/admin/modules/{state['registration_id']}/check",
    )
    if checked["health_status"] == "healthy":
        raise AcceptanceError("Offline Agent was reported healthy")
    member = _login(
        arguments.server_base_url,
        state["members"]["one"]["username"],
        state["members"]["one"]["password"],
    )
    feature = member.request(
        "GET",
        f"/api/module-features/{MODULE_ID}",
    )
    if feature["available"]:
        raise AcceptanceError("Offline Agent feature remained available")
    member.request("POST", "/api/chats")
    print("T7 Agent offline diagnosis passed", flush=True)


def linkdb_offline(arguments) -> None:
    state = json.loads(arguments.state_file.read_text(encoding="utf-8"))
    admin = _login(
        arguments.server_base_url,
        "t7admin",
        "t7-admin-password-strong-2026",
    )
    checked = admin.request(
        "POST",
        f"/api/admin/modules/{state['registration_id']}/check",
    )
    if (
        checked["health_status"] != "healthy"
        or checked["ready_status"] == "ready"
    ):
        raise AcceptanceError("LinkDB outage was not isolated to readiness")
    member = _login(
        arguments.server_base_url,
        state["members"]["two"]["username"],
        state["members"]["two"]["password"],
    )
    rejected = member.request(
        "POST",
        "/api/module-tasks",
        payload={
            "module_id": MODULE_ID,
            "action_id": ACTION_ID,
            "input": {"message": "must not run"},
        },
        headers={"Idempotency-Key": f"t7-{uuid.uuid4().hex}"},
        expected=(409, 503),
    )
    if not rejected.get("code"):
        raise AcceptanceError("Unavailable Agent task was not diagnosed")
    member.request("POST", "/api/chats")
    admin.request(
        "POST",
        f"/api/admin/modules/{state['registration_id']}/disable",
    )
    feature = member.request(
        "GET",
        f"/api/module-features/{MODULE_ID}",
    )
    if feature["available"]:
        raise AcceptanceError("Disabled Agent feature remained available")
    print("T7 LinkDB offline and disable diagnosis passed", flush=True)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    subcommands = result.add_subparsers(dest="command", required=True)
    for name in (
        "bootstrap",
        "start-recovery",
        "resume",
        "agent-offline",
        "linkdb-offline",
    ):
        command = subcommands.add_parser(name)
        command.add_argument("--server-base-url", required=True)
        command.add_argument("--state-file", type=Path, required=True)
        if name == "bootstrap":
            command.add_argument("--module-base-url", required=True)
            command.add_argument("--setup-token", required=True)
            command.add_argument("--pairing-code", required=True)
            command.add_argument("--plugin-dir", type=Path, required=True)
            command.add_argument("--model-base-url", required=True)
    return result


def main() -> int:
    arguments = parser().parse_args()
    {
        "bootstrap": bootstrap,
        "start-recovery": start_recovery,
        "resume": resume,
        "agent-offline": agent_offline,
        "linkdb-offline": linkdb_offline,
    }[arguments.command](arguments)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
