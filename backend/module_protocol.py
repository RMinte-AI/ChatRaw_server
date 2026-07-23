"""Validation primitives for the registration-only ChatRaw Module Protocol v1."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version


SUPPORTED_PROTOCOL_MAJOR = 1
MAX_MANIFEST_BYTES = 256 * 1024
MAX_CONFIG_BYTES = 128 * 1024
MAX_JSON_DEPTH = 24
MAX_JSON_NODES = 6000
MAX_STRING_BYTES = 64 * 1024
SECRET_SCHEMA_FLAG = "x-chatraw-secret"
SUPPORTED_SCHEMA_KEYWORDS = {
    "$schema",
    "$id",
    "title",
    "description",
    "type",
    "const",
    "enum",
    "default",
    "examples",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "minItems",
    "maxItems",
    "uniqueItems",
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minProperties",
    "maxProperties",
    SECRET_SCHEMA_FLAG,
}
CONFIG_VALUE_TYPES = {"string", "boolean", "number", "integer"}
CONFIG_SCHEMA_KEYWORDS = {
    "$schema",
    "$id",
    "title",
    "description",
    "type",
    "properties",
    "required",
    "additionalProperties",
    "minProperties",
    "maxProperties",
}
CONFIG_FIELD_KEYWORDS = {
    "title",
    "description",
    "type",
    "default",
    "enum",
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    SECRET_SCHEMA_FLAG,
}
_HTML_OR_SCRIPT = re.compile(
    r"javascript\s*:|<\s*/?\s*[a-z][^>]*>",
    flags=re.IGNORECASE,
)


class ModuleProtocolError(ValueError):
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


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _inspect_json_limits(
    value: Any,
    *,
    max_depth: int = MAX_JSON_DEPTH,
    reject_executable_ui: bool = False,
) -> None:
    nodes = 0

    def visit(item: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > MAX_JSON_NODES:
            raise ModuleProtocolError(
                "json_too_complex",
                "Module response is too complex",
            )
        if depth > max_depth:
            raise ModuleProtocolError(
                "json_too_deep",
                "Module response exceeds the nesting limit",
            )
        if isinstance(item, dict):
            if len(item) > 500:
                raise ModuleProtocolError(
                    "json_too_complex",
                    "Module response has too many fields",
                )
            for key, child in item.items():
                if not isinstance(key, str) or len(key) > 160:
                    raise ModuleProtocolError(
                        "invalid_json_field",
                        "Module response contains an invalid field",
                    )
                if reject_executable_ui and key.lower() in {
                    "html",
                    "javascript",
                    "script",
                    "frontend",
                    "ui_bundle",
                    "executable_ui",
                }:
                    raise ModuleProtocolError(
                        "executable_ui_forbidden",
                        "Modules cannot provide executable UI",
                    )
                visit(child, depth + 1)
        elif isinstance(item, list):
            if len(item) > 1000:
                raise ModuleProtocolError(
                    "json_too_complex",
                    "Module response has too many list items",
                )
            for child in item:
                visit(child, depth + 1)
        elif isinstance(item, str):
            if len(item.encode("utf-8")) > MAX_STRING_BYTES:
                raise ModuleProtocolError(
                    "string_too_large",
                    "Module response contains an oversized string",
                )
            if reject_executable_ui and _HTML_OR_SCRIPT.search(item):
                raise ModuleProtocolError(
                    "executable_ui_forbidden",
                    "Modules cannot provide HTML or JavaScript",
                )

    visit(value, 0)


_MANIFEST_SCHEMA_PATH = (
    Path(__file__).resolve().parent
    / "contracts"
    / "module-manifest-v1.schema.json"
)
with _MANIFEST_SCHEMA_PATH.open("r", encoding="utf-8") as _schema_file:
    MODULE_MANIFEST_SCHEMA = json.load(_schema_file)
_MANIFEST_VALIDATOR = Draft202012Validator(MODULE_MANIFEST_SCHEMA)


def _validate_schema_subset(schema: dict[str, Any], *, label: str) -> None:
    def visit(item: dict[str, Any]) -> None:
        unsupported = set(item) - SUPPORTED_SCHEMA_KEYWORDS
        if unsupported:
            raise ModuleProtocolError(
                "unsupported_json_schema",
                f"{label} uses unsupported JSON Schema features",
            )
        properties = item.get("properties")
        if properties is not None:
            if not isinstance(properties, dict):
                raise ModuleProtocolError(
                    "invalid_json_schema",
                    f"{label} is not a valid JSON Schema",
                )
            for child in properties.values():
                if not isinstance(child, dict):
                    raise ModuleProtocolError(
                        "invalid_json_schema",
                        f"{label} is not a valid JSON Schema",
                    )
                visit(child)
        items = item.get("items")
        if items is not None:
            if not isinstance(items, dict):
                raise ModuleProtocolError(
                    "unsupported_json_schema",
                    f"{label} uses unsupported JSON Schema features",
                )
            visit(items)
        additional = item.get("additionalProperties")
        if isinstance(additional, dict):
            visit(additional)

    visit(schema)


def validate_json_schema(schema: dict[str, Any], *, label: str) -> None:
    _inspect_json_limits(schema, max_depth=18, reject_executable_ui=True)
    _validate_schema_subset(schema, label=label)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as error:
        raise ModuleProtocolError(
            "invalid_json_schema",
            f"{label} is not a valid JSON Schema",
        ) from error


def validate_config_schema(schema: dict[str, Any]) -> None:
    if (
        set(schema) - CONFIG_SCHEMA_KEYWORDS
        or schema.get("type") != "object"
        or schema.get("additionalProperties") is not False
        or not isinstance(schema.get("properties"), dict)
    ):
        raise ModuleProtocolError(
            "unsupported_config_schema",
            "Configuration schema must be a closed object",
        )
    properties = schema["properties"]
    required = schema.get("required", [])
    if (
        not isinstance(required, list)
        or not all(
            isinstance(name, str) and name in properties
            for name in required
        )
        or len(set(required)) != len(required)
    ):
        raise ModuleProtocolError(
            "unsupported_config_schema",
            "Configuration schema has invalid required fields",
        )
    for definition in properties.values():
        if set(definition) - CONFIG_FIELD_KEYWORDS:
            raise ModuleProtocolError(
                "unsupported_config_schema",
                "Configuration fields use unsupported schema features",
            )
        value_type = definition.get("type")
        if value_type not in CONFIG_VALUE_TYPES:
            raise ModuleProtocolError(
                "unsupported_config_schema",
                "Configuration fields must use supported scalar types",
            )
        if definition.get(SECRET_SCHEMA_FLAG) is True and value_type != "string":
            raise ModuleProtocolError(
                "unsupported_config_schema",
                "Secret configuration fields must be strings",
            )
        if definition.get(SECRET_SCHEMA_FLAG) is True and set(definition) & {
            "default",
            "enum",
        }:
            raise ModuleProtocolError(
                "unsupported_config_schema",
                "Secret configuration fields cannot expose defaults",
            )
        if "enum" in definition and (
            value_type != "string"
            or not definition["enum"]
            or not all(
                isinstance(value, str)
                for value in definition["enum"]
            )
        ):
            raise ModuleProtocolError(
                "unsupported_config_schema",
                "Configuration enums must contain strings",
            )


def validate_manifest(
    manifest: Any,
    *,
    raw_size: int | None = None,
) -> dict[str, Any]:
    if raw_size is None:
        try:
            raw_size = len(canonical_json(manifest).encode("utf-8"))
        except (TypeError, ValueError) as error:
            raise ModuleProtocolError(
                "invalid_manifest",
                "Module manifest is not valid JSON",
            ) from error
    if raw_size > MAX_MANIFEST_BYTES:
        raise ModuleProtocolError(
            "manifest_too_large",
            "Module manifest exceeds the size limit",
        )
    if not isinstance(manifest, dict):
        raise ModuleProtocolError(
            "invalid_manifest",
            "Module manifest must be an object",
        )
    _inspect_json_limits(manifest, reject_executable_ui=True)
    errors = sorted(
        _MANIFEST_VALIDATOR.iter_errors(manifest),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        raise ModuleProtocolError(
            "invalid_manifest",
            "Module manifest does not match Module Protocol v1",
        )

    action_ids: set[str] = set()
    for action in manifest["actions"]:
        action_id = action["action_id"]
        if action_id in action_ids:
            raise ModuleProtocolError(
                "duplicate_action",
                "Module action identifiers must be unique",
            )
        action_ids.add(action_id)
        validate_json_schema(
            action["input_schema"],
            label=f"Input schema for {action_id}",
        )
        validate_json_schema(
            action["output_schema"],
            label=f"Output schema for {action_id}",
        )
    validate_json_schema(manifest["config_schema"], label="Configuration schema")
    validate_config_schema(manifest["config_schema"])
    try:
        SpecifierSet(manifest["companion_plugin"]["version_range"])
    except InvalidSpecifier as error:
        raise ModuleProtocolError(
            "invalid_plugin_version_range",
            "Companion plugin version range is invalid",
        ) from error
    return deepcopy(manifest)


def protocol_is_compatible(protocol_version: str) -> bool:
    try:
        return Version(protocol_version).major == SUPPORTED_PROTOCOL_MAJOR
    except InvalidVersion:
        return False


def module_major(version: str) -> int:
    try:
        return Version(version).major
    except InvalidVersion as error:
        raise ModuleProtocolError(
            "invalid_module_version",
            "Module version is invalid",
        ) from error


def permission_projection(manifest: dict[str, Any]) -> dict[str, Any]:
    actions = []
    for action in manifest["actions"]:
        actions.append(
            {
                "action_id": action["action_id"],
                "action_major": module_major(action["action_version"]),
                "input_schema_digest": digest_json(
                    action["input_schema"]
                ),
                "output_schema_digest": digest_json(
                    action["output_schema"]
                ),
                "minimum_role": action["minimum_role"],
                "supports_stream": action["supports_stream"],
                "supports_cancel": action["supports_cancel"],
                "supports_approval": action["supports_approval"],
                "supports_artifacts": action["supports_artifacts"],
                "supports_chat_projection": action[
                    "supports_chat_projection"
                ],
            }
        )
    actions.sort(key=lambda item: item["action_id"])
    return {
        "module_major": module_major(manifest["module_version"]),
        "requested_host_capabilities": sorted(
            manifest["requested_host_capabilities"]
        ),
        "actions": actions,
        "companion_plugin": manifest["companion_plugin"],
        "supports_data_purge": manifest["administration"][
            "supports_data_purge"
        ],
    }


def permission_digest(manifest: dict[str, Any]) -> str:
    return digest_json(permission_projection(manifest))


def companion_version_matches(version: str, version_range: str) -> bool:
    try:
        return Version(version) in SpecifierSet(version_range)
    except (InvalidVersion, InvalidSpecifier):
        return False


def _config_properties(
    config_schema: dict[str, Any],
) -> tuple[dict[str, Any], set[str]]:
    properties = config_schema.get("properties", {})
    if not isinstance(properties, dict):
        raise ModuleProtocolError(
            "unsupported_config_schema",
            "Configuration schema must declare object properties",
        )
    secrets = {
        name
        for name, definition in properties.items()
        if isinstance(definition, dict)
        and definition.get(SECRET_SCHEMA_FLAG) is True
    }
    return properties, secrets


def validate_config_update(
    config_schema: dict[str, Any],
    payload: Any,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ModuleProtocolError(
            "invalid_config_update",
            "Configuration update must be an object",
        )
    _inspect_json_limits(payload, max_depth=12, reject_executable_ui=True)
    if len(canonical_json(payload).encode("utf-8")) > MAX_CONFIG_BYTES:
        raise ModuleProtocolError(
            "config_too_large",
            "Configuration update exceeds the size limit",
        )
    if set(payload) != {"revision", "values", "secrets"}:
        raise ModuleProtocolError(
            "invalid_config_update",
            "Configuration update fields are invalid",
        )
    if not isinstance(payload["revision"], str) or not payload["revision"]:
        raise ModuleProtocolError(
            "invalid_revision",
            "Configuration revision is required",
        )
    if not isinstance(payload["values"], dict) or not isinstance(
        payload["secrets"], dict
    ):
        raise ModuleProtocolError(
            "invalid_config_update",
            "Configuration values and secrets must be objects",
        )

    properties, secret_names = _config_properties(config_schema)
    if set(payload["values"]) & secret_names:
        raise ModuleProtocolError(
            "secret_in_plain_values",
            "Secret configuration must use secret actions",
        )
    unknown_values = set(payload["values"]) - set(properties)
    unknown_secrets = set(payload["secrets"]) - secret_names
    if unknown_values or unknown_secrets:
        raise ModuleProtocolError(
            "unknown_config_field",
            "Configuration contains an unknown field",
        )

    nonsecret_schema = deepcopy(config_schema)
    nonsecret_properties = {
        name: definition
        for name, definition in properties.items()
        if name not in secret_names
    }
    nonsecret_schema["properties"] = nonsecret_properties
    nonsecret_schema["required"] = [
        name
        for name in config_schema.get("required", [])
        if name not in secret_names
    ]
    try:
        Draft202012Validator(nonsecret_schema).validate(payload["values"])
    except ValidationError as error:
        raise ModuleProtocolError(
            "invalid_config_values",
            "Configuration values do not match the module schema",
        ) from error

    normalized_secrets: dict[str, dict[str, str]] = {}
    for name, action_payload in payload["secrets"].items():
        if not isinstance(action_payload, dict):
            raise ModuleProtocolError(
                "invalid_secret_action",
                "Secret configuration action is invalid",
            )
        action = action_payload.get("action")
        if action not in {"keep", "replace", "clear"}:
            raise ModuleProtocolError(
                "invalid_secret_action",
                "Secret action must be keep, replace, or clear",
            )
        if action == "replace":
            value = action_payload.get("value")
            if not isinstance(value, str) or not value or len(value) > 8192:
                raise ModuleProtocolError(
                    "invalid_secret_value",
                    "Replacement secret is invalid",
                )
            try:
                Draft202012Validator(properties[name]).validate(value)
            except ValidationError as error:
                raise ModuleProtocolError(
                    "invalid_secret_value",
                    "Replacement secret does not match its schema",
                ) from error
            normalized_secrets[name] = {"action": action, "value": value}
        else:
            if set(action_payload) != {"action"}:
                raise ModuleProtocolError(
                    "invalid_secret_action",
                    "Keep and clear actions cannot include a value",
                )
            normalized_secrets[name] = {"action": action}

    return {
        "revision": payload["revision"],
        "values": deepcopy(payload["values"]),
        "secrets": normalized_secrets,
    }


def validate_config_view(
    config_schema: dict[str, Any],
    payload: Any,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ModuleProtocolError(
            "invalid_config_response",
            "Module configuration response is invalid",
        )
    _inspect_json_limits(payload, max_depth=12, reject_executable_ui=True)
    if len(canonical_json(payload).encode("utf-8")) > MAX_CONFIG_BYTES:
        raise ModuleProtocolError(
            "config_too_large",
            "Module configuration response exceeds the size limit",
        )
    required = {
        "revision",
        "values",
        "secret_configured",
        "configured",
        "missing_required",
    }
    if set(payload) != required:
        raise ModuleProtocolError(
            "invalid_config_response",
            "Module configuration response fields are invalid",
        )
    properties, secret_names = _config_properties(config_schema)
    if (
        not isinstance(payload["revision"], str)
        or not payload["revision"]
        or len(payload["revision"]) > 256
    ):
        raise ModuleProtocolError(
            "invalid_config_response",
            "Module configuration revision is invalid",
        )
    if not isinstance(payload["values"], dict):
        raise ModuleProtocolError(
            "invalid_config_response",
            "Module configuration values are invalid",
        )
    if set(payload["values"]) - (set(properties) - secret_names):
        raise ModuleProtocolError(
            "invalid_config_response",
            "Module returned an undeclared configuration value",
        )
    if (
        not isinstance(payload["secret_configured"], dict)
        or set(payload["secret_configured"]) != secret_names
        or not all(
            isinstance(value, bool)
            for value in payload["secret_configured"].values()
        )
    ):
        raise ModuleProtocolError(
            "invalid_config_response",
            "Module secret configuration state is invalid",
        )
    if not isinstance(payload["configured"], bool) or not isinstance(
        payload["missing_required"], list
    ):
        raise ModuleProtocolError(
            "invalid_config_response",
            "Module configuration state is invalid",
        )
    missing_required = payload["missing_required"]
    if (
        len(missing_required) > len(properties)
        or not all(
            isinstance(name, str) and name in properties
            for name in missing_required
        )
        or len(set(missing_required)) != len(missing_required)
        or (payload["configured"] and missing_required)
    ):
        raise ModuleProtocolError(
            "invalid_config_response",
            "Module missing-field state is invalid",
        )
    nonsecret_schema = deepcopy(config_schema)
    nonsecret_schema["properties"] = {
        name: definition
        for name, definition in properties.items()
        if name not in secret_names
    }
    nonsecret_schema["required"] = [
        name
        for name in config_schema.get("required", [])
        if name not in secret_names
    ]
    try:
        Draft202012Validator(nonsecret_schema).validate(payload["values"])
    except ValidationError as error:
        raise ModuleProtocolError(
            "invalid_config_response",
            "Module configuration values do not match its schema",
        ) from error
    return deepcopy(payload)
