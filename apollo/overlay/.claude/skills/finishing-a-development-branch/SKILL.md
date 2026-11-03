---
name: finishing-a-development-branch
description: Use when implementation is complete and the user has verified it - commits the work, pushes the feature branch and merges it into the test integration branch ({{AP_INTEGRATION_BRANCH}} / {{AP_SUBLINE_INTEGRATION_BRANCH}}) following this repo's branch rules, with a conflict preview and no force-push
---

# Finishing a Development Branch ({{AP_PROJECT_SLUG}})

**Announce at start:** "I'm using the finishing-a-development-branch skill to complete this work."

Branch rules live in `docs/agents/workflow.md` §分支规则. Delivery = feature branch → **test integration branch** (`{{AP_INTEGRATION_BRANCH}}`, or `{{AP_SUBLINE_INTEGRATION_BRANCH}}` for {{AP_SUBLINE}}). Release branches (`{{AP_MAIN_BRANCH}}`, `master_<cc>`, `{{AP_SUBLINE_BRANCH}}`) are merged by the release owner — never merge or push them.

## Step 0: Gate

Only start after the user has said the work passed verification ("通过") and agreed to commit. If not, stop and say what is still pending (verification, open tasks 0.x / 4.x).

## Step 1: Fresh evidence

Run and read the output (do not reuse earlier runs):

```bash
bash dev.sh check --arch          # first line shows the detected base; must be all ✅
bash dev.sh check --changed       # JDK 8 module compile; SKIP_API_INSTALL=1 if the API layer is unchanged
git status --short                # only this change's files; never stage local-only files (AGENTS.md edits, harness files)
```

Failures → stop and report; do not continue to Step 2.

## Step 2: Ask once (single AskUserQuestion)

Determine the integration branch from the rules table (country tag in the Zentao title → `master_<cc>` base → `{{AP_INTEGRATION_BRANCH}}`; {{AP_SUBLINE}} → `{{AP_SUBLINE_INTEGRATION_BRANCH}}`). Preview the merge before asking:

```bash
git fetch -q origin <integration>
git rev-list --count origin/<integration>..HEAD          # commits the merge will bring
python3 docs/agents/merge-preview.py HEAD origin/<integration>      # conflicts, sorted; exit 2 = some are ours
```

`merge-preview.py` also previews base-vs-integration and splits conflicts into **introduced** (caused by this branch — read carefully) and **pre-existing** (the base branch, e.g. `{{AP_CC_BRANCH}}`, already conflicts with the integration branch; not ours). For each hunk it says whether one side already contains the other ("take integration side") or needs a hand merge. Uncommitted work can be previewed by building a dangling commit: `T=$(mktemp); cp .git/index $T; GIT_INDEX_FILE=$T git add -A; C=$(git commit-tree $(GIT_INDEX_FILE=$T git write-tree) -p HEAD -m preview); rm $T` and passing `$C`.

Put the conflict list (with the pre-existing / introduced split and the proposed resolution per file) into the question text.

Ask the user, in one question, with the numbers in the question text:
1. **Commit + push feature branch + merge into `<integration>` + push (Recommended)**
2. Commit + push feature branch only
3. Commit only, keep local

## Step 3: Execute

1. Backfill `docs/openspec/changes/<name>/tasks.md` (verify items, 5.1/5.2) — same push cycle as the commit
2. `git add <change files>`; commit message references the Zentao id and change name; **no attribution trailer**
3. `git push -u origin <feature-branch>`
4. Option 1 only — merge in a throwaway detached worktree so the main checkout (and any other worktree that has `<integration>` checked out) is never switched:
   ```bash
   W=<session scratchpad>/merge-<integration>
   git worktree add -q --detach "$W" origin/<integration>
   (cd "$W" && git merge --no-ff --no-edit <feature-branch>)
   # resolve, verify (below), then: git commit; git fetch; git merge-base --is-ancestor origin/<integration> HEAD
   (cd "$W" && git push origin HEAD:<integration>)
   git worktree remove --force "$W"
   ```
   - Pre-existing conflicts reported as "take integration side": `git checkout --ours -- <file>` and confirm `git diff --quiet origin/<integration> -- <file>`; still list them in the report
   - Conflicts: resolve file by file, keep both sides' intent, preserve each file's line endings (binary-mode edits for CRLF files), validate JSON files parse; show the user each resolution in the final report
   - Re-check after resolving: no conflict markers; compile the touched modules in the worktree with an isolated Maven repo (`.mvn/maven.config`: `-Dmaven.repo.local=$W/.m2-local -Dmaven.repo.local.tail=$HOME/.m2/repository`) so integration-branch jars do not overwrite the feature branch's in `~/.m2`
   - `git push origin <integration>`; if rejected (remote moved): `git fetch` + `git merge origin/<integration>` + push again — **never force-push**
5. Confirm the main checkout is still on `<feature-branch>` with a clean `git status`

## Step 4: Report

Commits and their SHAs, what the merge brought in (commit count), each conflict and how it was resolved, what was not verified, then ask: "是否还有其他任务？没有的话我来做完结（`openspec-archive-change`）和禅道工时（zentao）。"

## Never

- Commit, push or merge before the user's verification and consent
- Merge into or push release branches (`{{AP_MAIN_BRANCH}}`, `master_<cc>`, `{{AP_SUBLINE_BRANCH}}`)
- Force-push, or discard work without a typed confirmation
- Stage files the user did not ask to commit
