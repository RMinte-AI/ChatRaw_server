# ChatRaw Plugin Workspace UI Implementation Guide

本文给出一个完整、可交互的 Plugin Workspace 实现。它使用现有参考模块
`chatraw.reference.echo`，但不修改参考模块、Server 后端或 Module Protocol。

## 1. 用户看到什么

插件入口仍由 `registerToolbarButton` 或侧边栏按钮提供。点击入口后，工作台直接出现在
ChatRaw 主内容区，而不是弹窗：

- `right`、`top`、`bottom`：工作台和聊天同时可见、同时可操作；
- `main`：工作台占据主区域，聊天 DOM 和当前消息仍然保留；
- 宽度不超过 1024px：由 Server 统一按 `main` 呈现；
- 关闭、停用、卸载或重载插件后，工作台 DOM 和监听器都会被清理。

Server 只提供布局和真实 DOM 容器。表单、列表、折叠区域、Module SDK 状态和业务交互均由
Plugin 自己实现。

## 2. 插件目录

```text
reference-workspace-companion/
├── manifest.json
├── main.js
└── icon.svg
```

`manifest.json`：

```json
{
  "id": "reference-workspace-companion",
  "version": "1.0.0",
  "name": {
    "en": "Reference Workspace Companion",
    "zh": "参考工作台插件"
  },
  "description": {
    "en": "Demonstrates an interactive Server-owned plugin workspace.",
    "zh": "演示 Server 主内容区中的可交互插件工作台。"
  },
  "author": "ChatRaw",
  "icon": "icon.svg",
  "main": "main.js",
  "type": "ui_extension",
  "hooks": [],
  "settings": []
}
```

## 3. 完整 main.js

下面的代码可以直接作为插件入口。它不会直连模块，不保存任务内容，也不会在 Workspace API
不可用时退回旧弹窗。

```js
(function () {
    'use strict';

    const PLUGIN_ID = 'reference-workspace-companion';
    const PANEL_ID = 'reference-workbench';
    const MODULE_ID = 'chatraw.reference.echo';
    const ACTION_ID = 'echo.task';

    const copy = {
        en: {
            title: 'Reference workbench',
            description: 'Run a reference module task without leaving chat.',
            input: 'Task text',
            steps: 'Steps',
            run: 'Run task',
            idle: 'Ready',
            loading: 'Checking module…',
            running: 'Task running…',
            empty: 'No output yet.',
            unavailable: 'Reference module is unavailable.',
            failed: 'The task could not be completed.',
            incompatible: 'This Server does not support Plugin Workspace.'
        },
        zh: {
            title: '参考工作台',
            description: '无需离开聊天即可运行参考模块任务。',
            input: '任务内容',
            steps: '执行步数',
            run: '运行任务',
            idle: '可以开始',
            loading: '正在检查模块…',
            running: '任务执行中…',
            empty: '暂时没有输出。',
            unavailable: '参考模块当前不可用。',
            failed: '任务未能完成。',
            incompatible: '当前 Server 不支持 Plugin Workspace。'
        }
    };

    function t(key) {
        const lang = ChatRawPlugin.utils.getLanguage?.() || 'en';
        return copy[lang]?.[key] || copy.en[key] || key;
    }

    function element(document, tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function mountWorkspace({ container, placement }) {
        const document = container.ownerDocument;
        let disposed = false;
        let unsubscribe = null;

        const root = element(document, 'div', 'cr-reference-workspace');
        root.dataset.placement = placement;

        const style = element(document, 'style');
        style.textContent = `
            .cr-reference-workspace {
                min-height: 100%;
                padding: 16px;
                color: var(--text-primary);
                background: var(--bg-primary);
                font-family: var(--font-main);
            }
            .cr-reference-workspace__intro {
                margin: 0 0 14px;
                color: var(--text-secondary);
                font-size: 13px;
            }
            .cr-reference-workspace__form {
                display: grid;
                grid-template-columns: minmax(0, 1fr) 96px auto;
                gap: 8px;
                align-items: end;
            }
            .cr-reference-workspace__field {
                display: grid;
                gap: 5px;
                min-width: 0;
                color: var(--text-secondary);
                font-size: 12px;
            }
            .cr-reference-workspace input,
            .cr-reference-workspace select,
            .cr-reference-workspace button {
                min-height: 38px;
                border: 1px solid var(--border-color);
                border-radius: var(--radius-sm);
                font: inherit;
            }
            .cr-reference-workspace input,
            .cr-reference-workspace select {
                min-width: 0;
                padding: 7px 9px;
                color: var(--text-primary);
                background: var(--bg-primary);
            }
            .cr-reference-workspace button {
                padding: 7px 14px;
                color: var(--on-accent);
                background: var(--accent-color);
                cursor: pointer;
            }
            .cr-reference-workspace button:disabled {
                cursor: not-allowed;
                opacity: .55;
            }
            .cr-reference-workspace__status {
                margin-top: 14px;
                padding: 10px 12px;
                border: 1px solid var(--border-color);
                border-radius: var(--radius-sm);
                color: var(--text-secondary);
                background: var(--bg-secondary);
            }
            .cr-reference-workspace__output {
                min-height: 120px;
                margin: 10px 0 0;
                padding: 12px;
                overflow: auto;
                border: 1px solid var(--border-color);
                border-radius: var(--radius-sm);
                color: var(--text-primary);
                background: var(--bg-primary);
                font-family: var(--font-mono);
                white-space: pre-wrap;
            }
            @media (max-width: 680px) {
                .cr-reference-workspace__form {
                    grid-template-columns: 1fr;
                }
            }
        `;

        const intro = element(
            document,
            'p',
            'cr-reference-workspace__intro',
            t('description')
        );
        const form = element(document, 'form', 'cr-reference-workspace__form');
        const textField = element(document, 'label', 'cr-reference-workspace__field');
        textField.append(element(document, 'span', '', t('input')));
        const input = element(document, 'input');
        input.name = 'text';
        input.required = true;
        input.maxLength = 4000;
        textField.append(input);

        const stepsField = element(document, 'label', 'cr-reference-workspace__field');
        stepsField.append(element(document, 'span', '', t('steps')));
        const select = element(document, 'select');
        select.name = 'steps';
        for (const value of [4, 8, 12]) {
            const option = element(document, 'option', '', String(value));
            option.value = String(value);
            if (value === 8) option.selected = true;
            select.append(option);
        }
        stepsField.append(select);

        const submit = element(document, 'button', '', t('run'));
        submit.type = 'submit';
        const status = element(
            document,
            'div',
            'cr-reference-workspace__status',
            t('loading')
        );
        status.setAttribute('role', 'status');
        const output = element(
            document,
            'pre',
            'cr-reference-workspace__output',
            t('empty')
        );

        form.append(textField, stepsField, submit);
        root.append(style, intro, form, status, output);
        container.append(root);

        function setBusy(busy, message) {
            if (disposed) return;
            submit.disabled = busy;
            input.disabled = busy;
            select.disabled = busy;
            status.textContent = message;
        }

        async function loadStatus() {
            try {
                const feature = await window.ChatRaw.modules.getFeatureStatus(
                    MODULE_ID
                );
                if (disposed) return;
                setBusy(!feature.available, feature.available
                    ? t('idle')
                    : feature.reason?.message || t('unavailable'));
            } catch (error) {
                setBusy(true, error?.message || t('unavailable'));
            }
        }

        async function onSubmit(event) {
            event.preventDefault();
            if (!input.value.trim()) return;
            unsubscribe?.();
            unsubscribe = null;
            output.textContent = '';
            setBusy(true, t('running'));
            try {
                const request = {
                    module_id: MODULE_ID,
                    action_id: ACTION_ID,
                    input: {
                        text: input.value.trim(),
                        steps: Number(select.value),
                        delay_ms: 80,
                        require_approval: false,
                        create_artifact: false
                    }
                };
                const chatId = ChatRawPlugin.utils.getCurrentChatId();
                if (chatId) request.chat_id = chatId;
                const task = await window.ChatRaw.modules.startTask(
                    request,
                    { presentation: 'embedded' }
                );
                if (disposed) return;
                unsubscribe = window.ChatRaw.modules.subscribe(
                    task.task_id,
                    {
                        onEvent(event) {
                            if (disposed) return;
                            if (event.event === 'output.delta') {
                                output.textContent += event.data?.text || '';
                            }
                            if (event.event === 'task.terminal') {
                                unsubscribe?.();
                                unsubscribe = null;
                                const succeeded = event.data?.state === 'succeeded';
                                setBusy(false, succeeded ? t('idle') : t('failed'));
                                if (!output.textContent) {
                                    output.textContent = t('empty');
                                }
                            }
                        },
                        onError(error) {
                            setBusy(false, error?.message || t('failed'));
                        }
                    }
                );
            } catch (error) {
                setBusy(false, error?.message || t('failed'));
            }
        }

        form.addEventListener('submit', onSubmit);
        loadStatus();

        return function dispose() {
            if (disposed) return;
            disposed = true;
            unsubscribe?.();
            unsubscribe = null;
            form.removeEventListener('submit', onSubmit);
        };
    }

    const ui = window.ChatRawPlugin?.ui;
    if (typeof ui?.registerWorkspacePanel !== 'function') {
        ChatRawPlugin.utils.showToast(t('incompatible'), 'error');
        throw new Error('Plugin Workspace API unavailable');
    }

    ui.registerWorkspacePanel(
        {
            id: PANEL_ID,
            title: { en: copy.en.title, zh: copy.zh.title },
            icon: 'ri-layout-right-line',
            placements: ['right', 'top', 'bottom', 'main'],
            defaultPlacement: 'right',
            mount: mountWorkspace
        },
        PLUGIN_ID
    );

    ui.registerToolbarButton(
        {
            id: 'open-reference-workspace',
            icon: 'ri-layout-right-line',
            label: { en: copy.en.title, zh: copy.zh.title },
            placement: 'sidebar',
            order: 70,
            onClick() {
                ui.openWorkspacePanel(PANEL_ID, undefined, PLUGIN_ID);
            }
        },
        PLUGIN_ID
    );
})();
```

## 4. 生命周期要求

`mount` 本身必须同步结束，因此不能声明为 `async`。需要加载状态时，先渲染 Loading，再启动
异步函数。`dispose()` 至少负责：

- 取消 `window.ChatRaw.modules.subscribe()`；
- 移除 Plugin 自己注册的 DOM 或 Window 事件；
- 中止 Plugin 自己创建且仍可取消的请求；
- 设置 disposed 标记，阻止已经返回的异步结果继续更新 DOM。

`mount()` 和 `dispose()` 都不能递归调用 Workspace 的注册、注销、打开或关闭 API。需要切换
面板时，应由当前回调返回后的用户操作或异步流程发起；Host 会拒绝同步重入，防止新面板的
`dispose()` 被旧回调覆盖。

Server 会在 `dispose()` 返回后清空挂载容器。Plugin 不需要删除 Server 的标题栏或关闭按钮。

## 5. 样式和性能

- 所有选择器必须从 Plugin 根类开始，例如 `.cr-reference-workspace`。
- 使用容器自身滚动，不修改 `body`、`.main-content` 或 `.chat-container`。
- 不使用轮询来判断 Workspace 是否打开，也不使用 MutationObserver 查找 Server DOM。
- 长列表由 Plugin 分页或虚拟化；Server 不替 Plugin 管理业务列表。
- 不依赖固定宽高。右侧、上下和窄屏主区域会提供不同尺寸的容器。

## 6. 错误与兼容

- Workspace API 不存在：显示版本不兼容并停止注册，不打开旧弹窗。
- Module 不可用：保留工作台，禁用业务操作，并显示 Module SDK 的安全错误说明。
- `mount` 抛错或没有返回函数：Server 关闭并清空面板，错误继续抛给调用者。
- Workspace 关闭后业务任务可以继续由 Server 管理；Plugin 只停止自己的事件订阅，不伪造取消任务。

正式接口以 [Plugin UI SDK Contract](../backend/contracts/plugin-ui-sdk-v1.json) 为准。
