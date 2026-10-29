# Harness Starter Kit

> 一条命令，把一套 **AI 协作开发规范**装进你的 Java 项目：AI 代理的工作流程、编码规则、架构检查脚本和 20 个工程方法论 skill。
> 适用于 Claude Code、Cursor 等能读取 `.claude/skills/` 和 `AGENTS.md` 的 AI 编程工具。

- **完整使用文档**：[docs/USAGE.md](docs/USAGE.md)
- 安装细节与降级方案：[INSTALL.md](INSTALL.md)　·　安装后要改哪些字段：[CUSTOMIZE.md](CUSTOMIZE.md)

---

## 它解决什么问题

让 AI 写代码很快，但没有约束时容易出现：改一半就提交、跨模块乱依赖、改了后端忘了前端、说"已修复"却没验证。这个起步包把一套经过实践的约束直接放进仓库：

| 装进项目的内容 | 作用 |
|---|---|
| `AGENTS.md` | AI 进项目先读的总规则：按改动规模（S / M / L）走不同流程，**未经人确认不提交** |
| `BACKEND_RULES.md` / `FRONTEND_RULES.md` | 编码规则示例：模块依赖方向、依赖注入、异常、时间类型、前端跨域 import |
| `dev.sh` + `docker-compose.dev.yml` | 开发容器、编译、测试、日志，以及 `check --arch` 架构规则扫描 |
| `.claude/skills/`（20 个） | 头脑风暴、写计划、TDD、系统化调试、代码评审、完成前验证、OpenSpec 需求变更等方法论 |
| `docs/agents/`、`.learnings/`、`openspec/templates/` | 会话 / 验证 / 归档的操作规程、经验沉淀模板、需求文档模板 |

可选再装：前端设计（`frontend-design`、`ui-ux-pro-max`）、库表血缘分析（`table-lineage`）、Jenkins 发布（`jenkins-deploy`：`/jenkins-deploy` 一条命令用当前分支触发已有任务，发送前先让你确认）。

## 快速开始

在你的项目根目录运行：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/caokang1/harness-agent/main/bootstrap.sh) --auto
```

它会自动识别项目名、模块、包名、技术栈、启动类、前端目录、端口和构建工具，列出来让你确认后再安装。安装过程在临时目录里完成，项目里不会留下起步包本身。

```
  1)  ✅  project-name       = my-service
  2)  ✅  modules            = common,auth,core,order,start
  3)  ✅  backend-package    = com.example.myservice
  4)  ✅  tech-stack         = springboot+vue
  5)  ✅  app-main-class     = MyServiceApplication
  6)  ✅  frontend-dir       = ../my-service-ui
  7)  ✅  backend-port       = 8080
  8)  ✅  build-tool         = gradle

确认：[回车] 接受并继续  [数字 1-8] 修改第 N 项  [q] 退出 >
```

装完后二选一：

- **让 AI 收尾（推荐）**：在 Claude Code / Cursor 里打开项目，发送"请用 harness-install-finisher 完成剩余配置"
- **手工收尾**：按 `CUSTOMIZE.md` 改 5～10 个字段

然后跑一次架构检查确认基线：

```bash
bash dev.sh check --arch
```

常用变体：

```bash
bash <(curl -fsSL .../bootstrap.sh) --auto --dry-run              # 只看识别结果，不安装
bash <(curl -fsSL .../bootstrap.sh) --auto --yes                  # 不询问，直接采用（CI 用）
bash <(curl -fsSL .../bootstrap.sh) --auto --include-table-lineage # 加装库表血缘 skill
bash <(curl -fsSL .../bootstrap.sh) --auto --include-jenkins       # 加装 Jenkins 发布 skill
```

不想用一行命令，也可以 `git clone` 下来审阅后再装，见 [使用文档 · 安装](docs/USAGE.md#2-安装)。

## 环境要求

| 用途 | 需要 |
|---|---|
| 安装 | `bash` 3.2 及以上、`git`、`curl` |
| `dev.sh`（开发容器、编译、测试） | Docker 与 Docker Compose |
| 支持的项目 | Spring Boot（Gradle 或 Maven，单 / 多模块），可带 Vue 前端；纯后端也支持 |
| 可选 skill | `ui-ux-pro-max`：Python 3；`table-lineage`：Python 3.11+ |

Windows 上请在 WSL 或 Git Bash 里运行。

## 卸载

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/caokang1/harness-agent/main/uninstall.sh) --dry-run   # 先看会删什么
bash <(curl -fsSL https://raw.githubusercontent.com/caokang1/harness-agent/main/uninstall.sh) --yes
```

安装时会记一份清单 `.harness-starter-manifest`，卸载只删清单里的文件；你原有的 `AGENTS.md`、`.claude/settings.json` 等不会被动到。

## 仓库结构

```
├── bootstrap.sh / init.sh / uninstall.sh   安装、初始化、卸载脚本
├── bin/cli.js、package.json                 npm 入口（团队自建 npm 源时用）
├── scripts/                                 项目识别（detect-project.sh）、单文件安装包打包（build-installer.sh）
├── tier1-direct/                            与项目无关，原样复制
│   ├── .claude/skills/                      20 个方法论 skill
│   ├── docs/agents/                         会话 / 验证 / 评审 / 归档 规程
│   ├── .learnings/                          经验沉淀模板
│   └── openspec/templates/                  需求变更文档模板
├── tier1-direct-optional/.claude/skills/    可选 skill：frontend-design、ui-ux-pro-max、table-lineage、jenkins-deploy
├── tier2-template/                          带占位符、安装时按项目填好
│   ├── AGENTS.md、BACKEND_RULES.md、FRONTEND_RULES.md、CUSTOMIZE.md
│   └── dev.sh、docker-compose.dev.yml
└── docs/                                    使用文档、设计说明
```

三层的复用程度：

| 层 | 复用程度 | 怎么用 |
|---|---|---|
| Tier 1 | 100% 与项目无关 | 安装时原样复制 |
| Tier 2 | 骨架通用，需要填空 | 安装时替换占位符，再按 `CUSTOMIZE.md` 微调 |
| Tier 3 | 每个项目自己写 | 不在本包内；`CUSTOMIZE.md` 末尾给了写法指南 |

## 它不是什么

- **不是常驻服务**：安装是一次性复制文件，装完的文件就是你仓库的一部分，可以随意修改，不需要和本仓库同步。
- **不是项目脚手架**：不会帮你生成业务代码，只放规则、流程和脚本。
- **不是开箱即完美**：`dev.sh` 里的检查规则以 Java 项目为例，其他技术栈需要按 `CUSTOMIZE.md` 调整。

## 反馈

发现某条规则在你的技术栈上不适用，或者识别结果不对？欢迎在 [GitHub Issues](https://github.com/caokang1/harness-agent/issues) 提出。
