import json
import shutil
import subprocess
import textwrap
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
        self.assertEqual(contract["version"], "1.2.0")
        self.assertEqual(contract["global"], "window.ChatRaw.modules")
        self.assertEqual(
            set(contract["methods"]),
            {
                "getFeatureStatus",
                "startTask",
                "listTasks",
                "getTask",
                "subscribe",
                "cancelTask",
                "respondApproval",
                "downloadArtifact",
                "uploadTaskResource",
                "getTaskResourceView",
                "downloadTaskResource",
            },
        )
        self.assertIn(
            "supports_resources",
            contract["$defs"]["FeatureAction"]["required"],
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
        self.assertEqual(
            contract["$defs"]["StartTaskOptions"]["properties"][
                "presentation"
            ]["default"],
            "task_center",
        )
        self.assertIn(
            "frontend_integration",
            contract["$defs"]["FeatureStatus"]["required"],
        )

    def test_browser_sdk_preserves_legacy_plugin_global(self):
        source = APP_PATH.read_text(encoding="utf-8")
        self.assertIn("window.ChatRaw.modules = modulesSdk", source)
        self.assertIn("window.ChatRawPlugin = {", source)
        self.assertIn("'Last-Event-ID': String(cursor)", source)
        self.assertIn("credentials: 'same-origin'", source)
        self.assertIn("module_event_stream_incomplete", source)
        self.assertIn("const MODULE_SDK_VERSION = '1.2.0'", source)
        self.assertIn(
            "fetch('/api/module-task-resources'",
            source,
        )
        self.assertIn(
            "?disposition=${encodeURIComponent(disposition)}",
            source,
        )
        self.assertIn(
            "await response.body.cancel()",
            source,
        )
        self.assertIn("'task_resource_view_failed'", source)
        self.assertIn("'task_resource_download_failed'", source)
        self.assertNotIn("module-task-resources", source.split(
            "window.ChatRawPlugin = {", 1
        )[1])
        for method in json.loads(
            CONTRACT_PATH.read_text(encoding="utf-8")
        )["methods"]:
            self.assertRegex(source, rf"\b{method}(?::|,)")

    @unittest.skipUnless(shutil.which("node"), "Node.js is required")
    def test_resource_sdk_runtime_validation_and_error_semantics(self):
        script = textwrap.dedent(
            f"""
            const assert = require('node:assert/strict');
            const fs = require('node:fs');
            const vm = require('node:vm');

            global.marked = {{ setOptions() {{}} }};
            global.localStorage = {{
                getItem() {{ return null; }},
                setItem() {{}},
                removeItem() {{}}
            }};
            global.window = {{
                matchMedia() {{ return {{ matches: false }}; }}
            }};
            global.document = {{
                createElement() {{
                    return {{ click() {{}}, set href(value) {{}}, set download(value) {{}} }};
                }}
            }};

            vm.runInThisContext(
                fs.readFileSync({json.dumps(str(APP_PATH))}, 'utf8'),
                {{ filename: 'app.js' }}
            );
            const instance = app();
            instance.initPluginSystem();
            const sdk = window.ChatRaw.modules;
            const requests = [];
            const response = (status, payload, headers = {{}}, body = null) => ({{
                ok: status >= 200 && status < 300,
                status,
                body,
                async json() {{ return payload; }},
                headers: {{
                    get(name) {{ return headers[name.toLowerCase()] ?? null; }}
                }}
            }});
            const queue = [];
            global.fetch = async (url, options = {{}}) => {{
                requests.push({{ url, options }});
                assert.ok(queue.length, `unexpected fetch: ${{url}}`);
                return queue.shift();
            }};

            (async () => {{
                let cancelledBodies = 0;
                const probeBody = () => ({{
                    async cancel() {{ cancelledBodies += 1; }}
                }});
                const file = new Blob(['x'], {{ type: 'text/plain' }});
                Object.defineProperty(file, 'name', {{ value: 'input.txt' }});

                queue.push(response(200, {{ resource_id: 'missing-fields' }}));
                await assert.rejects(
                    sdk.uploadTaskResource(file),
                    error => error.code === 'task_resource_upload_response_invalid'
                        && error.status === 502
                );

                const validUpload = {{
                    resource_id: 'res_1',
                    filename: 'input.txt',
                    media_type: 'text/plain',
                    size: 1,
                    sha256: 'a'.repeat(64),
                    expires_at: '2026-07-26T00:00:00Z'
                }};
                queue.push(response(200, validUpload));
                assert.deepEqual(
                    await sdk.uploadTaskResource(file),
                    validUpload
                );

                queue.push(response(
                    410,
                    {{ detail: 'Resource expired', code: 'task_resource_expired' }}
                ));
                await assert.rejects(
                    sdk.getTaskResourceView('task/a', 'ref ?/#'),
                    error => error.message === 'Resource expired'
                        && error.code === 'task_resource_expired'
                        && error.status === 410
                );
                assert.equal(
                    requests.at(-1).url,
                    '/api/module-tasks/task%2Fa/resources/ref%20%3F%2F%23'
                        + '?disposition=inline'
                );

                queue.push(response(200, null, {{
                    'content-disposition': 'attachment; filename="report.docx"',
                    'content-type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'content-length': '42'
                }}, probeBody()));
                await assert.rejects(
                    sdk.getTaskResourceView('task', 'office'),
                    error => error.code === 'task_resource_preview_unavailable'
                        && error.status === 415
                );

                queue.push(response(200, null, {{
                    'content-disposition': "inline; filename*=UTF-8''hello%20world.pdf",
                    'content-type': 'application/pdf',
                    'content-length': '7'
                }}, probeBody()));
                const view = await sdk.getTaskResourceView('task', 'pdf');
                assert.equal(view.filename, 'hello world.pdf');
                assert.equal(view.disposition, 'inline');
                assert.equal(view.mime, 'application/pdf');
                assert.equal(view.size, 7);
                assert.equal(requests.at(-1).options.method, 'GET');

                queue.push(response(200, null, {{
                    'content-disposition': 'inline; filename="empty.txt"',
                    'content-type': 'text/plain',
                    'content-length': '0'
                }}, probeBody()));
                const emptyView = await sdk.getTaskResourceView(
                    'task',
                    'empty'
                );
                assert.equal(emptyView.size, 0);
                assert.equal(emptyView.disposition, 'inline');

                queue.push(response(200, null, {{
                    'content-type': 'text/plain',
                    'content-length': '3'
                }}, probeBody()));
                await assert.rejects(
                    sdk.getTaskResourceView('task', 'missing-disposition'),
                    error => error.code === 'task_resource_view_failed'
                        && error.status === 502
                );
                assert.equal(cancelledBodies, 4);

                queue.push(response(
                    403,
                    {{ detail: 'Forbidden', code: 'task_resource_forbidden' }}
                ));
                await assert.rejects(
                    sdk.downloadTaskResource('task', 'secret'),
                    error => error.message === 'Forbidden'
                        && error.code === 'task_resource_forbidden'
                        && error.status === 403
                );
                assert.equal(queue.length, 0);
            }})().catch(error => {{
                console.error(error);
                process.exitCode = 1;
            }});
            """
        )
        result = subprocess.run(
            ["node", "-e", script],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )

    def test_core_owns_task_ui_and_persistence_is_identifier_only(self):
        source = APP_PATH.read_text(encoding="utf-8")
        markup = INDEX_PATH.read_text(encoding="utf-8")
        self.assertIn("Core module task center", markup)
        self.assertIn("moduleTaskViews()", markup)
        self.assertIn("selectModuleTask(view.task.task_id)", markup)
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
        self.assertIn("moduleTasks: {}", source)
        self.assertIn("upsertModuleTask(task", source)
        self.assertIn("presentation === 'task_center'", source)
        self.assertIn(
            "if (presentation === 'task_center')",
            source,
        )
        self.assertIn("listTasks: async (filters = {})", source)
        self.assertIn(
            "(left.order ?? 100) - (right.order ?? 100)",
            source,
        )
        self.assertNotIn(
            "window.ChatRaw.modules.subscribe(taskId);\n                        return;",
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
