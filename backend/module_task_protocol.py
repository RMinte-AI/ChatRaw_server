"""Validation and state-machine primitives for Module Protocol v1 tasks."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

try:
    from .module_protocol import canonical_json
except ImportError:
    from module_protocol import canonical_json


PUBLIC_TASK_STATES = {
    "queued",
    "running",
    "waiting_approval",
    "cancel_requested",
    "succeeded",
    "failed",
    "cancelled",
}
INTERNAL_TASK_STATES = {"submitting", "abandoned"}
TERMINAL_TASK_STATES = {"succeeded", "failed", "cancelled"}
ACTIVE_TASK_STATES = PUBLIC_TASK_STATES - TERMINAL_TASK_STATES
TASK_EVENTS = {
    "task.status",
    "task.progress",
    "output.delta",
    "output.snapshot",
    "approval.requested",
    "approval.resolved",
    "artifact.added",
    "task.terminal",
}
HOST_CAPABILITIES = {
    "chat.read",
    "resource.read",
    "resource.stream",
    "model.invoke",
}
MAX_TASK_REQUEST_BYTES = 256 * 1024
MAX_TASK_RESPONSE_BYTES = 512 * 1024
MAX_EVENT_BYTES = 128 * 1024
MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_IDEMPOTENCY_KEY_LENGTH = 200
MAX_TASK_LIST_LIMIT = 100
MAX_INPUT_RESOURCES = 64
CAPABILITY_TOKEN_TTL_SECONDS = 15 * 60
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
_TASK_SCHEMA_PATH = (
    Path(__file__).resolve().parent
    / "contracts"
    / "module-task-v1.schema.json"
)
with _TASK_SCHEMA_PATH.open("r", encoding="utf-8") as _schema_file:
    MODULE_TASK_SCHEMA = json.load(_schema_file)


def _contract_validator(definition: str) -> Draft202012Validator:
    return Draft202012Validator(
        {
            "$ref": f"#/$defs/{definition}",
            "$defs": MODULE_TASK_SCHEMA["$defs"],
        }
    )


_SUMMARY_VALIDATOR = _contract_validator("moduleSummary")
_EVENT_VALIDATOR = _contract_validator("event")
_ARTIFACT_VALIDATOR = _contract_validator("artifact")
_RESOURCE_VALIDATOR = _contract_validator("resource")


class ModuleTaskProtocolError(ValueError):
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


def digest_task_request(value: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _inspect_task_json(value: Any) -> None:
    stack = [(value, 0)]
    nodes = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > 6000 or depth > 24:
            raise ModuleTaskProtocolError(
                "invalid_task_response",
                "Module task response is too complex",
                status_code=502,
            )
        if isinstance(item, dict):
            if len(item) > 500:
                raise ModuleTaskProtocolError(
                    "invalid_task_response",
                    "Module task response is too complex",
                    status_code=502,
                )
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            if len(item) > 1000:
                raise ModuleTaskProtocolError(
                    "invalid_task_response",
                    "Module task response is too complex",
                    status_code=502,
                )
            stack.extend((child, depth + 1) for child in item)
        elif isinstance(item, str) and len(item.encode("utf-8")) > 64 * 1024:
            raise ModuleTaskProtocolError(
                "invalid_task_response",
                "Module task response contains an oversized string",
                status_code=502,
            )


def _valid_timestamp(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return parsed.tzinfo is not None


def validate_idempotency_key(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_IDEMPOTENCY_KEY_LENGTH
        or any(ord(character) < 0x21 or ord(character) > 0x7E for character in value)
    ):
        raise ModuleTaskProtocolError(
            "invalid_idempotency_key",
            "Idempotency-Key is invalid",
        )
    return value


def validate_task_input(
    value: Any,
    schema: dict[str, Any],
) -> dict[str, Any]:
    try:
        encoded = canonical_json(value).encode("utf-8")
    except (TypeError, ValueError):
        raise ModuleTaskProtocolError(
            "invalid_task_input",
            "Task input must be valid JSON",
        ) from None
    if len(encoded) > MAX_TASK_REQUEST_BYTES:
        raise ModuleTaskProtocolError(
            "task_input_too_large",
            "Task input exceeds the size limit",
            status_code=413,
        )
    if not isinstance(value, dict):
        raise ModuleTaskProtocolError(
            "invalid_task_input",
            "Task input must be an object",
        )
    try:
        Draft202012Validator(schema).validate(value)
    except ValidationError:
        raise ModuleTaskProtocolError(
            "invalid_task_input",
            "Task input does not match the action schema",
        ) from None
    return value


def validate_task_summary(
    value: Any,
    *,
    expected_task_id: str,
    expected_action_id: str,
    expected_action_version: str,
    expected_config_revision: str,
    output_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _inspect_task_json(value)
    if not isinstance(value, dict):
        raise ModuleTaskProtocolError(
            "invalid_task_response",
            "Module returned an invalid task response",
            status_code=502,
        )
    if list(_SUMMARY_VALIDATOR.iter_errors(value)):
        raise ModuleTaskProtocolError(
            "invalid_task_response",
            "Module returned an invalid task response",
            status_code=502,
        )
    allowed = {
        "task_id",
        "action_id",
        "action_version",
        "config_revision",
        "state",
        "last_event_id",
        "outcome_code",
        "result",
        "chat_projection",
        "artifacts",
        "resources",
    }
    required = {
        "task_id",
        "action_id",
        "action_version",
        "config_revision",
        "state",
        "last_event_id",
    }
    if set(value) - allowed or not required.issubset(value):
        raise ModuleTaskProtocolError(
            "invalid_task_response",
            "Module returned an invalid task response",
            status_code=502,
        )
    if (
        value["task_id"] != expected_task_id
        or value["action_id"] != expected_action_id
        or value["action_version"] != expected_action_version
        or value["config_revision"] != expected_config_revision
        or value["state"] not in PUBLIC_TASK_STATES
        or not isinstance(value["last_event_id"], int)
        or value["last_event_id"] < 0
    ):
        raise ModuleTaskProtocolError(
            "task_identity_mismatch",
            "Module task identity does not match the request",
            status_code=502,
        )
    outcome_code = value.get("outcome_code")
    if outcome_code is not None and (
        not isinstance(outcome_code, str)
        or not _IDENTIFIER.fullmatch(outcome_code)
    ):
        raise ModuleTaskProtocolError(
            "invalid_task_response",
            "Module returned an invalid outcome code",
            status_code=502,
        )
    if value["state"] == "failed" and outcome_code is None:
        raise ModuleTaskProtocolError(
            "invalid_task_response",
            "Failed tasks must include an outcome code",
            status_code=502,
        )
    if "result" in value:
        if value["state"] != "succeeded" or output_schema is None:
            raise ModuleTaskProtocolError(
                "invalid_task_response",
                "Only succeeded tasks may include a result",
                status_code=502,
            )
        try:
            Draft202012Validator(output_schema).validate(value["result"])
        except ValidationError:
            raise ModuleTaskProtocolError(
                "invalid_task_response",
                "Task result does not match the action schema",
                status_code=502,
            ) from None
    projection = value.get("chat_projection")
    if projection is not None and (
        value["state"] != "succeeded"
        or not isinstance(projection, str)
        or len(projection.encode("utf-8")) > MAX_TASK_RESPONSE_BYTES
    ):
        raise ModuleTaskProtocolError(
            "invalid_task_response",
            "Module returned an invalid chat projection",
            status_code=502,
        )
    artifacts = value.get("artifacts", [])
    if not isinstance(artifacts, list) or len(artifacts) > 128:
        raise ModuleTaskProtocolError(
            "invalid_task_response",
            "Module returned invalid artifact metadata",
            status_code=502,
        )
    for artifact in artifacts:
        validate_artifact_metadata(artifact)
    resources = value.get("resources", [])
    if not isinstance(resources, list) or len(resources) > 128:
        raise ModuleTaskProtocolError(
            "invalid_task_response",
            "Module returned invalid resource metadata",
            status_code=502,
        )
    for resource in resources:
        validate_resource_metadata(resource)
    return value


def validate_task_event(
    value: Any,
    *,
    previous_event_id: int,
) -> dict[str, Any]:
    _inspect_task_json(value)
    if list(_EVENT_VALIDATOR.iter_errors(value)):
        raise ModuleTaskProtocolError(
            "invalid_task_event",
            "Module returned an invalid task event stream",
            status_code=502,
        )
    if (
        not isinstance(value, dict)
        or set(value) != {"id", "event", "data"}
        or not isinstance(value["id"], int)
        or value["id"] <= previous_event_id
        or value["event"] not in TASK_EVENTS
        or not isinstance(value["data"], dict)
    ):
        raise ModuleTaskProtocolError(
            "invalid_task_event",
            "Module returned an invalid task event stream",
            status_code=502,
        )
    if len(canonical_json(value).encode("utf-8")) > MAX_EVENT_BYTES:
        raise ModuleTaskProtocolError(
            "task_event_too_large",
            "Module task event exceeds the size limit",
            status_code=502,
        )
    event = value["event"]
    data = value["data"]
    if event in {"task.status", "task.terminal"}:
        if set(data) - {"state", "outcome_code"}:
            raise ModuleTaskProtocolError(
                "invalid_task_event",
                "Module returned an invalid task state event",
                status_code=502,
            )
        state = data.get("state")
        if state not in PUBLIC_TASK_STATES:
            raise ModuleTaskProtocolError(
                "invalid_task_event",
                "Module returned an invalid task state event",
                status_code=502,
            )
        if event == "task.terminal" and state not in TERMINAL_TASK_STATES:
            raise ModuleTaskProtocolError(
                "invalid_task_event",
                "Module returned an invalid terminal event",
                status_code=502,
            )
        outcome_code = data.get("outcome_code")
        if outcome_code is not None and (
            not isinstance(outcome_code, str)
            or not _IDENTIFIER.fullmatch(outcome_code)
        ):
            raise ModuleTaskProtocolError(
                "invalid_task_event",
                "Module returned an invalid task outcome",
                status_code=502,
            )
        if (
            event == "task.terminal"
            and state == "failed"
            and outcome_code is None
        ):
            raise ModuleTaskProtocolError(
                "invalid_task_event",
                "Failed tasks must include an outcome code",
                status_code=502,
            )
    elif event == "task.progress":
        if set(data) - {"progress", "message"} or (
            "message" in data
            and (
                not isinstance(data["message"], str)
                or len(data["message"]) > 1000
            )
        ):
            raise ModuleTaskProtocolError(
                "invalid_task_event",
                "Module returned invalid task progress",
                status_code=502,
            )
        progress = data.get("progress")
        if (
            isinstance(progress, bool)
            or not isinstance(progress, (int, float))
            or not 0 <= progress <= 1
        ):
            raise ModuleTaskProtocolError(
                "invalid_task_event",
                "Module returned invalid task progress",
                status_code=502,
            )
    elif event in {"output.delta", "output.snapshot"}:
        allowed = (
            {"text"}
            if event == "output.delta"
            else {"text", "compacted_through"}
        )
        if not isinstance(data.get("text"), str):
            raise ModuleTaskProtocolError(
                "invalid_task_event",
                "Module returned invalid task output",
                status_code=502,
            )
        if set(data) - allowed or (
            "compacted_through" in data
            and (
                not isinstance(data["compacted_through"], int)
                or data["compacted_through"] < 0
            )
        ):
            raise ModuleTaskProtocolError(
                "invalid_task_event",
                "Module returned invalid task output",
                status_code=502,
            )
    elif event in {"approval.requested", "approval.resolved"}:
        if not isinstance(data.get("approval_id"), str) or not _IDENTIFIER.fullmatch(
            data["approval_id"]
        ):
            raise ModuleTaskProtocolError(
                "invalid_task_event",
                "Module returned an invalid approval event",
                status_code=502,
            )
        if event == "approval.requested":
            if (
                set(data) != {"approval_id", "prompt", "expires_at"}
                or not isinstance(data["prompt"], str)
                or not 1 <= len(data["prompt"]) <= 4000
                or not isinstance(data["expires_at"], str)
                or not _valid_timestamp(data["expires_at"])
            ):
                raise ModuleTaskProtocolError(
                    "invalid_task_event",
                    "Module returned an invalid approval event",
                    status_code=502,
                )
        elif (
            set(data) != {"approval_id", "decision"}
            or data["decision"] not in {"approve", "deny"}
        ):
            raise ModuleTaskProtocolError(
                "invalid_task_event",
                "Module returned an invalid approval event",
                status_code=502,
            )
    elif event == "artifact.added":
        validate_artifact_metadata(data)
    return value


def validate_artifact_metadata(value: Any) -> dict[str, Any]:
    required = {"artifact_id", "filename", "media_type", "size", "expires_at"}
    if (
        not isinstance(value, dict)
        or list(_ARTIFACT_VALIDATOR.iter_errors(value))
        or set(value) != required
        or not isinstance(value["artifact_id"], str)
        or not _IDENTIFIER.fullmatch(value["artifact_id"])
        or not isinstance(value["filename"], str)
        or not 1 <= len(value["filename"]) <= 255
        or "/" in value["filename"]
        or "\\" in value["filename"]
        or any(
            ord(character) < 0x20 or ord(character) == 0x7F
            for character in value["filename"]
        )
        or not isinstance(value["media_type"], str)
        or not 1 <= len(value["media_type"]) <= 127
        or not isinstance(value["size"], int)
        or isinstance(value["size"], bool)
        or not 0 <= value["size"] <= MAX_ARTIFACT_BYTES
        or (
            value["expires_at"] is not None
            and (
                not isinstance(value["expires_at"], str)
                or not _valid_timestamp(value["expires_at"])
            )
        )
    ):
        raise ModuleTaskProtocolError(
            "invalid_artifact",
            "Module returned invalid artifact metadata",
            status_code=502,
        )
    return value


def validate_resource_metadata(value: Any) -> dict[str, Any]:
    required = {"resource_id", "filename", "media_type", "size"}
    allowed = required | {"expires_at"}
    if (
        not isinstance(value, dict)
        or list(_RESOURCE_VALIDATOR.iter_errors(value))
        or not required.issubset(value)
        or set(value) - allowed
        or not isinstance(value["resource_id"], str)
        or not _IDENTIFIER.fullmatch(value["resource_id"])
        or not isinstance(value["filename"], str)
        or not 1 <= len(value["filename"]) <= 255
        or "/" in value["filename"]
        or "\\" in value["filename"]
        or any(
            ord(character) < 0x20 or ord(character) == 0x7F
            for character in value["filename"]
        )
        or not isinstance(value["media_type"], str)
        or not 1 <= len(value["media_type"]) <= 127
        or not isinstance(value["size"], int)
        or isinstance(value["size"], bool)
        or value["size"] < 0
        or (
            value.get("expires_at") is not None
            and (
                not isinstance(value["expires_at"], str)
                or not _valid_timestamp(value["expires_at"])
            )
        )
    ):
        raise ModuleTaskProtocolError(
            "invalid_resource",
            "Module returned invalid resource metadata",
            status_code=502,
        )
    return value
