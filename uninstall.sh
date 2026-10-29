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
#     安装时因"已存在"而跳过的用户文件不在清单里，不会被删；
#     安装后被你改过的文件（校验和对不上）也不会删，只列出来请你处理
#   没有清单、但有 .harness-starter-applied.log 时（旧版 init.sh 安装）：
#     只删 harness 的 skill 目录、docs/agents/、.learnings/、openspec/templates/；
#     AGENTS.md、dev.sh 等顶层文件无法确认是不是你自己的，只列出来请你手动处理
#   之后删掉因此变空的目录（只删空目录，.claude/ 里你自己的设置、命令、钩子不会动）
#   装过 zentao skill 的，从 .claude/settings.json 里移除它加的两个计时钩子，其余配置原样保留
#
# 不删除：
#   项目原有的 docs/、openspec/、.claude/ 里的其他内容
#   .harness/ 目录（含进度文件、review 报告，可能有用户数据）
#   既没有清单也没有安装日志时，判断不了是否装过，什么都不删
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
      # 用 heredoc 而不是读 $0：通过 bash <(curl ...) 运行时 $0 是已被读过的管道，读不到说明
      cat <<'USAGE'
用法（在已安装的项目根目录执行）：
  bash uninstall.sh             # 交互确认后删除
  bash uninstall.sh --yes       # 跳过确认（CI/脚本调用）
  bash uninstall.sh --dry-run   # 只列出会删除的文件，不实际删除

只删除安装清单 .harness-starter-manifest 里记录的文件；安装后改过的文件、
你原有的文件、.harness/ 目录都会保留。装过 zentao skill 的，会从
.claude/settings.json 里移除它添加的两个计时钩子，其余配置原样保留。
USAGE
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
  jenkins-deploy
  zentao
)
LEGACY_DIRS=("docs/agents" ".learnings" "openspec/templates")
LEGACY_FILES=("AGENTS.md" "BACKEND_RULES.md" "FRONTEND_RULES.md" "dev.sh" "docker-compose.dev.yml" "CUSTOMIZE.md")

DELETE_FILES=()   # 相对路径
DELETE_DIRS=()    # 相对路径（仅旧版模式）
MANUAL=()         # 无法确认归属、请用户手动处理的文件

if [ -f "$MANIFEST" ]; then
  MODE="manifest"
  while IFS= read -r line; do
    case "$line" in ''|'#'*) continue ;; esac
    rel="${line%%$'\t'*}"
    sum=""
    [ "$rel" != "$line" ] && sum="${line#*$'\t'}"   # 新版清单：路径<TAB>校验和
    # 防御：清单里只接受项目内的相对路径
    case "$rel" in /*|*..*) continue ;; esac
    [ -f "${TARGET_DIR}/${rel}" ] || continue
    # .env 是 init.sh 建的空模板；用户往里填了变量就保留
    if [ "$rel" = ".env" ] && grep -qvE '^[[:space:]]*(#|$)' "${TARGET_DIR}/.env"; then
      MANUAL+=(".env")
      continue
    fi
    if [ -n "$sum" ] && [ "$(cksum <"${TARGET_DIR}/${rel}" | awk '{print $1}')" != "$sum" ]; then
      MANUAL+=("$rel（安装后改过）")
      continue
    fi
    DELETE_FILES+=("$rel")
  done < <(sort -u "$MANIFEST")
  DELETE_FILES+=(".harness-starter-manifest")
elif [ -f "${TARGET_DIR}/.harness-starter-applied.log" ]; then
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
else
  echo "未找到安装清单 .harness-starter-manifest 和安装日志 .harness-starter-applied.log，"
  echo "无法确认这个目录装过 harness-starter，不做任何删除。"
  exit 0
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

# zentao skill 在 .claude/settings.json 里加过计时钩子：删除 skill 前先移除，不然钩子会指向不存在的脚本
ZENTAO_SCRIPT="${TARGET_DIR}/.claude/skills/zentao/scripts/zentao.py"
SETTINGS_FILE="${TARGET_DIR}/.claude/settings.json"
ZENTAO_HOOKS=0
if [ -f "$SETTINGS_FILE" ] && grep -q 'zentao/scripts/zentao.py' "$SETTINGS_FILE"; then
  ZENTAO_HOOKS=1
fi

echo "将要删除："
[ "$ZENTAO_HOOKS" -eq 1 ] && echo "  [HOOK] .claude/settings.json 里的禅道计时钩子（其余配置保留）"
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

if [ "$ZENTAO_HOOKS" -eq 1 ]; then
  if command -v python3 >/dev/null 2>&1 && [ -f "$ZENTAO_SCRIPT" ]; then
    python3 "$ZENTAO_SCRIPT" hooks uninstall --settings "$SETTINGS_FILE" | sed 's/^/  ✅ /'
  else
    echo "  ⚠️  无法自动移除禅道计时钩子（缺少 python3），请手动删除 .claude/settings.json 里含 zentao.py track 的两项"
  fi
fi

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
