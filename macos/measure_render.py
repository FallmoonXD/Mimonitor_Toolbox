#!/usr/bin/env python3
"""页切渲染耗时测量：用截图变化判断页面何时画好。

为什么不用辅助功能树查询：`entire contents` 在含滑条的页面上单次要 4 秒
（要遍历 AppKit 控件并逐个取属性），测出来的"延迟"几乎全是查询开销，
而且那个查询本身还会打热 CoreUI 主题系统，误导采样分析。

截图法完全不碰辅助功能树，测的是像素真正变化的时间。

前提：app 在运行；/tmp/clicker 已编译。
用法： python3 measure_render.py [轮数]
"""
import hashlib
import subprocess
import sys
import time

import measure_pages as M   # 复用 click_row / row_ys / activate

SHOT = "/tmp/_render_shot.png"


def window_region():
    """从窗口位置推导右侧内容区，窗口被挪动也适用。"""
    out, _ = M.osa(f'tell application "System Events" to tell process "{M.APP}" '
                    f'to return ((position of window 1) & " " & (size of window 1))')
    nums = [int(float(v)) for v in out.replace(",", " ").split()]
    if len(nums) < 4:
        return None
    x, y, w, h = nums[0], nums[1], nums[2], nums[3]
    rx = x + 240                      # 跳过侧边栏
    ry = y + 20
    rw = max(120, w - 250)
    rh = min(420, max(120, h - 40))
    return f"{rx},{ry},{rw},{rh}"


def shot_hash(region):
    subprocess.run(["screencapture", "-x", "-R" + region, SHOT],
                   capture_output=True, timeout=20)
    try:
        with open(SHOT, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except OSError:
        return None


def wait_stable(region, max_wait=6.0, need_same=2):
    """等到画面连续 need_same 次不再变化，返回稳定耗时(ms)"""
    t0 = time.perf_counter()
    last = shot_hash(region)
    same = 0
    while time.perf_counter() - t0 < max_wait:
        h = shot_hash(region)
        if h == last:
            same += 1
            if same >= need_same:
                return (time.perf_counter() - t0) * 1000
        else:
            same = 0
            last = h
    return None


def measure(region, y, baseline_hash):
    """点击后测量：画面首次变化 和 完全稳定 各耗时多少"""
    t0 = time.perf_counter()
    M.click_row(y)

    first = None
    while time.perf_counter() - t0 < 6.0:
        if shot_hash(region) != baseline_hash:
            first = (time.perf_counter() - t0) * 1000
            break

    stable = wait_stable(region)
    return first, (stable + (first or 0) if stable is not None else None)


def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 2

    M.osa(f'tell application "{M.APP}" to activate')
    time.sleep(1.0)
    ys = M.row_ys()
    if not ys:
        print("❌ 读不到侧边栏坐标")
        return 1
    region = window_region()
    if not region:
        print("❌ 读不到窗口位置")
        return 1
    print(f"截图区域: {region}\n")

    for rnd in range(1, rounds + 1):
        print("=" * 64)
        print(f"第 {rnd} 轮：点击 → 画面变化 / 画面稳定")
        print("=" * 64)
        rows = []
        for (label, _), y in zip(M.PAGES, ys):
            # 先切到别的页作为起点
            other = ys[(ys.index(y) + 3) % len(ys)]
            M.click_row(other)
            time.sleep(1.2)
            base = shot_hash(region)

            first, stable = measure(region, y, base)
            if first is None:
                print(f"  {label:<12} ❌ 超时")
            else:
                rows.append((label, first, stable))
                st = f"{stable:7.0f} ms" if stable is not None else "   ?   "
                print(f"  {label:<12} 首次变化 {first:6.0f} ms   完全稳定 {st}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
