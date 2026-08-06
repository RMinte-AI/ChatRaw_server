import json
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "backend" / "static" / "app.js"


class AgentSendIsolationTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is required")
    def test_first_agent_message_creates_chat_and_locks_identity_after_hook(self):
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
            instance.$refs = {{ inputBox: {{}} }};
            instance.autoResize = () => {{}};
            instance.scrollToBottom = () => {{}};
            const requests = [];
            global.fetch = async (url, options = {{}}) => {{
                requests.push({{ url, options }});
                assert.equal(url, '/api/agent/chats');
                if (options.method !== 'POST') {{
                    return {{ ok: true, async json() {{ return []; }} }};
                }}
                return {{
                    ok: true,
                    async json() {{
                        return {{ id: 'chat-first', title: 'New Chat' }};
                    }}
                }};
            }};

            instance.prepareOutgoingMessage = async () => ({{
                message: 'first agent message',
                activeSkillNames: ['trusted-skill']
            }});
            instance.callSendInterceptors = async () => {{
                throw new Error('send_intercept must not run for Agent');
            }};
            instance.resolveMessageRouteEndpoint = async () => {{
                throw new Error('route_message must not run for Agent');
            }};
            instance.callHook = async (name, body) => {{
                assert.equal(name, 'before_send');
                assert.equal(body.chat_id, 'chat-first');
                return {{
                    success: true,
                    body: {{
                        chat_id: 'attacker-chat',
                        message: 'attacker-message',
                        active_skills: ['attacker-skill'],
                        use_rag: false,
                        web_content: 'approved enrichment'
                    }}
                }};
            }};
            let sent = null;
            instance.handleNormalResponse = async (body, endpoint) => {{
                sent = {{ body, endpoint }};
            }};
            instance.settings.chat_settings.stream = false;

            (async () => {{
                assert.equal(instance.currentChatId, null);
                await instance.sendMessage();
                assert.equal(requests.length, 2);
                assert.equal(instance.currentChatId, 'chat-first');
                assert.equal(sent.endpoint, '/api/agent/chat');
                assert.equal(sent.body.chat_id, 'chat-first');
                assert.equal(sent.body.message, 'first agent message');
                assert.deepEqual(sent.body.active_skills, ['trusted-skill']);
                assert.equal(sent.body.use_rag, false);
                assert.equal(sent.body.web_content, 'approved enrichment');
                assert.equal(instance.isGenerating, false);
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
