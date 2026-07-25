# ChatRaw Server 管理员指南 / Administrator Guide

## 中文

### 1. 管理员负责什么

管理员控制一个共享 ChatRaw Server 实例：

- 创建、启用、停用用户并重置密码；
- 配置模型、插件与模块；
- 审批模块权限和版本变化；
- 查看安全审计记录；
- 组织 Server 与各模块的备份、恢复和升级；
- 判断本地工程验证与客户现场验收的边界。

管理员不是模块内部数据库的自动管理员。模块拥有自己的数据、依赖和恢复流程。

### 2. 首次安装

#### Source

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/python scripts/prepare-server-secrets.py --data-dir data
DATA_DIR="$PWD/data" CHATRAW_LOOPBACK_DEV=1 \
  .venv/bin/python backend/main.py
```

#### Docker Compose

```bash
./scripts/create-module-network.sh
docker compose up -d --build
docker compose exec chatraw \
  python -c "from pathlib import Path; print(Path('/app/data/secrets/setup-token').read_text().strip())"
```

访问 `/setup` 并创建首位管理员。Setup Token 只用于首次创建管理员；不要把它提交到 Git、聊天或工单。

生产环境要求：

- HTTPS 终止于可信反向代理；
- 反向代理保留正确的 Host 和 Origin；
- Server 数据目录或卷只对运行账户可写；
- 不设置 `CHATRAW_LOOPBACK_DEV=1`；
- 只发布 Server 端口，不发布模块或模块私有依赖端口。

`GET /health` 表示进程存活；`GET /ready` 还会验证数据库和 Schema。负载均衡应使用 `/ready`。

### 3. 用户与权限

在“设置 → Users”中创建 `admin` 或 `member`：

- `admin` 可以管理用户、模型、插件和模块。
- `member` 可以使用共享数据和已启用功能，但不能管理插件或模块。

停用用户会使其会话和未过期的任务型 Host Capability 失效。重置密码后要求用户重新登录。

至少保留一个可用管理员。操作前确认目标用户名，避免停用自己的唯一管理入口。

### 4. 插件管理

插件是管理员安装的可信前端代码。它与 ChatRaw 页面运行在同一 JavaScript 上下文中，不是浏览器安全沙箱。

安装前检查：

- 来源和版本；
- `manifest.json` 的 hook、proxy、settings 和依赖；
- `main.js` 是否访问不需要的数据或外部地址；
- 是否确实需要其声明的能力；
- 是否是某个模块要求的配套插件版本。

普通用户能使用已启用插件，但不能安装、停用或删除。禁用或删除插件会移除前端入口，不会自动删除模块数据。

### 5. 连接和启用模块

1. 生成至少 16 个字符的一次性 Pairing Code，通过部署系统的环境变量或 Secret 注入模块后启动。模块不能把它输出到日志。
2. 在“设置 → Modules”输入模块在模块网桥中的地址和 Pairing Code。
3. ChatRaw 获取 manifest，但不会立即启用模块。
4. 审查：
   - `module_id`、版本和协议版本；
   - Action、最低角色和输入/输出 Schema；
   - 流式、取消、审批、产物和聊天投影能力；
   - 请求的 Host Capability；
   - 前端集成模式、ID 与版本范围；
   - 是否支持数据清理。
5. 批准 manifest。
6. 配置非秘密字段和秘密字段。已有秘密只显示“已配置”，不会回显。
7. Plugin 模式：安装并启用匹配版本的配套插件。Resident 模式：确认当前 Server 构建包含匹配的 Resident；WebUI 不会动态安装 Resident 源码。
8. 执行 Check，确认 Health、Ready、Config 和 Frontend Integration 都通过。
9. 启用模块。

任何影响权限边界的 manifest 变化都会进入 `review required`，原 Capability Grant 被撤销；管理员必须重新检查和批准。权限边界包括模块主版本、Action 契约和能力、Host Capability、前端集成模式/ID/版本约束、数据清理能力，以及完整的 `config_schema`。因此新增秘密配置字段也一定会重新触发审核。

### 6. 模块生命周期

| 操作 | 作用 | 数据 |
|---|---|---|
| Check/Refresh | 重新读取状态或 manifest | 保留 |
| Enable | 允许用户创建任务 | 保留 |
| Drain | 拒绝新任务，等待现有任务结束 | 保留 |
| Disable | 拒绝新任务 | 保留 |
| Disconnect | 删除 ChatRaw 中的连接凭证 | 模块数据保留 |
| Purge data | 请求模块删除自己的持久数据 | 删除，且不可撤销 |

不要把 Disconnect 当作卸载或删除。需要下线模块时：

1. Drain；
2. 等待活动任务结束；
3. Disable；
4. 备份模块数据；
5. Disconnect；
6. 停止模块服务。

只有明确要求永久清除时才执行 Purge data。

### 7. 网络边界

推荐 Compose 拓扑：

```text
浏览器 ──HTTPS──> ChatRaw Server
                    │
          chatraw-modules 外部网桥
                    │
                  Module
                    │
             模块私有 internal 网桥
                    │
              私有数据库/依赖
```

- Server 与模块加入 `chatraw-modules`。
- 模块私有依赖只加入模块自己的 internal 网络。
- 私有依赖不加入 `chatraw-modules`。
- 模块和私有依赖默认不发布宿主机端口。
- 浏览器只能访问 Server。

创建公共模块网桥：

```bash
./scripts/create-module-network.sh
```

### 7.1 模块任务临时资源

Module SDK 的临时输入资源与普通文档上传完全独立：它没有核心页面入口，不进入文档表、解析器或
索引。任何已登录用户都可以通过同源 Module SDK 上传临时资源；是否展示上传操作由插件决定，
不是 Server 对插件启用状态的额外授权。默认单文件上限为 100 MiB，可通过
`CHATRAW_MODULE_TASK_RESOURCE_MAX_BYTES` 调整；未设置时使用默认值，显式设置为非法值会使
Server 启动失败，不会静默回退。

未绑定任务的临时文件在 24 小时后清理。文件绑定任务后不能再次绑定；任务进入终态后保留 24 小时，
随后清理 Server 的临时输入文件及其记录。模块自己的输出文件仍由模块负责保存、过期和备份，Server
只保存授权所需的引用。

管理员应把 Server 数据目录视为敏感数据，不要公开临时资源目录。反向代理必须允许 `GET`、`HEAD`
和单段 Range，并保留 `Content-Length`、`Content-Range`、`Content-Type` 和
`Content-Disposition`；不要缓存带登录态的任务资源响应。

单文件上限不是按用户或全站累计配额。未绑定资源在清理期限内仍占用磁盘，因此管理员还应在反向代理
设置与 Server 一致或更小的请求体上限，并监控临时资源目录和数据卷剩余空间。不要通过增大单文件
上限代替容量规划。

### 8. 经典数据导入

先停止经典 ChatRaw。导入工具：

- 只读取经典目录；
- 要求 Server 目标目录不存在；
- 使用 SQLite 一致性快照；
- 在副本上执行迁移；
- 比较经典表的行数与内容摘要；
- 验证经典数据保持无归属；
- 再次确认经典源文件没有变化。

```bash
.venv/bin/python -m backend.server_data import-classic \
  --source-data-dir /srv/chatraw-classic \
  --server-data-dir /srv/chatraw-server \
  --confirm-source-quiesced
```

保留目标目录中的 `import-manifest.json`。导入不等于备份；上线前再创建一份 Server 备份。

### 9. Source 备份与恢复

停止 Server 和会写入 Server 数据的维护任务：

```bash
.venv/bin/python -m backend.server_data backup \
  --data-dir /srv/chatraw-server \
  --backup-dir /srv/backups/chatraw-2026-07-23 \
  --confirm-source-quiesced

.venv/bin/python -m backend.server_data verify \
  --backup-dir /srv/backups/chatraw-2026-07-23
```

恢复到新目录：

```bash
.venv/bin/python -m backend.server_data restore \
  --backup-dir /srv/backups/chatraw-2026-07-23 \
  --data-dir /srv/chatraw-restored \
  --confirm-destination-quiesced
```

先用恢复目录启动一个隔离实例，验证管理员登录、普通用户登录、聊天、文档、插件和模块注册记录，再切换正式服务。

### 10. Compose 备份与恢复

备份当前项目卷：

```bash
mkdir -p backups
docker compose stop chatraw
docker compose run --rm --no-deps \
  -v "$PWD/backups:/backup" \
  chatraw python /app/server_data.py backup \
  --data-dir /app/data \
  --backup-dir /backup/chatraw-2026-07-23 \
  --confirm-source-quiesced
docker compose run --rm --no-deps \
  -v "$PWD/backups:/backup:ro" \
  chatraw python /app/server_data.py verify \
  --backup-dir /backup/chatraw-2026-07-23
```

恢复时使用新的 Compose project，从而创建新卷：

```bash
COMPOSE_PROJECT_NAME=chatraw-restored docker compose run --rm --no-deps \
  -v "$PWD/backups:/backup:ro" \
  chatraw python /app/server_data.py restore \
  --backup-dir /backup/chatraw-2026-07-23 \
  --data-dir /app/data \
  --confirm-destination-quiesced \
  --allow-empty-destination

COMPOSE_PROJECT_NAME=chatraw-restored docker compose up -d
```

`--allow-empty-destination` 只允许现有的**空目录或新卷**，仍拒绝覆盖任何文件。

每个模块必须单独备份。Server 备份只包含 Server 数据和模块注册信息，不包含 Agent、LinkDB 或其他模块的数据卷。

### 11. 升级与回滚

升级前：

1. 阅读目标版本的协议、Schema 和迁移变化。
2. Drain 高价值模块。
3. 停止写入。
4. 分别备份 Server 和每个模块。
5. 验证所有备份。
6. 记录当前镜像或 Git commit。

升级后检查：

- `/ready`；
- 管理员和普通用户登录；
- 经典导入数据；
- 模型验证；
- 插件加载；
- 模块 Health/Ready/Config/Plugin；
- 版本变化是否触发重新审批；
- Agent 全链路。

跨数据库迁移回滚时，代码和数据必须回到同一备份时间点。不要让旧代码打开已经升级到更高 Schema 的数据库。

### 12. 故障处理

#### Server 无法 Ready

检查日志、数据目录权限和数据库 Schema。不要删除数据库锁文件或手工修改 Schema；先停止服务并从已验证备份恢复。

#### 模块 Unreachable

检查模块进程、`chatraw-modules` 网络、服务别名和模块地址。不要把模块端口临时暴露到公网作为修复。

#### 模块 Not Ready

查看模块自己的依赖状态和缺失配置。Health 正常只表示模块进程存活。

#### Review required

比较新旧 manifest、权限摘要和前端集成版本。确认变化后重新批准，不要绕过审批状态。

#### 用户无法登录

确认用户未被停用、密码是否已重置、浏览器是否访问正确 HTTPS 域名。检查服务器时间和反向代理 Origin/Host。

### 13. 审计与验收

管理员应保留：

- 安装和升级版本；
- 备份 manifest 与 verify 输出；
- 模块审批和权限变化；
- Source/Compose conformance 输出；
- 现场验收人、环境和时间。

本地 fixture、模拟 API 和合成负载只能证明工程契约。客户数据、客户 Token、真实硬件/网络、生产 TLS/防火墙、真实上游行为与性能必须标记 `PENDING_ONSITE`，直到现场证据完成。

---

## English

### Administrator responsibilities

Administrators manage users, models, trusted frontend plugins, backend module connections, permission reviews, audit events, upgrades, and recovery for one shared Server instance. Module-owned databases and private dependencies remain the responsibility of each module.

### Installation

Use the Source or Compose commands in the [README](../README.md). Protect the one-time Setup Token. Production requires HTTPS, a trusted reverse proxy, a protected data volume, and no loopback development mode.

`/health` proves process liveness. `/ready` also checks the database and supported Schema and is the correct load-balancer target.

### Users

Admins manage the platform. Members use shared data and enabled features but cannot manage plugins or modules. Disabling a user revokes sessions and outstanding task capability grants. Keep at least one working administrator.

### Plugins are trusted code

Plugins execute in the ChatRaw page JavaScript context. Review their source, manifest hooks, proxy declarations, dependencies, and companion-module compatibility before installation. Disabling a plugin removes its frontend entry point; it does not delete module data.

### Module onboarding

Pair with a fresh one-time code, review the manifest, approve permissions, and configure values and secrets. For plugin mode, install the compatible companion plugin. For Resident mode, deploy a Server build containing the compatible source package; the WebUI does not install Resident code dynamically. Check Health/Ready/Config/Frontend Integration, and then enable the module.

Permission-relevant manifest changes revoke grants and require a new review.

| Operation | Effect | Module data |
|---|---|---|
| Check/Refresh | Refresh status or manifest | Preserved |
| Enable | Allow new tasks | Preserved |
| Drain | Reject new tasks while current work finishes | Preserved |
| Disable | Reject new tasks | Preserved |
| Disconnect | Remove the Server credential | Preserved |
| Purge data | Ask the module to erase persistent data | Destroyed |

Drain, disable, back up, disconnect, and stop in that order. Purge only for an explicit permanent-erasure request.

### Network boundary

Only Server is browser-facing. Server and modules share the external `chatraw-modules` bridge. A module's databases and private dependencies belong on a separate internal network. Do not publish module or private-dependency ports by default.

Module task inputs use a dedicated temporary store and do not enter the normal document upload,
parser, or index. Any signed-in user can call the same-origin SDK upload; a plugin decides whether
to expose that operation, but its enabled state is not an additional Server authorization check.
The default limit is 100 MiB per file and can be changed with
`CHATRAW_MODULE_TASK_RESOURCE_MAX_BYTES`; an explicitly invalid value prevents startup instead of
falling back. Unbound inputs expire after 24 hours, and task-bound inputs become eligible for
cleanup 24 hours after the task reaches a terminal state. Preserve `GET`, `HEAD`, single-range, and
content metadata headers at the reverse proxy, and do not cache authenticated task resource
responses. The per-file limit is not a per-user or aggregate quota: set an equal or smaller request
body limit at the reverse proxy and monitor temporary storage and free disk space. Module-owned
output files require their own backup and retention policy.

### Classic import

Stop the classic service and import into a new destination:

```bash
.venv/bin/python -m backend.server_data import-classic \
  --source-data-dir /srv/chatraw-classic \
  --server-data-dir /srv/chatraw-server \
  --confirm-source-quiesced
```

The tool snapshots SQLite, migrates the copy, compares classic content, preserves ownerless legacy semantics, and verifies the source remained unchanged.

### Backup and restore

Stop writes, create a backup, and verify it before relying on it:

```bash
.venv/bin/python -m backend.server_data backup \
  --data-dir /srv/chatraw-server \
  --backup-dir /srv/backups/chatraw-2026-07-23 \
  --confirm-source-quiesced

.venv/bin/python -m backend.server_data verify \
  --backup-dir /srv/backups/chatraw-2026-07-23
```

Restore into a new path:

```bash
.venv/bin/python -m backend.server_data restore \
  --backup-dir /srv/backups/chatraw-2026-07-23 \
  --data-dir /srv/chatraw-restored \
  --confirm-destination-quiesced
```

For Compose, use the exact commands in the Chinese section above: stop the service, run the production image against the current volume to create and verify a backup, then restore into a new Compose project and its empty volume. `--allow-empty-destination` never permits overwriting files.

Server backups do not contain module-owned volumes. Back up and restore every module independently.

### Upgrade and incident rules

Before an upgrade, drain modules, stop writes, verify Server and module backups, and record the current image or commit. Afterward, verify both roles, imported data, models, plugins, module review state, and the Agent chain.

Never open a newer database with older code. Never expose a private module port as a quick incident workaround.

### Evidence boundary

Retain backup manifests, verification output, permission reviews, conformance output, and environment-specific acceptance records. Fixtures and synthetic loads are engineering evidence only. Customer data, credentials, hardware, networks, production TLS/firewall, upstream behavior, and performance remain `PENDING_ONSITE` until verified on site.
