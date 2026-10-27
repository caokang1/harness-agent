# Harness Starter Kit · 设计决策

> 这份文档**不是用户文档**，是给"维护这个起步包的人"看的——记录 4 个关键决策的理由。新人接手或想改本包时，先读这份避免翻车。

---

## 决策 1：分层为 Tier 1（直接拿来）/ Tier 2（占位符模板）/ Tier 3（不在本包内）

**为什么不全部做成模板？** 因为 Tier 1 这 18 个必装 skill（`using-superpowers` / `brainstorming` / `writing-plans` / `executing-plans` / `verification-before-completion` / `systematic-debugging` / `receiving-code-review` / `requesting-code-review` / `openspec-{explore,propose,apply-change,archive-change}` / `test-driven-development` / `using-git-worktrees` / `dispatching-parallel-agents` / `subagent-driven-development` / `finishing-a-development-branch` / `writing-skills`）**完全是项目无关的工程方法论**，没有任何项目特异性内容可填——硬塞占位符反而显得不专业。直接拷贝才是正确动作。

**为什么不全部做成"直接拿来"？** 因为 `AGENTS.md` 里项目名、模块名、技术栈、目录约定，每条都是**强项目特异性**的；`dev.sh` 里 grep 规则的模块路径、docker compose 的服务名同理。如果不留占位符，使用者要么逐字找替换（容易漏），要么放弃用。

**为什么 Tier 3 不在本包里？** 因为 Tier 3 内容（项目特异 grep 规则、verify-snapshot 表清单、MCP 服务名）**没有任何文件层面可复用的部分**——只能给方法论，不能给文件。塞进来反而会让使用者误以为 starter 里就是答案，跳过自己的反推工作。

---

## 决策 2：独立仓库化 + 手动 cherry-pick，不做自动镜像

starter 初版**物理抽自** `mcp-gateway` 主项目，初期两边是同 commit 同步的强耦合。独立仓库化后，这个设计改了：

**为什么独立成仓库？**
- 起步包的受众是**跨项目**的，放在 mcp-gateway 下面不利于发现和传播（别人得知道这个项目才能找到 starter）
- 独立仓库有独立的 issue / MR 流，社区反馈不会混进 mcp-gateway 的业务讨论
- 使用方一条 `git clone` 即可，不需要 clone 整个 mcp-gateway（后者是完整业务项目，体量大）

**为什么独立后不做自动镜像？**
- starter 和 mcp-gateway 的演化节奏必然分化：starter 要追求**通用性**（让别的栈也能用），mcp-gateway 要追求**项目化**（特定业务约束）。强制双向同步反而会让两边都别扭
- 起步包的价值是"拷贝下来的那一刻已经自洽"——使用方根本不需要知道上游是谁，就像用脚手架生成的代码跟脚手架本身再无关系
- 自动同步要维护一套跨仓库 diff / webhook / CI，**投入产出比**低

**那两边怎么不腐烂？** 靠**手动 cherry-pick + 对账**：
1. **单向为主**：mcp-gateway 的 skill / SOP / OpenSpec 模板改动有通用价值时，starter 维护者按 `SYNC.md` 流程 cherry-pick
2. **反向选择性回传**：starter 收到社区反馈改的通用逻辑（比如更好的 grep 模式），如果对 mcp-gateway 也有用就回传
3. **季度对账**：每 3 个月跑一次 `diff -r` 检查，给 starter 列一份"可选采纳清单"，维护者 review 后决定是否合入

详见 `SYNC.md`。

---

## 决策 3：Tier 2 的 dev.sh 模板只示范 Java + Vue

**为什么不覆盖 Node / Python / Go？**
- 完整跑通一套别的栈起码再加 200 行 dev.sh + 一份 docker-compose，**测试成本不可控**
- 别的栈的人按 `CUSTOMIZE.md` 末尾的"自写指南"改 30 行，比硬塞一套半生不熟的模板更可靠
- 培训文档第六部分会单独给"按你的栈对照修改"checklist，那里讲方法论

**未来如果要扩栈怎么办？** 在 `tier2-template/` 下平行建 `dev.sh.nodejs`、`dev.sh.python` 等扩展模板，让 init.sh 加 `--tech-stack` 参数选择。**当前阶段先不做**，等有 3+ 真实非 Java 用户反馈后再上。

---

## 决策 5：独立仓库的目录结构保留 Tier 分层，而不是铺平

独立仓库化后有一个诱惑：**既然是独立仓库，目录为什么不直接就是使用方将来的目录结构？** 比如 `.claude/skills/` 直接放在仓库根，使用方 `cp -r harness-starter/* your-project/` 就能用。

**不这么做的理由**：
- 使用方只能**全量**采纳，想挑 Tier 1 的某一部分（比如只要 skill）就得自己摘——反而劝退
- starter 仓库里要有"给使用方看的文档"（README / INSTALL / CUSTOMIZE）和"给使用方装完后留在项目里的文件"（skill / AGENTS.md），这两类混在一起会让两边都看不懂
- Tier 分层本身就是**使用方读完文档应该形成的心智模型**，目录结构就是这个模型的显性化

所以保留 `tier1-direct/` / `tier1-direct-optional/` / `tier2-template/` 三个子目录，由 `init.sh` 负责把它们铺到正确位置。

---

## 决策 4：`.learnings/` 只拷骨架不拷内容

**为什么主项目的 `.learnings/` 三个子文件（best_practice / correction / knowledge_gap）共 631 行，starter 里却只有空头部？**

因为 learnings 内容**全是 mcp-gateway 项目特异的事故记录**（比如 `[LRN-2026-04-15-003] Mono.fromCallable 返回 null`），别人项目根本踩不到这些坑。直接拷过去会让使用者误以为"这些是必须遵守的规则"，反而污染他们的判断。

**保留的部分**：
- `LEARNINGS.md` 索引模板（去掉具体条目数和 Categories 表的数据，留结构）
- 24 类 Tag 词典（这部分是**通用工程主题**，可直接复用：workspace-hygiene / verify-gate / openspec-lifecycle 等）
- 三个子文件的**头部说明**（怎么写一条 learning），但条目区域为空

让使用者从**自己项目的第一次事故**开始填，比塞别人的事故有效。

---

## 不在本包范围内的事

明确列出**不做**，避免后续被问：

| 不做 | 为什么 |
|------|-------|
| 提供 GUI 安装器 / Web UI | 起步包用一次就丢，CLI sed 替换够用，GUI 是过度工程 |
| 集成到 IDE 插件 | Cursor / Claude Code 已经原生扫描 `.claude/skills/`，不需要额外集成 |
| 提供 ArchUnit / Checkstyle 配置 | 故意的——`dev.sh` 用 grep 是为了让规则源码化、易审计，标准 linter 反而提高门槛（见培训文档 4.6.3） |
| 自动检测项目栈并选择模板 | 阶段 1 只支持 Java + Vue；自动检测要等多栈支持完成后再做 |
| 跑通完整端到端测试套件 | 起步包的"测试"就是装到一个新仓库里跑通一次完整 OpenSpec 流程；自动化测试投入产出不划算 |

---

## 演进路线

| 阶段 | 内容 | 触发条件 |
|------|------|---------|
| **阶段 1**（当前） | 目录骨架 + 18 必装 + 2 可选 skill + Java/Vue 示范 + 非交互式 init.sh + **独立仓库化** | 已完成 |
| **阶段 2** | 完整交互式 init.sh wizard + SYNC.md 流程自动化工具 + 自验流程 + CI（lint init.sh / 跑 dry-run） | 阶段 1 收到第一轮反馈后启动 |
| **阶段 3**（按需） | 多栈模板（Node / Python / Go） + 按栈选择的 init.sh 分支 | 出现 3+ 真实非 Java 用户后再做 |
