import asyncio
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from backend import main


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "backend" / "contracts" / "chatraw-v2.2.1.json"
CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


class JsonRequest:
    async def json(self):
        return {}


async def collect_stream(response):
    return [chunk async for chunk in response.body_iterator]


def streaming_submission(chat_id="chat-contract"):
    settings = main.Settings()
    settings.chat_settings.stream = True
    return {
        "chat_id": chat_id,
        "message": "contract",
        "use_rag": False,
        "use_thinking": False,
        "image_base64": "",
        "web_content": "",
        "web_url": "",
        "settings": settings,
        "effective_system_prompt": "",
    }


class V221CompatibilityContractTests(unittest.TestCase):
    def test_tests_use_temporary_data_dir(self):
        data_dir = Path(main.DATA_DIR).resolve()
        temp_root = Path(tempfile.gettempdir()).resolve()
        self.assertTrue(data_dir.is_relative_to(temp_root), data_dir)
        self.assertFalse(data_dir.is_relative_to(REPO_ROOT), data_dir)

    def test_legacy_routes_remain_available(self):
        actual = {
            (method, route.path)
            for route in main.app.routes
            for method in getattr(route, "methods", set())
            if method not in {"HEAD", "OPTIONS"}
        }
        expected = {tuple(route) for route in CONTRACT["legacy_routes"]}
        self.assertEqual(set(), expected - actual)

        static_contract = CONTRACT["static_mount"]
        self.assertTrue(
            any(
                route.path == static_contract["path"]
                and route.name == static_contract["name"]
                for route in main.app.routes
            )
        )

    def test_existing_database_columns_are_preserved(self):
        conn = main.db.get_conn()
        for table, expected_columns in CONTRACT["database_tables"].items():
            actual_columns = {
                row["name"] for row in conn.execute(f"PRAGMA table_info({table})")
            }
            self.assertEqual(set(), set(expected_columns) - actual_columns, table)

    def test_existing_model_fields_are_preserved(self):
        for model_name, expected_fields in CONTRACT["pydantic_models"].items():
            model = getattr(main, model_name)
            self.assertEqual(
                set(),
                set(expected_fields) - set(model.model_fields),
                model_name,
            )

    def test_plugin_global_namespaces_and_hooks_are_preserved(self):
        app_source = (
            REPO_ROOT / "backend" / "static" / "app.js"
        ).read_text(encoding="utf-8")
        self.assertIn("window.ChatRawPlugin = {", app_source)

        plugin_block = app_source.split("window.ChatRawPlugin = {", 1)[1].split(
            "// Load enabled plugins", 1
        )[0]
        for namespace in CONTRACT["plugin_api"]["namespaces"]:
            self.assertRegex(plugin_block, rf"\b{re.escape(namespace)}\s*:")

        hooks_block = app_source.split("pluginHooks: {", 1)[1].split(
            "loadedPluginDeps:", 1
        )[0]
        for hook in CONTRACT["plugin_api"]["available_hooks"]:
            self.assertRegex(hooks_block, rf"\b{re.escape(hook)}\s*:")

    def test_bundled_plugin_manifest_contracts_are_preserved(self):
        plugin_root = REPO_ROOT / "Plugins" / "Plugin_market"
        for plugin_id, expected in CONTRACT["bundled_plugins"].items():
            manifest = json.loads(
                (plugin_root / plugin_id / "manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(plugin_id, manifest["id"])
            self.assertEqual(expected["type"], manifest["type"])
            self.assertEqual(expected["hooks"], manifest["hooks"])

    def test_frontend_entrypoint_uses_generated_assets(self):
        frontend = CONTRACT["frontend_build"]
        index = (REPO_ROOT / frontend["html_entrypoint"]).read_text(
            encoding="utf-8"
        )
        self.assertIn(Path(frontend["javascript_artifact"]).name, index)
        self.assertIn(Path(frontend["stylesheet_artifact"]).name, index)
        self.assertIn(f'x-data="{frontend["alpine_root"]}"', index)

    def test_core_database_crud_flow(self):
        with tempfile.TemporaryDirectory(prefix="chatraw-contract-db-") as tmp:
            database = main.Database(os.path.join(tmp, "chatraw.db"))
            chat = database.create_chat("Contract chat")
            user_message = database.add_message(chat.id, "user", "hello")
            assistant_message = database.add_message(
                chat.id, "assistant", "world"
            )
            document_id = database.save_document("contract.txt", "content")

            self.assertTrue(database.chat_exists(chat.id))
            self.assertEqual(
                [user_message.id, assistant_message.id],
                [message.id for message in database.get_messages(chat.id)],
            )
            self.assertEqual(
                ["contract.txt"],
                [document["filename"] for document in database.get_documents()],
            )

            database.delete_document(document_id)
            database.delete_chat(chat.id)
            self.assertFalse(database.chat_exists(chat.id))
            self.assertEqual([], database.get_documents())


class V221StreamingCompatibilityTests(unittest.TestCase):
    def test_chat_stream_remains_newline_delimited_json(self):
        async def fake_chat_stream(*args):
            del args
            yield json.dumps({"content": "hello"})
            yield json.dumps({"done": True})

        async def exercise():
            with patch(
                "backend.main.prepare_chat_submission",
                new=AsyncMock(return_value=streaming_submission()),
            ), patch.object(
                main.llm_service,
                "chat_stream",
                new=fake_chat_stream,
            ):
                response = await main.chat(JsonRequest())
                return response, await collect_stream(response)

        response, chunks = asyncio.run(exercise())
        self.assertEqual("text/event-stream", response.media_type)
        self.assertEqual(
            [
                json.dumps({"chat_id": "chat-contract"}) + "\n",
                json.dumps({"content": "hello"}) + "\n",
                json.dumps({"done": True}) + "\n",
            ],
            chunks,
        )
        self.assertTrue(all(not chunk.startswith("data:") for chunk in chunks))

    def test_hermes_stream_remains_newline_delimited_json(self):
        async def fake_hermes_stream(submission, config):
            del submission, config
            yield json.dumps({"content": "hello"})
            yield json.dumps({"done": True})

        async def exercise():
            with patch(
                "backend.main.validate_hermes_request_origin"
            ), patch(
                "backend.main.validate_hermes_chat_body"
            ), patch(
                "backend.main.get_hermes_config",
                return_value={
                    "api_mode": main.HERMES_API_MODE_CHAT_COMPLETIONS
                },
            ), patch(
                "backend.main.prepare_chat_submission",
                new=AsyncMock(return_value=streaming_submission()),
            ), patch(
                "backend.main._stream_hermes_chat_chunks",
                new=fake_hermes_stream,
            ):
                response = await main.hermes_chat(JsonRequest())
                return response, await collect_stream(response)

        response, chunks = asyncio.run(exercise())
        self.assertEqual("text/event-stream", response.media_type)
        self.assertEqual(
            [
                json.dumps({"chat_id": "chat-contract"}) + "\n",
                json.dumps({"content": "hello"}) + "\n",
                json.dumps({"done": True}) + "\n",
            ],
            chunks,
        )
        self.assertTrue(all(not chunk.startswith("data:") for chunk in chunks))
