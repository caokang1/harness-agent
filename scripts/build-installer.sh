#!/usr/bin/env bash
# ============================================================
# Harness Starter Kit · 离线安装包构建器
#
# 用途：把 tier1-direct / tier1-direct-optional / tier2-template / init.sh
#       打成 base64 嵌入到 dist/install.sh，生成一个零依赖单文件安装包。
#
# 运行：cd harness-starter && bash scripts/build-installer.sh
# 输出：dist/install.sh  （上传 MinIO 后用 curl | bash 安装）
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$REPO_ROOT/dist"
OUTPUT="$DIST_DIR/install.sh"
VERSION="${HARNESS_VERSION:-$(git -C "$REPO_ROOT" describe --tags --always 2>/dev/null || echo "dev")}"
BUILD_DATE="$(date -u '+%Y-%m-%d %H:%M UTC')"

mkdir -p "$DIST_DIR"

echo "[build] 打包内容（tier1-direct, tier1-direct-optional, tier2-template, init.sh, scripts/detect-project.sh）..."
PAYLOAD=$(
  cd "$REPO_ROOT" && \
  tar -czf - \
    tier1-direct/ \
    tier1-direct-optional/ \
    tier2-template/ \
    init.sh \
    scripts/detect-project.sh \
  | base64 | tr -d '\n'
)  # 不用 GNU 专有的 base64 -w 0，macOS 上也能打包

echo "[build] payload 大小：$(echo "$PAYLOAD" | wc -c | awk '{printf "%.1fKB", $1/1024}') (base64)"

cat > "$OUTPUT" <<SCRIPT_EOF
#!/usr/bin/env bash
# ============================================================
# Harness Starter Kit · 离线单文件安装包
#
# 版本：${VERSION}
# 构建时间：${BUILD_DATE}
#
# 用法（在要改造的项目根目录执行）：
#
#   bash <(curl -fsSL https://your-minio.example.com/harness-starter/install.sh) \\
#     --project-name="my-svc" \\
#     --tech-stack="springboot+vue" \\
#     --modules="api,core,common" \\
#     --backend-package="com.example.mysvc" \\
#     --frontend-dir="../my-svc-ui"
#
# 可选参数：
#   --include-frontend-design   额外安装 frontend-design / ui-ux-pro-max 两个前端 UI 设计 skill
#   --help / -h                 查看完整参数说明
#
# 工作原理：
#   脚本内嵌了完整的 harness-starter 内容（base64 tarball）。
#   运行时自动解压到系统临时目录，调用 init.sh，结束后自动清理，
#   不在项目根留下任何临时文件。
# ============================================================

set -euo pipefail

PAYLOAD="${PAYLOAD}"

# --- 环境自检 ---
if ! command -v base64 >/dev/null 2>&1; then
  echo "[install] ❌ 未检测到 base64 命令，请安装 coreutils 后重试" >&2
  exit 127
fi
if ! command -v tar >/dev/null 2>&1; then
  echo "[install] ❌ 未检测到 tar 命令" >&2
  exit 127
fi

# --- 临时目录 + 自动清理 ---
TMPDIR="\$(mktemp -d -t harness-starter.XXXXXX)"
cleanup() {
  local exit_code=\$?
  [ -d "\$TMPDIR" ] && rm -rf "\$TMPDIR"
  exit \$exit_code
}
trap cleanup EXIT INT TERM HUP

echo "[install] Harness Starter Kit ${VERSION} · 解压中..."
# base64 --decode：GNU 和 macOS（含旧版）都认；-d 在旧版 macOS 上不是解码
echo "\$PAYLOAD" | base64 --decode | tar -xz -C "\$TMPDIR"

if [ ! -f "\$TMPDIR/init.sh" ]; then
  echo "[install] ❌ 解压内容异常：缺少 init.sh" >&2
  exit 1
fi

TARGET_DIR="\$(pwd)"
echo "[install] 初始化目标目录：\$TARGET_DIR"
echo "--------------------------------------------------------"
HARNESS_TARGET_DIR="\$TARGET_DIR" bash "\$TMPDIR/init.sh" "\$@"
echo "--------------------------------------------------------"
echo "[install] ✅ 完成 · 临时文件已自动清理"
SCRIPT_EOF

chmod +x "$OUTPUT"

echo "[build] ✅ 生成完成：$OUTPUT"
echo "[build] 文件大小：$(du -sh "$OUTPUT" | cut -f1)"

# --- 自动上传到 MinIO（可选）---
# 读取环境变量或 scripts/.env.build 文件里的配置（跟本脚本同目录）
ENV_FILE="$SCRIPT_DIR/.env.build"
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

MINIO_ALIAS="${MINIO_ALIAS:-}"
MINIO_ENDPOINT="${MINIO_ENDPOINT:-}"
MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-}"
MINIO_BUCKET="${MINIO_BUCKET:-}"
MINIO_PATH="${MINIO_PATH:-harness-starter/install.sh}"

if [ -n "$MINIO_ENDPOINT" ] && [ -n "$MINIO_ACCESS_KEY" ] && [ -n "$MINIO_SECRET_KEY" ] && [ -n "$MINIO_BUCKET" ]; then
  ALIAS="${MINIO_ALIAS:-harness-minio}"
  echo ""
  echo "[build] 检测到 MinIO 配置，开始自动上传..."
  mc alias set "$ALIAS" "$MINIO_ENDPOINT" "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" --quiet
  mc cp "$OUTPUT" "$ALIAS/$MINIO_BUCKET/$MINIO_PATH"
  mc anonymous set download "$ALIAS/$MINIO_BUCKET/$(dirname "$MINIO_PATH")/" 2>/dev/null || true
  PUBLIC_URL="$MINIO_ENDPOINT/$MINIO_BUCKET/$MINIO_PATH"
  echo "[build] ✅ 上传完成：$PUBLIC_URL"
  echo ""
  echo "用户安装命令："
  echo ""
  echo "  bash <(curl -fsSL $PUBLIC_URL) \\"
  echo "    --project-name=\"my-svc\" \\"
  echo "    --tech-stack=\"springboot+vue\" \\"
  echo "    --modules=\"api,core,common\" \\"
  echo "    --backend-package=\"com.example.mysvc\" \\"
  echo "    --frontend-dir=\"../my-svc-ui\""
else
  echo ""
  echo "提示：未配置 MinIO，跳过自动上传。手动上传方式："
  echo ""
  echo "  方式 A — 配置 scripts/.env.build 后重跑本脚本（推荐）："
  echo "    cp scripts/.env.build.example scripts/.env.build"
  echo "    # 编辑 scripts/.env.build 填入你的 MinIO 信息"
  echo "    bash scripts/build-installer.sh"
  echo ""
  echo "  方式 B — 手动执行 mc 命令："
  echo "    mc alias set myalias https://your-minio.example.com ACCESS_KEY SECRET_KEY"
  echo "    mc cp $OUTPUT myalias/your-bucket/harness-starter/install.sh"
  echo "    mc anonymous set download myalias/your-bucket/harness-starter/"
fi
