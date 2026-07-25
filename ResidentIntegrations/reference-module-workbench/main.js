(function () {
    'use strict';

    ChatRawResident.register({
        id: 'reference-module-workbench',
        mount(context) {
            const root = context.container;
            root.replaceChildren();

            const stateLabels = {
                queued: { en: 'Queued', zh: '排队中' },
                running: { en: 'Running', zh: '运行中' },
                waiting_approval: { en: 'Waiting for approval', zh: '等待审批' },
                cancel_requested: { en: 'Cancellation requested', zh: '正在取消' },
                succeeded: { en: 'Succeeded', zh: '已成功' },
                failed: { en: 'Failed', zh: '已失败' },
                cancelled: { en: 'Cancelled', zh: '已取消' }
            };
            const errorLabels = {
                module_not_enabled: { en: 'This module is not enabled.', zh: '此模块尚未启用。' },
                module_not_ready: { en: 'This module is not ready.', zh: '此模块尚未就绪。' },
                module_review_required: { en: 'This module requires administrator review.', zh: '此模块需要管理员审核。' },
                module_action_forbidden: { en: 'You do not have permission to run this action.', zh: '你没有权限运行此操作。' },
                invalid_task_request: { en: 'The task request is invalid.', zh: '任务请求无效。' },
                task_not_found: { en: 'The task could not be found.', zh: '找不到此任务。' },
                module_event_stream_failed: { en: 'The task event stream was interrupted.', zh: '任务事件流已中断。' },
                module_event_stream_incomplete: { en: 'The task event stream ended unexpectedly.', zh: '任务事件流意外结束。' }
            };

            function localizeError(error) {
                const localized = errorLabels[error?.code];
                if (localized) return context.t(localized);
                return context.t({
                    en: error?.message || 'Unable to run the task.',
                    zh: '无法运行任务，请稍后重试。'
                });
            }

            function localizeProgress(data) {
                const progress = Number(data?.progress);
                if (Number.isFinite(progress)) {
                    return context.t({
                        en: data?.message || `${Math.round(progress * 100)}% complete`,
                        zh: `已完成 ${Math.round(progress * 100)}%`
                    });
                }
                return context.t({
                    en: data?.message || 'Task is running…',
                    zh: '任务正在运行…'
                });
            }

            const form = document.createElement('form');
            form.className = 'reference-resident-form';

            const title = document.createElement('h2');
            title.textContent = context.t({
                en: 'Reference module workbench',
                zh: '参考模块工作台'
            });

            const description = document.createElement('p');
            description.textContent = context.t({
                en: 'Run a durable module task without leaving this workspace.',
                zh: '无需离开当前工作台即可运行可恢复的模块任务。'
            });

            const input = document.createElement('textarea');
            input.required = true;
            input.maxLength = 4000;
            input.placeholder = context.t({
                en: 'Text to process',
                zh: '请输入要处理的文本'
            });

            const submit = document.createElement('button');
            submit.type = 'submit';
            submit.className = 'btn-primary';
            submit.textContent = context.t({
                en: 'Run task',
                zh: '运行任务'
            });

            const status = document.createElement('p');
            status.className = 'section-desc';

            const output = document.createElement('pre');
            output.className = 'module-task-output';

            form.append(title, description, input, submit, status, output);
            root.append(form);

            let unsubscribe = null;
            form.addEventListener('submit', async event => {
                event.preventDefault();
                const text = input.value.trim();
                if (!text || submit.disabled) return;
                submit.disabled = true;
                output.textContent = '';
                status.textContent = context.t({
                    en: 'Starting…',
                    zh: '正在启动…'
                });
                try {
                    const chatId = context.getCurrentChatId();
                    const request = {
                        module_id: context.moduleId,
                        action_id: 'echo.task',
                        input: {
                            text,
                            steps: 8,
                            delay_ms: 80,
                            require_approval: false,
                            create_artifact: true
                        }
                    };
                    if (chatId) {
                        request.chat_id = chatId;
                        request.user_message = text;
                    }
                    const task = await context.modules.startTask(
                        request,
                        { presentation: 'embedded' }
                    );
                    unsubscribe?.();
                    unsubscribe = context.modules.subscribe(task.task_id, {
                        onEvent(moduleEvent) {
                            if (moduleEvent.event === 'task.progress') {
                                status.textContent = localizeProgress(moduleEvent.data);
                            } else if (moduleEvent.event === 'output.delta') {
                                output.textContent += moduleEvent.data.text;
                            } else if (
                                moduleEvent.event === 'output.snapshot'
                            ) {
                                output.textContent = moduleEvent.data.text;
                            } else if (
                                moduleEvent.event === 'task.terminal'
                            ) {
                                const state = moduleEvent.data.state;
                                status.textContent = stateLabels[state]
                                    ? context.t(stateLabels[state])
                                    : context.t({ en: 'Task finished.', zh: '任务已结束。' });
                                submit.disabled = false;
                            }
                        },
                        onError(error) {
                            status.textContent = localizeError(error);
                            submit.disabled = false;
                        }
                    });
                } catch (error) {
                    status.textContent = localizeError(error);
                    submit.disabled = false;
                }
            });

            return () => {
                unsubscribe?.();
                root.replaceChildren();
            };
        }
    });
})();
