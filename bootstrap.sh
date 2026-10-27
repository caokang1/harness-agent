#!/usr/bin/env bash
# ============================================================
# Harness Starter Kit · Bootstrap（零残留安装器）
#
# 仓库：https://github.com/caokang1/harness-agent
#
# 一行跑完（在你要改造的项目根目录执行）：
#
#   bash <(curl -fsSL \
#     https://raw.githubusercontent.com/caokang1/harness-agent/main/bootstrap.sh) \
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

REPO_URL="${HARNESS_STARTER_REPO:-https://github.com/caokang1/harness-agent.git}"
REF="${HARNESS_STARTER_REF:-main}"

# --- 环境自检 ---
if ! command -v git >/dev/null 2>&1; then
  cat >&2 <<'EOF'
[bootstrap] 未检测到 git 命令。

bootstrap.sh 依赖 git 做浅克隆。两种解决方式：
  1) 安装 git（推荐）：apt-get install -y git  /  yum install -y git  /  brew install git
  2) 走无 git 的 tar.gz 降级路径（见 INSTALL.md "常见问题 Q6"）：
       curl -fsSL <tar.gz url> | tar -xz -C /tmp
       bash /tmp/harness-agent-main/init.sh ...
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

# 克隆到临时目录下的 repo/，错误日志也放在临时目录里，中断时随临时目录一起清理
REPO_DIR="$TMPDIR/repo"
ERR_LOG="$TMPDIR/clone.err"
echo "[bootstrap] 临时克隆 $REPO_URL @ $REF → $REPO_DIR"
if ! git clone --depth=1 --branch "$REF" --quiet "$REPO_URL" "$REPO_DIR" 2>"$ERR_LOG"; then
  # --branch 只认分支和标签；REF 是提交号时改为完整克隆再 checkout。
  # 两种都失败就报错退出——绝不悄悄换成默认分支，否则固定版本就失去意义
  rm -rf "$REPO_DIR"
  if ! { git clone --quiet "$REPO_URL" "$REPO_DIR" && git -C "$REPO_DIR" checkout --quiet "$REF"; } 2>>"$ERR_LOG"; then
    echo "[bootstrap] ❌ 无法获取 $REPO_URL 的版本 $REF：" >&2
    sed 's/^/    /' "$ERR_LOG" >&2
    exit 1
  fi
fi

# --- 透传参数给 init.sh ---
# 用 -f 而不是 -x：git 里 init.sh 不一定带可执行位，下面本来就用 bash 调用
# 起步包可能在仓库根目录，也可能在仓库的 harness-starter/ 子目录
STARTER_DIR="$REPO_DIR"
[ -f "$STARTER_DIR/init.sh" ] || STARTER_DIR="$REPO_DIR/harness-starter"
if [ ! -f "$STARTER_DIR/init.sh" ]; then
  echo "[bootstrap] ❌ 克隆内容异常：仓库根目录和 harness-starter/ 下都没有 init.sh" >&2
  exit 1
fi

TARGET_DIR="$(pwd)"
echo "[bootstrap] 执行 init.sh（落地到 $TARGET_DIR）"
echo "--------------------------------------------------------"
# 告诉 init.sh 真正的项目根（starter 在 /tmp，不能用 $SCRIPT_DIR/.. 推断）
HARNESS_TARGET_DIR="$TARGET_DIR" bash "$STARTER_DIR/init.sh" "$@"
echo "--------------------------------------------------------"
echo "[bootstrap] ✅ 完成 · 临时目录已自动清理 · 项目根无 .harness-starter 残留"
