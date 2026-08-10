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

# 项目特异配置（init.sh 替换占位符）
BACKEND_SERVICE="{{PROJECT_NAME}}-dev"
FRONTEND_SERVICE="{{PROJECT_NAME}}-ui-dev"
FRONTEND_DIR="${SCRIPT_DIR}/{{FRONTEND_DIR}}"
APP_MAIN_CLASS="{{APP_MAIN_CLASS}}"   # 例：MyServiceApplication（用于 logs 检测启动成功）

ERRORS_FOUND=0

check_deps() {
  if ! command -v docker &>/dev/null; then
    echo "[ERROR] 未找到 docker，请先安装 Docker"
    exit 1
  fi
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
    docker compose -f "${COMPOSE_FILE}" exec -T "${BACKEND_SERVICE}" \
      gradle compileJava --no-daemon -q
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
    docker compose -f "${COMPOSE_FILE}" exec -T "${BACKEND_SERVICE}" \
      gradle compileJava --no-daemon
    ;;

  check)
    check_deps
    CHECK_MODE="${2:---all}"

    # ====================================================
    # Java 编译检查
    # ====================================================
    run_java_check() {
      echo "[Java] 编译检查..."
      if docker compose -f "${COMPOSE_FILE}" exec -T "${BACKEND_SERVICE}" \
            gradle compileJava --no-daemon -q 2>&1; then
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

      _check() {
        local name="$1"; shift
        local hit; hit=$("$@" 2>/dev/null || true)
        if [ -n "$hit" ]; then
          echo "  ❌ [$name] 发现违规："
          echo "$hit" | sed 's/^/      /'
          arch_errors=$((arch_errors + 1))
          ERRORS_FOUND=1
        else
          echo "  ✅ [$name] 无违规"
        fi
      }

      # --- 依赖方向（BACKEND_RULES.md §模块依赖方向） ---
      # CUSTOMIZE: 把模块名换成你项目的业务模块 / 基础模块
      _check "dep-business-cross" \
        grep -E "implementation project\(':({{BUSINESS_MODULE_1}}|{{BUSINESS_MODULE_2}})'\)" \
          {{BUSINESS_MODULE_1}}/build.gradle {{BUSINESS_MODULE_2}}/build.gradle

      _check "dep-base-to-business" \
        grep -E "implementation project\(':({{BUSINESS_MODULE_1}}|{{BUSINESS_MODULE_2}}|{{BASE_MODULE_3}})'\)" \
          {{BASE_MODULE_1}}/build.gradle {{BASE_MODULE_2}}/build.gradle

      # --- 依赖注入（BACKEND_RULES.md §依赖注入与 Lombok） ---
      _check "autowired-field-injection" \
        grep -rn --include='*.java' '@Autowired' \
          {{MODULES_SRC_PATHS}}

      # --- 异常契约（BACKEND_RULES.md §异常与响应契约） ---
      _check "runtime-exception-in-business" \
        grep -rn --include='*.java' 'throw new RuntimeException' \
          {{MODULES_SRC_PATHS}}

      # --- 时间类型（BACKEND_RULES.md §时间类型约定） ---
      _check "legacy-date-api" \
        grep -rnE --include='*.java' 'new Date\(\)|new SimpleDateFormat' \
          {{MODULES_SRC_PATHS}}

      # --- 前端跨域 import（FRONTEND_RULES.md §文件职责边界） ---
      echo ""
      echo "[Arch] FRONTEND_RULES.md 跨域 import 扫描..."
      if [ ! -d "$FRONTEND_DIR/src/views" ]; then
        echo "  ⚠️  [frontend-cross-domain] 未找到前端仓库（$FRONTEND_DIR），跳过"
      else
        local fe_hits=""
        # CUSTOMIZE: 把 domain 列表换成你前端 views/ 下的实际目录名
        for d in {{DOMAIN_1}} {{DOMAIN_2}} {{DOMAIN_3}} {{DOMAIN_4}}; do
          for other in {{DOMAIN_1}} {{DOMAIN_2}} {{DOMAIN_3}} {{DOMAIN_4}}; do
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
      if [ $arch_errors -eq 0 ]; then
        echo "✅ [Arch] 架构规则全部通过（基线）"
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
    docker compose -f "${COMPOSE_FILE}" exec -T "${BACKEND_SERVICE}" \
      gradle test --no-daemon "${@:2}"
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
