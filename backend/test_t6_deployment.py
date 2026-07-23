import json
import unittest
from pathlib import Path
from unittest import mock

from backend import main
from backend.module_registry import ModuleAddressPolicy, ModuleRegistryError


ROOT = Path(__file__).resolve().parents[1]


class T6DeploymentTests(unittest.TestCase):
    def test_source_accepts_loopback_but_container_requires_service_name(self):
        source = ModuleAddressPolicy()
        self.assertEqual(
            source.normalize("http://127.0.0.1:8765"),
            "http://127.0.0.1:8765",
        )
        container = ModuleAddressPolicy(containerized=True)
        for address in (
            "http://127.0.0.1:8765",
            "http://localhost:8765",
            "http://[::1]:8765",
        ):
            with self.subTest(address=address):
                with self.assertRaises(ModuleRegistryError) as blocked:
                    container.normalize(address)
                self.assertEqual(
                    blocked.exception.code,
                    "module_loopback_unreachable_from_container",
                )
        self.assertEqual(
            container.normalize(
                "http://chatraw-reference-module:8765"
            ),
            "http://chatraw-reference-module:8765",
        )

    def test_container_warnings_are_admin_repair_prompts_not_rewrites(self):
        models = [
            main.ModelConfig(
                id="loopback-model",
                name="Local Model",
                api_url="http://127.0.0.1:1234/v1",
                model_id="example",
            ),
            main.ModelConfig(
                id="remote-model",
                name="Remote Model",
                api_url="https://models.example.test/v1",
                model_id="example",
            ),
        ]
        plugin_config = {
            "plugins": {
                "hermes": {
                    "enabled": True,
                    "settings_values": {
                        "baseUrl": "http://localhost:8642/v1"
                    },
                }
            }
        }
        with (
            mock.patch.object(main, "CONTAINERIZED", True),
            mock.patch.object(
                main.db,
                "get_model_configs",
                return_value=models,
            ),
            mock.patch.object(
                main,
                "load_plugin_config",
                return_value=plugin_config,
            ),
        ):
            warnings = main._deployment_warnings()
        self.assertEqual(
            {item["code"] for item in warnings},
            {
                "model_loopback_unreachable_from_container",
                "hermes_loopback_unreachable_from_container",
            },
        )
        serialized = json.dumps(warnings)
        self.assertNotIn("127.0.0.1:1234", serialized)
        self.assertNotIn("localhost:8642", serialized)
        self.assertEqual(
            models[0].api_url,
            "http://127.0.0.1:1234/v1",
        )
        self.assertEqual(
            plugin_config["plugins"]["hermes"]["settings_values"][
                "baseUrl"
            ],
            "http://localhost:8642/v1",
        )

    def test_compose_sources_exclude_orchestration_privileges(self):
        server = (ROOT / "docker-compose.yml").read_text(
            encoding="utf-8"
        )
        module = (
            ROOT / "examples/reference-module/compose.yml"
        ).read_text(encoding="utf-8")
        combined = f"{server}\n{module}"
        self.assertNotIn("network_mode: host", combined)
        self.assertNotIn("docker.sock", combined)
        self.assertNotIn("privileged:", combined)
        self.assertIn("external: true", server)
        self.assertIn("internal: true", module)
        self.assertIn(
            '"host.docker.internal:host-gateway"',
            server,
        )
        self.assertNotIn("\n    ports:", module)
        self.assertIn("reference_module_data:/app/data", module)

    def test_admin_ui_exposes_repair_prompt_without_container_controls(self):
        markup = (ROOT / "backend/static/index.html").read_text(
            encoding="utf-8"
        )
        source = (ROOT / "backend/static/app.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("deploymentStatus.warnings", markup)
        self.assertIn(
            "Existing addresses were not changed automatically.",
            markup,
        )
        self.assertIn("/api/admin/deployment-status", source)
        for forbidden in (
            "docker compose",
            "docker.sock",
            "startContainer",
            "stopContainer",
        ):
            self.assertNotIn(forbidden, source)

    def test_source_and_compose_use_one_black_box_acceptance(self):
        source_gate = (
            ROOT / "scripts/run-t6-source-gate.sh"
        ).read_text(encoding="utf-8")
        compose_gate = (
            ROOT / "scripts/run-t6-compose-gate.sh"
        ).read_text(encoding="utf-8")
        runner = "scripts/t6-deployment-acceptance.py"
        self.assertIn(runner, source_gate)
        self.assertIn(runner, compose_gate)


if __name__ == "__main__":
    unittest.main()
