# ChatRaw Server 用户指南 / User Guide

## 中文

### 1. 先理解这是一个共享平台

ChatRaw Server 的所有用户使用同一个平台。聊天、文档、模型能力、插件和模块不是按用户创建独立副本。

- 你必须登录后才能进入主界面或访问业务 API。
- 普通用户可以使用管理员已经启用的功能。
- 普通用户不能安装、停用或删除插件与模块。
- 经典版导入的数据没有创建者，普通用户可以使用，但只能由管理员改名或删除。
- 新数据会记录创建者，用于防止普通用户互相修改；这不代表数据对其他用户不可见。

如果业务需要公司或客户之间的强数据隔离，应部署不同的 ChatRaw Server 实例，而不是在同一实例中创建多个用户。

### 2. 登录和账户

打开管理员提供的 ChatRaw Server 地址。未登录时，所有业务页面和 `/api/*` 数据接口都会要求认证。
平台不提供公开的用户自助注册；账户由管理员创建。管理员可以调整账户角色、停用或重新启用账户，
也可以重置其他用户的密码。角色变更、停用或管理员重置密码后，现有登录会话会失效，需要重新登录。

登录后可以在“设置 → Account”中：

- 查看用户名和角色；
- 修改自己的密码；
- 退出登录。

登录页和首次初始化页右上角可直接选择 `English` 或 `中文`。进入主界面后，
所有登录用户都可以在“设置 → Account”中切换语言；选择会保存在当前浏览器中，并应用到核心界面的
标签、按钮、状态、确认提示、警告和错误消息。插件或 Resident Integration 提供的功能也应跟随
同一语言设置；模块协议返回的机器状态值不会直接作为界面文案显示。

当前产品只提供浅色界面，不提供深色模式开关。

修改密码后现有会话会失效，需要使用新密码重新登录。不要共享账号，不要把浏览器 Cookie 当作 API Token 保存。

### 3. 首页、内容页与 Agent

登录后首页只展示三个固定分类：`数据中枢`、`知识中枢`、`业务中枢`。切换分类会显示对应的业务卡片；卡片只有在配套 Module 可用且 Companion Plugin 已安装启用时才能打开。点击卡片进入独立内容页，左侧内容导航高亮当前卡片，返回按钮回到首页。设置按钮打开单独的全页设置界面。旧版聊天侧栏已经移除，不再承载会话、Plugin 或 Resident 入口。

右下角 Hermes Agent 浮窗是当前产品唯一的通用对话入口：

1. 点击 Agent 圆形按钮打开当前对话；
2. 点击浮窗顶部的加号新建对话，点击其右侧的历史按钮查看会话列表；
3. 可以切换、内联改名或删除自己的会话。历史面板右上角的垃圾桶按钮会在确认后一次清理所有空闲会话；正在生成回复或执行 Module 任务的会话会被保留；
4. 输入区不再提供 Hermes Agent 选择按钮或思考模式开关；发送消息即固定进入 Hermes Agent；
5. 点击浮窗顶部的窗口扩展按钮，可在不离开当前页面的情况下打开全屏浮动对话窗口，便于查看宽表格和模型渲染内容。

输入区只直接显示上传图片、上传文档和解析网页三个核心操作。存在当前用户可见的 Plugin 或
Resident 入口时，右侧会出现向上箭头；点击后在输入框上方打开扩展面板。安装或启用扩展只会
让入口出现，不会自动执行。键盘用户可直接聚焦三个核心操作和扩展箭头；打开面板后焦点进入
第一个可用入口，按 `Esc` 关闭并返回箭头。当前用户有权看到但 Module 暂不可用的 Resident 会保留为禁用项。

Hermes Agent 会话只对创建它的登录用户可见，其他普通用户和管理员都不能通过 Agent 或经典聊天接口枚举、读取、改名或删除。业务模块数据、文档以及保留的经典聊天仍遵循共享平台边界。

消息中的宽 Markdown 表格会限制在消息区域内，并提供独立的横向滚动。可以在表格上使用触控板、
Magic Mouse 的横向手势，或按住 Shift 使用鼠标滚轮。ChatRaw 会在整个页面接管横向手势：
位于可横向滚动区域时只滚动该区域，位于首页或普通内容时直接停止，因此滚到边缘或在空白处
继续滑动都不会拉出 Safari 的前进/后退页面。普通纵向滚动和捏合缩放不受影响。

### 4. 功能套件：插件和模块

一个大型功能通常由后端模块和一种前端入口组成：

- **配套插件**：由管理员在 WebUI 安装和启停的按钮、开关或结果展示。
- **Resident Integration**：随 Server 源码构建、由 Agent 扩展面板承载的常驻入口。
- **后端模块**：在独立服务中执行真正的任务。

普通用户不需要分别配置它们。管理员完成安装和连接后，功能入口会自动可用。

业务入口由首页卡片统一承载。界面设置中的副标题显示在首页中央 Logo 下方；空副标题不会占据
首页空间。三个分类由 Host 固定，卡片名称、顺序、说明、图标和目标面板来自已注册 Module 的
严格 Manifest；当前浏览器还会确认配套 Plugin 面板已经加载并支持主内容区。单个入口配置错误
只会禁用该卡片。

配套插件可以在主内容区打开交互工作台。工作台可能出现在聊天右侧、上侧、下侧，或占据整个
主区域；右、上、下模式不会阻止继续操作聊天。窄屏设备会统一显示为主区域；高度很低时，
上、下模式也会显示为主区域。工作台关闭后，
当前聊天和消息不会丢失；刷新页面后工作台保持关闭。标题栏由 ChatRaw 提供，
用户点击或用键盘激活 ChatRaw 提供的所属插件入口时，键盘焦点会进入工作台标题，关闭后
返回原入口。模块任务、定时器、插件内其他控件或其他后台流程打开工作台时，当前焦点保持不变。
工作台内的表单、列表和业务状态由对应插件提供。

管理员升级、启停或删除插件时，已打开标签页中的旧插件工作台会被关闭并切换到当前版本。正在编辑但尚未提交的插件表单不会跨版本保留；请从最新入口重新打开工作台后继续操作。

Plugin 不会直连 Module 或 Hermes，也拿不到 Module、Hermes、LinkDB 的地址和凭证；所有调用仍经过 ChatRaw 后端的同源接口和权限检查。

#### Agent 规则作用域

每位用户可以创建和管理自己的个人规则。管理员还可以发布系统默认规则；激活后，
它会进入所有用户后续新建的 Agent 任务。普通用户能看到系统规则的名称、激活状态、
版本和哈希，但不能打开 Source、编译原文、错误详情或历史候选。

创建 Source、保存新版本或编译候选都不会自动生效，必须明确激活。每个任务在创建时
冻结当时有效的规则作用域、Compiled 版本和哈希，因此修改或停用规则不会改变在途或
历史任务；同一聊天中的下一次发送会创建新任务并读取最新规则。个人规则与系统默认
规则冲突时，个人规则优先，但不能覆盖平台安全限制。

未激活的个人规则可以删除；激活规则必须先停用。删除后规则会从列表消失并允许同名
新建，但不会影响已经冻结该版本的在途或历史任务。管理员对系统规则遵循同样的
“先停用、再删除”要求；普通成员没有系统规则删除权限。

### 5. 任务状态

模块任务可能出现：

| 状态 | 含义 |
|---|---|
| Queued | 已提交，等待模块处理 |
| Running | 模块正在执行 |
| Waiting approval | 等待你批准或拒绝敏感步骤 |
| Cancel requested | ChatRaw 已请求取消，等待模块确认 |
| Succeeded | 已成功完成 |
| Failed | 已失败，界面显示安全的错误说明 |
| Cancelled | 已取消 |

并非所有模块都支持取消、审批、流式输出或产物下载。界面只会展示模块在 manifest 中声明并通过管理员审批的能力。

刷新页面后，ChatRaw 会根据任务 ID恢复仍在执行的任务。浏览器不保存模块地址、模块 Token、任务输入或任务输出。
右下角任务入口只显示仍在运行或有尚未查看结果的任务；查看终态后入口消失。直接在对话或
Resident 工作区中展示的任务不会重复出现在这个全局入口中。

对话内的“执行过程”只包含模块明确提供的计划和工具活动，不是模型隐藏思维链。工具参数和结果是
经过脱敏、截断的预览；最终答案使用同一条消息中的唯一正文区域。

### 6. 功能不可用时

如果功能入口显示不可用：

- `Plugin missing/disabled/incompatible`：配套插件未安装、未启用或版本不兼容。
- `Resident missing/incompatible`：当前 Server 构建未包含匹配的常驻入口，或它与模块版本不兼容。入口会保留但置灰。
- `Module unhealthy/unreachable`：模块未运行或网络不可达。
- `Module not ready`：模块依赖或配置未就绪。
- `Review required`：模块版本或权限发生变化，等待管理员重新批准。
- `Module disabled`：管理员已停用。

普通用户不应尝试修改模块地址。把界面显示的状态和发生时间提供给管理员即可。

当 Hermes Agent 不可用时，浮窗显示错误并保留当前会话；系统不会把消息改送到普通聊天或其他模型。

### 7. 安全注意事项

- 只使用管理员提供的 Server 地址。
- 不要在聊天中粘贴不必要的访问令牌、Cookie 或生产密钥。
- 审批对话框只表示当前任务请求的动作，不是永久授权。
- 下载模块产物后，由本机安全策略负责扫描和保存。
- 发现自己能够打开用户、插件或模块管理入口时，停止操作并报告管理员。

### 8. 获取帮助

向管理员提供：

- 发生时间；
- 使用的功能名称；
- 当前聊天 ID（如可见）；
- 页面显示的公开错误码；
- Hermes Agent 浮窗或具体业务卡片是否可用。

不要发送密码、Cookie、模块 Token、模型 API Key 或 LinkDB 凭证。

---

## English

### 1. One shared platform

All users share one ChatRaw Server instance. Chats, documents, model access, plugins, and modules are not duplicated per user.

- Authentication is required before accessing product pages or APIs.
- Members can use features enabled by an administrator.
- Members cannot install, disable, or remove plugins or modules.
- Imported classic data has no creator. Members can use it, but only administrators can rename or delete it.
- New data records its creator to prevent members from modifying each other's resources; this is not a visibility boundary.

If separate companies or customers require strong data isolation, deploy separate Server instances.

### 2. Sign-in and account

Use the Server URL supplied by your administrator. After signing in, open **Settings → Account** to view your role, change your password, or sign out.

Every signed-in user can switch between English and Chinese under **Settings → Account**. The selection is stored in the current browser and updates the Host shell without reloading or discarding the active category, Agent session, or Workspace.

The current product exposes only the light interface and has no dark-mode control.

ChatRaw has no public self-registration; an administrator creates accounts. Administrators can
change an account's role, disable or re-enable it, and reset another user's password. A role change,
account disable, or administrator password reset invalidates existing sessions and requires a new
sign-in.

Changing your password invalidates the current session. Sign in again with the new password. Do not share accounts or retain browser cookies as API tokens.

### 3. Home, content, and Agent

After sign-in, the home page has three fixed categories: **Data Hub**, **Knowledge Hub**, and **Operations Hub**. Switching category changes the business cards. A card opens only when its Module is available and its Companion Plugin is enabled. Selecting a card opens a dedicated content view with a highlighted content-navigator entry and a return control. Settings is a separate full-page view. The legacy chat sidebar has been removed and no longer hosts conversations, Plugin entries, or Resident entries.

The bottom-right Hermes Agent popup is the only generic conversation UI:

1. Open the popup to continue the current conversation.
2. Use the plus button in its header to create a session, or the history button immediately to its right to reveal the session list.
3. Switch, rename inline, or delete your own sessions. After confirmation, the trash button in the history-panel header clears all idle sessions in one operation. Sessions generating a response or running Module work are kept.
4. The composer has no Hermes selection button or thinking-mode switch; every message goes directly to Hermes Agent.
5. Use the window-expand button in the popup header to open a full-screen floating conversation window without leaving the current page. This gives wide tables and rendered model content enough room.

The composer directly shows only the image, document, and web-page actions. When the current user has
visible Plugin or Resident entries, an adjacent up-arrow opens the extension palette above the composer.
Installing or enabling an extension only makes its entry available; it never runs the action automatically.
Keyboard users can focus all three core actions and the extension arrow. Opening the palette moves focus to
the first enabled entry; `Escape` closes it and returns focus to the arrow. An eligible but unavailable Resident
remains visible as a disabled entry.

Hermes Agent sessions are private to their creator. Other members and administrators cannot enumerate, read, rename, or delete them through either Agent or classic chat APIs. Module-owned business data, documents, and retained classic chats continue to use the shared-platform boundary.

### 4. Feature suites

A large feature has a backend module and one frontend integration:

- a **companion plugin** installed and managed by an administrator, or a source-built **Resident Integration** for a persistent entry;
- a **backend module** that performs the task in an independent service.

Members do not connect these pieces manually. Once the administrator completes installation and pairing, the feature entry point becomes available.

Business entry points live on the home card grid. The subtitle from Interface settings appears
below the centered home logo; an empty subtitle occupies no space. The Host fixes the three
categories; each registered Module manifest supplies its localized card metadata and target panel.
The current browser also verifies that the Companion Plugin registered that panel with `main`
support. A broken declaration disables only its card.

A companion plugin may open an interactive workspace in the main content area. It can appear to
the right, above, below, or in place of the visible chat surface. Right, top, and bottom workspaces
leave chat interactive. Narrow screens use the main presentation; short screens also use it for
top and bottom workspaces. Closing a workspace preserves the current chat and messages; reloading
the page starts with the workspace closed. When a user activates that plugin's ChatRaw-provided entry
with a click or keyboard, focus moves to the Host workspace title and returns to the entry on close.
Opens from module tasks, timers, controls inside plugin content, or other background flows preserve
the current focus.

When an administrator upgrades, enables, disables, or removes a plugin, open tabs dispose and close
the previous plugin workspace before switching to the current runtime. Unsaved plugin form input is
not carried across versions; reopen the workspace from the current entry before continuing.

Plugins never connect directly to Modules or Hermes and never receive Module, Hermes, LinkDB, or other private credentials. Calls continue through same-origin ChatRaw APIs and authorization checks.

#### Agent rule scopes

Each user can manage personal rules. Administrators may also publish a
system-default rule that applies to every user's future new Agent tasks.
Members can see its name, activation state, version, and hash, but cannot open
its Source, compiler output, validation details, or candidate history.

Creating a Source version or compiling a candidate never activates it.
Each task freezes the effective scope, Compiled version, and hash at creation,
so later activation changes do not alter in-flight or historical tasks. The
next send in the same chat is a new task and reads the latest active rules.
Personal rules take precedence over conflicting system defaults, while platform
security controls remain non-overridable.

The fallback Agent supports aggregate summaries and one explicitly requested
detail page. It does not walk pages for all details or exports in chat. A
single-page result remains explicitly partial, and neither a personal nor a
system rule can raise the fixed safety limits.

An inactive personal rule may be deleted; an active rule must first be
deactivated. It disappears from ordinary lists and its name may be reused, but
in-flight and historical tasks that froze the version remain readable. The
same explicit deactivate-then-delete rule applies to administrator-managed
system defaults; members cannot delete system rules.

### 5. Task states

| State | Meaning |
|---|---|
| Queued | Accepted and waiting for module execution |
| Running | Module work is in progress |
| Waiting approval | A sensitive step needs your decision |
| Cancel requested | ChatRaw requested cancellation |
| Succeeded | Completed successfully |
| Failed | Failed with a safe public explanation |
| Cancelled | Cancellation completed |

Streaming, cancellation, approval, and artifacts are optional action capabilities. ChatRaw only exposes capabilities declared by the manifest and approved by an administrator.

After a page reload, ChatRaw resumes tasks by task ID. The browser does not retain module addresses, tokens, task input, or task output.
The bottom-right task entry only appears for running tasks or results that have not
yet been viewed, and disappears after a terminal result is viewed. Tasks presented
inside a conversation or Resident workspace are not duplicated in this global entry.

The execution process contains explicit module-provided plans and tool activity,
not hidden model reasoning. Tool inputs and results are redacted, bounded previews.

### 6. When a feature is unavailable

Common reasons include:

- companion plugin missing, disabled, or incompatible;
- Resident Integration missing or incompatible;
- module unhealthy or unreachable;
- module dependency or configuration not ready;
- changed permissions awaiting administrator review;
- module disabled by an administrator.

Report the visible status and time to an administrator. Do not attempt to discover or edit the private module address.

If Hermes Agent is unavailable, the popup reports the failure and preserves the current session. It never reroutes the message to normal chat or another model.

### 7. Security

- Use only the Server URL supplied by your administrator.
- Do not paste unnecessary access tokens, cookies, or production keys into chats.
- An approval dialog authorizes one task decision, not permanent access.
- Local security policy applies to downloaded artifacts.
- If a member account can access user, plugin, or module management controls, stop and report it.

### 8. Support information

Provide the time, feature name, public error code, chat ID when available, and whether the Hermes Agent popup or affected business card is available. Never send passwords, cookies, module credentials, model API keys, or LinkDB credentials.
