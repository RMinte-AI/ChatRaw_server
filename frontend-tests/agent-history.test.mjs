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
globalThis.document = {
    querySelector() { return null; }
};

vm.runInThisContext(
    fs.readFileSync('backend/static/app.js', 'utf8'),
    { filename: 'app.js' }
);

function createHost() {
    const host = app();
    host.chats = [
        { id: 'chat-1', title: 'First' },
        { id: 'chat-2', title: 'Second' }
    ];
    host.currentChatId = 'chat-1';
    host.messages = [{ role: 'user', content: 'keep when retained' }];
    host.isGenerating = false;
    host.showToast = (message, type) => {
        host.toast = { message, type };
    };
    host.announceAgentChatChange = (action, chatId) => {
        host.announcement = { action, chatId };
    };
    host.$nextTick = callback => callback();
    return host;
}

test('inline rename opens with the current title and selects the input', () => {
    const host = createHost();
    const input = {
        focusCalled: false,
        selectCalled: false,
        focus() { this.focusCalled = true; },
        select() { this.selectCalled = true; }
    };
    globalThis.document.querySelector = () => input;

    host.startRenameChat(host.chats[0]);

    assert.equal(host.renamingChatId, 'chat-1');
    assert.equal(host.renameChatDraft, 'First');
    assert.equal(input.focusCalled, true);
    assert.equal(input.selectCalled, true);
});

test('inline rename rejects blank text and keeps the draft', async () => {
    const host = createHost();
    host.renamingChatId = 'chat-1';
    host.renameChatDraft = '   ';
    let requests = 0;
    globalThis.fetch = async () => { requests += 1; };

    await host.submitRenameChat(host.chats[0]);

    assert.equal(requests, 0);
    assert.equal(host.renamingChatId, 'chat-1');
    assert.equal(host.renameChatDraft, '   ');
    assert.deepEqual(host.toast, {
        message: 'Enter a conversation title.',
        type: 'error'
    });
});

test('inline rename failure preserves the draft for retry', async () => {
    const host = createHost();
    host.renamingChatId = 'chat-1';
    host.renameChatDraft = 'Retry me';
    globalThis.fetch = async () => ({
        ok: false,
        async json() { return { code: 'rename_failed' }; }
    });

    await host.submitRenameChat(host.chats[0]);

    assert.equal(host.chats[0].title, 'First');
    assert.equal(host.renamingChatId, 'chat-1');
    assert.equal(host.renameChatDraft, 'Retry me');
    assert.equal(host.isRenamingChat, false);
    assert.deepEqual(host.toast, { message: 'Rename failed', type: 'error' });
});

test('inline rename saves once, updates title, and broadcasts', async () => {
    const host = createHost();
    host.renamingChatId = 'chat-1';
    host.renameChatDraft = '  New title  ';
    const requests = [];
    globalThis.fetch = async (...args) => {
        requests.push(args);
        return {
            ok: true,
            async json() { return { success: true, title: 'New title' }; }
        };
    };

    await host.submitRenameChat(host.chats[0]);

    assert.deepEqual(requests, [[
        '/api/agent/chats/chat-1',
        {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: 'New title' })
        }
    ]]);
    assert.equal(host.chats[0].title, 'New title');
    assert.equal(host.renamingChatId, null);
    assert.equal(host.renameChatDraft, '');
    assert.deepEqual(host.announcement, {
        action: 'renamed',
        chatId: 'chat-1'
    });
});

test('closing or selecting cancels an unsubmitted inline rename', async () => {
    const host = createHost();
    host.renamingChatId = 'chat-1';
    host.renameChatDraft = 'Unsaved';
    host.agentHistoryOpen = true;
    host.toggleAgentHistory();
    assert.equal(host.renamingChatId, null);
    assert.equal(host.renameChatDraft, '');

    host.renamingChatId = 'chat-1';
    host.renameChatDraft = 'Unsaved again';
    host.loadMessages = async () => {};
    await host.selectChat('chat-2');
    assert.equal(host.renamingChatId, null);
    assert.equal(host.renameChatDraft, '');
});

test('clear cancellation leaves state and network untouched', async () => {
    const host = createHost();
    const requests = [];
    globalThis.confirm = () => false;
    globalThis.fetch = async (...args) => { requests.push(args); };

    await host.clearAllChats();

    assert.equal(requests.length, 0);
    assert.equal(host.currentChatId, 'chat-1');
    assert.equal(host.isClearingChats, false);
});

test('full clear uses one collection DELETE and clears deleted current chat', async () => {
    const host = createHost();
    const requests = [];
    globalThis.confirm = () => true;
    globalThis.fetch = async (...args) => {
        requests.push(args);
        return {
            ok: true,
            async json() {
                return { success: true, deleted_count: 2, retained_count: 0 };
            }
        };
    };
    host.loadAgentChats = async () => {
        host.chats = [];
        return true;
    };

    await host.clearAllChats();

    assert.deepEqual(requests, [['/api/agent/chats', { method: 'DELETE' }]]);
    assert.equal(host.currentChatId, null);
    assert.deepEqual(host.messages, []);
    assert.deepEqual(host.toast, {
        message: 'All chats cleared',
        type: 'success'
    });
    assert.deepEqual(host.announcement, { action: 'cleared', chatId: '' });
});

test('partial clear reloads server truth and keeps the retained current chat', async () => {
    const host = createHost();
    globalThis.confirm = () => true;
    globalThis.fetch = async () => ({
        ok: true,
        async json() {
            return { success: true, deleted_count: 1, retained_count: 1 };
        }
    });
    host.loadAgentChats = async () => {
        host.chats = [{ id: 'chat-1', title: 'First' }];
        return true;
    };

    await host.clearAllChats();

    assert.equal(host.currentChatId, 'chat-1');
    assert.deepEqual(
        host.messages,
        [{ role: 'user', content: 'keep when retained' }]
    );
    assert.deepEqual(host.toast, {
        message: 'Deleted 1 conversations; kept 1 with active work.',
        type: 'success'
    });
});

test('partial clear localizes retained-count feedback in Chinese', async () => {
    const host = createHost();
    host.lang = 'zh';
    globalThis.confirm = () => true;
    globalThis.fetch = async () => ({
        ok: true,
        async json() {
            return { success: true, deleted_count: 1, retained_count: 1 };
        }
    });
    host.loadAgentChats = async () => {
        host.chats = [{ id: 'chat-1', title: 'First' }];
        return true;
    };

    await host.clearAllChats();

    assert.deepEqual(host.toast, {
        message: '已删除 1 个会话；1 个正在运行的会话已保留。',
        type: 'success'
    });
});

test('clear reports a failed server-truth refresh without inventing local state', async () => {
    const host = createHost();
    globalThis.confirm = () => true;
    globalThis.fetch = async () => ({
        ok: true,
        async json() {
            return { success: true, deleted_count: 2, retained_count: 0 };
        }
    });
    host.loadAgentChats = async () => false;

    await host.clearAllChats();

    assert.equal(host.currentChatId, 'chat-1');
    assert.deepEqual(host.chats.map(chat => chat.id), ['chat-1', 'chat-2']);
    assert.deepEqual(host.toast, {
        message: 'The delete requests finished, but conversation history could not be refreshed. Try again.',
        type: 'error'
    });
    assert.equal(host.announcement, undefined);
});

test('clear ignores duplicate invocation while request is in flight', async () => {
    const host = createHost();
    globalThis.confirm = () => true;
    let releaseRequest;
    const response = new Promise(resolve => {
        releaseRequest = () => resolve({
            ok: true,
            async json() {
                return { success: true, deleted_count: 2, retained_count: 0 };
            }
        });
    });
    let requestCount = 0;
    globalThis.fetch = async () => {
        requestCount += 1;
        return response;
    };
    host.loadAgentChats = async () => {
        host.chats = [];
        return true;
    };

    const first = host.clearAllChats();
    await host.clearAllChats();
    assert.equal(requestCount, 1);
    assert.equal(host.isClearingChats, true);
    releaseRequest();
    await first;
    assert.equal(host.isClearingChats, false);
});
