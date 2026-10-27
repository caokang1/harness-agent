# 会话管理 SOP

> AGENTS.md 保留 7 步契约级清单 + 扫读预算 + Learnings 晋升摘要；完整的命令与示例、启动体检清单、进度文件模板、learnings 分类与晋升规则见本文件。本文件是**详版唯一来源**，AGENTS.md 与本文件出现表述漂移时以本文件为准。

## 每次新会话开始时

> **顺序强制**：体检动作必须在读文档之前。脏工作区/活跃 change 脱节会让后续所有动作白费。

1. **工作区体检**（先跑，否则禁止接新主题）：
   ```bash
   git status --short
   ```
   工作区非空时，**必须三选一**再开始：
   - 继续完成既有主题
   - `git stash push -m "<原因> @ YYYY-MM-DD"` 暂存
   - 在 `.harness/progress.md` 明确记录"这些文件属于 <某主题>，暂搁置原因 ..."

   **禁止在脏工作区上开启不相关的新主题**。

2. 读 `AGENTS.md` 确认当前流程（重点扫「规则变更日志」段判断增量）
3. **只读** `.harness/progress.md`（已做滚动归档）：扫「当前状态」+「外部阻塞」+「最近 3 次会话」。需要追溯更早会话时按指针下钻 `.harness/progress-archive/YYYY-MM.md`
4. **只扫** `.learnings/LEARNINGS.md` **索引表 + Tag 词典**（索引表按日期倒序、Tags 列已聚合主题）。按 Tag / Category 定位后再下钻对应 `LEARNINGS-<category>.md`。**不要一次性把 3 个子文件全读了**——那违背索引化的初衷
5. 运行 `openspec list` 查看活跃变更
6. **启动体检**：见下面「启动体检清单」——对每个活跃 change 做 tasks/代码对账 + 外部阻塞新鲜度检查
7. **扫描 learnings 密度（按 tag 聚合）**：跑下面命令统计每个 tag 的跨子文件命中数；任一 tag ≥ 3 → 当前会话**首要动作**是晋升（见「Learnings 晋升」）。
   ```bash
   awk '/^\*\*Tags\*\*:/{print}' .learnings/LEARNINGS-*.md | tr ',' '\n' | grep -oE '`[a-z-]+`' | sort | uniq -c | sort -rn
   ```
   **不再用 `grep -c "<keyword>"`**——同一本质问题用不同关键词分散时 grep 漏判，按 tag 聚合不漏。

> **扫读预算**：AGENTS.md + progress.md + LEARNINGS.md 索引段 合计应控制在 **~400 行以内**（各项目随规模增长，但这是新会话必读清单的软上限）。剩余内容（归档会话 / category 全文 / archive 历史）按需下钻，不列入预算。

## 启动体检清单（第 6 步展开）

对 `openspec list` 列出的**每一个活跃 change**，按顺序核对：

| 状态 | 识别方式 | 立即动作 |
|------|---------|---------|
| **tasks 空勾但代码已入库** | `grep -c '^- \[x\]' openspec/changes/<name>/tasks.md` = 0，同时 `git log --oneline --all -- <change 关联文件或 scope>` 有相关 commit | 立刻按 git log 回填 checkbox（不要留到实现阶段） |
| **tasks 全勾但未归档** | 已完成数 == 总数，但目录仍在 `openspec/changes/`（非 archive） | 立刻进入 `docs/agents/archive.md` 的三步流程 |
| **tasks 部分勾 + 无最近 commit** | 活跃但近 7 天 git log 无相关提交 | 询问用户是继续还是放弃（放弃则走回滚流程） |

> **识别"change 关联 commit"的实操**：多数 commit message 不会引用 change name，用 change 涉及的关键 scope / 关键文件路径比对 `git log --oneline -- <path>` 更可靠。

**外部阻塞新鲜度**：读 `progress.md`「外部阻塞」段，**>7 天未更新**的条目主动 ping 用户是否仍阻塞。

## 不确定处理（会话中途的硬动作）

> 借鉴 Karpathy "Think Before Coding" 准则（对应 `AGENTS.md` §Commit 规则「外科手术式改动」+ §编码纪律「简洁优先」的会话内配套动作）。进入 apply 后发生下列任一信号，**立即停下来问用户，不要默认选一个继续**：

| 信号 | 反模式 | 正确动作 |
|------|--------|---------|
| 需求描述有两种以上合理解释 | 默默选一个方向实现 → verify 阶段才被用户发现不是要的 | 列出所有解释 + 各自代价，请用户定档 |
| 两条技术路径都可行，但取舍不同（性能 vs 可读性 / 抽象程度 / 依赖引入） | 按"Agent 偏好"直接选 | 明示各自利弊，让用户选或提出 tradeoff 观点 |
| 当前代码与预期不符，不确定是 bug 还是设计意图 | 直接"修复"导致反而破坏原设计 | 先 `git blame` + 搜索 commit message，仍不确定则问用户 |
| tasks.md 某条粒度过粗 / 实施到一半发现应拆或应合 | 强行按原粒度做或擅自偏离 | 停下来改 tasks.md，或改为 `[~]` 放弃态 + 理由（详见 `AGENTS.md` §归档合法终态）|

> **原则**：Agent 的沉默 ≠ 确定。每一次"默默选了一个方向"都在把选择权单方面接管过来，增加 verify 阶段被打回的概率。**主动暴露困惑 > 伪装确定**。

## 每次会话结束前（强制）

### 1. 更新 `.harness/progress.md`（按模板填，不要自由发挥）

```markdown
## YYYY-MM-DD HH:mm — <本次会话主题>

### 做了什么
- <完成的 task 1，附 commit SHA 或文件路径>
- <完成的 task 2>

### 当前阻塞
- <遇到但未解决的问题，或 None>

### 下次从哪里开始
- <具体到文件/行/ task id，不要只写"继续">

### 未归档的 openspec change
- <name1>: <tasks.md 完成度>
- <name2>: <tasks.md 完成度>

### 外部阻塞（跨会话持续 — 每次新会话启动必须扫）
- [PR #xxx] 等待 <reviewer> review，创建于 YYYY-MM-DD
- [upstream] <描述，如：x 字段待运维协同>，关联 change <name>，最近推进 YYYY-MM-DD
- （无则写 None）
```

> 「外部阻塞」不是可选字段——每次会话结束都要更新一次（哪怕只是把某条状态从"待 review"改成"已合并"）。**>7 天未更新的条目**由下一次会话启动的 Agent 主动 ping 用户确认是否仍阻塞。

### 2. 经验回顾

**触发时机——两类硬动作，不要只靠会话末尾兜底**：

- **事件触发（会话中途 · 高敏感度 · 硬中断）**——一旦出现下列任一信号，**立即停下当前任务**，按下表归档一条 `LRN-` / `ERR-` / `FEAT-`，再恢复任务：
  1. 被用户纠正（出现 "不对" / "你弄错了" / "应该是..." / "重新改" 等词）
  2. 命令返回非预期错误 / 编译失败 / 启动失败 / 测试红
  3. 发现文档、AGENTS.md、RULES、learnings 与实际代码/行为不符
  4. 踩中一个**已经晋升过的硬规则**又被打脸（说明硬规则描述不够清楚，本身也是一条 learning）

  **不要积攒到会话末尾再补记**——中间环节一多就漏；漏的条目永远不会触发晋升。

- **会话末尾兜底（结束前扫一次）**——按下表过一遍确认没遗漏。确实没有要**显式说出**："本次会话无新增 learnings。"（沉默不等于"没有"。）

| 发生了什么 | 记到哪 | 格式 |
|-----------|--------|------|
| 命令失败、编译报错、启动失败 | `.learnings/ERRORS.md` | `[ERR-YYYYMMDD-NN]` |
| 被用户纠正（"不对，应该是..."） | `.learnings/LEARNINGS.md`（correction）| `[LRN-YYYYMMDD-NN]` |
| 发现文档过时或知识有误 | `.learnings/LEARNINGS.md`（knowledge_gap） | `[LRN-YYYYMMDD-NN]` |
| 找到更好的做法 | `.learnings/LEARNINGS.md`（best_practice） | `[LRN-YYYYMMDD-NN]` |
| 用户提出新功能需求 | `.learnings/FEATURE_REQUESTS.md` | `[FEAT-YYYYMMDD-NN]` |

> **为什么要双触发**：只靠"会话末尾兜底"相当于靠 Agent 记性好——会话越长越容易漏；加上"事件即记"，在事件发生当下就把上下文钉死（错误原文、用户原话、现场输出），也能让同一个会话内被纠正两次的同类问题合成一条而不是忘掉。参考：业界 `self-improving-agent` skill 的事件驱动激活思路，我们把它吸收到 session.md 的硬 SOP 层（而不是单独做成 skill），接到下节的 Tag 聚合/晋升通道上。

## Learnings 晋升（硬动作，不是口号）

**触发条件**：同一个 tag 在 `.learnings/` 里跨子文件合计命中 ≥ 3 次。

> **为什么按 tag 而不是关键词**：同一本质问题在不同条目用不同关键词描述（如"脏工作区" vs "未 commit 改动" vs "messy worktree"），关键词 grep 必漏。tag 是预定义的"问题主题"标识，强制收敛。tag 词典见 `.learnings/LEARNINGS.md` §推荐 Tag 词典。

**执行者**：**新会话启动时的 Agent**——在扫 `.learnings/LEARNINGS.md` 索引时，必须执行：

```bash
# 跨子文件按 tag 聚合命中数
awk '/^\*\*Tags\*\*:/{print}' .learnings/LEARNINGS-*.md | tr ',' '\n' | grep -oE '`[a-z-]+`' | sort | uniq -c | sort -rn
```

若某 tag 命中 ≥ 3 → 当前会话的**首要动作**：

1. 列出该 tag 下所有 learning（`grep -B2 '<tag>' .learnings/LEARNINGS-*.md` 看上下文）
2. 把共性规则提升到 `AGENTS.md` 或对应 `*_RULES.md` 的合适章节
3. 在原条目（在对应 `LEARNINGS-<category>.md` 里）末尾追加 `→ PROMOTED to AGENTS.md#<section> on YYYY-MM-DD`

**例外**：若一次事故代价极高（如归档进入半失败中间态），允许**单次命中即晋升**，不必等满 3 次——在 PROMOTED 标记里说明"直接晋升，代价过高"即可。

**新 tag 登记**：写新 learning 时若发现现有词典覆盖不到，**必须**在 `LEARNINGS.md` §推荐 Tag 词典里登记一行，避免发散。**禁止"先随便打一个、以后再说"**——这是 tag 体系失效的最常见路径。

**近义合并**：每月会话回顾时（或发现两个 tag 主题高度重叠时）合并近义 tag。合并步骤：
1. 选定保留 tag，把被合并 tag 的所有条目 `**Tags**` 字段批量替换
2. `LEARNINGS.md` 索引表 Tags 列同步替换
3. 词典表删除被合并 tag，在保留 tag 行末加注 "（合并自 X，YYYY-MM-DD）"

**不要寄希望于"下次有空再做"**——晋升和登记都是入场动作，不是可选动作。
