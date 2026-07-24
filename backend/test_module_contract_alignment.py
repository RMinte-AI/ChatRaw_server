import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from backend.module_protocol import (
    ModuleProtocolError,
    permission_digest,
    validate_manifest,
)
from backend.module_task_protocol import (
    ModuleTaskProtocolError,
    validate_task_event,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "backend" / "contracts"
REFERENCE_MANIFEST = json.loads(
    (
        ROOT / "examples/reference-module/manifest.example.json"
    ).read_text(encoding="utf-8")
)


def _load(name):
    return json.loads(
        (CONTRACT_DIR / name).read_text(encoding="utf-8")
    )


def _definition_validator(contract, definition):
    return Draft202012Validator(
        {
            "$ref": f"#/$defs/{definition}",
            "$defs": contract["$defs"],
        }
    )


class ModuleContractAlignmentTests(unittest.TestCase):
    def test_frontend_integration_legacy_plugin_normalizes_without_review_churn(
        self,
    ):
        legacy = validate_manifest(copy.deepcopy(REFERENCE_MANIFEST))
        canonical_input = copy.deepcopy(REFERENCE_MANIFEST)
        plugin = canonical_input.pop("companion_plugin")
        canonical_input["frontend_integration"] = {
            "mode": "plugin",
            **plugin,
        }
        canonical = validate_manifest(canonical_input)
        self.assertNotIn("companion_plugin", legacy)
        self.assertEqual(
            legacy["frontend_integration"],
            canonical["frontend_integration"],
        )
        self.assertEqual(
            permission_digest(legacy),
            permission_digest(canonical),
        )

    def test_manifest_accepts_exactly_one_plugin_or_resident_integration(self):
        resident = json.loads(
            (
                ROOT
                / "examples/reference-module/manifest.resident.example.json"
            ).read_text(encoding="utf-8")
        )
        normalized = validate_manifest(resident)
        self.assertEqual(
            normalized["frontend_integration"],
            {
                "mode": "resident",
                "id": "reference-module-workbench",
                "version_range": ">=1.0.0,<2.0.0",
            },
        )

        both = copy.deepcopy(REFERENCE_MANIFEST)
        both["frontend_integration"] = copy.deepcopy(
            resident["frontend_integration"]
        )
        neither = copy.deepcopy(REFERENCE_MANIFEST)
        del neither["companion_plugin"]
        for invalid in (both, neither):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ModuleProtocolError):
                    validate_manifest(invalid)

    def test_manifest_rejects_invalid_resident_version_range(self):
        resident = json.loads(
            (
                ROOT
                / "examples/reference-module/manifest.resident.example.json"
            ).read_text(encoding="utf-8")
        )
        resident["frontend_integration"]["version_range"] = "not a range"
        with self.assertRaises(ModuleProtocolError) as rejected:
            validate_manifest(resident)
        self.assertEqual(
            rejected.exception.code,
            "invalid_frontend_integration_version_range",
        )

    def test_contract_roots_reject_unrelated_values(self):
        for name in (
            "module-management-v1.schema.json",
            "module-task-v1.schema.json",
        ):
            validator = Draft202012Validator(_load(name))
            for value in (None, 7, {"totally": "wrong"}):
                with self.subTest(contract=name, value=value):
                    self.assertTrue(list(validator.iter_errors(value)))

    def test_manifest_rejects_non_object_action_input(self):
        manifest = copy.deepcopy(REFERENCE_MANIFEST)
        manifest["actions"][0]["input_schema"] = {"type": "string"}
        with self.assertRaises(ModuleProtocolError) as rejected:
            validate_manifest(manifest)
        self.assertIn(
            rejected.exception.code,
            {"invalid_manifest", "unsupported_input_schema"},
        )

    def test_pair_contract_requires_explicit_callback_base(self):
        contract = _load("module-management-v1.schema.json")
        validator = _definition_validator(contract, "pairRequest")
        valid = {
            "pairing_code": "x" * 32,
            "host": {
                "product": "ChatRaw Server",
                "module_protocol": "1.0.0",
                "capability_base_url": "http://127.0.0.1:51111",
            },
        }
        self.assertFalse(list(validator.iter_errors(valid)))
        invalid = copy.deepcopy(valid)
        del invalid["host"]["capability_base_url"]
        self.assertTrue(list(validator.iter_errors(invalid)))

    def test_event_schema_and_runtime_accept_same_valid_event(self):
        contract = _load("module-task-v1.schema.json")
        validator = _definition_validator(contract, "event")
        event = {
            "id": 1,
            "event": "approval.requested",
            "data": {
                "approval_id": "approval-1",
                "prompt": "Continue?",
                "expires_at": "2099-01-01T00:00:00Z",
            },
        }
        self.assertFalse(list(validator.iter_errors(event)))
        self.assertEqual(
            validate_task_event(event, previous_event_id=0),
            event,
        )

    def test_event_schema_and_runtime_reject_same_invalid_event(self):
        contract = _load("module-task-v1.schema.json")
        validator = _definition_validator(contract, "event")
        event = {
            "id": 1,
            "event": "task.progress",
            "data": {"progress": 2},
        }
        self.assertTrue(list(validator.iter_errors(event)))
        with self.assertRaises(ModuleTaskProtocolError):
            validate_task_event(event, previous_event_id=0)


if __name__ == "__main__":
    unittest.main()
