# 归档 SOP — OpenSpec Change 归档完整流程

> AGENTS.md 只保留触发条件 + 归档三步摘要，完整的 precheck 清单、TRACE 模板、偏差处理见本文件。

## 触发时机

**条件**：`tasks.md` 里所有条目达到**合法终态** + 用户确认实现完成 + PR 已创建。

**合法终态有两种**：

| 标记 | 含义 | 使用场景 |
|------|------|---------|
| `- [x]` | **已完成** | 代码实现并验证通过 |
| `- [~]` | **已决策放弃**（不再做） | 实现过程中发现此项不必做——例如 rules 定稿后否决了原计划粒度、实际场景下该抽象没有复用需求、被其它 task 职责等价覆盖 |

`- [ ]`（未勾）**不是合法终态**，归档前必须确定转成 `[x]` 或 `[~]`。

**`[~]` 放弃态要求**：必须在该 task 行后面紧跟一行缩进注释，写明放弃理由（一句话即可）。例：

```markdown
- [~] 3.2 抽取通用工具类：放弃
  > 仅当前模块一处使用，无跨模块复用需求；按 BACKEND_RULES「跨模块使用才放 common 层」原则保留在原模块内。
```

> PR 是否已 merge **不作为归档前置条件**——因为 merge 通常在外部（GitHub/GitLab 网页）完成，Agent 下次会话感知不到 merge 事件。归档独立于 merge 推进，但归档目录里**必须记录完整追溯元数据**（见下）。

## 归档前 precheck 清单（强制，执行 `openspec archive` 之前必须全部通过）

> 归档前 precheck 是防止半失败中间态污染后续尝试的关键，务必按顺序执行。

按顺序自检：

1. **tasks.md 无悬空未勾项**
   ```bash
   grep -n '^- \[ \]' openspec/changes/<name>/tasks.md
   ```
   命中 → 必须先决定每条转 `[x]` 或 `[~]`（后者需紧跟一行缩进放弃理由），否则不得归档。

2. **MODIFIED Requirements 的 base spec 必须真实存在**
   ```bash
   # 对 proposal.md "Specs: Modified capabilities" 列出的每一个 capability：
   ls openspec/specs/<capability>/spec.md
   ```
   任何一个 `ls` 失败 → **不要贸然 `openspec archive`**（会进入半失败中间态）。修复路径二选一：
   - 若该 capability 语义上是**新分层能力** → 把对应 spec delta 从 `## MODIFIED Requirements` 改为 `## ADDED Requirements`，作为新 capability 入库
   - 若该 capability 确实应该存在（历史 change 归档时 `openspec/specs/` 未入 git） → 先把对应 base spec 手动补齐入库，再归档本 change

3. **前序 attempt 的 spec 残留清理**
   第一次归档失败后重试前：`git diff openspec/specs/` 检查是否有来自本次失败尝试的中间态文件（已 applied 但 change 目录未移动），有则 `git checkout`/手动回滚到干净状态。

4. **TRACE.md 骨架已写好**
   归档三步走到第 3 步时才写 TRACE 已来不及。提 PR 后就应填好追溯元数据 + 实现偏差段，第 3 步只做 `mv`。

## 归档目录必须包含的追溯元数据

归档时在 `docs/plans/archive/YYYY-MM-DD-<name>/` 下创建 `TRACE.md`，至少包含：

```markdown
# Trace: <change-name>

## 追溯元数据
- 分支：feature/M-xxxxx/xxx
- 最后一次提交 SHA：<git rev-parse HEAD>
- PR：<url>
- 提 PR 时间：YYYY-MM-DD HH:mm
- merge 状态：pending / merged / reverted（归档时的状态，可能过时）
- 如需复查：在仓库 `git log <SHA>` 或 PR 评论追溯

## 实现偏差（如有）
<如果 tasks.md 中存在 `[~]` 放弃态，或实际实现和计划有职责/粒度调整，在此列明：
- 哪个 task 偏离、偏离成什么
- 偏离的决策依据（通常引用某条 rule）
- 这条偏差是否产生了新的规则沉淀（如有，标注到 rule 文件的对应章节）>

## 本次沉淀的经验（可选）
<如本次实现过程中发现的新规则/反面教材，已沉淀到 AGENTS.md / *_RULES.md / LEARNINGS.md，此处列出去向，便于未来逆向查阅：
- "行数是症状，职责混乱才是病因" → FRONTEND_RULES.md L??
- "tasks 粒度预设 vs rules 定稿冲突时 rules 优先" → ...>
```

即使 PR 最终没合并 / 被 revert，`TRACE.md` 里的 SHA 也能定位到具体代码状态。**不依赖 merge 事件，不依赖分支是否还活着**。

**实现偏差** 段是本 TRACE 和纯元数据型归档的关键差别——让未来的 Agent / 人能逆向理解"计划和实现为什么不一致"。

## 归档操作（三步）

1. **OpenSpec 归档**：`openspec archive` 把 `openspec/changes/<name>/` 移动到 `openspec/changes/archive/YYYY-MM-DD-<name>/`
2. **收集设计文档**：把 `docs/plans/` 根目录下本次变更的设计文档（`*-design.md`、`*-impl-plan.md`）移入 `openspec/changes/archive/YYYY-MM-DD-<name>/`
3. **统一迁移 + 追溯元数据**：
   ```bash
   # 注意：mv source/* 不会移动隐藏文件（.openspec.yaml 等），用下面的写法一次到位
   cp -a openspec/changes/archive/YYYY-MM-DD-<name>/. docs/plans/archive/YYYY-MM-DD-<name>/
   rm -rf openspec/changes/archive/YYYY-MM-DD-<name>
   # 在 docs/plans/archive/YYYY-MM-DD-<name>/ 下完善 TRACE.md（第 2 步的骨架在此填齐）
   ```
   确保 `openspec/changes/archive/` 清空（连目录都不应残留）。

> `docs/plans/archive/` 是**唯一**归档目标。`openspec/changes/archive/` 仅作 openspec CLI 临时中转。
> `docs/plans/architecture.md` 是长期文档，**不归档**。
> 若本次变更未产生独立设计文档（S 规模小改动），跳过第 2 步。

## 归档时裁剪 progress.md（防扫读预算膨胀）

每次归档完成后，**必须**检查并裁剪 `.harness/progress.md`：

1. 数一下 `## Session` 段的数量
2. 只保留**最近 3 次**（按日期/编号排序），其余移入 `.harness/progress-archive/YYYY-MM.md`
3. 更新"已归档会话"段的归档范围说明

```bash
# 查看当前 session 数量
grep -c "^## Session" .harness/progress.md
```

> **为什么是 3 次**：更早的 session 里的关键结论都已沉淀到 LEARNINGS.md / TRACE.md / AGENTS.md，
> progress.md 中保留超过 3 次只是增加扫读成本，无实质价值。

---

## 归档触发的主动询问

每次 commit & push 后，Agent **必须** 主动问：

> "本次改动已提交推送。是否还有其他任务？如果没有，我来做进度归档和经验总结。"

不要等用户说"结束"才触发。判断会话是否收尾是 Agent 的职责。
