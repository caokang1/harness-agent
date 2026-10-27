# Harness Starter · 安装体验 v2 设计文档

> **Status**: Design approved, ready for implementation
> **Branch**: `feat/install-experience-v2`
> **Scope**: 三件事打包 · 目录重排（C）+ `init.sh --auto` 扫描（A）+ `harness-install-finisher` skill（B）

---

## 1. 目标与成功标准

### 用户痛点

当前安装流程：

```
一行 curl ... install.sh ...              ← 5 ~ 10 个必填/推荐参数
  ↓
init.sh 铺完 Tier 1 / Tier 2 模板
  ↓
用户读 CUSTOMIZE.md，手工改 🔴 必改字段 15~20 分钟
（涉及 AGENTS.md / BACKEND_RULES.md / FRONTEND_RULES.md / dev.sh /
  docker-compose.dev.yml / harness-orchestrator/SKILL.md 至少 6 个文件）
  ↓
bash dev.sh check --arch → 得到基线
  ↓
git commit
```

**瓶颈**：不是 `init.sh` 本身，而是装完之后的 **15~20 分钟手工 CUSTOMIZE**。新用户没有 harness 上下文的情况下，这一步实际耗时 30~60 分钟。

### 目标

把「init.sh 跑完 → `dev.sh check --arch` 通过 → 准备好 commit」全链路压缩到 **≤ 3 分钟**（1 条命令 + 1 条 AI 消息 + 若干次 AskQuestion 确认）。

### 不做什么（YAGNI）

- ❌ 不做 GUI 安装器（沿袭 `design.md` 已有决策）
- ❌ 不做自动探测 Node/Python/Go 栈（阶段 1 只支持 Java+Vue）
- ❌ 不做多仓库联动装（一次装一个仓库）
- ❌ 不把 `openspec` 引入 starter 仓库本身（这个仓库的定位是装给别人，自己不吃狗粮）

---

## 2. 架构全景

### 三件事的依赖关系

```
[C · 根目录瘦身]
   ↓ 建立 docs/ + scripts/ 清爽基线
[A · init.sh --auto 扫描 + 交互式确认]
   ↓ 产出 .harness-starter-applied.log（记录扫描结果）
[B · harness-install-finisher skill]
   ↓ 消费 applied.log + 扫二次代码 + AskQuestion 补产品语义
   ↓ 完成 CUSTOMIZE.md 🔴 必改项
[用户 verify → dev.sh check --arch 基线跑通 → 首个 commit]
```

### 关键职责分工

| 层 | 扫什么 | 谁来决策 |
|----|--------|---------|
| **A · init.sh** | 结构性字段（项目名 / 模块 / 包名 / 启动类 / 端口 / 前端目录） | `sed` 硬替换 |
| **B · finisher skill** | 业务语义字段（模块分类 / 前端 domain / 关键业务表 / 项目简介） | AI + AskQuestion |

两层**不重叠**：A 只管"怎么装"，B 只管"装完怎么填剩下的空"。

### 改动影响面

| 区域 | 文件数 | 说明 |
|------|-------|------|
| 目录重排（C） | ~5 挪位 + 3 文档改链接 + 1 新 `.gitignore` 条目 | 纯位置变化 |
| init.sh 扫描（A） | init.sh +~150 行 / 新建 `scripts/detect-project.sh` / CUSTOMIZE.md 调整提示 | 新增函数，老参数路径零破坏 |
| finisher skill（B） | 新建 1 个 SKILL.md（放 `tier1-direct`）~300 行 + init.sh 末尾打印改一段 | 纯新增 |
| README/INSTALL 更新 | 2 个文档 | 一次改到位 |

**总计**：~10 个现有文件改动 + 3 个新文件。

---

## 3. 诉求 A · `init.sh --auto` 扫描设计

### 三种调用姿势

```bash
bash init.sh --auto                             # 扫描 + 交互式确认（新用户推荐）
bash init.sh --auto --yes                       # 扫描 + 无脑采用（CI 用）
bash init.sh --project-name=x --modules=y,z     # 老用法完全不变（向后兼容）
```

**优先级**：显式参数 > 扫描结果 > 默认值。允许混用（部分传、部分扫）。

### 扫描的 7 个字段 + 来源

| 字段 | 扫描链（前命中者胜） | 扫不到的 fallback |
|------|-------------------|-----------------|
| `project-name` | `git remote get-url origin` 取仓库名 → `settings.gradle(.kts)` 的 `rootProject.name` → `package.json` 的 `name` → 当前目录名 | **必问用户** |
| `modules` | `settings.gradle(.kts)` 的 `include(':…')` → `pom.xml` 的 `<module>` → 扫一级子目录含 `build.gradle`/`pom.xml` 的目录 | **必问用户** |
| `backend-package` | 扫 `**/src/main/java/**/*.java` 的 `package` 声明取公共前缀 | `com.example.app`（原默认）|
| `tech-stack` | 同时有 `build.gradle`/`pom.xml` + 相邻目录/子目录 `package.json` 含 `vue` → `springboot+vue` | 当前只支持该栈，扫不到报错 |
| `app-main-class` | `rg -l '@SpringBootApplication'` 取文件名 | `ApplicationStarter`（原默认）|
| `frontend-dir` | 按优先级试：`../<project-name>-ui` → `../<project-name>-frontend` → `./frontend` → `./ui`，**验证目录存在** | `../<project-name>-ui`（未验证，占位）|
| `backend-port` | `application-dev.yml` > `application.yml` > `application.properties` 的 `server.port` | `8080` |

### 交互式确认 UI

```
[扫描结果] 基于你的项目推断：

  1) ✅ project-name   = my-svc               ← from git remote
  2) ✅ modules        = api,core,common      ← from settings.gradle
  3) ✅ backend-package= com.example.mysvc    ← from src/main/java 公共前缀
  4) ⚠️  frontend-dir   = ../my-svc-ui         ← 推断（未验证存在）
  5) ❌ app-main-class = (未找到 @SpringBootApplication，用默认 ApplicationStarter)

确认方式：
  [回车] 全部接受并继续
  [数字] 修改第 N 项（例：3 → 手输新值）
  [q]    退出不安装
> _
```

### 代码组织

扫描函数独立成 `scripts/detect-project.sh`（随 C 的目录重排一起建），`init.sh` 通过 `source` 调用。好处：
- `detect-project.sh` 可被未来的 finisher skill 或其他脚本复用
- 便于针对扫描逻辑写单测（bats / shellcheck）
- `init.sh` 不被膨胀

### CI 的 `--yes` flag

保留 `--yes` 免交互，覆盖场景：
- Dockerfile 里预装 starter 到镜像基线
- GitHub Actions / GitLab CI pipeline 里 bootstrap 新项目骨架
- demo 脚本快速生成 sample project

---

## 4. 诉求 B · `harness-install-finisher` skill 设计

### 定位（与 `harness-orchestrator` 区分）

| skill | 生命周期 | 职责 |
|-------|---------|------|
| **harness-install-finisher** | **一次性** | 把 CUSTOMIZE.md 🔴 必改项全部填完，跑 `check --arch` 基线，交付"可 commit 状态" |
| **harness-orchestrator** | **常驻** | 每个新需求的 harness 全流程编排（brainstorm → openspec → verify → archive）|

**放置位置**：`tier1-direct/.claude/skills/harness-install-finisher/SKILL.md`

**触发词**（frontmatter description）严格限定：

> "Use when a user just ran harness-starter init.sh and needs to complete the remaining 🔴 customization fields. Trigger on phrases like 'complete harness-starter install', '完成 harness-starter 安装收尾', or 'finish harness starter setup'."

### 执行流（严格 checklist，TodoWrite 跟踪）

```
1. 体检
   - 读 .harness-starter-applied.log 确认是刚装完状态
   - log 不存在 / 超过 24h → 报错拒绝触发

2. 加载 CUSTOMIZE.md 的 🔴 必改项 → TodoWrite list

3. 逐项分类执行
   [AUTO] 代码可客观扫出 → Read 确认占位符还在 → 直接填 → 记录
   [ASK]  涉及产品语义   → AskQuestion 一次一个 → 填 → 记录

4. 跑 bash dev.sh check --arch 看基线
   - 通过 → 进入 5
   - 不通过 → 展示违规 + 协助修（改代码 or 注释规则）

5. 输出总结
   - 自动填了 X 项 / 用户确认了 Y 项
   - check 状态
   - 下一步：git diff 自检 + commit message 建议（不代执行）

6. 打印：Harness 方法论已就位，此 skill 使命完成，后续请用 harness-orchestrator
```

### AUTO vs ASK 分工清单

**[AUTO]**（代码客观扫出，AI 直接填）：

| 目标文件 | 字段 | 扫描源 |
|---------|------|--------|
| `AGENTS.md` | 模块依赖图 | 扫 `build.gradle` 的 `implementation project(':...')` |
| `BACKEND_RULES.md` | DTO 包路径 | `{backend-package}.{module}.dto` 模板 |
| `dev.sh` | docker 服务名 | `{project-name}-dev` |
| `dev.sh` | 启动成功关键字 | `Started {AppMainClass}` |
| `dev.sh` | `run_arch_check` 模块路径列表 | 每个模块的 `src/main/java` 展开 |
| `docker-compose.dev.yml` | 服务名 / main 模块引用 | 从 project-name + modules 推 |
| `harness-orchestrator/SKILL.md` | `{{PROJECT_NAME}}` | 直接替换 |

**[ASK]**（产品语义，必须 AskQuestion）：

| 目标文件 | 字段 | 扫描辅助 + 问法 |
|---------|------|---------------|
| `BACKEND_RULES.md` | 业务模块 vs 基础模块分类 | 启发式预填：`common` / `auth` / `infra` / `shared` / `core` 命名归"基础"，其他归"业务" → checkbox 给用户调整 |
| `FRONTEND_RULES.md` | domain 列表 | 扫 `src/views/*` 列候选 → 让用户勾选最终 3-5 个 |
| `dev.sh` | `verify-snapshot` 关键业务表 | 扫 `@Entity` + Flyway migration 列全部候选 → 让用户勾选 5-15 张 |
| `AGENTS.md` | 项目简介段 | 纯文字 → 问"这个项目是什么 / 给谁用 / 当前状态"三问 |
| `harness-orchestrator/SKILL.md` | `{{ENTRY_HOOK}}` | 业务特异 → 给 3 个示例让用户改 |

### 安全阀

- **AUTO 前 Read**：每次 AUTO 填之前，Read 目标文件确认占位符还在（防止用户已手改过）
- **AskQuestion 节奏**：一次只问一个字段（对齐 brainstorming skill 节奏）
- **修改前 git stash**：所有修改先打 `git stash push -m "finisher-<timestamp>"`，出错可 `git stash pop` 回滚
- **绝不 commit**：最后一步只**建议** commit message，不代执行，让用户 review 后 `git add . && git commit`

### 退场策略

skill 使命完成后**不物理删除**—— 保留作为：
1. 「这个仓库是 harness 起源」的留档
2. 应对用户未来大规模改造（加模块、换启动类）时二次复用

---

## 5. 诉求 C · 根目录瘦身

### 文件挪动清单

| From | To | 备注 |
|------|----|------|
| `design.md` | `docs/design.md` | 维护者文档 |
| `build-installer.sh` | `scripts/build-installer.sh` | 维护者脚本 |
| `.env.build` | `scripts/.env.build` | `build-installer.sh` 的配置 |
| `.env.build.example` | `scripts/.env.build.example` | 同上 |
| `harness-starter.iml` | **删除** | IDEA 配置，补进 `.gitignore` |

**新增目录**：
- `docs/`（装 `design.md` + `docs/plans/*.md`，即 brainstorming 产物）
- `scripts/`（装维护者脚本）

### 必须更新的链接/引用

- `README.md` 的 `./design.md` → `./docs/design.md`
- `INSTALL.md` / `CUSTOMIZE.md` grep 确认无遗漏引用
- `.npmignore` 新增 `docs/`、`scripts/`、`dist/`（不发 npm 包）
- `scripts/build-installer.sh` 内部的 `$(dirname "$0")/..` 相对路径要改
- `.gitignore` 追加 `*.iml`

### 保持不动的根目录文件

| 文件 | 为什么不动 |
|------|----------|
| `README.md` / `INSTALL.md` / `CUSTOMIZE.md` | 使用方入口文档，被外部链接 |
| `init.sh` | `bin/cli.js` 和 `bootstrap.sh` 都 hardcode `path.resolve(__dirname, '..', 'init.sh')` |
| `bootstrap.sh` | `https://.../raw/main/bootstrap.sh` 是公开 URL |
| `package.json` / `bin/` / `.npmignore` | npm 发布规范 |
| `uninstall.sh` | 跟 `init.sh` 对称，好找 |
| `tier1-direct/` / `tier1-direct-optional/` / `tier2-template/` | 仓库结构就是内容语义，由 `init.sh` 消费 |
| `dist/install.sh` | `build-installer.sh` 的产物，要上传 MinIO |

### 改动后的根目录（11 → 7 顶层条目可见）

```
# 用户入口（3 件套）
README.md  INSTALL.md  CUSTOMIZE.md

# 使用方脚本
init.sh  bootstrap.sh  uninstall.sh

# npm 包
package.json  bin/  .npmignore

# 核心内容（被 init.sh 消费）
tier1-direct/  tier1-direct-optional/  tier2-template/

# 维护者区
docs/  scripts/  dist/
```

---

## 6. 实施计划（四阶段 Commit）

```
Stage 0 · Design 落盘                      ← 本文档
└── commit: "docs: 添加安装体验 v2 设计文档"

Stage 1 · 目录重排（C）
├── git mv design.md docs/design.md
├── git mv build-installer.sh scripts/build-installer.sh
├── git mv .env.build* scripts/
├── rm harness-starter.iml（+ .gitignore *.iml）
├── 改 README.md / INSTALL.md / CUSTOMIZE.md / .npmignore 内部引用
├── 改 scripts/build-installer.sh 相对路径
├── 自验：bash init.sh --help 跑通 / bash scripts/build-installer.sh 能重打包
└── commit: "chore: 重排根目录结构（design.md / build 脚本入 docs/scripts）"

Stage 2 · init.sh --auto 扫描（A）
├── 新建 scripts/detect-project.sh（7 个 detect_* 函数）
├── init.sh 加 --auto / --yes / --dry-run 三个 flag + source detect-project.sh
├── 更新 README.md / INSTALL.md 的快速开始示例
├── 更新 CUSTOMIZE.md（提示：装完后可以跑 finisher skill）
├── 自验：mcp-gateway 副本跑 --auto --yes / 老参数路径跑通
└── commit: "feat: init.sh 新增 --auto 扫描模式，支持零参数自动装"

Stage 3 · finisher skill（B）
├── 新建 tier1-direct/.claude/skills/harness-install-finisher/SKILL.md
├── init.sh 末尾"下一步"打印改造（提示用户去 AI 里跑 finisher）
├── 更新 README.md / INSTALL.md 的「装完之后」章节
├── 自验：干净测试目录跑 --auto → 对 SKILL.md 做 dry-run 手演
└── commit: "feat: 新增 harness-install-finisher skill 自动完成安装收尾"

最终 · 推到远端 + 创建 PR（等用户授权）
```

### 分支策略

单 feature 分支 `feat/install-experience-v2`，四阶段线性 commit，不开 worktree。

### 风险 & 回滚

| 风险 | 回滚方式 |
|------|---------|
| Stage 1 挪错文件 | 单 commit `git revert` |
| Stage 2 扫描 bug | 老显式参数路径 100% 可用作 fallback |
| Stage 3 skill 描述不准确 | 改 SKILL.md，不影响 init.sh |

### 测试策略

用 `mcp-gateway` 的**副本**当白鼠（`git clone` 到 `/tmp` 再跑），避免污染真正的 mcp-gateway 工作区的 rules 和 skill。

---

## 7. 验收清单

- [ ] Stage 1：`bash init.sh --help` 仍能跑 / `bash scripts/build-installer.sh` 能从新位置重打包 / `rm -rf docs/plans dist` 后 npm pack 不包含这些
- [ ] Stage 2：对一个干净的 Java+Vue 项目跑 `bash init.sh --auto --yes`，输出的 `.harness-starter-applied.log` 所有字段都扫对
- [ ] Stage 2：老用户姿势 `bash init.sh --project-name=x --modules=y` 行为与 v1 完全一致
- [ ] Stage 3：`harness-install-finisher` skill 的 description 触发词在装完后的项目里能被 AI 识别
- [ ] Stage 3：按 SKILL.md 走一遍，🔴 必改项全部填完、`dev.sh check --arch` 通过
- [ ] 最终：README / INSTALL 的「30 秒上手」示例跑通无误

---

## 附录 · 未来工作（不在本 change 内）

- 多栈支持（Node / Python / Go）的扫描扩展：`detect-project.sh` 可扩展
- finisher skill 的英文版（`ui-ux-pro-max` 类国际化需求）
- starter 自动升级（当前每次装是 snapshot，没有 `harness-starter upgrade` 命令）
- 配合 GitLab MCP 自动创建 group / project / ci template（跨工具链联动）
