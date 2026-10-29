# Harness Starter Kit · 设计决策

> 这份文档**不是用户文档**，是给"维护这个起步包的人"看的，记录几个关键决策的理由。新人接手或想改本包时，先读这份，避免翻车。

---

## 决策 1：分层为 Tier 1（直接拿来）/ Tier 2（占位符模板）/ Tier 3（不在本包内）

**为什么不全部做成模板？**
- Tier 1 的 20 个必装 skill 里，18 个是**完全项目无关的工程方法论**，没有任何项目特异性内容可填，硬塞占位符反而显得不专业，直接拷贝才是正确动作。这 18 个是：`using-superpowers` / `brainstorming` / `writing-plans` / `executing-plans` / `verification-before-completion` / `systematic-debugging` / `receiving-code-review` / `requesting-code-review` / `openspec-{explore,propose,apply-change,archive-change}` / `test-driven-development` / `using-git-worktrees` / `dispatching-parallel-agents` / `subagent-driven-development` / `finishing-a-development-branch` / `writing-skills`。
- 另外 2 个 `harness-orchestrator`、`harness-install-finisher` 是本包自己的流程编排，同样与具体项目无关。

**为什么不全部做成"直接拿来"？**
- `AGENTS.md` 里的项目名、模块名、技术栈、目录约定，每条都是**强项目特异性**的。
- `dev.sh` 里 grep 规则的模块路径、docker compose 的服务名也一样。
- 如果不留占位符，使用者要么逐字找替换（容易漏），要么放弃用。

**为什么 Tier 3 不在本包里？**
- Tier 3 的内容（项目特异的 grep 规则、verify-snapshot 表清单、MCP 服务名）**没有任何文件层面可复用的部分**，只能给方法论，不能给文件。
- 塞进来反而会让使用者误以为 starter 里就是答案，跳过自己的反推工作。

**Tier 1 与 `AGENTS.md` 冲突怎么办？**
- 方法论 skill 多数来自通用开源项目（来源见 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)），其中有些步骤和本包规则不一致，比如自动 commit、按工时判断规模。
- 本包的处理方式：在 `AGENTS.md` 和 `using-superpowers` 里写明「`AGENTS.md` 优先」，并把最关键的几处（自动提交、评审对比的提交范围）直接改掉。
- 改动上游 skill 时尽量少动，便于以后对照上游更新。

---

## 决策 2：独立仓库化，不和源项目自动同步

起步包初版抽自一个内部业务项目（下称"源项目"），之后独立成了这个仓库。

**为什么独立成仓库？**
- 起步包的受众是**跨项目**的。放在源项目里不利于发现和传播，别人得先知道那个项目才能找到 starter。
- 独立仓库有独立的 Issue / PR 流，反馈不会混进源项目的业务讨论。
- 使用方只需要一条命令就能安装，不需要接触源项目。

**为什么不做自动同步？**
- starter 要追求**通用性**，源项目要追求**项目化**，两边的演化节奏必然分化，强制双向同步会让两边都别扭。
- 起步包的价值是"拷贝下来的那一刻已经自洽"。使用方不需要知道上游是谁，就像脚手架生成的代码和脚手架本身再无关系。
- 自动同步要维护一套跨仓库 diff / webhook / CI，投入产出比低。

**那两边怎么不腐烂？**手动挑选、定期对账：
1. 源项目里 skill / SOP / OpenSpec 模板的改动有通用价值时，维护者手动挑选合入 starter，合入前去掉项目特有的内容。
2. starter 里改进的通用逻辑（比如更好的 grep 模式），对源项目也有用时手动回传。
3. 定期用 `diff -r` 对比两边，列一份"可选采纳清单"，由维护者决定是否合入。

---

## 决策 3：Tier 2 的 dev.sh 模板只示范 Java + Vue

**为什么不覆盖 Node / Python / Go？**
- 完整跑通一套别的栈，起码要再加 200 行 dev.sh 和一份 docker-compose，**测试成本不可控**。
- 别的栈的人按 `CUSTOMIZE.md` 末尾的「自写指南」改 30 行左右，比硬塞一套半生不熟的模板更可靠。

**未来要扩栈怎么办？**
- 在 `tier2-template/` 下平行建 `dev.sh.nodejs`、`dev.sh.python` 等扩展模板，让 init.sh 按 `--tech-stack` 选择。
- **当前不做**，等有 3 个以上真实的非 Java 用户反馈后再上。

---

## 决策 4：独立仓库的目录结构保留 Tier 分层，而不是铺平

独立仓库化后有一个诱惑：既然是独立仓库，目录为什么不直接就是使用方将来的目录结构？比如把 `.claude/skills/` 直接放在仓库根，使用方 `cp -r harness-starter/* your-project/` 就能用。

**不这么做的理由**：
- 铺平后使用方只能**全量**采纳，想挑 Tier 1 的某一部分（比如只要 skill）就得自己摘，反而劝退。
- starter 仓库里既有"给使用方看的文档"（README / INSTALL / CUSTOMIZE），也有"装完后留在项目里的文件"（skill / AGENTS.md），混在一起会让两边都看不懂。
- Tier 分层本身就是使用方读完文档应该形成的心智模型，目录结构就是这个模型的显性化。

所以保留 `tier1-direct/`、`tier1-direct-optional/`、`tier2-template/` 三个目录，由 `init.sh` 负责复制到正确位置。

---

## 决策 5：`.learnings/` 只拷骨架不拷内容

**为什么源项目积累了几百行 learnings，starter 里却只有空头部？**
- learnings 的内容**全是源项目特有的事故记录**，别的项目根本踩不到这些坑。
- 直接拷过去会让使用者误以为"这些是必须遵守的规则"，反而污染他们的判断。

**保留的部分**：
- `LEARNINGS.md` 索引模板：去掉具体条目和统计数据，只留结构。
- Tag 词典：这部分是**通用工程主题**，可直接复用，比如 workspace-hygiene / verify-gate / openspec-lifecycle。
- 各分类文件（含 `ERRORS.md`、`FEATURE_REQUESTS.md`）的**头部说明**，讲清楚怎么写一条记录，条目区域为空。

让使用者从**自己项目的第一次事故**开始填，比塞别人的事故有效。

---

## 决策 6：连接外部系统的可选 skill 统一安全约定

`jenkins-deploy`、`zentao` 这类 skill 会用使用者的个人凭据去读写外部系统，统一遵守以下约定：

- 凭据只放在用户目录下的配置文件里，权限 600，不进项目仓库，不出现在命令行参数里。
- 默认拒绝明文 HTTP，需要使用者在配置里显式打开。
- 带凭据的请求不跟随跳转。
- 写操作先预览，凭确认码执行；确认后内容有任何变化，旧确认码就失效。
- 脚本只依赖 Python 标准库，并附带离线测试（本地模拟服务端）。

---

## 不在本包范围内的事

明确列出**不做**的事，避免后续被问：

| 不做 | 为什么 |
|------|-------|
| GUI 安装器 / Web UI | 起步包用一次就丢，命令行安装加交互确认已经够用，GUI 是过度工程 |
| IDE 插件 | Cursor / Claude Code 已经原生扫描 `.claude/skills/`，不需要额外集成 |
| ArchUnit / Checkstyle 配置 | 故意的：`dev.sh` 用 grep 是为了让规则写在源码里、容易审计，标准 linter 反而提高门槛 |
| 按技术栈自动选择模板 | `--auto` 能识别项目信息，但模板只有 Java + Vue 一套，多栈模板见决策 3 |

---

## 演进路线

| 阶段 | 内容 | 状态 |
|------|------|------|
| **阶段 1** | 目录骨架、Java/Vue 示范、非交互式 init.sh、独立仓库化 | 已完成 |
| **阶段 2** | `--auto` 扫描 + 交互确认、`harness-install-finisher`、安装清单与卸载、单文件安装包与 npm 入口、可选 skill（前端设计、库表血缘、Jenkins、禅道） | 已完成 |
| **阶段 3** | CI：每次提交自动跑脚本语法检查、示例项目安装 / 卸载、各 skill 的离线测试 | 未开始 |
| **阶段 4**（按需） | 多栈模板（Node / Python / Go）和按栈选择的 init.sh 分支 | 出现 3 个以上真实的非 Java 用户后再做 |
