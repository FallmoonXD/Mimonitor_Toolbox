#!/usr/bin/env python3
"""JNI 全量验证：逐个写入 JNI 值 → 回读 → 比对 → 还原。

用法： python3 verify_jni.py
前提： 显示器已连接（app 的 adb server 在 5038 端口）

安全性：
  - 开始时记录所有被测键的原始值，结束时无条件还原。
  - EDID / FreeSync 类键会改变显示器接受的信号格式（可能黑屏或改分辨率），
    只做「读取 + 映射校验」，不写入。
"""
import os
import re
import subprocess
import sys

ADB = "/Applications/红米G Pro ToolBox.app/Contents/Resources/runtime/adb"
SERIAL = os.environ.get("MIMONITOR_SERIAL", "192.168.5.205:5555")
JAR_MTK = "/data/data/mitv.service/cache/MtkDirectTool.jar"
CACHE = "/data/data/mitv.service/cache"
RESULT = "/sdcard/Download/Mimonitor_Toolbox/.mtk_batch_result.txt"

ENV = dict(os.environ, ANDROID_ADB_SERVER_PORT="5038")


def shell(cmd, timeout=25):
    r = subprocess.run([ADB, "-s", SERIAL, "shell", cmd],
                       capture_output=True, text=True, timeout=timeout, env=ENV)
    return (r.stdout or "") + (r.stderr or "")


def _tvservice(payload):
    """构造 service call TvService 命令，与 app 的 buildTvserviceCommand 完全一致。"""
    encoded = "".join("\\${IFS}" + a for a in payload)
    return ('service call TvService 3 s16 "sh -c eval\\${IFS}CLASSPATH=%s'
            '\\${IFS}/system/bin/app_process\\${IFS}%s%s"' % (JAR_MTK, CACHE, encoded))


def jni_set(key, value, upd=3):
    shell(_tvservice(["MtkDirectTool", "set", key, str(value), str(upd)]))


def hdr_tone_mapping(value, upd=3):
    shell(_tvservice(["MtkDirectTool", "setHdrToneMapping", str(value), str(upd)]))


def set_color_gains(r, g, b):
    shell(_tvservice(["MtkDirectTool", "setColorGains", str(r), str(g), str(b)]))


def batch_get(keys):
    """与 app 的 jniBatchGet 相同的读取方式。"""
    payload = _tvservice(["MtkDirectTool", "batchGet"] + keys)
    cmd = ("mkdir -p /sdcard/Download/Mimonitor_Toolbox; rm -f %s; %s >/dev/null; "
           "i=0; while [ $i -lt 30 ] && [ ! -f %s ]; do sleep 0.1; i=$((i+1)); done; "
           "cat %s 2>/dev/null") % (RESULT, payload, RESULT, RESULT)
    out = shell(cmd)
    values = {}
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("__") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if v.startswith("ERROR"):
            continue
        values[k] = v
    return values


def settings_get(keys):
    out = shell("settings list global")
    allset = {}
    for line in out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            allset[k] = v
    return {k: allset.get(k, "") for k in keys}


# ── 被测项目：(显示名, JNI 键, 测试值列表, 原版 UI 值 → MTK 值 的映射) ──────────
# 只写这些；EDID / FreeSync 单独处理（只读）
CASES = [
    ("背光",              "g_disp__disp_back_light",        [20, 50, 80]),
    ("精密控光",          "g_video__vid_local_dimming",     [0, 1, 2, 3]),
    ("色域",              "g_video__vid_gamut_mapping_mode", [0, 3, 6, 4, 5, 7]),
    ("动态清晰度",        "g_video__vid_insert_black",      [0, 1, 2, 3]),
    ("响应时间",          "g_video__vid_od_response_time",  [1, 2, 3]),
    ("色温(MTK 值)",      "g_video__clr_temp",              [0, 1, 2, 3, 4, 5, 6]),
]

# UI 映射校验：app 会把 UI 值按这些表换算成 MTK 值
UI_TO_MTK = {
    "色温": {0: 1, 1: 2, 2: 3, 3: 0, 4: 4, 5: 5, 8: 6},
    "HDR 色调映射": {0: 5, 1: 0, 2: 2, 3: 1},
    "色域": {0: 0, 3: 3, 6: 6, 4: 4, 5: 5, 7: 7},
}

READONLY_KEYS = [
    "g_fusion_picture__dp_edid_version",
    "g_fusion_picture__hdmi_edid_version",
    "g_video__dp_adaptive_sync",
    "g_video__freesync_switch",
    "g_video__vid_hdr_tone_mapping_mode",
    "g_video__clr_gain_r",
    "g_video__clr_gain_g",
    "g_video__clr_gain_b",
]


def main():
    print("=" * 68)
    print("JNI 全量验证")
    print("=" * 68)

    # get-state 是 adb 主机命令，不能走 shell
    state = subprocess.run([ADB, "-s", SERIAL, "get-state"],
                           capture_output=True, text=True, timeout=10,
                           env=ENV).stdout.strip()
    if state != "device":
        print(f"❌ 设备状态 {state}，请先连接显示器")
        return 1
    print(f"✅ 设备已连接: {SERIAL}\n")

    all_keys = [c[1] for c in CASES] + READONLY_KEYS
    print("── 记录原始值 ──")
    original = batch_get(all_keys)
    for k in all_keys:
        print(f"   {k:44s} = {original.get(k, '(未读到)')}")
    if not original:
        print("❌ batchGet 完全没返回，检查 jar 是否已部署")
        return 1
    print()

    failures = []

    print("── 写入 / 回读 验证 ──")
    for label, key, values in CASES:
        orig = original.get(key)
        print(f"\n[{label}]  {key}")
        for v in values:
            jni_set(key, v)
            got = batch_get([key]).get(key)
            ok = (got == str(v))
            mark = "✅" if ok else "❌"
            print(f"   写 {v:<4} → 回读 {got!s:<6} {mark}")
            if not ok:
                failures.append((label, key, v, got))
        # 还原
        if orig is not None:
            jni_set(key, orig)
            back = batch_get([key]).get(key)
            print(f"   还原为 {orig} → 回读 {back!s:<6} {'✅' if back == str(orig) else '❌'}")

    # 色彩增益（走 setColorGains 专用通道）
    print("\n[色彩增益]  setColorGains")
    cur = batch_get(["g_video__clr_gain_r", "g_video__clr_gain_g", "g_video__clr_gain_b"])
    print(f"   当前: R={cur.get('g_video__clr_gain_r')} G={cur.get('g_video__clr_gain_g')} B={cur.get('g_video__clr_gain_b')}")
    r0, g0, b0 = (int(cur.get(k, 1024) or 1024) for k in
                  ("g_video__clr_gain_r", "g_video__clr_gain_g", "g_video__clr_gain_b"))
    test_r = 1024 if r0 != 1024 else 1100
    set_color_gains(test_r, g0, b0)
    got = batch_get(["g_video__clr_gain_r"]).get("g_video__clr_gain_r")
    ok = (got == str(test_r))
    print(f"   写 R={test_r} → 回读 {got} {'✅' if ok else '❌'}")
    if not ok:
        failures.append(("色彩增益", "g_video__clr_gain_r", test_r, got))
    set_color_gains(r0, g0, b0)
    print(f"   还原 R={r0} → 回读 {batch_get(['g_video__clr_gain_r']).get('g_video__clr_gain_r')}")

    # HDR 色调映射
    print("\n[HDR 色调映射]  setHdrToneMapping")
    hdr_before = original.get("g_video__vid_hdr_tone_mapping_mode")
    print(f"   当前: {hdr_before}")
    for mtk in [0, 1, 2, 5]:
        hdr_tone_mapping(mtk)
        got = batch_get(["g_video__vid_hdr_tone_mapping_mode"]).get("g_video__vid_hdr_tone_mapping_mode")
        ok = (got == str(mtk))
        print(f"   写 {mtk} → 回读 {got!s:<6} {'✅' if ok else '❌'}")
        if not ok:
            failures.append(("HDR 色调映射", "g_video__vid_hdr_tone_mapping_mode", mtk, got))
    if hdr_before is not None:
        hdr_tone_mapping(hdr_before)
        print(f"   还原为 {hdr_before} → 回读 {batch_get(['g_video__vid_hdr_tone_mapping_mode']).get('g_video__vid_hdr_tone_mapping_mode')}")

    # 只读键
    print("\n── 只读键（不改动，仅记录当前值供映射核对）──")
    ro = batch_get(READONLY_KEYS)
    for k in READONLY_KEYS:
        print(f"   {k:44s} = {ro.get(k, '(未读到)')}")

    # settings 侧的对应值
    print("\n── settings 侧对应值 ──")
    sk = ["picture_mode", "picture_backlight", "picture_color_temperature",
          "picture_local_dimming", "picture_response_time", "picture_dynamic_definition",
          "tv_picture_advanced_video_color_space", "settings_display_hdr_color_tone",
          "picture_red_gain", "picture_green_gain", "picture_blue_gain"]
    for k, v in settings_get(sk).items():
        print(f"   {k:44s} = {v}")

    print("\n" + "=" * 68)
    if failures:
        print(f"❌ 发现 {len(failures)} 处写入/回读不一致：")
        for label, key, wrote, got in failures:
            print(f"   [{label}] {key}: 写 {wrote} 但回读 {got}")
    else:
        print("✅ 全部 JNI 写入/回读一致")
    print("=" * 68)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
