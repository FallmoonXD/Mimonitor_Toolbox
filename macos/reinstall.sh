#!/bin/bash
# 一键：构建 → 安装到 /Applications → 重启应用
#
# 用法： ./reinstall.sh [--no-build]
#   --no-build   跳过构建，直接把当前产物装过去（改了配置想快速重启时用）
#
# 注意：会先退出正在运行的实例。应用是菜单栏常驻（LSUIElement），
# 退出后菜单栏图标会消失，重启脚本末尾会自动拉起来。
set -euo pipefail
cd "$(dirname "$0")"

APP_NAME="MimonitorToolbox"
SRC_APP="$APP_NAME.app"
DEST_APP="/Applications/$APP_NAME.app"

SKIP_BUILD=0
[ "${1:-}" = "--no-build" ] && SKIP_BUILD=1

if [ "$SKIP_BUILD" = "0" ]; then
    echo "==> 构建"
    ./build_app.sh
else
    echo "==> 跳过构建（使用现有产物）"
    [ -d "$SRC_APP" ] || { echo "❌ 没有 $SRC_APP，先跑一次完整构建"; exit 1; }
fi

echo "==> 退出正在运行的实例"
if pgrep -f "$DEST_APP/Contents/MacOS" >/dev/null 2>&1; then
    pkill -f "$DEST_APP/Contents/MacOS" || true
    # 等它真的退出，否则下面的 rm 可能撞上还在写入的进程
    for _ in $(seq 1 20); do
        pgrep -f "$DEST_APP/Contents/MacOS" >/dev/null 2>&1 || break
        sleep 0.25
    done
    echo "    已退出"
else
    echo "    （本来就没在运行）"
fi

echo "==> 安装到 /Applications"
rm -rf "$DEST_APP"
cp -R "$SRC_APP" "$DEST_APP"
# 让 LaunchServices 重新登记，否则 Finder / 启动台 / 权限列表可能还显示旧名字或旧图标
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$DEST_APP"

echo "==> 启动"
open -a "$DEST_APP"
sleep 3

if pgrep -f "$DEST_APP/Contents/MacOS" >/dev/null 2>&1; then
    echo "    ✅ 已启动（菜单栏常驻，不在 Dock）"
else
    echo "    ⚠️ 进程未检测到，稍等几秒再看看"
fi

echo ""
echo "完成。应用在 $DEST_APP"
