# ChatRaw Resident Module Integration Guide

## 中文

### 1. 它解决什么问题

Resident Integration 用于“需要长期存在于 ChatRaw 界面，但后端能力仍由独立模块提供”的功能。它是随 ChatRaw Server 源码一起审查、构建和发布的前端集成包。

它不改变模块边界：

```text
Resident UI → ChatRaw Module SDK → ChatRaw Server → Module Protocol → Module
```

模块进程永远不能向浏览器提供或注入 JavaScript。Resident 也不能直连模块地址、读取模块 Token，或绕过 ChatRaw 登录、角色和模块启用状态。

### 2. 什么时候选择它

选择普通配套插件：

- 功能通过工具栏或侧栏入口打开插件工作台；
- 希望管理员在 WebUI 中安装、启停或升级前端入口；
- 不需要修改 ChatRaw Server 源码并重新构建。

选择 Resident Integration：

- 功能入口及其工作区必须随 Server 源码长期存在；
- 需要一个由 ChatRaw 托管的稳定工作区；
- 前端代码可以进入 Server 源码审查和发布流程；
- 接受“修改源码、重新构建、重新部署”这一交付方式。

Resident 不是插件的更高权限版本，也不是运行时模块市场。WebUI 只显示 Resident 的构建状态和对应模块状态，不动态安装、删除或改写 Resident 源码。

Resident 的源码存在不代表必须显示入口。对应 Module 尚未完成配对、审核、配置和首次启用时，
Server 对普通界面隐藏该入口；已经启用过的功能如果后来发生故障，入口可以保留并显示当前状态，
便于用户识别已部署能力与临时故障。

### 3. 冻结边界

Resident 只能写在自己的目录：

```text
ResidentIntegrations/<integration-id>/
├── integration.json
├── main.js
├── styles.css
└── tests/
```

一个集成包不得直接修改：

- `backend/static/app.js`
- `backend/static/index.html`
- ChatRaw 内部 Alpine 状态
- 插件目录或其他 Resident 目录
- 模块后端源码

如果现有挂载位或 SDK 不够，停止集成开发，先提出通用的 ChatRaw Host 能力变更。不要在集成包中查询私有 DOM、复制内部函数或临时增加全局变量。

当前稳定挂载位：

- `sidebar`：侧边栏常驻入口；
- `composer`：聊天输入区常驻入口。

两种入口都打开由 ChatRaw Core 管理的 Resident workspace。集成只负责在收到的 `container` 中渲染自己的内容。

### 4. 模块 manifest

Resident 模式的模块必须声明：

```json
{
  "frontend_integration": {
    "mode": "resident",
    "id": "example-workbench",
    "version_range": ">=1.0.0,<2.0.0"
  }
}
```

`frontend_integration` 与旧字段 `companion_plugin` 只能存在一个。旧 `companion_plugin` 会被 Server 规范化为 `mode: plugin`，已有模块不需要迁移。

Resident 的 `id` 和版本范围属于模块审批权限面。修改模式、ID 或版本范围会触发管理员重新审批。参考双模式 manifest：

- [Plugin manifest](../examples/reference-module/manifest.example.json)
- [Resident manifest](../examples/reference-module/manifest.resident.example.json)

### 5. integration.json

描述文件由 [resident-integration-v1.schema.json](../backend/contracts/resident-integration-v1.schema.json) 定义：

```json
{
  "schema_version": "1",
  "id": "example-workbench",
  "version": "1.0.0",
  "module_id": "com.example.module",
  "name": {
    "en": "Example workbench",
    "zh": "示例工作台"
  },
  "description": {
    "en": "Runs the example module.",
    "zh": "使用示例模块。"
  },
  "minimum_role": "member",
  "entrypoints": [
    {
      "id": "open-example",
      "placement": "sidebar",
      "icon": "ri-layout-grid-line",
      "label": {
        "en": "Example",
        "zh": "示例"
      },
      "order": 70
    }
  ],
  "required_actions": [
    {
      "action_id": "example.run",
      "version_range": ">=1.0.0,<2.0.0"
    }
  ],
  "main": "main.js",
  "styles": "styles.css"
}
```

约束：

- 目录名必须等于 `id`；
- `module_id` 必须等于模块 manifest 的 `module_id`；
- `version` 必须满足模块声明的 Resident 版本范围；
- 每个 `required_actions` 必须存在且 Action 版本兼容；
- Resident 的 `minimum_role` 不能低于它调用的 Action 角色；
- `main` 和 `styles` 只能是当前目录根部文件名；
- ID、入口 ID 和 Action ID 必须唯一。

### 6. 注册与挂载

构建器把所有 Resident 源码生成到：

```text
backend/static/resident-integrations/
├── catalog.json
├── resident-integrations.min.js
└── resident-integrations.min.css
```

这些是生成文件，不要手工编辑。启动时 Server 会严格验证 catalog；缺失或无效时启动失败，避免界面和后端处于不确定状态。

`main.js` 只在构建包加载期间注册一次：

```js
(function () {
    'use strict';

    ChatRawResident.register({
        id: 'example-workbench',
        mount(context) {
            const root = context.container;
            root.replaceChildren();

            const button = document.createElement('button');
            button.textContent = context.t({
                en: 'Run',
                zh: '运行'
            });
            root.append(button);

            return () => {
                root.replaceChildren();
            };
        }
    });
})();
```

`mount(context)` 可以使用：

- `container`：唯一允许写入的 DOM 容器；
- `moduleId`：catalog 中绑定的模块 ID；
- `modules`：`window.ChatRaw.modules`；
- `t(localizedText)`：按当前语言选择文本；
- `showToast(message, type)`：显示 ChatRaw 提示；
- `getCurrentChatId()`：读取当前聊天 ID。

返回 cleanup 函数，用于移除监听器、定时器、订阅和集成自己的 DOM。正式机器契约见 [resident-integration-sdk-v1.json](../backend/contracts/resident-integration-sdk-v1.json)。

### 7. 调用模块与嵌入式任务

Resident 只能通过 Module SDK 调用模块：

```js
const task = await context.modules.startTask(
    {
        module_id: context.moduleId,
        action_id: 'example.run',
        input: { text: 'hello' }
    },
    { presentation: 'embedded' }
);
```

`presentation`：

- `task_center`：默认值；启动任务并打开 ChatRaw 核心任务中心；
- `embedded`：启动并登记任务，但不自动打开任务中心或自动建立 SSE；Resident 使用 `subscribe()` 在自己的工作区展示进度。
- `conversation`：要求 `chat_id` 和 `user_message`；由 ChatRaw Core 在对应对话中展示和恢复，不打开任务中心。

读取历史任务：

```js
const tasks = await context.modules.listTasks({
    module_id: context.moduleId,
    action_id: 'example.run',
    limit: 20
});
```

审批、取消、产物、安全错误和任务持久化仍由 ChatRaw Core 管理。Resident 不复制这些后端协议，也不建立通用查询通道。完整接口见 [module-plugin-sdk-v1.json](../backend/contracts/module-plugin-sdk-v1.json)。

### 8. 用户体验与状态

- 用户角色低于 `minimum_role`：不显示入口；
- 角色符合但模块未连接、未审批、未启用、故障或不兼容：入口保留并置灰；
- 模块和 Resident 契约均就绪：入口可用；
- 普通用户可以使用已启用功能，不能管理插件、模块或 Resident；
- 管理员在 Modules 设置中管理模块，不能在 WebUI 动态删除 Resident 源码。

Resident 入口被置灰不是前端自行判断网络状态，而是读取 Server 的 `getFeatureStatus()` 结果。

### 9. 面向 AI 的修改协议

AI 开始修改前必须完整读取：

1. 本指南；
2. [resident-integration-v1.schema.json](../backend/contracts/resident-integration-v1.schema.json)；
3. [resident-integration-sdk-v1.json](../backend/contracts/resident-integration-sdk-v1.json)；
4. [module-plugin-sdk-v1.json](../backend/contracts/module-plugin-sdk-v1.json)；
5. [reference-module-workbench](../ResidentIntegrations/reference-module-workbench/)；
6. 对应模块 manifest 和 Action Schema。

AI 必须先输出并冻结：

- integration ID、模块 ID 和最低角色；
- 使用的挂载位；
- 需要的 Action 与版本范围；
- 需要的 SDK 方法；
- 允许修改的文件清单；
- 正向、禁用、不兼容、权限不足和重启测试。

遇到以下任一情况必须停止并解释，不得自行扩大修改面：

- 需要修改 `app.js`、`index.html` 或内部 Alpine 状态；
- 需要直连模块、私有依赖或新增浏览器凭证；
- 需要现有契约没有的 Host 能力；
- 需要运行时下载或执行模块提供的代码；
- 无法用稳定 Action Schema 表达输入或输出。

### 10. 构建与验收

```bash
npm run build:frontend
npm run check:frontend
npm run test:frontend
./scripts/run-t6-source-gate.sh
T6_FRONTEND_MODE=resident \
T6_SOURCE_SERVER_PORT=51122 \
T6_SOURCE_MODULE_PORT=8766 \
./scripts/run-t6-source-gate.sh
```

Resident 变更至少证明：

- 描述文件和生成 catalog 有效；
- 注册 ID 与 catalog 一致；
- 不可用入口可见但禁用，角色不符合时隐藏；
- 默认任务中心行为没有回归；
- `embedded` 不自动打开任务中心；
- 内容通过安全 DOM API 输出，不执行模块返回的 HTML；
- cleanup 真正取消订阅和监听；
- 旧 `companion_plugin` manifest、旧插件和 Source/Compose 模块继续工作。

参考实现：[reference-module-workbench](../ResidentIntegrations/reference-module-workbench/)。

---

## English

### 1. Purpose and boundary

A Resident Integration is source-reviewed frontend code shipped in the ChatRaw Server build for a module feature that needs a persistent ChatRaw entry point.

```text
Resident UI → ChatRaw Module SDK → ChatRaw Server → Module Protocol → Module
```

The module process never supplies browser code. A Resident Integration never calls a module address directly, reads module credentials, or bypasses ChatRaw authentication, roles, review, and enablement.

Use a companion plugin when an administrator should install, enable, disable, or upgrade the frontend entry at runtime; a plugin entry may choose the toolbar or sidebar mount. Use a Resident Integration when the entry and workspace must be reviewed, rebuilt, and deployed with Server source rather than installed dynamically.

Resident is not a privileged plugin or a runtime marketplace. The WebUI reports its build and module status; it does not dynamically install or rewrite Resident code.

A source-built Resident is not automatically visible. The ordinary UI hides its entry until the matching
Module has completed setup and first enablement. After first enablement, a later outage may keep the entry
visible with its current status so users can distinguish a deployed feature from an unconfigured one.

### 2. Source package

Each integration is isolated:

```text
ResidentIntegrations/<integration-id>/
├── integration.json
├── main.js
├── styles.css
└── tests/
```

Integration code must not patch `app.js`, `index.html`, Alpine internals, another integration, a plugin, or module backend source. If the stable `sidebar` and `composer` mounts or the documented SDK are insufficient, stop and propose a generic Host contract change first.

The module selects Resident mode with:

```json
{
  "frontend_integration": {
    "mode": "resident",
    "id": "example-workbench",
    "version_range": ">=1.0.0,<2.0.0"
  }
}
```

Exactly one of `frontend_integration` and legacy `companion_plugin` is allowed. Legacy plugin declarations remain supported and normalize to plugin mode without permission-review churn.

### 3. Contracts and lifecycle

Use:

- [Resident descriptor schema](../backend/contracts/resident-integration-v1.schema.json)
- [Resident Host SDK](../backend/contracts/resident-integration-sdk-v1.json)
- [Module browser SDK](../backend/contracts/module-plugin-sdk-v1.json)
- [Reference Resident](../ResidentIntegrations/reference-module-workbench/)
- [Resident reference manifest](../examples/reference-module/manifest.resident.example.json)

The descriptor binds one stable integration ID and version to one module ID, minimum role, entry points, and required Action versions. The build produces a catalog and JS/CSS bundles under `backend/static/resident-integrations/`; these generated files must not be edited manually. Server validates the catalog at startup and fails closed.

During bundle loading, `main.js` registers exactly one `{id, mount}` definition with `ChatRawResident.register`. `mount(context)` receives only the Server-owned container, bound module ID, Module SDK, localization helper, toast helper, and current chat ID helper. It returns an optional cleanup function.

Eligible users always see the entry. It is disabled when the module, approval, enablement, health, Resident version, or required Action contract is unavailable. Users below `minimum_role` do not see it. Members may use enabled features but cannot manage modules, plugins, or Resident source.

### 4. Embedded tasks

`context.modules.startTask(request)` keeps the existing default, opens the core
task center, and subscribes. `{presentation: "embedded"}` registers without
opening or subscribing, so the Resident owns presentation. The additive
`conversation` mode requires `chat_id` and `user_message`; Core renders and
recovers it inside that chat without opening the task center.
`listTasks(filters)` retrieves the authenticated task list by module, Action,
state, chat, and limit. Approvals, cancellation, artifacts, persistence, and
security errors remain Core-owned.

There is intentionally no generic module query API. Add a typed Module Action when the integration needs new backend behavior.

### 5. AI stop rules and acceptance

Before editing, an AI must read all three machine contracts, this guide, the reference Resident, and the target module Action schemas. It must freeze the integration ID, module ID, role, placements, required Actions, SDK calls, writable files, and test cases.

The AI must stop instead of broadening scope if it needs to patch Core files, inspect private DOM or Alpine state, connect directly to a module or private dependency, introduce browser credentials, execute module-supplied code, or use an undocumented Host capability.

Build and verify:

```bash
npm run build:frontend
npm run check:frontend
npm run test:frontend
T6_FRONTEND_MODE=resident \
T6_SOURCE_SERVER_PORT=51122 \
T6_SOURCE_MODULE_PORT=8766 \
./scripts/run-t6-source-gate.sh
```

Acceptance must cover catalog validation, exact registration, role visibility, disabled states, compatible Action versions, embedded presentation, safe text rendering, cleanup, restart recovery, and regression compatibility for legacy plugin modules.
