import { expect, test } from '@playwright/test';


const username = 't6-admin';
const password = 'T6-acceptance-password-2026';
const modelPort = 51152;


async function loginAndConfigureModel(page, request) {
    const consoleErrors = [];
    page.on('console', message => {
        if (message.type() === 'error') consoleErrors.push(message.text());
    });
    await expect.poll(async () => {
        const response = await request.get('/api/setup/status');
        return (await response.json()).setup_required;
    }, {
        timeout: 120_000
    }).toBe(false);
    await page.goto('/login');
    await page.getByLabel(/Username|用户名/).fill(username);
    await page.getByLabel(/Password|密码/).fill(password);
    await page.getByRole('button', { name: /Sign in|登录/ }).click();
    await expect(page).toHaveURL(/\/$/);
    await page.locator('.agent-launcher').click();
    await expect(page.locator('textarea[x-ref="inputBox"]')).toBeVisible();
    await page.evaluate(async ({ port }) => {
        const response = await fetch('/api/models', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id: 'default-chat',
                name: 'Browser deterministic chat model',
                api_url: `http://127.0.0.1:${port}/v1`,
                model_id: 't7-model',
                context_length: 32768,
                max_output: 4096,
                type: 'chat',
                capability: {
                    vision: false,
                    reasoning: false,
                    tools: false
                },
                api_key_action: 'clear'
            })
        });
        if (!response.ok) {
            throw new Error(`model configuration failed: ${response.status}`);
        }
        const models = await (await fetch('/api/models')).json();
        if (!models.some(model => (
            model.id === 'default-chat'
            && model.api_url === `http://127.0.0.1:${port}/v1`
        ))) {
            throw new Error('configured model was not persisted');
        }
    }, { port: modelPort });
    return consoleErrors;
}

async function createNewChat(page) {
    await page.evaluate(() => document.body._x_dataStack[0].createNewChat());
    await expect.poll(() => page.evaluate(
        () => document.body._x_dataStack?.[0]?.currentChatId || ''
    )).not.toBe('');
    return page.evaluate(
        () => document.body._x_dataStack[0].currentChatId
    );
}

async function waitForReferenceModule(page) {
    await expect.poll(() => page.evaluate(async () => {
        const response = await fetch('/api/admin/modules');
        if (!response.ok) return '';
        const payload = await response.json();
        const module = payload.modules.find(
            item => item.module_id === 'chatraw.reference.echo'
        );
        if (!module) return '';
        return [
            module.lifecycle_state,
            module.health_status,
            module.ready_status,
            module.config_status
        ].join(':');
    }), {
        timeout: 120_000
    }).toBe('enabled:healthy:ready:configured');
}

async function reloadAndSelectChat(page, chatId) {
    await page.reload();
    await expect.poll(() => page.evaluate(id => {
        const state = document.body._x_dataStack?.[0];
        return Boolean(
            window.ChatRaw?.modules
            && state?.me
            && state.chats?.some(chat => chat.id === id)
        );
    }, chatId)).toBe(true);
    await page.locator('.agent-launcher').click();
    await page.evaluate(
        id => document.body._x_dataStack[0].selectChat(id),
        chatId
    );
}


async function measureRoleLayout(page) {
    return page.evaluate(() => {
        const last = selector => {
            const matches = [...document.querySelectorAll(selector)];
            return matches.at(-1);
        };
        const rectangle = element => {
            const { x, width } = element.getBoundingClientRect();
            return { x, width };
        };
        const assistantElement = last(
            '.messages .message.assistant:not([x-show])'
        );
        const userElement = last('.messages .message.user');
        return {
            assistantRow: rectangle(assistantElement),
            assistantAvatar: rectangle(
                assistantElement.querySelector('.message-avatar')
            ),
            assistantContent: rectangle(
                assistantElement.querySelector('.message-content')
            ),
            userRow: rectangle(userElement),
            userAvatar: rectangle(
                userElement.querySelector('.message-avatar')
            ),
            userContent: rectangle(
                userElement.querySelector('.message-content')
            )
        };
    });
}

function expectRoleLayout({
    assistantRow,
    assistantAvatar,
    assistantContent,
    userRow,
    userAvatar,
    userContent
}) {
    expect(assistantAvatar.x).toBeLessThan(assistantContent.x);
    expect(Math.abs(assistantAvatar.x - assistantRow.x)).toBeLessThan(2);
    expect(userAvatar.x).toBeGreaterThan(userContent.x);
    expect(
        Math.abs(
            userAvatar.x + userAvatar.width - (userRow.x + userRow.width)
        )
    ).toBeLessThan(2);
    expect(
        Math.abs(
            assistantContent.x + assistantContent.width
            - (userContent.x + userContent.width)
        )
    ).toBeLessThanOrEqual(16);
}

async function assertRoleLayout(page) {
    const assistant = page.locator(
        '.messages .message.assistant:not([x-show])'
    ).last();
    const user = page.locator('.messages .message.user').last();
    for (const locator of [
        assistant,
        assistant.locator('.message-avatar'),
        assistant.locator('.message-content'),
        user,
        user.locator('.message-avatar'),
        user.locator('.message-content')
    ]) {
        await expect(locator).toBeVisible();
    }
    expectRoleLayout(await measureRoleLayout(page));

    const originalViewport = page.viewportSize();
    const resizedWidth = originalViewport.width > 768 ? 900 : 320;
    if (resizedWidth === originalViewport.width) return;
    await page.setViewportSize({
        width: resizedWidth,
        height: originalViewport.height
    });
    await page.waitForFunction(
        expectedWidth => window.innerWidth === expectedWidth,
        resizedWidth
    );
    expectRoleLayout(await measureRoleLayout(page));
    await page.setViewportSize(originalViewport);
}


test('direct chat renders, titles, aligns, and survives reload', async ({
    page,
    request
}) => {
    const consoleErrors = await loginAndConfigureModel(page, request);
    const chatId = await createNewChat(page);
    const input = page.locator('textarea[x-ref="inputBox"]');
    await input.fill('browser direct hi');
    await page.getByRole('button', { name: /Send|发送/ }).click();

    await expect(page.locator('.messages .message.user').last()).toContainText(
        'browser direct hi'
    );
    await expect(
        page.locator('.messages .message.assistant:not([x-show])').last()
    ).toContainText(
        'T7 deterministic model response.'
    );
    await assertRoleLayout(page);

    await expect.poll(async () => page.evaluate(async id => {
        const response = await fetch('/api/agent/chats');
        const payload = await response.json();
        const chat = payload.find(item => item.id === id);
        return chat?.title || '';
    }, chatId)).not.toBe('New Chat');

    await reloadAndSelectChat(page, chatId);
    await expect(page.locator('.messages .message.user').last()).toContainText(
        'browser direct hi'
    );
    await expect(
        page.locator('.messages .message.assistant:not([x-show])').last()
    ).toContainText(
        'T7 deterministic model response.'
    );
    await assertRoleLayout(page);
    expect(consoleErrors).toEqual([]);
});


test('module conversation keeps one final body and survives reload', async ({
    page,
    request
}) => {
    const consoleErrors = await loginAndConfigureModel(page, request);
    await waitForReferenceModule(page);
    const chatId = await createNewChat(page);
    const taskId = await page.evaluate(async () => {
        const state = document.body._x_dataStack?.[0];
        if (!state?.currentChatId) {
            throw new Error('current chat is unavailable');
        }
        const task = await window.ChatRaw.modules.startTask({
            module_id: 'chatraw.reference.echo',
            action_id: 'echo.task',
            input: {
                text: 'browser module hello',
                steps: 4,
                delay_ms: 20
            },
            chat_id: state.currentChatId,
            user_message: 'browser module hello'
        }, {
            presentation: 'conversation'
        });
        return task.task_id;
    });

    await expect(page.locator('.messages .message.user').last()).toContainText(
        'browser module hello'
    );
    await expect(
        page.locator('.messages .message.assistant:not([x-show])').last()
    ).toContainText(
        'T6: browser module hello'
    );
    await expect(
        page.locator('.messages .message.assistant:not([x-show])')
    ).toHaveCount(1);
    await expect(page.locator('.module-run-block')).toHaveCount(1);
    await assertRoleLayout(page);

    await expect.poll(async () => page.evaluate(async id => {
        const response = await fetch(`/api/module-tasks/${id}`);
        return (await response.json()).state;
    }, taskId)).toBe('succeeded');

    await reloadAndSelectChat(page, chatId);
    await expect(page.locator('.messages .message.user')).toHaveCount(1);
    await expect(
        page.locator('.messages .message.assistant:not([x-show])')
    ).toHaveCount(1);
    await expect(
        page.locator('.messages .message.assistant:not([x-show])').last()
    ).toContainText(
        'T6: browser module hello'
    );
    await expect(page.locator('.module-run-block')).toHaveCount(1);
    await assertRoleLayout(page);
    expect(consoleErrors).toEqual([]);
});
