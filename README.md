# ChatRaw Server

ChatRaw Server 是 ChatRaw 的多人共享版本：用户必须登录后才能使用任何业务功能；管理员统一管理用户、模型、插件和后端模块；普通用户可以使用已启用且角色允许的功能，但不能安装、停用或删除插件与模块。

[English](#english) · [用户指南](docs/user-guide.md) · [管理员指南](docs/admin-guide.md) · [AI 文档导航](AGENTS.md) · [模块开发](docs/module-developer-guide.md) · [Resident 集成](docs/resident-module-integration-guide.md)

## 它解决什么问题

ChatRaw Server 只做两件核心事情：

1. **多人共享与权限管理**：所有用户共享同一个 ChatRaw 平台和业务数据，不做租户式数据隔离；管理员与普通用户拥有不同的管理权限。
2. **大型功能模块化**：需要独立后端、高权限或复杂依赖的功能作为单独模块运行，不把业务代码塞进 ChatRaw 后端。前端入口选择可由管理员动态管理的插件，或随 Server 源码构建的 Resident Integration。

插件与模块不是同一种东西：

- **插件**运行在 ChatRaw 前端，用来增加按钮、拦截发送或展示结果。
- **Resident Integration**也是前端代码，但位于独立源码目录，随 Server 审查、构建和部署，用于常驻入口；它不能由模块动态注入。
- **模块**是独立后端服务，负责长任务、私有依赖、数据库或高权限能力。
- **ChatRaw Server**负责登录、授权、模块生命周期、任务转发和安全边界。
- 模块功能可以通过配套插件或 Resident Integration 扩展 ChatRaw 前端；独立运行的模块进程不能在运行时改写 ChatRaw Core，也不能向浏览器下发可执行界面代码。

```text
用户
  → ChatRaw 前端
  → 配套插件或 Resident Integration
  → ChatRaw 通用模块网关
  → 独立模块
  → 模块自己的私有依赖
```

Agent 是第一个按通用协议完成工程验收的模块适配，但模块协议并不包含 Agent 专用逻辑：

```text
用户 → Agent 配套插件 → ChatRaw Module Protocol v1
     → Agent → Agent–LinkDB 私有协议 → LinkDB
```

只有 ChatRaw 到 Agent 的北向接口是通用模块协议。Agent–LinkDB 协议继续保持私有，不属于公共模块开发接口。

## 权限模型

| 操作 | 管理员 | 普通用户 |
|---|---:|---:|
| 登录并使用聊天、文档和已启用功能 | ✓ | ✓ |
| 使用角色允许的已启用插件与模块功能 | ✓ | ✓ |
| 管理用户和审计记录 | ✓ | — |
| 配置模型、插件和模块 | ✓ | — |
| 安装、启停或删除插件 | ✓ | — |
| 连接、审批、启停、断开或清理模块 | ✓ | — |

ChatRaw Server 是共享平台，不是应用编排或租户隔离平台。聊天和文档对平台用户可见；创建者和管理员可以执行相应管理操作，经典版导入的无归属数据只能由管理员管理。

## 快速开始

### Docker Compose

要求：Docker Engine 和 Docker Compose v2。

当前尚未发布 GitHub Release，Docker Hub 仓库也没有可拉取的镜像标签。现在请使用仓库源码构建：

```bash
./scripts/create-module-network.sh
docker compose up -d --build
docker compose exec chatraw \
  python -c "from pathlib import Path; print(Path('/app/data/secrets/setup-token').read_text().strip())"
```

打开 `http://127.0.0.1:51111/setup`，输入一次性 Setup Token，创建首位管理员。

正式 GitHub Release 发布后，自动化流程会构建并验证 `linux/amd64` 与 `linux/arm64`，再发布 `massif01/chatraw-server:<version>`；只有 Docker Hub manifest 验证成功的标签才应写入部署配置。

Compose 默认：

- 只向宿主机发布 ChatRaw 的 `51111` 端口。
- 将 Server 数据保存在命名卷中。
- 将 Server 接入外部 `chatraw-modules` 网桥。
- 模块可以加入网桥，但模块的私有依赖不应加入该网桥。

生产环境必须在可信反向代理后使用 HTTPS。不要在公网环境开启 `CHATRAW_LOOPBACK_DEV=1`。

### 源码运行

要求：Python 3.11 或更高版本。

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/python scripts/prepare-server-secrets.py --data-dir data
DATA_DIR="$PWD/data" CHATRAW_LOOPBACK_DEV=1 \
  .venv/bin/python backend/main.py
```

使用 `prepare-server-secrets.py` 显示的一次性 Setup Token，打开 `http://127.0.0.1:51111/setup` 创建首位管理员。`CHATRAW_LOOPBACK_DEV=1` 只用于本机 HTTP 开发；正式部署必须使用 HTTPS。

## 管理流程

首次管理员登录后：

1. 在设置中创建普通用户或其他管理员。
2. 配置并验证模型。
3. 安装需要的插件。
4. 为独立模块设置一次性 Pairing Code，并通过部署系统的环境变量或 Secret 注入后启动模块。Pairing Code 不会输出到日志。
5. 在“设置 → Modules”中输入模块地址和 Pairing Code。
6. 检查模块请求的 Host Capability、Action、前端集成模式/版本和数据清理能力。
7. 批准、配置、检查并启用模块。

断开模块默认保留模块自己的数据。清理模块数据是独立的高风险操作，仅在模块声明支持时出现。

## 数据迁移、备份与恢复

经典 ChatRaw 数据必须在旧服务停止后导入到一个**不存在的新目录**：

```bash
.venv/bin/python -m backend.server_data import-classic \
  --source-data-dir /path/to/classic-data \
  --server-data-dir /path/to/new-server-data \
  --confirm-source-quiesced
```

Server 备份必须在服务停止后执行：

```bash
.venv/bin/python -m backend.server_data backup \
  --data-dir /path/to/server-data \
  --backup-dir /path/to/new-backup \
  --confirm-source-quiesced

.venv/bin/python -m backend.server_data verify \
  --backup-dir /path/to/new-backup
```

恢复默认拒绝覆盖任何已有目录：

```bash
.venv/bin/python -m backend.server_data restore \
  --backup-dir /path/to/backup \
  --data-dir /path/to/new-restored-data \
  --confirm-destination-quiesced
```

ChatRaw 备份不包含模块自己的数据库。每个模块必须独立备份，并在恢复后重新检查连接状态。完整操作见[管理员指南](docs/admin-guide.md)。

## 开发者入口

- [AI 文档导航](AGENTS.md)：告诉 AI 在不同任务中必须阅读和同步哪些文档。
- [Plugin Developer Guide](docs/plugin-developer-guide.md)：前端可信代码边界、插件生命周期和 Module SDK。
- [Module Developer Guide](docs/module-developer-guide.md)：manifest、任务、SSE、审批、产物、Host Capability 和部署模板。
- [Resident Module Integration Guide](docs/resident-module-integration-guide.md)：源码级常驻入口、稳定挂载位、Host SDK、AI 修改边界和验收。
- [Human + AI Development Guide](docs/human-ai-development-guide.md)：面向人和 AI 的最小目录、Schema、命令、验收清单和禁止事项。
- [Server 与模块部署](docs/deployment/server-and-modules.md)：Source/Compose 网络与持久化。
- [发布流程](docs/release/release-process.md)与 [T8 验收状态](docs/release/acceptance-status.md)
- [OpenAPI](docs/api/openapi.json)：Server HTTP API 的机器可读快照。
- [Module Manifest Schema](backend/contracts/module-manifest-v1.schema.json)
- [Module Management Schema](backend/contracts/module-management-v1.schema.json)
- [Module Task Schema](backend/contracts/module-task-v1.schema.json)
- [Module Plugin SDK Contract](backend/contracts/module-plugin-sdk-v1.json)
- [Resident Integration Schema](backend/contracts/resident-integration-v1.schema.json) 与 [Host SDK Contract](backend/contracts/resident-integration-sdk-v1.json)
- [Reference Module](examples/reference-module/)

常用开发验证：

```bash
.venv/bin/python scripts/export-openapi.py --check
.venv/bin/python scripts/module-conformance.py contracts
```

以下在线 probe 需要先在 `127.0.0.1:8765` 启动待验收模块，并注入匹配的一次性 Pairing Code：

```bash
.venv/bin/python scripts/module-conformance.py task-probe \
  --base-url http://127.0.0.1:8765 \
  --pairing-code A_FRESH_ONE_TIME_CODE \
  --fixture examples/reference-module/conformance-fixture.json
```

端到端 Source 门禁会自行启动并清理参考 Server 与模块：

```bash
./scripts/run-t6-source-gate.sh
```

## 兼容与发布边界

- 经典 `v2.2.1` 数据通过只读源导入进入 Server，不在原目录上迁移。
- 旧插件接口继续兼容；模块配套插件应只通过 `window.ChatRaw.modules` 访问模块功能。
- Module Protocol v1 只承诺协议主版本 1 内的兼容规则。
- Source、Compose、参考模块和 Agent 链路已有工程验收记录；具体证据等级见 [T8 验收状态](docs/release/acceptance-status.md)。
- 客户数据、客户 Token、客户硬件与网络、生产 DNS/TLS/防火墙、真实上游 API 和生产性能仍为 `PENDING_ONSITE`，合成测试不代表客户或生产验收。

## License

MIT

---

# English

ChatRaw Server is the shared multi-user edition of ChatRaw. Every user must sign in before accessing product data or functions. Administrators manage users, models, plugins, and backend modules. Members can use enabled features allowed by their role but cannot install, disable, or remove plugins or modules.

[User Guide](docs/user-guide.md) · [Administrator Guide](docs/admin-guide.md) · [AI Documentation Map](AGENTS.md) · [Module Development](docs/module-developer-guide.md) · [Resident Integration](docs/resident-module-integration-guide.md)

## Product model

ChatRaw Server has two primary responsibilities:

1. **Shared multi-user access with roles.** Users share one platform and its business data; this is not tenant-level data isolation.
2. **Large features as independent modules.** A feature that needs a backend, privileged access, a database, or complex dependencies runs outside the ChatRaw backend. Its frontend entry is either an administrator-managed plugin or a source-built Resident Integration.

- A **plugin** is trusted frontend code that adds an entry point or presentation.
- A **Resident Integration** is trusted frontend source shipped in the Server build for a persistent entry point. It is never injected by a module.
- A **module** is an independent backend service.
- **ChatRaw Server** owns authentication, authorization, lifecycle management, task forwarding, and the security boundary.
- A module-backed feature may extend the ChatRaw UI through a companion plugin or source-built Resident Integration. The independent module process cannot rewrite ChatRaw Core at runtime or deliver executable UI code to the browser.

```text
User → ChatRaw UI → companion plugin or Resident Integration → generic module gateway
     → independent module → module-private dependencies
```

Agent is the first module adapter to complete engineering acceptance through the generic protocol. Only the ChatRaw-to-Agent northbound interface is standardized. The private Agent–LinkDB protocol is unchanged and is not part of the public Module Protocol.

## Roles

| Operation | Admin | Member |
|---|---:|---:|
| Sign in and use shared product data | ✓ | ✓ |
| Use enabled plugin and module features allowed by the role | ✓ | ✓ |
| Manage users and audit events | ✓ | — |
| Configure models, plugins, and modules | ✓ | — |
| Install, disable, or remove plugins | ✓ | — |
| Pair, approve, enable, disconnect, or purge modules | ✓ | — |

Classic imported resources have no creator. Members can use them, while only administrators can manage them.

## Quick start

### Docker Compose

Requires Docker Engine and Docker Compose v2.

No GitHub Release or pullable Docker Hub tag has been published yet. Build from this repository:

```bash
./scripts/create-module-network.sh
docker compose up -d --build
docker compose exec chatraw \
  python -c "from pathlib import Path; print(Path('/app/data/secrets/setup-token').read_text().strip())"
```

Open `http://127.0.0.1:51111/setup` and use the one-time Setup Token to create the first administrator.

After a formal GitHub Release, automation builds and verifies `linux/amd64` and `linux/arm64` before publishing `massif01/chatraw-server:<version>`. Only tags with a verified Docker Hub manifest should be used for deployment.

The default Compose project exposes only the Server port, persists Server data in a named volume, and joins the external `chatraw-modules` bridge. Production deployments must use HTTPS behind a trusted reverse proxy. Never enable `CHATRAW_LOOPBACK_DEV=1` on a public deployment.

### Source

Requires Python 3.11 or later.

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/python scripts/prepare-server-secrets.py --data-dir data
DATA_DIR="$PWD/data" CHATRAW_LOOPBACK_DEV=1 \
  .venv/bin/python backend/main.py
```

Open `http://127.0.0.1:51111/setup` with the one-time Setup Token printed by `prepare-server-secrets.py`. The loopback development flag is only for local HTTP use.

## Module onboarding

An administrator injects a fresh one-time Pairing Code through the deployment environment, starts the module, and pairs it under **Settings → Modules**. The code is never printed to logs. Before enabling the module, review:

- requested Host Capabilities;
- actions and minimum roles;
- frontend integration mode, ID, and version range;
- health, readiness, and configuration state;
- whether destructive data purge is supported.

Disconnect preserves module-owned data. Data purge is a separate, explicit operation.

## Migration, backup, and recovery

Import classic data only while the classic service is stopped, and always target a new directory:

```bash
.venv/bin/python -m backend.server_data import-classic \
  --source-data-dir /path/to/classic-data \
  --server-data-dir /path/to/new-server-data \
  --confirm-source-quiesced
```

Back up and verify Server data while the service is stopped:

```bash
.venv/bin/python -m backend.server_data backup \
  --data-dir /path/to/server-data \
  --backup-dir /path/to/new-backup \
  --confirm-source-quiesced

.venv/bin/python -m backend.server_data verify \
  --backup-dir /path/to/new-backup
```

Restore into a new destination:

```bash
.venv/bin/python -m backend.server_data restore \
  --backup-dir /path/to/backup \
  --data-dir /path/to/new-restored-data \
  --confirm-destination-quiesced
```

Server backups do not contain module-owned databases. Back up each module separately and re-check it after recovery.

## Documentation and contracts

- [AI Documentation Map](AGENTS.md)
- [User Guide](docs/user-guide.md)
- [Administrator Guide](docs/admin-guide.md)
- [Plugin Developer Guide](docs/plugin-developer-guide.md)
- [Module Developer Guide](docs/module-developer-guide.md)
- [Resident Module Integration Guide](docs/resident-module-integration-guide.md)
- [Human + AI Development Guide](docs/human-ai-development-guide.md)
- [Deployment and module operations](docs/deployment/server-and-modules.md)
- [Release process](docs/release/release-process.md) and [acceptance status](docs/release/acceptance-status.md)
- [OpenAPI snapshot](docs/api/openapi.json)
- [Module JSON Schemas](backend/contracts/)
- [Reference module](examples/reference-module/)

```bash
.venv/bin/python scripts/export-openapi.py --check
.venv/bin/python scripts/module-conformance.py contracts
```

The online probe below requires a module running on `127.0.0.1:8765` with the matching one-time Pairing Code:

```bash
.venv/bin/python scripts/module-conformance.py task-probe \
  --base-url http://127.0.0.1:8765 \
  --pairing-code A_FRESH_ONE_TIME_CODE \
  --fixture examples/reference-module/conformance-fixture.json
```

The end-to-end Source gate starts and cleans up its own reference Server and module:

```bash
./scripts/run-t6-source-gate.sh
```

## Acceptance boundary

Source, Compose, the reference module, and the Agent chain have recorded engineering evidence; see the [acceptance status](docs/release/acceptance-status.md) for its exact level. Customer data, credentials, hardware, networks, production DNS/TLS/firewall, real upstream behavior, and production performance remain `PENDING_ONSITE`. Synthetic evidence must not be presented as customer or production acceptance.

## License

MIT
