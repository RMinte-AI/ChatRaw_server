(function () {
    'use strict';

    const PLUGIN_ID = 'reference-module-companion';
    const MODULE_ID = 'chatraw.reference.echo';
    const ACTION_ID = 'echo.task';

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
                    status.reason?.message || 'Reference feature is unavailable',
                    'error'
                );
                return;
            }
            const text = window.prompt('Text for the reference module task');
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
                error.message || 'Unable to start reference task',
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
