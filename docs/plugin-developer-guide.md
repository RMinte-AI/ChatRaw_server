# ChatRaw Server Plugin Developer Guide

## 中文

### 1. 插件的产品边界

插件只负责 ChatRaw 前端接入：

- 增加工具栏按钮、补全、展示或发送拦截；
- 读取管理员允许暴露的运行配置；
- 通过 ChatRaw 提供的同源 API调用 Server；
- 对大型功能，通过 `window.ChatRaw.modules` 调用后端模块。

插件不应承担：

- 独立数据库、后台进程或长期任务；
- 直接连接模块地址；
- 保存模块 Token、模型 API Key 或其他服务密钥；
- 实现模块安装、启停、审批或删除；
- 绕过 ChatRaw Server 调用模块私有接口。

独立运行的模块进程不能在运行时向 ChatRaw 注入前端代码。大型功能可以使用“模块 + 配套插件”扩展界面；如果入口必须随 Server 常驻，则使用“模块 + 源码级 Resident Integration”。Resident 不是插件包，详见 [Resident Module Integration Guide](resident-module-integration-guide.md)。

### 2. 可信代码边界

ChatRaw 插件不是浏览器沙箱。启用后，`main.js` 与 ChatRaw 页面运行在同一个 JavaScript 上下文中，技术上可以访问页面 DOM、浏览器存储和同源请求。

因此：

- 只有管理员可以安装、启停、配置和删除插件。
- 普通用户只能使用管理员启用的插件。
- “本地上传”代表管理员主动信任这份代码，不代表 ChatRaw 已证明其安全。
- 官方目录插件会显示目录哈希验证状态；哈希不匹配的插件按本地可信代码处理。
- 不要依赖私有 DOM 结构、Alpine 内部字段或未记录的全局变量。

### 3. 最小目录

```text
my-plugin/
├── manifest.json
├── main.js
└── icon.png
```

ZIP 中可以有一个顶层目录，也可以直接放文件，但必须满足：

- 恰好一个 `manifest.json`；
- manifest 与 `main.js` 在同一插件根目录；
- 不包含绝对路径、`..`、反斜杠路径、重复路径或符号链接；
- `main` 只能是插件根目录中的单个文件名；
- 插件 ID 必须稳定，升级时不能改 ID。

### 4. 最小 manifest

```json
{
  "id": "example-companion",
  "version": "1.0.0",
  "name": {
    "en": "Example Companion",
    "zh": "示例连接插件"
  },
  "description": {
    "en": "Connects an example feature to ChatRaw.",
    "zh": "将示例功能接入 ChatRaw。"
  },
  "author": "Example",
  "icon": "icon.png",
  "main": "main.js",
  "type": "ui_extension",
  "hooks": []
}
```

模块 manifest 中的旧 `companion_plugin.id` 或新 `frontend_integration`（`mode: plugin`）ID 必须等于插件 `id`，`version` 必须满足模块声明的版本范围。版本使用 SemVer；破坏兼容性的插件 API 改动提升主版本。

### 5. 运行配置与管理配置

插件 manifest 可以声明 `settings`。默认情况下，设置值只出现在管理员管理视图，不会发给普通用户的插件运行时。

需要在浏览器运行时读取的非秘密字段必须显式声明：

```json
{
  "settings": [
    {
      "id": "display_mode",
      "type": "select",
      "default": "compact",
      "exposure": "runtime"
    }
  ],
  "runtimeSettings": [
    "display_mode"
  ]
}
```

规则：

- `runtimeSettings` 只能包含可以安全暴露给所有平台用户的非秘密值。
- API Key 不属于 runtime setting。
- 远程服务 API Key 使用 manifest 的 `proxy` 声明和 Server 管理界面保存。
- 普通用户获取到的 runtime manifest 会移除 `proxy`、管理配置和未暴露的设置值。
- 模块秘密由模块配置界面管理，不应复制到插件设置。

运行时读取：

```js
const settings = ChatRawPlugin.settings('example-companion');
const mode = settings.display_mode || 'compact';
```

### 6. 插件生命周期

`main.js` 应是可重复加载、可清理的 IIFE：

```js
(function () {
    'use strict';

    const PLUGIN_ID = 'example-companion';

    ChatRawPlugin.ui.registerToolbarButton(
        {
            id: 'example',
            icon: 'ri-pulse-line',
            label: { en: 'Example', zh: '示例' },
            order: 70,
            onClick: async () => {
                ChatRawPlugin.utils.showToast('Ready', 'success');
            }
        },
        PLUGIN_ID
    );
})();
```

卸载、停用或重新加载时，ChatRaw 会清理已登记 hook、补全和扩展入口。插件自己建立的定时器、事件监听或外部对象仍应由插件清理。

公共扩展入口 API（为兼容既有插件保留 `Toolbar` 方法名）：

- `ChatRawPlugin.ui.registerToolbarButton(definition, pluginId)`
- `ChatRawPlugin.ui.unregisterToolbarButton(buttonId, pluginId)`
- `ChatRawPlugin.ui.setButtonState(buttonId, state, pluginId)`
- `ChatRawPlugin.ui.openFullscreenModal(options, pluginId)`
- `ChatRawPlugin.ui.closeFullscreenModal()`

公共主内容区 API：

- `ChatRawPlugin.ui.registerWorkspacePanel(definition, pluginId)`
- `ChatRawPlugin.ui.unregisterWorkspacePanel(panelId, pluginId)`
- `ChatRawPlugin.ui.openWorkspacePanel(panelId, options, pluginId)`
- `ChatRawPlugin.ui.closeWorkspacePanel(panelId, pluginId)`

Workspace 是 Server 主内容区中的非模态交互区域，支持 `right`、`top`、`bottom` 和
`main`。右、上、下位置不会阻止用户继续操作聊天；`main` 只隐藏聊天的视觉区域，不销毁
聊天 DOM 和状态。屏幕宽度不超过 1024px 时，所有位置按 `main` 呈现；屏幕高度不超过
420px 时，上、下位置按 `main` 呈现。

```js
const PLUGIN_ID = 'example-companion';

ChatRawPlugin.ui.registerWorkspacePanel(
    {
        id: 'workbench',
        title: { en: 'Example workbench', zh: '示例工作台' },
        icon: 'ri-dashboard-line',
        placements: ['right', 'main'],
        defaultPlacement: 'right',
        mount({ container, placement }) {
            const button = document.createElement('button');
            button.type = 'button';
            button.textContent = `Run in ${placement}`;
            const onClick = () => {
                ChatRawPlugin.utils.showToast('Ready', 'success');
            };
            button.addEventListener('click', onClick);
            container.append(button);
            return () => {
                button.removeEventListener('click', onClick);
            };
        }
    },
    PLUGIN_ID
);

ChatRawPlugin.ui.registerToolbarButton(
    {
        id: 'open-workbench',
        icon: 'ri-dashboard-line',
        label: { en: 'Example workbench', zh: '示例工作台' },
        placement: 'toolbar',
        onClick() {
            ChatRawPlugin.ui.openWorkspacePanel(
                'workbench',
                { placement: 'right' },
                PLUGIN_ID
            );
        }
    },
    PLUGIN_ID
);
```

多个只在 `main` 位置显示的相关面板可以声明同一个可选 `collection`。Server 会为该
collection 不创建独立入口；用户从首页目录卡片进入后，Host 在 Workspace 标题下渲染面板标签：

```js
collection: {
    id: 'operations',
    title: { en: 'Operations', zh: '运营' },
    icon: 'ri-dashboard-line',
    order: 20,
    tabOrder: 10
}
```

collection 面板必须包含 `main`，且 `defaultPlacement` 必须是 `main`。不同 Plugin 可以
加入同一 collection，但 `id` 相同时 `title`、`icon` 和 `order` 必须完全一致；Server
按 `order` 排 collection，按 `tabOrder` 排标签，相同序号再按 Plugin ID 和面板 ID
稳定排序。切换标签仍遵循“先 dispose 旧面板，再 mount 新面板”的单 Workspace 生命周期。

Workspace 规则：

- `pluginId` 必须显式提供；它是生命周期归属命名空间，不是浏览器安全沙箱。
- `mount` 必须同步返回一个 `dispose()` 函数；`dispose()` 也必须同步执行并返回
  `undefined`，不能声明为 `async`。异步请求可以在 mount 内启动，但关闭时必须取消订阅、
  事件监听和仍可取消的请求。
- `mount()` 和 `dispose()` 执行期间不得递归调用 Workspace 的注册、注销、打开或关闭 API；
  Host 会直接抛错，避免重入覆盖当前面板的生命周期状态。
- Plugin 只能修改传入的 `container`，不能查找 ChatRaw 私有 DOM、读取 Alpine 内部状态或向
  Server 挂载点写入模块返回的 HTML。
- 同一时刻只有一个 Workspace。打开另一面板或切换位置时，旧面板先执行一次 `dispose()`。
- 同一面板以同一位置重复打开不会重复 mount。页面刷新后 Workspace 保持关闭。
- 只有用户点击或用键盘激活 Host 在 Agent 扩展面板渲染的所属入口，且该入口的 `onClick` 在返回前同步
  打开同一 Plugin 所属的 Workspace 时，Host 才会把焦点移到 Workspace 标题；关闭、挂载失败或
  替换失败后，焦点返回稳定的 Agent 扩展箭头。
  直接 API 调用、在 `await` 之后打开、模块回调、定时器或跨 Plugin 代开都保持当前焦点。
  Plugin 不能传入参数覆盖这一 Host 判定。需要异步数据时，先同步打开并在 `mount()` 中渲染
  Loading，再启动异步工作。
- 非法定义、未声明的位置、挂载异常或缺失 `dispose()` 会直接抛错；不得改用全屏弹窗兜底。
- Plugin CSS 必须限定在自己的根节点内。不要使用影响 `body`、`.main-content` 或其他核心元素的
  全局选择器。
- Host 在页面根节点接管横向滚轮、触控板和 Magic Mouse 手势，阻止 Safari 历史页面回弹。
  Plugin 内需要横向滚动的区域必须显式使用 `overflow-x: auto` 或 `scroll`；Host 会把手势路由到
  最近的这类容器并在边缘继续消费。不要依赖 `body` 横向溢出，也不要拦截普通纵向滚动或
  `Ctrl` + 滚轮缩放。

首页卡片来自配套 Module Manifest 的 `frontend_integration.catalog`，并通过同级 `workspace_panel_id` 指向 `plugin_id + panel_id`。Plugin 不得自行向首页插入 DOM；它必须保持插件 ID、面板 ID 稳定，并让该面板的 `placements` 明确包含 `main`。Host 只有在 Module 服务就绪、Plugin 安装启用且版本兼容、当前浏览器已注册目标面板时才将卡片标记为可用；首页点击固定以 `main` 打开，不会退回 `defaultPlacement`。对于已进入目录的面板，`catalog.icon` 是 Host 首页卡片、内容导航、Workspace 标题和 collection 页签的唯一展示图标；`WorkspacePanelDefinition.icon` 仅作为无目录面板的回退。开发者应让两者语义一致，但不能依赖注册图标覆盖 Host 目录图标。

机器契约见 [Plugin UI SDK Contract](../backend/contracts/plugin-ui-sdk-v1.json)，完整可运行示例见
[Plugin Workspace UI Implementation Guide](plugin-workspace-ui-guide.md)。

产品本身只启用浅色主题。Host 仍保留未激活的公共 `[data-theme="dark"]` CSS token 别名，避免既有 Plugin 的公共变量引用失效；Plugin 不得把这些兼容 token 当成可用的用户主题开关，也不得自行切换根节点主题。

Plugin 与 Resident 的视觉实现同时遵循[前端配色要求](frontend-color-requirements.md)：公共语义变量只读，选择器限定在分配的根节点内。

`registerToolbarButton` 注册由 Host 呈现的 Agent 扩展入口。Agent 输入区只直接保留图片、文档和
网页三个核心操作；`placement: 'toolbar'` 和历史 `placement: 'sidebar'` 都显示在箭头打开的扩展面板。
API 名称、参数、返回值和生命周期保持兼容，插件不得假设入口一定是独立的输入栏图标。入口可以提供
本地化 `status`，并通过 `setButtonState` 更新 `status`、`disabled`、`active` 或 `loading`。
独立业务能力的首选入口是 Module Manifest 目录卡片；插件不得自行查询或修改 ChatRaw DOM 来移动入口。

不要使用 `querySelector` 定位 ChatRaw 内部按钮，也不要读取 `_x_dataStack` 等框架内部状态。

### 7. Hook

当前产品发送链路只调用 `before_send`：

```js
ChatRawPlugin.hooks.register('before_send', {
    priority: 100,
    async handler(context) {
        return {
            success: true,
            body: { use_rag: true }
        };
    }
});
```

`ChatRawPlugin.hooks.available()` 仍列出历史 hook 名称，供旧插件完成注册和卸载，但四页式产品 UI
不会执行 `send_intercept`、`transform_input`、`route_message` 或 `after_receive`。Agent 对
`before_send` 的结果只读取白名单中的 `use_rag`、`web_content` 和 `web_url`；Host 随后重写
`chat_id`、`message` 和技能身份，并固定发送到 `/api/agent/chat`。插件不得依赖未执行的 hook，
也不得把 `before_send` 当作身份、路由或权限入口。

### 8. Module SDK

模块配套插件只能使用：

```js
window.ChatRaw.modules
```

正式契约：[module-plugin-sdk-v1.json](../backend/contracts/module-plugin-sdk-v1.json)。

常用方法：

- `getFeatureStatus(moduleId)`
- `startTask(request)`
- `getTask(taskId)`
- `subscribe(taskId, handlers)`
- `cancelTask(taskId)`
- `respondApproval(taskId, approvalId, decision)`
- `downloadArtifact(taskId, artifactRef)`
- `uploadTaskResource(file)`
- `getTaskResourceView(taskId, resourceRef)`
- `downloadTaskResource(taskId, resourceRef)`

最小示例：

```js
const PLUGIN_ID = 'example-companion';
const MODULE_ID = 'com.example.module';

async function run() {
    const status = await window.ChatRaw.modules.getFeatureStatus(MODULE_ID);
    if (!status.available) {
        ChatRawPlugin.utils.showToast(
            status.reason?.message || 'Feature unavailable',
            'error'
        );
        return;
    }
    await window.ChatRaw.modules.startTask({
        module_id: MODULE_ID,
        action_id: 'example.run',
        input: { text: 'hello' },
        chat_id: ChatRawPlugin.utils.getCurrentChatId(),
        user_message: 'hello'
    }, {
        presentation: 'conversation'
    });
}
```

禁止：

- `fetch('http://module:port/...')`
- 在 manifest 中保存模块 URL 或 Token
- 通过 ChatRaw 旧 proxy 接口转发模块协议
- 伪造用户、角色、`actor_ref` 或 Host Capability
- 在浏览器存储任务输入、输出或产物路径

SDK 只在浏览器保存可恢复的 `task_id`，并使用当前 ChatRaw Session 访问同源 Server。

需要把原始文件交给模块时：

```js
const uploaded = await window.ChatRaw.modules.uploadTaskResource(file);
const task = await window.ChatRaw.modules.startTask({
    module_id: 'com.example.module',
    action_id: 'example.import',
    input: { display_name: file.name },
    resource_ids: [uploaded.resource_id]
});
```

上传接口只返回不透明资源 ID 和文件元数据，不返回用户身份、Cookie 或 Host Capability Token。
临时资源只能绑定一个任务；上传成功后如果任务创建失败，插件应向用户报告失败，不能改用普通文档上传。

任务成功后，插件可以使用任务摘要中的 `resource_ref`：

```js
const view = await window.ChatRaw.modules.getTaskResourceView(
    task.task_id,
    resource.resource_ref
);
// 只有 Server 返回 disposition: "inline" 时才会成功。
previewFrame.src = view.url;

await window.ChatRaw.modules.downloadTaskResource(
    task.task_id,
    resource.resource_ref
);
```

`getTaskResourceView` 先发起一次同源 `GET` 元数据探测：收到响应头后立即取消响应体，不会把整个文件
读入浏览器；错误响应则读取 Server 的结构化错误。校验文件名、媒体类型和长度后，它返回当前 Session
可访问的同源 `url`。它只适用于浏览器能够原生显示且 Server 明确返回
`Content-Disposition: inline` 的格式，
例如 PDF、图片和受支持的文本。DOCX、XLSX、PPTX 等通常以 `attachment` 返回，此时 SDK 抛出
`task_resource_preview_unavailable`；需要在 Modal 中预览这类文件的插件必须自带安全的渲染器，
或让模块先转换为浏览器可显示的输出格式，不能把下载 URL 直接当作 iframe 预览。

插件不得持久化该 URL、改写 `resource_ref`、推导模块地址或绕过 Server 读取资源。
服务端错误按 SDK 稳定错误码直接展示或处理，不应切换到旧上传路径、猜测 MIME 或静默重试。

`presentation` 有三种冻结语义：

- `task_center`：默认值，打开 Core 任务中心并订阅；
- `embedded`：只登记任务，调用方自行订阅和展示；
- `conversation`：要求 `chat_id` 和 `user_message`，由 Core 在对话内展示、订阅和恢复，不打开任务中心。

每次 `startTask` 都会登记一个独立任务。插件不要自己复制任务列表、执行时间线、审批界面或产物凭证。
`conversation` 只适用于已经拥有真实 `chat_id` 与 `user_message` 的显式 Module SDK 调用；当前
Agent 输入链路不会通过 hook 自动创建它。conversation 消息只有 `content` 是可渲染、可复制的答案正文：流式 task output
更新 Core 管理的虚拟助手消息，终态 projection 持久化后再按消息 ID 替换它。插件不得把
`task.result` 或 `chat_projection` 再渲染成第二份答案。

### 9. 错误处理

SDK 错误为：

```js
{
    name: 'ModuleSdkError',
    message: 'safe public message',
    code: 'stable_machine_code',
    status: 400
}
```

插件应根据 `code` 决定 UI，不要解析自然语言 `message`。常见代码以 [Module SDK contract](../backend/contracts/module-plugin-sdk-v1.json) 的 `errors` 为准。

`module_event_stream_incomplete` 表示 SSE 在出现终态之前结束。SDK 会带 `Last-Event-ID` 有界重连；插件可以显示暂时失联，但不能把它当作任务成功、清除任务，或绕过 Server 直连模块。最终失败会由 Server 持久化，并在重连时以 `task.terminal` 重放。

无论发生何种模块错误，配套插件都应释放 loading 状态，并允许用户回到普通 ChatRaw 功能。

### 10. 兼容规则

- 插件依赖公共 `ChatRawPlugin` 和 `window.ChatRaw.modules`，不依赖内部 DOM。
- 配套插件主版本必须满足模块 manifest 的 `version_range`。
- 新增可选功能可以提升次版本；删除方法、改变 hook 语义或改变任务输入需要提升主版本。
- 插件不得假设模块一定支持 stream、cancel、approval 或 artifact；以 Action 声明和 Feature Status 为准。
- 模块不可用时，插件入口可以显示不可用状态，但不能绕过 Server 直连模块。

### 11. 本地检查

```bash
node --check my-plugin/main.js
node --test tests/plugin-contract.test.mjs
zip -r my-plugin.zip my-plugin
unzip -t my-plugin.zip
```

配套插件还必须在真实浏览器验证：

- 管理员能安装、配置、启停和删除；
- 普通用户能使用但看不到管理操作；
- 模块可用时能创建任务；
- 模块不可用时不接管普通聊天；
- 页面刷新后任务能够恢复；
- 浏览器控制台没有错误；
- 页面和浏览器存储中没有模块凭证。

参考实现：

- [Reference Module Companion](../Plugins/Plugin_market/reference-module-companion/)
- Agent companion plugin 位于独立交付仓库；其私有后端协议不是插件接口。

---

## English

### Boundary

Plugins are trusted frontend code. They may add UI, hooks, and presentation, but they must not own backend services, durable jobs, module addresses, or secrets. Large features use a companion plugin plus an independent module. A persistent entry shipped with Server source is a Resident Integration, not a dynamically installed plugin; see the [Resident Module Integration Guide](resident-module-integration-guide.md).

Plugins are not sandboxed. Only administrators install, configure, enable, disable, or remove them. Members can use enabled plugins. A locally uploaded ZIP is administrator-trusted code, not automatically verified code.

### Package

```text
my-plugin/
├── manifest.json
├── main.js
└── icon.png
```

The archive must contain exactly one manifest, no traversal paths or symlinks, and a root-level main file. Keep the plugin ID stable and use SemVer.

### Configuration

Management settings are admin-only by default. Declare only safe non-secret values in `runtimeSettings` or with `"exposure": "runtime"`. API keys use Server-managed proxy secrets. Module secrets belong to module configuration and must never be copied into plugin settings.

### Public APIs

Use `ChatRawPlugin.hooks`, `ChatRawPlugin.ui`, `ChatRawPlugin.utils`, and documented input/storage helpers. Do not depend on internal DOM or framework fields.

`ChatRawPlugin.ui` also provides the Server-owned, non-modal Workspace API:
`registerWorkspacePanel`, `unregisterWorkspacePanel`, `openWorkspacePanel`, and
`closeWorkspacePanel`. A workspace can request `right`, `top`, `bottom`, or `main`; at
1024px or narrower the host renders every placement as `main`; at 420px or shorter it also
renders `top` and `bottom` as `main`. The plugin receives a real DOM container. `mount`
must synchronously return one cleanup function, and that function must synchronously return
`undefined`. It must not fall back to the legacy fullscreen modal when registration or
mounting fails. The Host focuses the Workspace title only when the `onClick` callback of that plugin's
Host-rendered Agent extension palette entry synchronously opens its own workspace during click or keyboard
activation. Closing, mount failure, or replacement failure then restores the connected Host entry;
palette entries return to the stable extension arrow. Direct API calls, opens after `await`, module
callbacks, timers, and cross-plugin opens preserve the current focus. Plugins cannot override this
Host decision with an option. If data is asynchronous, open synchronously, render loading state from
`mount()`, and then start the asynchronous work. See the
[Plugin UI SDK Contract](../backend/contracts/plugin-ui-sdk-v1.json) and the
[complete implementation guide](plugin-workspace-ui-guide.md).

Related panels that render only in `main` may declare the same optional
`collection` object with `id`, localized `title`, `icon`, `order`, and
`tabOrder`. A collection does not create a separate entry; after a catalog card opens one member,
the Host renders a tab for each enabled panel. Collection panels must include `main` and use it as
`defaultPlacement`. Panels from different plugins may share an ID only when
their title, icon, and collection order are identical. Collection order and tab
order are deterministic, and switching tabs still disposes the old panel
before mounting the new one.

For a catalog-backed panel, `frontend_integration.catalog.icon` is the canonical
icon across the Host card, content navigator, Workspace heading, and collection
tab. `WorkspacePanelDefinition.icon` is used only as the fallback for a panel
without a catalog entry. Keep both icons semantically aligned, but do not rely
on the registered panel icon to override the Host catalog.

The Host consumes horizontal wheel, trackpad, and Magic Mouse gestures at the page root to prevent
Safari history rubber-banding. A plugin-owned horizontal region must explicitly use
`overflow-x: auto` or `scroll`; the Host routes the gesture to the nearest such overflow container
and keeps consuming it at either edge. Do not depend on horizontal `body` overflow or intercept
ordinary vertical scrolling and `Ctrl`+wheel zoom.

The four-page product UI executes only `before_send`. Historical hook names remain available for registration and cleanup compatibility, but the Agent does not invoke `send_intercept`, `transform_input`, `route_message`, or `after_receive`. From `before_send`, the Host accepts only whitelisted non-identity context, rewrites chat, message, and skill identity, and always posts to `/api/agent/chat`.

Companion plugins use only `window.ChatRaw.modules`. The machine-readable contract is [module-plugin-sdk-v1.json](../backend/contracts/module-plugin-sdk-v1.json). They must never fetch a module URL directly, retain module credentials, use the legacy proxy as a module tunnel, or invent actor/capability identity.

Module SDK 1.6 exposes the validated `workspace_panel_id` and `catalog` metadata in feature status. The browser must still compute Plugin runtime readiness from the current tab's actual Workspace registration; service readiness alone never makes a card openable.

The product activates only the light theme. The Host retains unactivated public `[data-theme="dark"]` CSS token aliases so existing plugins do not lose public variable references. Plugins must not treat those aliases as a user-facing theme option or switch the root theme themselves.

Plugin and Resident visual work must also follow the [frontend color requirements](frontend-color-requirements.md). Use the public semantic variables as read-only fallbacks and keep all selectors below the assigned root.

SDK 1.5 adds the `conversation` presentation. It requires `chat_id` and
`user_message`; Core owns the inline activity timeline, subscription, recovery,
approval, and artifacts without opening the task center. A conversation
message's `content` is the only rendered and copied answer body. Streaming task
output updates a Core-owned virtual assistant message; after terminal
projection, the persisted assistant message replaces that virtual message by
ID. Plugins must not render `task.result` or `chat_projection` as a second
answer. `task_center` remains the default and `embedded` remains caller-owned.
Resource uploads and downloads remain same-origin and session-protected.
Plugins must not persist task content or resource URLs, infer module endpoints,
guess media types, or fall back to another upload path.

### Compatibility and acceptance

Honor the module's companion version range and action capability flags. Fail closed to normal ChatRaw behavior when a module is unavailable. Validate syntax, package integrity, both roles in a real browser, task recovery, outage behavior, and absence of credentials in browser-visible state.
