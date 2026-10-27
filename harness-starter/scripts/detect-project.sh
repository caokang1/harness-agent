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
      name="$(grep -E "^[[:space:]]*rootProject\.name[[:space:]]*=" "$f" 2>/dev/null \
        | head -1 \
        | sed -E "s/.*=[[:space:]]*['\"]?([^'\"]+)['\"]?.*/\1/" \
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
    # 路径通过参数传给 node，不拼进代码里
    name="$(node -e "try{process.stdout.write(require(process.argv[1]).name||'')}catch(e){}" "$dir/package.json" 2>/dev/null || true)"
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
        /^[[:space:]]*include[[:space:]]*\(/ {capturing=1; sub(/^[^(]*\(/, ""); }
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
        /^[[:space:]]*include[[:space:]]+["\047]/ {
          sub(/^[^[\047"]*/, "");
          sub(/\/\/.*$/, "");
          print;
          next;
        }
      ' "$f" 2>/dev/null \
        | tr -d "'\"" \
        | tr ',' '\n' \
        | sed -E 's#^[[:space:]]*:?[[:space:]]*##; s#[[:space:]]*$##; s#^.*/##' \
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
  # 逐个文件读（不用 GNU 专有的 xargs -r，路径带空格也没问题）
  pkgs="$(find "$dir" -path '*/src/main/java/*.java' -type f 2>/dev/null \
    | head -n "$_HS_MAX_FILES" \
    | while IFS= read -r f; do grep -hE "^package[[:space:]]+" "$f" 2>/dev/null; done \
    | sed -E 's/^package[[:space:]]+([a-zA-Z0-9_.]+)[[:space:]]*;.*/\1/' \
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

  # 扫自己的 package.json，以及和 detect_frontend_dir 相同的候选目录：
  # ../<项目名>-ui、../<项目名>-frontend、./frontend、./ui
  # （不能扫所有相邻的 *-ui：同一个父目录下别的项目的前端会被误认成本项目的）
  local name pkgs=()
  name="$(detect_project_name "$dir")"
  [ -f "$dir/package.json" ] && pkgs+=("$dir/package.json")
  for candidate in "$dir/../$name-ui" "$dir/../$name-frontend" "$dir/frontend" "$dir/ui"; do
    [ -f "$candidate/package.json" ] && pkgs+=("$candidate/package.json")
  done
  for pj in ${pkgs[@]+"${pkgs[@]}"}; do
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
    local f port
    while IFS= read -r f; do
      [ -n "$f" ] || continue
      if [[ "$f" == *.yml || "$f" == *.yaml ]]; then
        port="$(_yaml_server_port "$f")"
      else
        port="$(grep -E '^[[:space:]]*server\.port[[:space:]]*[=:]' "$f" 2>/dev/null | head -1 \
          | sed -E 's/.*[=:][[:space:]]*([0-9]+).*/\1/')"
      fi
      if [[ "$port" =~ ^[0-9]+$ ]]; then
        echo "$port"
        return 0
      fi
    done < <(find "$dir" -name "$pat" -type f -not -path '*/node_modules/*' -not -path '*/build/*' -not -path '*/target/*' 2>/dev/null)
  done
  return 1
}

# 只取 server.port：支持 "server.port: 9090" 和 "server:" 下面缩进的 "port: 9090"
# （不能取文件里第一个 port:，那可能是 redis / datasource 的端口）
_yaml_server_port() {
  awk '
    { sub(/\r$/, "") }
    /^[[:space:]]*#/ { next }
    /^server\.port:[[:space:]]*[0-9]+/ { sub(/^server\.port:[[:space:]]*/, ""); sub(/[^0-9].*$/, ""); print; exit }
    /^[^[:space:]]/ { in_server = ($0 ~ /^server:[[:space:]]*$/); indent = -1; next }
    in_server && /^[[:space:]]+[A-Za-z_-]+:/ {
      match($0, /^[[:space:]]+/); cur = RLENGTH
      if (indent < 0) indent = cur
      if (cur == indent && $0 ~ /^[[:space:]]+port:[[:space:]]*[0-9]+/) {
        sub(/^[[:space:]]+port:[[:space:]]*/, ""); sub(/[^0-9].*$/, ""); print; exit
      }
    }
  ' "$1" 2>/dev/null
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

  # init.sh 会 eval 这些行：值一律用 %q 转义，目录名带空格或 $(...) 也只会被当成普通字符串
  local key
  for key in project_name modules backend_package tech_stack app_main_class frontend_dir frontend_status backend_port; do
    printf '%s=%q\n' "$key" "${!key}"
  done
}

# ---------------------------------------------------------
# 如果被 source 加载则只暴露函数；被直接调用则跑 detect_all
# ---------------------------------------------------------
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  TARGET_DIR="${1:-$(pwd)}"
  detect_all "$TARGET_DIR"
fi
