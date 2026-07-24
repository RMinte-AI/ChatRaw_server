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

模块也不能直接给 ChatRaw 注入前端。大型功能使用“模块 + 配套插件”；如果入口必须随 Server 常驻，则使用“模块 + 源码级 Resident Integration”。Resident 不是插件包，详见 [Resident Module Integration Guide](resident-module-integration-guide.md)。

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

卸载、停用或重新加载时，ChatRaw 会清理已登记 hook、补全和工具栏按钮。插件自己建立的定时器、事件监听或外部对象仍应由插件清理。

公共工具栏 API：

- `ChatRawPlugin.ui.registerToolbarButton(definition, pluginId)`
- `ChatRawPlugin.ui.unregisterToolbarButton(buttonId, pluginId)`
- `ChatRawPlugin.ui.setButtonState(buttonId, state, pluginId)`
- `ChatRawPlugin.ui.openFullscreenModal(options, pluginId)`
- `ChatRawPlugin.ui.closeFullscreenModal()`

不要使用 `querySelector` 定位 ChatRaw 内部按钮，也不要读取 `_x_dataStack` 等框架内部状态。

### 7. Hook

使用：

```js
ChatRawPlugin.hooks.register('send_intercept', {
    priority: 100,
    async handler(context) {
        return null;
    }
});
```

已公开的 hook 名称由 `ChatRawPlugin.hooks.available()` 返回。插件必须处理“不接管”的情况：

- 返回 `null`，或
- 返回 `{ success: false }`。

只有明确返回 `{ success: true, handled: true }` 时，`send_intercept` 才接管发送。异常不能被当作成功；除 `AbortError` 外，ChatRaw 会记录错误并继续尝试安全路径。

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
        chat_id: ChatRawPlugin.utils.getCurrentChatId() || undefined
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

ChatRaw 的任务中心归 Server 所有。每次 `startTask` 都会登记一个独立任务；刷新页面后恢复全部已登记任务，后台任务继续订阅，用户可以在任务间切换。插件不要自己复制任务列表、审批弹窗或产物凭证。

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

Companion plugins use only `window.ChatRaw.modules`. The machine-readable contract is [module-plugin-sdk-v1.json](../backend/contracts/module-plugin-sdk-v1.json). They must never fetch a module URL directly, retain module credentials, use the legacy proxy as a module tunnel, or invent actor/capability identity.

### Compatibility and acceptance

Honor the module's companion version range and action capability flags. Fail closed to normal ChatRaw behavior when a module is unavailable. Validate syntax, package integrity, both roles in a real browser, task recovery, outage behavior, and absence of credentials in browser-visible state.
