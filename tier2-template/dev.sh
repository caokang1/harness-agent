#!/usr/bin/env bash
# ============================================================
# {{PROJECT_NAME}} 开发辅助脚本
#
# 来源：harness-starter / Tier 2 模板
# 用法：
#   bash dev.sh start            # 启动开发容器
#   bash dev.sh reload           # 热重载后端（编译 + DevTools 重启）
#   bash dev.sh restart          # 完整重启（改配置/依赖后用）
#   bash dev.sh compile          # 仅编译（用于检查编译错误）
#   bash dev.sh check [--arch]   # 编译 + 架构规则检查；--arch 仅跑硬规则
#   bash dev.sh test             # 容器内运行测试
#   bash dev.sh logs [be|fe]     # 查看实时日志
#   bash dev.sh stop             # 停止容器
#   bash dev.sh verify-snapshot [before|after|diff]
# ============================================================

set -euo pipefail

COMPOSE_FILE="docker-compose.dev.yml"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACTION="${1:-help}"
# 下面的路径（compose 文件、模块目录、源码目录）都相对项目根：从任何目录运行都先切过去
cd "$SCRIPT_DIR"

# 项目特异配置（init.sh 替换占位符）
BACKEND_SERVICE="{{PROJECT_NAME}}-dev"
FRONTEND_SERVICE="{{PROJECT_NAME}}-ui-dev"
FRONTEND_DIR="{{FRONTEND_DIR}}"       # 相对项目根，或绝对路径
case "$FRONTEND_DIR" in /*) ;; *) FRONTEND_DIR="${SCRIPT_DIR}/${FRONTEND_DIR}" ;; esac
APP_MAIN_CLASS="{{APP_MAIN_CLASS}}"   # 例：MyServiceApplication（用于 logs 检测启动成功）
BUILD_TOOL="{{BUILD_TOOL}}"           # gradle 或 maven

# 模块分工（check --arch 用，空格分隔；按 BACKEND_RULES.md §模块依赖方向 调整）
BASE_MODULES="{{BASE_MODULES}}"          # 基础模块，自下而上：只能依赖排在它前面的基础模块
BUSINESS_MODULES="{{BUSINESS_MODULES}}"  # 业务模块：互相不能依赖，只能依赖基础模块
SRC_PATHS="{{MODULES_SRC_PATHS}}"        # 扫描 Java 源码的目录
FRONTEND_DOMAINS="{{DOMAINS}}"           # 前端 src/views/ 下的业务域目录

ERRORS_FOUND=0

check_deps() {
  if ! command -v docker &>/dev/null; then
    echo "[ERROR] 未找到 docker，请先安装 Docker"
    exit 1
  fi
}

# 在后端容器里构建：$1 = compile | test，其余参数原样传给构建工具
_build() {
  local action="$1"; shift
  local cmd
  case "$BUILD_TOOL:$action" in
    maven:compile)  cmd=(mvn -B compile) ;;
    maven:test)     cmd=(mvn -B test) ;;
    gradle:compile) cmd=(gradle compileJava --no-daemon) ;;
    gradle:test)    cmd=(gradle test --no-daemon) ;;
    *) echo "[ERROR] 不支持的构建工具 $BUILD_TOOL（dev.sh 顶部 BUILD_TOOL 只能是 gradle 或 maven）"; exit 1 ;;
  esac
  docker compose -f "${COMPOSE_FILE}" exec -T "${BACKEND_SERVICE}" "${cmd[@]}" "$@"
}

case "$ACTION" in

  start|up)
    check_deps
    echo "========================================"
    echo "  启动 {{PROJECT_NAME}} 开发容器"
    echo "========================================"
    docker compose -f "${COMPOSE_FILE}" up -d
    echo ""
    echo "容器已启动："
    echo "  后端 : http://localhost:{{BACKEND_PORT}}"
    echo "  前端 : http://localhost:{{FRONTEND_PORT}}"
    ;;

  reload)
    check_deps
    echo "[reload] 编译后端..."
    _build compile -q
    echo "[reload] DevTools 将在 ~5-15s 内自动重启。tail logs 验证："
    echo "  bash dev.sh logs backend"
    ;;

  restart)
    check_deps
    docker compose -f "${COMPOSE_FILE}" stop "${BACKEND_SERVICE}"
    docker compose -f "${COMPOSE_FILE}" start "${BACKEND_SERVICE}"
    ;;

  compile)
    check_deps
    _build compile
    ;;

  check)
    check_deps
    CHECK_MODE="${2:---all}"

    # ====================================================
    # Java 编译检查
    # ====================================================
    run_java_check() {
      echo "[Java] 编译检查..."
      if _build compile -q 2>&1; then
        echo "✅ [Java] 编译通过"
      else
        echo "❌ [Java] 编译失败"
        ERRORS_FOUND=1
      fi
    }

    # ====================================================
    # 仅检查 git diff 涉及的文件（轻量）
    # ====================================================
    run_changed_check() {
      local changed
      changed=$(git diff --name-only --diff-filter=ACM HEAD 2>/dev/null | grep -E '\.java$' || true)
      if [ -z "$changed" ]; then
        echo "[Changed] 无改动 Java 文件，跳过"
        return
      fi
      echo "[Changed] 改动文件：$changed"
      run_java_check
    }

    # ====================================================
    # 架构/规则硬门槛扫描
    # 基线：下列规则全部为 0 命中。
    # 任何新命中 = 回归，必须修复后再 commit。
    # 规则来源：BACKEND_RULES.md + FRONTEND_RULES.md
    # ====================================================
    run_arch_check() {
      local arch_errors=0

      echo ""
      echo "[Arch] BACKEND_RULES.md 硬规则扫描..."

      local skipped=0

      # 输出一条规则的结果。第 3 个参数非空 = 没法检查（路径不存在等），
      # 明确标成"跳过"，不能当成"无违规"，否则门禁会悄悄失效
      _result() {
        local name="$1" hit="$2" skip_reason="${3:-}"
        if [ -n "$skip_reason" ]; then
          echo "  ⚠️  [$name] 跳过：$skip_reason"
          skipped=$((skipped + 1))
        elif [ -n "$hit" ]; then
          echo "  ❌ [$name] 发现违规："
          echo "$hit" | sed 's/^/      /'
          arch_errors=$((arch_errors + 1))
          ERRORS_FOUND=1
        else
          echo "  ✅ [$name] 无违规"
        fi
      }

      # 模块的构建文件：Gradle（Groovy / Kotlin DSL）或 Maven
      _build_file() {
        local f
        for f in "$1/build.gradle" "$1/build.gradle.kts" "$1/pom.xml"; do
          [ -f "$f" ] && { echo "$f"; return 0; }
        done
        return 1
      }

      # 在构建文件里找对 $2.. 这些模块的依赖
      _dep_hits() {
        local file="$1" m; shift
        for m in "$@"; do
          case "$file" in
            *.xml)  # 只看 <dependencies> 里的 artifactId（嵌套模块 a/x 的 artifactId 一般是 x）
              awk '/<dependencies>/{d=1} d{print FILENAME":"FNR": "$0} /<\/dependencies>/{d=0}' "$file" \
                | grep -E "<artifactId>${m##*/}</artifactId>" || true ;;
            *)      # project(':m') / project(":m")，implementation / api / compileOnly 都算；嵌套模块目录 a/x 对应 :a:x
              grep -nE "project\([\"']:${m//\//:}[\"']\)" "$file" | sed "s|^|${file}:|" || true ;;
          esac
        done
      }

      # 依赖检查：$1 规则名，$2 被检查的模块，$3 每个模块禁止依赖的模块（函数名，参数是模块名）
      _check_deps() {
        local name="$1" modules="$2" forbidden_fn="$3"
        local m bf hits="" missing="" checked=0
        if [ -z "$modules" ]; then
          _result "$name" "" "没有需要检查的模块（dev.sh 顶部的模块配置为空）"
          return
        fi
        for m in $modules; do
          if ! bf=$(_build_file "$m"); then
            missing="${missing:+$missing, }$m"
            continue
          fi
          checked=$((checked + 1))
          local h
          # shellcheck disable=SC2046
          h=$(_dep_hits "$bf" $("$forbidden_fn" "$m"))
          [ -n "$h" ] && hits="${hits:+$hits$'\n'}$h"
        done
        [ -n "$missing" ] && echo "  ⚠️  [$name] 找不到构建文件（build.gradle / build.gradle.kts / pom.xml）：$missing"
        if [ "$checked" -eq 0 ]; then
          _result "$name" "" "所有模块都找不到构建文件"
        else
          _result "$name" "$hits"
        fi
      }

      _other_business() { local b; for b in $BUSINESS_MODULES; do [ "$b" != "$1" ] && echo "$b"; done; true; }
      _base_forbidden() {  # 业务模块 + 排在它后面的基础模块
        local b seen=0
        echo "$BUSINESS_MODULES"
        for b in $BASE_MODULES; do
          [ "$seen" -eq 1 ] && echo "$b"
          [ "$b" = "$1" ] && seen=1
        done
        true
      }

      # 源码扫描：只扫存在的目录；一个都不存在就标成跳过
      _check_src() {
        local name="$1"; shift
        local p dirs=""
        for p in $SRC_PATHS; do [ -d "$p" ] && dirs="$dirs $p"; done
        if [ -z "$dirs" ]; then
          _result "$name" "" "源码目录都不存在（$SRC_PATHS）"
          return
        fi
        # shellcheck disable=SC2086
        _result "$name" "$("$@" $dirs 2>/dev/null || true)"
      }

      # --- 依赖方向（BACKEND_RULES.md §模块依赖方向） ---
      if [ "$(echo $BUSINESS_MODULES | wc -w)" -lt 2 ]; then
        _result "dep-business-cross" "" "业务模块少于 2 个，无需检查"
      else
        _check_deps "dep-business-cross" "$BUSINESS_MODULES" _other_business
      fi
      _check_deps "dep-base-to-business" "$BASE_MODULES" _base_forbidden

      # --- 依赖注入（BACKEND_RULES.md §依赖注入与 Lombok） ---
      _check_src "autowired-field-injection" grep -rn --include='*.java' '@Autowired'

      # --- 异常契约（BACKEND_RULES.md §异常与响应契约） ---
      _check_src "runtime-exception-in-business" grep -rn --include='*.java' 'throw new RuntimeException'

      # --- 时间类型（BACKEND_RULES.md §时间类型约定） ---
      _check_src "legacy-date-api" grep -rnE --include='*.java' 'new Date\(\)|new SimpleDateFormat'

      # --- 前端跨域 import（FRONTEND_RULES.md §文件职责边界） ---
      echo ""
      echo "[Arch] FRONTEND_RULES.md 跨域 import 扫描..."
      if [ ! -d "$FRONTEND_DIR/src/views" ]; then
        echo "  ⚠️  [frontend-cross-domain] 未找到前端仓库（$FRONTEND_DIR），跳过"
      else
        local fe_hits=""
        # CUSTOMIZE: 把 domain 列表换成你前端 views/ 下的实际目录名
        for d in $FRONTEND_DOMAINS; do
          for other in $FRONTEND_DOMAINS; do
            [ "$d" = "$other" ] && continue
            [ ! -d "$FRONTEND_DIR/src/views/$d" ] && continue
            local h
            h=$(grep -rn --include='*.vue' --include='*.js' --include='*.ts' \
                  "from ['\"].*views/$other/" "$FRONTEND_DIR/src/views/$d/" 2>/dev/null || true)
            if [ -n "$h" ]; then
              fe_hits+="[$d → $other]\n$h\n"
            fi
          done
        done
        if [ -n "$fe_hits" ]; then
          echo "  ❌ [frontend-cross-domain] 发现跨域 import："
          printf "%b" "$fe_hits" | sed 's/^/      /'
          arch_errors=$((arch_errors + 1))
          ERRORS_FOUND=1
        else
          echo "  ✅ [frontend-cross-domain] 无跨域 import"
        fi
      fi

      # --- 遗留 .harness-starter/ 目录检测 ---
      # Harness Starter 独立仓库化后，装完应立即 rm -rf .harness-starter。
      # 如果还留着，说明安装流程没走完，提醒但不阻塞构建。
      if [ -d "${SCRIPT_DIR}/.harness-starter" ]; then
        echo ""
        echo "  ⚠️  [starter-leftover] 发现 .harness-starter/ 残留目录"
        echo "      starter 装完后应该删除（参见 .harness-starter/INSTALL.md 第 5 步）："
        echo "      rm -rf .harness-starter"
      fi

      echo ""
      if [ "$skipped" -gt 0 ]; then
        echo "⚠️  [Arch] 有 $skipped 项检查被跳过，没有真正检查。请核对 dev.sh 顶部的模块配置。"
      fi
      if [ $arch_errors -eq 0 ]; then
        echo "✅ [Arch] 已检查的架构规则全部通过（基线）"
      else
        echo "❌ [Arch] 发现 $arch_errors 项违规"
        echo ""
        echo "💡 修复建议："
        echo "   - 依赖违规 → 按 BACKEND_RULES.md §模块依赖方向 走 DIP"
        echo "   - @Autowired → 改为 @RequiredArgsConstructor + final 字段"
        echo "   - RuntimeException → 改为 BusinessException(BizErrorCode.XXX, ...)"
        echo "   - new Date() / SimpleDateFormat → LocalDateTime / DateTimeFormatter"
        echo "   - 前端跨域 import → 抽到 src/components/ 或 src/composables/"
      fi
    }

    case "$CHECK_MODE" in
      --java)    run_java_check ;;
      --changed) run_changed_check ;;
      --arch)    run_arch_check ;;
      --all|*)   run_java_check; run_arch_check ;;
    esac

    if [ $ERRORS_FOUND -ne 0 ]; then
      exit 1
    fi
    ;;

  test)
    check_deps
    _build test "${@:2}"
    ;;

  logs)
    check_deps
    SERVICE="${2:-backend}"
    case "$SERVICE" in
      backend|be) SVC="${BACKEND_SERVICE}" ;;
      frontend|fe) SVC="${FRONTEND_SERVICE}" ;;
      *) SVC="$SERVICE" ;;
    esac
    docker compose -f "${COMPOSE_FILE}" logs -f --tail=100 "${SVC}"
    ;;

  stop|down)
    check_deps
    docker compose -f "${COMPOSE_FILE}" down
    ;;

  verify-snapshot)
    # CUSTOMIZE: 这里是占位实现。按你的项目改：
    #   1. 列出关键业务表（5~15 张）
    #   2. before：dump 当前状态（行数 + sample 关键字段）到 .harness/verify-snapshots/before.txt
    #   3. after：dump 同样 schema 到 after.txt
    #   4. diff：对比并输出 delta
    # 详见 docs/agents/verify.md §verify-snapshot
    PHASE="${2:-help}"
    case "$PHASE" in
      before|after|diff)
        echo "[verify-snapshot] $PHASE"
        echo "⚠️  这是 starter 的占位实现。按 docs/agents/verify.md 自己实现。"
        echo "    关键业务表清单（CUSTOMIZE）：{{KEY_TABLES}}"
        ;;
      *)
        echo "用法：bash dev.sh verify-snapshot [before|after|diff]"
        ;;
    esac
    ;;

  help|*)
    sed -n '3,16p' "$0"
    ;;
esac

exit ${ERRORS_FOUND}
