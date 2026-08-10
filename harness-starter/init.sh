#!/usr/bin/env bash
# ============================================================
# Harness Starter Kit · 非交互式初始化脚本
#
# 仓库：https://git.example.com/your-group/harness-starter
#
# 推荐路径（零残留，一行搞定，见 bootstrap.sh）：
#   bash <(curl -fsSL \
#     https://git.example.com/your-group/harness-starter/-/raw/main/bootstrap.sh) \
#     --project-name="my-svc" \
#     --tech-stack="springboot+vue" \
#     --modules="api,core,common,auth,start" \
#     --backend-package="com.example.mysvc" \
#     --frontend-dir="../my-svc-ui" \
#     [--include-frontend-design]
#   bootstrap 会：临时 clone → 调本脚本 → trap 自动清理 /tmp 目录
#
# 直调用法（想先审计 / 固定 commit / 离线安装）：
#   cd /path/to/your-project
#   git clone https://git.example.com/your-group/harness-starter.git .harness-starter
#   bash .harness-starter/init.sh \
#     --project-name="my-svc" \
#     --tech-stack="springboot+vue" \
#     --modules="api,core,common,auth,start" \
#     --backend-package="com.example.mysvc" \
#     --frontend-dir="../my-svc-ui" \
#     [--include-frontend-design]
#   rm -rf .harness-starter    # 装完手动删（含其 .git/）
#
# 参数：
#   --auto                      零参数自动模式：从项目现场扫出 project-name / modules
#                               / backend-package / tech-stack / app-main-class /
#                               frontend-dir / backend-port，进入交互式确认界面
#   --yes                       配合 --auto 使用，跳过交互直接采用扫描结果（CI 用）
#   --dry-run                   配合 --auto 使用，只输出扫描结果后退出，不装任何文件
#   --include-frontend-design   额外安装 frontend-design / ui-ux-pro-max 2 个前端 UI 设计 skill
#                               （纯后端项目可不加；前端占比高的项目建议加）
#
# 参数优先级（混用时）：显式参数 > --auto 扫描结果 > 默认值
#
# 环境变量：
#   HARNESS_TARGET_DIR          覆盖"项目根"推断（bootstrap.sh 场景下使用）
#                               未设时默认 = dirname(脚本)/..（对应直调场景）
#
# 行为：
#   1. 把 tier1-direct/（18 个通用 skill + SOP + learnings + 模板）移到项目根
#   2. 按 --include-frontend-design 可选移入 tier1-direct-optional/（2 个前端 skill）
#   3. 把 tier2-template/（AGENTS.md / RULES / dev.sh / 1 个项目特异 skill）移到项目根
#   4. 用 sed 替换所有 {{PLACEHOLDER}} 为参数值
#   5. 给 dev.sh 加可执行权限
#   6. 留下 .harness-starter-applied.log 记录
# ============================================================

set -euo pipefail

# --- 默认值 ---
PROJECT_NAME=""
TECH_STACK="springboot+vue"
MODULES=""
BACKEND_PACKAGE="com.example.app"
FRONTEND_DIR="../app-ui"
BACKEND_PORT="8080"
FRONTEND_PORT="5173"
JDK_IMAGE="gradle:8.12-jdk21"
PROJECT_DESC="Replace this with one-line project description"
APP_MAIN_CLASS="ApplicationStarter"
INCLUDE_FRONTEND_DESIGN=0   # --include-frontend-design 开启后把 D 的 2 个前端/UI skill 一起装上
AUTO=0                      # --auto：开启项目现场自动扫描
YES=0                       # --yes ：跳过交互直接采用扫描结果
DRY_RUN=0                   # --dry-run：只打印扫描结果后退出

# --- 记录用户显式传过的参数 key（用于后续 "显式 > 扫描 > 默认" 的优先级判定）---
declare -A EXPLICIT=()

# --- 解析参数 ---
for arg in "$@"; do
  case "$arg" in
    --project-name=*)          PROJECT_NAME="${arg#*=}";       EXPLICIT[PROJECT_NAME]=1 ;;
    --tech-stack=*)            TECH_STACK="${arg#*=}";         EXPLICIT[TECH_STACK]=1 ;;
    --modules=*)               MODULES="${arg#*=}";            EXPLICIT[MODULES]=1 ;;
    --backend-package=*)       BACKEND_PACKAGE="${arg#*=}";    EXPLICIT[BACKEND_PACKAGE]=1 ;;
    --frontend-dir=*)          FRONTEND_DIR="${arg#*=}";       EXPLICIT[FRONTEND_DIR]=1 ;;
    --backend-port=*)          BACKEND_PORT="${arg#*=}";       EXPLICIT[BACKEND_PORT]=1 ;;
    --frontend-port=*)         FRONTEND_PORT="${arg#*=}";      EXPLICIT[FRONTEND_PORT]=1 ;;
    --jdk-image=*)             JDK_IMAGE="${arg#*=}";          EXPLICIT[JDK_IMAGE]=1 ;;
    --project-desc=*)          PROJECT_DESC="${arg#*=}";       EXPLICIT[PROJECT_DESC]=1 ;;
    --app-main-class=*)        APP_MAIN_CLASS="${arg#*=}";     EXPLICIT[APP_MAIN_CLASS]=1 ;;
    --include-frontend-design) INCLUDE_FRONTEND_DESIGN=1 ;;
    --auto)                    AUTO=1 ;;
    --yes)                     YES=1 ;;
    --dry-run)                 DRY_RUN=1 ;;
    --help|-h)
      sed -n '2,52p' "$0"
      exit 0
      ;;
    *)
      echo "[ERROR] 未知参数：$arg"
      exit 1
      ;;
  esac
done

# --- 计算路径（提前到扫描前，供扫描模块定位用）---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${HARNESS_TARGET_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd)}"

# --- --auto 模式：扫描 + 交互式确认 ---
if [ "$AUTO" -eq 1 ]; then
  DETECT_SCRIPT="${SCRIPT_DIR}/scripts/detect-project.sh"
  if [ ! -f "$DETECT_SCRIPT" ]; then
    echo "[ERROR] 找不到 $DETECT_SCRIPT"
    echo "        --auto 模式需要 detect-project.sh，请确认安装包完整"
    exit 1
  fi

  # shellcheck disable=SC1090
  source "$DETECT_SCRIPT"

  echo "[auto] 扫描项目结构：$TARGET_DIR"
  echo ""

  # 扫描 → 输出 key=value 到临时变量
  # shellcheck disable=SC2046
  eval "$(detect_all "$TARGET_DIR" 2>/dev/null)"

  # 封装展示函数
  _show_scan_result() {
    local fmt="  %-3s %s  %-18s = %s\n"
    local i1="✅" i2="⚠️ " i3="❌"
    printf "$fmt" "1)" "$([ -n "$project_name" ]    && echo "$i1" || echo "$i3")" "project-name"    "${project_name:-(未扫到)}"
    printf "$fmt" "2)" "$([ -n "$modules" ]         && echo "$i1" || echo "$i3")" "modules"         "${modules:-(未扫到)}"
    printf "$fmt" "3)" "$([ -n "$backend_package" ] && echo "$i1" || echo "$i3")" "backend-package" "${backend_package:-(未扫到，默认 com.example.app)}"
    printf "$fmt" "4)" "$([ -n "$tech_stack" ]      && echo "$i1" || echo "$i3")" "tech-stack"      "${tech_stack:-(未扫到)}"
    printf "$fmt" "5)" "$([ -n "$app_main_class" ]  && echo "$i1" || echo "$i3")" "app-main-class"  "${app_main_class:-(未扫到，默认 ApplicationStarter)}"
    if [ "${frontend_status:-1}" = "0" ]; then
      printf "$fmt" "6)" "$i1" "frontend-dir" "$frontend_dir"
    elif [ "${frontend_status:-1}" = "2" ]; then
      printf "$fmt" "6)" "$i2" "frontend-dir" "$frontend_dir  ← 推断（目录未验证存在）"
    else
      printf "$fmt" "6)" "$i3" "frontend-dir" "(未扫到)"
    fi
    printf "$fmt" "7)" "$([ -n "$backend_port" ] && echo "$i1" || echo "$i3")" "backend-port"    "${backend_port:-(未扫到，默认 8080)}"
  }

  _show_scan_result

  # --dry-run：展示完就退出
  if [ "$DRY_RUN" -eq 1 ]; then
    echo ""
    echo "[auto] --dry-run 模式，不安装，扫描结果如上。"
    exit 0
  fi

  # --yes：跳过交互，直接采用
  if [ "$YES" -eq 0 ]; then
    while true; do
      echo ""
      read -r -p "确认：[回车] 接受并继续  [数字 1-7] 修改第 N 项  [q] 退出 > " choice
      case "$choice" in
        ''|y|Y)  break ;;
        q|Q)     echo "[auto] 用户取消安装"; exit 0 ;;
        1) read -r -p "  新 project-name: "    project_name ;;
        2) read -r -p "  新 modules (逗号分隔): " modules ;;
        3) read -r -p "  新 backend-package: " backend_package ;;
        4) read -r -p "  新 tech-stack (目前仅支持 springboot+vue): " tech_stack ;;
        5) read -r -p "  新 app-main-class: " app_main_class ;;
        6) read -r -p "  新 frontend-dir: "   frontend_dir;    frontend_status=0 ;;
        7) read -r -p "  新 backend-port: "   backend_port ;;
        *) echo "  (未识别的输入，请输入 1-7 / 回车 / q)" ;;
      esac
      echo ""
      _show_scan_result
    done
  fi

  # 把扫描结果合并到已声明变量（显式参数优先级最高）
  [ -z "${EXPLICIT[PROJECT_NAME]:-}" ]    && [ -n "$project_name" ]    && PROJECT_NAME="$project_name"
  [ -z "${EXPLICIT[MODULES]:-}" ]         && [ -n "$modules" ]         && MODULES="$modules"
  [ -z "${EXPLICIT[BACKEND_PACKAGE]:-}" ] && [ -n "$backend_package" ] && BACKEND_PACKAGE="$backend_package"
  [ -z "${EXPLICIT[TECH_STACK]:-}" ]      && [ -n "$tech_stack" ]      && TECH_STACK="$tech_stack"
  [ -z "${EXPLICIT[APP_MAIN_CLASS]:-}" ]  && [ -n "$app_main_class" ]  && APP_MAIN_CLASS="$app_main_class"
  [ -z "${EXPLICIT[FRONTEND_DIR]:-}" ]    && [ -n "$frontend_dir" ]    && FRONTEND_DIR="$frontend_dir"
  [ -z "${EXPLICIT[BACKEND_PORT]:-}" ]    && [ -n "$backend_port" ]    && BACKEND_PORT="$backend_port"
fi

# --- 校验必填 ---
if [ -z "$PROJECT_NAME" ] || [ -z "$MODULES" ]; then
  echo "[ERROR] 必填参数缺失：--project-name 和 --modules"
  echo "        提示：可以使用 --auto 让 init.sh 从项目现场自动扫描"
  echo "运行 bash $(basename "$0") --help 查看用法"
  exit 1
fi

if [ "$TECH_STACK" != "springboot+vue" ]; then
  echo "[ERROR] 当前阶段只支持 --tech-stack=springboot+vue"
  echo "其他栈请按 CUSTOMIZE.md 末尾的「自写指南」手动改造"
  exit 1
fi

# --- 路径已在 --auto 段提前计算好 ---
# SCRIPT_DIR / TARGET_DIR 已赋值（见上方）
# 项目根推断：
#   - 默认为 starter 的父目录（对应 "git clone 到 .harness-starter/" 场景）
#   - bootstrap.sh / install.sh 场景下 starter 被克隆/解压到 /tmp/，此时由
#     HARNESS_TARGET_DIR=<用户项目根> 覆盖默认推断
LOG_FILE="${TARGET_DIR}/.harness-starter-applied.log"

echo "========================================"
echo "  Harness Starter Init"
echo "========================================"
echo "  项目名     : $PROJECT_NAME"
echo "  技术栈     : $TECH_STACK"
echo "  模块列表   : $MODULES"
echo "  后端包名   : $BACKEND_PACKAGE"
echo "  前端目录   : $FRONTEND_DIR"
echo "  目标根目录 : $TARGET_DIR"
echo "========================================"

# --- 解析模块列表 ---
IFS=',' read -ra MODULE_ARR <<< "$MODULES"
MODULE_COUNT=${#MODULE_ARR[@]}

if [ "$MODULE_COUNT" -lt 5 ]; then
  echo "[WARN] 模块数 $MODULE_COUNT < 5，无法完整填充模板。建议至少 5 个模块（3 基础 + 1 业务 + 1 入口）。"
  echo "       将用占位字符串补齐。"
  while [ ${#MODULE_ARR[@]} -lt 5 ]; do
    MODULE_ARR+=("placeholder-$(( ${#MODULE_ARR[@]} + 1 ))")
  done
fi

# 简化分配：前 3 个为基础模块，第 4 个为业务模块 1，第 5 个为业务模块 2 / 入口模块
# （如果模块数 ≥ 6，最后一个作为入口模块）
BASE_MODULE_1="${MODULE_ARR[0]}"
BASE_MODULE_2="${MODULE_ARR[1]}"
BASE_MODULE_3="${MODULE_ARR[2]}"
BUSINESS_MODULE_1="${MODULE_ARR[3]}"
if [ "$MODULE_COUNT" -ge 6 ]; then
  BUSINESS_MODULE_2="${MODULE_ARR[4]}"
  ENTRY_MODULE="${MODULE_ARR[$((MODULE_COUNT - 1))]}"
else
  BUSINESS_MODULE_2="${MODULE_ARR[4]:-business2-placeholder}"
  ENTRY_MODULE="${MODULE_ARR[$((MODULE_COUNT - 1))]}"
fi

# 派生路径
BACKEND_ROOT="$TARGET_DIR"
FRONTEND_ROOT="$(cd "$TARGET_DIR" && cd "$FRONTEND_DIR" 2>/dev/null && pwd || echo "${TARGET_DIR}/${FRONTEND_DIR}")"

# --- 生成动态占位符内容（多行）---

# MODULES_SRC_PATHS: 给 dev.sh 的多个 _check 调用的路径列表
MODULES_SRC_PATHS_ARR=()
for m in "${MODULE_ARR[@]}"; do
  MODULES_SRC_PATHS_ARR+=("${m}/src/main/java")
done
MODULES_SRC_PATHS=$(IFS=' ' ; echo "${MODULES_SRC_PATHS_ARR[*]}")

# 默认前端 domain（4 个占位，由 CUSTOMIZE.md 提示用户调整）
DOMAIN_1="domain1"
DOMAIN_2="domain2"
DOMAIN_3="domain3"
DOMAIN_4="common"

# 关键业务表占位
KEY_TABLES="<table1>, <table2>, <table3>"

# --- 1. 移动 Tier 1 必装（直接拿来即用）---
# 逐文件复制：目标文件已存在则跳过（保留用户修改），不存在则写入
# 这样目录存在时也能合并，绝不覆盖已有文件
_merge_dir() {
  local src="$1" dst_parent="$2"
  local dst
  dst="${dst_parent}/$(basename "$src")"
  mkdir -p "$dst"
  local skipped=0 added=0
  while IFS= read -r -d '' f; do
    local rel="${f#${src}/}"
    local target="${dst}/${rel}"
    mkdir -p "$(dirname "$target")"
    if [ -f "$target" ]; then
      skipped=$((skipped + 1))
    else
      cp "$f" "$target"
      added=$((added + 1))
    fi
  done < <(find "$src" -type f -print0)
  if [ "$skipped" -gt 0 ]; then
    echo "  ℹ️  ${dst}：新增 ${added} 个文件，跳过 ${skipped} 个已存在文件（保留原内容）"
  fi
}

echo ""
echo "[1/3] 移动 Tier 1 必装文件..."
_merge_dir "${SCRIPT_DIR}/tier1-direct/.claude"              "${TARGET_DIR}"
_merge_dir "${SCRIPT_DIR}/tier1-direct/docs/agents"          "${TARGET_DIR}/docs"
_merge_dir "${SCRIPT_DIR}/tier1-direct/.learnings"           "${TARGET_DIR}"
mkdir -p "${TARGET_DIR}/openspec"
_merge_dir "${SCRIPT_DIR}/tier1-direct/openspec/templates"   "${TARGET_DIR}/openspec"
TIER1_COUNT=$(ls -1 "${TARGET_DIR}/.claude/skills" 2>/dev/null | wc -l)
echo "  ✅ Tier 1 必装已就位（${TIER1_COUNT} 个 skill）"

# --- 1b. Tier 1 可选（D：前端/UI 设计 skill）---
if [ "$INCLUDE_FRONTEND_DESIGN" -eq 1 ]; then
  echo "[1b/3] 移动 Tier 1 可选（前端/UI 设计 skill）..."
  if [ -d "${SCRIPT_DIR}/tier1-direct-optional/.claude/skills" ]; then
    for d in "${SCRIPT_DIR}/tier1-direct-optional/.claude/skills/"*/; do
      name="$(basename "$d")"
      if [ -e "${TARGET_DIR}/.claude/skills/${name}" ]; then
        echo "  ⚠️  ${name} 已存在，跳过"
      else
        cp -r "$d" "${TARGET_DIR}/.claude/skills/"
        echo "  ✅ ${name}"
      fi
    done
  fi
else
  echo "[1b/3] 跳过 Tier 1 可选（未加 --include-frontend-design；如需前端/UI 设计 skill，按 CUSTOMIZE.md §D 手动安装）"
fi

# --- 2. 复制 Tier 2（带占位符）---
echo ""
echo "[2/3] 移动 Tier 2 模板..."
for f in AGENTS.md BACKEND_RULES.md FRONTEND_RULES.md dev.sh docker-compose.dev.yml CUSTOMIZE.md; do
  if [ -e "${TARGET_DIR}/${f}" ]; then
    echo "  ⚠️  ${f} 已存在，跳过（参考 INSTALL.md Q2 手动合并）"
  else
    cp "${SCRIPT_DIR}/tier2-template/${f}" "${TARGET_DIR}/${f}"
    echo "  ✅ ${f}"
  fi
done

# 拷贝 harness-orchestrator skill 到 .claude/skills/
mkdir -p "${TARGET_DIR}/.claude/skills"
if [ -e "${TARGET_DIR}/.claude/skills/harness-orchestrator" ]; then
  echo "  ⚠️  .claude/skills/harness-orchestrator 已存在，跳过"
else
  cp -r "${SCRIPT_DIR}/tier2-template/.claude/skills/harness-orchestrator" \
     "${TARGET_DIR}/.claude/skills/"
  echo "  ✅ .claude/skills/harness-orchestrator"
fi

# --- 3. 占位符替换 ---
echo ""
echo "[3/3] 替换占位符..."

# 收集所有目标文件（避免对 .git / node_modules / vendor 等做替换）
TARGETS=$(find "${TARGET_DIR}" -type f \
  \( -name 'AGENTS.md' -o -name 'BACKEND_RULES.md' -o -name 'FRONTEND_RULES.md' \
     -o -name 'dev.sh' -o -name 'docker-compose.dev.yml' \
     -o -path '*/.claude/skills/harness-orchestrator/*' \) \
  2>/dev/null)

# 简单 sed 替换的占位符
declare -A REPLACE=(
  ["{{PROJECT_NAME}}"]="$PROJECT_NAME"
  ["{{PROJECT_DESC}}"]="$PROJECT_DESC"
  ["{{TECH_STACK}}"]="$TECH_STACK"
  ["{{BACKEND_PORT}}"]="$BACKEND_PORT"
  ["{{FRONTEND_PORT}}"]="$FRONTEND_PORT"
  ["{{BACKEND_ROOT}}"]="$BACKEND_ROOT"
  ["{{FRONTEND_ROOT}}"]="$FRONTEND_ROOT"
  ["{{FRONTEND_DIR}}"]="$FRONTEND_DIR"
  ["{{BACKEND_PACKAGE}}"]="$BACKEND_PACKAGE"
  ["{{JDK_IMAGE}}"]="$JDK_IMAGE"
  ["{{APP_MAIN_CLASS}}"]="$APP_MAIN_CLASS"
  ["{{BASE_MODULE_1}}"]="$BASE_MODULE_1"
  ["{{BASE_MODULE_2}}"]="$BASE_MODULE_2"
  ["{{BASE_MODULE_3}}"]="$BASE_MODULE_3"
  ["{{BUSINESS_MODULE_1}}"]="$BUSINESS_MODULE_1"
  ["{{BUSINESS_MODULE_2}}"]="$BUSINESS_MODULE_2"
  ["{{ENTRY_MODULE}}"]="$ENTRY_MODULE"
  ["{{DOMAIN_1}}"]="$DOMAIN_1"
  ["{{DOMAIN_2}}"]="$DOMAIN_2"
  ["{{DOMAIN_3}}"]="$DOMAIN_3"
  ["{{DOMAIN_4}}"]="$DOMAIN_4"
  ["{{MODULES_SRC_PATHS}}"]="$MODULES_SRC_PATHS"
  ["{{KEY_TABLES}}"]="$KEY_TABLES"
)

for f in $TARGETS; do
  for key in "${!REPLACE[@]}"; do
    val="${REPLACE[$key]}"
    # 转义 sed 特殊字符（/ & |）
    key_esc=$(printf '%s' "$key" | sed 's/[][\/.*^$]/\\&/g')
    val_esc=$(printf '%s' "$val" | sed 's/[\/&|]/\\&/g')
    sed -i "s|${key_esc}|${val_esc}|g" "$f" 2>/dev/null || true
  done
done

# --- 4. 给 dev.sh 加可执行权限 ---
[ -f "${TARGET_DIR}/dev.sh" ] && chmod +x "${TARGET_DIR}/dev.sh"

# --- 5. 写日志 ---
{
  echo "Harness Starter applied at $(date -Iseconds)"
  echo "PROJECT_NAME=$PROJECT_NAME"
  echo "TECH_STACK=$TECH_STACK"
  echo "MODULES=$MODULES"
  echo "BACKEND_PACKAGE=$BACKEND_PACKAGE"
  echo "FRONTEND_DIR=$FRONTEND_DIR"
  echo "INCLUDE_FRONTEND_DESIGN=$INCLUDE_FRONTEND_DESIGN"
  echo ""
  echo "Files placed:"
  echo "  AGENTS.md"
  echo "  BACKEND_RULES.md"
  echo "  FRONTEND_RULES.md"
  echo "  dev.sh"
  echo "  docker-compose.dev.yml"
  FINAL_SKILL_COUNT=$(ls -1 "${TARGET_DIR}/.claude/skills" 2>/dev/null | wc -l)
  echo "  .claude/skills/      (${FINAL_SKILL_COUNT} skills total)"
  echo "  docs/agents/         (session/verify/archive)"
  echo "  .learnings/          (索引 + 24 类 Tag + 3 类骨架)"
  echo "  openspec/templates/  (proposal/design/tasks/TRACE)"
} > "$LOG_FILE"

# --- 6. 自检：未替换的占位符 ---
echo ""
echo "[自检] 检测未替换的占位符..."
REMAINING=$(grep -rn '{{[A-Z_]\+}}' \
  "${TARGET_DIR}/AGENTS.md" \
  "${TARGET_DIR}/BACKEND_RULES.md" \
  "${TARGET_DIR}/FRONTEND_RULES.md" \
  "${TARGET_DIR}/dev.sh" \
  "${TARGET_DIR}/docker-compose.dev.yml" \
  "${TARGET_DIR}/.claude/skills/harness-orchestrator/SKILL.md" \
  2>/dev/null | grep -v '^$' || true)

if [ -n "$REMAINING" ]; then
  echo "  ⚠️  以下占位符未被替换（init.sh 没覆盖到，按 CUSTOMIZE.md 手动改）："
  echo "$REMAINING" | sed 's/^/      /'
else
  echo "  ✅ 所有 init.sh 范围内的占位符已替换"
fi

echo ""
echo "========================================"
echo "  Harness Starter 安装完成"
echo "========================================"
echo ""
echo "下一步（选一）："
echo ""
echo "  🟢 推荐 · 让 AI 帮你做完剩下的（1-3 分钟）："
echo "     在 Cursor / Claude Code 里打开此项目，发送："
echo "       请用 harness-install-finisher 完成剩余配置"
echo "     它会：扫代码自动填 AUTO 字段 → AskQuestion 收集产品语义字段"
echo "         → 跑 check --arch 基线 → 给 commit message 建议（不代提交）"
echo ""
echo "  🟡 手工路径（10-20 分钟）："
echo "     1. cat .harness-starter-applied.log     （查看清单）"
echo "     2. 按 CUSTOMIZE.md 逐项改 🔴 必改字段"
echo "     3. bash dev.sh check --arch             （首次跑确认基线）"
# bootstrap 场景下 starter 在 /tmp 且由 bootstrap trap 自动清理，用户项目根本无 .harness-starter
if [ -z "${HARNESS_TARGET_DIR:-}" ]; then
  echo ""
  echo "  清理（通用）："
  echo "     rm -rf .harness-starter                （清理起步包目录）"
fi
echo ""
