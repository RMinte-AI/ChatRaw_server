# ChatRaw Module Protocol v1 Developer Guide

## 中文

### 1. 模块是什么

模块是独立运行的后端服务。它适合：

- 长时间或可恢复任务；
- 独立数据库；
- 原生依赖、GPU、局域网服务或高权限操作；
- 不应进入 ChatRaw 后端的复杂业务；
- 需要 Source 和 Docker Compose 两种部署方式的功能。

独立运行的模块进程不是：

- ChatRaw 前端插件；
- 任意代码注入机制；
- Kubernetes、DeFi 或通用应用编排平台；
- 绕过 ChatRaw 登录和权限的后门。

模块进程不能在运行时提供 HTML、JavaScript 或可执行 UI。模块功能的前端接入只能选择：

- 管理员在 WebUI 安装的配套插件；
- 随 ChatRaw Server 源码审查、构建和发布的 Resident Integration。

两种方式都只能通过 ChatRaw Module SDK 连接模块。需要常驻入口时阅读 [Resident Module Integration Guide](resident-module-integration-guide.md)。

### 2. 公开与私有边界

Module Protocol 只定义 ChatRaw Server 与模块之间的北向接口：

```text
ChatRaw Server ⇄ Module Protocol v1 ⇄ Module
                                      ⇄ private dependencies
```

模块内部的数据库、设备、商业协议和私有依赖不属于公共协议。公共 manifest 只描述 ChatRaw 需要审批和调用的部分，不应泄露内部 URL、Token、表结构或私有传输。

Agent–LinkDB 协议是私有实现，不进入本指南、公共 Schema、OpenAPI、示例 manifest 或 conformance 输出。

### 3. 事实来源

发生冲突时，以以下机器可读文件和运行验证为准：

1. [module-manifest-v1.schema.json](../backend/contracts/module-manifest-v1.schema.json)
2. [module-management-v1.schema.json](../backend/contracts/module-management-v1.schema.json)
3. [module-task-v1.schema.json](../backend/contracts/module-task-v1.schema.json)
4. [module-plugin-sdk-v1.json](../backend/contracts/module-plugin-sdk-v1.json)
5. [resident-integration-v1.schema.json](../backend/contracts/resident-integration-v1.schema.json)
6. [Reference plugin manifest](../examples/reference-module/manifest.example.json)
7. [Reference Resident manifest](../examples/reference-module/manifest.resident.example.json)
8. [Reference module implementation](../examples/reference-module/app.py)
9. `scripts/module-conformance.py`
10. `scripts/run-t6-source-gate.sh` 与 `scripts/run-t6-compose-gate.sh`

文档不能扩展这些契约中不存在的能力。

### 4. 最小目录

```text
my-module/
├── module_manifest.json
├── app.py
├── requirements.txt
├── Dockerfile
├── compose.yml
├── deploy/
│   └── module.env.example
└── tests/
    └── test_module_protocol.py
```

参考模板：[examples/reference-module](../examples/reference-module/)。

模块必须将运行数据放在明确的数据目录中，不能把状态只保存在进程内存。至少持久化：

- 稳定的 `instance_id`；
- 已配对的访问凭证摘要；
- 配置 revision 和秘密配置状态；
- task、event、approval 和 artifact 元数据；
- 重启后恢复任务所需的业务状态。

不要明文保存 Pairing Code 或访问 Token。Token 只返回一次，模块持久化其安全摘要。

### 5. manifest

最小结构：

```json
{
  "schema_version": "1",
  "module_id": "com.example.echo",
  "module_version": "1.0.0",
  "protocol_version": "1.0.0",
  "name": "Example Echo",
  "description": "Runs a durable example task.",
  "actions": [],
  "config_schema": {
    "type": "object",
    "additionalProperties": false,
    "properties": {}
  },
  "requested_host_capabilities": [],
  "companion_plugin": {
    "id": "example-echo-companion",
    "version_range": ">=1.0.0,<2.0.0"
  },
  "administration": {
    "supports_data_purge": false
  }
}
```

以上是兼容的插件写法。新 manifest 也可以使用规范形式：

```json
{
  "frontend_integration": {
    "mode": "plugin",
    "id": "example-echo-companion",
    "version_range": ">=1.0.0,<2.0.0"
  }
}
```

常驻源码集成使用：

```json
{
  "frontend_integration": {
    "mode": "resident",
    "id": "example-echo-workbench",
    "version_range": ">=1.0.0,<2.0.0"
  }
}
```

`companion_plugin` 和 `frontend_integration` 必须且只能出现一个。旧字段会规范化为 plugin 模式，不要求已有模块修改 manifest。

规则：

- `module_id` 是产品身份，发布后保持稳定。
- `instance_id` 是一次具体部署身份，不写进 manifest，由 Pair API 返回。
- `module_version`、`protocol_version` 和 Action version 使用 SemVer。
- Server 当前接受协议主版本 1。
- Action ID 在一个 manifest 中唯一。
- `minimum_role` 只能是 `member` 或 `admin`。
- 输入、输出和配置使用 Server 支持的 JSON Schema 子集。
- 配置必须是 `additionalProperties: false` 的闭合对象。
- 秘密字段使用 `"x-chatraw-secret": true`。
- manifest 不包含模块地址、密钥、前端代码或私有依赖细节。

权限相关变化会改变 permission digest，包括：

- 模块主版本；
- Host Capability；
- Action 主版本；
- 输入/输出 Schema；
- 完整配置 Schema（包括新增秘密字段）；
- 最低角色；
- stream/cancel/approval/artifact/chat projection 标志；
- 前端集成模式、ID 和版本约束；
- data purge 能力。

这些变化会触发管理员重新审批。permission digest 带有独立版本号；开发者不能自行计算一个“兼容摘要”绕过 Server 的复审逻辑。

### 6. 管理接口

固定前缀：

```text
/chatraw-module/v1
```

| 方法与路径 | 鉴权 | 用途 |
|---|---|---|
| `POST /pair` | Pairing Code | 一次性配对并返回访问 Token |
| `GET /manifest` | Bearer | 返回 manifest |
| `GET /health` | Bearer | 进程和核心依赖健康状态 |
| `GET /ready` | Bearer | 是否可以接收任务 |
| `GET /config` | Bearer | 返回脱敏配置视图 |
| `PUT /config` | Bearer | revision 乐观锁更新配置 |
| `POST /disconnect` | Bearer | 断开并保留模块数据 |
| `POST /purge-data` | Bearer | 可选，永久清除模块数据 |

Pair 请求：

```json
{
  "pairing_code": "one-time-code",
  "host": {
    "product": "ChatRaw Server",
    "module_protocol": "1.0.0",
    "capability_base_url": "https://chatraw.example.com"
  }
}
```

Pair 响应：

```json
{
  "module_id": "com.example.echo",
  "instance_id": "stable-installation-id",
  "access_token": "returned-only-once"
}
```

Pairing Code 必须：

- 至少 16 个字符；
- 有短有效期；
- 只能成功消费一次；
- 不写入日志和公共响应；
- 成功后不能再次换取 Token。

模块必须要求部署者显式注入 Pairing Code；没有有效 Code 时启动失败。不要自动生成一个无法安全取回的 Code，也不要通过标准输出、健康接口或容器日志交付它。

访问 Token 保护 `/pair` 之外的所有接口。错误 Token 返回 401，响应和日志不能泄露正确 Token。

Health：

```json
{"status": "healthy"}
```

不健康时返回 HTTP 503 和 `{"status":"unhealthy"}`。

Ready：

```json
{
  "ready": false,
  "reasons": ["configuration_missing"]
}
```

Health 表示模块是否正常运行；Ready 表示是否能接收新任务。不要用 HTTP 200 的空响应伪装 Ready。

配置视图：

```json
{
  "revision": "3",
  "values": {
    "mode": "safe"
  },
  "secret_configured": {
    "service_key": true
  },
  "configured": true,
  "missing_required": []
}
```

秘密永不回显。更新秘密只接受：

- `{"action":"keep"}`
- `{"action":"clear"}`
- `{"action":"replace","value":"..."}`

revision 不匹配返回 409。

Disconnect 请求固定为：

```json
{"preserve_data": true}
```

Purge 仅在 manifest 声明支持时实现，请求 confirmation 为：

```text
PURGE <module_id>
```

成功响应固定为 `{"purged":true}`。

### 7. 任务接口

固定前缀：

```text
/chatraw-module/v1/tasks
```

| 方法与路径 | 用途 |
|---|---|
| `POST /tasks` | 幂等创建任务 |
| `GET /tasks/{task_id}` | 获取任务摘要 |
| `GET /tasks/{task_id}/events` | SSE 事件流与断线续传 |
| `POST /tasks/{task_id}/cancel` | 请求取消 |
| `POST /tasks/{task_id}/approvals/{approval_id}` | 批准或拒绝 |
| `GET /tasks/{task_id}/artifacts/{artifact_id}` | 下载模块原始产物 |
| `GET|HEAD /tasks/{task_id}/resources/{resource_id}` | 流式返回声明的任务输出资源 |

Server 创建任务时发送：

```json
{
  "task_id": "uuid",
  "request_digest": "sha256",
  "action_id": "echo.task",
  "action_version": "1.0.0",
  "config_revision": "3",
  "input": {
    "text": "hello"
  },
  "host_capabilities": []
}
```

幂等规则：

- `task_id` 是稳定身份。
- 同一 `task_id` 和同一 `request_digest` 重试时，返回同一个任务。
- 同一 `task_id` 但不同 digest 返回 409。
- 模块不能因网络重试重复执行副作用。

任务公开状态：

```text
queued
running
waiting_approval
cancel_requested
succeeded
failed
cancelled
```

只有 `succeeded`、`failed`、`cancelled` 是终态。失败任务必须返回稳定的 `outcome_code`。成功任务可以返回符合 output Schema 的 `result`，以及声明支持时的 `chat_projection`、artifacts 和 resources。

任务摘要：

```json
{
  "task_id": "uuid",
  "action_id": "echo.task",
  "action_version": "1.0.0",
  "config_revision": "3",
  "state": "running",
  "last_event_id": 4
}
```

字段必须严格匹配任务身份，不能在运行中切换 Action 或配置 revision。

### 8. SSE

事件格式：

```text
id: 5
event: task.progress
data: {"progress":0.5,"message":"Working"}

```

事件类型：

- `task.status`
- `task.progress`
- `output.delta`
- `output.snapshot`
- `approval.requested`
- `approval.resolved`
- `activity.updated`
- `artifact.added`
- `task.terminal`

要求：

- event ID 从 1 开始严格递增；
- 持久化事件后再发送；
- 支持 `Last-Event-ID`；
- 重连时重放所有 `id > Last-Event-ID` 的事件；
- 可以发送以 `:` 开头的 heartbeat；
- 终态事件之后结束流；
- Server 可能同时通过 GET task 摘要对账，摘要是恢复依据；
- 不把 Token、私有 URL 或内部 trace 放入事件。

`output.delta` 适用于追加文本；事件过多时可以用 `output.snapshot` 给出完整安全快照和 `compacted_through`。

`activity.updated` 是可选的通用执行活动快照。`data` 必须符合
`module-task-v1.schema.json` 中的严格 `phase | plan | tool` 结构；同一
`run_id + activity_id` 的后续事件完整替换前一个快照。参数和结果只能发送脱敏、截断后的预览，
不得发送隐藏思维链、Prompt、Token、私有 URL、堆栈或原始异常。Activity SSE 不等于 token
流式输出，因此不改变 `supports_stream`。

即使 Action 声明 `supports_stream: false`，任务仍通过 SSE 报告状态和终态；该标志只表示是否提供输出增量。

### 9. 取消

只有 manifest 声明 `supports_cancel: true` 才实现取消语义。

- 请求体为 `{}`。
- 接受请求后返回当前摘要，通常进入 `cancel_requested`。
- 模块完成清理后进入 `cancelled`。
- 如果副作用已经不可取消，可以返回 409。
- 终态任务的重复取消不得重新执行任务。
- 取消与成功竞争时，模块必须给出一个确定终态并保持幂等。

### 10. 审批

只有声明 `supports_approval: true` 时使用：

```json
{
  "approval_id": "approval-1",
  "prompt": "Allow this operation?",
  "expires_at": "2026-07-23T12:00:00Z"
}
```

模块先持久化审批，再发出 `approval.requested` 并进入 `waiting_approval`。Server 只接受 `approve` 或 `deny`。

- 相同决定的重试是幂等的。
- 冲突决定返回 409。
- 已过期审批返回 410。
- deny 应进入明确的失败或取消终态。
- 未批准前不得执行受保护副作用。

### 11. 产物

只有声明 `supports_artifacts: true` 时返回：

```json
{
  "artifact_id": "report",
  "filename": "report.json",
  "media_type": "application/json",
  "size": 1234,
  "expires_at": "2026-07-23T12:10:00Z"
}
```

限制：

- 单产物最大 16 MiB；
- 文件名不能作为服务器路径使用；
- 过期返回 410；
- 不存在返回 404；
- Server 下载后生成面向用户的短期 `artifact_ref`；
- 响应使用 `Content-Type`、`Content-Length`，避免可执行内容嗅探。

### 12. Host Capability

Host Capability 是 Server 为某个 task 签发的最小、短期、可撤销权限，不是模块长期权限。

当前公共能力：

| Capability | Server 回调 | Scope |
|---|---|---|
| `chat.read` | `GET /api/module-capabilities/v1/chat` | 当前 task 的 chat |
| `resource.read` | `GET /api/module-capabilities/v1/resources/{id}` | 创建任务时选择的 resource IDs |
| `resource.stream` | `GET /api/module-capabilities/v1/resource-stream/{id}` | 当前任务绑定的临时输入原始字节 |
| `model.invoke` | `POST /api/module-capabilities/v1/model/invoke` | 当前 task 的模型调用 |
| `model.chat.completions` | `POST /api/module-capabilities/v1/openai/chat/completions` | 当前 task 的 OpenAI-compatible Chat Completions |
| `skill.read` | `GET /api/module-capabilities/v1/skills/{skill_id}` | 创建任务时冻结的个人 Skill 版本 |
| `rule.read` | `GET /api/module-capabilities/v1/rules/{document_id}` | 创建任务时冻结的已激活 Compiled Rule 版本 |

模块从任务的 `host_capabilities` 中获得：

```json
{
  "capability": "chat.read",
  "endpoint": "https://chatraw.example.com/api/module-capabilities/v1/chat",
  "token": "task-scoped-bearer",
  "scope": {
    "chat_id": "..."
  },
  "expires_at": "RFC3339"
}
```

调用规则：

- 对 Server 回调使用该项的 Bearer Token；
- Token 与 task、用户、模块和 scope 绑定；
- 默认有效期 15 分钟；
- 用户停用、任务终态、模块停用/断开时可被撤销；
- 不能把 Token 转发给浏览器或私有依赖；
- 401/403 必须视为权限失败，不能改用其他身份重试。

`chat.read` 返回可信的 `conversation_ref` 和 `actor_ref`。模块不得接受浏览器自行传入的用户、角色或 Principal 作为替代。

模块必须使用 envelope 自带的完整 `endpoint`，不能根据模块地址猜测 ChatRaw 地址。
`resource.read` 和 `resource.stream` 的 endpoint 包含 `{resource_id}` 占位符，只能替换为 scope
中授权的资源 ID。`resource.stream` 返回原始字节流；模块必须检查 `Content-Type`、
`Content-Length` 和 `X-Content-SHA256`，并将实际字节数和 SHA256 与响应头比对；不一致时
立即失败。

`model.chat.completions` 的 endpoint 是 OpenAI-compatible base URL；模块在其后追加
`/chat/completions`。请求只能使用 scope 中的逻辑模型 profile，不能传 Server 模型地址或密钥。
每个 task 最多 64 次、单请求最大 1 MiB。

`skill.read` 与 `rule.read` 都是不可变任务快照：创建任务后，用户更新或停用原对象不会改写
已签发 task。Skill capability 注入 `SKILL.md` 并返回静态资源清单；它不返回或执行资源内容、
不授予权限；每个 task 最多 5 个。
Rule 只返回经过 Compiler Specification 编译、Pydantic 校验且由用户明确激活的 Compiled Rule，
每个 task 最多 10 个。模块必须再次按自己的 Compiled Rule schema 校验，不能执行任意文本。

需要原始文件的插件先通过 Module SDK 上传临时资源，再把返回的 `resource_id` 放入创建任务请求的
`resource_ids`。临时资源不进入 ChatRaw 文档表、解析器或索引，只能绑定一个任务。Action 必须声明
`supports_resources: true` 才能接收临时输入或返回输出资源。

模块返回的输出资源使用：

```json
{
  "resources": [
    {
      "resource_id": "module-private-id",
      "filename": "report.pdf",
      "media_type": "application/pdf",
      "size": 123456,
      "expires_at": null
    }
  ]
}
```

`expires_at` 可省略；省略或设为 `null` 表示模块未声明过期时间。
`resource_id` 只在 Server 与模块之间使用。Server 面向插件返回不可猜测的 `resource_ref`，并通过
`GET|HEAD /api/module-tasks/{task_id}/resources/{resource_ref}?disposition=inline|attachment`
代理资源。模块的资源端点必须支持 `GET`、`HEAD` 和单段 Range，且各响应的
`Content-Type`、`Content-Length`（以及 206 的 `Content-Range`）必须严格一致。Server 根据已
登记的文件名生成对外 `Content-Disposition`，并在公开的 GET/HEAD 响应中返回这些元数据。不要
返回重定向，也不要用文件名构造本地路径。协议不接受 MIME 猜测、元数据修复或旧路径回退。

当前 Server 硬限制：

| 项目 | 限制 |
|---|---:|
| manifest | 256 KiB |
| config 请求或响应 | 128 KiB |
| task 创建请求 | 256 KiB |
| task 摘要响应 | 512 KiB |
| 单个 SSE event | 128 KiB |
| 单个 artifact | 16 MiB |
| 单个临时任务输入 | 100 MiB（默认，可由管理员配置） |
| task 关联资源 | 64 个 |
| task 列表单页 | 100 条 |
| Host Capability 有效期 | 15 分钟 |
| `model.invoke` | 每个 task 最多 8 次 |
| `model.invoke` prompt | 64 KiB |
| `model.chat.completions` | 每个 task 最多 64 次；单请求 1 MiB |
| `skill.read` | 每个 task 最多 5 个不可变版本 |
| `rule.read` | 每个 task 最多 10 个不可变版本 |
| `resource.read` 内容 | 2 MiB |

允许的 artifact MIME 类型以 Server 的 `SAFE_ARTIFACT_MEDIA_TYPES` 为准；不要把 HTML、脚本或可执行文件伪装成下载产物。

### 13. Source 部署

模块至少支持：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
MODULE_DATA_DIR="$PWD/data" \
MODULE_PAIRING_CODE="fresh-one-time-code" \
.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8765
```

正式环境将 Pairing Code 通过临时环境变量、受保护文件或部署系统 secret 注入。不要把示例 Pairing Code 当默认值。

### 14. Compose 部署

最小拓扑：

```yaml
services:
  my-module:
    build: .
    expose:
      - "8765"
    volumes:
      - my_module_data:/app/data
    networks:
      chatraw_modules:
        aliases:
          - my-module
      private_backend:
    restart: unless-stopped

volumes:
  my_module_data:

networks:
  chatraw_modules:
    external: true
    name: "${CHATRAW_MODULE_NETWORK:-chatraw-modules}"
  private_backend:
    internal: true
```

模块不发布宿主端口。只有模块加入 `chatraw_modules`；私有依赖只加入 `private_backend`。若模块不需要私有依赖，不要创建空的额外网络。

容器必须提供 healthcheck，数据卷必须覆盖所有恢复状态。`docker compose down` 后重新 `up` 应保留配对身份、配置和任务。

### 15. Conformance

离线验证 manifest：

```bash
.venv/bin/python scripts/module-conformance.py manifest \
  /path/to/module_manifest.json
```

验证所有已提交 Schema 和示例：

```bash
.venv/bin/python scripts/module-conformance.py contracts
```

对刚启动、尚未配对的模块验证管理接口：

```bash
.venv/bin/python scripts/module-conformance.py probe \
  --base-url http://127.0.0.1:8765 \
  --pairing-code YOUR_FRESH_CODE
```

`probe` 会消费 Pairing Code，只用于一次性测试实例。

完整任务与 Host Capability 验收：

```bash
.venv/bin/python scripts/module-conformance.py task-probe \
  --base-url http://127.0.0.1:8765 \
  --pairing-code YOUR_FRESH_CODE \
  --fixture /path/to/conformance-fixture.json
```

fixture 必须符合
[`module-conformance-fixture-v1.schema.json`](../backend/contracts/module-conformance-fixture-v1.schema.json)。
`task-probe` 默认在随机回环端口启动受控 Host Capability 回调桩；fixture 对 Capability 的覆盖必须与 manifest 的申请完全一致，并且声明的每一项都必须被模块真正调用。它还验证流式任务、终态、审批、取消和产物。

完整参考实现：

```bash
./scripts/run-t6-source-gate.sh
./scripts/run-t6-compose-gate.sh
```

发布前还需验证：

- Server 重启；
- 模块重启；
- SSE 断线续传；
- 重复创建任务；
- 取消竞争；
- 审批通过、拒绝和过期；
- 产物下载和过期；
- 模块离线；
- 私有依赖离线；
- 配套插件缺失和版本不兼容；
- 普通用户权限；
- 浏览器没有模块 Token；
- 备份与恢复。

### 16. 禁止事项

- 修改 ChatRaw 后端来接入单个模块。
- 让模块进程在运行时注入代码、改写 ChatRaw Core 或向浏览器提供可执行 UI。
- 让插件直连模块。
- 把 Pairing Code、access token 或 Capability Token 写进 manifest、浏览器或日志。
- 让 Server 加入模块私有网络。
- 让模块信任浏览器提供的用户或角色。
- 只在内存中保存 task/event。
- 用随机文本替代稳定错误码。
- 未声明能力却发送 stream、approval 或 artifact。
- 把模拟、fixture 或合成负载描述成客户验收。
- 在公共指南中记录模块私有协议。

---

## English

### Scope

A module is an independent backend for durable jobs, databases, privileged operations, private dependencies, or complex runtime requirements. It is not a frontend plugin or a general orchestration platform. Modules never supply executable UI. The frontend entry is either an administrator-managed companion plugin or a source-reviewed Resident Integration shipped in the Server build.

Module Protocol v1 covers only the ChatRaw-to-module northbound interface. Internal databases and proprietary protocols remain private and must not appear in public manifests, contracts, examples, or conformance output.

### Authoritative contracts

Use the committed manifest, management, task, and Resident JSON Schemas; the Module SDK contracts; both reference manifests and the implementation; and the conformance commands listed above. Documentation cannot add behavior absent from those sources. See the [Resident Module Integration Guide](resident-module-integration-guide.md) for persistent Server-owned frontend entries.

### Required behavior

- Stable module ID and installation instance ID.
- One-time, expiring pairing code.
- Hashed persistent access credential.
- Authenticated manifest, health, ready, config, disconnect, and optional purge endpoints.
- Closed JSON Schemas and SemVer compatibility.
- Durable task identity, idempotent creation, persisted ordered SSE, replay with `Last-Event-ID`, and restart recovery.
- Optional cancellation, approval, artifacts, and chat projection exactly as declared.
- Task-scoped, expiring Host Capability tokens; never trust browser-supplied identity.
- Temporary task inputs through `resource.stream`, and module-owned output resources through the
  authenticated task resource proxy, only for actions that declare `supports_resources`.
- Source and Compose deployment, persistent data, health checks, and no default host port.

### Endpoints

Management uses `/chatraw-module/v1`; tasks use `/chatraw-module/v1/tasks`. All endpoints except `/pair` require the paired Bearer credential. The exact payloads are defined in the JSON Schemas and demonstrated by the reference module.

### Conformance

```bash
.venv/bin/python scripts/module-conformance.py manifest /path/to/manifest.json
.venv/bin/python scripts/module-conformance.py contracts
.venv/bin/python scripts/module-conformance.py probe \
  --base-url http://127.0.0.1:8765 \
  --pairing-code A_FRESH_ONE_TIME_CODE
.venv/bin/python scripts/module-conformance.py task-probe \
  --base-url http://127.0.0.1:8765 \
  --pairing-code A_FRESH_ONE_TIME_CODE \
  --fixture /path/to/conformance-fixture.json
./scripts/run-t6-source-gate.sh
./scripts/run-t6-compose-gate.sh
```

The live probe consumes its pairing code. Full release evidence also includes restart, replay, idempotency, failure, permissions, browser secret-negative checks, and backup recovery. Fixtures remain engineering evidence, not customer or production acceptance.
