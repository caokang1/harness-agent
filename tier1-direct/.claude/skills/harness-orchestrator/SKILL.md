---
name: harness-orchestrator
description: "End-to-end development pipeline orchestrator. Use when starting a new feature, requirement, or bugfix — guides the complete workflow from brainstorming through implementation to delivery."
metadata:
  author: harness-starter
  version: "1.0"
---

# Harness Orchestrator

End-to-end development pipeline that chains existing skills into a coherent workflow.

## The Pipeline

```
需求输入
  │
  ▼
① brainstorming（可选，大需求必须）
  │
  ▼
② openspec propose（生成 proposal + design + tasks）
  │
  ▼
③ using-git-worktrees（创建隔离工作区）
  │
  ▼
④ writing-plans（细化实现计划）
  │
  ▼
⑤ subagent-driven-development
  │  └─ 每个 task 内循环:
  │     实现 → dev.sh check --changed → dev.sh reload → spec review → quality review
  │
  ▼
⑥ verification-before-completion（全量验证）
  │
  ▼
⑦ finishing-a-development-branch（合并/PR/清理）
  │
  ▼
⑧ openspec archive（归档 + 提取 learnings）
  │
  ▼
⑨ 更新 .harness/progress.md + .learnings/
```

## When to Use

| 场景 | 从哪一步开始 |
|------|-------------|
| 全新需求 | ① brainstorming |
| 已有明确方案 | ② openspec propose |
| 已有 OpenSpec change | ⑤ subagent-driven-development |
| S 规模改动（按 AGENTS.md 结构性标准判定） | 直接编码 → check → reload → test → **等用户 verify** → commit |
| 紧急热修复 | 直接编码 → check → test → **等用户 verify** → commit；发布由用户决定 |

## Process

### Phase 0: Session Recovery

Every session starts here:

1. Read `.harness/progress.md` to understand current state
2. Read `.learnings/LEARNINGS.md` for known pitfalls
3. Run `openspec list` to check active changes
4. If resuming work, skip to the appropriate pipeline step

### Phase 1: Understand (Steps ①-②)

**Step ① Brainstorming** (skip for small/clear tasks)

Invoke skill: `brainstorming`

- One question at a time, multiple choice preferred
- Explore 2-3 approaches with trade-offs
- Output: design document in `docs/plans/`

**Step ② OpenSpec Propose**

Invoke skill: `openspec-propose`

```bash
openspec new change "<name>"
```

- Generates: proposal.md, design.md, tasks.md
- Validate each artifact with user before proceeding

### Phase 2: Prepare (Steps ③-④)

**Step ③ Git Worktree**

Invoke skill: `using-git-worktrees`

- Create isolated workspace for this change
- Run baseline tests to confirm clean state

**Step ④ Writing Plans**

Invoke skill: `writing-plans`

- Break tasks into 2-5 minute steps
- Save to `docs/plans/YYYY-MM-DD-<name>.md`

### Phase 3: Build (Step ⑤)

**Step ⑤ Subagent-Driven Development**

Invoke skill: `subagent-driven-development`

For each task in the plan:

1. **Implement**: Dispatch implementer subagent
2. **Check**: Run `bash dev.sh check --changed`
3. **Reload**: Run `bash dev.sh reload` (for Java changes)
4. **Spec Review**: Dispatch spec reviewer subagent
5. **Quality Review**: Dispatch code quality reviewer subagent

**Quality Gate per task:**
- `dev.sh check` must pass before review
- Spec review must pass before quality review
- Quality review must pass before next task

### Phase 4: Deliver (Steps ⑥-⑨)

**Step ⑤·五 交叉 Review（M/L 规模必须，S 跳过）**

Agent 自验通过后，执行交叉 Review（完整 SOP 见 `docs/agents/cross-review.md`）：

- **优先**：调用 `requesting-code-review` skill，派独立 subagent 以全新上下文审查（无认知路径依赖）
- **降级**：不适合启动 subagent 时，同实例切换审查者角色（审查前先只读需求和 tasks.md 再看 diff）
- 审查通过 → 进入 Step ⑥；审查不通过 → 退回 Step ⑤ 修复

**Step ⑥ Verification**

Invoke skill: `verification-before-completion`

```bash
bash dev.sh test        # Full test suite
bash dev.sh check       # Full quality check
```

**Step ⑦ Finish Branch**

Invoke skill: `finishing-a-development-branch`

- Verify tests → Present 4 options → Execute → Cleanup

**Step ⑧ Archive**

Invoke skill: `openspec-archive-change`

- Archive the completed change
- Extract learnings from this development cycle

**Step ⑨ Update Harness State**

1. Update `.harness/progress.md`:
   - Mark change as completed
   - Record session summary

2. **经验回顾（必须执行，不可跳过）**:
   - 回顾本次会话，逐项检查：是否有命令失败？被用户纠正？发现过时知识？找到更好做法？
   - 有 → 按格式写入 `.learnings/` 对应文件
   - 没有 → 显式确认："本次会话无新增 learnings。"
   - 同一个 learning 出现 3 次以上 → promote 到 `AGENTS.md`

## Flexibility Rules

The pipeline is a **recommended flow**, not a rigid sequence:

- **Skip**: Small tasks can skip brainstorming; clear specs can skip writing-plans
- **Back-track**: If implementation reveals design issues, go back to openspec-explore
- **Branch**: If a task is blocked, park it and continue with others
- **Abort**: If requirements change fundamentally, archive current change and start fresh

## Human's Role

The human is the only one who can see the entire maze:

- **Sets direction**: What to build, priority, acceptance criteria
- **Approves designs**: Review proposals and architectural decisions
- **Reviews PRs**: Final quality gate before merge
- **Unblocks**: When Agent hits a wall, provide context it can't see

The human does NOT:
- Manually schedule which skill to run (that's the orchestrator's job)
- Debug step-by-step (Agent has systematic-debugging for that)
- Write boilerplate code (Agent handles implementation)

## Anti-Patterns

| Anti-Pattern | Correct Approach |
|-------------|-----------------|
| Skip brainstorming for large features | Always brainstorm for L-size work (structural criteria in AGENTS.md, not hours) |
| Skip `dev.sh check` between tasks | Quality gate is mandatory per task |
| Continue after test failures | Stop, debug, fix, then continue |
| Forget to update progress.md | Always update at session end |
| Ignore learnings from past sessions | Always read `.learnings/` at session start |
| Human micro-manages each step | Human sets direction, Agent executes pipeline |

## Integration Map

```
harness-orchestrator (this skill)
├── brainstorming
├── openspec-propose
│   └── openspec-explore (if needed)
├── using-git-worktrees
├── writing-plans
├── subagent-driven-development
│   ├── test-driven-development (per subagent)
│   ├── requesting-code-review (per task)
│   └── systematic-debugging (on failure)
├── verification-before-completion
│   └── cross-review (M/L，见 docs/agents/cross-review.md)
├── finishing-a-development-branch
└── openspec-archive-change
```
