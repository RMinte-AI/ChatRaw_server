# CI / PR 自动化文档

## 概述

自动化流程，包含 **CI**（代码检查与 Docker 构建）与 **PR Review**（安全检查、静态检查、AI 代码审查、自动标签、审查报告）。本文档记录所有关键设计决策与实现细节，以便完整复现。

---

## 文件结构

```
.github/
├── CI.md                    # 本文档
├── workflows/
│   ├── ci.yml               # CI：语法、Flake8、模块导入、Docker 构建
│   └── pr-review.yml        # PR Review：安全检测、静态检查、AI 审查、评论
└── scripts/
    └── ai_review.py         # AI 审查脚本（Gemini / OpenAI 兼容）
```

---

## 工作流概览

| 工作流 | 文件 | 触发 | 功能 |
|--------|------|------|------|
| CI | `ci.yml` | `main` 推送、PR 创建/更新 | 代码检查、后端回归、源码部署验收、前端依赖审计与构建校验、Chromium/WebKit 聊天回归、Docker 构建 |
| PR Review | `pr-review.yml` | PR 创建/更新 | 安全检查、静态检查、AI 代码审查、自动标签、审查报告 |

### 触发路径

| 工作流 | 监听的路径 |
|--------|------------|
| CI | `backend/**/*.py`, `backend/requirements*.txt`, `backend/static/**`, `backend/contracts/**`, `browser-tests/**`, `examples/reference-module/**`, `package*.json`, `playwright.config.mjs`, `scripts/**`, `Dockerfile`, `docker-compose.yml`, `docs/**`, `.github/workflows/**` |
| PR Review | 同上，外加 `.github/scripts/**` |

---

## 安全模型（关键）

### 设计原则

当 PR 修改了 `.github/workflows/*.yml` 或 `.github/scripts/*.py` 时，存在恶意代码操控审查逻辑的风险。因此：

1. PR Review 只使用 `pull_request`。Fork 代码只能在只读 Token、无仓库 Secrets 的环境中检出和检查；不得使用 `pull_request_target` 高权限检出 Fork 代码。
2. **`security-check`** 检测这些敏感文件是否被改动
3. 若被改动 → `safe_to_run=false`
4. `auto-check` 和 `ai-review` 在 `safe_to_run=false` 时 **不执行**（跳过）
5. **`comment` 始终执行**（`if: always() && github.event.pull_request != null`），用于：
   - 当 `safe_to_run=true` 时：发布完整审查报告（含 AI 结果）
   - 当 `safe_to_run=false` 时：发布说明性评论，告知用户因修改敏感文件而跳过 AI 审查

### 实现细节

- **敏感文件检测命令**：
  ```bash
  git diff --name-only origin/$BASE_REF...HEAD -- '.github/workflows/*.yml' '.github/scripts/*.py'
  ```
- 每个检出目录中的 `origin/$BASE_REF` 都从 PR 的上游仓库显式获取，不能使用 Fork 自己可能滞后的同名分支作为比较基线。
- Fork PR 的 `GITHUB_TOKEN` 没有标签和评论写权限；`labeler` 与 `comment` 此时记录跳过信息，但不把代码检查判为失败。
- **`comment` 的 `if` 条件**：必须为 `always()`，否则在 `ai-review` 被 skip 时，`comment` 也会因依赖失败而被 skip，导致 PR 上没有任何评论。
- **当 `safe_to_run=false` 时**：`comment` 将 `aiResult` 覆盖为固定提示文案，说明跳过原因。

---

## PR Review 流程

```
security-check（检测 .github/workflows、.github/scripts 是否被修改）
       ↓
    safe_to_run = true/false
       ↓
auto-check（仅当 safe_to_run=true：对变更的 .py 做语法 + Flake8，检测 .py/.js/.css 变更）
       ↓
    has_reviewable_changes、syntax_ok
       ↓
ai-review（仅当 safe_to_run=true 且 has_reviewable_changes=true 且 auto-check 成功）
       ↓
    脚本从 main 分支拉取，审查 PR 分支的 Python/JavaScript/CSS diff
       ↓
comment（always 执行，汇总报告，发表/更新 PR 评论）
```

`labeler` 独立运行，按文件路径和变更量打标签。

---

## AI 审查实现

### 安全设计

- **脚本来源**：`ai_review.py` 从 **main 分支** 拉取（`checkout ref: default_branch`），不执行 PR 分支中的脚本，防止恶意 PR 篡改审查逻辑。
- **执行目录**：PR 代码 checkout 到 `pr-code/`，脚本在 `pr-code` 下运行，但脚本文件来自 `main-scripts/.github/scripts/`。

### API 优先级

1. **优先**：OpenAI 兼容接口（DeepSeek、OpenAI、国产模型等）
   - 环境变量：`OPENAI_API_KEY`（必须）、`OPENAI_BASE_URL`（可选）、`OPENAI_MODEL`（可选）
2. **备用**：Gemini
   - 环境变量：`GEMINI_API_KEY`、`GEMINI_MODEL_FALLBACK`（可选）

### 脚本逻辑

- 使用 `git diff origin/$BASE_REF...HEAD -- *.py *.js *.css backend/**/*` 获取变更的 Python/JavaScript/CSS 文件及 diff
- diff 超过 15000 字符时截断
- 审查维度：安全、Bug、性能、可读性、架构、前端特有（JS/CSS：DOM 安全、兼容性、无障碍性）
- 结果写入 `ai_review_result.txt`，供 `comment` job 读取并发布

### Comment 与 Artifact

- `comment` 依赖 `download-artifact@ai-review-result`，需设置 `continue-on-error: true`：当 `ai-review` 被 skip 时无 artifact，下载会失败，但不影响后续步骤
- 当 `ai_review_result.txt` 不存在时，`comment` 使用默认文案；当 `safe_to_run=false` 时，强制覆盖为跳过说明

---

## GitHub 配置

### Secrets（必须至少其一）

| Secret | 用途 |
|--------|------|
| `OPENAI_API_KEY` | OpenAI 兼容 API Key（推荐，支持 DeepSeek / OpenAI / 国产模型） |
| `GEMINI_API_KEY` | Gemini API Key（备用） |

### Variables（可选）

| Variable | 说明 | DeepSeek 示例 |
|----------|------|---------------|
| `OPENAI_BASE_URL` | API 地址 | `https://api.deepseek.com/v1` |
| `OPENAI_MODEL` | 模型名 | `deepseek-chat` 或 `deepseek-coder` |
| `GEMINI_MODEL_FALLBACK` | Gemini 模型（仅当用 Gemini 时） | `gemini-2.5-flash` |

### Labels（需预先在仓库中创建）

- **业务**：`backend`、`plugins`、`frontend`、`documentation`、`ci/cd`、`scripts`
- **规模**：`size/S`、`size/M`、`size/L`、`size/XL`

---

## 复现指南

### 1. 创建目录结构

```bash
mkdir -p .github/workflows .github/scripts
```

### 2. 创建 `ci.yml`

参考 `.github/workflows/ci.yml`，包含：
- 触发：`pull_request`，路径为 `backend/**/*.py` 等
- `code-check`：从 `backend/requirements-dev.txt` 安装锁定依赖，运行 compileall、Flake8 E9/F63/F7/F82、模块导入、后端回归、源码部署验收、npm 生产依赖审计与前端构建产物校验，并在真实 Chromium、WebKit 和移动 WebKit 中验证普通聊天、Module conversation、标题、刷新恢复及模型左/用户右布局
- `docker-build`：`docker build` + 冒烟测试

### 3. 创建 `pr-review.yml`

参考 `.github/workflows/pr-review.yml`，关键点：
- 只使用 `pull_request`；Fork PR 不获得仓库 Secrets，Token 由 GitHub 降级为只读
- 从上游仓库显式获取 base 分支，不能从 Fork 的 `origin/main` 计算差异
- `security-check`：检测 `.github/workflows/*.yml`、`.github/scripts/*.py`
- `auto-check`：`if: needs.security-check.outputs.safe_to_run == 'true'`
- `ai-review`：`if` 包含 `safe_to_run`、`has_reviewable_changes`、`auto-check.result == 'success'`
- **`comment`**：`if: always() && github.event.pull_request != null`（必须！）
- `comment` 中：当 `!safeToRun` 时，将 `aiResult` 设为说明性文案
- 标签或评论写入必须捕获 Fork 只读 Token 的拒绝，不能让报告写入权限影响代码检查结论

### 4. 创建 `ai_review.py`

参考 `.github/scripts/ai_review.py`，包含：
- `get_py_diff()`：获取变更的 .py 文件和 diff
- `call_openai_compatible()`：优先调用 OpenAI 兼容 API
- `call_gemini()`：备用 Gemini
- `write_result()`：写入 `ai_review_result.txt`

### 5. 配置 GitHub

- 在仓库 Settings → Secrets and variables → Actions 中添加 `OPENAI_API_KEY` 或 `GEMINI_API_KEY`
- 可选：添加 `OPENAI_BASE_URL`、`OPENAI_MODEL`
- 创建上述 Labels

### 6. 配置 `.flake8`

CI 使用 `flake8 --select=E9,F63,F7,F82`（仅严重错误），与 `.flake8` 的 `ignore` 不冲突。

---

## 验证步骤

### 验证 1：业务代码 PR（应触发完整 AI 审查）

1. 创建分支，**只修改** `backend/main.py`（如改一行注释）
2. 推送并创建 PR
3. 预期：
   - `security-check` → `safe_to_run=true`
   - `auto-check`、`ai-review` 均执行
   - PR 上出现「🤖 自动审查报告」评论，且包含 AI 审查内容

### 验证 2：修改 .github 的 PR（应跳过 AI 审查）

1. 创建分支，修改 `.github/workflows/pr-review.yml` 或 `.github/scripts/ai_review.py`
2. 推送并创建 PR
3. 预期：
   - `security-check` → `safe_to_run=false`
   - `auto-check`、`ai-review` 被 skip
   - PR 上**仍有**「🤖 自动审查报告」评论，但说明「本 PR 修改了敏感文件，已跳过 AI 审查」

---

## 本地检查

```bash
# Python 检查
cd backend
python -m py_compile main.py
flake8 --select=E9,F63,F7,F82 main.py
python -c "from main import app"

# Docker
docker build -t chatraw:test .
docker run --rm chatraw:test python -c "print('✅ Docker OK')"
```

---

## 故障排查

| 现象 | 可能原因 |
|------|----------|
| PR 上没有任何评论 | `comment` 的 `if` 不是 `always()`，或依赖的 job 被 skip 导致整链失败。应改为 `if: always() && github.event.pull_request != null` |
| AI 审查不执行 | 未配置 `OPENAI_API_KEY` 或 `GEMINI_API_KEY`；或 `safe_to_run=false`（修改了 .github）；或无 Python/JS/CSS 变更 |
| 修改 .github 后无评论 | 同上：`comment` 必须用 `always()`，并在 `!safeToRun` 时发布说明性评论 |
| ai-review 报错 | 检查 API Key、BASE_URL、MODEL 配置；或查看 Actions 日志中的具体异常 |

---

## 参考

- `.github/workflows/ci.yml`：CI 工作流
- `.github/workflows/pr-review.yml`：PR Review 工作流
- `.github/scripts/ai_review.py`：AI 审查脚本
