# 安装指南

> 全程 30 分钟内完成。前提：已有一个 git 仓库，装了 `bash`、`git`、`curl`；Docker 只有 Tier 2 的 `dev.sh` 需要。
>
> 更完整的说明（参数、日常使用、卸载）见 [使用文档](docs/USAGE.md)。

---

## 推荐路径 · `--auto` 零参数自动装

```bash
cd /path/to/your-project

bash <(curl -fsSL https://raw.githubusercontent.com/caokang1/harness-agent/main/bootstrap.sh) --auto
# 扫出 8 个字段（project-name / modules / backend-package / tech-stack /
# app-main-class / frontend-dir / backend-port / build-tool）展示后交互确认
#
# 前端占比高的项目再加 --include-frontend-design
```

**扫描界面长这样**：

```
[auto] 扫描项目结构：/path/to/your-project

  1)  ✅  project-name       = my-awesome-service
  2)  ✅  modules            = api,core,common,auth
  3)  ✅  backend-package    = com.example.myservice
  4)  ✅  tech-stack         = springboot+vue
  5)  ✅  app-main-class     = MyAwesomeApplication
  6)  ✅  frontend-dir       = ../my-awesome-service-ui
  7)  ✅  backend-port       = 8080
  8)  ✅  build-tool         = gradle

确认：[回车] 接受并继续  [数字 1-8] 修改第 N 项  [q] 退出 >
```

**三种 `--auto` 的变体**：

| 用法 | 行为 |
|------|------|
| `--auto` | 扫描后进入交互式确认 |
| `--auto --yes` | 扫描后直接采用，不问（CI / 无人值守推荐） |
| `--auto --dry-run` | 只扫描展示，**不**安装（先看看会识别成什么） |

### 显式参数路径（CI 固定配置 / 老用法）

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/caokang1/harness-agent/main/bootstrap.sh) \
  --project-name="my-awesome-service" \
  --tech-stack="springboot+vue" \
  --modules="api,core,common,auth" \
  --backend-package="com.example.myservice" \
  --frontend-dir="../my-awesome-service-ui"
# 前端占比高的项目再加 --include-frontend-design
```

> 显式参数 > `--auto` 扫描 > 默认值。允许混用（部分传、部分扫）。

**这条命令做了什么**：

1. `curl` 把 `bootstrap.sh` 下载到一个**进程流**（不落盘到你项目）
2. `bootstrap.sh` 把本仓库浅克隆到系统临时目录（指定版本用环境变量 `HARNESS_STARTER_REF`，取不到会直接报错，不会改装默认分支）
3. 设 `HARNESS_TARGET_DIR=$(pwd)` 调用 `init.sh`——`init.sh` 把 `tier1/tier2` 的内容铺到你当前目录，并替换占位符
4. 临时目录在结束时（包括出错、Ctrl+C）自动清理
5. **结果**：你的项目根出现 `AGENTS.md` / `dev.sh` / `.claude/` / `.learnings/` / `docs/agents/` / `openspec/templates/`，但**看不到** `.harness-starter/`，也不用自己 `rm -rf`

**前置条件**：`curl` + `bash` + `git`。没有 `git` 的环境用下面的降级 B。

**常用参数**（完整列表见 [使用文档 · 安装参数](docs/USAGE.md#3-安装参数)）：

| 参数 | 含义 | 示例 |
|------|------|------|
| `--project-name` | 项目英文名（用于 docker 服务名、`AGENTS.md` 标题等） | `my-awesome-service` |
| `--tech-stack` | `springboot+vue`，或纯后端 `springboot`（不装前端规则、compose 不含前端服务） | `springboot+vue` |
| `--modules` | 后端 Gradle/Maven 子模块，逗号分隔，**按依赖从底到顶排列**：最后一个是入口模块，其余前面最多 3 个是基础模块，剩下的是业务模块（装完可在 `dev.sh` 顶部调整） | `common,auth,core,market,start` |
| `--build-tool` | `gradle` 或 `maven`；不填按项目根的构建文件自动判断，决定 dev.sh 的编译/测试命令和开发容器镜像 | `maven` |
| `--backend-package` | 后端 Java 顶级包名 | `com.example.myservice` |
| `--frontend-dir` | 前端仓库相对于后端的路径 | `../my-awesome-service-ui` |
| `--include-frontend-design` | 额外装 `frontend-design` / `ui-ux-pro-max` 2 个前端 skill | *（flag，无值）* |
| `--include-table-lineage` | 额外装 `table-lineage` 库表血缘 skill（需 Python 3.11+） | *（flag，无值）* |
| `--include-jenkins` | 额外装 `jenkins-deploy` Jenkins 发布 skill（需 Python 3.8+） | *（flag，无值）* |
| `--include-zentao` | 额外装 `zentao` 禅道 skill，并在 `.claude/settings.json` 加计时钩子（需 Python 3.8+） | *（flag，无值）* |

跑完之后，二选一：

### 🟢 推荐 · 让 AI 帮你配完剩下的（1-3 分钟）

在 Cursor / Claude Code 里打开此项目，发送：

> 请用 harness-install-finisher 完成剩余配置

AI 会：
1. 扫你项目的实际代码，自动填 AGENTS.md 的模块依赖图、dev.sh 启动关键字、docker 服务名等 [AUTO] 字段
2. 用 AskQuestion 收集"业务/基础模块分类""前端 domain 列表""verify-snapshot 业务表"等 [ASK] 字段
3. 跑 `bash dev.sh check --arch` 确认基线
4. 给 commit message 建议（**不代提交**，让你 review）

```bash
# AI 跑完、你 review 过后：
git add .
git commit -m "chore: 引入 harness-starter (Java+Vue 模板)"
```

### 🟡 手工路径（10-20 分钟）

```bash
# 1. 看清单
cat .harness-starter-applied.log

# 2. 按 CUSTOMIZE.md 逐条走 5~10 个项目特异字段

# 3. 首次跑架构检查，确认基线
bash dev.sh check --arch

# 4. 首个 commit
git add .
git commit -m "chore: 引入 harness-starter (Java+Vue 模板)"
```

---

## 降级 A · `git clone` 直调（想先审计源码 / 固定 commit / 离线环境）

```bash
cd /path/to/your-project
git clone https://github.com/caokang1/harness-agent.git .harness-starter
# 想固定到某个 commit：  git -C .harness-starter checkout <sha>
bash .harness-starter/init.sh \
  --project-name="my-awesome-service" \
  --tech-stack="springboot+vue" \
  --modules="api,core,common,auth" \
  --backend-package="com.example.myservice" \
  --frontend-dir="../my-awesome-service-ui"
rm -rf .harness-starter           # 手动清理起步包目录（含它自己的 .git/）
```

**什么时候选这条路**：

- 想在跑 `init.sh` 前先 `cat` 一遍所有模板、看清到底往仓库写了什么
- 审计要求：安装前必须有本地副本 + 固定 commit sha
- 想改一两行 starter 的模板（例如调某条 grep 规则）再装

---

## 降级 B · `curl | tar`（没有 git 命令 / CI 容器）

```bash
cd /path/to/your-project
mkdir -p .harness-starter
curl -fsSL https://github.com/caokang1/harness-agent/archive/refs/heads/main.tar.gz \
  | tar -xz --strip-components=1 -C .harness-starter
bash .harness-starter/init.sh \
  --project-name="my-awesome-service" \
  --tech-stack="springboot+vue" \
  --modules="api,core,common,auth" \
  --backend-package="com.example.myservice" \
  --frontend-dir="../my-awesome-service-ui"
rm -rf .harness-starter
```

**什么时候选这条路**：

- CI 容器里没装 `git`（只有 `curl` + `tar`）
- 网络代理只放行 HTTPS 下载，不放行 git 协议
- 想固定某个标签：把 URL 里的 `refs/heads/main` 换成 `refs/tags/<标签>`

> **私有副本**：如果你把起步包放在自己的私有仓库里，CI 身份不能匿名访问，就在 `curl` 里带上访问令牌，例如 GitHub 用 `-H "Authorization: token <PAT>"`，GitLab 用 `-H "PRIVATE-TOKEN: <PAT>"`。

---

## init.sh 做了什么

无论从哪条路径进来，最终都会调 `init.sh`。它：

1. **复制** `tier1-direct/`（20 个通用 skill + SOP + learnings + 模板）到项目根
2. 按 `--include-frontend-design` / `--include-table-lineage` / `--include-jenkins` / `--include-zentao` 可选复制 `tier1-direct-optional/` 里对应的 skill（`--include-zentao` 另外在 `.claude/settings.json` 加两个计时钩子）
3. **复制** `tier2-template/`（`AGENTS.md` / RULES / `dev.sh` / CUSTOMIZE.md）到项目根
4. 把本次写入的文件里的 `{{PLACEHOLDER}}` 替换为参数值（你原有的同名文件不碰）
5. 给 `dev.sh` 加可执行权限；项目里没有 `.env` 时建一个只有注释的
6. 写入 `.harness-starter-applied.log`（装了什么、哪些参数）和 `.harness-starter-manifest`（安装清单，记录每个文件的校验和；卸载时只删清单里、且安装后没改过的文件）
7. 项目是 git 仓库时，在 `.gitignore` 里加一行 `.harness/`（本地进度和评审记录不提交）

> 注意是 `cp` 不是 `mv`——`init.sh` 不破坏安装包源文件，同一套 `harness-starter` 可以重复向不同目录安装而不影响自身。

---

## 首次 `dev.sh check` 的期望输出

```
[Arch] BACKEND_RULES.md 硬规则扫描...
  ✅ [dep-business-cross] 无违规
  ✅ [autowired-field-injection] 无违规
  ...
✅ [Arch] 架构规则全部通过（基线）
```

**如果有违规**——说明你的现存代码触犯了 starter 自带的示范规则。**这是正常的**——按提示二选一：

1. 修代码到合规（推荐：当下就把屎山入口堵了）
2. 在 `dev.sh` 里把不适用的规则注释掉（理由写到 `BACKEND_RULES.md` 对应段）

---

## 常见问题

**Q1：我项目不是 Spring Boot / Vue，能用吗？**
A：本期只覆盖 Java + Vue 双栈。如果你是 Node/Python/Go：
- Tier 1 全部可用（项目无关）
- Tier 2 的 `AGENTS.md` 模板 + 6 类 grep 规则需要按你的栈改 grep pattern
- `dev.sh` 模板需要改 docker 命令、编译命令、日志关键字
具体看 `CUSTOMIZE.md` 末尾的"自写指南：非 Java/Vue 栈如何改造"章节。

**Q2：我已经有 `AGENTS.md` 了怎么办？**
A：`init.sh` 会**跳过已存在的文件**并报警。手动合并：
```bash
# bootstrap 场景已自动清理 TMPDIR，用降级 A 拿到本地副本再 diff：
git clone --depth=1 https://github.com/caokang1/harness-agent.git /tmp/hs-ref
diff -u AGENTS.md /tmp/hs-ref/tier2-template/AGENTS.md
```
按需把 starter 里没有的段合并到你现有的文件。

**Q3：我只想要 skill，不要 `dev.sh` / OpenSpec / `.learnings` 怎么办？**
A：走降级 A 的"拿到本地副本"方式：
```bash
git clone --depth=1 https://github.com/caokang1/harness-agent.git /tmp/hs-ref
cp -r /tmp/hs-ref/tier1-direct/.claude .
rm -rf /tmp/hs-ref
```

**Q4：装完发现某条 grep 规则太严格，我项目跑不通怎么办？**
A：直接改 `dev.sh` 注释掉那条 `_check`，并在 `BACKEND_RULES.md` 对应段加一行 `> 已禁用：<理由>`。规则可以随项目演进调整，但**改一条要在两个地方留痕**。

**Q5：装完之后需要和起步包保持同步吗？**
A：**不需要**。拷到你仓库的那一刻起，那就是你的文件，可以随意修改。起步包以后有更新，你可以对比着手动挑选需要的改动合进来。

**Q6：我想在 CI / Dockerfile 里自动装 starter，怎么做？**
A：用降级 B（`curl | tar`），并**锁定一个 git tag**，例如：
```bash
# Dockerfile 或 CI 配置
RUN mkdir -p .harness-starter \
  && curl -fsSL https://github.com/caokang1/harness-agent/archive/refs/tags/<标签>.tar.gz \
     | tar -xz --strip-components=1 -C .harness-starter \
  && bash .harness-starter/init.sh --project-name=... \
  && rm -rf .harness-starter
```
不要在 CI 里直接跑 `bash <(curl ...) bootstrap.sh` ——那等于每次都拉 `main`，构建不可复现。

**Q7：install 跑到一半 `Ctrl+C` 了，会不会留下残骸？**
A：临时目录会在进程退出时自动清理。**但是**如果 `init.sh` 已经开始 `cp` 了，**已经铺到你项目根的文件不会自动撤销**；在 git 仓库里先用 `git status` 查看，再用 `git clean -fd` 清掉未跟踪的新文件。**`git clean -fd` 会删除所有未跟踪的文件，运行前先确认里面没有你自己新建、还没提交的文件**（可先跑 `git clean -nd` 预览）。
