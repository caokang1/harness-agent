---
name: openspec-archive-change
description: Archive a completed change in the experimental workflow. Use when the user wants to finalize and archive a change after implementation is complete.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.2.0"
---

Archive a completed change in the experimental workflow.

**Input**: Optionally specify a change name. If omitted, check if it can be inferred from conversation context. If vague or ambiguous you MUST prompt for available changes.

**Steps**

1. **If no change name provided, prompt for selection**

   Run `openspec list --json` to get available changes. Use the **AskUserQuestion tool** to let the user select.

   Show only active changes (not already archived).
   Include the schema used for each change if available.

   **IMPORTANT**: Do NOT guess or auto-select a change. Always let the user choose.

2. **Check artifact completion status**

   Run `openspec status --change "<name>" --json` to check artifact completion.

   Parse the JSON to understand:
   - `schemaName`: The workflow being used
   - `artifacts`: List of artifacts with their status (`done` or other)

   **If any artifacts are not `done`:**
   - Display warning listing incomplete artifacts
   - Use **AskUserQuestion tool** to confirm user wants to proceed
   - Proceed if user confirms

3. **Check task completion status**

   Read the tasks file (typically `tasks.md`) to check for incomplete tasks.

   Count tasks marked with `- [ ]` (incomplete) vs `- [x]` (complete).

   **If incomplete tasks found:**
   - Display warning showing count of incomplete tasks
   - Use **AskUserQuestion tool** to confirm user wants to proceed
   - Proceed if user confirms

   **If no tasks file exists:** Proceed without task-related warning.

4. **Assess delta spec sync state**

   Check for delta specs at `openspec/changes/<name>/specs/`. If none exist, proceed without sync prompt.

   **If delta specs exist:**
   - Compare each delta spec with its corresponding main spec at `openspec/specs/<capability>/spec.md`
   - Determine what changes would be applied (adds, modifications, removals, renames)
   - Show a combined summary before prompting

   **Prompt options:**
   - If changes needed: "Archive and merge specs (recommended)", "Archive without merging specs"
   - If already synced: "Archive now", "Cancel"

   Spec merging is done by the `openspec archive` CLI in step 5a — do not edit `openspec/specs/` by hand. "Archive without merging specs" maps to `--skip-specs`.

5. **Perform the archive（统一归档到 docs/plans/archive/）**

   Generate target name using current date: `YYYY-MM-DD-<change-name>`

   归档方式与 `docs/agents/archive.md` 一致：先由 OpenSpec 命令归档并合并 specs，再整体迁到 `docs/plans/archive/`。不要用 `mv` 手动搬 `openspec/changes/<name>`，那样不会合并 specs。

   **Step 5a — OpenSpec 归档（合并 specs，临时中转）**：
   ```bash
   openspec archive <name> --yes                # 用户选了不合并 specs 时加 --skip-specs
   ls -d openspec/changes/archive/*-<name>      # 记下实际生成的目录名（日期以命令生成的为准）
   ```
   命令失败时停下来把输出给用户看，按 `docs/agents/archive.md` 的 precheck 清单排查，不要改用手动 `mv`。

   **Step 5b — 收集设计文档和计划**：
   1. 文件名里带变更名的，直接移入：
      ```bash
      for f in docs/plans/*<name>*.md; do [ -f "$f" ] && mv "$f" openspec/changes/archive/YYYY-MM-DD-<name>/; done
      ```
      `writing-plans` 按 `docs/plans/YYYY-MM-DD-<name>-impl-plan.md` 命名，会在这一步被收进来。
   2. 再列出 `docs/plans/` 根目录下剩余的 `*.md`（`architecture.md` 除外），问用户其中有没有属于本次变更的，比如 brainstorming 按主题命名的 `*-design.md`。用户确认的再移入，不要猜。

   **Step 5c — 统一迁移到最终归档位置**：
   ```bash
   mkdir -p docs/plans/archive
   mv openspec/changes/archive/YYYY-MM-DD-<name> docs/plans/archive/
   ```

   **Check if target already exists in docs/plans/archive/:**
   - If yes: Fail with error, suggest renaming existing archive or using different date
   - If no: Proceed with move

   **确认 openspec/changes/archive/ 已清空**（如果没有其他待归档的变更）。

6. **Display summary**

   Show archive completion summary including:
   - Change name
   - Schema that was used
   - Final archive location (`docs/plans/archive/YYYY-MM-DD-<name>/`)
   - Whether specs were synced (if applicable)
   - Collected design docs (if any)
   - Note about any warnings (incomplete artifacts/tasks)

**Output On Success**

```
## Archive Complete

**Change:** <change-name>
**Schema:** <schema-name>
**Archived to:** docs/plans/archive/YYYY-MM-DD-<name>/
**Design docs collected:** <list or "none">
**Specs:** ✓ Synced to main specs (or "No delta specs" or "Sync skipped")

All artifacts complete. All tasks complete.
```

**Guardrails**
- Always prompt for change selection if not provided
- Use artifact graph (openspec status --json) for completion checking
- Don't block archive on warnings - just inform and confirm
- Preserve .openspec.yaml when moving to archive (it moves with the directory)
- Show clear summary of what happened
- If sync is requested, use openspec-sync-specs approach (agent-driven)
- If delta specs exist, always run the sync assessment and show the combined summary before prompting
