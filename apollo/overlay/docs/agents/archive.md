# 完结 SOP — OpenSpec 变更就地完结

> `docs/agents/workflow.md` 只保留触发条件和动作摘要，完整清单和 TRACE 模板见本文件。
>
> 2026-10-30 起改为**就地完结**：变更目录留在 `docs/openspec/changes/<name>/`，不搬到 `docs/plans/archive/`，不跑 `openspec archive`（团队 36 个变更都没归档过，搬目录只会在团队仓库里多一个只有自己在用的目录）。此前唯一一次搬目录的 `docs/plans/archive/2026-10-30-{{AP_CC}}-{{AP_ARCHIVED_CHANGE}}/` 保持不动。

## 触发时机

**条件**：`tasks.md` 全部达到**合法终态** + 用户确认实现完成 + 代码已推送并合入测试集成分支（见 workflow.md「分支规则」）。

**合法终态有两种**：

| 标记 | 含义 | 使用场景 |
|------|------|---------|
| `- [x]` | **已完成** | 代码实现并验证通过 |
| `- [~]` | **已决策放弃**（不再做） | 实现中发现不必做，例如被其它 task 等价覆盖 |

`- [ ]`（未勾）**不是合法终态**，完结前必须转成 `[x]` 或 `[~]`。`[~]` 必须紧跟一行缩进注释写明放弃理由：

```markdown
- [~] 3.2 抽取通用工具类：放弃
  > 仅当前模块一处使用，无跨模块复用需求。
```

## 完结前检查

1. tasks.md 无悬空未勾项：`grep -n '^- \[ \]' docs/openspec/changes/<name>/tasks.md` 无输出
2. 代码提交已在测试集成分支上：`git merge-base --is-ancestor <sha> origin/<集成分支>`
3. 禅道任务已填工时并完成（zentao skill）

## 完结动作

1. 在 `docs/openspec/changes/<name>/TRACE.md` 写追溯元数据（模板见下）
2. TRACE.md 和最后一次 tasks 回填一起提交 → 推功能分支 → 合入测试集成分支并推送 → 切回功能分支
3. 不移动目录、不修改 delta spec（仓库没有主 spec 库，`specs/` 原样保留）

## TRACE.md 模板

```markdown
# Trace: <change-name>

## 追溯元数据
| 字段 | 值 |
|------|----|
| 禅道 | #<id> <url>（工时 Xh） |
| 需求文档 | <url> |
| 规模 | S / M / L |
| 分支 | <功能分支>（基线 <origin/master_xx> @ <sha>） |
| 代码提交 | <sha> <subject> |
| 合入 | <集成分支>：<merge sha>，已推送 |

## 实际范围 vs 计划范围
<一致则写"无偏差"；否则列 新增 / 砍掉 / 推迟 及原因>

## 实现与合并中的偏差
<编码时发现 design.md 方案不符而临时调整的决策；合并冲突怎么解的>

## 测试覆盖
<编译 / 单测 / 审查 / 测试环境验证 的实际结果>

## 后续待办
- [ ] <明确不在本次范围、但要追踪的事>

## 留给后人的话
<1-3 段：最难的决策、最容易踩的坑、最不希望被怎样误改>
```

## 完结后裁剪 progress.md

`.harness/progress.md` 只保留最近 3 次会话段（以 `## YYYY-MM-DD HH:mm — 主题` 开头），其余移入 `.harness/progress-archive/YYYY-MM.md`：

```bash
grep -cE "^## [0-9]{4}-[0-9]{2}-[0-9]{2}" .harness/progress.md
```

## 完结触发的主动询问

每次 commit & push 后，Agent **必须**主动问：

> "本次改动已提交推送。是否还有其他任务？如果没有，我来做完结和经验总结。"
