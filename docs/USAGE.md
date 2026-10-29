# Harness Starter Kit 使用文档

本文档覆盖从安装到日常使用、卸载的全过程。只想快速装上，看 [README](../README.md) 的"快速开始"即可。

- [1. 概念：装进项目的是什么](#1-概念装进项目的是什么)
- [2. 安装](#2-安装)
- [3. 安装参数](#3-安装参数)
- [4. 安装后收尾](#4-安装后收尾)
- [5. 日常开发流程](#5-日常开发流程)
- [6. dev.sh 命令](#6-devsh-命令)
- [7. 架构检查规则](#7-架构检查规则)
- [8. 可选 skill](#8-可选-skill)
- [9. 卸载](#9-卸载)
- [10. 团队自建分发（可选）](#10-团队自建分发可选)
- [11. 常见问题](#11-常见问题)

---

## 1. 概念：装进项目的是什么

起步包本身是一个目录树，`init.sh` 把其中的文件**复制**到你的项目根目录，并按你的项目填好占位符。复制完就结束了：没有常驻进程，不需要和本仓库保持同步，装进去的文件就是你仓库的一部分。

安装后项目里会多出：

| 路径 | 内容 |
|---|---|
| `AGENTS.md` | AI 代理的入口规则：开发流程、提交规则、验证要求 |
| `BACKEND_RULES.md` | 后端编码规则（模块依赖方向、依赖注入、异常、时间类型等） |
| `FRONTEND_RULES.md` | 前端编码规则（纯后端项目不安装） |
| `CUSTOMIZE.md` | 还需要你按项目改的字段清单 |
| `dev.sh`、`docker-compose.dev.yml` | 开发容器、编译、测试、日志、架构检查 |
| `.env` | 开发容器的环境变量（项目里原来没有时才建，只有注释） |
| `.claude/skills/` | 20 个方法论 skill，加上你选装的可选 skill |
| `docs/agents/` | 会话管理、验证、交叉评审、归档的操作规程 |
| `.learnings/` | 经验沉淀模板（错误、纠正、最佳实践） |
| `openspec/templates/` | 需求变更文档模板：proposal / design / tasks / TRACE |
| `.harness-starter-applied.log` | 本次安装用的参数和放置的文件 |
| `.harness-starter-manifest` | 安装清单，卸载时只删清单里的文件 |

**已经存在的同名文件不会被覆盖**，安装时会提示"已存在，跳过"，占位符替换也不会碰它们。

## 2. 安装

所有方式效果相同，最终都会在你的项目根目录运行 `init.sh`。

### 方式一：一行命令（推荐）

```bash
cd /path/to/your-project
bash <(curl -fsSL https://raw.githubusercontent.com/caokang1/harness-agent/main/bootstrap.sh) --auto
```

`bootstrap.sh` 把本仓库浅克隆到系统临时目录，运行 `init.sh`，结束后（包括出错、按 Ctrl+C）自动删除临时目录。

固定版本：

```bash
HARNESS_STARTER_REF=<标签、分支或提交号> bash <(curl -fsSL .../bootstrap.sh) --auto
```

指定的版本不存在时会报错退出，**不会**悄悄改装默认分支。也可以用 `HARNESS_STARTER_REPO` 指向你 fork 的仓库。

### 方式二：先克隆、审阅，再安装

适合需要先看清会写入哪些文件，或者想改一两条模板再装的情况：

```bash
cd /path/to/your-project
git clone https://github.com/caokang1/harness-agent.git .harness-starter
# 可选：git -C .harness-starter checkout <提交号>
bash .harness-starter/init.sh --auto
rm -rf .harness-starter
```

### 方式三：没有 git 时下载压缩包

```bash
cd /path/to/your-project
mkdir -p .harness-starter
curl -fsSL https://github.com/caokang1/harness-agent/archive/refs/heads/main.tar.gz \
  | tar -xz --strip-components=1 -C .harness-starter
bash .harness-starter/init.sh --auto
rm -rf .harness-starter
```

把 URL 里的 `refs/heads/main` 换成 `refs/tags/<标签>` 即可固定版本。CI 里请固定版本，否则每次构建拉到的内容可能不同。

## 3. 安装参数

### 自动识别

| 参数 | 作用 |
|---|---|
| `--auto` | 从项目里识别 8 项信息，列出后让你确认或逐项修改 |
| `--auto --yes` | 识别后直接采用，不询问（CI、无人值守） |
| `--auto --dry-run` | 只显示识别结果，不安装 |

优先级：**命令行显式参数 > 自动识别 > 默认值**，可以混用，例如 `--auto --modules=api,core,start`。

### 项目信息

| 参数 | 说明 | 不填时 |
|---|---|---|
| `--project-name` | 项目英文名，用于容器名、文档标题 | 必填（`--auto` 会识别） |
| `--modules` | 后端子模块，逗号分隔，**按依赖从底到顶排列**（见下文"模块分工"） | 必填（`--auto` 会识别） |
| `--tech-stack` | `springboot+vue`，或纯后端 `springboot` | `springboot+vue` |
| `--build-tool` | `gradle` 或 `maven` | 按项目根的构建文件判断：有 Gradle 文件用 gradle，只有 `pom.xml` 用 maven |
| `--backend-package` | Java 顶级包名 | `com.example.app` |
| `--app-main-class` | Spring Boot 启动类名 | `ApplicationStarter` |
| `--frontend-dir` | 前端仓库路径，相对项目根或绝对路径 | `../app-ui` |
| `--backend-port` | 后端端口 | `8080`（`--auto` 会读 `server.port`） |
| `--frontend-port` | 前端开发服务器端口 | `5173` |
| `--jdk-image` | 开发容器镜像 | Gradle：`gradle:8.12-jdk21`；Maven：`maven:3.9-eclipse-temurin-21` |
| `--project-desc` | 项目一句话简介，写进 `AGENTS.md` | 占位文字 |

### 可选 skill

| 参数 | 安装的 skill |
|---|---|
| `--include-frontend-design` | `frontend-design`、`ui-ux-pro-max`（前端界面与 UI/UX 设计） |
| `--include-table-lineage` | `table-lineage`（库表血缘分析，需 Python 3.11+） |
| `--include-jenkins` | `jenkins-deploy`（`/jenkins-deploy` 一条命令触发已有的 Jenkins 任务） |
| `--include-zentao` | `zentao`（`/zentao` 读禅道任务 / Bug，累计 AI 工时，确认后完成任务或解决 Bug） |

### 模块分工

`--modules` 的顺序决定每个模块的角色，`dev.sh check --arch` 按角色检查依赖方向：

- **最后一个**是入口模块（放启动类）；
- 其余模块里，前面最多 3 个是**基础模块**，剩下的是**业务模块**（至少留 1 个业务模块）。

| `--modules` | 基础模块 | 业务模块 | 入口模块 |
|---|---|---|---|
| `common,auth,core,order,pay,start` | common、auth、core | order、pay | start |
| `api,core,start` | api | core | start |
| `common,start` | common | （无） | start |

嵌套模块写成目录路径，例如 Gradle 的 `:services:order` 对应 `services/order`。分得不对也没关系，装完改 `dev.sh` 顶部的 `BASE_MODULES` / `BUSINESS_MODULES` 即可。

## 4. 安装后收尾

模板里有些内容只有你清楚，比如业务模块怎么划分、前端有哪些业务域、关键业务表是哪些。两种收尾方式：

**让 AI 收尾（1～3 分钟）**：在 Claude Code 或 Cursor 里打开项目，发送：

> 请用 harness-install-finisher 完成剩余配置

它会扫描代码自动填能推断的字段，向你提问收集只有你知道的字段，再跑一次 `bash dev.sh check --arch` 确认基线，最后给出提交建议（不会替你提交）。

**手工收尾（10～20 分钟）**：查看 `.harness-starter-applied.log`，按 `CUSTOMIZE.md` 里标 🔴 的必改项逐条修改，再运行：

```bash
bash dev.sh check --arch
```

确认无误后提交：

```bash
git add .
git commit -m "chore: 引入 harness-starter"
```

## 5. 日常开发流程

装好后，AI 代理每次进入项目会先读 `AGENTS.md`。核心约定：

**按改动规模走不同流程**（按结构判断，不按工时）：

| 规模 | 判定 | 流程 |
|---|---|---|
| S | 只改一层、不改 API、不加表、不加模块依赖、改动不超过 3 个文件 | 直接编码 → 检查 → 测试 → 等你确认 → 提交 |
| M | 改 API、同时改前后端、加表或字段、加模块依赖、改动超过 3 个文件 | 写变更提案 → 实现 → 交叉评审 → 等你确认 → 归档 |
| L | 新模块、架构调整、全新需求 | 头脑风暴 → 提案 → 独立工作区 → 计划 → 分任务实现 → 评审 → 等你确认 → 归档 |

拿不准时按 M 处理。

**提交规则**：AI 完成实现后必须停下来，出示实现摘要、测试结果和验证证据，**等你明确说"通过"才能提交**。

**每次改代码后**的固定动作：

```bash
bash dev.sh check --changed   # 改完就查
bash dev.sh test              # 每个任务完成后
bash dev.sh check --arch      # 提交前必跑
```

开始一个新需求时，可以直接让 AI "用 harness-orchestrator 处理这个需求"，它会串起头脑风暴、提案、计划、实现、验证、收尾整条流程。

## 6. dev.sh 命令

`dev.sh` 可以在项目里任意目录运行，它会先切到自己所在的项目根目录。

| 命令 | 作用 |
|---|---|
| `bash dev.sh start` | 启动开发容器（后端，以及前端，如有） |
| `bash dev.sh reload` | 让后端加载代码改动。Gradle：编译后由 DevTools 自动重启；Maven：重新构建并重启后端容器（多模块下其他模块以 jar 加载，只编译不生效，所以会慢一些） |
| `bash dev.sh restart` | 完整重启后端容器（改配置、依赖后用） |
| `bash dev.sh compile` | 只编译 |
| `bash dev.sh check` | 编译检查 + 架构规则检查 |
| `bash dev.sh check --arch` | 只跑架构规则检查（不需要容器在运行） |
| `bash dev.sh check --changed` | 只在有改动的 Java 文件时做编译检查 |
| `bash dev.sh check --java` | 只做编译检查 |
| `bash dev.sh test [参数]` | 在容器里跑测试，额外参数原样传给 Gradle / Maven |
| `bash dev.sh logs [be\|fe]` | 查看后端 / 前端实时日志 |
| `bash dev.sh stop` | 停止并删除开发容器 |
| `bash dev.sh verify-snapshot before\|after\|diff` | 验证前后的数据快照（占位实现，按 `docs/agents/verify.md` 自己补全） |

开发容器的环境变量（数据库地址等）写在项目根的 `.env` 里。

## 7. 架构检查规则

`bash dev.sh check --arch` 的基线应当是"全部通过"，之后任何新的违规都算回归，提交前必须处理。

| 规则 | 检查什么 |
|---|---|
| `dep-business-cross` | 业务模块之间不能互相依赖 |
| `dep-base-to-business` | 基础模块不能依赖业务模块，也不能依赖排在它后面的基础模块 |
| `autowired-field-injection` | 不用 `@Autowired` 字段注入，改用构造器注入 |
| `runtime-exception-in-business` | 业务代码不直接抛 `RuntimeException` |
| `legacy-date-api` | 不用 `new Date()` / `SimpleDateFormat`，改用 `java.time` |
| `frontend-cross-domain` | 前端 `src/views/` 下的业务域之间不互相 import |

依赖检查支持 `build.gradle`、`build.gradle.kts` 和 Maven `pom.xml`。

**"跳过"不等于"通过"**：找不到构建文件、源码目录或前端仓库时，对应规则会显示"⚠️ 跳过"，结尾还会提示有几项没真正检查。看到跳过时，请核对 `dev.sh` 顶部的模块和路径配置。

**规则不适用怎么办**：在 `dev.sh` 里注释掉对应检查，并在 `BACKEND_RULES.md` 对应段落写明理由，两处都要留痕。

## 8. 可选 skill

### ui-ux-pro-max（`--include-frontend-design`）

内置 UI 风格、配色、字体、图表、UX 规范和各前端框架的最佳实践数据，AI 做界面时会自动调用。也可以手动查询（在项目根目录运行，需要 Python 3）：

```bash
# 生成一整套设计方案（风格、配色、字体、要避免的做法）
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "saas analytics dashboard" --design-system -p "我的项目"

# 保存成 design-system/MASTER.md，供后续页面统一参照
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "saas analytics dashboard" --design-system --persist -p "我的项目"

# 按领域或技术栈查询
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "animation accessibility" --domain ux
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "form validation" --stack vue
```

### table-lineage（`--include-table-lineage`）

从 Java / Spring / MyBatis 代码加 MySQL 元数据，生成可交互的库表血缘页面：每张表由谁写、从哪些表取数、谁在读、属于哪个业务域，附 ER 图和问题清单。

直接对 AI 说"帮我理清这个项目的报表都是怎么来的"或"做个库表血缘页面"即可触发，AI 会按 skill 里的流程一步步做。要点：

- 工作目录放在代码仓库**外面**，不往你的仓库写文件；
- 元数据可以用 skill 自带的 SQL 在任意数据库客户端导出成 CSV（MySQL 8 导出的大写表头也能识别），也可以配置只读账号直连；
- 账号密码只写在本机的 `db.cnf` 里，不要发到对话中；
- 准确率要用人工核对的标准答案实测，页面会如实标注是否经过测量。

### jenkins-deploy（`--include-jenkins`）

用当前 git 分支触发项目在 Jenkins 上**已有的**任务，不创建也不修改任务。在 Claude Code 里输入一条命令：

```
/jenkins-deploy                              # 用默认任务
/jenkins-deploy team/svc-dev deployEnv=test  # 指定任务和参数
```

AI 会一口气做完下面几步，中间只停一次等你确认：

1. **找任务**：先用命令里指定的；没指定就读仓库根的 `.jenkins-deploy.json`；还没有就按仓库地址自动匹配。
2. **模拟运行**：分支参数填当前分支，标签参数填当前提交上的标签，其他参数用任务默认值。
3. **请你确认**：把任务、参数、远端提交、⚠ 警告和确认码整块发给你。有 ✗ 错误时不能触发，比如分支没推送、参数名拼错。
4. **触发**：你回复"确认"后，用确认码触发。任务、参数或远端提交与确认时有任何不同，都会拒绝触发。
5. **监控**：在后台监控构建，结束后告诉你结果，并发桌面通知。失败不会自动重试，结束监控也不会停止构建。

需要两份配置：

```bash
# ~/.config/jenkins-deploy/config.json —— 个人凭据，不进仓库（chmod 600）
{"url": "https://jenkins.example.com", "user": "<用户名>", "token": "<API Token>"}
# Token：Jenkins 右上角用户名 → Security → API Token
# 默认拒绝 http:// 地址；只能用 http 的内网环境，加 "allow_http": true

# .jenkins-deploy.json —— 放在仓库根目录，可以提交，团队共用
{"job": "team-a/dev/order-service"}
```

只依赖 Python 3.8+ 标准库。离线自测：`python3 .claude/skills/jenkins-deploy/scripts/run_tests.py`。该 skill 改编自 ABCFed/claude-marketplace（MIT License）。

### zentao（`--include-zentao`）

从禅道领任务或 Bug 给 AI 做，做完自动填工时、推进状态。在 Claude Code 里输入：

```
/zentao 123                                   # 任务
/zentao B45                                   # Bug
/zentao http://禅道地址/zentao/task-view-123.html   # 也可以直接贴链接
```

1. **读需求**：任务读描述、关联需求和验收标准；Bug 读重现步骤。
2. **开始**：任务在禅道里标成"进行中"，Bug 不改状态，两者都开始计时。
3. **干活**：按 `AGENTS.md` 的流程实现，修 Bug 时走系统化调试，直到你验证通过、代码提交。
4. **确认工时**：AI 列出每段工作的时间和内容，给出建议工时。你回复"确认"，或者直接回复一个小时数来修改，只问一次。
5. **完成**：任务记工时并标成"已完成"。Bug 标成"已解决"（解决版本"主干"），指派回提 Bug 的人，耗时写进解决备注，因为开源版禅道不能在 Bug 上记工时。

计时只算 AI 在干活的时间。安装时会在 `.claude/settings.json` 里加两个钩子，每轮对话开始和结束时各打一个时间戳。等你回复的时间、关掉会话的时间都不算，跨会话、跨天自动累加。中途切去做别的事时，对 AI 说"暂停计时"。计时记录在 `~/.cache/zentao/`，不进仓库。

账号写在 `~/.config/zentao/config.json`（chmod 600）：

```json
{"url": "http://禅道地址/zentao", "account": "<账号>", "password": "<密码>", "allow_http": true}
```

只能用 http 访问的禅道必须写 `"allow_http": true`，因为密码会明文传输；能用 https 就用 https，并去掉这一项。离线自测：`python3 .claude/skills/zentao/scripts/run_tests.py`。

### render-graphs.js（随 `writing-skills` 安装）

把 skill 文档里的 ```dot 流程图渲染成 SVG，需要安装 Graphviz：

```bash
node .claude/skills/writing-skills/render-graphs.js .claude/skills/test-driven-development
node .claude/skills/writing-skills/render-graphs.js .claude/skills/test-driven-development --combine
```

## 9. 卸载

在项目根目录运行：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/caokang1/harness-agent/main/uninstall.sh) --dry-run   # 先看会删什么
bash <(curl -fsSL https://raw.githubusercontent.com/caokang1/harness-agent/main/uninstall.sh)             # 确认后删除
```

- 只删除安装清单 `.harness-starter-manifest` 里记录的文件，删完再清理因此变空的目录；
- 你原有的文件（包括安装时"已存在，跳过"的那些）、`.claude/` 里你自己的设置和命令都不会动；
- `.env` 只有在仍然只有注释时才删，填过变量的会保留并提示；
- `.harness/` 目录（进度、评审记录）不删，需要的话手动处理。

更早版本安装、没有清单的项目，只会删除 skill 目录、`docs/agents/`、`.learnings/`、`openspec/templates/`；`AGENTS.md` 等顶层文件无法确认归属，只列出来请你自己处理。

## 10. 团队自建分发（可选）

团队内部想用更短的命令安装时，可以把起步包发布到自己的服务上：

**单文件安装包**：`bash scripts/build-installer.sh` 会生成 `dist/install.sh`，里面内嵌全部模板，用户只需 `bash <(curl -fsSL <你的地址>/install.sh) --auto`，不需要 git。复制 `scripts/.env.build.example` 为 `scripts/.env.build` 并填好对象存储（MinIO 等）的地址和密钥后，打包时会自动上传。`.env.build` 已被忽略，不会提交。

**npm 包**：把 `package.json` 里的包名和 `publishConfig.registry` 改成你们的 scope 和源，发布后即可：

```bash
npx --registry=<你的 npm 源> -y <你的包名> --auto
```

Windows 上 npm 入口会自动寻找 Git Bash；找不到时可以用环境变量 `HARNESS_BASH` 指定 bash 路径。

## 11. 常见问题

**项目不是 Spring Boot / Vue 能用吗？**
Tier 1 的 skill 和规程与技术栈无关，可以直接用。`AGENTS.md`、规则文件和 `dev.sh` 以 Java 为例，其他技术栈需要按 `CUSTOMIZE.md` 末尾的指南改检查规则和构建命令。

**项目里已经有 `AGENTS.md` 了怎么办？**
安装会跳过它。可以克隆本仓库，用 `diff -u AGENTS.md <克隆目录>/tier2-template/AGENTS.md` 对比后手动合并。

**只想要 skill，不要 `dev.sh` 和其他文件？**

```bash
git clone --depth=1 https://github.com/caokang1/harness-agent.git /tmp/hs
cp -r /tmp/hs/tier1-direct/.claude .
rm -rf /tmp/hs
```

**安装到一半中断了怎么办？**
临时目录会自动清理，但已经复制到项目里的文件不会撤销。在 git 仓库里用 `git status` 查看，`git clean -fd` 可以清掉未跟踪的新文件（运行前先确认没有你自己的新文件）。

**`dev.sh start` 报找不到 `.env`？**
安装时只在项目里没有 `.env` 时才建空模板。如果之后删掉了，新建一个空的 `.env` 即可。

**识别出的模块或构建工具不对？**
用 `--auto --dry-run` 先看识别结果，再用显式参数覆盖，例如 `--auto --modules=common,core,start --build-tool=maven`。
