import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "backend" / "contracts" / "module-plugin-sdk-v1.json"
APP_PATH = ROOT / "backend" / "static" / "app.js"
INDEX_PATH = ROOT / "backend" / "static" / "index.html"
PLUGIN_DIR = (
    ROOT
    / "Plugins"
    / "Plugin_market"
    / "reference-module-companion"
)


class ModulePluginSdkContractTests(unittest.TestCase):
    def test_contract_is_machine_readable_and_method_set_is_frozen(self):
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(contract)
        self.assertEqual(contract["version"], "1.0.0")
        self.assertEqual(contract["global"], "window.ChatRaw.modules")
        self.assertEqual(
            set(contract["methods"]),
            {
                "getFeatureStatus",
                "startTask",
                "getTask",
                "subscribe",
                "cancelTask",
                "respondApproval",
                "downloadArtifact",
            },
        )
        self.assertFalse(
            contract["transport"]["plugin_calls_module_directly"]
        )
        self.assertFalse(
            contract["transport"]["module_supplies_frontend_code"]
        )
        self.assertEqual(
            set(contract["events"]["types"]),
            {
                "task.status",
                "task.progress",
                "output.delta",
                "output.snapshot",
                "approval.requested",
                "approval.resolved",
                "artifact.added",
                "task.terminal",
            },
        )
        self.assertIn(
            "invalid_sdk_argument",
            contract["errors"]["local_codes"],
        )

    def test_browser_sdk_preserves_legacy_plugin_global(self):
        source = APP_PATH.read_text(encoding="utf-8")
        self.assertIn("window.ChatRaw.modules = modulesSdk", source)
        self.assertIn("window.ChatRawPlugin = {", source)
        self.assertIn("'Last-Event-ID': String(cursor)", source)
        self.assertIn("credentials: 'same-origin'", source)
        for method in json.loads(
            CONTRACT_PATH.read_text(encoding="utf-8")
        )["methods"]:
            self.assertRegex(source, rf"\b{method}(?::|,)")

    def test_core_owns_task_ui_and_persistence_is_identifier_only(self):
        source = APP_PATH.read_text(encoding="utf-8")
        markup = INDEX_PATH.read_text(encoding="utf-8")
        self.assertIn("Core module task UI", markup)
        self.assertIn("moduleTaskUi.approval", markup)
        self.assertIn("downloadVisibleModuleArtifact", markup)
        self.assertIn("artifact.artifact_ref", source)
        self.assertIn("event.event === 'artifact.added'", source)
        self.assertIn(
            "await appInstance.loadMessages(",
            source,
        )
        self.assertIn(
            "JSON.stringify(taskIds)",
            source,
        )
        self.assertNotIn("module_address", source)
        self.assertNotIn("module_token", source)

    def test_alpine_component_initializes_only_once(self):
        markup = INDEX_PATH.read_text(encoding="utf-8")
        self.assertIn('<body x-data="app()"', markup)
        self.assertNotIn('x-init="init()"', markup)

    def test_reference_companion_uses_only_host_sdks(self):
        source = (PLUGIN_DIR / "main.js").read_text(encoding="utf-8")
        manifest = json.loads(
            (PLUGIN_DIR / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["id"], "reference-module-companion")
        self.assertNotIn("fetch(", source)
        self.assertIn("window.ChatRaw.modules.getFeatureStatus", source)
        self.assertIn("window.ChatRaw.modules.startTask", source)
        self.assertIn(
            "ChatRawPlugin.ui.registerToolbarButton",
            source,
        )


if __name__ == "__main__":
    unittest.main()
