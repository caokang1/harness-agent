#!/usr/bin/env bash
# ============================================================
# Harness Starter Kit · 一键清除脚本
#
# 用法（在已安装的项目根目录执行）：
#   bash uninstall.sh             # 交互确认后删除
#   bash uninstall.sh --yes       # 跳过确认（CI/脚本调用）
#   bash uninstall.sh --dry-run   # 只列出会删除的文件，不实际删除
#
# 删除范围：
#   有安装清单 .harness-starter-manifest 时（新版 init.sh 安装）：
#     只删清单里列出的文件——也就是 init.sh 当时真正写入的文件；
#     安装时因"已存在"而跳过的用户文件不在清单里，不会被删
#   没有清单时（旧版 init.sh 安装）：
#     只删 harness 的 skill 目录、docs/agents/、.learnings/、openspec/templates/；
#     AGENTS.md、dev.sh 等顶层文件无法确认是不是你自己的，只列出来请你手动处理
#   之后删掉因此变空的目录（只删空目录，.claude/ 里你自己的设置、命令、钩子不会动）
#
# 不删除：
#   项目原有的 docs/、openspec/、.claude/ 里的其他内容
#   .harness/ 目录（含进度文件、review 报告，可能有用户数据）
# ============================================================

set -euo pipefail

TARGET_DIR="$(pwd)"
MANIFEST="${TARGET_DIR}/.harness-starter-manifest"
DRY_RUN=0
AUTO_YES=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --yes|-y)  AUTO_YES=1 ;;
    --help|-h)
      sed -n '2,/^set -/p' "$0" | grep '^#' | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "[ERROR] 未知参数：$arg（可用 --yes / --dry-run / --help）"
      exit 1
      ;;
  esac
done

# ---- 旧版安装（无清单）时的删除范围 ----
HARNESS_SKILLS=(
  brainstorming
  dispatching-parallel-agents
  executing-plans
  finishing-a-development-branch
  harness-install-finisher
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
  # 可选 skill
  frontend-design
  ui-ux-pro-max
  table-lineage
)
LEGACY_DIRS=("docs/agents" ".learnings" "openspec/templates")
LEGACY_FILES=("AGENTS.md" "BACKEND_RULES.md" "FRONTEND_RULES.md" "dev.sh" "docker-compose.dev.yml" "CUSTOMIZE.md")

DELETE_FILES=()   # 相对路径
DELETE_DIRS=()    # 相对路径（仅旧版模式）
MANUAL=()         # 无法确认归属、请用户手动处理的文件

if [ -f "$MANIFEST" ]; then
  MODE="manifest"
  while IFS= read -r rel; do
    case "$rel" in ''|'#'*) continue ;; esac
    # 防御：清单里只接受项目内的相对路径
    case "$rel" in /*|*..*) continue ;; esac
    [ -f "${TARGET_DIR}/${rel}" ] || continue
    # .env 是 init.sh 建的空模板；用户往里填了变量就保留
    if [ "$rel" = ".env" ] && grep -qvE '^[[:space:]]*(#|$)' "${TARGET_DIR}/.env"; then
      MANUAL+=(".env")
      continue
    fi
    DELETE_FILES+=("$rel")
  done < <(sort -u "$MANIFEST")
  DELETE_FILES+=(".harness-starter-manifest")
else
  MODE="legacy"
  for skill in "${HARNESS_SKILLS[@]}"; do
    [ -d "${TARGET_DIR}/.claude/skills/${skill}" ] && DELETE_DIRS+=(".claude/skills/${skill}")
  done
  for d in "${LEGACY_DIRS[@]}"; do
    [ -d "${TARGET_DIR}/${d}" ] && DELETE_DIRS+=("$d")
  done
  [ -f "${TARGET_DIR}/.harness-starter-applied.log" ] && DELETE_FILES+=(".harness-starter-applied.log")
  for f in "${LEGACY_FILES[@]}"; do
    [ -f "${TARGET_DIR}/${f}" ] && MANUAL+=("$f")
  done
fi

echo ""
echo "========================================"
echo "  Harness Starter · 卸载预览"
echo "  目标目录：$TARGET_DIR"
if [ "$MODE" = manifest ]; then
  echo "  依据：安装清单 .harness-starter-manifest"
else
  echo "  依据：未找到安装清单（旧版安装），按默认范围"
fi
echo "========================================"
echo ""

if [ ${#DELETE_FILES[@]} -eq 0 ] && [ ${#DELETE_DIRS[@]} -eq 0 ] && [ ${#MANUAL[@]} -eq 0 ]; then
  echo "  （未检测到 harness-starter 安装内容，无需清除）"
  exit 0
fi

echo "将要删除："
for d in ${DELETE_DIRS[@]+"${DELETE_DIRS[@]}"}; do echo "  [DIR ] $d"; done
for f in ${DELETE_FILES[@]+"${DELETE_FILES[@]}"}; do echo "  [FILE] $f"; done
if [ ${#MANUAL[@]} -gt 0 ]; then
  echo ""
  echo "以下文件无法确认是 harness-starter 装的还是你自己的，不会自动删除，请自行检查："
  for f in "${MANUAL[@]}"; do echo "  [保留] $f"; done
fi

echo ""
if [ "$DRY_RUN" -eq 1 ]; then
  echo "[ DRY-RUN ] 以上内容不会被删除。去掉 --dry-run 参数后重跑以实际执行。"
  exit 0
fi

if [ ${#DELETE_FILES[@]} -eq 0 ] && [ ${#DELETE_DIRS[@]} -eq 0 ]; then
  echo "没有可以自动删除的内容。"
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

PARENTS=""
for d in ${DELETE_DIRS[@]+"${DELETE_DIRS[@]}"}; do
  rm -rf "${TARGET_DIR:?}/${d}"
  echo "  ✅ 已删除 ${d}/"
  PARENTS="${PARENTS}$(dirname "$d")"$'\n'
done
for f in ${DELETE_FILES[@]+"${DELETE_FILES[@]}"}; do
  rm -f "${TARGET_DIR:?}/${f}"
  PARENTS="${PARENTS}$(dirname "$f")"$'\n'
done
echo "  ✅ 已删除 ${#DELETE_FILES[@]} 个文件"

# 删除因此变空的目录：从深到浅逐级 rmdir，目录里还有别的东西就停（rmdir 不会删非空目录）
removed_dirs=0
while IFS= read -r d; do
  while [ -n "$d" ] && [ "$d" != "." ]; do
    rmdir "${TARGET_DIR}/${d}" 2>/dev/null || break
    removed_dirs=$((removed_dirs + 1))
    d="$(dirname "$d")"
  done
done < <(printf '%s' "$PARENTS" | awk -F/ '{print NF "\t" $0}' | sort -rn | cut -f2- | uniq)
[ "$removed_dirs" -gt 0 ] && echo "  ✅ 已删除 ${removed_dirs} 个变空的目录"

echo ""
echo "========================================"
echo "  Harness Starter 卸载完成"
echo "  注意：.harness/ 目录未删除（含进度/review 数据，请手动处理）"
echo "========================================"
