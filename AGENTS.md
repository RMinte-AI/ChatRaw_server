# AI 文档导航

本文件适用于整个仓库，只负责告诉 AI 应阅读和同步哪些文档。不要在这里重复协议、接口或部署细节。

## 阅读原则

- 所有修改先读 `README.md` 和 `docs/human-ai-development-guide.md`。
- 涉及安全、认证、权限或秘密时，同时读 `SECURITY.md`。
- JSON Schema、OpenAPI、SDK Contract 和实际运行结果是机器事实源；指南不能扩展机器契约中不存在的能力。
- 只阅读与当前任务有关的专项文档，不要借此扩大修改范围。

## 文档用途

| 路径 | 用途 | AI 关注要求 |
|---|---|---|
| `README.md` | 产品定位、架构边界、启动方式和文档总入口 | **所有任务必读；产品能力变化时同步** |
| `docs/human-ai-development-guide.md` | 人与 AI 的开发顺序、边界、验收和禁止事项 | **所有代码修改必读** |
| `docs/frontend-color-requirements.md` | 四页式界面的浅色语义色板、对比度和 Plugin/Resident 配色边界 | **修改前端视觉、CSS 或 Workspace UI 时必读并同步** |
| `SECURITY.md` | 登录、权限、秘密、漏洞报告和安全要求 | **安全相关修改必读** |
| `docs/user-guide.md` | 普通用户可见功能和使用体验 | 用户行为变化时同步 |
| `docs/admin-guide.md` | 用户、插件、模块、备份和权限管理 | 管理行为变化时同步 |
| `docs/plugin-developer-guide.md` | 插件权限、生命周期、设置和 Module SDK | **修改插件或插件接口时必读** |
| `docs/module-developer-guide.md` | Module Protocol、任务、SSE、审批、产物和 Host Capability | **修改模块系统时必读** |
| `docs/resident-module-integration-guide.md` | Resident 源码边界、挂载位、Host SDK 和 AI 停止条件 | **修改 Resident 时必读** |
| `docs/deployment/server-and-modules.md` | Source、Compose、网络、持久化、备份和恢复 | 修改部署或运行方式时必读并同步 |
| `docs/release/release-process.md` | 正式发布、迁移、备份和回滚流程 | 发版或修改发布自动化时必读 |
| `docs/release/acceptance-status.md` | 当前验收状态和 `PENDING_ONSITE` 边界 | 更新验收结论时同步 |
| `docs/release/v0.0.1.md`、`RELEASE_v2.2.1.md` | 版本说明和历史记录 | 仅对应版本发布时更新；旧版本不是当前事实源 |
| `docs/hermes.md`、`docs/skills.md` | Hermes 与 Skills 专项功能 | 修改对应功能时阅读 |
| `docs/contracts/*` | 经典版兼容边界说明 | 修改兼容行为时必读并同步 |
| `Plugins/README.md` | 内置插件目录和开发入口 | 修改插件市场结构时阅读 |
| `.github/CI.md`、`.github/PULL_REQUEST_TEMPLATE.md` | CI、审查和提交约定 | 修改 GitHub 自动化时阅读 |

## 机器契约与示例

| 路径 | 用途 | AI 关注要求 |
|---|---|---|
| `docs/api/openapi.json` | Server HTTP API 快照 | **修改 API 时必须同步；通过生成脚本更新** |
| `backend/contracts/module-*.json` | Module Manifest、管理、任务、SDK 和 conformance 契约 | **修改模块行为前必读** |
| `backend/contracts/plugin-ui-sdk-v1.json` | Plugin 工具栏、弹窗与主内容区 Workspace 契约 | **修改插件 UI 公共接口前必读** |
| `backend/contracts/resident-*.json` | Resident 描述文件与 Host SDK 契约 | **修改 Resident 行为前必读** |
| `backend/contracts/chatraw-server-schema-v1.json` | Server 数据库版本和表结构契约 | 修改数据库迁移时必读并同步 |
| `backend/contracts/chatraw-v2.2.1.json` | 经典版导入兼容契约 | 修改经典版兼容时阅读 |
| `examples/reference-module/*` | Plugin 与 Resident 双模式参考模块和 conformance 示例 | 开发模块或修改公共契约时必读 |
| `Plugins/Plugin_market/*/manifest.json`、`Plugins/Plugin_market/index.json` | 插件清单和市场索引 | 修改对应插件或市场时同步 |
| `ResidentIntegrations/*/integration.json` | Resident ID、入口、角色和 Action 依赖 | 修改对应 Resident 时必读并同步 |

## 生成文件

- `docs/api/openapi.json` 由 `scripts/export-openapi.py` 生成。
- `backend/static/resident-integrations/*` 由 `scripts/build-frontend.mjs` 生成。
- `docs/lighthouse/*` 是性能报告。
- 不要手工修改生成文件；修改源文件后运行对应生成或检查命令。

## 完成前

- 公共行为变化时，同步用户、管理员或开发者指南中的对应说明。
- 公共契约变化时，同步 Schema、OpenAPI、示例、实现和测试。
- 不把 Agent–LinkDB 或其他商业私有协议写入公共文档。
- 至少运行 `.venv/bin/python scripts/check-t8-docs.py`；再按任务运行 OpenAPI、conformance、前端或部署检查。
