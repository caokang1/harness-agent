#!/usr/bin/env bash
# ============================================================
# Harness Starter Kit · 一键清除脚本
#
# 用法（在已安装的项目根目录执行）：
#   bash uninstall.sh             # 交互确认后删除
#   bash uninstall.sh --yes       # 跳过确认（CI/脚本调用）
#   bash uninstall.sh --dry-run   # 只列出会删除的文件，不实际删除
#
# 删除范围：由 harness-starter init.sh 安装的所有内容：
#   .claude/skills/<所有 harness skill>
#   docs/agents/（session / verify / archive / cross-review）
#   .learnings/
#   openspec/templates/
#   AGENTS.md  BACKEND_RULES.md  FRONTEND_RULES.md
#   dev.sh  docker-compose.dev.yml
#   .harness-starter-applied.log
#
# 不删除：
#   项目原有的 docs/（只删 docs/agents/）
#   项目原有的 openspec/（只删 openspec/templates/）
#   .harness/ 目录（含进度文件、review 报告，可能有用户数据）
# ============================================================

set -euo pipefail

TARGET_DIR="$(pwd)"
DRY_RUN=0
AUTO_YES=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --yes|-y)  AUTO_YES=1 ;;
    --help|-h)
      sed -n '2,/^set -/p' "$0" | grep '^#' | sed 's/^# \?//'
      exit 0
      ;;
  esac
done

# ---- 待删除列表 ----
HARNESS_SKILLS=(
  brainstorming
  dispatching-parallel-agents
  executing-plans
  finishing-a-development-branch
  harness-orchestrator
  openspec-apply-change
  openspec-archive-change
  openspec-explore
  openspec-propose
  receiving-code-review
  requesting-code-review
  subagent-driven-development
  systematic-debugging
  test-driven-development
  using-git-worktrees
  using-superpowers
  verification-before-completion
  writing-plans
  writing-skills
  # 可选前端 skill
  frontend-design
  ui-ux-pro-max
)

DIRECT_FILES=(
  "AGENTS.md"
  "BACKEND_RULES.md"
  "FRONTEND_RULES.md"
  "dev.sh"
  "docker-compose.dev.yml"
  ".harness-starter-applied.log"
)

DIRECT_DIRS=(
  "docs/agents"
  ".learnings"
  "openspec/templates"
)

echo ""
echo "========================================"
echo "  Harness Starter · 卸载预览"
echo "  目标目录：$TARGET_DIR"
echo "========================================"
echo ""
echo "将要删除："

any=0

for skill in "${HARNESS_SKILLS[@]}"; do
  p="${TARGET_DIR}/.claude/skills/${skill}"
  if [ -d "$p" ]; then
    echo "  [DIR ] .claude/skills/${skill}"
    any=1
  fi
done

for d in "${DIRECT_DIRS[@]}"; do
  p="${TARGET_DIR}/${d}"
  if [ -d "$p" ]; then
    echo "  [DIR ] ${d}"
    any=1
  fi
done

for f in "${DIRECT_FILES[@]}"; do
  p="${TARGET_DIR}/${f}"
  if [ -f "$p" ]; then
    echo "  [FILE] ${f}"
    any=1
  fi
done

# .claude/skills 目录本身（如果已空）
SKILLS_DIR="${TARGET_DIR}/.claude/skills"
CLAUDE_DIR="${TARGET_DIR}/.claude"

if [ "$any" -eq 0 ]; then
  echo "  （未检测到 harness-starter 安装内容，无需清除）"
  exit 0
fi

echo ""
if [ "$DRY_RUN" -eq 1 ]; then
  echo "[ DRY-RUN ] 以上内容不会被删除。去掉 --dry-run 参数后重跑以实际执行。"
  exit 0
fi

if [ "$AUTO_YES" -eq 0 ]; then
  printf "确认删除以上内容？[y/N] "
  read -r answer
  if [[ ! "$answer" =~ ^[yY]$ ]]; then
    echo "已取消。"
    exit 0
  fi
fi

echo ""
echo "正在清除..."

for skill in "${HARNESS_SKILLS[@]}"; do
  p="${TARGET_DIR}/.claude/skills/${skill}"
  if [ -d "$p" ]; then
    rm -rf "$p"
    echo "  ✅ 已删除 .claude/skills/${skill}"
  fi
done

# 如果 .claude/skills 已空，删除整个 .claude
if [ -d "$SKILLS_DIR" ] && [ -z "$(ls -A "$SKILLS_DIR" 2>/dev/null)" ]; then
  rm -rf "$CLAUDE_DIR"
  echo "  ✅ 已删除 .claude/（skills 目录已空）"
fi

for d in "${DIRECT_DIRS[@]}"; do
  p="${TARGET_DIR}/${d}"
  if [ -d "$p" ]; then
    rm -rf "$p"
    echo "  ✅ 已删除 ${d}"
  fi
done

for f in "${DIRECT_FILES[@]}"; do
  p="${TARGET_DIR}/${f}"
  if [ -f "$p" ]; then
    rm -f "$p"
    echo "  ✅ 已删除 ${f}"
  fi
done

echo ""
echo "========================================"
echo "  Harness Starter 卸载完成"
echo "  注意：.harness/ 目录未删除（含进度/review 数据，请手动处理）"
echo "========================================"
