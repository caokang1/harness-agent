# Harness Starter Kit

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![bash 3.2+](https://img.shields.io/badge/bash-3.2%2B-4EAA25)
![platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20WSL-lightgrey)
![Claude Code / Cursor](https://img.shields.io/badge/AI-Claude%20Code%20%7C%20Cursor-D97757)

一条命令，把一套 **AI 协作开发规范**装进你的 Java 项目：AI 进项目先读的总规则、编码规则、架构检查脚本，以及 20 个工程方法论 skill。装好以后，AI 会按改动大小走不同的流程，改完先检查、再给你验证，**你确认之前不会提交代码**。

适用于 Claude Code、Cursor 等能读取 `AGENTS.md` 和 `.claude/skills/` 的 AI 编程工具。

## 目录

- [为什么需要它](#为什么需要它)
- [快速开始](#快速开始)
- [装好以后怎么用](#装好以后怎么用)
- [可选 skill](#可选-skill)
- [安装参数](#安装参数)
- [环境要求](#环境要求)
- [卸载](#卸载)
- [工作原理](#工作原理)
- [常见问题](#常见问题)
- [文档](#文档)
- [参与贡献](#参与贡献)
- [致谢](#致谢)
- [许可证](#许可证)

## 为什么需要它

让 AI 写代码很快，但没有约束时经常出现这些情况：

- 改了一半就提交，或者没经过你同意就推送；
- 跨模块乱加依赖，业务代码里到处是字段注入、`new Date()`；
- 改了后端接口，忘了前端；
- 说"已修复"，其实没跑过测试。

这个起步包把一套经过实践的约束直接放进你的仓库，AI 每次进项目都会先读到：

| 装进项目的内容 | 作用 |
|---|---|
| `AGENTS.md` | 总规则：按改动规模（S / M / L）走不同流程，切换主题前先清理工作区，**未经你确认不提交** |
| `BACKEND_RULES.md` / `FRONTEND_RULES.md` | 编码规则：模块依赖方向、构造器注入、异常、时间类型、前端业务域隔离 |
| `dev.sh` + `docker-compose.dev.yml` | 开发容器、编译、测试、日志，以及 `check --arch` 架构规则扫描 |
| `.claude/skills/`（20 个） | 头脑风暴、写计划、TDD、系统化调试、代码评审、完成前验证、OpenSpec 需求变更等方法论 |
| `docs/agents/`、`.learnings/`、`openspec/templates/` | 会话、验证、交叉评审、归档的操作规程，经验沉淀和需求文档模板 |

## 快速开始

**1. 安装。**在你的项目根目录运行：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/caokang1/harness-agent/main/bootstrap.sh) --auto
```

它会自动识别项目信息，列出来让你确认后再安装。安装在临时目录里完成，项目里不会留下起步包本身：

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

**2. 收尾。**模板里有些内容只有你清楚，比如业务模块怎么划分、关键业务表是哪些。在 Claude Code 或 Cursor 里打开项目，发送：

> 请用 harness-install-finisher 完成剩余配置

它会扫描代码自动填能推断的字段，向你提问收集剩下的，最后给出提交建议，不会替你提交。也可以按 [CUSTOMIZE.md](CUSTOMIZE.md) 手工修改，大约 10～20 分钟。

**3. 确认基线。**

```bash
bash dev.sh check --arch
```

结果应当是全部通过，之后任何新的违规都算回归。确认无误后提交：

```bash
git add . && git commit -m "chore: 引入 harness-starter"
```

## 装好以后怎么用

AI 每次进入项目会先读 `AGENTS.md`，按改动的**结构**（不按工时）选择流程：

| 规模 | 判定 | 流程 |
|---|---|---|
| S | 只改一层，不改接口、不加表、不加模块依赖，改动不超过 3 个文件 | 编码 → 检查 → 测试 → 等你确认 → 提交 |
| M | 改接口、前后端都改、加表或字段、加模块依赖、改动超过 3 个文件 | 写变更提案 → 实现 → 交叉评审 → 等你确认 → 归档 |
| L | 新模块、架构调整、全新需求 | 头脑风暴 → 提案 → 独立工作区 → 计划 → 分任务实现 → 评审 → 等你确认 → 归档 |

拿不准时按 M 处理。几个常用的说法：

| 你想做的事 | 对 AI 说 |
|---|---|
| 从头处理一个新需求 | "用 harness-orchestrator 处理这个需求：……" |
| 先想清楚再动手 | "先头脑风暴一下：……" |
| 排查一个 bug | "系统化调试这个问题：……" |
| 用 Jenkins 构建 / 发布 | `/jenkins-deploy`（需要安装时加 `--include-jenkins`） |
| 做禅道上的任务或 Bug | `/zentao 123`、`/zentao B45`（需要安装时加 `--include-zentao`） |

`dev.sh` 的常用命令：

```bash
bash dev.sh start            # 启动开发容器
bash dev.sh check --changed  # 改完代码就查
bash dev.sh test             # 每个任务完成后跑测试
bash dev.sh check --arch     # 提交前必跑的架构检查
```

完整命令和每条架构规则的说明见 [使用文档](docs/USAGE.md#6-devsh-命令)。

## 可选 skill

默认不装，安装时加对应参数：

| 参数 | 安装的 skill | 做什么 | 额外需要 |
|---|---|---|---|
| `--include-frontend-design` | `frontend-design`、`ui-ux-pro-max` | 生产级前端界面设计；UI/UX 风格、配色、字体的检索和设计方案生成 | Python 3 |
| `--include-table-lineage` | `table-lineage` | 从 Java / MyBatis 代码加 MySQL 元数据生成库表血缘页面，准确率用人工标准答案实测 | Python 3.11+ |
| `--include-jenkins` | `jenkins-deploy` | `/jenkins-deploy` 一条命令：按当前分支触发已有的 Jenkins 任务，给你确认后才触发，并在后台监控结果 | Python 3.8+ |
| `--include-zentao` | `zentao` | `/zentao 编号`：读禅道任务或 Bug，自动累计 AI 工作时间，你确认工时（任务还会按你的习惯推荐指派人）后完成任务或解决 Bug | Python 3.8+ |

连接外部系统的 skill（Jenkins、禅道）有几条共同的安全约定：

- 凭据只放在你用户目录下的配置文件里，权限 600，不进项目仓库；
- 默认拒绝明文 HTTP，需要你在配置里明确允许；
- 写操作先预览，凭确认码执行，内容和你确认的不一致就拒绝执行。

各 skill 的配置和用法见 [使用文档 · 可选 skill](docs/USAGE.md#8-可选-skill)。

## 安装参数

```bash
B=https://raw.githubusercontent.com/caokang1/harness-agent/main/bootstrap.sh

bash <(curl -fsSL $B) --auto --dry-run          # 只看识别结果，不安装
bash <(curl -fsSL $B) --auto --yes              # 不询问，直接采用识别结果（CI 用）
bash <(curl -fsSL $B) --auto --modules=common,core,start --build-tool=maven   # 识别不准时手动指定
bash <(curl -fsSL $B) --auto --include-jenkins --include-zentao              # 同时加装可选 skill
```

- 想先审阅源码、固定到某个版本，或者机器上没有 git，见 [INSTALL.md](INSTALL.md)。
- 全部参数见 [使用文档 · 安装参数](docs/USAGE.md#3-安装参数)。
- 团队想自建分发（单文件安装包、npm 私有源），见 [使用文档 · 团队自建分发](docs/USAGE.md#10-团队自建分发可选)。

## 环境要求

| 用途 | 需要 |
|---|---|
| 安装 | `bash` 3.2 及以上、`git`、`curl` |
| `dev.sh` | Docker 与 Docker Compose（`check --arch` 架构检查不需要） |
| M / L 规模的流程 | [OpenSpec](https://github.com/Fission-AI/OpenSpec) 命令行工具：`brew install openspec` 或 `npm install -g @fission-ai/openspec`，装好后在项目里运行 `openspec init` |
| 支持的项目 | Spring Boot（Gradle 或 Maven，单模块或多模块），可带 Vue 前端，纯后端也支持 |
| 可选 skill | 见上面的[可选 skill](#可选-skill) 表 |

Windows 上请在 WSL 或 Git Bash 里运行。

## 卸载

```bash
U=https://raw.githubusercontent.com/caokang1/harness-agent/main/uninstall.sh
bash <(curl -fsSL $U) --dry-run   # 先看会删什么
bash <(curl -fsSL $U) --yes
```

安装时会记一份清单 `.harness-starter-manifest`，卸载只删清单里的文件。你原有的 `AGENTS.md` 等文件安装时就会跳过，卸载时也不会动；装好后你又改过的文件，卸载时会保留并列出来，由你决定是否删除。装过 `zentao` 的，会从 `.claude/settings.json` 里移除它添加的两个计时钩子，其余配置原样保留。

## 工作原理

起步包按"能复用多少"分三层：

| 层 | 复用程度 | 安装时怎么处理 |
|---|---|---|
| Tier 1 | 与项目无关 | 原样复制 |
| Tier 2 | 骨架通用，需要填空 | 替换占位符，再按 `CUSTOMIZE.md` 微调 |
| Tier 3 | 每个项目自己写 | 不在本包内，`CUSTOMIZE.md` 末尾给了写法指南 |

```
├── bootstrap.sh / init.sh / uninstall.sh   安装、初始化、卸载
├── bin/cli.js、package.json                 npm 入口（团队自建 npm 源时用）
├── scripts/                                 项目识别、单文件安装包打包
├── tier1-direct/                            Tier 1：原样复制
│   ├── .claude/skills/                      20 个方法论 skill
│   ├── docs/agents/                         会话 / 验证 / 交叉评审 / 归档规程
│   ├── .learnings/                          经验沉淀模板
│   └── openspec/templates/                  需求变更文档模板
├── tier1-direct-optional/.claude/skills/    可选 skill
├── tier2-template/                          Tier 2：AGENTS.md、规则文件、dev.sh 等模板
└── docs/                                    使用文档、设计说明
```

它**不是**常驻服务：安装是一次性复制，装完的文件就是你仓库的一部分，可以随意修改，不需要和本仓库同步。它也**不是**项目脚手架，不生成业务代码。

## 常见问题

**项目不是 Spring Boot / Vue 能用吗？**
Tier 1 的 skill 和规程与技术栈无关，可以直接用。`AGENTS.md`、规则文件和 `dev.sh` 以 Java 为例，其他技术栈按 [CUSTOMIZE.md](CUSTOMIZE.md) 末尾的指南调整。

**项目里已经有 `AGENTS.md` 了？**
安装会跳过已存在的文件。可以用 `diff` 对比本仓库的 `tier2-template/AGENTS.md` 后手动合并。

**识别出的模块或构建工具不对？**
先用 `--auto --dry-run` 看识别结果，再用显式参数覆盖，例如 `--modules=common,core,start --build-tool=maven`。

更多问题见 [使用文档 · 常见问题](docs/USAGE.md#11-常见问题)。

## 文档

| 文档 | 内容 |
|---|---|
| [docs/USAGE.md](docs/USAGE.md) | 完整使用文档：安装、参数、日常流程、`dev.sh`、架构规则、可选 skill、卸载 |
| [INSTALL.md](INSTALL.md) | 安装细节和降级方案（克隆后安装、没有 git 时安装） |
| [CUSTOMIZE.md](CUSTOMIZE.md) | 安装后要改哪些字段，以及非 Java 技术栈的改造指南 |
| [docs/design.md](docs/design.md) | 给维护者看的设计决策 |

## 参与贡献

欢迎提 [Issue](https://github.com/caokang1/harness-agent/issues) 和 Pull Request。本地验证方法、提交前自检清单，以及新增可选 skill 要同步修改的地方，见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 致谢

部分 skill 改编自以下开源项目，感谢原作者：

- [obra/superpowers](https://github.com/obra/superpowers)：14 个工程方法论 skill（MIT）
- [Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec)：OpenSpec 需求变更 skill（MIT）
- [anthropics/skills](https://github.com/anthropics/skills)：frontend-design（Apache 2.0）
- [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)：ui-ux-pro-max（MIT）
- [ABCFed/claude-marketplace](https://github.com/ABCFed/claude-marketplace)：jenkins-deploy 的原型（MIT）

各项目的版权和许可证声明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 许可证

[MIT](LICENSE) © 2026 caokang1
