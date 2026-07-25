(function () {
    'use strict';

    const PLUGIN_ID = 'reference-module-companion';
    const MODULE_ID = 'chatraw.reference.echo';
    const ACTION_ID = 'echo.task';

    const messages = {
        en: {
            unavailable: 'Reference feature is unavailable',
            prompt: 'Text for the reference module task',
            startFailed: 'Unable to start reference task'
        },
        zh: {
            unavailable: '参考模块功能暂不可用',
            prompt: '请输入参考模块任务要处理的文本',
            startFailed: '无法启动参考模块任务'
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

    async function runReferenceTask() {
        ChatRawPlugin.ui.setButtonState(
            'reference-task',
            { loading: true },
            PLUGIN_ID
        );
        try {
            const status = await featureStatus();
            if (!status.available) {
                ChatRawPlugin.utils.showToast(
                    displayError(status.reason, 'unavailable'),
                    'error'
                );
                return;
            }
            const text = window.prompt(t('prompt'));
            if (!text?.trim()) return;
            await window.ChatRaw.modules.startTask({
                module_id: MODULE_ID,
                action_id: ACTION_ID,
                input: {
                    text: text.trim(),
                    steps: 8,
                    delay_ms: 80,
                    require_approval: true,
                    create_artifact: true
                },
                chat_id: ChatRawPlugin.utils.getCurrentChatId() || undefined
            });
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
})();
