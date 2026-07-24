import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

import { JSDOM } from 'jsdom';


const root = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    '../../..'
);
const source = await fs.readFile(
    path.join(
        root,
        'ResidentIntegrations',
        'reference-module-workbench',
        'main.js'
    ),
    'utf8'
);

test('reference Resident registers and starts an embedded host task', async () => {
    const dom = new JSDOM('<!doctype html><body><main></main></body>', {
        runScripts: 'outside-only',
        url: 'http://chatraw.test/'
    });
    let definition;
    dom.window.ChatRawResident = {
        register(value) {
            definition = value;
        }
    };
    dom.window.eval(source);
    assert.equal(definition.id, 'reference-module-workbench');

    const calls = [];
    let unsubscribed = false;
    const cleanup = definition.mount({
        container: dom.window.document.querySelector('main'),
        moduleId: 'chatraw.reference.echo',
        modules: {
            async startTask(request, options) {
                calls.push({ request, options });
                return { task_id: 'task-1' };
            },
            subscribe(taskId, handlers) {
                assert.equal(taskId, 'task-1');
                handlers.onEvent({
                    event: 'output.delta',
                    data: { text: '<safe>' }
                });
                handlers.onEvent({
                    event: 'task.terminal',
                    data: { state: 'succeeded' }
                });
                return () => {
                    unsubscribed = true;
                };
            }
        },
        t: value => value.en,
        showToast() {},
        getCurrentChatId: () => 'chat-1'
    });
    const textarea = dom.window.document.querySelector('textarea');
    textarea.value = 'Resident input';
    dom.window.document.querySelector('form').dispatchEvent(
        new dom.window.Event('submit', {
            bubbles: true,
            cancelable: true
        })
    );
    await new Promise(resolve => dom.window.setTimeout(resolve, 0));

    assert.deepEqual(JSON.parse(JSON.stringify(calls)), [
        {
            request: {
                module_id: 'chatraw.reference.echo',
                action_id: 'echo.task',
                input: {
                    text: 'Resident input',
                    steps: 8,
                    delay_ms: 80,
                    require_approval: false,
                    create_artifact: true
                },
                chat_id: 'chat-1',
                user_message: 'Resident input'
            },
            options: { presentation: 'embedded' }
        }
    ]);
    assert.equal(
        dom.window.document.querySelector('pre').textContent,
        '<safe>'
    );
    assert.equal(dom.window.document.querySelector('pre').children.length, 0);

    cleanup();
    assert.equal(unsubscribed, true);
    assert.equal(dom.window.document.querySelector('main').children.length, 0);
});
