import { expect, test } from '@playwright/test';

const username = 't6-admin';
const password = 'T6-acceptance-password-2026';

async function login(page, request) {
    await expect.poll(async () => {
        const response = await request.get('/api/setup/status');
        return (await response.json()).setup_required;
    }, { timeout: 120_000 }).toBe(false);
    await page.goto('/login');
    await page.getByLabel(/Username|用户名/).fill(username);
    await page.getByLabel(/Password|密码/).fill(password);
    await page.getByRole('button', { name: /Sign in|登录/ }).click();
    await expect(page).toHaveURL(/\/$/);
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
    }), { timeout: 120_000 }).toBe('enabled:healthy:ready:configured');
}

async function replaceFixtureChats(page) {
    return page.evaluate(async () => {
        await fetch('/api/agent/chats', { method: 'DELETE' });
        const create = async title => {
            const chat = await (
                await fetch('/api/agent/chats', { method: 'POST' })
            ).json();
            await fetch(`/api/agent/chats/${encodeURIComponent(chat.id)}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title })
            });
            return chat.id;
        };
        return {
            active: await create('History Active'),
            idle: await create('History Idle')
        };
    });
}

async function openHistory(page) {
    if (!await page.locator('.chat-container').isVisible()) {
        await page.locator('.agent-launcher').click();
    }
    if (!await page.locator('.agent-history').isVisible()) {
        await page.getByRole('button', {
            name: /Conversation history|会话历史/
        }).click();
    }
}

test('settings shell clips its panes to the final corner geometry', async ({
    page,
    request
}) => {
    await login(page, request);
    await page.getByRole('button', { name: /Settings|设置/ }).click();
    const modal = page.locator(
        'body > .modal-overlay[aria-labelledby="settings-modal-title"] .settings-modal'
    );
    await expect(modal).toBeVisible();
    const geometry = await modal.evaluate(element => ({
        narrow: window.innerWidth <= 768,
        overflow: getComputedStyle(element).overflow,
        radius: getComputedStyle(element).borderRadius
    }));
    expect(geometry.overflow).toBe('hidden');
    expect(geometry.radius).toBe(geometry.narrow ? '0px' : '16px');
});

test('Agent history renames inline, syncs tabs, and atomically retains active work', async ({
    page,
    request,
    context
}) => {
    const nativeDialogs = [];
    await login(page, request);
    await waitForReferenceModule(page);
    const ids = await replaceFixtureChats(page);
    await page.reload();
    await openHistory(page);

    const chrome = await page.evaluate(() => ({
        headerIcons: [
            ...document.querySelectorAll(
                '.agent-header > div:last-child > button i'
            )
        ].map(icon => icon.className),
        historyTag: document.querySelector(
            '.agent-history > header > span'
        )?.tagName,
        titlePadding: getComputedStyle(
            document.querySelector('.agent-history .agent-chat-title')
        ).paddingInline,
        clearRight: document.querySelector(
            '.agent-history > header > button'
        )?.getBoundingClientRect().right,
        deleteRight: document.querySelector(
            '.agent-history > div > button:last-child'
        )?.getBoundingClientRect().right
    }));
    expect(chrome.headerIcons).toEqual([
        'ri-add-line',
        'ri-history-line',
        'ri-expand-diagonal-line',
        'ri-close-line'
    ]);
    expect(chrome.historyTag).toBe('SPAN');
    expect(chrome.titlePadding).toBe('12px');
    expect(chrome.clearRight).toBe(chrome.deleteRight);

    const peer = await context.newPage();
    await peer.goto('/');
    await openHistory(peer);

    let rejectRename = true;
    await page.route(`**/api/agent/chats/${ids.idle}`, async route => {
        if (route.request().method() === 'PATCH' && rejectRename) {
            rejectRename = false;
            await route.fulfill({
                status: 500,
                contentType: 'application/json',
                body: JSON.stringify({ code: 'rename_failed' })
            });
            return;
        }
        await route.continue();
    });

    let idleRow = page.locator(
        `.agent-history > div[data-chat-id="${ids.idle}"]`
    );
    await idleRow.getByRole('button', {
        name: /Rename conversation|重命名会话/
    }).click();
    let renameInput = idleRow.getByRole('textbox');
    await expect(renameInput).toBeFocused();
    await expect(renameInput).toHaveValue('History Idle');
    await renameInput.fill('Retry title');
    await renameInput.press('Enter');
    await expect(renameInput).toHaveValue('Retry title');
    await expect(page.locator('.toast')).toContainText(/Rename failed|重命名失败/);

    await renameInput.press('Enter');
    await expect(page.locator('.agent-history')).toContainText('Retry title');
    await expect(peer.locator('.agent-history')).toContainText('Retry title');

    idleRow = page.locator(
        `.agent-history > div[data-chat-id="${ids.idle}"]`
    );
    await idleRow.getByRole('button', {
        name: /Rename conversation|重命名会话/
    }).click();
    renameInput = idleRow.getByRole('textbox');
    await renameInput.fill('Discarded title');
    await renameInput.press('Escape');
    await expect(page.locator('.agent-history')).toContainText('Retry title');
    await expect(page.locator('.agent-history')).not.toContainText(
        'Discarded title'
    );

    await page.evaluate(async chatId => {
        const state = document.body._x_dataStack[0];
        await state.selectChat(chatId);
        await window.ChatRaw.modules.startTask({
            module_id: 'chatraw.reference.echo',
            action_id: 'echo.task',
            input: {
                text: 'keep active history',
                steps: 40,
                delay_ms: 100
            },
            chat_id: chatId,
            user_message: 'keep active history'
        }, { presentation: 'conversation' });
    }, ids.active);
    await openHistory(page);

    page.once('dialog', async dialog => {
        nativeDialogs.push(dialog.type());
        await dialog.accept();
    });
    await page.locator('.agent-history > header > button').click();
    await expect(page.locator('.agent-history')).toContainText('History Active');
    await expect(page.locator('.agent-history')).not.toContainText('Retry title');
    await expect(page.locator('.toast')).toContainText(
        /Deleted 1 conversations; kept 1|已删除 1 个会话；1 个正在运行/
    );

    await expect.poll(() => page.evaluate(async chatId => {
        const tasks = await window.ChatRaw.modules.listTasks({
            chat_id: chatId,
            limit: 10
        });
        return tasks[0]?.state || '';
    }, ids.active), { timeout: 30_000 }).toBe('succeeded');

    page.once('dialog', async dialog => {
        nativeDialogs.push(dialog.type());
        await dialog.accept();
    });
    await page.locator('.agent-history > header > button').click();
    await expect(page.locator('.agent-history > div')).toHaveCount(0);
    await expect(page.locator('.agent-history > header > button')).toBeDisabled();
    expect(nativeDialogs).toEqual(['confirm', 'confirm']);
    await peer.close();
});
