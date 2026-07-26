import json
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "backend" / "static" / "app.js"


class SendInterceptChatCreationTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is required")
    def test_first_message_creates_chat_before_send_interceptor(self):
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
                createElement() {{ return {{}}; }}
            }};

            vm.runInThisContext(
                fs.readFileSync({json.dumps(str(APP_PATH))}, 'utf8'),
                {{ filename: 'app.js' }}
            );
            const instance = app();
            instance.$nextTick = callback => callback();
            instance.scrollToBottom = () => {{}};
            const requests = [];
            global.fetch = async (url, options = {{}}) => {{
                requests.push({{ url, options }});
                assert.equal(url, '/api/chats');
                assert.equal(options.method, 'POST');
                return {{
                    ok: true,
                    async json() {{
                        return {{ id: 'chat-first', title: 'New Chat' }};
                    }}
                }};
            }};

            instance.prepareOutgoingMessage = async () => ({{
                message: 'first module message',
                activeSkillNames: []
            }});
            let interceptContext = null;
            instance.callSendInterceptors = async context => {{
                interceptContext = context;
                assert.equal(instance.currentChatId, 'chat-first');
                return {{
                    success: true,
                    handled: true,
                    userMessage: context.message
                }};
            }};
            instance.applySendInterceptResult = () => {{}};

            (async () => {{
                assert.equal(instance.currentChatId, null);
                await instance.sendMessage();
                assert.equal(requests.length, 1);
                assert.equal(instance.currentChatId, 'chat-first');
                assert.equal(instance.chats[0].id, 'chat-first');
                assert.equal(interceptContext.currentChatId, 'chat-first');
                assert.equal(interceptContext.message, 'first module message');
                assert.equal(instance.isGenerating, false);
                instance.messages = [];
                instance.applySendInterceptResult({{
                    success: true,
                    handled: true,
                    userMessage: false,
                    clearInput: false,
                    clearAttachments: false
                }}, 'must not be duplicated');
                assert.deepEqual(instance.messages, []);
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


if __name__ == "__main__":
    unittest.main()
