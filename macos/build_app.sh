#!/bin/bash
# 打包 MimonitorToolbox 为可直接分发的 .app（无需 Xcode，仅需命令行工具里的 swift）
#
# 用法：  cd macos && ./build_app.sh
# 产物：  .build/MimonitorToolbox.app
#
# 所有运行时资源都会被内嵌进 .app，最终用户无需安装任何东西（不需要 brew / adb）：
#   - adb      : 优先用仓库 assets/runtime/adb；没有就自动从 Google 官方下载 platform-tools 并缓存
#   - *.jar    : 复用仓库 assets/runtime/
#   - 保活 apk : 复用仓库 assets/adb_guardian/
set -euo pipefail

cd "$(dirname "$0")"

APP_NAME="MimonitorToolbox"
BUILD_DIR=".build"   # swift 的中间产物，隐藏目录
CACHE_DIR=".cache"   # platform-tools 下载缓存，隐藏目录
# 最终 .app 直接放在 macos/ 下，方便在 Finder 里直接看到（已在 .gitignore 中排除 *.app）
APP_DIR="$APP_NAME.app"
CONTENTS="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS/MacOS"
RES_DIR="$CONTENTS/Resources"
REPO_ROOT="$(cd .. && pwd)"

PLATFORM_TOOLS_URL="https://dl.google.com/android/repository/platform-tools-latest-darwin.zip"

# 由 ./setup_signing_cert.sh 创建的固定签名身份名。
# 允许外部覆盖，方便模拟「本机没装证书」的情况（CI 就是这样）：
#   SIGN_CERT_NAME="不存在" ./build_app.sh
SIGN_CERT_NAME="${SIGN_CERT_NAME:-MimonitorToolbox Local Signing}"

# ---------- 获取 adb 二进制 ----------
# stdout 只输出 adb 路径，过程信息走 stderr，方便调用方捕获。
fetch_adb() {
    # 1) 仓库自带（想固定版本时可自行放入 macOS 版 adb 覆盖）
    if [ -f "$REPO_ROOT/assets/runtime/adb" ]; then
        echo "    使用仓库自带 assets/runtime/adb" >&2
        echo "$REPO_ROOT/assets/runtime/adb"
        return 0
    fi
    # 2) 上次下载的缓存，避免每次打包都重新下载 15MB
    if [ -x "$CACHE_DIR/platform-tools/adb" ]; then
        echo "    使用已缓存的 platform-tools" >&2
        echo "$CACHE_DIR/platform-tools/adb"
        return 0
    fi
    # 3) 从 Google 官方下载（仅首次需要联网）
    echo "    未找到 adb，正在从 Google 官方下载 platform-tools ..." >&2
    mkdir -p "$CACHE_DIR"
    local zip="$CACHE_DIR/platform-tools-darwin.zip"
    if ! curl -fL --progress-bar -o "$zip" "$PLATFORM_TOOLS_URL"; then
        echo "" >&2
        echo "    下载失败。可手动下载：" >&2
        echo "      $PLATFORM_TOOLS_URL" >&2
        echo "    解压后把 platform-tools/adb 放到 $REPO_ROOT/assets/runtime/adb，再重跑本脚本。" >&2
        return 1
    fi
    rm -rf "$CACHE_DIR/platform-tools"
    unzip -q -o "$zip" -d "$CACHE_DIR"
    rm -f "$zip"
    # 只留 adb 和 NOTICE，其余（fastboot / mke2fs / sqlite3 …）用不到，省掉约 18MB
    find "$CACHE_DIR/platform-tools" -mindepth 1 -maxdepth 1 \
        ! -name adb ! -name NOTICE.txt -exec rm -rf {} +
    chmod +x "$CACHE_DIR/platform-tools/adb"
    echo "    下载完成并已缓存（后续打包无需重复下载）" >&2
    echo "$CACHE_DIR/platform-tools/adb"
}

# 通用二进制（Intel + Apple Silicon）。分架构各编一次再 lipo 合并 ——
# `swift build --arch a --arch b` 那种写法依赖 xcbuild（完整 Xcode），
# 纯命令行工具会报错，所以这里退而求其次分开编。
# 想加快本地构建可以 UNIVERSAL=0 ./build_app.sh
UNIVERSAL="${UNIVERSAL:-1}"

echo "==> 1/5 编译 release 版本（通用二进制: ${UNIVERSAL}）..."
if [ "$UNIVERSAL" = "1" ]; then
    swift build -c release --arch arm64
    swift build -c release --arch x86_64
    BIN_PATH="$BUILD_DIR/release-universal/$APP_NAME"
    mkdir -p "$(dirname "$BIN_PATH")"
    lipo -create -output "$BIN_PATH" \
        "$BUILD_DIR/arm64-apple-macosx/release/$APP_NAME" \
        "$BUILD_DIR/x86_64-apple-macosx/release/$APP_NAME"
else
    swift build -c release
    BIN_PATH="$BUILD_DIR/release/$APP_NAME"
fi
echo "    架构: $(lipo -archs "$BIN_PATH")"

echo "==> 2/5 组装 .app 目录结构..."
rm -rf "$APP_DIR"
mkdir -p "$MACOS_DIR" "$RES_DIR"

cp "$BIN_PATH" "$MACOS_DIR/$APP_NAME"

echo "==> 3/5 内嵌运行时资源（adb / jar / 保活 apk）..."
mkdir -p "$RES_DIR/runtime" "$RES_DIR/adb_guardian"

ADB_SRC="$(fetch_adb)"
cp "$ADB_SRC" "$RES_DIR/runtime/adb"
chmod +x "$RES_DIR/runtime/adb"
echo "    已内嵌 adb: $("$RES_DIR/runtime/adb" version 2>/dev/null | head -n 2 | tail -n 1)"

for jar in MtkDirectTool.jar ColorfulLedTool.jar; do
    if [ -f "$REPO_ROOT/assets/runtime/$jar" ]; then
        cp "$REPO_ROOT/assets/runtime/$jar" "$RES_DIR/runtime/$jar"
        echo "    已内嵌 $jar"
    else
        echo "    警告：未找到 ${jar}（对应的画面/灯效 JNI 功能不可用）"
    fi
done

GUARDIAN_APK="$REPO_ROOT/assets/adb_guardian/adbguardian-signed.apk"
if [ -f "$GUARDIAN_APK" ]; then
    cp "$GUARDIAN_APK" "$RES_DIR/adb_guardian/adbguardian-signed.apk"
    echo "    已内嵌 adbguardian-signed.apk"
else
    echo "    警告：未找到 adbguardian-signed.apk（保活守护不可用）"
fi

# 随包附带 adb 的 NOTICE（Apache-2.0 再分发要求）
if [ -f "$CACHE_DIR/platform-tools/NOTICE.txt" ]; then
    cp "$CACHE_DIR/platform-tools/NOTICE.txt" "$RES_DIR/runtime/NOTICE-platform-tools.txt"
fi

# 应用图标：直接复用 Windows 版的 assets/app/icon.ico，转换产物在 assets/AppIcon.icns
# （Windows 图标更新后用 ./make_icon.sh 重新生成）
ICON_SRC="assets/AppIcon.icns"
if [ -f "$ICON_SRC" ]; then
    cp "$ICON_SRC" "$RES_DIR/AppIcon.icns"
    echo "    已内嵌应用图标（源自 assets/app/icon.ico）"
else
    echo "    警告：未找到 ${ICON_SRC}，将使用系统默认图标"
fi

echo "==> 4/5 生成 Info.plist..."
cat > "$CONTENTS/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>MimonitorToolbox</string>
    <key>CFBundleIdentifier</key>
    <string>com.mimonitor.toolbox</string>
    <key>CFBundleName</key>
    <string>红米G Pro ToolBox</string>
    <key>CFBundleDisplayName</key>
    <string>红米G Pro ToolBox</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>0.1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>13.0</string>
    <!-- 只在菜单栏常驻，不进 Dock（对应原版的托盘图标行为） -->
    <key>LSUIElement</key>
    <true/>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.utilities</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>NSLocalNetworkUsageDescription</key>
    <string>需要访问局域网以发现并连接同一网络下的红米显示器（无线 ADB，端口 5555）。</string>
</dict>
</plist>
PLIST

echo "==> 5/5 签名..."
# 去掉浏览器下载带来的隔离属性，否则内嵌的 adb 会被 Gatekeeper 拦下
xattr -cr "$APP_DIR" 2>/dev/null || true
# adb 自带 Google 的 Developer ID 签名，能用就保留；失效时再 ad-hoc 补签
if ! codesign --verify "$RES_DIR/runtime/adb" >/dev/null 2>&1; then
    codesign --force --sign - "$RES_DIR/runtime/adb" >/dev/null 2>&1 || true
fi

# 优先用固定身份的自签名证书。macOS 的「本地网络」权限要求稳定的代码身份才能记住授权，
# ad-hoc 签名的身份是内容哈希、每次编译都变，会导致局域网访问被静默拒绝。
#
# 末尾的 `|| true` 不能省：脚本开了 `set -euo pipefail`，找不到证书时
# `grep -m1` 返回 1，会让整条管道失败、进而让这个赋值失败、脚本直接中止。
# CI 上本来就没有证书（只存在于本机钥匙串），所以这个分支必然走到 ——
# 本地因为证书在，grep 总能匹配，反而测不出来。
SIGN_ID="$(security find-identity -v -p codesigning 2>/dev/null \
    | grep -m1 "$SIGN_CERT_NAME" | sed -E 's/^[^"]*"([^"]*)".*/\1/' || true)"
if [ -n "$SIGN_ID" ]; then
    if codesign --force --sign "$SIGN_ID" "$APP_DIR" 2>/dev/null; then
        echo "    已用固定证书签名：$SIGN_ID"
    else
        codesign --force --sign - "$APP_DIR" >/dev/null 2>&1 \
            && echo "    固定证书签名失败，已退回 ad-hoc" || echo "    签名失败"
    fi
else
    codesign --force --sign - "$APP_DIR" >/dev/null 2>&1 \
        && echo "    ad-hoc 签名完成（⚠️ 局域网权限可能无法授权，运行 ./setup_signing_cert.sh 修复）" \
        || echo "    签名失败"
fi

echo ""
echo "完成！.app 就在 macos/ 目录下：$APP_DIR"
echo "  · 运行：      open $APP_DIR"
echo "  · 复制安装：  cp -R $APP_DIR /Applications/"
echo "  · 分发：把 $APP_NAME.app 压缩成 zip 发给别人即可，对方无需安装 adb 或 brew"
echo "  · 全局快捷键：首次使用需在 系统设置→隐私与安全性→辅助功能 中授权"
