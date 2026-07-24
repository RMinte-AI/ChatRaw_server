(function () {
    'use strict';

    ChatRawResident.register({
        id: 'reference-module-workbench',
        mount(context) {
            const root = context.container;
            root.replaceChildren();

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
                                status.textContent = (
                                    moduleEvent.data.message
                                    || `${Math.round(moduleEvent.data.progress * 100)}%`
                                );
                            } else if (moduleEvent.event === 'output.delta') {
                                output.textContent += moduleEvent.data.text;
                            } else if (
                                moduleEvent.event === 'output.snapshot'
                            ) {
                                output.textContent = moduleEvent.data.text;
                            } else if (
                                moduleEvent.event === 'task.terminal'
                            ) {
                                status.textContent = moduleEvent.data.state;
                                submit.disabled = false;
                            }
                        },
                        onError(error) {
                            status.textContent = error.message;
                            submit.disabled = false;
                        }
                    });
                } catch (error) {
                    status.textContent = error.message;
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
