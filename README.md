# ChatRaw Server

ChatRaw Server 是 ChatRaw 的多人共享版本：用户必须登录后才能使用任何业务功能；管理员统一管理用户、模型、插件和后端模块；普通用户可以使用已启用的功能，但不能安装、停用或删除插件与模块。

[English](#english) · [用户指南](docs/user-guide.md) · [管理员指南](docs/admin-guide.md) · [模块开发](docs/module-developer-guide.md)

## 它解决什么问题

ChatRaw Server 只做两件核心事情：

1. **多人共享与权限管理**：所有用户共享同一个 ChatRaw 平台和业务数据，不做租户式数据隔离；管理员与普通用户拥有不同的管理权限。
2. **大型功能模块化**：需要独立后端、高权限或复杂依赖的功能作为单独模块运行，不把业务代码塞进 ChatRaw 后端。模块的前端入口仍由 ChatRaw 插件提供。

插件与模块不是同一种东西：

- **插件**运行在 ChatRaw 前端，用来增加按钮、拦截发送或展示结果。
- **模块**是独立后端服务，负责长任务、私有依赖、数据库或高权限能力。
- **ChatRaw Server**负责登录、授权、模块生命周期、任务转发和安全边界。
- 模块不能直接修改 ChatRaw 前端，也不能向浏览器下发可执行界面代码。

```text
用户
  → ChatRaw 前端
  → 配套插件
  → ChatRaw 通用模块网关
  → 独立模块
  → 模块自己的私有依赖
```

Agent 是第一个正式模块，但模块协议并不包含 Agent 专用逻辑：

```text
用户 → Agent 配套插件 → ChatRaw Module Protocol v1
     → Agent → Agent–LinkDB 私有协议 → LinkDB
```

只有 ChatRaw 到 Agent 的北向接口是通用模块协议。Agent–LinkDB 协议继续保持私有，不属于公共模块开发接口。

## 权限模型

| 操作 | 管理员 | 普通用户 |
|---|---:|---:|
| 登录并使用聊天、文档和已启用功能 | ✓ | ✓ |
| 使用已启用插件与模块 | ✓ | ✓ |
| 管理用户和审计记录 | ✓ | — |
| 配置模型、插件和模块 | ✓ | — |
| 安装、启停或删除插件 | ✓ | — |
| 连接、审批、启停、断开或清理模块 | ✓ | — |

ChatRaw Server 是共享平台，不是应用编排或租户隔离平台。聊天和文档对平台用户可见；创建者和管理员可以执行相应管理操作，经典版导入的无归属数据只能由管理员管理。

## 快速开始

### Docker Compose

要求：Docker Engine 和 Docker Compose v2。

正式发布镜像同时支持 x86-64 与 ARM64：

```bash
docker pull massif01/chatraw-server:0.0.1
```

需要使用仓库内 Compose 配置和本地源码构建时：

```bash
./scripts/create-module-network.sh
docker compose up -d --build
docker compose exec chatraw \
  python -c "from pathlib import Path; print(Path('/app/data/secrets/setup-token').read_text().strip())"
```

打开 `http://127.0.0.1:51111/setup`，输入一次性 Setup Token，创建首位管理员。

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

打开终端输出中提示的 `/setup` 地址。`CHATRAW_LOOPBACK_DEV=1` 只用于本机 HTTP 开发；正式部署必须使用 HTTPS。

## 管理流程

首次管理员登录后：

1. 在设置中创建普通用户或其他管理员。
2. 配置并验证模型。
3. 安装需要的插件。
4. 为独立模块设置一次性 Pairing Code，并通过部署系统的环境变量或 Secret 注入后启动模块。Pairing Code 不会输出到日志。
5. 在“设置 → Modules”中输入模块地址和 Pairing Code。
6. 检查模块请求的 Host Capability、Action、配套插件版本和数据清理能力。
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

- [Plugin Developer Guide](docs/plugin-developer-guide.md)：前端可信代码边界、插件生命周期和 Module SDK。
- [Module Developer Guide](docs/module-developer-guide.md)：manifest、任务、SSE、审批、产物、Host Capability 和部署模板。
- [Human + AI Development Guide](docs/human-ai-development-guide.md)：面向人和 AI 的最小目录、Schema、命令、验收清单和禁止事项。
- [Server 与模块部署](docs/deployment/server-and-modules.md)：Source/Compose 网络与持久化。
- [发布流程](docs/release/release-process.md)与 [T8 验收状态](docs/release/acceptance-status.md)
- [OpenAPI](docs/api/openapi.json)：Server HTTP API 的机器可读快照。
- [Module Manifest Schema](backend/contracts/module-manifest-v1.schema.json)
- [Module Management Schema](backend/contracts/module-management-v1.schema.json)
- [Module Task Schema](backend/contracts/module-task-v1.schema.json)
- [Module Plugin SDK Contract](backend/contracts/module-plugin-sdk-v1.json)
- [Reference Module](examples/reference-module/)

常用一致性检查：

```bash
.venv/bin/python scripts/export-openapi.py --check
.venv/bin/python scripts/module-conformance.py contracts
.venv/bin/python scripts/module-conformance.py task-probe \
  --base-url http://127.0.0.1:8765 \
  --pairing-code A_FRESH_ONE_TIME_CODE \
  --fixture examples/reference-module/conformance-fixture.json
./scripts/run-t6-source-gate.sh
```

## 兼容与发布边界

- 经典 `v2.2.1` 数据通过只读源导入进入 Server，不在原目录上迁移。
- 旧插件接口继续兼容；模块配套插件应只通过 `window.ChatRaw.modules` 访问模块功能。
- Module Protocol v1 只承诺协议主版本 1 内的兼容规则。
- 本仓库的 Source、Compose、参考模块和 Agent 链路有本地工程验收。
- 客户数据、客户 Token、客户硬件与网络、生产 DNS/TLS/防火墙、真实上游 API 和生产性能仍为 `PENDING_ONSITE`，合成测试不代表客户或生产验收。

## License

MIT

---

# English

ChatRaw Server is the shared multi-user edition of ChatRaw. Every user must sign in before accessing product data or functions. Administrators manage users, models, plugins, and backend modules. Members can use enabled features but cannot install, disable, or remove plugins or modules.

[User Guide](docs/user-guide.md) · [Administrator Guide](docs/admin-guide.md) · [Module Development](docs/module-developer-guide.md)

## Product model

ChatRaw Server has two primary responsibilities:

1. **Shared multi-user access with roles.** Users share one platform and its business data; this is not tenant-level data isolation.
2. **Large features as independent modules.** A feature that needs a backend, privileged access, a database, or complex dependencies runs outside the ChatRaw backend. Its frontend entry point is still a ChatRaw plugin.

- A **plugin** is trusted frontend code that adds an entry point or presentation.
- A **module** is an independent backend service.
- **ChatRaw Server** owns authentication, authorization, lifecycle management, task forwarding, and the security boundary.
- A module cannot modify the ChatRaw frontend or deliver executable UI code.

```text
User → ChatRaw UI → companion plugin → generic module gateway
     → independent module → module-private dependencies
```

Agent is the first production module. Only the ChatRaw-to-Agent northbound interface is standardized. The private Agent–LinkDB protocol is unchanged and is not part of the public Module Protocol.

## Roles

| Operation | Admin | Member |
|---|---:|---:|
| Sign in and use shared product data | ✓ | ✓ |
| Use enabled plugins and modules | ✓ | ✓ |
| Manage users and audit events | ✓ | — |
| Configure models, plugins, and modules | ✓ | — |
| Install, disable, or remove plugins | ✓ | — |
| Pair, approve, enable, disconnect, or purge modules | ✓ | — |

Classic imported resources have no creator. Members can use them, while only administrators can manage them.

## Quick start

### Docker Compose

The published image supports both x86-64 and ARM64:

```bash
docker pull massif01/chatraw-server:0.0.1
```

To build from this repository and use its Compose configuration:

```bash
./scripts/create-module-network.sh
docker compose up -d --build
docker compose exec chatraw \
  python -c "from pathlib import Path; print(Path('/app/data/secrets/setup-token').read_text().strip())"
```

Open `http://127.0.0.1:51111/setup` and use the one-time Setup Token to create the first administrator.

The default Compose project exposes only the Server port, persists Server data in a named volume, and joins the external `chatraw-modules` bridge. Production deployments must use HTTPS behind a trusted reverse proxy. Never enable `CHATRAW_LOOPBACK_DEV=1` on a public deployment.

### Source

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/python scripts/prepare-server-secrets.py --data-dir data
DATA_DIR="$PWD/data" CHATRAW_LOOPBACK_DEV=1 \
  .venv/bin/python backend/main.py
```

The loopback development flag is only for local HTTP use.

## Module onboarding

An administrator injects a fresh one-time Pairing Code through the deployment environment, starts the module, and pairs it under **Settings → Modules**. The code is never printed to logs. Before enabling the module, review:

- requested Host Capabilities;
- actions and minimum roles;
- companion plugin ID and version range;
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

- [User Guide](docs/user-guide.md)
- [Administrator Guide](docs/admin-guide.md)
- [Plugin Developer Guide](docs/plugin-developer-guide.md)
- [Module Developer Guide](docs/module-developer-guide.md)
- [Human + AI Development Guide](docs/human-ai-development-guide.md)
- [Deployment and module operations](docs/deployment/server-and-modules.md)
- [Release process](docs/release/release-process.md) and [acceptance status](docs/release/acceptance-status.md)
- [OpenAPI snapshot](docs/api/openapi.json)
- [Module JSON Schemas](backend/contracts/)
- [Reference module](examples/reference-module/)

```bash
.venv/bin/python scripts/export-openapi.py --check
.venv/bin/python scripts/module-conformance.py contracts
.venv/bin/python scripts/module-conformance.py task-probe \
  --base-url http://127.0.0.1:8765 \
  --pairing-code A_FRESH_ONE_TIME_CODE \
  --fixture examples/reference-module/conformance-fixture.json
./scripts/run-t6-source-gate.sh
```

## Acceptance boundary

Source, Compose, the reference module, and the Agent chain have local engineering evidence. Customer data, credentials, hardware, networks, production DNS/TLS/firewall, real upstream behavior, and production performance remain `PENDING_ONSITE`. Synthetic evidence must not be presented as customer or production acceptance.

## License

MIT
