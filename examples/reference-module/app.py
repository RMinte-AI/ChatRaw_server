"""Independent, durable reference implementation of Module Protocol v1."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import secrets
import tempfile
import threading
import time
import urllib.request
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse


ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(
    os.environ.get(
        "REFERENCE_MODULE_DATA_DIR",
        str(ROOT / "reference-module-data"),
    )
).resolve()
STATE_FILE = DATA_DIR / "state.json"
FRONTEND_MODE = os.environ.get(
    "REFERENCE_MODULE_FRONTEND_MODE",
    "plugin",
).strip()
MANIFEST_FILES = {
    "plugin": ROOT / "manifest.example.json",
    "resident": ROOT / "manifest.resident.example.json",
}
if FRONTEND_MODE not in MANIFEST_FILES:
    raise RuntimeError(
        "REFERENCE_MODULE_FRONTEND_MODE must be plugin or resident"
    )
MANIFEST_FILE = MANIFEST_FILES[FRONTEND_MODE]
PAIRING_TTL_SECONDS = int(
    os.environ.get("REFERENCE_MODULE_PAIRING_TTL_SECONDS", "600")
)
MODULE_ID = "chatraw.reference.echo"
INSTANCE_ID = os.environ.get(
    "REFERENCE_MODULE_INSTANCE_ID",
    str(uuid.uuid4()),
)
TASK_PREFIX = "/chatraw-module/v1/tasks"
TERMINAL_STATES = {"succeeded", "failed", "cancelled"}
STATE_LOCK = threading.RLock()
WORKERS: dict[str, asyncio.Task] = {}
APPROVAL_MONITORS: dict[str, asyncio.Task] = {}
NOTIFIERS: dict[str, asyncio.Condition] = {}
MAX_RETAINED_EVENTS = 40
PRIVATE_HEALTH_URL = os.environ.get(
    "REFERENCE_MODULE_PRIVATE_HEALTH_URL",
    "",
).strip()


class HostCapabilityError(RuntimeError):
    """A declared ChatRaw host callback could not be used safely."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _private_dependency_healthy() -> bool:
    if not PRIVATE_HEALTH_URL:
        return True
    try:
        with urllib.request.urlopen(PRIVATE_HEALTH_URL, timeout=2) as response:
            payload = json.load(response)
        return (
            response.status == 200
            and payload == {"status": "healthy"}
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def _read_capability_json(
    endpoint: str,
    token: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = None
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        endpoint,
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read(512 * 1024 + 1)
            if response.status != 200 or len(body) > 512 * 1024:
                raise HostCapabilityError("Host capability response is invalid")
            result = json.loads(body)
    except (OSError, ValueError, json.JSONDecodeError):
        raise HostCapabilityError(
            "Host capability request failed"
        ) from None
    if not isinstance(result, dict):
        raise HostCapabilityError("Host capability response is invalid")
    return result


def _exercise_host_capabilities(
    task_id: str,
    capabilities: list[dict[str, Any]],
) -> None:
    if not capabilities:
        raise HostCapabilityError("No Host Capability was provided")
    seen: set[str] = set()
    required_fields = {
        "capability",
        "endpoint",
        "token",
        "scope",
        "expires_at",
    }
    for envelope in capabilities:
        if (
            not isinstance(envelope, dict)
            or set(envelope) != required_fields
            or not isinstance(envelope.get("capability"), str)
            or envelope["capability"] in seen
            or not isinstance(envelope.get("endpoint"), str)
            or not isinstance(envelope.get("token"), str)
            or len(envelope["token"]) < 32
            or not isinstance(envelope.get("scope"), dict)
            or not isinstance(envelope.get("expires_at"), str)
        ):
            raise HostCapabilityError("Host capability envelope is invalid")
        capability = envelope["capability"]
        seen.add(capability)
        endpoint = envelope["endpoint"]
        parsed = urlsplit(endpoint)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise HostCapabilityError("Host capability endpoint is invalid")
        if capability == "chat.read":
            response = _read_capability_json(endpoint, envelope["token"])
            if (
                response.get("task_id") != task_id
                or not isinstance(response.get("conversation_ref"), str)
                or not isinstance(response.get("actor_ref"), str)
                or not isinstance(response.get("messages"), list)
            ):
                raise HostCapabilityError(
                    "chat.read response is invalid"
                )
        elif capability == "resource.read":
            resource_ids = envelope["scope"].get("resource_ids")
            if (
                not isinstance(resource_ids, list)
                or not resource_ids
                or not all(
                    isinstance(resource_id, str) and resource_id
                    for resource_id in resource_ids
                )
                or "{resource_id}" not in endpoint
            ):
                raise HostCapabilityError(
                    "resource.read scope is invalid"
                )
            resource_id = resource_ids[0]
            response = _read_capability_json(
                endpoint.replace(
                    "{resource_id}",
                    quote(resource_id, safe=""),
                ),
                envelope["token"],
            )
            resource = response.get("resource")
            if (
                response.get("task_id") != task_id
                or not isinstance(resource, dict)
                or resource.get("id") != resource_id
                or not isinstance(resource.get("content"), str)
            ):
                raise HostCapabilityError(
                    "resource.read response is invalid"
                )
        elif capability == "model.invoke":
            response = _read_capability_json(
                endpoint,
                envelope["token"],
                method="POST",
                payload={"prompt": "Reference module capability check"},
            )
            if (
                response.get("task_id") != task_id
                or not isinstance(response.get("content"), str)
            ):
                raise HostCapabilityError(
                    "model.invoke response is invalid"
                )
        else:
            raise HostCapabilityError("Host capability is unsupported")


def _default_state() -> dict[str, Any]:
    return {
        "revision": 1,
        "values": {
            "greeting": "Hello",
            "uppercase": False,
        },
        "secret_digest": None,
        "access_token_digest": None,
        "consumed_pairing_code_digest": None,
        "tasks": {},
    }


def _read_state_unlocked() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return _default_state()
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise RuntimeError("Reference module state is invalid") from None
    required = {
        "revision",
        "values",
        "secret_digest",
        "access_token_digest",
        "consumed_pairing_code_digest",
        "tasks",
    }
    legacy_required = required - {"tasks"}
    if isinstance(state, dict) and set(state) == legacy_required:
        state["tasks"] = {}
    if (
        not isinstance(state, dict)
        or set(state) != required
        or not isinstance(state["tasks"], dict)
    ):
        raise RuntimeError("Reference module state is invalid")
    for task in state["tasks"].values():
        if isinstance(task, dict):
            task.setdefault("approval_completed", False)
            task.setdefault("next_step", 0)
    return state


def _read_state() -> dict[str, Any]:
    with STATE_LOCK:
        return _read_state_unlocked()


def _write_state_unlocked(state: dict[str, Any]) -> None:
    DATA_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(DATA_DIR, 0o700)
    fd, raw_path = tempfile.mkstemp(prefix=".state.", dir=DATA_DIR)
    temporary_path = Path(raw_path)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as state_file:
            json.dump(
                state,
                state_file,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            state_file.flush()
            os.fsync(state_file.fileno())
        os.replace(temporary_path, STATE_FILE)
        os.chmod(STATE_FILE, 0o600)
    finally:
        temporary_path.unlink(missing_ok=True)


def _write_state(state: dict[str, Any]) -> None:
    with STATE_LOCK:
        _write_state_unlocked(state)


def _config_view(state: dict[str, Any]) -> dict[str, Any]:
    greeting = state["values"].get("greeting")
    configured = isinstance(greeting, str) and bool(greeting.strip())
    return {
        "revision": str(state["revision"]),
        "values": dict(state["values"]),
        "secret_configured": {
            "service_key": bool(state["secret_digest"]),
        },
        "configured": configured,
        "missing_required": [] if configured else ["greeting"],
    }


PAIRING_CODE = os.environ.get("REFERENCE_MODULE_PAIRING_CODE", "")
if not 16 <= len(PAIRING_CODE) <= 4096:
    raise RuntimeError(
        "REFERENCE_MODULE_PAIRING_CODE must contain 16 to 4096 characters"
    )
PAIRING_CODE_DIGEST = _digest(PAIRING_CODE)
PAIRING_EXPIRES_AT = time.time() + PAIRING_TTL_SECONDS

DATA_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
os.chmod(DATA_DIR, 0o700)
if not STATE_FILE.exists():
    _write_state(_default_state())
else:
    _write_state(_read_state())

with MANIFEST_FILE.open("r", encoding="utf-8") as manifest_file:
    MANIFEST = json.load(manifest_file)


def _require_access(authorization: str | None) -> dict[str, Any]:
    if (
        not authorization
        or not authorization.startswith("Bearer ")
        or len(authorization) > 5000
    ):
        raise HTTPException(status_code=401, detail="Authentication required")
    token = authorization[7:]
    state = _read_state()
    expected = state["access_token_digest"]
    if not expected or not secrets.compare_digest(_digest(token), expected):
        raise HTTPException(status_code=401, detail="Authentication required")
    return state


def _task_or_404(state: dict[str, Any], task_id: str) -> dict[str, Any]:
    task = state["tasks"].get(task_id)
    if not isinstance(task, dict):
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _artifact_metadata(task: dict[str, Any]) -> list[dict[str, Any]]:
    return [
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


def _task_summary(task: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "task_id": task["task_id"],
        "action_id": task["action_id"],
        "action_version": task["action_version"],
        "config_revision": task["config_revision"],
        "state": task["state"],
        "last_event_id": task["last_event_id"],
        "artifacts": _artifact_metadata(task),
    }
    if task.get("outcome_code"):
        summary["outcome_code"] = task["outcome_code"]
    if task["state"] == "succeeded":
        summary["result"] = task["result"]
        summary["chat_projection"] = task["chat_projection"]
    return summary


async def _notify(task_id: str) -> None:
    condition = NOTIFIERS.setdefault(task_id, asyncio.Condition())
    async with condition:
        condition.notify_all()


def _append_event_unlocked(
    state: dict[str, Any],
    task: dict[str, Any],
    event_name: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    task["last_event_id"] += 1
    event = {
        "id": task["last_event_id"],
        "event": event_name,
        "data": data,
    }
    task["events"].append(event)
    if len(task["events"]) > MAX_RETAINED_EVENTS:
        task["last_event_id"] += 1
        snapshot = {
            "id": task["last_event_id"],
            "event": "output.snapshot",
            "data": {
                "text": task["output"],
                "compacted_through": event["id"],
            },
        }
        task["events"] = [snapshot]
    task["updated_at"] = _utc_now()
    _write_state_unlocked(state)
    return event


async def _append_event(
    task_id: str,
    event_name: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    with STATE_LOCK:
        state = _read_state_unlocked()
        task = _task_or_404(state, task_id)
        event = _append_event_unlocked(state, task, event_name, data)
    await _notify(task_id)
    return event


async def _set_state(
    task_id: str,
    task_state: str,
    *,
    outcome_code: str | None = None,
    terminal: bool = False,
) -> None:
    with STATE_LOCK:
        state = _read_state_unlocked()
        task = _task_or_404(state, task_id)
        if task["state"] in TERMINAL_STATES:
            if task["state"] == task_state:
                return
            raise RuntimeError("Reference task attempted a terminal transition")
        task["state"] = task_state
        task["outcome_code"] = outcome_code
        task["updated_at"] = _utc_now()
        if terminal:
            task["terminal_at"] = _utc_now()
        _write_state_unlocked(state)
    data: dict[str, Any] = {"state": task_state}
    if outcome_code is not None:
        data["outcome_code"] = outcome_code
    await _append_event(
        task_id,
        "task.terminal" if terminal else "task.status",
        data,
    )


async def _run_task(task_id: str) -> None:
    try:
        with STATE_LOCK:
            state = _read_state_unlocked()
            task = _task_or_404(state, task_id)
            if task["state"] in TERMINAL_STATES:
                return
            if task["state"] == "cancel_requested":
                cancel_before_start = True
            else:
                cancel_before_start = False
        if cancel_before_start:
            await _set_state(task_id, "cancelled", terminal=True)
            return
        await _set_state(task_id, "running")
        with STATE_LOCK:
            persisted = _task_or_404(_read_state_unlocked(), task_id)
            task_input = dict(persisted["input"])
            start_step = persisted.get("next_step", 0)
            host_capabilities = list(persisted["host_capabilities"])
        if task_input.get("exercise_capabilities"):
            try:
                await asyncio.to_thread(
                    _exercise_host_capabilities,
                    task_id,
                    host_capabilities,
                )
            except HostCapabilityError:
                await _set_state(
                    task_id,
                    "failed",
                    outcome_code="host_capability_failed",
                    terminal=True,
                )
                return
        text = task_input["text"]
        steps = task_input.get("steps", 8)
        delay = task_input.get("delay_ms", 15) / 1000
        approval_at = max(1, steps // 2)
        for index in range(start_step, steps):
            with STATE_LOCK:
                current = _task_or_404(_read_state_unlocked(), task_id)
                state_name = current["state"]
            if state_name == "cancel_requested" and not task_input.get(
                "cancel_race_succeeds", False
            ):
                await _set_state(task_id, "cancelled", terminal=True)
                return
            with STATE_LOCK:
                approval_completed = bool(
                    _task_or_404(
                        _read_state_unlocked(), task_id
                    ).get("approval_completed")
                )
            if (
                task_input.get("require_approval")
                and not approval_completed
                and index == approval_at
            ):
                approval_id = f"approval-{uuid.uuid4().hex}"
                expires_at = (
                    datetime.now(timezone.utc) + timedelta(minutes=5)
                ).isoformat().replace("+00:00", "Z")
                with STATE_LOCK:
                    state = _read_state_unlocked()
                    current = _task_or_404(state, task_id)
                    current["approval"] = {
                        "approval_id": approval_id,
                        "expires_at": expires_at,
                        "decision": None,
                    }
                    current["next_step"] = index
                    current["state"] = "waiting_approval"
                    _write_state_unlocked(state)
                await _append_event(
                    task_id,
                    "approval.requested",
                    {
                        "approval_id": approval_id,
                        "prompt": "Continue the reference task?",
                        "expires_at": expires_at,
                    },
                )
                await _append_event(
                    task_id,
                    "task.status",
                    {"state": "waiting_approval"},
                )
                while True:
                    await asyncio.sleep(0.02)
                    with STATE_LOCK:
                        current = _task_or_404(
                            _read_state_unlocked(), task_id
                        )
                        decision = current["approval"]["decision"]
                        current_state = current["state"]
                        approval_expires_at = datetime.fromisoformat(
                            current["approval"]["expires_at"].replace(
                                "Z", "+00:00"
                            )
                        )
                    if current_state == "cancel_requested":
                        await _set_state(task_id, "cancelled", terminal=True)
                        return
                    if (
                        decision is None
                        and approval_expires_at <= datetime.now(timezone.utc)
                    ):
                        await _set_state(
                            task_id,
                            "failed",
                            outcome_code="approval_expired",
                            terminal=True,
                        )
                        return
                    if decision is not None:
                        break
                if decision == "deny":
                    await _set_state(
                        task_id,
                        "failed",
                        outcome_code="approval_denied",
                        terminal=True,
                    )
                    return
                with STATE_LOCK:
                    state = _read_state_unlocked()
                    current = _task_or_404(state, task_id)
                    current["approval_completed"] = True
                    _write_state_unlocked(state)
                await _set_state(task_id, "running")
            piece = text[index % len(text)] if text else " "
            with STATE_LOCK:
                state = _read_state_unlocked()
                current = _task_or_404(state, task_id)
                current["output"] += piece
                current["next_step"] = index + 1
                _write_state_unlocked(state)
            await _append_event(task_id, "output.delta", {"text": piece})
            await _append_event(
                task_id,
                "task.progress",
                {"progress": (index + 1) / steps},
            )
            if delay:
                await asyncio.sleep(delay)
        if task_input.get("outcome_unknown"):
            await _set_state(
                task_id,
                "failed",
                outcome_code="outcome_unknown",
                terminal=True,
            )
            return
        with STATE_LOCK:
            state = _read_state_unlocked()
            current = _task_or_404(state, task_id)
            greeting = state["values"]["greeting"]
            output = f"{greeting}: {text}"
            if state["values"].get("uppercase"):
                output = output.upper()
            current["output"] = output
            current["result"] = {"text": output}
            current["chat_projection"] = output
            if task_input.get("create_artifact"):
                content = output.encode("utf-8")
                artifact_id = f"artifact-{uuid.uuid4().hex}"
                expires_at = (
                    datetime.now(timezone.utc)
                    + timedelta(
                        seconds=task_input.get("artifact_ttl_seconds", 600)
                    )
                ).isoformat().replace("+00:00", "Z")
                current["artifacts"][artifact_id] = {
                    "artifact_id": artifact_id,
                    "filename": "reference-output.txt",
                    "media_type": "text/plain",
                    "size": len(content),
                    "expires_at": expires_at,
                    "content_base64": base64.b64encode(content).decode("ascii"),
                }
            _write_state_unlocked(state)
            artifacts = _artifact_metadata(current)
        await _append_event(
            task_id,
            "output.snapshot",
            {"text": output},
        )
        for artifact in artifacts:
            await _append_event(task_id, "artifact.added", artifact)
        await _set_state(task_id, "succeeded", terminal=True)
    finally:
        WORKERS.pop(task_id, None)


def _ensure_worker(task_id: str) -> None:
    worker = WORKERS.get(task_id)
    if worker is not None and not worker.done():
        return
    WORKERS[task_id] = asyncio.create_task(_run_task(task_id))


async def _monitor_waiting_approval(task_id: str) -> None:
    try:
        while True:
            await asyncio.sleep(0.02)
            with STATE_LOCK:
                state = _read_state_unlocked()
                task = _task_or_404(state, task_id)
                if task["state"] in TERMINAL_STATES:
                    return
                if task["state"] == "cancel_requested":
                    resolution = "cancel"
                elif task["state"] != "waiting_approval":
                    return
                else:
                    approval = task.get("approval")
                    if not approval:
                        raise RuntimeError(
                            "Waiting reference task has no approval"
                        )
                    decision = approval["decision"]
                    expires_at = datetime.fromisoformat(
                        approval["expires_at"].replace("Z", "+00:00")
                    )
                    if decision == "approve":
                        task["approval_completed"] = True
                        task["state"] = "running"
                        _write_state_unlocked(state)
                        resolution = "approve"
                    elif decision == "deny":
                        resolution = "deny"
                    elif expires_at <= datetime.now(timezone.utc):
                        resolution = "expire"
                    else:
                        resolution = None
            if resolution is None:
                continue
            if resolution == "cancel":
                await _set_state(task_id, "cancelled", terminal=True)
            elif resolution == "deny":
                await _set_state(
                    task_id,
                    "failed",
                    outcome_code="approval_denied",
                    terminal=True,
                )
            elif resolution == "expire":
                await _set_state(
                    task_id,
                    "failed",
                    outcome_code="approval_expired",
                    terminal=True,
                )
            else:
                _ensure_worker(task_id)
            return
    finally:
        APPROVAL_MONITORS.pop(task_id, None)


def _ensure_approval_monitor(task_id: str) -> None:
    monitor = APPROVAL_MONITORS.get(task_id)
    if monitor is not None and not monitor.done():
        return
    APPROVAL_MONITORS[task_id] = asyncio.create_task(
        _monitor_waiting_approval(task_id)
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    state = _read_state()
    for task_id, task in state["tasks"].items():
        if task["state"] in {"queued", "running", "cancel_requested"}:
            _ensure_worker(task_id)
        elif task["state"] == "waiting_approval":
            _ensure_approval_monitor(task_id)
    yield
    workers = [
        *WORKERS.values(),
        *APPROVAL_MONITORS.values(),
    ]
    for worker in workers:
        worker.cancel()
    if workers:
        await asyncio.gather(*workers, return_exceptions=True)


app = FastAPI(
    title="ChatRaw Reference Module",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)


@app.post("/chatraw-module/v1/pair")
async def pair(request: Request):
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid request") from None
    if not isinstance(payload, dict) or set(payload) != {
        "pairing_code",
        "host",
    }:
        raise HTTPException(status_code=400, detail="Invalid request")
    code = payload.get("pairing_code")
    host = payload.get("host")
    if (
        not isinstance(code, str)
        or not isinstance(host, dict)
        or set(host) != {
            "product",
            "module_protocol",
            "capability_base_url",
        }
        or host.get("product") != "ChatRaw Server"
        or host.get("module_protocol") != "1.0.0"
    ):
        raise HTTPException(status_code=400, detail="Pairing rejected")
    try:
        callback = urlsplit(host["capability_base_url"])
        callback_valid = (
            callback.scheme in {"http", "https"}
            and bool(callback.hostname)
            and callback.username is None
            and callback.password is None
            and callback.query == ""
            and callback.fragment == ""
            and callback.path in {"", "/"}
        )
    except (TypeError, ValueError):
        callback_valid = False
    if not callback_valid:
        raise HTTPException(status_code=400, detail="Pairing rejected")
    with STATE_LOCK:
        state = _read_state_unlocked()
        if (
            state["consumed_pairing_code_digest"] == PAIRING_CODE_DIGEST
            or time.time() > PAIRING_EXPIRES_AT
            or not secrets.compare_digest(_digest(code), PAIRING_CODE_DIGEST)
        ):
            raise HTTPException(status_code=400, detail="Pairing rejected")
        token = secrets.token_urlsafe(48)
        state["access_token_digest"] = _digest(token)
        state["consumed_pairing_code_digest"] = PAIRING_CODE_DIGEST
        _write_state_unlocked(state)
    return {
        "module_id": MODULE_ID,
        "instance_id": INSTANCE_ID,
        "access_token": token,
    }


@app.get("/chatraw-module/v1/manifest")
async def manifest(authorization: str | None = Header(default=None)):
    _require_access(authorization)
    return MANIFEST


@app.get("/chatraw-module/v1/health")
async def health(authorization: str | None = Header(default=None)):
    _require_access(authorization)
    healthy = await asyncio.to_thread(_private_dependency_healthy)
    if not healthy:
        return JSONResponse(
            {"status": "unhealthy"},
            status_code=503,
        )
    return {"status": "healthy"}


@app.get("/chatraw-module/v1/ready")
async def ready(authorization: str | None = Header(default=None)):
    state = _require_access(authorization)
    view = _config_view(state)
    dependency_ready = await asyncio.to_thread(
        _private_dependency_healthy
    )
    reasons = []
    if not view["configured"]:
        reasons.append("configuration_missing")
    if not dependency_ready:
        reasons.append("private_dependency_unavailable")
    return {"ready": not reasons, "reasons": reasons}


@app.get("/chatraw-module/v1/config")
async def get_config(authorization: str | None = Header(default=None)):
    state = _require_access(authorization)
    return _config_view(state)


@app.put("/chatraw-module/v1/config")
async def update_config(
    request: Request,
    authorization: str | None = Header(default=None),
):
    _require_access(authorization)
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid request") from None
    if not isinstance(payload, dict) or set(payload) != {
        "revision",
        "values",
        "secrets",
    }:
        raise HTTPException(status_code=400, detail="Invalid request")
    with STATE_LOCK:
        state = _read_state_unlocked()
        if payload["revision"] != str(state["revision"]):
            return JSONResponse(
                {"detail": "Revision conflict"},
                status_code=409,
            )
        values = payload.get("values")
        secret_updates = payload.get("secrets")
        if (
            not isinstance(values, dict)
            or set(values) - {"greeting", "uppercase"}
            or not isinstance(secret_updates, dict)
            or set(secret_updates) - {"service_key"}
        ):
            raise HTTPException(status_code=400, detail="Invalid request")
        greeting = values.get("greeting")
        uppercase = values.get("uppercase")
        if (
            not isinstance(greeting, str)
            or not 1 <= len(greeting) <= 200
            or not isinstance(uppercase, bool)
        ):
            raise HTTPException(status_code=400, detail="Invalid request")
        secret_update = secret_updates.get(
            "service_key", {"action": "keep"}
        )
        if not isinstance(secret_update, dict):
            raise HTTPException(status_code=400, detail="Invalid request")
        action = secret_update.get("action")
        if action == "replace":
            value = secret_update.get("value")
            if not isinstance(value, str) or not value or len(value) > 8192:
                raise HTTPException(status_code=400, detail="Invalid request")
            state["secret_digest"] = _digest(value)
        elif action == "clear":
            if set(secret_update) != {"action"}:
                raise HTTPException(status_code=400, detail="Invalid request")
            state["secret_digest"] = None
        elif action == "keep":
            if set(secret_update) != {"action"}:
                raise HTTPException(status_code=400, detail="Invalid request")
        else:
            raise HTTPException(status_code=400, detail="Invalid request")
        state["values"] = {
            "greeting": greeting,
            "uppercase": uppercase,
        }
        state["revision"] += 1
        _write_state_unlocked(state)
        return _config_view(state)


@app.post(TASK_PREFIX)
async def create_task(
    request: Request,
    authorization: str | None = Header(default=None),
):
    state = _require_access(authorization)
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid request") from None
    required = {
        "task_id",
        "request_digest",
        "action_id",
        "action_version",
        "config_revision",
        "input",
        "host_capabilities",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise HTTPException(status_code=400, detail="Invalid request")
    task_id = payload["task_id"]
    if (
        not isinstance(task_id, str)
        or payload["action_id"] != "echo.task"
        or payload["action_version"] != "1.0.0"
        or payload["config_revision"] != str(state["revision"])
        or not isinstance(payload["request_digest"], str)
        or len(payload["request_digest"]) != 64
        or not isinstance(payload["host_capabilities"], list)
    ):
        raise HTTPException(status_code=409, detail="Task contract conflict")
    task_input = payload["input"]
    allowed_input = {
        "text",
        "steps",
        "delay_ms",
        "require_approval",
        "create_artifact",
        "outcome_unknown",
        "cancel_race_succeeds",
        "cancel_rejected",
        "artifact_ttl_seconds",
        "exercise_capabilities",
    }
    if (
        not isinstance(task_input, dict)
        or set(task_input) - allowed_input
        or not isinstance(task_input.get("text"), str)
        or not task_input["text"]
    ):
        raise HTTPException(status_code=400, detail="Invalid task input")
    with STATE_LOCK:
        state = _read_state_unlocked()
        existing = state["tasks"].get(task_id)
        if existing is not None:
            if existing["request_digest"] != payload["request_digest"]:
                raise HTTPException(
                    status_code=409,
                    detail="Task identity conflict",
                )
            existing["host_capabilities"] = payload["host_capabilities"]
            _write_state_unlocked(state)
            return JSONResponse(_task_summary(existing), status_code=202)
        now = _utc_now()
        state["tasks"][task_id] = {
            "task_id": task_id,
            "request_digest": payload["request_digest"],
            "action_id": payload["action_id"],
            "action_version": payload["action_version"],
            "config_revision": payload["config_revision"],
            "input": task_input,
            "host_capabilities": payload["host_capabilities"],
            "state": "queued",
            "outcome_code": None,
            "last_event_id": 0,
            "events": [],
            "output": "",
            "result": None,
            "chat_projection": None,
            "artifacts": {},
            "approval": None,
            "approval_completed": False,
            "next_step": 0,
            "created_at": now,
            "updated_at": now,
            "terminal_at": None,
        }
        task = state["tasks"][task_id]
        _write_state_unlocked(state)
    _ensure_worker(task_id)
    return JSONResponse(_task_summary(task), status_code=202)


@app.get(f"{TASK_PREFIX}/{{task_id}}")
async def get_task(
    task_id: str,
    authorization: str | None = Header(default=None),
):
    state = _require_access(authorization)
    return _task_summary(_task_or_404(state, task_id))


@app.get(f"{TASK_PREFIX}/{{task_id}}/events")
async def task_events(
    task_id: str,
    authorization: str | None = Header(default=None),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
):
    _require_access(authorization)
    try:
        cursor = int(last_event_id or "0")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cursor") from None
    if cursor < 0:
        raise HTTPException(status_code=400, detail="Invalid cursor")

    async def stream():
        nonlocal cursor
        while True:
            with STATE_LOCK:
                state = _read_state_unlocked()
                task = _task_or_404(state, task_id)
                available = [
                    event for event in task["events"] if event["id"] > cursor
                ]
                terminal = task["state"] in TERMINAL_STATES
            for event in available:
                cursor = event["id"]
                yield (
                    f"id: {event['id']}\n"
                    f"event: {event['event']}\n"
                    f"data: {json.dumps(event['data'], separators=(',', ':'))}\n\n"
                )
            if terminal and not available:
                return
            if not available:
                yield ": heartbeat\n\n"
                condition = NOTIFIERS.setdefault(
                    task_id, asyncio.Condition()
                )
                try:
                    async with condition:
                        await asyncio.wait_for(condition.wait(), timeout=1)
                except asyncio.TimeoutError:
                    pass

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Content-Encoding": "identity",
        },
    )


@app.post(f"{TASK_PREFIX}/{{task_id}}/cancel")
async def cancel_task(
    task_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
):
    _require_access(authorization)
    if await request.json() != {}:
        raise HTTPException(status_code=400, detail="Invalid request")
    with STATE_LOCK:
        state = _read_state_unlocked()
        task = _task_or_404(state, task_id)
        if task["state"] in TERMINAL_STATES:
            return _task_summary(task)
        if task["input"].get("cancel_rejected"):
            raise HTTPException(status_code=409, detail="Cancellation rejected")
        if task["state"] != "cancel_requested":
            task["state"] = "cancel_requested"
            _write_state_unlocked(state)
            should_emit = True
        else:
            should_emit = False
    if should_emit:
        await _append_event(
            task_id,
            "task.status",
            {"state": "cancel_requested"},
        )
    return JSONResponse(_task_summary(_read_state()["tasks"][task_id]), status_code=202)


@app.post(f"{TASK_PREFIX}/{{task_id}}/approvals/{{approval_id}}")
async def resolve_approval(
    task_id: str,
    approval_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
):
    _require_access(authorization)
    payload = await request.json()
    if (
        not isinstance(payload, dict)
        or set(payload) != {"decision"}
        or payload["decision"] not in {"approve", "deny"}
    ):
        raise HTTPException(status_code=400, detail="Invalid request")
    with STATE_LOCK:
        state = _read_state_unlocked()
        task = _task_or_404(state, task_id)
        approval = task.get("approval")
        if not approval or approval["approval_id"] != approval_id:
            raise HTTPException(status_code=404, detail="Approval not found")
        previous = approval["decision"]
        if previous is not None and previous != payload["decision"]:
            raise HTTPException(status_code=409, detail="Approval conflict")
        if previous is not None:
            return _task_summary(task)
        if datetime.fromisoformat(
            approval["expires_at"].replace("Z", "+00:00")
        ) <= datetime.now(timezone.utc):
            raise HTTPException(status_code=410, detail="Approval expired")
        if task["state"] in TERMINAL_STATES:
            raise HTTPException(status_code=409, detail="Task is terminal")
        if previous is None:
            approval["decision"] = payload["decision"]
            task["approval_completed"] = payload["decision"] == "approve"
            if payload["decision"] == "approve":
                task["state"] = "running"
            _write_state_unlocked(state)
            should_emit = True
        else:
            should_emit = False
    if should_emit:
        await _append_event(
            task_id,
            "approval.resolved",
            {
                "approval_id": approval_id,
                "decision": payload["decision"],
            },
        )
        if payload["decision"] == "deny":
            await _set_state(
                task_id,
                "failed",
                outcome_code="approval_denied",
                terminal=True,
            )
        else:
            _ensure_worker(task_id)
    return _task_summary(_read_state()["tasks"][task_id])


@app.get(f"{TASK_PREFIX}/{{task_id}}/artifacts/{{artifact_id}}")
async def get_artifact(
    task_id: str,
    artifact_id: str,
    authorization: str | None = Header(default=None),
):
    state = _require_access(authorization)
    task = _task_or_404(state, task_id)
    artifact = task["artifacts"].get(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    if datetime.fromisoformat(
        artifact["expires_at"].replace("Z", "+00:00")
    ) <= datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Artifact expired")
    body = base64.b64decode(artifact["content_base64"])
    return Response(
        content=body,
        media_type=artifact["media_type"],
        headers={"Content-Length": str(len(body))},
    )


@app.post("/chatraw-module/v1/disconnect")
async def disconnect(
    request: Request,
    authorization: str | None = Header(default=None),
):
    _require_access(authorization)
    if await request.json() != {"preserve_data": True}:
        raise HTTPException(status_code=400, detail="Invalid request")
    with STATE_LOCK:
        state = _read_state_unlocked()
        state["access_token_digest"] = None
        _write_state_unlocked(state)
    return {"disconnected": True, "data_preserved": True}


@app.post("/chatraw-module/v1/purge-data")
async def purge_data(
    request: Request,
    authorization: str | None = Header(default=None),
):
    _require_access(authorization)
    if await request.json() != {"confirmation": f"PURGE {MODULE_ID}"}:
        raise HTTPException(status_code=400, detail="Invalid confirmation")
    with STATE_LOCK:
        state = _read_state_unlocked()
        state["values"] = {
            "greeting": "",
            "uppercase": False,
        }
        state["secret_digest"] = None
        state["tasks"] = {}
        state["revision"] += 1
        _write_state_unlocked(state)
    return {"purged": True}
