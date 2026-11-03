# {{AP_PROJECT_SLUG}} — Agent 开发流程

> 多国部署的{{AP_BUSINESS}}微服务系统。Java 8 + Spring Boot 2.6 + Spring Cloud + Nacos + MyBatis + MySQL，Maven 多模块。
>
> 开发环境：不使用容器；单个服务本地 `cd <服务目录> && mvn spring-boot:run`（需要 Nacos 运行以加载配置）。本项目无前端仓库。

## 编码规则入口（每次改代码前必读）

| 层 | 规则文件 |
|----|---------|
| 后端（Java） | [`BACKEND_RULES.md`](../../BACKEND_RULES.md) |
| 前端（Vue） | [`FRONTEND_RULES.md`](../../FRONTEND_RULES.md)（本项目无前端仓库，仅备查） |

**每次修改代码前**：先读对应层的规则文件，执行其「强制触发规则」里的问题清单，再动手。业务逻辑先按上文「导航流程」读知识库文档。

## 优先级（本文件高于任何 skill）

`.claude/skills/` 里的方法论 skill 多数来自通用开源项目，部分步骤（自动 commit、push、合并分支、按工时判断规模）与本项目规则不同。**冲突时一律以本文件为准**：

- 任何 skill 里的 `git commit` / `git push` / 合并分支步骤，都只能在**用户 verify 通过并明确同意后**执行；在此之前改动留在工作区。
- 规模按本文件「规模判定」的结构性标准判断，不按 skill 里的工时或"是否行为变更"判断。
- 测试命令用 `bash dev.sh test <模块>`，不用 skill 示例里的 pytest / npm test。

---

## 开发流程（按规模选择）

### 规模判定（按结构性标准，不按工时）

| 规模 | 判定标准（满足任一即命中） | 路径 |
|------|---------------------------|------|
| **S** | **全部**满足：只改一个服务 / 不改 API 契约 / 不加 schema / 不加模块依赖 / 改动 ≤ 3 个文件 | 直接编码 → check → test → **等用户 verify** → commit |
| **M** | 命中以下任一：改 API 契约（新/改请求参数、响应字段或 Feign 接口）/ 同时改多个服务 / 新增数据库表或字段 / 新增模块间依赖 / 改动 > 3 个关联文件 | `openspec propose` → `openspec apply` → **交叉 Review** → **等用户 verify** → finish（提交 → 推功能分支 → 合入测试集成分支）→ 完结 |
| **L** | 命中以下任一：新增模块 / 架构调整 / 跨多个 openspec change 协同 / 预计需要拆分 subagent 并行 / **新需求（来自产品或用户、无先例参考的诉求，即使代码改动面不大）** | brainstorming → openspec → worktree → plans → subagent-dev → **交叉 Review** → **等用户 verify** → finish → 完结 |

> **规模升级硬条件（命中任一，禁止走 S）**：
> - 改 API 请求参数、响应字段或 Feign 接口
> - 同时涉及多个服务
> - 新增数据库 schema（表/字段/索引）
> - 新增跨模块依赖（见 `BACKEND_RULES.md`「当前合法的横向依赖」）
> - 改动 > 3 个功能相关联的文件
>
> 这些都是 **先验可判断** 的结构性条件，不依赖工时估算。**不确定是否命中时，默认走 M**。

**典型降级陷阱**：用户说"加一个查询条件" → Agent 以为"只改 {{AP_SVC_ADMIN}} 的接口" → 没改提供数据的服务和 Feign 接口 → 实际不生效。此类改动天然跨服务，命中第二条，必须走 M。

### 分支规则（开工前定基线，收尾时定去向）

依据：`{{AP_DISTRIBUTE_SCRIPT}}` + 2026-08~10 合并历史。发布链路 = 功能分支 → 测试集成分支 → 上线分支。

| 需求类型 | 判断依据 | 基线（从哪拉） | 测试集成分支（Agent 可合） | 上线（Agent 不合） |
|---|---|---|---|---|
| 通用 / 多国 | 禅道标题无国家标签，或标多国 | `origin/{{AP_MAIN_BRANCH}}` | `{{AP_INTEGRATION_BRANCH}}` | 发布负责人以 {{AP_MERGE_ALIAS_OPEN}}分支>` 合入 `{{AP_MAIN_BRANCH}}`，再由 `{{AP_DISTRIBUTE_SCRIPT}}` 分发到 `master_<cc>` |
| 国家专属 | 标题带国家标签，如【{{AP_PROJECT}}-{{AP_CC_UPPER}}】→ {{AP_CC}}、【{{AP_PROJECT}}-{{AP_CC2_UPPER}}】→ {{AP_CC2}} | `origin/master_<cc>` | `{{AP_INTEGRATION_BRANCH}}` | 合入 `master_<cc>`（发布负责人） |
| {{AP_SUBLINE}} | 标题或需求属 {{AP_SUBLINE}} | `origin/{{AP_SUBLINE_BRANCH}}` | `{{AP_SUBLINE_INTEGRATION_BRANCH}}` | `{{AP_SUBLINE_BRANCH}}` |

- 国家码以 `{{AP_DISTRIBUTE_SCRIPT}}` 的 `{{AP_COUNTRIES_VAR}}` 为准（{{AP_COUNTRY_CODES}}）；判断不了国家 → **开工前问用户**，不要默认 `{{AP_MAIN_BRANCH}}`。
- 分支命名：`{{BRANCH_OWNER}}/feature-<禅道号>-<变更名>`（前缀即 `feat new` 用的 `FEAT_BRANCH_OWNER`）。
- 合入测试集成分支用 **merge**（团队惯例；国家分支会把国家提交一起带进 {{AP_INTEGRATION_SHORT}}，属正常）。合并前先 `python3 docs/agents/merge-preview.py HEAD origin/<集成分支>` 预演：冲突分「本次引起」和「基线既有」两类，并逐段给出取哪一侧的建议，一并列给用户。合并在临时 detached worktree 里做，不切换主目录分支（见 finishing-a-development-branch skill）。
- 推送被拒（远端有新提交）→ 先 merge 远端再推，**禁止强推**共享分支。
- `{{AP_MAIN_BRANCH}}` / `master_<cc>` / `{{AP_SUBLINE_BRANCH}}` 是上线分支，Agent 不合、不推。

### 主题切换纪律（会话中途换主题时触发）

**触发**：会话中途要开始与前一项不相关的新主题。

**硬动作**：先 `git status --short`；工作区非空 → **三选一**再动新主题：先收尾 commit（推荐）/ `git stash` 暂存 / `progress.md` 登记搁置。**跨主题文件是红灯**：新主题将改的文件已在脏工作区 → 必须先处理旧主题。

**计时**：新主题与当前禅道任务无关 → 先 `python3 .claude/skills/zentao/scripts/zentao.py pause` 停表，回到原任务再 `start`；否则无关时间会记到当前任务上（#{{AP_TICKET_A}} 曾因此混入约 3 小时）。

**并行多个需求**：每个需求一个 worktree + 一个会话，用 `feat new <禅道号>`（`docs/agents/feat.sh`），不要在同一个目录里来回切分支。各 worktree 的禅道计时、Maven SNAPSHOT 安装天然隔离。

> 完整说明与反例见 [`docs/agents/session.md`](session.md) §主题切换。

### 需求变更检测（所有关联禅道的改动）

禅道需求可能在开发中途被产品修订。`zentao start` 会保存需求快照，以下节点**必须**先跑 `python3 .claude/skills/zentao/scripts/zentao.py check`：

- 写 / 改 proposal、design 之前
- `openspec apply` 开始写代码之前
- 请用户 verify 之前、`finish` 之前

退出码 2 = 需求被改过：把差异原样给用户看、说明对设计 / 已写代码的影响，**停下来等用户决定**；用户确认后 `check --accept` 更新快照。

M/L 的 design.md 按 `openspec/templates/design.template.md` 写，**必须**含「需求对照表」「系统导读（含标出变动点的时序图）」「异常与降级」，有新表 / 缓存 / 消息时含「数据示例」。需求原文对不上的输出一律标「Agent 提议」，用户确认前不写进实现（#{{AP_TICKET_A}} 曾自加「告警列订单号」）。

### 回退与备份

回退未提交的实现（`git checkout --` / 删除新文件）前，先把现场存进 git，**不要只备份到 `/tmp` 或会话临时目录**（会被清理，#{{AP_TICKET_A}} 曾因此丢失第一版实现）：

```bash
git stash push -u -m "backup: <禅道号> <原因>"      # 或
git switch -c backup/<分支名>-$(date +%Y%m%d) && git add -A && git commit -m "backup: ..." && git switch -
```

第二种写法在切回原分支时，改动已经留在备份分支上，原分支工作区随之变干净，等于同时完成了回退。备份分支只留在本地，不推送；回退后在回复里告诉用户备份位置。

### Commit 规则（所有规模适用）

- 实现完成后，Agent **必须停下来等用户 review 并确认通过**，才能执行 `git commit`。禁止在用户未确认前自行 commit 或 push。
- **外科手术式改动**（借鉴 Karpathy 准则）：commit 前 `git diff` 自检，**每一行改动都要能直接对应到用户请求**。发现无关 dead code / 风格不一致 / 可改进点 → **只提不改**（记到 commit message 的 `Notes:` 段或另开 openspec 变更处理）。你自己的改动产生的 orphan import / 未使用变量**必须**随本次 commit 清理；**不属于**你改动范围的既有 dead code 禁止顺手删。

### tasks.md 回填规则（openspec 变更必执行）

用户 verify 通过 → commit 之后 → **在同一次 `git push` 前必须完成** `docs/openspec/changes/<name>/tasks.md` 对应 checkbox 回填。

- commit 与 tasks.md 回填视作**同一个 push 周期的一组操作**，禁止"下次再补"或"跨 push 补"。
- push 前自检：本周期 `git diff --stat` 必须包含对应 change 的 `tasks.md` 变更，否则停下来补勾再 push。
- 若本次 commit 让 `tasks.md` 变为**全勾** → 立即进入「完结」流程，不要留到下一次会话。
- 例外：S 规模改动若未关联任何活跃 change，跳过本规则。

---

## 编码纪律（所有层通用）

> 完整命令速查见 [`附录 A 命令速查`](session.md#命令速查)；本项目 `dev.sh` 已改为本地 Maven 版本，`bash dev.sh help` 查看实际用法。

- **每次修改代码后**：运行 `bash dev.sh check --changed`（编译本分支改动涉及的模块），有错误先修复再继续。
- **每个 task 完成后**：运行 `bash dev.sh test <模块>` 确认测试通过。
- **commit 前必跑**：`bash dev.sh check --arch`——架构硬规则扫描（依赖方向、`@Autowired` 字段注入、业务路径 `RuntimeException`、`new Date()/SimpleDateFormat`）。代码类规则只扫本分支相对**基线分支**新增的 Java 文件；基线为 0 命中，任何输出即回归。
- **基线分支**：`dev.sh` 自动在 `origin/{{AP_MAIN_BRANCH}}`、`origin/master_<cc>`、`origin/{{AP_SUBLINE_BRANCH}}` 中选离 HEAD 最近的一个（输出首行 `[base]` 可见）；识别错了用 `BASE_REF=origin/master_xx bash dev.sh ...` 指定。
- **JDK**：项目要求 Java 8，已装在 `~/.local/jdk8`（Temurin），`dev.sh` 自动使用；系统默认 java 是 25，不要直接裸跑 `mvn`。
- **编译前置**：`check --changed` / `compile` 会先用本分支源码 `install` 一次 `{{AP_MOD_API}}`（避免 `~/.m2` 里别的分支装的旧 API jar 导致假报错，首次约 5 分钟）；确认 API 层没变时可加 `SKIP_API_INSTALL=1` 提速。
- **需要运行验证时**：本地 `cd <服务目录> && mvn spring-boot:run`，检查日志确认启动成功。
- **细化规则**：后端看 `BACKEND_RULES.md`——本文件只放流程，不重复编码细则。
- **简洁优先**（借鉴 Karpathy 准则）：不加**没被要求**的功能 / 抽象 / 配置项 / 错误处理；单次使用不抽象组件或 helper；能 50 行写的不写 200 行。**例外**：基础设施层 / API 契约层 / 明确声明的扩展点（如 Skills / Starter Kit 模板）。

---

## Verify（三阶段，缺一不可）

**契约摘要**（完整 SOP → [`docs/agents/verify.md`](verify.md)）：

- **阶段一 · Agent 自验**：`check --changed` + `check --arch` + `test` + **可观察证据四选一**（curl / 日志 / DB 记录 / 单测断言）。自验失败不得进入阶段二。
- **阶段二 · 用户验证**：Agent 出示「实现摘要 + 测试结果 + 证据清单」后**停下来**，等用户明确说"通过"才能 commit。
  - 测试环境操作（查库自测、改 Nacos、建 / 启停 xxl-job、按国家发版）走 `env-config` skill：库默认只读、Nacos 带备份和 CAS、写操作记 `~/.cache/apollo-env/ops.log`。
  - 测试环境证据：能连上时，用 `jenkins-deploy` 发测试环境 + `apollo-logs` 按需求里的日志关键字（如 `{{AP_CC}} {{AP_LOG_KEYWORD}}`）查 SLS，把查到的日志作为证据给用户，用户只需确认；MCP（aliyun-observability）连不上就明确告知并改为用户手验。
- **超时 Fallback**：用户不回应时**不 stash、不 commit**，只更新 `.harness/progress.md` 后停手。
- **数据卫生**：测试数据必须带 `__agent_verify_` 前缀；`drop/truncate/reset` 前必须确认当前数据源（配置在 Nacos，仅个人/开发库可 reset，其他环境禁止）。

---

## 完结（就地，不搬目录）

完整 SOP → [`docs/agents/archive.md`](archive.md)。

团队惯例：openspec 变更留在 `docs/openspec/changes/<name>/`，**不移动、不跑 `openspec archive`**（2026-10-30 起；此前唯一一次搬目录归档的是 `docs/plans/archive/2026-10-30-{{AP_CC}}-{{AP_ARCHIVED_CHANGE}}/`，保持不动）。

**触发**：`tasks.md` 全部达合法终态（`[x]`/`[~]+理由`，`[ ]` 禁止完结）+ 用户确认 + 代码已推送并合入测试集成分支。  
**动作**：在变更目录内写 `TRACE.md`（追溯元数据 + 偏差 + 后续待办）→ 和最后一次 tasks 回填一起提交、推送、合入测试集成分支。  
**每次 push 后**主动问用户"是否还有任务，否则完结"。

---

## 会话管理

完整 SOP → [`docs/agents/session.md`](session.md)。

**启动 7 步（顺序强制）**：① 工作区体检（`git status`，非空三选一）② 读本文件 ③ 读 `.harness/progress.md` ④ 扫 `.learnings/LEARNINGS.md` 索引 ⑤ `cd docs && openspec list` ⑥ 启动体检（tasks/代码对账）⑦ Learnings 密度扫（tag ≥ 3 立刻晋升）

**openspec CLI**：变更在 `docs/openspec/`，所有 `openspec` 命令都在 `docs/` 目录下执行（`cd docs && openspec status --change <name>`），在仓库根目录执行只会看到根 `openspec/changes/` 下的 4 个旧变更。

> **扫读预算**：步骤 ②③④ 合计控制在 ~400 行内，细节按指针下钻。

**结束**：更新 `progress.md`（做了什么 / 阻塞 / 下次起点 / 未归档 change / 外部阻塞）+ 经验回顾（失败 → `ERRORS.md`；纠正/过时 → `LEARNINGS.md`）。

**Learnings 晋升**：任一 tag ≥ 3 → 首要动作晋升进本文件 / `*_RULES.md`，原条目追加 `→ PROMOTED to <target> on YYYY-MM-DD`。

---

## 关键目录

| 路径 | 说明 |
|------|------|
| `BACKEND_RULES.md` | 编码规则（**改代码前必读**）；**模块拓扑与依赖方向**在后端规则中维护 |
| `docs/index.json` | 知识库根索引（架构 / 业务 / 表结构文档，按上文「导航流程」读）|
| `docs/openspec/changes/` | 团队 openspec 变更（proposal / design / specs / tasks / TRACE），完结后原地保留 |
| `openspec/` | 根目录旧变更（4 个）+ 本地模板 `templates/`；新变更不放这里 |
| `docs/agents/workflow.md` | 本文件：本地 Agent 流程（经 `CLAUDE.local.md` 自动加载，不进仓库）|
| `{{AP_DISTRIBUTE_SCRIPT}}` | `{{AP_MAIN_BRANCH}}` → 各国 `master_<cc>` 的分发脚本（分支规则依据）|
| `.claude/skills/` | Agent 技能唯一源 |
| `.harness/progress.md` | 跨会话进度 |
| `.learnings/` | 经验沉淀（ERRORS / LEARNINGS / FEATURE_REQUESTS）|

---

## 规则变更历史

见 [`docs/agents/rules-history.md`](rules-history.md)。Agent 新会话无需读取——规则的当前有效状态即本文档正文。
