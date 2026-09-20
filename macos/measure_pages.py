#!/usr/bin/env python3
"""页切耗时测量：点击侧边栏，测量「点击 → 目标页标题出现」的耗时。

前提：
  - app 正在运行
  - 终端已获辅助功能权限
  - /tmp/clicker 已编译（swiftc -O clicker.swift -o clicker）

用法： python3 measure_pages.py [重复轮数]
"""
import subprocess
import sys
import time

APP = "MimonitorToolbox"
CLICKER = "/tmp/clicker"
SIDEBAR_X = 902          # 侧边栏行的点击横坐标
# 文本列表里，开头连续若干条是侧边栏标签，其后第一条才是当前页标题。
# 侧边栏加了「菜单栏」页之后是 8 项 —— 这个数字会随页面增减变化，别写死。
SIDEBAR_COUNT = 8
TITLE_INDEX = SIDEBAR_COUNT

# 侧边栏顺序 -> (标签, 页面标题)
PAGES = [
    ("主页 & 连接", "红米 G Pro 27U Toolbox"),
    ("画面设置", "画面设置"),
    ("游戏模式", "游戏模式"),
    ("信号源切换", "信号源切换"),
    ("屏幕灯", "屏幕灯"),
    ("工具与设置", "工具与设置"),
    ("遥控器", "遥控器"),
]


def osa(script):
    r = subprocess.run(["osascript", "-e", script],
                       capture_output=True, text=True, timeout=60)
    return (r.stdout or "").strip(), (r.stderr or "").strip()


def texts():
    out, _ = osa(f'''tell application "System Events" to tell process "{APP}"
  set out to ""
  set all to entire contents of window 1
  repeat with i from 1 to (count of all)
    try
      set e to item i of all
      if (class of e as text) is "static text" then set out to out & (value of e as text) & linefeed
    end try
  end repeat
  return out
end tell''')
    return out.splitlines()


def row_ys():
    """读取侧边栏每行的纵坐标（窗口可能被移动过）"""
    out, err = osa(f'''tell application "System Events" to tell process "{APP}"
  set out to ""
  tell outline 1 of scroll area 1 of UI element 1 of UI element 1 of UI element 1 of window 1
    repeat with i from 1 to (count of rows)
      set p to position of row i
      set out to out & (item 2 of p) & linefeed
    end repeat
  end tell
  return out
end tell''')
    if err or not out:
        return None
    return [int(float(v)) for v in out.splitlines()]


def row_rects():
    """读取侧边栏每行的 (x, y, w, h)。直接用行自身的坐标，不依赖窗口位置 ——
    写死坐标或者从窗口推算，窗口一挪就点到内容区去了。

    遍历整个窗口找 row 而不是走固定层级路径：侧边栏改成 HStack 之后
    层级变了，写死的 `outline 1 of scroll area 1 of ...` 直接失效。
    用横坐标过滤出侧边栏那几行（内容区的列表也有一堆 row）。
    """
    out, err = osa(f'''tell application "System Events" to tell process "{APP}"
  set out to ""
  set all to entire contents of window 1
  repeat with i from 1 to (count of all)
    try
      set e to item i of all
      if (class of e as text) is "row" then
        set p to position of e
        set s to size of e
        set out to out & (item 1 of p) & "," & (item 2 of p) & "," & (item 1 of s) & "," & (item 2 of s) & linefeed
      end if
    end try
  end repeat
  return out
end tell''')
    if err or not out:
        return None
    win_x = window_origin_x()
    rects = []
    for line in out.splitlines():
        try:
            nums = [int(float(v)) for v in line.split(",")]
        except ValueError:
            continue
        if len(nums) != 4:
            continue
        x, y, w, h = nums
        # 侧边栏紧贴窗口左边，宽度固定 220；内容区的列表行不满足
        if win_x is not None and abs(x - win_x) > 4:
            continue
        if w != 220:
            continue
        rects.append((x, y, w, h))
    return rects or None


def window_origin_x():
    out, _ = osa(f'''tell application "System Events" to tell process "{APP}"
  return (item 1 of (position of window 1))
end tell''')
    try:
        return int(float(out.split(",")[0].strip()))
    except (ValueError, IndexError):
        return None


def click_row(y):
    """y 为行的纵坐标；横坐标从该行的实际位置取。"""
    rects = row_rects()
    x = SIDEBAR_X
    if rects:
        # 找到与传入 y 匹配的那一行，用它的真实横坐标
        for (rx, ry, rw, rh) in rects:
            if abs(ry - y) <= 2:
                x = rx + rw // 2
                break
    subprocess.run([CLICKER, str(x), str(y + 14)],
                   capture_output=True, timeout=20)


def current_title():
    t = texts()
    return t[TITLE_INDEX] if len(t) > TITLE_INDEX else ""


def switch_and_time(y, expect_title, timeout=8.0):
    t0 = time.perf_counter()
    click_row(y)
    deadline = t0 + timeout
    while time.perf_counter() < deadline:
        if current_title() == expect_title:
            return (time.perf_counter() - t0) * 1000
    return None


def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 2

    osa(f'tell application "{APP}" to activate')
    time.sleep(1.0)

    ys = row_ys()
    if not ys or len(ys) != len(PAGES):
        print(f"❌ 读不到侧边栏坐标（拿到 {ys}）")
        return 1
    print(f"侧边栏纵坐标: {ys}\n")

    for rnd in range(1, rounds + 1):
        print("=" * 62)
        print(f"第 {rnd} 轮：点击 → 目标页标题出现")
        print("=" * 62)
        results = []
        for (label, title), y in zip(PAGES, ys):
            # 先跳到别的页，确保是真正的切换
            other = ys[(PAGES.index((label, title)) + 1) % len(ys)]
            click_row(other)
            time.sleep(0.6)

            ms = switch_and_time(y, title)
            if ms is None:
                print(f"  {label:<12} ❌ 超时")
            else:
                results.append((label, ms))
                print(f"  {label:<12} {ms:7.0f} ms")
        if results:
            print("-" * 62)
            worst = max(results, key=lambda x: x[1])
            print(f"  最慢: {worst[0]} {worst[1]:.0f} ms"
                  f"    平均: {sum(m for _, m in results)/len(results):.0f} ms")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
