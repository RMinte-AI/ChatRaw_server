# ChatRaw Server deployment and module operations

This document defines the T6 deployment boundary. Source and Docker Compose are
two supported ways to run the same ChatRaw Server and Module Protocol v1. They
do not define two products or two module APIs.

## Product boundary

- ChatRaw registers, reviews, configures, enables, drains, disables,
  disconnects, and requests data purge through Module Protocol v1.
- ChatRaw never starts, stops, upgrades, or deletes a process, container,
  network, or volume.
- The WebUI never receives the Docker socket. It shows deployment-aware repair
  guidance, but the administrator performs infrastructure operations.
- A backend module never injects frontend code. The frontend is either an
  administrator-managed companion plugin or a source-built Resident
  Integration shipped with the Server.

## Source deployment

Run ChatRaw and each module as separate operating-system services. For local
development, loopback addresses are valid:

```bash
python scripts/prepare-server-secrets.py --data-dir ./data
DATA_DIR=./data PORT=51111 python backend/main.py

REFERENCE_MODULE_DATA_DIR=./reference-data \
REFERENCE_MODULE_PAIRING_CODE="$(openssl rand -hex 24)" \
python -m uvicorn --app-dir examples/reference-module app:app \
  --host 127.0.0.1 --port 8765
```

Keep the generated code in the administrator's terminal or secret manager and
enter it once under **Settings → Modules** when connecting
`http://127.0.0.1:8765`. The module deliberately does not print the code. It
must be 16–4096 characters, expires, and is consumed by the first successful
pair.

To exercise the same module with its source-built Resident entry, set
`REFERENCE_MODULE_FRONTEND_MODE=resident` before starting it. Resident source
is compiled into the Server image or source deployment; changing it requires a
Server rebuild and redeployment, not a WebUI install action.

## Docker Compose deployment

The administrator creates the shared northbound bridge once:

```bash
./scripts/create-module-network.sh
```

Defaults are network `chatraw-modules` and CIDR `172.30.0.0/24`. Both can be
changed together:

```bash
CHATRAW_MODULE_NETWORK=acme-chatraw-modules \
CHATRAW_MODULE_NETWORK_CIDR=172.31.40.0/24 \
./scripts/create-module-network.sh
```

Start the independently owned Compose projects:

```bash
docker compose up -d --build
docker compose -f examples/reference-module/compose.yml up -d --build
docker compose -f examples/reference-module/compose.yml logs reference-module
```

In the WebUI, connect
`http://chatraw-reference-module:8765`. Neither the module nor its private
dependency publishes a host port. The reference module joins the shared bridge
for northbound ChatRaw traffic and an internal private network for its
downstream dependency. ChatRaw cannot resolve or reach that private dependency.

In Compose, `127.0.0.1` and `localhost` mean the current container. ChatRaw
therefore rejects a loopback module address and shows administrators repair
warnings for existing loopback model or Hermes addresses. It never rewrites an
address silently.

For the explicit hybrid case where **ChatRaw runs in Compose but a module runs
from source on the Linux host**, the Server Compose defines
`host.docker.internal:host-gateway`. Bind that source module only to an
administrator-approved host interface, connect with
`http://host.docker.internal:<port>`, and add the exact host-gateway `/32` to
`CHATRAW_MODULE_EXTRA_CIDRS`. This mapping does not expose the Docker socket or
grant host networking. The reverse hybrid—source ChatRaw reaching a Compose
module—is intentionally not enabled by the reference Compose, because doing so
would require publishing the module port to the host. Use both-source or
both-Compose deployment instead.

## Persistence and lifecycle

Source deployments persist ChatRaw and module data in their configured data
directories. Compose persists them in separate named volumes. Ownership stays
separate: ChatRaw backup does not include module-owned data, and disconnecting
a module preserves its data.

Recommended upgrade sequence:

1. Drain the module in ChatRaw so no new tasks start.
2. Wait for active tasks to finish or cancel them explicitly.
3. Back up both ChatRaw data and the affected module data.
4. Upgrade and start the module; run health and readiness checks.
5. Upgrade and start ChatRaw; verify the registration and persisted tasks.
6. Re-enable the feature suite.

For source deployments, stop the service and use `backend.server_data` to
create and verify a checksummed SQLite-consistent backup. For Compose,
`docker compose down` preserves named volumes; `down --volumes` deletes them
and must not be used during a normal upgrade.

Example ChatRaw Compose backup, using the existing service image and a local
`backups` directory:

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

Restore into a new Compose project and its new empty volume. This keeps the
current volume recoverable and avoids an in-place overwrite:

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

`--allow-empty-destination` accepts only an existing empty directory or volume;
it still refuses to overwrite files. Back up each module separately according
to that module's recovery contract. Test restoration on a disposable project
before relying on a backup. A rollback that crosses a database migration must
restore the matching pre-upgrade data snapshot; do not run older code against
a newer schema.

If an upgrade fails, keep the feature suite drained, preserve logs and volumes,
restore the matching ChatRaw/module snapshots, start the previous versions,
then run health, readiness, task recovery, approval, and artifact checks before
re-enabling. Data purge is a separate, explicit administrator action and is not
part of disconnect, disable, `compose down`, or rollback.

## Deployment conformance

Both forms use the same black-box acceptance:

```bash
./scripts/run-t6-source-gate.sh
./scripts/run-t6-compose-gate.sh
```

It covers pairing, configuration, tasks, SSE, cancellation, approval,
artifacts, bad credentials, process/container restart, Server restart, and
persistent recovery. The Compose gate additionally checks published ports,
network isolation, external bridge configuration, and volume retention across
`compose down`.

---

# ChatRaw Server 部署与模块运维

本文定义 T6 的部署边界。源码和 Docker Compose 是运行同一套 ChatRaw
Server 与 Module Protocol v1 的两种方式，不是两个产品，也不允许出现两套模块
协议。

## 产品边界

- ChatRaw 只通过 Module Protocol v1 完成注册、审核、配置、启用、排空、
  停用、断开和数据清除请求。
- ChatRaw 不启动、停止、升级或删除任何进程、容器、网络和数据卷。
- WebUI 不接触 Docker socket，只显示与部署方式相关的修复提示；基础设施操作
  必须由管理员在系统外执行。
- 后端模块不能注入前端代码；前端连接只能由管理员管理的配套插件，或随
  Server 源码构建的 Resident Integration 完成。

## 源码部署

ChatRaw 和每个模块分别作为操作系统服务运行。本机开发可以使用回环地址：

```bash
python scripts/prepare-server-secrets.py --data-dir ./data
DATA_DIR=./data PORT=51111 python backend/main.py

REFERENCE_MODULE_DATA_DIR=./reference-data \
REFERENCE_MODULE_PAIRING_CODE="$(openssl rand -hex 24)" \
python -m uvicorn --app-dir examples/reference-module app:app \
  --host 127.0.0.1 --port 8765
```

部署者必须保管并显式注入一次性配对码，模块不会把它输出到日志。在
**设置 → Modules** 中使用该配对码连接 `http://127.0.0.1:8765`，
审核声明、完成配置并启用功能套件。

要让同一参考模块使用源码级常驻入口，启动模块前设置
`REFERENCE_MODULE_FRONTEND_MODE=resident`。Resident 源码随 Server 镜像或
源码部署一起构建；修改后需要重新构建和部署 Server，不能在 WebUI 动态安装。

## Docker Compose 部署

管理员先显式创建一次共享的北向网桥：

```bash
./scripts/create-module-network.sh
```

默认网络名为 `chatraw-modules`，CIDR 为 `172.30.0.0/24`。如需修改，必须
同时修改并保持一致：

```bash
CHATRAW_MODULE_NETWORK=acme-chatraw-modules \
CHATRAW_MODULE_NETWORK_CIDR=172.31.40.0/24 \
./scripts/create-module-network.sh
```

然后分别启动两个独立归属的 Compose 项目：

```bash
docker compose up -d --build
docker compose -f examples/reference-module/compose.yml up -d --build
docker compose -f examples/reference-module/compose.yml logs reference-module
```

在 WebUI 中连接 `http://chatraw-reference-module:8765`。模块和私有依赖都
不发布宿主机端口。参考模块同时加入共享北向网桥和内部私有网络；ChatRaw 不能
解析或访问私有依赖。

在容器内，`127.0.0.1` 与 `localhost` 都指向当前容器。因此 ChatRaw 会
拒绝回环模块地址，并对旧的回环模型或 Hermes 地址显示管理员修复提示，但绝不
静默改写配置。

若明确采用“**ChatRaw 运行在 Compose、模块源码运行在 Linux 宿主机**”的混合
方式，Server Compose 已声明 `host.docker.internal:host-gateway`。源码模块应
只监听管理员批准的宿主机接口，使用
`http://host.docker.internal:<端口>` 接入，并把宿主网关的精确 `/32` 加入
`CHATRAW_MODULE_EXTRA_CIDRS`。该映射不会暴露 Docker socket，也不授予 host
网络。反方向的“源码 ChatRaw 访问 Compose 模块”不会由参考 Compose 开启，
因为那需要向宿主机发布模块端口；应改用全源码或全 Compose 部署。

## 持久化与生命周期

源码部署把 ChatRaw 与模块数据分别保存在各自的数据目录中；Compose 使用互相
独立的命名卷。数据所有权始终分离：ChatRaw 备份不包含模块数据，断开模块也不会
删除模块数据。

建议升级顺序：

1. 在 ChatRaw 中排空模块，停止接收新任务。
2. 等待活动任务结束，或由管理员明确取消。
3. 分别备份 ChatRaw 数据和目标模块数据。
4. 升级并启动模块，检查健康与 Ready。
5. 升级并启动 ChatRaw，确认注册信息和持久任务均可恢复。
6. 重新启用功能套件。

源码部署应先停止服务，再使用 `backend.server_data` 创建经过校验的 SQLite
一致性备份。Compose 的 `docker compose down` 会保留命名卷；正常升级绝不能
使用会删除数据的 `down --volumes`。

以下示例使用现有服务镜像和本地 `backups` 目录备份 ChatRaw Compose 数据：

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

恢复到一个新的 Compose project 和空数据卷，避免覆盖当前卷：

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

`--allow-empty-destination` 只接受空目录或空卷，仍然拒绝覆盖任何文件。每个模块
按照自己的恢复契约单独备份。正式依赖备份前，先在一次性项目中验证恢复。若回滚
跨越数据库迁移，必须恢复与旧版本匹配的升级前快照，不能让旧代码直接读取新结构。

升级失败时，保持功能套件处于排空状态，保留日志与数据卷，恢复配套的
ChatRaw/模块快照，启动旧版本，并重新验证健康、Ready、任务恢复、审批和产物，
确认后再启用。数据清除是另一项独立且明确的管理员操作，不属于断开、停用、
`compose down` 或回滚。

## 部署一致性验收

两种部署方式使用同一个黑盒验收器：

```bash
./scripts/run-t6-source-gate.sh
./scripts/run-t6-compose-gate.sh
```

它覆盖配对、配置、任务、SSE、取消、审批、产物、错误凭据、进程或容器重启、
Server 重启和持久恢复。Compose 验收还会检查端口暴露、网络隔离、外部共享
网桥，以及 `compose down` 后的数据卷保留。
