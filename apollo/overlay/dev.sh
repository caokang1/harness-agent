#!/usr/bin/env bash
# ============================================================
# {{AP_PROJECT_SLUG}} 开发辅助脚本
#
# 来源：harness-starter / Tier 2 模板（已按本项目改造：Maven 多模块 + Java 8 + 微服务）
# 用法：
#   bash dev.sh compile [模块...]      # 本地 mvn 编译；不传模块时编译本分支改动涉及的模块
#   bash dev.sh check [--arch|--java|--changed|--all]
#                                      # --arch 仅跑架构硬规则（不需要 Maven/Docker）
#   bash dev.sh test <模块> [mvn 参数]   # 本地 mvn test
#   bash dev.sh verify-snapshot [before|after|diff]
#   bash dev.sh start|reload|restart|logs|stop
#                                      # 本项目不使用容器开发，见下方说明
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"
ACTION="${1:-help}"

# 项目特异配置
# 基线分支：新增代码 = 相对它的 merge-base 新增。留空则在主干与各国分支中自动选离 HEAD 最近的一个，
# 也可手动指定：BASE_REF=origin/{{AP_CC_BRANCH}} bash dev.sh check --arch
BASE_REF="${BASE_REF:-}"
BASE_CANDIDATES="{{AP_MAIN_BRANCH}} {{AP_SUBLINE_BRANCH}} $(printf 'master_%s ' {{AP_COUNTRY_CODES_EXT}})"
JDK8_HOME="${JDK8_HOME:-$HOME/.local/jdk8}"  # 项目要求 Java 8；存在时 mvn 固定用它
FRONTEND_DIR="${SCRIPT_DIR}/../{{AP_NS}}-admin-ui"   # 本项目无前端仓库，前端检测会自动跳过

# 基础层模块（不得依赖业务服务）
BASE_POMS="{{AP_MOD_FRAMEWORK}}/pom.xml {{AP_MOD_COMMONS}}/pom.xml {{AP_MOD_API}}/pom.xml {{AP_MOD_MQ}}/pom.xml {{AP_MOD_SCHEDULE}}/pom.xml"
# 业务服务目录（横向只走 Feign）
BUSINESS_SERVICES="gateway {{AP_SVC_OPEN}} {{AP_SVC_AUTH}} {{AP_SVC_USER}} {{AP_SVC_LOAN}} {{AP_SVC_PAYMENT}} {{AP_SVC_REPAY}} collection {{AP_SVC_STAT}} {{AP_SVC_TABLE}} {{AP_SVC_ADMIN}} {{AP_SVC_MIGRATE}} {{AP_SVC_TOOL}}"
# 业务服务自身的 artifactId（区分大小写：{{AP_API_OPEN}} 是 Feign 接口包，id-{{AP_SVC_OPEN}} 是服务）
SERVICE_ARTIFACTS="{{AP_SVC_ADMIN}} {{AP_SVC_STAT}} {{AP_SVC_TABLE}} {{AP_ART_COLLECTION}} gateway id-{{AP_SVC_AUTH}} id-{{AP_SVC_LOAN}} id-{{AP_SVC_OPEN}} id-{{AP_SVC_PAYMENT}} id-{{AP_SVC_REPAY}} id-{{AP_SVC_USER}} {{AP_SVC_MIGRATE}} {{AP_SVC_TOOL}}"
# verify-snapshot 关键业务表
KEY_TABLES="{{AP_KEY_TABLES}}"

ERRORS_FOUND=0

if [ -x "${JDK8_HOME}/bin/javac" ]; then
  export JAVA_HOME="${JDK8_HOME}"
  export PATH="${JAVA_HOME}/bin:${PATH}"
fi

# 在候选基线（远端分支）里选 HEAD 领先提交数最少的一个
detect_base_ref() {
  local best="" best_n="" c n
  for c in ${BASE_CANDIDATES}; do
    git rev-parse -q --verify "origin/${c}" >/dev/null || continue
    n=$(git rev-list --count "origin/${c}..HEAD" 2>/dev/null) || continue
    if [ -z "$best_n" ] || [ "$n" -lt "$best_n" ]; then
      best="origin/${c}"; best_n="$n"
    fi
  done
  echo "${best:-{{AP_MAIN_BRANCH}}}"
}
[ -n "${BASE_REF}" ] || BASE_REF="$(detect_base_ref)"

require_mvn() {
  if ! command -v mvn &>/dev/null; then
    echo "[ERROR] 未找到 mvn，请先安装 Maven 并配置 JDK 8"
    exit 1
  fi
  if ! java -version 2>&1 | grep -q '"1\.8\.'; then
    echo "[WARN] 当前 java 不是 1.8（JAVA_HOME=${JAVA_HOME:-未设置}），可把 JDK 8 解压到 ${JDK8_HOME}"
  fi
}

# 本分支相对主干新增/改动的文件（含未提交、未跟踪）
changed_files() {
  local filter="$1" base
  base=$(git merge-base HEAD "${BASE_REF}" 2>/dev/null || echo HEAD)
  {
    git diff --name-only --diff-filter="${filter}" "${base}" 2>/dev/null || true
    git ls-files --others --exclude-standard 2>/dev/null || true
  } | sort -u
}

# 新增的主代码 Java 文件（存量代码不追溯）
new_java_files() {
  changed_files A | grep -E '/src/main/java/.*\.java$' || true
}

# 改动涉及的顶层模块（含 pom.xml 的一级目录）
changed_modules() {
  changed_files ACMR | awk -F/ 'NF>1{print $1}' | sort -u | while read -r m; do
    [ -f "${m}/pom.xml" ] && echo "$m"
  done
}

# 读取 pom.xml 的 <dependencies> 里声明的 artifactId（跳过 dependencyManagement 与 parent）
pom_deps() {
  tr -d '\r' < "$1" | awk '
    /<dependencyManagement>/ {dm=1}
    /<\/dependencyManagement>/ {dm=0; next}
    /<parent>/ {pa=1}
    /<\/parent>/ {pa=0; next}
    dm || pa {next}
    /<dependencies>/ {deps=1}
    /<\/dependencies>/ {deps=0}
    deps && /<artifactId>/ {
      gsub(/.*<artifactId>|<\/artifactId>.*/, ""); print
    }'
}

# 列出某个 pom 依赖了哪些业务服务 artifact
pom_service_deps() {
  local pom="$1" a s
  for a in $(pom_deps "$pom"); do
    for s in $SERVICE_ARTIFACTS; do
      [ "$a" = "$s" ] && echo "${pom}: ${a}"
    done
  done
}

compile_modules() {
  require_mvn
  local mods=("$@")
  if [ ${#mods[@]} -eq 0 ]; then
    mapfile -t mods < <(changed_modules)
  fi
  if [ ${#mods[@]} -eq 0 ]; then
    echo "[Java] 本分支无改动模块，跳过编译"
    return 0
  fi
  # ~/.m2 里的 commons / API jar 可能是别的分支装的，先按本分支源码重装（SKIP_API_INSTALL=1 跳过）
  if [ "${SKIP_API_INSTALL:-0}" != "1" ]; then
    local base_mod
    for base_mod in {{AP_MOD_COMMONS}} {{AP_MOD_API}}; do
      [ -f "${base_mod}/pom.xml" ] || continue
      echo "[Java] 安装 ${base_mod}（本分支源码）..."
      if ! (cd "${base_mod}" && mvn -q -DskipTests install); then
        echo "❌ [Java] ${base_mod} 安装失败"
        ERRORS_FOUND=1
        return 0
      fi
    done
  fi
  local m out
  for m in "${mods[@]}"; do
    echo "[Java] 编译 ${m} ..."
    if out=$(cd "${m}" && mvn -q -DskipTests compile 2>&1); then
      echo "✅ [Java] ${m} 编译通过"
    elif echo "$out" | grep -q 'maven-resources-plugin.*MalformedInputException'; then
      # 既有资源文件编码不是 UTF-8 导致过滤失败（如 {{AP_SVC_TABLE}} 的 message_zh_CN.properties），与 Java 代码无关
      echo "⚠️  [Java] ${m} 资源过滤失败（既有文件编码问题），跳过资源只编译 Java："
      echo "$out" | grep -o 'filtering [^ ]* ' | head -1 | sed 's/^/      /'
      if (cd "${m}" && mvn -q -DskipTests -Dmaven.resources.skip=true compile); then
        echo "✅ [Java] ${m} Java 编译通过（资源已跳过）"
      else
        echo "❌ [Java] ${m} 编译失败"
        ERRORS_FOUND=1
      fi
    else
      echo "$out" | grep -E '\[ERROR\]' | head -20
      echo "❌ [Java] ${m} 编译失败"
      ERRORS_FOUND=1
    fi
  done
}

case "$ACTION" in

  start|up|reload|restart|logs|stop|down)
    echo "本项目不使用容器开发环境（docker-compose.dev.yml 仅为参考模板）。"
    echo "本地启动单个服务：cd <服务目录> && mvn spring-boot:run（需要 Nacos 运行以加载配置）"
    echo "全量构建顺序：{{AP_MOD_FRAMEWORK}} -> {{AP_MOD_COMMONS}} -> {{AP_MOD_API}} -> 各服务"
    ;;

  compile)
    compile_modules "${@:2}"
    ;;

  check)
    CHECK_MODE="${2:---all}"
    echo "[base] 基线分支 ${BASE_REF}（merge-base $(git merge-base HEAD "${BASE_REF}" 2>/dev/null | cut -c1-10)）"

    # ====================================================
    # 架构/规则硬门槛扫描
    # 基线：下列规则全部为 0 命中。
    # 代码类规则只扫本分支新增的 Java 文件（存量代码不追溯）。
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
      _dep_business_cross() {
        local s
        for s in $BUSINESS_SERVICES; do
          [ -f "${s}/pom.xml" ] && pom_service_deps "${s}/pom.xml"
        done
      }
      _dep_base_to_business() {
        local p
        for p in $BASE_POMS {{AP_MOD_API}}/*/pom.xml; do
          [ -f "$p" ] && pom_service_deps "$p"
        done
      }
      _check "dep-business-cross" _dep_business_cross
      _check "dep-base-to-business" _dep_base_to_business

      # --- 代码类规则：只扫新增 Java 文件 ---
      local new_files
      new_files=$(new_java_files)
      if [ -z "$new_files" ]; then
        echo "  ℹ️  本分支相对 ${BASE_REF} 无新增 Java 文件，代码类规则无扫描对象"
      fi
      _grep_new() {
        [ -z "$new_files" ] && return 0
        echo "$new_files" | tr '\n' '\0' | xargs -0 grep -HnE "$1" 2>/dev/null || true
      }

      # 依赖注入（BACKEND_RULES.md §依赖注入与 Lombok）
      _check "autowired-field-injection" _grep_new '@Autowired'

      # 异常契约（BACKEND_RULES.md §异常与响应契约）
      _check "runtime-exception-in-business" _grep_new 'throw new RuntimeException'

      # 时间类型（BACKEND_RULES.md §时间类型约定）
      _check "legacy-date-api" _grep_new 'new Date\(\)|new SimpleDateFormat'

      # --- 存量文件改造纪律（CLAUDE.md「存量代码改造纪律」）：只追加或 1-3 行插入，不整体改写 ---
      local merge_base
      merge_base=$(git merge-base HEAD "${BASE_REF}" 2>/dev/null || echo HEAD)
      # 存量文件被大面积改写（换行符翻转、格式化）：改动行数超过文件的一半
      _legacy_rewrite() {
        git diff --numstat "$merge_base" --diff-filter=M -- '*.java' '*.xml' '*.md' '*.json' '*.yml' '*.properties' 2>/dev/null |
        while read -r add del f; do
          [ "$add" = "-" ] && continue
          local total; total=$(git show "${merge_base}:${f}" 2>/dev/null | wc -l)
          [ "$total" -gt 20 ] && [ $((del * 2)) -gt "$total" ] && echo "${f}: -${del}/${total} 行，疑似整体改写（换行符或格式化）"
        done
      }
      # 同一文件里 CRLF 和 LF 混用（脚本按文本模式写回 CRLF 文件时常见）
      _mixed_endings() {
        git diff --name-only "$merge_base" --diff-filter=AM 2>/dev/null | while read -r f; do
          [ -f "$f" ] || continue
          local lines crs; lines=$(wc -l < "$f"); crs=$(tr -cd '\r' < "$f" | wc -c)
          [ "$crs" -gt 0 ] && [ "$crs" -ne "$lines" ] && echo "${f}: ${crs}/${lines} 行是 CRLF"
        done
      }
      _check "legacy-rewrite" _legacy_rewrite
      _check "mixed-line-endings" _mixed_endings
      # 存量文件里有删除：不一定违规（1-3 行替换允许），列出来逐个确认
      local legacy_del
      legacy_del=$(git diff --numstat "$merge_base" --diff-filter=M 2>/dev/null | awk '$2 != "-" && $2 > 0 {print "      " $3 ": -" $2}')
      if [ -n "$legacy_del" ]; then
        echo "  ⚠️  [legacy-deletions] 存量文件有删除行，确认都是 1-3 行替换、不是顺手删改："
        echo "$legacy_del"
      fi

      # --- 前端跨域 import（FRONTEND_RULES.md §文件职责边界） ---
      echo ""
      echo "[Arch] FRONTEND_RULES.md 跨域 import 扫描..."
      if [ ! -d "$FRONTEND_DIR/src/views" ]; then
        echo "  ⚠️  [frontend-cross-domain] 本项目无前端仓库（$FRONTEND_DIR），跳过"
      fi

      # --- 遗留 .harness-starter/ 目录检测 ---
      if [ -d "${SCRIPT_DIR}/.harness-starter" ]; then
        echo ""
        echo "  ⚠️  [starter-leftover] 发现 .harness-starter/ 残留目录，装完后应删除：rm -rf .harness-starter"
      fi

      echo ""
      if [ $arch_errors -eq 0 ]; then
        echo "✅ [Arch] 架构规则全部通过（基线）"
      else
        echo "❌ [Arch] 发现 $arch_errors 项违规"
        echo ""
        echo "💡 修复建议："
        echo "   - 依赖违规 → 跨服务调用改走 {{AP_MOD_API}} 的 Feign 接口"
        echo "   - @Autowired → 新文件改为 @RequiredArgsConstructor + final 字段"
        echo "   - RuntimeException → 改为 ServiceException / ExceptionBuilder.build(ErrorMessageKey.X, ...)"
        echo "   - new Date() / SimpleDateFormat → LocalDateTime / DateTimeFormatter 或 DateUtil"
      fi
    }

    case "$CHECK_MODE" in
      --java|--changed) compile_modules ;;
      --arch)           run_arch_check ;;
      --all|*)          compile_modules; run_arch_check ;;
    esac

    if [ $ERRORS_FOUND -ne 0 ]; then
      exit 1
    fi
    ;;

  test)
    require_mvn
    MODULE="${2:-}"
    if [ -z "$MODULE" ] || [ ! -f "${MODULE}/pom.xml" ]; then
      echo "用法：bash dev.sh test <模块目录> [mvn 参数]，例如 bash dev.sh test {{AP_SVC_STAT}} -Dtest={{AP_EXAMPLE_TEST}}"
      exit 1
    fi
    TEST_LOG=$(mktemp)
    set +e
    (cd "${MODULE}" && mvn test "${@:3}") 2>&1 | tee "$TEST_LOG"
    TEST_RC=${PIPESTATUS[0]}
    EXTRA=()
    if [ "$TEST_RC" -ne 0 ] && grep -q 'maven-resources-plugin.*MalformedInputException' "$TEST_LOG"; then
      echo ""
      echo "⚠️  [test] ${MODULE} 资源过滤失败（既有文件编码问题），跳过资源重跑："
      EXTRA=(-Dmaven.resources.skip=true)
      (cd "${MODULE}" && mvn test "${EXTRA[@]}" "${@:3}") 2>&1 | tee "$TEST_LOG"
      TEST_RC=${PIPESTATUS[0]}
    fi
    set -e
    # 模块有 JUnit 5 测试，却一个都没跑：多半是老版本 surefire（如 2.17）不认 JUnit 5，"0 个测试"会被误当成通过
    # （带 -Dtest 时老 surefire 还会因 "No tests were executed" 报失败，所以不看退出码，只排除编译失败）
    if grep -rlq 'org.junit.jupiter' "${MODULE}/src/test" 2>/dev/null \
        && ! grep -qE 'Tests run: [1-9]|COMPILATION ERROR' "$TEST_LOG"; then
      echo ""
      echo "❌ [test] ${MODULE} 有 JUnit 5 测试但运行数为 0（$(grep -o 'surefire:[0-9.]*' "$TEST_LOG" | head -1)），改用 surefire 2.22.2 重跑："
      (cd "${MODULE}" && mvn test-compile org.apache.maven.plugins:maven-surefire-plugin:2.22.2:test "${EXTRA[@]}" "${@:3}") 2>&1 | tee "$TEST_LOG"
      TEST_RC=${PIPESTATUS[0]}
      grep -qE 'Tests run: [1-9]' "$TEST_LOG" || { echo "❌ [test] 重跑后仍没有测试被执行"; TEST_RC=1; }
    fi
    rm -f "$TEST_LOG"
    exit "$TEST_RC"
    ;;

  verify-snapshot)
    # 占位实现：需要本地 mysql 客户端与只读账号（连接信息在 Nacos），按 docs/agents/verify.md 补齐：
    #   1. before：dump 关键业务表的行数 + 关键字段 sample 到 .harness/verify-snapshots/before.txt
    #   2. after：同样 schema dump 到 after.txt
    #   3. diff：对比并输出 delta
    PHASE="${2:-help}"
    case "$PHASE" in
      before|after|diff)
        echo "[verify-snapshot] $PHASE"
        echo "⚠️  占位实现，尚未连接数据库。按 docs/agents/verify.md 实现。"
        echo "    关键业务表：${KEY_TABLES}"
        ;;
      *)
        echo "用法：bash dev.sh verify-snapshot [before|after|diff]"
        ;;
    esac
    ;;

  help|*)
    sed -n '3,15p' "$0"
    ;;
esac

exit ${ERRORS_FOUND}
