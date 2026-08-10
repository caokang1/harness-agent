# Harness Starter Kit

> 把 MCP Gateway 半年沉淀的 Harness 工程实践抽出**可复用部分**，让任何团队 30 分钟内把 AI-first 的开发流水线装到自己项目上。

**仓库地址**：<https://git.example.com/your-group/harness-starter>

---

## 这是什么

一份**目录树形态的起步包**（源码即内容）：带占位符和示范代码的 `tier1-direct/` / `tier2-template/`，由 `init.sh` 铺到你的项目根。它不是 SaaS、不是常驻守护进程。

**三种入口**（任选其一，效果等价）：

| 入口 | 适用场景 |
|------|----------|
| **npm 私库** `npx @your-org/harness-starter` | 内网已配 `npm.example.com`，无需 MinIO / 无需 clone 起步包仓库 |
| **MinIO 单文件** `bash <(curl …) install.sh` | 零依赖、单文件分发（见下文） |
| **git clone + init.sh** | 要审计源码、固定 commit、离线环境 |

装完后：按 `CUSTOMIZE.md` 改少量字段，或在 Cursor 里让 AI 跑 **`harness-install-finisher`** 收尾；再 `bash dev.sh check --arch`，**Harness 工程体系就在你的仓库里跑起来了**。

## 给谁用

- **新仓库从 0 搭 AI 流水线**：直接用，省掉自己摸索 3-6 个月的时间
- **老仓库要补 AI 流水线**：按 Tier 分层逐步引入（先 skill + AGENTS.md，再 dev.sh，最后 OpenSpec）
- **只想拿走某一块**：可以——三层是物理隔离的（见下方）

## 起步包的两层结构

```
harness-starter/
├── README.md              ← 你正在读的文件
├── INSTALL.md             ← 5 步安装指南
├── CUSTOMIZE.md           ← 各文件"必改/选改/可不改"清单
├── init.sh                ← 非交互式初始化脚本（sed 替换占位符）
├── bootstrap.sh           ← 一行零残留安装入口（git clone 版）
├── uninstall.sh           ← 卸载脚本
├── package.json           ← npm 包 `@your-org/harness-starter`（私库 npx 入口）
├── bin/                   ← `harness-starter` CLI → 调 `init.sh`
├── docs/                  ← 维护者文档
│   ├── design.md          ← 这套包为什么这样分层（回答"为什么不用 npm？"等问题）
│   └── plans/             ← 各版本的设计文档（含 brainstorming 产物）
├── scripts/               ← 维护者脚本 + 安装时扫描逻辑
│   ├── build-installer.sh ← 重新打包 install.sh 并上传 MinIO
│   └── detect-project.sh  ← `init.sh --auto` 用的项目结构探测（也打进 install.sh 包内）
│
├── tier1-direct/                   ← 100% 项目无关，cp -r 即用
│   ├── .claude/skills/             ← 19 个通用工程方法论 skill（含一次性安装收尾）
│   │    ├─ using-superpowers / brainstorming / writing-plans / executing-plans
│   │    ├─ verification-before-completion / systematic-debugging
│   │    ├─ receiving-code-review / requesting-code-review
│   │    ├─ openspec-{explore,propose,apply-change,archive-change}
│   │    ├─ test-driven-development / using-git-worktrees
│   │    ├─ dispatching-parallel-agents / subagent-driven-development
│   │    ├─ finishing-a-development-branch / writing-skills
│   │    └─ harness-install-finisher  ← 装完 starter 后填 CUSTOMIZE 🔴 项（一次性）
│   ├── docs/agents/                ← session.md / verify.md / archive.md SOP
│   ├── .learnings/                 ← 索引模板 + 24 类 Tag 词典 + 子文件骨架
│   └── openspec/templates/         ← 四件套模板：proposal/design/tasks/TRACE
│
├── tier1-direct-optional/          ← 可选，需 --include-frontend-design 启用
│   └── .claude/skills/
│       ├─ frontend-design          ← 前端页面/组件/海报设计 skill
│       └─ ui-ux-pro-max            ← UI/UX 设计智能（50 styles / 21 palettes ...）
│
└── tier2-template/                 ← 含占位符，按项目改
    ├── AGENTS.md                   ← 入口契约（{{PROJECT_NAME}} 等）
    ├── BACKEND_RULES.md            ← 6 类常见后端规则示例（Java 风味）
    ├── FRONTEND_RULES.md           ← 跨域 import 等前端规则示例
    ├── dev.sh                      ← 开发脚本骨架（compile/check/reload/test/logs）
    ├── docker-compose.dev.yml
    └── .claude/skills/harness-orchestrator/  ← 项目编排入口（项目特异）
```

> mcp-gateway 上游还有 2 个 skill（`ent-mcp-operate-analysis` / `testCaseWriting-infra-DevOps`）**不进起步包**——它们是 mcp-gateway 特有的业务分析 / 测试基建 skill，没有跨项目复用价值。如果你的项目有类似场景，参考 `CUSTOMIZE.md §F` 的方法论自己写一份。

## 三层复用度分级

| 层级 | 复用程度 | 怎么用 |
|------|---------|-------|
| **Tier 1 · 直接拿来即用** | 100% 项目无关 | `init.sh` 自动把 `tier1-direct/` 铺到项目根 |
| **Tier 2 · 模板 + 占位符** | 骨架可复用，需填空 | 跑 `init.sh` 替换占位符，再按 `CUSTOMIZE.md` 改 5~10 字段 |
| **Tier 3 · 项目自写**（不在本包内）| 0% 文件复用，给方法论 | 见 `CUSTOMIZE.md` 末尾的"自写指南"——例如怎么从事故反推 grep 规则 |

## 30 秒上手（推荐 · `--auto` 零参数自动扫描）

### 方式 A · npm 私库（内网推荐）

```bash
cd /path/to/your-project

# 已把 registry 配进 ~/.npmrc 时可省略 --registry=
npx --registry=https://npm.example.com/ -y @your-org/harness-starter --auto
# 同上：扫 7 个字段 → 交互确认 → 安装
# CI：加 --yes；只看扫描结果：加 --dry-run
# 前端 UI skill：npx … @your-org/harness-starter --auto --include-frontend-design
```

包名：`@your-org/harness-starter`；**请用私库 `latest`（当前 ≥1.1.1）**，含 Gradle 多行 `include 'mod'` 模块扫描修复。

### 方式 B · MinIO 单文件 install.sh

```bash
cd /path/to/your-project

bash <(curl -fsSL https://minio.example.com/your-bucket/harness-starter/install.sh) --auto
# 会自动扫出 project-name / modules / backend-package / tech-stack /
# app-main-class / frontend-dir / backend-port 7 个字段，展示给你确认后继续
#
# CI / 无人值守场景，加 --yes 跳过确认：
# bash <(curl ... install.sh) --auto --yes
#
# 纯后端项目建议：bash <(curl ... install.sh) --auto
# 前端 UI 占比高的项目：bash <(curl ... install.sh) --auto --include-frontend-design
```

> MinIO 上的 `install.sh` 需由维护者执行 `bash scripts/build-installer.sh` 重新打包上传后，才会带上与 Git 主线一致的 `--auto` / `detect-project.sh`。

装完之后：

```bash
# 按 CUSTOMIZE.md 改 5~10 个字段，也可以让 AI 帮你做：
#   在 Cursor / Claude Code 里打开此项目，发送：
#     请用 harness-install-finisher 完成剩余配置
# AI 会基于你项目的实际代码扫字段、逐项填好、跑一次 arch 基线。

# 一条龙检查：
bash dev.sh check --arch
```

### 显式参数路径（CI 固定配置 / 需要精确控制）

```bash
bash <(curl -fsSL https://minio.example.com/your-bucket/harness-starter/install.sh) \
  --project-name="my-awesome-service" \
  --tech-stack="springboot+vue" \
  --modules="api,core,common" \
  --backend-package="com.example.mysvc" \
  --frontend-dir="../my-awesome-service-ui"
```

> 显式参数 > `--auto` 扫描 > 默认值。可以混用——比如 `--auto --modules=api,core`（仅模块用显式，其他字段走扫描）。

**行为**：`install.sh` 是**自包含安装包**——文件内嵌了所有模板内容（base64 tar），无需网络访问 GitLab、无需 `git` 命令，下载一个文件即可完成全部安装。解压到 `mktemp -d` 临时目录后调 `init.sh` 把 `tier1/tier2` 铺到你当前目录，**项目根从头到尾不出现 `.harness-starter/`，也不用手动 `rm -rf`**。

### 备选：`git clone` 直调（想先审计源码 / 固定 commit）

```bash
cd /path/to/your-project
git clone https://git.example.com/your-group/harness-starter.git .harness-starter
# 推荐：零参数扫描（与 MinIO / npx 行为一致）
bash .harness-starter/init.sh --auto
# 或显式参数（同前）
# bash .harness-starter/init.sh --project-name=… --modules=… …
rm -rf .harness-starter
```

完整步骤与降级方案（包括无 `git` 命令时走 `curl | tar`）见 [`INSTALL.md`](./INSTALL.md)。

## 不是什么

- **不是常驻运行时**：`npx @your-org/harness-starter` 只是把模板**一次性**拷进当前仓库；没有长期驻留进程、没有「装在你机器上的服务」。npm 只是**可选分发通道**，核心仍是目录树 + `init.sh`。
- **不是传统「创建项目」脚手架**：`init.sh` / `bootstrap.sh` / npx 包装都是一次性入口，跑完退出；不会在全局注册持续升级的 CLI。
- **不是开箱完美**：6 类 grep 规则示例**基于 Java 项目反推**，其他栈需要按 `CUSTOMIZE.md` 改 grep 模式。
- **不是单元测试套件**：本包不带测试，靠"装上之后跑一次完整 OpenSpec 流程不报错"自验。

## 与 mcp-gateway 上游的关系

本起步包的初版**物理抽自** `mcp-gateway` 主项目对应文件，但已独立仓库化——**独立后两边不自动同步**：

- mcp-gateway 是 starter 的**最初源头**，但不是"主版本"
- mcp-gateway 后续改 skill / 规则 / SOP 时，**不自动**传递到 starter
- starter 的维护者**手动 cherry-pick / 对账**值得带进来的改动（通常是通用性强的方法论更新）
- 反过来 starter 的改动也不自动回传 mcp-gateway

换句话说：独立后各自演进，定期对账，而不是实时镜像。分层与同步策略见 [`docs/design.md`](./docs/design.md)。

## 反馈

发现 starter 里某条规则在你的项目栈不适用？直接在本仓库提 issue / MR：<https://git.example.com/your-group/harness-starter>

我们会在 `CUSTOMIZE.md` 里补一条对应栈的改造指引。
