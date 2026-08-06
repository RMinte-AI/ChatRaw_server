(function () {
    'use strict';

    const PLUGIN_ID = 'reference-module-companion';
    const MODULE_ID = 'chatraw.reference.echo';
    const ACTION_ID = 'echo.task';
    const PANEL_ID = 'reference-module-workspace';

    const messages = {
        en: {
            unavailable: 'Reference feature is unavailable',
            prompt: 'Text for the reference module task',
            startFailed: 'Unable to start reference task',
            title: 'Reference Module',
            description: 'Run the public protocol example from this Workspace.',
            inputLabel: 'Task text',
            run: 'Run task',
            started: 'Reference task started'
        },
        zh: {
            unavailable: '参考模块功能暂不可用',
            prompt: '请输入参考模块任务要处理的文本',
            startFailed: '无法启动参考模块任务',
            title: '参考模块',
            description: '在此工作区运行公共协议参考任务。',
            inputLabel: '任务文本',
            run: '运行任务',
            started: '参考任务已启动'
        }
    };

    function t(key) {
        const lang = ChatRawPlugin.utils.getLanguage?.() || 'en';
        return messages[lang]?.[key] || messages.en[key] || key;
    }

    function displayError(error, fallbackKey) {
        const lang = ChatRawPlugin.utils.getLanguage?.() || 'en';
        if (lang === 'en' && error?.message) return error.message;
        return t(fallbackKey);
    }

    async function featureStatus() {
        return window.ChatRaw.modules.getFeatureStatus(MODULE_ID);
    }

    async function startReferenceTask(text) {
        const normalized = text?.trim();
        if (!normalized) return false;
        const status = await featureStatus();
        if (!status.available) {
            ChatRawPlugin.utils.showToast(
                displayError(status.reason, 'unavailable'),
                'error'
            );
            return false;
        }
        await window.ChatRaw.modules.startTask({
            module_id: MODULE_ID,
            action_id: ACTION_ID,
            input: {
                text: normalized,
                steps: 8,
                delay_ms: 80,
                require_approval: true,
                create_artifact: true
            },
            chat_id: ChatRawPlugin.utils.getCurrentChatId() || undefined
        });
        return true;
    }

    async function runReferenceTask() {
        ChatRawPlugin.ui.setButtonState(
            'reference-task',
            { loading: true },
            PLUGIN_ID
        );
        try {
            const text = window.prompt(t('prompt'));
            await startReferenceTask(text);
        } catch (error) {
            ChatRawPlugin.utils.showToast(
                displayError(error, 'startFailed'),
                'error'
            );
        } finally {
            ChatRawPlugin.ui.setButtonState(
                'reference-task',
                { loading: false },
                PLUGIN_ID
            );
        }
    }

    function mountWorkspace(container) {
        const root = document.createElement('section');
        root.className = 'crm-reference-workspace';
        root.innerHTML = `
            <style>
                .crm-reference-workspace {
                    box-sizing: border-box;
                    width: min(100%, 960px);
                    margin: 0 auto;
                    padding: clamp(24px, 5vw, 64px);
                    color: var(--text-primary, #161616);
                    font-family: var(--font-main, system-ui, sans-serif);
                }
                .crm-reference-workspace * { box-sizing: border-box; }
                .crm-reference-workspace__eyebrow {
                    margin: 0 0 12px;
                    color: var(--text-secondary, #75716b);
                    font-size: 12px;
                    letter-spacing: .12em;
                    text-transform: uppercase;
                }
                .crm-reference-workspace h2 {
                    margin: 0;
                    font: 500 clamp(30px, 5vw, 54px)/1.08 Georgia, serif;
                }
                .crm-reference-workspace__description {
                    max-width: 580px;
                    margin: 16px 0 36px;
                    color: var(--text-secondary, #75716b);
                    line-height: 1.7;
                }
                .crm-reference-workspace form {
                    display: grid;
                    gap: 12px;
                    max-width: 680px;
                    padding: clamp(20px, 4vw, 32px);
                    border: 1px solid var(--border-primary, #dedbd5);
                    border-radius: 16px;
                    background: var(--bg-secondary, #fff);
                }
                .crm-reference-workspace label { font-size: 13px; font-weight: 600; }
                .crm-reference-workspace textarea {
                    min-height: 140px;
                    resize: vertical;
                    padding: 14px;
                    border: 1px solid var(--border-primary, #dedbd5);
                    border-radius: 10px;
                    background: var(--bg-primary, #faf9f6);
                    color: inherit;
                    font: inherit;
                }
                .crm-reference-workspace button {
                    justify-self: start;
                    min-height: 44px;
                    padding: 0 20px;
                    border: 0;
                    border-radius: 10px;
                    background: var(--accent, #111);
                    color: var(--on-accent, #fff);
                    font: 600 14px/1 var(--font-main, system-ui, sans-serif);
                    cursor: pointer;
                }
                .crm-reference-workspace button:disabled { opacity: .55; cursor: wait; }
                .crm-reference-workspace__status { min-height: 20px; margin: 0; font-size: 13px; }
            </style>
            <p class="crm-reference-workspace__eyebrow">Module Protocol / v1</p>
            <h2>${t('title')}</h2>
            <p class="crm-reference-workspace__description">${t('description')}</p>
            <form>
                <label for="crm-reference-task-input">${t('inputLabel')}</label>
                <textarea id="crm-reference-task-input" required></textarea>
                <button type="submit">${t('run')}</button>
                <p class="crm-reference-workspace__status" aria-live="polite"></p>
            </form>
        `;
        const form = root.querySelector('form');
        const input = root.querySelector('textarea');
        const button = root.querySelector('button');
        const status = root.querySelector('[aria-live]');
        const onSubmit = async event => {
            event.preventDefault();
            button.disabled = true;
            status.textContent = '';
            try {
                if (await startReferenceTask(input.value)) {
                    status.textContent = t('started');
                }
            } catch (error) {
                status.textContent = displayError(error, 'startFailed');
            } finally {
                button.disabled = false;
            }
        };
        form.addEventListener('submit', onSubmit);
        container.replaceChildren(root);
        return () => {
            form.removeEventListener('submit', onSubmit);
            root.remove();
        };
    }

    featureStatus()
        .then(status => {
            if (!status.visible) return;
            ChatRawPlugin.ui.registerToolbarButton(
                {
                    id: 'reference-task',
                    icon: 'ri-pulse-line',
                    label: {
                        en: status.available
                            ? 'Reference module'
                            : 'Reference module unavailable',
                        zh: status.available
                            ? '参考模块'
                            : '参考模块暂不可用'
                    },
                    order: 60,
                    onClick: runReferenceTask
                },
                PLUGIN_ID
            );
        })
        .catch(error => {
            console.warn('[Reference module companion]', error);
        });

    ChatRawPlugin.ui.registerWorkspacePanel(
        {
            id: PANEL_ID,
            title: { en: 'Reference Module', zh: '参考模块' },
            icon: 'ri-pulse-line',
            placements: ['main'],
            defaultPlacement: 'main',
            mount: mountWorkspace
        },
        PLUGIN_ID
    );
})();
