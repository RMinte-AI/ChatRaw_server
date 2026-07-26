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
    const expandedButton = page.locator('.btn-new-chat');
    if (!await expandedButton.isVisible()) {
        const mobileMenu = page.locator('.mobile-header .btn-icon');
        if (await mobileMenu.isVisible()) {
            await mobileMenu.click();
            await expect(expandedButton).toBeVisible();
        }
    }
    if (await expandedButton.isVisible()) {
        await expandedButton.click();
    } else {
        await page.locator('.btn-new-chat-collapsed:visible').click();
    }
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
    ).toBeLessThan(2);
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


async function setSidebarFeatureStressState(page, {
    collapsed = false,
    count = 24
} = {}) {
    await page.evaluate(({ collapsed: nextCollapsed, count: entryCount }) => {
        const state = document.body._x_dataStack[0];
        state.sidebarCollapsed = nextCollapsed;
        state.residentIntegrations = [];
        state.pluginWorkspaceDefinitions = {};
        state.pluginToolbarButtons = Array.from(
            { length: entryCount },
            (_, index) => ({
                fullId: `browser-sidebar:entry-${index}`,
                pluginId: 'browser-sidebar',
                id: `entry-${index}`,
                icon: 'ri-tools-line',
                label: { en: `Browser feature ${index}` },
                onClick: () => {},
                order: index,
                placement: 'sidebar',
                status: null,
                disabled: false,
                active: false,
                loading: false
            })
        );
        state.chats = [{
            id: 'sidebar-layout-chat',
            title: 'Sidebar layout chat'
        }];
    }, { collapsed, count });
    await page.waitForFunction(
        ({ collapsed: nextCollapsed, count: entryCount }) => {
            const container = document.querySelector(
                nextCollapsed
                    ? '.resident-sidebar-collapsed'
                    : '.resident-sidebar-entries'
            );
            return (
                document.body._x_dataStack[0].sidebarCollapsed
                    === nextCollapsed
                && container?.querySelectorAll(
                    '.plugin-sidebar-entry, .plugin-sidebar-entry-collapsed'
                ).length === entryCount
            );
        },
        { collapsed, count }
    );
}

async function measureSidebarFeatureLayout(page, collapsed = false) {
    return page.evaluate(nextCollapsed => {
        const rectangle = selector => {
            const element = document.querySelector(selector);
            const box = element?.getBoundingClientRect();
            return box
                ? {
                    top: box.top,
                    bottom: box.bottom,
                    height: box.height
                }
                : null;
        };
        const featureArea = document.querySelector('.sidebar-feature-area');
        return {
            sidebar: rectangle('.sidebar'),
            feature: {
                ...rectangle('.sidebar-feature-area'),
                clientHeight: featureArea.clientHeight,
                scrollHeight: featureArea.scrollHeight,
                overflowY: getComputedStyle(featureArea).overflowY
            },
            firstFeatureEntry: rectangle(
                nextCollapsed
                    ? '.resident-sidebar-collapsed .plugin-sidebar-entry-collapsed'
                    : '.resident-sidebar-entries .plugin-sidebar-entry'
            ),
            divider: rectangle('.sidebar-section-divider'),
            newChat: rectangle(
                nextCollapsed
                    ? '.btn-new-chat-collapsed'
                    : '.btn-new-chat'
            ),
            chatList: nextCollapsed ? null : rectangle('.chat-list'),
            clearAll: nextCollapsed ? null : rectangle('.btn-clear-all'),
            footer: nextCollapsed ? null : rectangle('.sidebar-footer'),
            collapsedPlugins: nextCollapsed
                ? rectangle('.sidebar-plugins-collapsed')
                : null
        };
    }, collapsed);
}

function expectContained(inner, outer) {
    expect(inner.top).toBeGreaterThanOrEqual(outer.top - 1);
    expect(inner.bottom).toBeLessThanOrEqual(outer.bottom + 1);
}


test('sidebar feature overflow keeps chat controls reachable', async ({
    page,
    request
}) => {
    const consoleErrors = await loginAndConfigureModel(page, request);
    await page.setViewportSize({ width: 900, height: 600 });

    await setSidebarFeatureStressState(page, { count: 0 });
    await expect(page.locator('.sidebar-feature-area')).toBeHidden();
    await expect(page.locator('.sidebar-section-divider')).toBeHidden();
    await expect(page.locator('.btn-new-chat')).toBeVisible();

    await setSidebarFeatureStressState(page);
    await expect(page.locator('.sidebar-feature-area')).toBeVisible();
    const desktop = await measureSidebarFeatureLayout(page);
    expect(desktop.feature.scrollHeight).toBeGreaterThan(
        desktop.feature.clientHeight
    );
    expect(desktop.feature.overflowY).toBe('auto');
    expectContained(desktop.firstFeatureEntry, desktop.feature);
    expect(desktop.feature.bottom).toBeLessThanOrEqual(desktop.divider.top);
    expect(desktop.divider.bottom).toBeLessThanOrEqual(desktop.newChat.top);
    expect(desktop.chatList.height).toBeGreaterThanOrEqual(47);
    for (const element of [
        desktop.newChat,
        desktop.chatList,
        desktop.clearAll,
        desktop.footer
    ]) {
        expectContained(element, desktop.sidebar);
    }

    await setSidebarFeatureStressState(page, { collapsed: true });
    await expect(page.locator('.btn-new-chat-collapsed')).toBeVisible();
    const collapsed = await measureSidebarFeatureLayout(page, true);
    expect(collapsed.feature.scrollHeight).toBeGreaterThan(
        collapsed.feature.clientHeight
    );
    expect(collapsed.feature.overflowY).toBe('auto');
    expectContained(collapsed.firstFeatureEntry, collapsed.feature);
    expect(collapsed.feature.bottom).toBeLessThanOrEqual(
        collapsed.divider.top
    );
    expect(collapsed.divider.bottom).toBeLessThanOrEqual(
        collapsed.newChat.top
    );
    expectContained(collapsed.newChat, collapsed.sidebar);
    expectContained(collapsed.collapsedPlugins, collapsed.sidebar);
    expect(collapsed.newChat.bottom).toBeLessThanOrEqual(
        collapsed.collapsedPlugins.top
    );

    await page.setViewportSize({ width: 390, height: 500 });
    await page.waitForFunction(() => {
        const state = document.body._x_dataStack[0];
        return state.isMobileView && state.sidebarCollapsed;
    });
    await setSidebarFeatureStressState(page, { collapsed: true });
    await page.locator('.mobile-header .btn-icon').click();
    await expect(page.locator('.btn-new-chat')).toBeVisible();
    const mobile = await measureSidebarFeatureLayout(page);
    expect(mobile.feature.scrollHeight).toBeGreaterThan(
        mobile.feature.clientHeight
    );
    expect(mobile.feature.overflowY).toBe('auto');
    expectContained(mobile.firstFeatureEntry, mobile.feature);
    expect(mobile.chatList.height).toBeGreaterThanOrEqual(47);
    for (const element of [
        mobile.newChat,
        mobile.chatList,
        mobile.clearAll,
        mobile.footer
    ]) {
        expectContained(element, mobile.sidebar);
    }
    expect(consoleErrors).toEqual([]);
});


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
        const response = await fetch('/api/v1/chats?limit=100');
        const payload = await response.json();
        const chat = payload.items.find(item => item.id === id);
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
