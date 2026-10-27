# Learnings 索引

> **索引模式**：本文件只保留索引 + 规则说明 + tag 词典。完整条目按 category 拆到兄弟文件。
> 新会话启动时**只扫本文件**，按 tag / 关键词定位后再下钻到子文件。

## Categories（现有）

| Category | 子文件 | 条目数 | 用途 |
|----------|--------|--------|------|
| best_practice | [`LEARNINGS-best_practice.md`](LEARNINGS-best_practice.md) | 0 | 做法推荐、反模式避坑、架构判断依据 |
| knowledge_gap | [`LEARNINGS-knowledge_gap.md`](LEARNINGS-knowledge_gap.md) | 0 | 文档/工具/API 的认知盲区，补齐后可避免反复踩坑 |
| correction | [`LEARNINGS-correction.md`](LEARNINGS-correction.md) | 0 | 被用户/同行纠正的明确错误，作为 rule 升格的一手依据 |

## 推荐 Tag 词典（半开放）

> **目的**：替代旧的 `grep -c "<keyword>"` 启动动作。同一本质问题用不同关键词分散在多条时，grep 漏；按 tag 聚合不漏。
> **规则**：每条 learning **必填 1-3 个 topic tag**。优先从下表选；若现有 tag 都不贴切，可新增——但**必须同步在下表登记一行**，避免发散。
> **维度约定**：tag 只表达"问题主题"（topic），不打 domain（domain 由 category + 标题 + 子文件名已自明）。
>
> ⚠️ **Starter 说明**：下表分两段——**通用主题**直接保留；**栈相关示范**按你的项目栈裁剪（如 Node 项目可删 `spring-*` / `reactor-pitfall`，纯后端项目可删 `vue-*` / `css-*`）。

### A. 通用主题（项目无关，建议全部保留）

| Tag | 主题 | 命中场景示例 |
|-----|------|-------------|
| `workspace-hygiene` | 工作区状态 | 脏工作区、未 commit 改动累积、跨主题文件污染 |
| `tasks-traceability` | tasks ↔ 代码同步 | tasks.md 回填、归档前 precheck、悬空未勾 |
| `verify-gate` | 用户验证关卡 | apply 后等用户 verify、propose 后等 review、不得自行 commit |
| `openspec-lifecycle` | OpenSpec 流程 | propose/apply/archive、MODIFIED base spec 缺失、`[~]` 放弃态、归档迁移 |
| `rule-consistency` | 规则文档治理 | 多文档交叉对照、表述漂移、AND/OR 歧义、数字不一致 |
| `layer-boundary` | 分层依赖 | DIP 违反、Controller↔Service 反向 import、业务逻辑层归属 |
| `module-coupling` | 模块/组件耦合 | 跨组件数据依赖、跨域抽象时机、API 数据完整度 |
| `dto-placement` | DTO 位置 | record/DTO 定义在 controller vs dto 包 |
| `input-sanitization` | 输入净化 | HTTP Response Splitting、文件名净化、路径穿越 |
| `shell-pitfall` | Shell/bash 陷阱 | glob 不含 dotfiles、`exec` + 管道、wrapper 重读 |
| `cli-ux` | CLI 安装/使用体验 | 安装脚本自动配 PATH、零操作底线 |
| `tool-integration` | 第三方工具集成 | IDE hook 格式、git trailer 注入、skill registry 标记 |
| `file-download` | 浏览器下载 | `window.open` vs `axios+blob`、用户手势上下文 |
| `markdown-parser` | Markdown 解析 | marked setext 标题、frontmatter 误识别 |

### B. 栈相关示范（按项目栈裁剪）

| Tag | 主题 | 适用栈 |
|-----|------|-------|
| `reactor-pitfall` | Reactor 陷阱 | Java + Spring WebFlux |
| `spring-bean-injection` | Spring bean 注入 | Java + Spring |
| `spring-bom-breaking` | Spring/SDK 跨版本 | Java + Spring |
| `classpath-resource` | jar 资源读取 | Java |
| `devtools-reload` | 热重载行为 | Java + Spring DevTools |
| `jvm-flags` | JVM 参数 | Java |
| `vue-reactivity` | Vue 响应式 | Vue 3 |
| `vue-router` | Vue Router | Vue |
| `vue-scoped-css` | Vue scoped CSS | Vue |
| `css-layout-trap` | CSS 布局陷阱 | 任何前端 |

## 使用约定

- **新条目**：按 category 写到对应子文件末尾，**条目头部加 `**Tags**: \`tag1\`, \`tag2\``** 字段，同步在下方「索引表」追加一行（含 Tags 列）。
- **ID 格式**：`[LRN-YYYY-MM-DD-NN]`。`NN` 为当天序号（01/02/...）。
- **ID 必须全局唯一**：写新条目前先 `grep -l "LRN-YYYY-MM-DD-" .learnings/*.md` 确认当天已用的 NN，避免撞号。撞号的第二条用 `-alt` 后缀区分。
- **Tag 选择**：从「推荐 Tag 词典」选 1-3 个 topic tag。若都不贴切：(1) 先确认是否真的是新主题（很可能能复用现有 tag）；(2) 确需新增则同步登记到词典表，并在 commit message 里说明"新增 tag X 因为 Y"。
- **晋升**：详见 `AGENTS.md` §Learnings 晋升。同 tag ≥ 3 次或单次重大事故 → 晋升为 `AGENTS.md` 硬条款 / `BACKEND_RULES.md` 规则 / `dev.sh check --arch` grep 规则。晋升后在原条目末尾追加 `→ PROMOTED to <target> on YYYY-MM-DD`。
- **按月归档**：若单个子文件 > 800 行或跨越 ≥ 3 个月，再考虑按月拆。

## 索引表（按日期倒序）

| ID | 标题 | Category | Tags | 子文件 |
|----|------|----------|------|--------|
| _（空。第一条 learning 写完后追加在此）_ | | | | |

---

> Starter 说明：本索引在你的项目里被装入时是**空的**——这是有意的。从你项目的第一次事故开始填，比塞别人的事故有效。
