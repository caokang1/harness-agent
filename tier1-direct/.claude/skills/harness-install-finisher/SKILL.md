---
name: harness-install-finisher
description: "Use when a user just ran harness-starter init.sh and needs to complete the remaining 🔴 customization fields automatically. Trigger on phrases like 'complete harness-starter install', 'finish harness starter setup', '完成 harness-starter 安装收尾', '装完 harness 帮我配完剩下的', '跑一下 harness-install-finisher'. This skill auto-fills code-scannable fields and AskQuestion for product-semantic ones."
---

# Harness Install Finisher

## 定位

**一次性**的「装完 starter → 可以 commit」最后一公里 skill。

**我是**：把 `CUSTOMIZE.md` 的 🔴 必改项全部填完的自动化工具。
**我不是**：日常开发的 harness 编排入口（那是 `harness-orchestrator` 的职责）。

### 与 `harness-orchestrator` 的区别

| skill | 生命周期 | 职责 |
|-------|---------|------|
| **harness-install-finisher（本 skill）** | 一次性（装完就功成身退） | 填 🔴 字段、跑 `check --arch` 基线、交付"可 commit 状态" |
| **harness-orchestrator** | 常驻（每个新需求都用） | brainstorm → openspec → verify → archive 全流程编排 |

---

## 前置条件检查（如果不满足，报错拒绝触发）

在执行任何动作前：

1. **必须存在**：`.harness-starter-applied.log`
   - 不存在 → 报错：「未检测到 `.harness-starter-applied.log`。本 skill 只在刚跑完 `init.sh` 的仓库里生效。请先跑 `bash init.sh --auto` 或等效命令。」
   - 文件修改时间超过 **24 小时** → 警告：「`.harness-starter-applied.log` 已经是 X 小时前的文件，你确定现在还是"刚装完"状态吗？继续可能会覆盖你已经手改过的字段。回答 `yes` 继续 / `no` 中止。」
2. **必须存在**：`AGENTS.md` / `BACKEND_RULES.md` / `FRONTEND_RULES.md` / `dev.sh` / `docker-compose.dev.yml` / `CUSTOMIZE.md`
   - 任一缺失 → 报错：「缺少 `<file>`，安装可能不完整。请排查 init.sh 的输出。」

---

## 执行流（严格 checklist · 用 TodoWrite 跟踪）

### Step 1 · 体检 & 加载上下文

```
读 .harness-starter-applied.log → 记录：
  - PROJECT_NAME / TECH_STACK / MODULES / BACKEND_PACKAGE / FRONTEND_DIR
读 CUSTOMIZE.md → 提取所有 🔴 必改项作为 TodoWrite todo list
```

### Step 2 · 扫项目代码补齐扫描维度

用户跑 `init.sh --auto` 已扫过 7 个结构字段。本 skill 补扫：

```
- 模块间依赖（扫各模块 build.gradle 的 implementation project(':...')）
- @Entity 类列表（verify-snapshot 表候选）
- Flyway/Liquibase migration 文件（另一路表候选）
- src/views/* 的子目录（前端 domain 候选）
- 所有模块的 src/main/java 绝对路径（run_arch_check 规则路径）
```

### Step 3 · 逐项执行 [AUTO] 或 [ASK]

**对每个 🔴 必改项**：

#### [AUTO] 代码可客观扫出，直接填

| 目标文件 | 字段 | 填法 |
|---------|------|------|
| `BACKEND_RULES.md` | §模块依赖方向（占位图 / 分层说明） | 从 Step 2 扫各模块 `implementation project(':...')` 生成 ASCII 摘要；**拓扑只维护在后端规则**（AGENTS.md 保持精简，不重复维护拓扑） |
| `BACKEND_RULES.md` | DTO 包路径 | `{BACKEND_PACKAGE}.{module}.dto` 模板 |
| `dev.sh` | docker 服务名 | `{PROJECT_NAME}-dev` 替换占位 |
| `dev.sh` | 启动成功关键字 | `Started {AppMainClass}` |
| `dev.sh` | `run_arch_check` 模块路径 | Step 2 扫到的绝对路径列表展开 |
| `docker-compose.dev.yml` | 服务名 / main 模块引用 | 从 `PROJECT_NAME` + `MODULES` 推 |
| `harness-orchestrator/SKILL.md` | `{{PROJECT_NAME}}` | 直接替换 |

**AUTO 的操作约定**：
1. 每次填之前 `Read` 目标文件确认占位符（如 `{{...}}` 或"示范内容"）还在
2. 已被用户手改过 → 跳过 + 记录到"用户已手改清单"
3. 用 `StrReplace` 做替换，**绝不用 `sed`** 做多行复杂替换

#### [ASK] 产品语义，AskQuestion 一次一项

| 目标文件 | 字段 | 启发式预填 + 问法 |
|---------|------|-----------------|
| `BACKEND_RULES.md` | **业务/基础模块分类** | 启发式：`common` / `auth` / `infra` / `shared` / `core` 命名归"基础"，其他归"业务"；用 AskQuestion 的 multi-select + allow_multiple 让用户微调 |
| `FRONTEND_RULES.md` | **domain 列表** | 扫 `{FRONTEND_DIR}/src/views/*` 列所有候选，用 AskQuestion multi-select 让用户勾选 3-5 个真正有跨域约束的 |
| `dev.sh` | **verify-snapshot 关键业务表** | 聚合 Step 2 的 `@Entity` + migration 里的所有表名，用 AskQuestion multi-select（`allow_multiple=true`），让用户勾选 5-15 张业务关键表 |
| `AGENTS.md` | **项目简介段** | 3 问：「是什么？」「给谁用？」「当前状态？」（单独 3 条 AskQuestion 也可合并成一次收集） |
| `harness-orchestrator/SKILL.md` | `{{ENTRY_HOOK}}` | 给 3 个示例（功能需求 / bugfix / 性能优化）让用户选触发姿势，或手写 |

**ASK 的节奏约定**：
- 一次只问一个字段（对齐 `brainstorming` skill 的节奏）
- 预填值就是"启发式猜的答案"，用户按回车即接受
- 用户输入明显不合理（例如 `domains` 勾 > 10 个）→ 提醒 + 让重选

### Step 4 · 跑 arch 基线

```bash
bash dev.sh check --arch
```

- **通过** → 进入 Step 5
- **不通过** → 展示违规清单，二选一协助用户：
  - 改代码到合规
  - 在 `dev.sh` 注释掉不适用的规则 + 在 `BACKEND_RULES.md` 对应段加「已禁用：<理由>」

### Step 5 · 输出总结（不 commit）

输出结构化总结：

```
====== Harness 安装收尾完成 ======

[AUTO 自动填了 X 项]
  ✅ BACKEND_RULES.md 模块分层/依赖摘要
  ✅ dev.sh 启动成功关键字 = "Started MyApp"
  ...

[ASK 用户确认了 Y 项]
  ✅ BACKEND_RULES.md 业务模块 = [market, skills]
  ✅ FRONTEND_RULES.md domains  = [market, skills, admin]
  ...

[用户已手改跳过 Z 项]
  ⏭  AGENTS.md 项目简介段（已有内容，未覆盖）

[check --arch 基线]
  ✅ 全部通过 / ❌ 3 条违规需要修

下一步：
  1. git diff 看一眼本次改动
  2. git add . && git commit -m "chore: 应用 harness-starter 配置（v{VERSION}）"

此 skill 使命完成。后续请用 harness-orchestrator。
```

---

## 安全阀（严格遵守）

| 规则 | 做法 |
|------|------|
| **修改前必 Read** | 所有 AUTO 填写前先 Read 目标文件，确认占位符还在；用户已手改则跳过 |
| **AskQuestion 不塞多问题** | 一次只问一个字段（违反会让用户懵）|
| **绝不 commit** | 末尾只给 commit message 建议，`git add` / `git commit` 都让用户自己跑 |
| **大改动前 stash** | 如果要批量改 `dev.sh`（> 20 行 diff），先 `git stash push -m "finisher-auto-<timestamp>"`，失败可 `pop` |
| **不碰 .harness-starter-applied.log** | 这是"已装完"的凭据，finisher 只读不写 |

---

## 退场

- skill **不物理删除**，保留作为「这个仓库是 harness 起源」的留档
- 后续用户若要大规模改造（加模块 / 换启动类），可以再次手动调起本 skill 二次补全
- 但常规场景下，装完一次之后**不应再自动触发**——靠 `.harness-starter-applied.log` 是否存在 + 24h 时间窗守住

---

## Anti-Patterns（别干的事）

- ❌ **不要**跳过前置条件检查直接开始扫描——可能误触发在已经手改过多次的项目上
- ❌ **不要**把 AUTO 和 ASK 混成一次批量填——分开才能让用户 review 自动部分、交互补充语义部分
- ❌ **不要**用 `sed` 做多行替换——`StrReplace` 更可靠；`sed` 只用于 `init.sh` 那种单行占位符
- ❌ **不要**代用户 commit——即使 check --arch 全部通过。用户 review 才是最终关卡
- ❌ **不要**在未装完 starter 的项目上跑——前置条件检查就是为了挡这个

---

## 典型一次运行的时间预算

| 步骤 | 预期时间 |
|------|---------|
| Step 1 体检 + 加载 | < 5s |
| Step 2 扫项目 | 10-30s（项目越大越长）|
| Step 3 AUTO 部分（~8 项）| 15-30s |
| Step 3 ASK 部分（~5 项）| 60-120s（取决于用户思考速度）|
| Step 4 check --arch | 5-10s |
| Step 5 总结 | < 5s |

**合计**：干净项目 1.5-3 分钟（符合 v2 「3 分钟可 commit」设计目标）。
