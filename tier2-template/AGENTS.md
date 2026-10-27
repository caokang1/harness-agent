# {{PROJECT_NAME}} — Agent 导航

> {{PROJECT_DESC}}。{{TECH_STACK}}。
>
> 开发环境：后端 `:{{BACKEND_PORT}}`（Spring Boot，{{BUILD_TOOL}}）+ 前端 `:{{FRONTEND_PORT}}`（Vue3 + Vite dev server）

## 编码规则入口（每次改代码前必读）

| 层 | 规则文件 |
|----|---------|
| 后端（Java） | [`BACKEND_RULES.md`](BACKEND_RULES.md) |
| 前端（Vue） | [`{{FRONTEND_DIR}}/FRONTEND_RULES.md`]({{FRONTEND_DIR}}/FRONTEND_RULES.md) |

**每次修改代码前**：先读对应层的规则文件，执行其「强制触发规则」里的问题清单，再动手。

---

## 开发流程（按规模选择）

### 规模判定（按结构性标准，不按工时）

| 规模 | 判定标准（满足任一即命中） | 路径 |
|------|---------------------------|------|
| **S** | **全部**满足：只改一层（前或后）/ 不改 API 契约 / 不加 schema / 不加模块依赖 / 改动 ≤ 3 个文件 | 直接编码 → check → reload → test → **等用户 verify** → commit |
| **M** | 命中以下任一：改 API 契约（新/改请求参数或响应字段）/ 同时改前后端 / 新增数据库表或字段 / 新增模块间依赖 / 改动 > 3 个关联文件 | `openspec propose` → `openspec apply` → **交叉 Review** → **等用户 verify** → finish → archive |
| **L** | 命中以下任一：新增模块 / 架构调整 / 跨多个 openspec change 协同 / 预计需要拆分 subagent 并行 / **新需求（来自产品或用户、无先例参考的诉求，即使代码改动面不大）** | brainstorming → openspec → worktree → plans → subagent-dev → **交叉 Review** → **等用户 verify** → finish → archive |

> **规模升级硬条件（命中任一，禁止走 S）**：
> - 改 API 请求参数或响应字段
> - 同时涉及前端 + 后端
> - 新增数据库 schema（表/字段/索引）
> - 新增跨模块依赖（见 `BACKEND_RULES.md`「当前合法的横向依赖」）
> - 改动 > 3 个功能相关联的文件
>
> 这些都是 **先验可判断** 的结构性条件，不依赖工时估算。**不确定是否命中时，默认走 M**。

**典型降级陷阱**：用户说"加一个查询条件" → Agent 以为"只改前端加个筛选" → 没改后端 → 实际不生效。此类改动天然跨前后端，命中第二条，必须走 M。

### 主题切换纪律（会话中途换主题时触发）

**触发**：会话中途要开始与前一项不相关的新主题。

**硬动作**：先 `git status --short`（两个仓库）；工作区非空 → **三选一**再动新主题：先收尾 commit（推荐）/ `git stash` 暂存 / `progress.md` 登记搁置。**跨主题文件是红灯**：新主题将改的文件已在脏工作区 → 必须先处理旧主题。

> 完整说明与反例见 [`docs/agents/session.md`](docs/agents/session.md) §主题切换。

### Commit 规则（所有规模适用）

- 实现完成后，Agent **必须停下来等用户 review 并确认通过**，才能执行 `git commit`。禁止在用户未确认前自行 commit 或 push。
- **外科手术式改动**（借鉴 Karpathy 准则）：commit 前 `git diff` 自检，**每一行改动都要能直接对应到用户请求**。发现无关 dead code / 风格不一致 / 可改进点 → **只提不改**（记到 commit message 的 `Notes:` 段或另开 openspec 变更处理）。你自己的改动产生的 orphan import / 未使用变量**必须**随本次 commit 清理；**不属于**你改动范围的既有 dead code 禁止顺手删。

### tasks.md 回填规则（openspec 变更必执行）

用户 verify 通过 → commit 之后 → **在同一次 `git push` 前必须完成** `openspec/changes/<name>/tasks.md` 对应 checkbox 回填。

- commit 与 tasks.md 回填视作**同一个 push 周期的一组操作**，禁止"下次再补"或"跨 push 补"。
- push 前自检：本周期 `git diff --stat` 必须包含对应 change 的 `tasks.md` 变更，否则停下来补勾再 push。
- 若本次 commit 让 `tasks.md` 变为**全勾** → 立即进入「归档」流程，不要留到下一次会话。
- 例外：S 规模改动若未关联任何活跃 change，跳过本规则。

---

## 编码纪律（所有层通用）

> 完整命令速查见 [`附录 A 命令速查`](docs/agents/session.md#命令速查)（`dev.sh start/reload/check/test/logs/verify-snapshot`）。

- **每次修改代码后**：运行 `bash dev.sh check --changed`，有错误先修复再继续。
- **每个 task 完成后**：运行 `bash dev.sh test` 确认测试通过。
- **commit 前必跑**：`bash dev.sh check --arch`——架构硬规则扫描（依赖方向、`@Autowired` 字段注入、业务路径 `RuntimeException`、`new Date()/SimpleDateFormat`、前端跨域 import）。基线为 0 命中，任何输出即回归。
- **Java 改动后**：触发 `bash dev.sh reload`，检查日志确认启动成功。
- **前端改动**：无需 reload，Vite HMR 自动热更新。
- **细化规则**：后端看 `BACKEND_RULES.md`，前端看 `{{FRONTEND_DIR}}/FRONTEND_RULES.md`——本文件只放流程，不重复编码细则。
- **简洁优先**（借鉴 Karpathy 准则）：不加**没被要求**的功能 / 抽象 / 配置项 / 错误处理；单次使用不抽象组件或 helper；能 50 行写的不写 200 行。**例外**：基础设施层 / API 契约层 / 明确声明的扩展点（如 Skills / Starter Kit 模板）。

---

## Verify（三阶段，缺一不可）

**契约摘要**（完整 SOP → [`docs/agents/verify.md`](docs/agents/verify.md)）：

- **阶段一 · Agent 自验**：`check --changed` + `check --arch` + `test` + `reload` 日志 + **可观察证据四选一**（curl / 日志 / DB 记录 / 单测断言）。自验失败不得进入阶段二。
- **阶段二 · 用户验证**：Agent 出示「实现摘要 + 测试结果 + 证据清单」后**停下来**，等用户明确说"通过"才能 commit。
- **超时 Fallback**：用户不回应时**不 stash、不 commit**，只更新 `.harness/progress.md` 后停手。
- **数据卫生**：测试数据必须带 `__agent_verify_` 前缀；`drop/truncate/reset` 前必须 grep `application.yml` 确认当前数据源（仅个人/开发库可 reset，其他环境禁止）。

---

## 归档（Archive）

完整 SOP → [`docs/agents/archive.md`](docs/agents/archive.md)。

**触发**：`tasks.md` 全部达合法终态（`[x]`/`[~]+理由`，`[ ]` 禁止归档）+ 用户确认 + PR 已创建。  
**归档前**：4 步 precheck（tasks 无悬空 / spec 存在 / 残留清理 / TRACE 已写）→ `openspec archive`。  
**每次 push 后**主动问用户"是否还有任务，否则归档"。

---

## 会话管理

完整 SOP → [`docs/agents/session.md`](docs/agents/session.md)。

**启动 7 步（顺序强制）**：① 工作区体检（两仓库 `git status`，非空三选一）② 读本文件 ③ 读 `progress.md` ④ 扫 `LEARNINGS.md` 索引 ⑤ `openspec list` ⑥ 启动体检（tasks/代码对账）⑦ Learnings 密度扫（tag ≥ 3 立刻晋升）

> **扫读预算**：步骤 ②③④ 合计控制在 ~400 行内，细节按指针下钻。

**结束**：更新 `progress.md`（做了什么 / 阻塞 / 下次起点 / 未归档 change / 外部阻塞）+ 经验回顾（失败 → `ERRORS.md`；纠正/过时 → `LEARNINGS.md`）。

**Learnings 晋升**：任一 tag ≥ 3 → 首要动作晋升进 `AGENTS.md` / `*_RULES.md`，原条目追加 `→ PROMOTED to <target> on YYYY-MM-DD`。

---

## 关键目录

| 路径 | 说明 |
|------|------|
| `BACKEND_RULES.md` / `{{FRONTEND_DIR}}/FRONTEND_RULES.md` | 编码规则（**改代码前必读**）；**模块拓扑与依赖方向**在后端规则中维护 |
| `openspec/` | 活跃变更 tasks / 元数据；`changes/archive/` 为 CLI 临时中转（归档后清空）|
| `docs/plans/archive/` | **唯一归档目标**（tasks + design + TRACE.md）|
| `docs/plans/architecture.md` | 架构文档（长期，不归档）|
| `.claude/skills/` | Agent 技能唯一源（`.cursor/skills` 是软链）|
| `.harness/progress.md` | 跨会话进度 |
| `.learnings/` | 经验沉淀（ERRORS / LEARNINGS / FEATURE_REQUESTS）|

---

## 规则变更历史

见 [`docs/agents/rules-history.md`](docs/agents/rules-history.md)。Agent 新会话无需读取——规则的当前有效状态即本文档正文。
