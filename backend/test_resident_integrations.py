import copy
import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from backend.resident_integrations import (
    ResidentIntegrationCatalog,
    ResidentIntegrationCatalogError,
)


ROOT = Path(__file__).resolve().parents[1]
DESCRIPTOR = json.loads(
    (
        ROOT
        / "ResidentIntegrations"
        / "reference-module-workbench"
        / "integration.json"
    ).read_text(encoding="utf-8")
)


class ResidentIntegrationCatalogTests(unittest.TestCase):
    def _catalog(self, integrations):
        temporary = tempfile.TemporaryDirectory(
            prefix="chatraw-resident-catalog-"
        )
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "catalog.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "bundle_version": "a" * 64,
                    "integrations": integrations,
                }
            ),
            encoding="utf-8",
        )
        return ResidentIntegrationCatalog(path)

    def test_descriptor_and_host_sdk_contracts_are_valid_schemas(self):
        for filename in (
            "resident-integration-v1.schema.json",
            "resident-integration-sdk-v1.json",
        ):
            contract = json.loads(
                (
                    ROOT / "backend" / "contracts" / filename
                ).read_text(encoding="utf-8")
            )
            Draft202012Validator.check_schema(contract)

    def test_catalog_returns_defensive_copies(self):
        catalog = self._catalog([DESCRIPTOR])
        first = catalog.get("reference-module-workbench")
        self.assertEqual(first["module_id"], "chatraw.reference.echo")
        first["module_id"] = "changed"
        self.assertEqual(
            catalog.get("reference-module-workbench")["module_id"],
            "chatraw.reference.echo",
        )
        self.assertIsNone(catalog.get("missing"))

    def test_catalog_rejects_duplicate_ids_and_invalid_action_ranges(self):
        for integrations in (
            [DESCRIPTOR, copy.deepcopy(DESCRIPTOR)],
            [
                {
                    **copy.deepcopy(DESCRIPTOR),
                    "required_actions": [
                        {
                            "action_id": "echo.task",
                            "version_range": "invalid range",
                        }
                    ],
                }
            ],
        ):
            with self.subTest(integrations=integrations):
                with self.assertRaises(ResidentIntegrationCatalogError):
                    self._catalog(integrations)


if __name__ == "__main__":
    unittest.main()
