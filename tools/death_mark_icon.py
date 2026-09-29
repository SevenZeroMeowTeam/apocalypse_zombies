# -*- coding: utf-8 -*-
"""死亡标记（Death Mark）的 HUD 图标 —— 18×18 PNG，纯标准库写出。

Minecraft 的效果图标不是「一张图直接贴」，而是走 `mob_effects` 贴图图集：
每个效果按自己的 id 去 `textures/mob_effect/<path>.png` 找图（见
`net.minecraft.client.resources.MobEffectTextureManager`）。所以文件名必须与
效果注册名逐字一致，尺寸必须是 18×18 —— HUD 就是按 18×18 原样 blit 的
（`Gui.renderEffects` 里 `blit(x+3, y+3, 0, 18, 18, sprite)`），大一点小一点都会糊。

图形取「准星/瞄准环」：外环 + 四向刻度 + 白色中心点，外圈压一圈近黑的红描边。
理由是这个尺寸下细节全丢，只有「环 + 十字」这种粗结构还认得出，而且一眼就是
「你被锁定了」。放大镜预览用 tools/death_mark_icon.py --preview 出 8 倍最近邻图。

用法：
    python tools/death_mark_icon.py            # 写出正式图标
    python tools/death_mark_icon.py --preview  # 额外写一张 8 倍放大图（写进 scratch）
"""

import argparse
import os
import struct
import zlib

SIZE = 18

# 描边 / 环 / 高光 / 中心（中心用骨白：深浅两种 HUD 底色上都立得住）
OUTLINE = (0x2A, 0x0A, 0x0A, 255)
RING = (0xC8, 0x1E, 0x1E, 255)
HILIGHT = (0xFF, 0x5A, 0x4A, 255)
CORE = (0xF2, 0xED, 0xE4, 255)

OUT = os.path.join('src', 'main', 'resources', 'assets', 'apocalypse_zombies',
                   'textures', 'mob_effect', 'death_mark.png')


def blank():
    return [[(0, 0, 0, 0) for _ in range(SIZE)] for _ in range(SIZE)]


def radius_to(cx, cy):
    return [[((i - cx) ** 2 + (j - cy) ** 2) ** 0.5 for i in range(SIZE)] for j in range(SIZE)]


def dilate(mask):
    """把实心形状向外扩一圈，用来生成描边。"""
    out = [[False] * SIZE for _ in range(SIZE)]
    for j in range(SIZE):
        for i in range(SIZE):
            if not mask[j][i]:
                continue
            for dj in (-1, 0, 1):
                for di in (-1, 0, 1):
                    y, x = j + dj, i + di
                    if 0 <= y < SIZE and 0 <= x < SIZE:
                        out[y][x] = True
    return out


def build():
    img = blank()
    cx = cy = (SIZE - 1) / 2.0

    def px(i, j, color):
        if 0 <= i < SIZE and 0 <= j < SIZE:
            img[int(j)][int(i)] = color

    # ---- 主体遮罩：环 + 四向刻度 + 中心十字
    # 18px 的图经过 HUD 缩到 1:1 blit，细节全丢 —— 只留「环 + 十字」，别加整圈描边
    # （描边在 18px 上要吃掉 2px，环就没地方了；HUD 槽本身是深底，够衬得出来）。
    body = [[False] * SIZE for _ in range(SIZE)]
    inner_dark = [[False] * SIZE for _ in range(SIZE)]
    core = [[False] * SIZE for _ in range(SIZE)]
    for j in range(SIZE):
        for i in range(SIZE):
            dx, dy = i - cx, j - cy
            r = (dx * dx + dy * dy) ** 0.5
            if 5.6 <= r <= 6.8:                       # 外环（约 1px 厚）
                body[j][i] = True
            # 四向刻度：从环外沿直接连出去，不留缝（脱开就会像四个飘着的点）
            if abs(dx) <= 1.0 and 6.8 < abs(dy) <= 8.4:
                body[j][i] = True
            if abs(dy) <= 1.0 and 6.8 < abs(dx) <= 8.4:
                body[j][i] = True
            # 中心白十字：两臂各 5×2，18px 上刚好认得出是「十字」。
            # 不衬暗色内圈 —— 深红与骨白本身就是强对比，多一圈只会把 18px 搅浑。
            if (abs(dx) <= 0.8 and abs(dy) <= 2.0) or (abs(dy) <= 0.8 and abs(dx) <= 2.0):
                body[j][i] = True
                core[j][i] = True

    ring_mask = [[body[j][i] and not core[j][i] for i in range(SIZE)] for j in range(SIZE)]

    for j in range(SIZE):
        for i in range(SIZE):
            if not body[j][i]:
                continue
            if core[j][i]:
                px(i, j, CORE)
            else:
                # 环的左上一半提亮一档，给 18px 的小图一点体积感
                px(i, j, HILIGHT if (i + j) < (SIZE - 1) else RING)
    return img


def write_png(path, img, scale=1):
    w = h = SIZE * scale
    raw = b''
    for j in range(h):
        row = b''
        for i in range(w):
            row += bytes(img[j // scale][i // scale])
        raw += b'\x00' + row

    def chunk(tag, data):
        return (struct.pack('>I', len(data)) + tag + data
                + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF))

    blob = (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9))
            + chunk(b'IEND', b''))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(blob)
    return blob


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview', action='store_true', help='额外写一张 8 倍放大预览图')
    args = ap.parse_args()

    img = build()
    blob = write_png(OUT, img)
    assert len(blob) > 0
    print('写出 %s（%d 字节，%dx%d）' % (OUT, len(blob), SIZE, SIZE))

    if args.preview:
        scratch = os.environ.get('TMPDIR') or os.path.join(os.getcwd(), 'build')
        prev = os.path.join(scratch, 'death_mark_x8.png')
        write_png(prev, img, scale=8)
        print('预览 %s' % prev)


if __name__ == '__main__':
    main()
