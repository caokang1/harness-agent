#!/usr/bin/env bash
# ============================================================
# Harness Starter Kit · 项目结构自动探测
#
# 被 init.sh 通过 source 调用。提供 7 个 detect_* 函数，
# 每个函数按优先级尝试多条来源，扫到就 echo 出来，扫不到返回空串。
#
# 约定：
#   - 输入：无全局参数；每个 detect 函数内部从 $TARGET_DIR 推断
#   - 输出：一行纯文本（逗号分隔的列表或单个值）
#   - 失败：echo "" 并 return 1
#   - 静默：所有诊断信息走 stderr（不污染 stdout）
# ============================================================

set -o pipefail

# 扫源码文件上限（防大仓库扫炸）
_HS_MAX_FILES=2000

# ---------------------------------------------------------
# detect_project_name
#   来源优先级：git remote → settings.gradle(.kts) → package.json → 当前目录名
# ---------------------------------------------------------
detect_project_name() {
  local dir="${1:-$TARGET_DIR}"

  # 1) git remote origin → 取仓库名（去 .git 后缀）
  local git_url
  git_url="$(git -C "$dir" remote get-url origin 2>/dev/null || true)"
  if [ -n "$git_url" ]; then
    local name
    name="$(basename "$git_url" .git)"
    if [ -n "$name" ] && [ "$name" != "." ]; then
      echo "$name"
      return 0
    fi
  fi

  # 2) settings.gradle(.kts) rootProject.name
  for f in "$dir/settings.gradle" "$dir/settings.gradle.kts"; do
    if [ -f "$f" ]; then
      local name
      name="$(grep -E "^\s*rootProject\.name\s*=" "$f" 2>/dev/null \
        | head -1 \
        | sed -E "s/.*=\s*['\"]?([^'\"]+)['\"]?.*/\1/" \
        | tr -d ' ')"
      if [ -n "$name" ]; then
        echo "$name"
        return 0
      fi
    fi
  done

  # 3) package.json name
  if [ -f "$dir/package.json" ] && command -v node >/dev/null 2>&1; then
    local name
    name="$(node -e "try{process.stdout.write(require('$dir/package.json').name||'')}catch(e){}" 2>/dev/null || true)"
    if [ -n "$name" ]; then
      echo "$name"
      return 0
    fi
  fi

  # 4) 当前目录名
  basename "$dir"
}

# ---------------------------------------------------------
# detect_modules
#   来源优先级：settings.gradle include → pom.xml modules → 一级子目录含 build 文件
# ---------------------------------------------------------
detect_modules() {
  local dir="${1:-$TARGET_DIR}"

  # 1) Gradle settings.gradle(.kts) include(...) — 支持跨行写法
  for f in "$dir/settings.gradle" "$dir/settings.gradle.kts"; do
    if [ -f "$f" ]; then
      local modules
      # awk 跨行抓 include(...) 整块；兼容 include 'a','b' 无括号的老写法
      modules="$(awk '
        /^\s*include[[:space:]]*\(/ {capturing=1; sub(/^[^(]*\(/, ""); }
        capturing {
          # 删掉行尾注释
          sub(/\/\/.*$/, "");
          buf = buf " " $0;
          if (index(buf, ")")) {
            sub(/\).*$/, "", buf);
            print buf;
            exit;
          }
          next;
        }
        # Groovy 老写法：每行一个 include 'mod' / include "mod" / 或一行 include 'a','b'
        # 禁止在首行 match 后 exit —— 否则只会留下第一个模块（用户 soa-common/soa-service/soa-start 只扫到第一个）
        /^\s*include[[:space:]]+["\x27]/ {
          sub(/^[^[\047"]*/, "");
          sub(/\/\/.*$/, "");
          print;
          next;
        }
      ' "$f" 2>/dev/null \
        | tr -d "'\"" \
        | tr ',' '\n' \
        | sed -E 's#^\s*:?\s*##; s#\s*$##; s#^.*/##' \
        | grep -vE '^$' \
        | paste -sd ',' -)"
      if [ -n "$modules" ]; then
        echo "$modules"
        return 0
      fi
    fi
  done

  # 2) Maven pom.xml <module>
  if [ -f "$dir/pom.xml" ]; then
    local modules
    modules="$(grep -oE "<module>[^<]+</module>" "$dir/pom.xml" 2>/dev/null \
      | sed -E 's|<module>([^<]+)</module>|\1|' \
      | paste -sd ',' -)"
    if [ -n "$modules" ]; then
      echo "$modules"
      return 0
    fi
  fi

  # 3) 一级子目录有 build.gradle / pom.xml 的
  local modules=""
  for sub in "$dir"/*/; do
    [ -d "$sub" ] || continue
    local base
    base="$(basename "$sub")"
    case "$base" in .*|node_modules|dist|build|target|docs|scripts) continue ;; esac
    if [ -f "$sub/build.gradle" ] || [ -f "$sub/build.gradle.kts" ] || [ -f "$sub/pom.xml" ]; then
      modules="${modules:+$modules,}$base"
    fi
  done
  echo "$modules"
}

# ---------------------------------------------------------
# detect_backend_package
#   扫 src/main/java 的 package 声明，取公共前缀（到第一个分叉停）
# ---------------------------------------------------------
detect_backend_package() {
  local dir="${1:-$TARGET_DIR}"

  # 收集所有 package 声明
  local pkgs
  pkgs="$(find "$dir" -path '*/src/main/java/*.java' -type f 2>/dev/null \
    | head -$_HS_MAX_FILES \
    | xargs -r grep -hE "^package\s+" 2>/dev/null \
    | sed -E 's/^package\s+([a-zA-Z0-9_.]+)\s*;.*/\1/' \
    | sort -u)"

  [ -z "$pkgs" ] && return 1

  # 计算公共前缀（逐层判断是否所有包都以该层为前缀）
  local first_pkg
  first_pkg="$(echo "$pkgs" | head -1)"
  IFS='.' read -ra parts <<< "$first_pkg"

  local prefix=""
  for part in "${parts[@]}"; do
    local candidate="${prefix:+$prefix.}$part"
    local all_match=1
    while IFS= read -r p; do
      case "$p" in
        "$candidate"|"$candidate".*) ;;
        *) all_match=0; break ;;
      esac
    done <<< "$pkgs"
    if [ "$all_match" -eq 1 ]; then
      prefix="$candidate"
    else
      break
    fi
  done

  # 至少要有两段（a.b）才返回，单段太短不可信
  if echo "$prefix" | grep -qE '\.'; then
    echo "$prefix"
    return 0
  fi
  return 1
}

# ---------------------------------------------------------
# detect_tech_stack
#   判断规则：
#     后端（Java）：根目录有 build.gradle|pom.xml|settings.gradle
#     前端（Vue） ：frontend-dir 或相邻 *-ui 目录的 package.json 含 "vue"
# ---------------------------------------------------------
detect_tech_stack() {
  local dir="${1:-$TARGET_DIR}"
  local has_java=0 has_vue=0

  if [ -f "$dir/build.gradle" ] || [ -f "$dir/build.gradle.kts" ] \
     || [ -f "$dir/settings.gradle" ] || [ -f "$dir/settings.gradle.kts" ] \
     || [ -f "$dir/pom.xml" ]; then
    has_java=1
  fi

  # 扫自己的 package.json 或相邻 *-ui / ../frontend / ./frontend 目录
  local pkgs=()
  [ -f "$dir/package.json" ] && pkgs+=("$dir/package.json")
  for candidate in "$dir/../"*-ui "$dir/../frontend" "$dir/frontend" "$dir/ui"; do
    [ -f "$candidate/package.json" ] && pkgs+=("$candidate/package.json")
  done
  for pj in "${pkgs[@]}"; do
    if grep -q '"vue"' "$pj" 2>/dev/null; then
      has_vue=1
      break
    fi
  done

  if [ "$has_java" -eq 1 ] && [ "$has_vue" -eq 1 ]; then
    echo "springboot+vue"
    return 0
  elif [ "$has_java" -eq 1 ]; then
    echo "springboot"
    return 0
  fi
  return 1
}

# ---------------------------------------------------------
# detect_app_main_class
#   扫 @SpringBootApplication 标注的类文件名（去 .java）
# ---------------------------------------------------------
detect_app_main_class() {
  local dir="${1:-$TARGET_DIR}"

  local file
  file="$(grep -rlE '@SpringBootApplication' "$dir" \
    --include='*.java' \
    --exclude-dir='.git' \
    --exclude-dir='build' \
    --exclude-dir='target' \
    --exclude-dir='node_modules' \
    2>/dev/null | head -1)"

  if [ -n "$file" ]; then
    basename "$file" .java
    return 0
  fi
  return 1
}

# ---------------------------------------------------------
# detect_frontend_dir
#   按优先级验证是否存在：
#     ../<project-name>-ui → ../<project-name>-frontend → ./frontend → ./ui
# ---------------------------------------------------------
detect_frontend_dir() {
  local dir="${1:-$TARGET_DIR}"
  local project_name="${2:-}"

  # 如果没传 project_name，现场探测
  if [ -z "$project_name" ]; then
    project_name="$(detect_project_name "$dir")"
  fi

  local parent
  parent="$(cd "$dir/.." && pwd)"

  local candidates=()
  [ -n "$project_name" ] && candidates+=("../$project_name-ui" "../$project_name-frontend")
  candidates+=("./frontend" "./ui")

  for rel in "${candidates[@]}"; do
    local abs
    abs="$(cd "$dir" && cd "$rel" 2>/dev/null && pwd)" || continue
    if [ -d "$abs" ]; then
      echo "$rel"
      return 0
    fi
  done

  # 扫不到：返回推断值但标记未验证
  if [ -n "$project_name" ]; then
    echo "../$project_name-ui"
    return 2  # exit code 2 = 推断但未验证
  fi
  return 1
}

# ---------------------------------------------------------
# detect_backend_port
#   扫 application-dev.yml > application.yml > application.properties 的 server.port
# ---------------------------------------------------------
detect_backend_port() {
  local dir="${1:-$TARGET_DIR}"

  for pat in 'application-dev.yml' 'application-dev.yaml' \
             'application.yml' 'application.yaml' \
             'application-dev.properties' 'application.properties'; do
    local files
    files="$(find "$dir" -name "$pat" -type f -not -path '*/node_modules/*' -not -path '*/build/*' -not -path '*/target/*' 2>/dev/null)"
    [ -z "$files" ] && continue
    for f in $files; do
      local port
      if [[ "$f" == *.yml || "$f" == *.yaml ]]; then
        port="$(grep -E '^\s*port:\s*[0-9]+' "$f" 2>/dev/null | head -1 | sed -E 's/.*port:\s*([0-9]+).*/\1/')"
      else
        port="$(grep -E '^server\.port\s*=' "$f" 2>/dev/null | head -1 | sed -E 's/.*=\s*([0-9]+).*/\1/')"
      fi
      if [ -n "$port" ]; then
        echo "$port"
        return 0
      fi
    done
  done
  return 1
}

# ---------------------------------------------------------
# detect_all
#   一次跑完所有 detect，输出给 init.sh 消费的 key=value 行
# ---------------------------------------------------------
detect_all() {
  local dir="${1:-$TARGET_DIR}"

  local project_name modules backend_package tech_stack app_main_class frontend_dir frontend_status backend_port

  project_name="$(detect_project_name "$dir")"
  modules="$(detect_modules "$dir")"
  backend_package="$(detect_backend_package "$dir" 2>/dev/null || echo "")"
  tech_stack="$(detect_tech_stack "$dir" 2>/dev/null || echo "")"
  app_main_class="$(detect_app_main_class "$dir" 2>/dev/null || echo "")"

  # frontend_dir 的 exit code 区分"验证存在" vs "推断未验证"
  frontend_dir="$(detect_frontend_dir "$dir" "$project_name" 2>/dev/null)"
  frontend_status=$?

  backend_port="$(detect_backend_port "$dir" 2>/dev/null || echo "")"

  cat <<EOF
project_name=${project_name}
modules=${modules}
backend_package=${backend_package}
tech_stack=${tech_stack}
app_main_class=${app_main_class}
frontend_dir=${frontend_dir}
frontend_status=${frontend_status}
backend_port=${backend_port}
EOF
}

# ---------------------------------------------------------
# 如果被 source 加载则只暴露函数；被直接调用则跑 detect_all
# ---------------------------------------------------------
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  TARGET_DIR="${1:-$(pwd)}"
  detect_all "$TARGET_DIR"
fi
