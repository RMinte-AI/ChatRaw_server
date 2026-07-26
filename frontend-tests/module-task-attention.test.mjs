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
        state: 'running',
        artifacts: [],
        ...overrides
    };
}

test('only task-center work appears in the global attention entry', () => {
    const instance = app();
    instance.upsertModuleTask(task({ task_id: 'task-center' }), {
        presentation: 'task_center'
    });
    instance.upsertModuleTask(task({ task_id: 'conversation' }), {
        presentation: 'conversation'
    });
    instance.upsertModuleTask(task({ task_id: 'embedded' }), {
        presentation: 'embedded'
    });

    assert.deepEqual(
        instance.moduleTaskAttentionViews().map(
            view => view.task.task_id
        ),
        ['task-center']
    );
});

test('a viewed terminal task leaves the global attention entry', () => {
    const instance = app();
    const view = instance.upsertModuleTask(task(), {
        presentation: 'task_center',
        select: true
    });

    instance.applyModuleTaskEvent('task-1', {
        id: 1,
        event: 'task.terminal',
        data: { state: 'succeeded' }
    });
    assert.equal(instance.moduleTaskAttentionViews().length, 0);

    instance.closeModuleTask();
    assert.equal(view.attentionPending, false);
    assert.equal(instance.moduleTaskAttentionViews().length, 0);
});

test('an unseen terminal result remains actionable until viewed', () => {
    const instance = app();
    const view = instance.upsertModuleTask(task(), {
        presentation: 'task_center'
    });
    view.show = false;

    instance.applyModuleTaskEvent('task-1', {
        id: 1,
        event: 'task.terminal',
        data: { state: 'failed', outcome_code: 'upstream_failed' }
    });
    assert.equal(instance.moduleTaskAttentionViews().length, 1);

    instance.openModuleTaskCenter();
    instance.closeModuleTask();
    assert.equal(instance.moduleTaskAttentionViews().length, 0);
});

test('cancelled tasks disappear without leaving attention behind', () => {
    const instance = app();
    instance.upsertModuleTask(task(), {
        presentation: 'task_center'
    });

    instance.applyModuleTaskEvent('task-1', {
        id: 1,
        event: 'task.terminal',
        data: { state: 'cancelled' }
    });
    assert.equal(instance.moduleTaskAttentionViews().length, 0);
});

test('task trigger binds to actionable count instead of task history', () => {
    const markup = fs.readFileSync(
        'backend/static/index.html',
        'utf8'
    );
    const trigger = markup.slice(
        markup.indexOf('class="module-task-center-trigger"'),
        markup.indexOf('<div class="modal-overlay module-task-modal"')
    );

    assert.match(trigger, /moduleTaskAttentionViews\(\)\.length/);
    assert.doesNotMatch(trigger, /moduleTaskOrder\.length/);
});
