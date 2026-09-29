# -*- coding: utf-8 -*-
"""十字弩「透明瞄准镜」外观候选 mock —— 三选一，定方向后才写进 Java。

背景（为什么要这个工具）：
  `ClientEvents.renderScope` 目前只有**一种**画法 —— 望远镜式的黑圈：镜外全黑
  （`SCOPE_DARKNESS = 0.93`），镜内自绘十字 + 下方密位刻度 + 红心，用 `GuiGraphics.fill`
  逐条画出来，密位刻度按 `SCOPE_RADIUS_FRACTION × aimProgress` 缩放。
  十字弩的 `CrossbowItem.hasScopeOverlay()` 是 **false**（注释写着「没有玻璃可画」），
  所以右键举镜只有模型抬起来，屏幕上什么都没有。

  用户要的是「十字透明瞄准镜」= 有十字、能透过镜子看见世界（不是 AWM 那种黑镜筒）。
  本工具把三种候选按**目标 Java 代码同一套几何与颜色**画出来，供定稿：

    A 纯十字   —— 十字臂（中心留空） + 中心点 + 浅色晕；不遮世界，最「透明」。
    B 透明镜片 —— 淡青镜片 α0.07 + 细镜圈 + 十字 + 四向密位刻度 + 红心（推荐）。
    C 淡暗角   —— 镜外只压 0.28 的暗（对比 AWM 的 0.93），有镜感但不挡视野。

  三块面板的世界底完全相同：天/地渐变 + 远近剪影 + 中央僵尸剪影，用来同时判
  「亮背景（天）」和「暗背景（剪影/地面）」下的十字可读性。

  两张产出：`_sight_mock.png`（1936×360 三面板）与 `_sight_mock_zoom.png`
  （每块面板中心 320×352 区域的 2× 放大：十字细部、镜圈、镜片、暗角都在这一张里判）。

常量与 Java 侧一一对应（改这里就要改 ClientEvents）：
    SCOPE_RADIUS_FRACTION = 0.42    lens radius = min(w,h) × 0.42 × aimProgress
    十字臂长              = radius × 0.55          RETICLE_ARM_FRACTION
    中心留孔              = radius × 0.07（至少 2px）  RETICLE_GAP_FRACTION
    密位刻度              = radius 的 0.16/0.32/0.48/0.64 处（下）与 0.24/0.48 处（上），半宽 radius × 0.045
    暗芯                  = (0.85·p)<<24 | 0x101010     RETICLE_CORE_ALPHA / RETICLE_CORE_COLOUR
    浅晕                  = (0.45·p)<<24 | 0xF2F2F2     RETICLE_HALO_ALPHA / RETICLE_HALO_COLOUR
    红心                  = (0.90·p)<<24 | 0xB02020     （Java 侧沿用望远镜的 0xE6 = 0.902，同一条）
    镜片（B/C 增量）       = (0.07·p)<<24 | 0x8FB6C8     CLEAR_LENS_ALPHA / CLEAR_LENS_COLOUR
    镜圈（B/C 增量）       = (0.45·p)<<24 | 0x101010，厚 1.5px   CLEAR_RIM_ALPHA / CLEAR_RIM_THICKNESS
  三块面板的十字都是「暗芯 2px + 两侧浅色晕各 1px」；B 另有淡青镜片与细镜圈，C 另有镜外淡暗角 ——
  B 即定稿方案，Java 侧 `ClientEvents.renderClearSight` / `renderClearReticle` 按上表实现；
  tools/check_crossbow_anim.py 里有一条「观感同源」断言，逐项比对这几个颜色与透明度。

纯标准库：PNG 走 tools/bride_face_crop.py 的 write_png（zlib + struct），无 PIL / numpy。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bride_face_crop import write_png  # noqa: E402

W, H = 640, 360                 # 单块面板
GAP = 8                         # 面板间距
RADIUS_FRACTION = 0.42
ARM_FRACTION = 0.55
CORE = (0x10, 0x10, 0x10)       # 十字暗芯（与 Java 侧一致）
HALO = (0xF2, 0xF2, 0xF2)       # 浅色晕（新增项）
DOT = (0xB0, 0x20, 0x20)        # 红心（与 Java 侧一致）
LENS = (143, 182, 200)          # 镜片淡青（新增项）
CORE_A, HALO_A, DOT_A = 0.85, 0.45, 0.90
LENS_A, RIM_A = 0.07, 0.45


def put(buf, w, x, y, rgb, a):
    """alpha 合成一个像素，a ∈ [0,1]。"""
    if a <= 0.0 or x < 0 or y < 0 or x >= w or y >= H:
        return
    i = (y * w + x) * 4
    for k in range(3):
        buf[i + k] = int(buf[i + k] + (rgb[k] - buf[i + k]) * a + 0.5)


def box(buf, w, x0, y0, x1, y1, rgb, a=1.0):
    for y in range(max(0, int(y0)), min(H, int(y1) + 1)):
        for x in range(max(0, int(x0)), min(w, int(x1) + 1)):
            put(buf, w, x, y, rgb, a)


def disc(buf, w, cx, cy, r, rgb, a):
    for y in range(int(cy - r) - 1, int(cy + r) + 2):
        for x in range(int(cx - r) - 1, int(cx + r) + 2):
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if d <= r - 0.5:
                put(buf, w, x, y, rgb, a)
            elif d < r + 0.5:                        # 1px 软边，避免锯齿读成「粗一圈」
                put(buf, w, x, y, rgb, a * (r + 0.5 - d))


def coverage(inner, outer, d):
    """圆环在半径 d 处的覆盖率，内外各 0.5px 软边。"""
    if d < inner - 0.5 or d > outer + 0.5:
        return 0.0
    return max(0.0, min(1.0, min(d - (inner - 0.5), (outer + 0.5) - d)))


def ring(buf, w, cx, cy, radius, thickness, rgb, a):
    inner = radius - thickness
    for y in range(int(cy - radius) - 2, int(cy + radius) + 3):
        for x in range(int(cx - radius) - 2, int(cx + radius) + 3):
            cov = coverage(inner, radius, ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5)
            if cov > 0.0:
                put(buf, w, x, y, rgb, a * cov)


def veil_outside(buf, w, cx, cy, inner, rgb, a):
    """镜外遮罩：以到圆心的距离决定覆盖（外圈取屏幕对角线，四角都盖得住）。"""
    outer = (w * w + H * H) ** 0.5
    for y in range(H):
        for x in range(w):
            cov = coverage(inner, outer, ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5)
            if cov > 0.0:
                put(buf, w, x, y, rgb, a * cov)


def cross(buf, w, cx, cy, radius, progress=1.0, ticks=False):
    """十字 + 中心点：暗芯 2px + 两侧浅色晕各 1px（双色，亮/暗背景都能读）。"""
    arm = int(radius * ARM_FRACTION)
    hole = max(2, int(radius * 0.07))
    ix, iy = int(cx), int(cy)

    def bar(x0, y0, x1, y1):
        box(buf, w, x0 - 1, y0 - 1, x1 + 1, y1 + 1, HALO, HALO_A * progress)
        box(buf, w, x0, y0, x1, y1, CORE, CORE_A * progress)

    bar(ix - arm, iy, ix - hole, iy + 1)          # 左
    bar(ix + hole, iy, ix + arm, iy + 1)          # 右
    bar(ix, iy - arm, ix + 1, iy - hole)          # 上
    bar(ix, iy + hole, ix + 1, iy + arm)          # 下

    if ticks:
        half = int(radius * 0.045)
        rows = [(int(cy + radius * 0.16 * m), 1.0) for m in range(1, 5)]
        rows += [(int(cy - radius * 0.24 * m), 0.8) for m in (1, 2)]
        for y, weight in rows:
            box(buf, w, ix - half - 1, y - 1, ix + half + 1, y + 1, HALO, HALO_A * weight * progress)
            box(buf, w, ix - half, y, ix + half, y + 1, CORE, CORE_A * weight * progress)

    disc(buf, w, cx, cy, 1.7, DOT, DOT_A * progress)


def world(w):
    """三块面板共用的世界底：天/地渐变 + 远山 + 近景剪影 + 中央僵尸剪影。"""
    buf = bytearray(w * H * 4)
    horizon = int(H * 0.62)
    for y in range(H):
        for x in range(w):
            if y < horizon:                                       # 天空：上深下浅
                t = y / horizon
                rgb = (int(96 + 100 * t), int(140 + 76 * t), int(198 + 30 * t))
            else:                                                 # 地面
                t = (y - horizon) / (H - horizon)
                rgb = (int(126 - 56 * t), int(136 - 58 * t), int(104 - 42 * t))
            i = (y * w + x) * 4
            buf[i], buf[i + 1], buf[i + 2], buf[i + 3] = rgb[0], rgb[1], rgb[2], 255
    for x in range(0, w, 2):                                      # 远山（浅灰蓝，压在地平线上）
        h = int(10 + 7 * ((x * 0.013) % 2.0 > 1.0) + 5 * ((x * 0.031) % 2.0))
        box(buf, w, x, horizon - h, x + 1, horizon, (104, 118, 138), 0.85)
    box(buf, w, 0, horizon, w - 1, horizon, (78, 86, 74), 0.55)   # 地平线压一道暗
    for (rx, rw, rh, col) in ((0.06, 0.05, 0.10, (52, 58, 52)),      # 近景暗剪影（判暗背景可读性）
                              (0.14, 0.09, 0.16, (44, 50, 46)),
                              (0.86, 0.07, 0.13, (48, 54, 50)),
                              (0.94, 0.05, 0.09, (58, 62, 56))):
        x0 = int(rx * w)
        box(buf, w, x0, horizon - int(rh * H), x0 + int(rw * w), horizon + 4, col)
    # 中央僵尸剪影：脚踩地平线，胸口正落在屏幕中心（十字压在胸口上）
    cx = w // 2
    feet = horizon + 6
    head_top = feet - int(0.42 * H)
    head_bot = head_top + 12
    torso_bot = head_bot + 56
    box(buf, w, cx - 5, head_top, cx + 5, head_bot, (86, 108, 74))             # 头
    box(buf, w, cx - 12, head_bot - 2, cx + 12, torso_bot, (72, 92, 62))       # 躯干
    box(buf, w, cx - 12, head_bot - 2, cx - 20, torso_bot - 14, (66, 84, 58))  # 左臂
    box(buf, w, cx + 12, head_bot - 2, cx + 22, torso_bot - 20, (66, 84, 58))  # 右臂
    box(buf, w, cx - 10, torso_bot - 2, cx - 3, feet, (58, 72, 52))            # 左腿
    box(buf, w, cx + 3, torso_bot - 2, cx + 10, feet, (58, 72, 52))            # 右腿
    return buf


def letter(buf, w, x, y, ch, rgb=(0xF0, 0xF0, 0xF0)):
    """5×7 点阵，只有 A / B / C 三个字母（面板角标，带暗底）。"""
    glyphs = {
        'A': ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
        'B': ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
        'C': ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    }
    for gy, row in enumerate(glyphs[ch]):
        for gx, bit in enumerate(row):
            if bit == '1':
                box(buf, w, x + gx * 2 - 1, y + gy * 2 - 1, x + gx * 2 + 1, y + gy * 2 + 1,
                    (0, 0, 0), 0.55)
                box(buf, w, x + gx * 2, y + gy * 2, x + gx * 2 + 1, y + gy * 2 + 1, rgb, 0.90)


def panel(kind):
    buf = world(W)
    cx, cy = W / 2.0, H / 2.0
    r = min(W, H) * RADIUS_FRACTION
    if kind == 'A':
        cross(buf, W, cx, cy, r, ticks=False)
    elif kind == 'B':
        disc(buf, W, cx, cy, r, LENS, LENS_A)              # 淡青镜片
        ring(buf, W, cx, cy, r, 1.5, CORE, RIM_A)          # 细镜圈
        cross(buf, W, cx, cy, r, ticks=True)
    else:
        veil_outside(buf, W, cx, cy, r, (0, 0, 0), 0.28)   # 镜外淡暗角
        ring(buf, W, cx, cy, r, 1.5, CORE, RIM_A + 0.05)
        cross(buf, W, cx, cy, r, ticks=True)
    letter(buf, W, 10, 10, kind)
    return buf


def blit(dst, dst_w, src, src_w, x_off, y0, y1):
    for y in range(y0, y1):
        s = y * src_w * 4
        d = (y * dst_w + x_off) * 4
        dst[d:d + src_w * 4] = src[s:s + src_w * 4]


def divider(dst, dst_w, y0, y1, x0, x1):
    for y in range(y0, y1):
        for x in range(x0, x1):
            i = (y * dst_w + x) * 4
            dst[i], dst[i + 1], dst[i + 2], dst[i + 3] = 30, 30, 30, 255


def zoom_of(buf, cx0, cy0, zw, zh, z):
    """中心区域最近邻放大 z 倍 —— 判十字/刻度细部用。"""
    out = bytearray(zw * z * zh * z * 4)
    for oy in range(zh * z):
        sy = cy0 + oy // z
        for ox in range(zw * z):
            sx = cx0 + ox // z
            si = (sy * W + sx) * 4
            di = (oy * zw * z + ox) * 4
            out[di:di + 4] = buf[si:si + 4]
    return out


def main():
    base = os.path.abspath(os.path.join(HERE, '..', 'art', 'crossbow'))
    out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(base, '_sight_mock.png'))
    out_zoom = os.path.splitext(out)[0] + '_zoom.png'

    panels = [panel(k) for k in ('A', 'B', 'C')]

    total_w = W * 3 + GAP * 2
    sheet = bytearray(b'\x00' * total_w * H * 4)
    for k, p in enumerate(panels):
        blit(sheet, total_w, p, W, k * (W + GAP), 0, H)
        if k < 2:
            divider(sheet, total_w, 0, H, k * (W + GAP) + W, k * (W + GAP) + W + GAP)
    write_png(out, total_w, H, sheet)

    zw, zh, z = 320, 352, 2
    cx0, cy0 = W // 2 - zw // 2, H // 2 - zh // 2
    ztotal = zw * z * 3 + GAP * 2
    zsheet = bytearray(b'\x00' * ztotal * (zh * z) * 4)
    for k, p in enumerate(panels):
        zp = zoom_of(p, cx0, cy0, zw, zh, z)
        blit(zsheet, ztotal, zp, zw * z, k * (zw * z + GAP), 0, zh * z)
        if k < 2:
            divider(zsheet, ztotal, 0, zh * z,
                    k * (zw * z + GAP) + zw * z, k * (zw * z + GAP) + zw * z + GAP)
    write_png(out_zoom, ztotal, zh * z, zsheet)

    print('写出 %s  (%d×%d)' % (out, total_w, H))
    print('写出 %s  (%d×%d)' % (out_zoom, ztotal, zh * z))
    print('A 纯十字 / B 透明镜片+十字+刻度 / C 淡暗角+十字')


if __name__ == '__main__':
    main()
