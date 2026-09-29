# -*- coding: utf-8 -*-
"""无人值守的「美女僵尸出手」取证机。

为什么需要它：美女僵尸只在**玩家附近 1~3.5 格**才知道起手，而我不能控制
游戏镜头（没有 computer_use 工具）。所以改成后台守望：一直用原生窗口尺寸
做低成本探测，一旦她出现在画面里，就临时把窗口拉到 1600x900 录一段（原生
尺寸下她只有 ~90px，读不出手臂），录完还原窗口，再把每帧裁到她身上放大。

用法：
    python tools/bride_watch.py --title Minecraft --minutes 12 --out art/bride/_watch
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from game_shot import (find_window, grab, crop as crop_img,  # noqa: E402
                       gain, zoom, shrink, write_png, resize_window)
from game_frames import read_png, montage                    # noqa: E402
from bride_locate import bride_bbox, crop_scale              # noqa: E402

HI = (1600, 900)          # 取证分辨率（原生 872x527 的 ~3 倍像素）
COOLDOWN = 20.0           # 一次取证后静默这么久，免得连续刷屏
CAP_SECS = 9.0
CAP_GAP = 0.18
HBEAT = 20                # 每探测这么多次打一行心跳，方便判断它是不是还活着


def detect(hwnd, step=2):
    """原生尺寸快速探测。返回 (bbox, 帧尺寸, 数据) 或 None。

    窗口最小化/被移出屏幕时 grab 会抛错 —— 这里吃掉，当作「没看见她」，
    让守望继续跑到窗口回来（而不是整台机器崩掉）。
    """
    try:
        w, h, data = grab(hwnd)
    except Exception:
        return None
    box = bride_bbox(w, h, data, step=step)
    return (box, w, h, data) if box else None


def capture(hwnd, out_dir, gain_v=1.45, scale=2):
    """放大窗口录一段，逐帧裁切放大，返回 (帧数, 命中数, 最大白px)。"""
    os.makedirs(out_dir, exist_ok=True)
    orig = resize_window(hwnd, HI[0], HI[1])
    if orig is None:
        print("      窗口最小化了，本次取证跳过（不动它）")
        return 0, 0, 0, [], None
    time.sleep(1.2)
    frames, hits, best = 0, 0, 0
    crops, boxes = [], []
    t_end = time.time() + CAP_SECS
    try:
        while time.time() < t_end:
            frames += 1
            try:
                w, h, data = grab(hwnd)
            except Exception as e:
                print("      第 %d 帧抓取失败（%s），提前收工" % (frames, e))
                break
            p = os.path.join(out_dir, "f_%03d.png" % frames)
            write_png(p, w, h, data)
            box = bride_bbox(w, h, data, step=2)
            if box:
                hits += 1
                x0, y0, x1, y1, px = box
                nw, nh, buf = crop_scale(w, h, data, box, 12, scale)
                if gain_v != 1.0:
                    buf = gain(buf, gain_v)
                cp = os.path.join(out_dir, "c_%03d.png" % frames)
                write_png(cp, nw, nh, buf)
                crops.append((cp, buf, nw, nh))
                boxes.append((frames, y0, y1 - y0 + 1, px))
                best = max(best, px * (y1 - y0 + 1) // 10)
                for f in (p,):
                    try:
                        os.remove(f)          # 有裁切图就不留全帧，省盘
                    except OSError:
                        pass
            time.sleep(CAP_GAP)
    finally:
        resize_window(hwnd, 0, 0, restore=orig)
    sheet = None
    if crops:
        tw = max(c[2] for c in crops)
        th = max(c[3] for c in crops)
        sel = crops[:14] if len(crops) <= 14 else crops[::max(1, len(crops) // 14)][:14]
        sheet = os.path.join(out_dir, "_sheet.png")
        montage([(c[0], c[1], c[2], c[3]) for c in sel], sheet, cols=7, tile=(tw, th))
    return frames, hits, best, boxes, sheet


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default="Minecraft")
    ap.add_argument("--minutes", type=float, default=12.0)
    ap.add_argument("--out", default="art/bride/_watch")
    ap.add_argument("--caps", type=int, default=4, help="最多取证几次")
    ap.add_argument("--probe", type=float, default=1.5, help="探测间隔秒")
    a = ap.parse_args()

    def find():
        win = find_window(a.title)
        return (win[0], win[1], win[3], win[4]) if win else None

    got = find()
    if not got:
        print("没找到标题/类名含 %r 的可用窗口（游戏退出/最小化？）" % a.title)
        return 2
    hwnd, title = got[0], got[1]
    print("守望窗口：%s  %dx%d" % (title, got[2], got[3]))
    os.makedirs(a.out, exist_ok=True)
    t_end = time.time() + a.minutes * 60
    t0 = time.time()
    caps = 0
    last = 0.0
    seen = 0
    probes = 0
    blind = 0                 # 连续探测不到可用窗口的次数
    while time.time() < t_end and caps < a.caps:
        probes += 1
        if probes % HBEAT == 0:      # 心跳：证明它还活着（卡住也能看出来）
            print("[%s] 心跳：已守望 %d 分，探测 %d 次，取证 %d 次"
                  % (time.strftime("%H:%M:%S"), int((time.time() - t0) / 60),
                     probes, caps))
            sys.stdout.flush()
        try:
            d = detect(hwnd)
        except Exception as e:                   # 兜底：任何异常都不自杀
            print("      探测异常（%s），跳过本次" % e)
            d = None
        if not d:
            seen = 0
            blind += 1
            if blind >= 8:                       # 窗口可能被重建了，重找一次
                blind = 0
                new = find()
                if new and new[0] != hwnd:
                    print("      窗口换了：%s  %dx%d（换用新句柄）"
                          % (new[1], new[2], new[3]))
                    hwnd = new[0]
            time.sleep(a.probe)
            continue
        blind = 0
        seen += 1
        # 连续两次独立命中才算确认（避免亮块误判）
        if seen < 2 or time.time() - last < COOLDOWN:
            time.sleep(a.probe)
            continue
        caps += 1
        d0 = os.path.join(a.out, "cap_%02d" % caps)
        box, w, h, _ = d
        print("[%s] 第 %d 次取证：探测框 (%d,%d)-(%d,%d)  进入 %dx%d 录像 %gs"
              % (time.strftime("%H:%M:%S"), caps, box[0], box[1], box[2], box[3],
                 HI[0], HI[1], CAP_SECS))
        sys.stdout.flush()
        frames, hits, best, boxes, sheet = capture(hwnd, d0)
        print("      %d 帧，%d 帧锁到她，最大体量 %d%s"
              % (frames, hits, best, ("  接触表 %s" % sheet) if sheet else ""))
        if boxes:
            print("      逐帧框高：%s"
                  % ", ".join("%d:%d" % (f, bh) for f, _y, bh, _p in boxes[:24]))
        sys.stdout.flush()
        last = time.time()
        seen = 0
    print("守望结束：取证 %d 次" % caps)
    return 0


if __name__ == "__main__":
    sys.exit(main())
