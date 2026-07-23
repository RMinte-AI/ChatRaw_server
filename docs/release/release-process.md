# ChatRaw Server 发布流程 / Release Process

## 中文

### 发布原则

发布不是“测试通过后覆盖旧实例”，而是：

```text
冻结公共契约
→ 生成事实源
→ 全量工程验收
→ 分别备份 Server 和模块
→ 新环境或新卷部署
→ 双角色验证
→ 切换流量
→ 保留可执行回滚
```

正式版本必须固定：

- Server commit 和版本标签；
- Module Protocol 主版本；
- OpenAPI 与 JSON Schema；
- 每个模块的 commit/镜像 digest；
- 每个配套插件版本和 ZIP SHA-256；
- 数据库 Schema 版本；
- 备份 manifest 与 verify 输出。

### 发布前

1. 确认工作树只包含本次发布范围。
2. 运行：

```bash
./scripts/run-t8-release-gate.sh
```

3. 运行真实浏览器双角色验收。
4. Drain 高价值模块并停止写入。
5. 分别备份 Server、Agent 和其他模块。
6. 对每份备份执行校验和一次隔离恢复。
7. 记录当前可回滚 commit/镜像和数据快照。

T8 release gate 是本地工程验收，不自动等于客户或生产验收。

### GitHub Release 与 Docker Hub

正式镜像发布由 `.github/workflows/docker-release.yml` 负责，目标固定为：

```text
docker.io/massif01/chatraw-server
```

仓库管理员必须先在 GitHub Repository Actions Secrets 中配置：

```text
DOCKERHUB_TOKEN=<Docker Hub personal access token with Read & Write permission>
```

Token 不得写入源码、Release 文本、构建参数或普通 GitHub Variable。

发布 GitHub Release 时，Tag 必须采用 `vMAJOR.MINOR.PATCH`。发布事件会从该
Tag 对应的 commit 构建同一份 Dockerfile，并推送：

- `MAJOR.MINOR.PATCH`；
- `latest`，仅用于非预发布版本；
- 同一 manifest 下的 `linux/amd64` 和 `linux/arm64` 镜像。

工作流在推送后读取远程 manifest，并要求两个平台同时存在。GitHub Release 和
Docker Hub manifest 均成功后，才能把该版本标记为“镜像已发布”。

### 部署

优先部署到新目录、新 Compose project 或新卷，不在原数据上直接覆盖：

1. 恢复已验证备份或执行经典数据导入。
2. 启动 Server，等待 `/ready`。
3. 启动各模块，检查 Health/Ready。
4. 管理员登录，检查用户、模型、插件和模块。
5. 普通用户登录，完成普通聊天和 Agent 任务。
6. 检查浏览器控制台、审计记录和秘密负向项。
7. 再切换反向代理或正式入口。

### 回滚

触发条件包括：

- Server 无法 Ready；
- 登录或角色失效；
- 经典数据内容不一致；
- 模块权限状态异常；
- Agent 全链路失败；
- 数据库迁移后出现不可接受错误。

回滚时：

1. 停止新流量和新任务。
2. 保留失败实例日志与卷。
3. 启动旧代码和与其匹配的旧数据快照。
4. 不让旧代码读取升级后的数据库。
5. 验证双角色、普通聊天和关键模块后恢复流量。

### 现场验收

以下项目在真实证据完成前统一为 `PENDING_ONSITE`：

- 客户真实数据与语义；
- 客户 Token 和轮换；
- 真实服务器、GPU 或设备；
- 客户网络、DNS、TLS、代理和防火墙；
- 真实上游 API 行为与故障；
- 真实数据规模、并发和性能；
- 正式切流和回滚演练。

合成 fixture、模拟客户 API 和本机 Docker 网络不能替代这些证据。

---

## English

A release freezes commits, versions, OpenAPI, JSON Schemas, module and plugin artifacts, database Schema, and verified backup manifests. Run the full T8 release gate, complete a real two-role browser flow, drain writes, and restore Server and module backups into an isolated destination before rollout.

Published GitHub Releases trigger `.github/workflows/docker-release.yml`. The
workflow requires a repository Actions secret named `DOCKERHUB_TOKEN`, publishes
`docker.io/massif01/chatraw-server`, and verifies that the resulting manifest
contains both `linux/amd64` and `linux/arm64`. Stable releases publish the exact
semantic version and `latest`; prereleases do not update `latest`.

Prefer a new directory, Compose project, or volume. Verify Server readiness, module health/readiness, admin management, member use, normal chat, Agent, audit output, and browser secret-negative checks before switching traffic.

Rollback always restores matching code and data together. Preserve the failed instance for diagnosis; never let older code open a newer migrated database.

Customer data, credentials, hardware, networks, DNS/TLS/firewall, upstream behavior, production scale, traffic cutover, and rollback rehearsal remain `PENDING_ONSITE` until verified in that environment.
