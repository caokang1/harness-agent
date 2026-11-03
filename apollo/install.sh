#!/usr/bin/env bash
# ============================================================
# Harness Starter Kit · Apollo 项目安装脚本
#
# 把通用起步包（tier1-direct + jenkins / zentao / table-lineage）和 apollo/overlay/
# 里的项目定制文件装进项目仓库。所有文件只留在本地：写进 .git/info/exclude，
# 不进团队仓库，也不碰团队维护的 AGENTS.md / CLAUDE.md / docs/openspec/。
#
# overlay 里的项目专有名称（分支、模块、表、环境命名等）都是 {{AP_*}} 占位符，
# 真实值在私有 profile 目录里（不进本仓库，向团队成员索取），安装时还原。
#
# 用法（在项目仓库根目录）：
#   git clone -b apollo https://github.com/caokang1/harness-agent.git /tmp/harness-agent
#   bash /tmp/harness-agent/apollo/install.sh --branch-owner=<你的分支前缀，如 ZHANGSAN>
#
# 参数：
#   --branch-owner=X   功能分支前缀，分支名为 X/feature-<禅道号>-<变更名>（必填）
#   --profile=DIR      私有 profile 目录，默认 ~/.config/harness-agent/apollo
#   --target=DIR       项目仓库根目录，默认当前目录
#   --update           升级：覆盖已有的 harness 文件（规则、skill、脚本），
#                      经验与进度（.learnings/、.harness/、本地坐标表、.jenkins-deploy.json）始终保留
#   --dry-run          只列出将写入的文件，不改动
#   --uninstall        按安装清单删除装过的文件（不删 .learnings/ 和 .harness/）
# ============================================================
set -euo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$(pwd)"
PROFILE="$HOME/.config/harness-agent/apollo"
OWNER="" UPDATE=0 DRY=0 UNINSTALL=0

for a in "$@"; do
  case "$a" in
    --branch-owner=*) OWNER="${a#*=}" ;;
    --profile=*)      PROFILE="${a#*=}" ;;
    --target=*)       TARGET="${a#*=}" ;;
    --update)         UPDATE=1 ;;
    --dry-run)        DRY=1 ;;
    --uninstall)      UNINSTALL=1 ;;
    -h|--help)        sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "未知参数：$a（--help 查看用法）" >&2; exit 1 ;;
  esac
done

die() { echo "✗ $*" >&2; exit 1; }

TARGET="$(cd "$TARGET" && pwd)"
MANIFEST="$TARGET/.harness/apollo-manifest.txt"
PROF="python3 $KIT/apollo/profile.py"

# Never overwritten, even with --update: they hold the user's own data.
KEEP_RE='^(\.learnings/|\.harness/|\.jenkins-deploy\.json$|\.claude/skills/apollo-logs/references/sls-coordinates\.md$)'

# Local-only paths written to .git/info/exclude.
EXCLUDES="/CLAUDE.local.md /BACKEND_RULES.md /FRONTEND_RULES.md /dev.sh /.learnings/ /.harness/ /docs/agents/ /openspec/templates/ /.mvn /.m2-local"

git -C "$TARGET" rev-parse --git-dir >/dev/null 2>&1 || die "$TARGET 不是 git 仓库"

if [ "$UNINSTALL" = 1 ]; then
  [ -f "$MANIFEST" ] || die "没有安装清单 $MANIFEST"
  n=0
  while IFS= read -r rel; do
    [[ "$rel" =~ $KEEP_RE ]] && continue
    [ -f "$TARGET/$rel" ] && rm -f "$TARGET/$rel" && n=$((n + 1))
  done < "$MANIFEST"
  find "$TARGET/.claude/skills" "$TARGET/docs/agents" "$TARGET/openspec/templates" -type d -empty -delete 2>/dev/null || true
  python3 "$KIT/tier1-direct-optional/.claude/skills/zentao/scripts/zentao.py" hooks uninstall \
    --settings "$TARGET/.claude/settings.json" >/dev/null 2>&1 || true
  echo "✅ 已删除 $n 个文件；.learnings/ 和 .harness/ 保留，如不需要请手动删除"
  exit 0
fi

[ -n "$OWNER" ] || die "缺 --branch-owner（功能分支前缀，如 --branch-owner=ZHANGSAN）"
[[ "$OWNER" =~ ^[A-Za-z0-9._-]+$ ]] || die "--branch-owner 只能含字母、数字、. _ -"
[ -f "$PROFILE/profile.json" ] || die "找不到私有 profile：$PROFILE/profile.json
  向团队成员要一份 profile 目录（含 profile.json 和 files/），放到该位置并 chmod -R go-rwx，或用 --profile 指定"

dist="$($PROF get --profile "$PROFILE" AP_DISTRIBUTE_SCRIPT)"
api="$($PROF get --profile "$PROFILE" AP_MOD_API)"
[ -f "$TARGET/$dist" ] && [ -d "$TARGET/$api" ] \
  || die "$TARGET 不像本项目仓库（缺 $dist 或 $api/），用 --target 指定"

# Source layers, later ones win: generic kit → optional skills → project overlay.
LAYERS=(
  "$KIT/tier1-direct"
  "$KIT/tier1-direct-optional/.claude/skills/jenkins-deploy=.claude/skills/jenkins-deploy"
  "$KIT/tier1-direct-optional/.claude/skills/zentao=.claude/skills/zentao"
  "$KIT/tier1-direct-optional/.claude/skills/table-lineage=.claude/skills/table-lineage"
  "$KIT/apollo/overlay"
  "$PROFILE/files"
)

declare -A SRC
for layer in "${LAYERS[@]}"; do
  dir="${layer%%=*}"; prefix=""
  [[ "$layer" == *=* ]] && prefix="${layer#*=}/"
  [ -d "$dir" ] || continue
  while IFS= read -r -d '' f; do
    SRC["$prefix${f#"$dir"/}"]="$f"
  done < <(find "$dir" -type f -not -path '*/__pycache__/*' -print0)
done

added=0 updated=0 skipped=0 written=()
mkdir -p "$TARGET/.harness"
[ "$DRY" = 1 ] || : > "$MANIFEST.new"
for rel in $(printf '%s\n' "${!SRC[@]}" | sort); do
  dst="$TARGET/$rel"
  if [ -e "$dst" ] && { [ "$UPDATE" = 0 ] || [[ "$rel" =~ $KEEP_RE ]]; }; then
    skipped=$((skipped + 1))
  elif [ "$DRY" = 1 ]; then
    echo "  $([ -e "$dst" ] && echo 覆盖 || echo 新增)  $rel"
  else
    mkdir -p "$(dirname "$dst")"
    [ -e "$dst" ] && updated=$((updated + 1)) || added=$((added + 1))
    sed "s/{{BRANCH_OWNER}}/$OWNER/g" "${SRC[$rel]}" > "$dst"
    [ -x "${SRC[$rel]}" ] && chmod +x "$dst"
    written+=("$dst")
  fi
  [ "$DRY" = 1 ] || echo "$rel" >> "$MANIFEST.new"
done

if [ "$DRY" = 1 ]; then
  echo "dry-run：以上文件将写入，另有 $skipped 个已存在（不加 --update 时保留）"
  exit 0
fi
mv "$MANIFEST.new" "$MANIFEST"

# Restore the project names from the private profile.
if [ "${#written[@]}" -gt 0 ]; then
  $PROF apply --profile "$PROFILE" "${written[@]}"
  left="$(grep -lF '{{AP_' "${written[@]}" 2>/dev/null || true)"
  [ -z "$left" ] || echo "⚠ 以下文件还有未还原的 {{AP_*}} 占位符（profile 缺词条）：
$left"
fi

# Seed files that hold local data.
coords="$TARGET/.claude/skills/apollo-logs/references/sls-coordinates.md"
[ -e "$coords" ] || { cp "$TARGET/.claude/skills/apollo-logs/references/sls-coordinates.example.md" "$coords"; }
[ -e "$TARGET/.harness/progress.md" ] || cp "$KIT/apollo/progress.template.md" "$TARGET/.harness/progress.md"

# Keep everything out of the team repo.
exclude="$(git -C "$TARGET" rev-parse --git-path info/exclude)"
case "$exclude" in /*) ;; *) exclude="$TARGET/$exclude" ;; esac
mkdir -p "$(dirname "$exclude")"; touch "$exclude"
for p in $EXCLUDES $(printf '%s\n' "${!SRC[@]}" | sed -n 's#^\(\.claude/skills/[^/]*\)/.*#/\1/#p' | sort -u); do
  grep -qxF "$p" "$exclude" || echo "$p" >> "$exclude"
done

# ZenTao timing hooks, merged into .claude/settings.json.
python3 "$TARGET/.claude/skills/zentao/scripts/zentao.py" hooks install \
  --settings "$TARGET/.claude/settings.json" >/dev/null

cat <<EOF
✅ 已安装：新增 $added，覆盖 $updated，保留 $skipped 个已存在文件
   清单：.harness/apollo-manifest.txt（--uninstall 按它删除）

还需要你做（凭据只放用户目录，chmod 600，不进仓库）：
  1. 禅道：     ~/.config/zentao/config.json      {"url", "account", "password"}
  2. Jenkins：  ~/.config/jenkins-deploy/config.json   {"url", "user", "token"}
  3. 测试库：   ~/.config/apollo-db/<env>.properties  host= user= password=（建议只读账号）
  4. Nacos：    ~/.config/apollo-env/nacos.json   {"<env>": {"url", "namespace", "group"}}
  5. JDK 8 解压到 ~/.local/jdk8（或设 JDK8_HOME）；openspec CLI：npm i -g @fission-ai/openspec
  6. 多需求并行：echo '[ -f $TARGET/docs/agents/feat.sh ] && . $TARGET/docs/agents/feat.sh' >> ~/.bashrc
  7. 查生产日志：配置 aliyun-observability MCP，把各国坐标填进
     .claude/skills/apollo-logs/references/sls-coordinates.md
EOF
