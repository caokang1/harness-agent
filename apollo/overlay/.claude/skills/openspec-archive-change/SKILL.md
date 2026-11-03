---
name: openspec-archive-change
description: Finalize (complete in place) a finished OpenSpec change in this repo — write TRACE.md inside the change directory and commit it with the last tasks backfill; the directory is not moved. Use when the user wants to archive, finalize or close out a change after implementation is complete.
license: MIT
metadata:
  author: openspec (adapted for {{AP_PROJECT_SLUG}})
  version: "2.0"
---

Finalize a completed change **in place**. In this repo changes live in `docs/openspec/changes/<name>/` and stay there after completion; do not run `openspec archive`, do not move the directory, do not touch `openspec/specs/` (the repo has no main spec library). Full SOP: `docs/agents/archive.md`.

**Input**: optionally a change name. If omitted, infer it from the conversation; if still ambiguous, run `cd docs && openspec list --json` and let the user choose with **AskUserQuestion** (never auto-select).

**Steps**

1. **Check tasks**

   ```bash
   grep -n '^- \[ \]' docs/openspec/changes/<name>/tasks.md
   ```
   Any hit → stop. Each open item must become `[x]` (done) or `[~]` plus an indented one-line reason (abandoned). Ask the user which, do not guess.

2. **Check delivery**

   - The code commit is on the test integration branch (see "分支规则" in `docs/agents/workflow.md`):
     `git fetch -q origin <branch> && git merge-base --is-ancestor <sha> origin/<branch>`
   - Not there yet → stop and run `finishing-a-development-branch` first.
   - Zentao task finished? If not, remind the user (zentao skill); do not block on it.

3. **Write TRACE.md**

   Create `docs/openspec/changes/<name>/TRACE.md` (new file, LF) from the template in `docs/agents/archive.md`. Fill it from facts in this session and git, not from the plan:
   - metadata: Zentao id/url/hours, requirement doc url, size, feature branch + base sha, code commit sha, integration merge sha
   - scope and design deviations (compare with proposal.md / design.md / tasks.md)
   - test coverage actually achieved (compile command + result, unit tests, review, test-env verification)
   - follow-ups and the one or two things a future maintainer must not break

4. **Commit and deliver** (only after the user confirms finishing; same rules as `finishing-a-development-branch`)

   - Commit TRACE.md together with the tasks.md backfill on the feature branch; message `Finalize openspec change <name> (#<zentao id>)`, no attribution trailer
   - Push the feature branch, merge it into the test integration branch (preview with `git merge-tree --write-tree` first), push that branch (never force-push; if rejected, merge the remote first), switch back to the feature branch

5. **Trim progress** — keep only the last 3 session sections in `.harness/progress.md` (see `docs/agents/archive.md`).

**Output**

```
## Change finalized

**Change:** <name>
**Location:** docs/openspec/changes/<name>/ (in place)
**TRACE:** docs/openspec/changes/<name>/TRACE.md
**Commits:** <finalize sha> on <feature branch>; merged into <integration branch> @ <sha>
**Warnings:** <open follow-ups, Zentao not finished, etc. — or "none">
```

**Guardrails**
- Never move the change directory and never run `openspec archive` in this repo
- Never mark `[ ]` items done on your own; ask
- TRACE.md states what actually happened, including what was not verified
- No commit, push or merge before the user has verified the work and agreed
