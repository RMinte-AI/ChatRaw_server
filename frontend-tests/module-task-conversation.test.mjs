import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

globalThis.marked = { setOptions() {} };
globalThis.localStorage = {
    getItem() { return null; },
    setItem() {},
    removeItem() {}
};
globalThis.window = {
    matchMedia() { return { matches: false }; }
};

vm.runInThisContext(
    fs.readFileSync('backend/static/app.js', 'utf8'),
    { filename: 'app.js' }
);

function task(overrides = {}) {
    return {
        task_id: 'task-1',
        module_id: 'chatraw.agent',
        action_id: 'agent.chat',
        chat_id: 'chat-1',
        state: 'running',
        user_message_id: 'user-1',
        assistant_message_id: null,
        last_event_id: 0,
        created_at: '2026-07-26T00:00:00Z',
        accepted_at: '2026-07-26T00:00:01Z',
        artifacts: [],
        ...overrides
    };
}

function activity(overrides = {}) {
    return {
        schema_version: '1',
        run_id: '11111111-1111-4111-8111-111111111111',
        activity_id: '22222222-2222-4222-8222-222222222222',
        kind: 'tool',
        state: 'started',
        title: 'Query page 1',
        detail: {
            tool_name: 'station_records',
            arguments_preview: '{"page":1,"size":20}',
            arguments_truncated: false
        },
        ...overrides
    };
}

test('conversation task owns one user message and one virtual assistant', () => {
    const instance = app();
    instance.currentChatId = 'chat-1';
    instance.$nextTick = callback => callback();
    instance.scrollToBottom = () => {};

    instance.attachConversationTask(task(), 'query yesterday exits');
    instance.attachConversationTask(task(), 'query yesterday exits');

    assert.deepEqual(
        instance.messages.map(message => message.role),
        ['user', 'assistant']
    );
    assert.equal(instance.messages[0].id, 'user-1');
    assert.equal(instance.messages[1].id, 'module-task:task-1');
    assert.equal(instance.messages[1].moduleTask.task.task_id, 'task-1');
});

test('activity snapshots upsert and a new run marks unfinished work', () => {
    const instance = app();
    const view = instance.upsertModuleTask(task());

    instance.applyModuleTaskEvent('task-1', {
        id: 1,
        event: 'activity.updated',
        data: activity()
    });
    instance.applyModuleTaskEvent('task-1', {
        id: 2,
        event: 'activity.updated',
        data: activity({
            state: 'succeeded',
            detail: {
                ...activity().detail,
                result_preview: '{"row_count":20}',
                result_truncated: false,
                duration_ms: 180
            }
        })
    });
    instance.applyModuleTaskEvent('task-1', {
        id: 2,
        event: 'activity.updated',
        data: activity({
            state: 'succeeded',
            detail: {
                ...activity().detail,
                result_preview: '{"row_count":20}',
                result_truncated: false,
                duration_ms: 180
            }
        })
    });

    assert.equal(instance.moduleTaskActivityList(view).length, 1);
    assert.equal(instance.moduleTaskActivityList(view)[0].state, 'succeeded');
    assert.equal(view.events.length, 2);

    instance.applyModuleTaskEvent('task-1', {
        id: 3,
        event: 'activity.updated',
        data: activity({
            activity_id: '55555555-5555-4555-8555-555555555555',
            title: 'Query page 2'
        })
    });
    instance.applyModuleTaskEvent('task-1', {
        id: 4,
        event: 'activity.updated',
        data: activity({
            run_id: '33333333-3333-4333-8333-333333333333',
            activity_id: '44444444-4444-4444-8444-444444444444'
        })
    });
    assert.equal(instance.moduleTaskActivityList(view).length, 3);
    assert.equal(
        instance.moduleTaskActivityList(view).find(
            item => item.activity_id
                === '55555555-5555-4555-8555-555555555555'
        ).interrupted,
        true
    );
});

test('persisted projection replaces the virtual message without duplication', () => {
    const instance = app();
    const running = task();
    instance.upsertModuleTask(running);
    const merged = instance.mergeConversationTaskMessages(
        [{
            id: 'user-1',
            chat_id: 'chat-1',
            role: 'user',
            content: 'query',
            created_at: running.created_at
        }],
        [running]
    );
    assert.equal(merged.length, 2);

    const finished = task({
        state: 'succeeded',
        assistant_message_id: 'assistant-1'
    });
    const projected = instance.mergeConversationTaskMessages(
        [
            merged[0],
            {
                id: 'assistant-1',
                chat_id: 'chat-1',
                role: 'assistant',
                content: '**20 rows**',
                created_at: '2026-07-26T00:00:02Z'
            }
        ],
        [finished]
    );

    assert.equal(projected.length, 2);
    assert.equal(projected[1].content, '**20 rows**');
    assert.equal(projected[1].moduleTask.task.state, 'succeeded');
    assert.equal(
        instance.messageContent(projected[1]),
        '**20 rows**'
    );
});

test('conversation output updates canonical virtual message content', () => {
    const instance = app();
    instance.currentChatId = 'chat-1';
    instance.$nextTick = callback => callback();
    instance.scrollToBottom = () => {};
    instance.attachConversationTask(task(), 'query');

    instance.applyModuleTaskEvent('task-1', {
        id: 1,
        event: 'output.delta',
        data: { text: 'first' }
    });
    instance.applyModuleTaskEvent('task-1', {
        id: 2,
        event: 'output.snapshot',
        data: { text: 'final stream value' }
    });

    assert.equal(instance.messages[1].content, 'final stream value');
    assert.equal(
        instance.messageContent(instance.messages[1]),
        'final stream value'
    );
});

test('task output is never a second rendered message body', () => {
    const instance = app();
    assert.equal(instance.messageContent({
        role: 'assistant',
        content: '',
        moduleTask: { output: 'must not render' }
    }), '');
});

test('conversation presentation requires a real chat binding before POST', async () => {
    const instance = app();
    instance.initPluginSystem();
    await assert.rejects(
        window.ChatRaw.modules.startTask({
            module_id: 'chatraw.agent',
            action_id: 'agent.chat',
            input: { message: 'hello' }
        }, {
            presentation: 'conversation'
        }),
        error => error.code === 'invalid_sdk_argument'
    );
});
