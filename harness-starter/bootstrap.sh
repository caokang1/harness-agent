#!/usr/bin/env bash
# ============================================================
# Harness Starter Kit · Bootstrap（零残留安装器）
#
# 仓库：https://git.example.com/your-group/harness-starter
#
# 一行跑完（在你要改造的项目根目录执行）：
#
#   bash <(curl -fsSL \
#     https://git.example.com/your-group/harness-starter/-/raw/main/bootstrap.sh) \
#     --project-name="my-svc" \
#     --tech-stack="springboot+vue" \
#     --modules="common,auth,core,market,skills,start" \
#     --backend-package="com.example.mysvc" \
#     --frontend-dir="../my-svc-ui"
#
# 行为：
#   1. 在系统临时目录里 git clone --depth=1 本仓库（不污染项目根）
#   2. 调 $TMPDIR/init.sh，把 tier1/tier2 铺到项目根并替换占位符
#   3. 无论成功/失败/中断，trap 自动清理临时目录，不留 .git/
#
# 设计原则：
#   - 用户项目根在整个过程中完全干净（不出现 .harness-starter/）
#   - 所有参数原样透传给 init.sh，接口与 "git clone + bash init.sh" 完全一致
#   - 对 --help / -h 直接透传给 init.sh（保证用法只维护一处）
# ============================================================

set -euo pipefail

REPO_URL="${HARNESS_STARTER_REPO:-https://git.example.com/your-group/harness-starter.git}"
REF="${HARNESS_STARTER_REF:-main}"

# --- 环境自检 ---
if ! command -v git >/dev/null 2>&1; then
  cat >&2 <<'EOF'
[bootstrap] 未检测到 git 命令。

bootstrap.sh 依赖 git 做浅克隆。两种解决方式：
  1) 安装 git（推荐）：apt-get install -y git  /  yum install -y git  /  brew install git
  2) 走无 git 的 tar.gz 降级路径（见 INSTALL.md "常见问题 Q6"）：
       curl -fsSL <tar.gz url> | tar -xz -C /tmp
       bash /tmp/harness-starter-main/init.sh ...
EOF
  exit 127
fi

# --- 临时目录 + 自动清理 ---
TMPDIR="$(mktemp -d -t harness-starter.XXXXXX)"
cleanup() {
  local exit_code=$?
  if [ -d "$TMPDIR" ]; then
    rm -rf "$TMPDIR"
  fi
  exit $exit_code
}
trap cleanup EXIT INT TERM HUP

echo "[bootstrap] 临时克隆 $REPO_URL @ $REF → $TMPDIR"
if ! git clone --depth=1 --branch "$REF" --quiet "$REPO_URL" "$TMPDIR" 2>/dev/null; then
  # 有些老 git 不支持 --branch 对 commit SHA，回退重试一次
  git clone --depth=1 --quiet "$REPO_URL" "$TMPDIR"
fi

# --- 透传参数给 init.sh ---
if [ ! -x "$TMPDIR/init.sh" ]; then
  echo "[bootstrap] ❌ 克隆内容异常：缺少 init.sh" >&2
  exit 1
fi

TARGET_DIR="$(pwd)"
echo "[bootstrap] 执行 init.sh（落地到 $TARGET_DIR）"
echo "--------------------------------------------------------"
# 告诉 init.sh 真正的项目根（starter 在 /tmp，不能用 $SCRIPT_DIR/.. 推断）
HARNESS_TARGET_DIR="$TARGET_DIR" bash "$TMPDIR/init.sh" "$@"
echo "--------------------------------------------------------"
echo "[bootstrap] ✅ 完成 · 临时目录已自动清理 · 项目根无 .harness-starter 残留"
