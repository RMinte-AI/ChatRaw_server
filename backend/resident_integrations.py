"""Validated catalog for source-built Resident Integrations."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from packaging.specifiers import InvalidSpecifier, SpecifierSet


ROOT = Path(__file__).resolve().parent
DEFAULT_CATALOG_PATH = (
    ROOT / "static" / "resident-integrations" / "catalog.json"
)
SCHEMA_PATH = ROOT / "contracts" / "resident-integration-v1.schema.json"


class ResidentIntegrationCatalogError(RuntimeError):
    pass


class ResidentIntegrationCatalog:
    def __init__(self, path: str | Path = DEFAULT_CATALOG_PATH):
        self.path = Path(path).resolve()
        self._integrations = self._load()

    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise ResidentIntegrationCatalogError(
                "Resident Integration catalog is unavailable"
            ) from error
        if (
            not isinstance(payload, dict)
            or set(payload)
            != {"schema_version", "bundle_version", "integrations"}
            or payload.get("schema_version") != "1"
            or not isinstance(payload.get("bundle_version"), str)
            or len(payload["bundle_version"]) != 64
            or any(
                character not in "0123456789abcdef"
                for character in payload["bundle_version"]
            )
            or not isinstance(payload.get("integrations"), list)
        ):
            raise ResidentIntegrationCatalogError(
                "Resident Integration catalog is invalid"
            )
        validator = Draft202012Validator(schema)
        integrations: dict[str, dict[str, Any]] = {}
        for integration in payload["integrations"]:
            if list(validator.iter_errors(integration)):
                raise ResidentIntegrationCatalogError(
                    "Resident Integration catalog is invalid"
                )
            integration_id = integration["id"]
            if integration_id in integrations:
                raise ResidentIntegrationCatalogError(
                    "Resident Integration identifiers must be unique"
                )
            entrypoint_ids = [
                entrypoint["id"]
                for entrypoint in integration["entrypoints"]
            ]
            action_ids = [
                action["action_id"]
                for action in integration["required_actions"]
            ]
            if (
                len(entrypoint_ids) != len(set(entrypoint_ids))
                or len(action_ids) != len(set(action_ids))
            ):
                raise ResidentIntegrationCatalogError(
                    "Resident Integration declarations must be unique"
                )
            try:
                for action in integration["required_actions"]:
                    SpecifierSet(action["version_range"])
            except InvalidSpecifier as error:
                raise ResidentIntegrationCatalogError(
                    "Resident Integration action version range is invalid"
                ) from error
            integrations[integration_id] = deepcopy(integration)
        self.bundle_version = payload["bundle_version"]
        return integrations

    def get(self, integration_id: str) -> dict[str, Any] | None:
        integration = self._integrations.get(integration_id)
        return deepcopy(integration) if integration is not None else None

    def list(self) -> list[dict[str, Any]]:
        return [
            deepcopy(self._integrations[integration_id])
            for integration_id in sorted(self._integrations)
        ]
