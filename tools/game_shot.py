# -*- coding: utf-8 -*-
"""游戏窗口截屏（纯 ctypes + 标准库，无 PIL/numpy）。

用法：
    python tools/game_shot.py --list                  # 只列窗口
    python tools/game_shot.py --title Minecraft       # 按标题子串截图
    python tools/game_shot.py --screen                # 整个主屏
    python tools/game_shot.py --title Minecraft --crop 0.25,0,0.75,1 --width 1100

为什么不用 PIL：本机 python 没有 PIL/numpy（`ModuleNotFoundError`），
而 OpenGL 窗口（Minecraft）用 PrintWindow 常返回全黑 ⇒ 默认走「桌面 DC BitBlt」，
窗口必须可见（不能最小化、不能在别的虚拟桌面上，否则截到的是遮挡它的窗口）。
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import os
import struct
import sys
import zlib

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
user32.SetProcessDPIAware()

PW_RENDERFULLCONTENT = 0x00000002
SRCCOPY = 0x00CC0020
BI_RGB = 0
DIB_RGB_COLORS = 0


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", ctypes.c_long),
                ("biHeight", ctypes.c_long), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


def list_windows():
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, cls, 256)
                r = wt.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(r))
                out.append((hwnd, buf.value, cls.value,
                            r.right - r.left, r.bottom - r.top))
        return True

    user32.EnumWindows(cb, 0)
    return out


def find_window(sub, min_w=200, min_h=150):
    """标题或类名含 sub（不区分大小写）的**可用**可见窗口，取面积最大的那个。

    两类必须滤掉：① 面积过小的（拖拽提示条、输入法候选框——它们的标题里
    可能带完整路径，从而含 'minecraft'，实测把检测拐到 199x34 的窗口上）；
    ② 最小化的（GetWindowRect 返回 -32000 附近的坐标，BitBlt 抓到屏外垃圾）。
    """
    hits = []
    for w in list_windows():
        if sub.lower() not in w[1].lower() and sub.lower() not in w[2].lower():
            continue
        if w[3] < min_w or w[4] < min_h:
            continue
        if user32.IsIconic(w[0]):
            continue
        hits.append(w)
    if not hits:
        return None
    return max(hits, key=lambda w: w[3] * w[4])


def grab(hwnd, use_print=True):
    """返回 (w, h, BGRA bytes)。hwnd=None ⇒ 桌面。"""
    r = wt.RECT()
    if hwnd:
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        w, h = r.right - r.left, r.bottom - r.top
    else:
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
        r.left = r.top = 0
    if w <= 0 or h <= 0:
        raise RuntimeError("窗口尺寸为 0（最小化了？）")

    hdc_src = user32.GetDC(None)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_src)
    hbm = gdi32.CreateCompatibleBitmap(hdc_src, w, h)
    gdi32.SelectObject(hdc_mem, hbm)
    try:
        ok = 0
        if hwnd and use_print:
            ok = user32.PrintWindow(hwnd, hdc_mem, PW_RENDERFULLCONTENT)
        if not ok:
            # 桌面 DC 直接拷窗口区域（OpenGL 全屏/窗口化都吃这条）
            gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_src, r.left, r.top, SRCCOPY)

        bi = BITMAPINFO()
        bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bi.bmiHeader.biWidth = w
        bi.bmiHeader.biHeight = -h          # 负数 = 自上而下
        bi.bmiHeader.biPlanes = 1
        bi.bmiHeader.biBitCount = 32
        bi.bmiHeader.biCompression = BI_RGB
        buf = ctypes.create_string_buffer(w * h * 4)
        got = gdi32.GetDIBits(hdc_mem, hbm, 0, h, buf, ctypes.byref(bi),
                             DIB_RGB_COLORS)
        if not got:
            raise RuntimeError("GetDIBits 失败")
        data = buf.raw
    finally:
        gdi32.DeleteObject(hbm)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(None, hdc_src)
    return w, h, data


def resize_window(hwnd, w, h, restore=None):
    """SetWindowPos 改窗口尺寸；返回原 (x, y, w, h) 供还原。"""
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    orig = (r.left, r.top, r.right - r.left, r.bottom - r.top)
    SWP_NOZORDER, SWP_NOACTIVATE = 0x0004, 0x0010
    if restore:
        # 还原也要防退化矩形（被最小化时存下来的 w/h 可能是 0 或负数，
        # 拿它去 SetWindowPos 会把窗口缩成一个点）。
        if restore[2] > 0 and restore[3] > 0:
            x, y, w, h = restore
            user32.SetWindowPos(hwnd, 0, x, y, w, h, SWP_NOZORDER | SWP_NOACTIVATE)
        return orig
    if user32.IsIconic(hwnd):
        return None          # 最小化时别动：改了尺寸会把它从任务栏拽出来
    user32.SetWindowPos(hwnd, 0, orig[0], orig[1], w, h,
                        SWP_NOZORDER | SWP_NOACTIVATE)
    return orig


def crop(data, w, h, frac):
    x0, y0, x1, y1 = frac
    cx0, cy0 = int(w * x0), int(h * y0)
    cx1, cy1 = int(w * x1), int(h * y1)
    cw, ch = cx1 - cx0, cy1 - cy0
    rows = []
    for y in range(cy0, cy1):
        off = (y * w + cx0) * 4
        rows.append(data[off:off + cw * 4])
    return cw, ch, b"".join(rows)


def gain(data, g):
    """亮度增益（夜晚截图全靠这个），>1 提亮。"""
    if g == 1.0:
        return data
    lut = bytes(min(255, int(i * g)) for i in range(256))
    out = bytearray(data)
    for i in range(0, len(out), 4):
        out[i] = lut[out[i]]
        out[i + 1] = lut[out[i + 1]]
        out[i + 2] = lut[out[i + 2]]
    return bytes(out)


def zoom(data, w, h, k):
    """整数倍最近邻放大（给小窗口截图看点用）。"""
    if k <= 1:
        return w, h, data
    nw, nh = w * k, h * k
    out = bytearray(nw * nh * 4)
    for y in range(h):
        src = y * w * 4
        row = bytearray()
        for x in range(w):
            row += data[src + x * 4:src + x * 4 + 4] * k
        for j in range(k):
            out[(y * k + j) * nw * 4:(y * k + j) * nw * 4 + nw * 4] = row
    return nw, nh, bytes(out)


def shrink(data, w, h, maxw):
    """整数倍盒式降采样（保持长宽比），只为把 PNG 压小。"""
    if not maxw or w <= maxw:
        return w, h, data
    k = (w + maxw - 1) // maxw
    nw, nh = w // k, h // k
    out = bytearray()
    stride = w * 4
    for y in range(nh):
        base = y * k * stride
        row = bytearray(nw * 4)
        for x in range(nw):
            sx = base + x * k * 4
            b = g = r = 0
            for j in range(k):
                o = sx + j * 4
                b += data[o]
                g += data[o + 1]
                r += data[o + 2]
            d = x * 4
            row[d] = b // k
            row[d + 1] = g // k
            row[d + 2] = r // k
            row[d + 3] = 255
        out += row
    return nw, nh, bytes(out)


def write_png(path, w, h, rgb):
    """写 PNG。rgb 是逐像素 4 字节（R,G,B,A）—— 与 read_png 的返回顺序一致
    （GDI 抓回来的 BGRA 已在 grab() 里换过序，这里别再换第二次）。"""
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += rgb[y * w * 4:(y + 1) * w * 4]
    def chunk(tag, body):
        return (struct.pack(">I", len(body)) + tag + body +
                struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--title", default=None)
    ap.add_argument("--screen", action="store_true")
    ap.add_argument("--crop", default=None, help="x0,y0,x1,y1 比例")
    ap.add_argument("--gain", type=float, default=1.0, help="亮度增益，夜晚用 1.8~2.5")
    ap.add_argument("--zoom", type=int, default=1, help="整数倍最近邻放大")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--burst", action="store_true", help="连拍模式（单进程循环）")
    ap.add_argument("--seconds", type=float, default=20.0, help="连拍时长")
    ap.add_argument("--interval", type=float, default=0.0, help="帧间隔（0=能多快多快）")
    ap.add_argument("--resize", default=None, help="截屏期间把窗口改成 WxH，结束自动还原")
    ap.add_argument("-o", "--out", default="art/bride/_game_shot.png")
    a = ap.parse_args()

    if a.list:
        fg = user32.GetForegroundWindow()
        for hwnd, title, cls, w, h in sorted(list_windows(), key=lambda t: -t[3] * t[4]):
            tag = "  <<< 前台" if hwnd == fg else ""
            print("%-10s %5dx%-5d %-28s %s%s" % (hex(hwnd), w, h, cls[:28],
                                                 title[:60], tag))
        return 0

    hwnd = None
    if not a.screen:
        if not a.title:
            print("要么 --title <子串>，要么 --screen", file=sys.stderr)
            return 2
        hit = find_window(a.title)
        if not hit:
            print("没找到标题/类名含 %r 的可见窗口" % a.title, file=sys.stderr)
            return 3
        hwnd = hit[0]
        print("窗口 %s [%s] %dx%d" % (hit[1], hit[2], hit[3], hit[4]))

    w, h, data = grab(hwnd)
    if a.crop:
        frac = tuple(float(v) for v in a.crop.split(","))
        w, h, data = crop(data, w, h, frac)
    out_dir = None
    seq = 0
    orig_rect = None
    if a.resize:
        rw, rh = (int(v) for v in a.resize.lower().split("x"))
        orig_rect = resize_window(hwnd, rw, rh)
        import time as _t
        _t.sleep(1.2)          # 让 GLFW 重排 framebuffer
        print("窗口 %dx%d → %dx%d（结束还原）" % (orig_rect[2], orig_rect[3], rw, rh))
        try:
            w, h, data = grab(hwnd)
            w0, h0, d0 = shrink(data, w, h, a.width)
            d0 = gain(d0, a.gain)
            w0, h0, d0 = zoom(d0, w0, h0, a.zoom)
            p = os.path.join(os.path.dirname(a.out) or ".", "_resize_check.png")
            os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
            write_png(p, w0, h0, d0)
            print("重排后实测 %dx%d → %s" % (w, h, p))
        except Exception as e:  # noqa: BLE001
            print("重排自检失败: %s" % e)

    try:
        if a.burst:
            out_dir = os.path.dirname(a.out) or "."
            os.makedirs(out_dir, exist_ok=True)
            base = os.path.splitext(os.path.basename(a.out))[0]
            import time
            t_end = time.time() + a.seconds
            while time.time() < t_end:
                seq += 1
                t0 = time.time()
                w, h, data = grab(hwnd)
                if a.crop:
                    w, h, data = crop(data, w, h, frac)
                w2, h2, d2 = shrink(data, w, h, a.width)
                d2 = gain(d2, a.gain)
                w2, h2, d2 = zoom(d2, w2, h2, a.zoom)
                p = os.path.join(out_dir, "%s_%02d.png" % (base, seq))
                write_png(p, w2, h2, d2)
                print("  %s  %dx%d  (%.2fs)" % (p, w2, h2, time.time() - t0))
                sys.stdout.flush()
                rest = a.interval - (time.time() - t0)
                if rest > 0:
                    time.sleep(rest)
            print("连拍 %d 帧 / %.1fs" % (seq, a.seconds))
            return 0

        w2, h2, d2 = shrink(data, w, h, a.width)
        d2 = gain(d2, a.gain)
        w2, h2, d2 = zoom(d2, w2, h2, a.zoom)
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        n = write_png(a.out, w2, h2, d2)
        print("写出 %s  %dx%d  %.1f KB" % (a.out, w2, h2, n / 1024.0))
        return 0
    finally:
        if orig_rect:
            resize_window(hwnd, 0, 0, restore=orig_rect)
            print("窗口已还原 %dx%d" % (orig_rect[2], orig_rect[3]))


if __name__ == "__main__":
    sys.exit(main())
