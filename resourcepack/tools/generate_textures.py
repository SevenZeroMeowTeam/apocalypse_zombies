"""末日风方块材质生成器。

生成两套资源包：
  resourcepack/apocalypse_16x/   16×16
  resourcepack/apocalypse_32x/   32×32

每个包同时包含：
  assets/minecraft/textures/block/   1.13+ 的扁平化名称
  assets/minecraft/textures/blocks/  1.12- 的旧名称（同一批像素的副本）

全部随机数都用固定种子，重复运行得到完全相同的图。
"""

import json
import math
import os
import random
import shutil
import zlib

from PIL import Image

import _legacy_stream

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --------------------------------------------------------------------------- 基础工具

def rgb(hex_color):
    h = hex_color.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def shade(color, amount):
    return tuple(max(0, min(255, c + amount)) for c in color)


def jitter(color, amount, rng):
    return tuple(max(0, min(255, c + rng.randint(-amount, amount))) for c in color)


def noise_image(size, base, amount, rng):
    img = Image.new('RGB', (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            px[x, y] = jitter(base, amount, rng)
    return img


def crack(img, dark, count, rng):
    px = img.load()
    size = img.width
    for _ in range(count):
        x = rng.randrange(size)
        y = rng.randrange(size)
        length = rng.randrange(size // 3, size)
        dx = rng.choice((-1, 0, 1))
        dy = rng.choice((-1, 0, 1))
        if dx == 0 and dy == 0:
            dx = 1
        for _ in range(length):
            if 0 <= x < size and 0 <= y < size:
                px[x, y] = jitter(dark, 8, rng)
            if rng.random() < 0.35:
                x += rng.choice((-1, 0, 1))
            else:
                x += dx
            y += dy
            if y < 0 or y >= size:
                break


def speckle(img, color, count, rng, radius=1):
    px = img.load()
    size = img.width
    for _ in range(count):
        x = rng.randrange(size)
        y = rng.randrange(size)
        for oy in range(-radius, radius + 1):
            for ox in range(-radius, radius + 1):
                if 0 <= x + ox < size and 0 <= y + oy < size:
                    if rng.random() < 0.75:
                        px[x + ox, y + oy] = jitter(color, 12, rng)


def save(path, img):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)


# --------------------------------------------------------------------------- 方块材质

def stone(size, rng):
    img = noise_image(size, rgb('#4b4b50'), 10, rng)
    crack(img, rgb('#2c2c30'), max(2, size // 6), rng)
    speckle(img, rgb('#5d5d63'), max(4, size // 3), rng)
    return img


def cobblestone(size, rng):
    img = noise_image(size, rgb('#35353a'), 14, rng)
    cell = max(3, size // 4)
    for y in range(0, size, cell):
        for x in range(0, size, cell):
            tone = rng.randint(-16, 18)
            for yy in range(y + 1, min(size, y + cell - 1)):
                for xx in range(x + 1, min(size, x + cell - 1)):
                    img.putpixel((xx, yy), jitter(shade(rgb('#55555b'), tone), 10, rng))
    crack(img, rgb('#242428'), max(2, size // 7), rng)
    return img


def dirt(size, rng):
    img = noise_image(size, rgb('#3a2d24'), 12, rng)
    speckle(img, rgb('#574636'), max(6, size // 2), rng)
    speckle(img, rgb('#6d665c'), max(3, size // 5), rng)  # 灰烬
    return img


def coarse_dirt(size, rng):
    img = dirt(size, rng)
    speckle(img, rgb('#2a201a'), max(4, size // 3), rng)
    return img


# 草方块顶/侧、树叶与枯木都在下方「植被（烘焙光照）」一节实现。


def gravel(size, rng):
    img = noise_image(size, rgb('#4a4744'), 16, rng)
    for _ in range(max(8, size)):
        x = rng.randrange(size)
        y = rng.randrange(size)
        tone = rng.choice((rgb('#5f5b57'), rgb('#393634'), rgb('#6e6a64'), rgb('#2e2b29')))
        for oy in range(2):
            for ox in range(2):
                if x + ox < size and y + oy < size:
                    img.putpixel((x + ox, y + oy), jitter(tone, 8, rng))
    return img


def sand(size, rng):
    img = noise_image(size, rgb('#b3a688'), 9, rng)
    speckle(img, rgb('#8f8267'), max(5, size // 2), rng)
    speckle(img, rgb('#cfc3a4'), max(4, size // 3), rng)
    return img


def sandstone_top(size, rng):
    img = sand(size, rng)
    return img


def sandstone_side(size, rng):
    img = noise_image(size, rgb('#a89a7d'), 8, rng)
    for y in range(0, size, max(3, size // 4)):
        for x in range(size):
            img.putpixel((x, y), jitter(rgb('#8f8267'), 8, rng))
    speckle(img, rgb('#c2b595'), max(3, size // 4), rng)
    return img


def planks_colored(size, rng, base, dark, light):
    img = noise_image(size, base, 8, rng)
    board = max(4, size // 4)
    for y in range(0, size, board):
        for x in range(size):
            img.putpixel((x, y), jitter(dark, 8, rng))
        for x in range(size):
            if rng.random() < 0.12:
                img.putpixel((x, min(size - 1, y + 1)), jitter(light, 10, rng))
    for y in range(size):
        for x in range(size):
            if rng.random() < 0.05:
                img.putpixel((x, y), jitter(dark, 8, rng))
    return img


def planks(size, rng):
    return planks_colored(size, rng, rgb('#5b4937'), rgb('#3a2d21'), rgb('#6d5a45'))


def log_side(size, rng):
    img = noise_image(size, rgb('#4a3a2c'), 10, rng)
    for x in range(size):
        if rng.random() < 0.30:
            for y in range(size):
                img.putpixel((x, y), jitter(rgb('#33271e'), 8, rng))
        elif rng.random() < 0.15:
            for y in range(size):
                img.putpixel((x, y), jitter(rgb('#5b4837'), 8, rng))
    return img


def log_top(size, rng):
    img = noise_image(size, rgb('#6a5540'), 8, rng)
    c = (size - 1) / 2.0
    for y in range(size):
        for x in range(size):
            d = max(abs(x - c), abs(y - c))
            if int(d) % 2 == 0:
                img.putpixel((x, y), jitter(rgb('#4a3a2c'), 8, rng))
    crack(img, rgb('#2e231a'), max(1, size // 10), rng)
    return img


# 树叶见下方「植被（烘焙光照）」一节：oak / spruce / birch / jungle / acacia /
# dark_oak / mangrove / azalea / cherry 共 9 种，共用同一套明暗规则。


def stone_bricks(size, rng, cracked=False):
    img = noise_image(size, rgb('#45454a'), 10, rng)
    mortar = rgb('#2a2a2e')
    step = max(4, size // 2)
    for y in range(0, size, step):
        for x in range(size):
            img.putpixel((x, y), jitter(mortar, 6, rng))
    for y in range(0, size, step):
        offset = 0 if (y // step) % 2 == 0 else step // 2
        for x in range(offset, size, step):
            for yy in range(y, min(size, y + step)):
                img.putpixel((x, yy), jitter(mortar, 6, rng))
    if cracked:
        crack(img, rgb('#1f1f22'), max(3, size // 5), rng)
    speckle(img, rgb('#55555b'), max(3, size // 4), rng)
    return img


def bricks(size, rng):
    img = noise_image(size, rgb('#6a3a30'), 8, rng)
    mortar = rgb('#3a3532')
    row = max(3, size // 4)
    for y in range(0, size, row):
        for x in range(size):
            img.putpixel((x, y), jitter(mortar, 6, rng))
        offset = 0 if (y // row) % 2 == 0 else row
        for x in range(offset, size, row * 2):
            for yy in range(y, min(size, y + row)):
                img.putpixel((x, yy), jitter(mortar, 6, rng))
    return img


def glass(size, rng):
    img = Image.new('RGBA', (size, size), (120, 150, 165, 40))
    px = img.load()
    edge = rgb('#8fa0a8')
    for i in range(size):
        px[i, 0] = (*edge, 200)
        px[i, size - 1] = (*edge, 200)
        px[0, i] = (*edge, 200)
        px[size - 1, i] = (*edge, 200)
    for _ in range(max(2, size // 8)):
        x = rng.randrange(1, size - 1)
        y = rng.randrange(1, size - 1)
        for k in range(rng.randint(2, size // 2)):
            if x + k < size - 1:
                px[x + k, y] = (210, 230, 240, 120)
            if y + k < size - 1:
                px[x, y + k] = (210, 230, 240, 110)
    return img


def ore(size, rng, color):
    img = stone(size, rng)
    speckle(img, rgb(color), max(6, size // 2), rng, radius=0)
    return img


def bedrock(size, rng):
    img = noise_image(size, rgb('#2a2a2e'), 18, rng)
    speckle(img, rgb('#151518'), max(8, size), rng)
    speckle(img, rgb('#45454a'), max(5, size // 2), rng)
    crack(img, rgb('#101012'), max(3, size // 5), rng)
    return img


def obsidian(size, rng):
    img = noise_image(size, rgb('#191322'), 8, rng)
    speckle(img, rgb('#3a2258'), max(4, size // 2), rng, radius=0)
    speckle(img, rgb('#7a4aa8'), max(2, size // 5), rng, radius=0)
    return img


def netherrack(size, rng):
    img = noise_image(size, rgb('#5a2424'), 14, rng)
    crack(img, rgb('#2e1010'), max(3, size // 5), rng)
    speckle(img, rgb('#7a2f2f'), max(4, size // 3), rng)
    return img


def soul_sand(size, rng):
    img = noise_image(size, rgb('#4a3a32'), 10, rng)
    speckle(img, rgb('#6b5a4a'), max(4, size // 2), rng)
    speckle(img, rgb('#2e2a3a'), max(3, size // 3), rng)
    return img


def blackstone(size, rng):
    img = noise_image(size, rgb('#2b2730'), 10, rng)
    speckle(img, rgb('#443f4a'), max(4, size // 3), rng)
    return img


def basalt_side(size, rng):
    img = noise_image(size, rgb('#3a3a42'), 8, rng)
    for x in range(size):
        if rng.random() < 0.35:
            for y in range(size):
                img.putpixel((x, y), jitter(rgb('#26262c'), 8, rng))
    return img


def deepslate(size, rng):
    img = noise_image(size, rgb('#3a3a40'), 8, rng)
    for y in range(size):
        if rng.random() < 0.4:
            for x in range(size):
                img.putpixel((x, y), jitter(rgb('#2a2a30'), 8, rng))
    crack(img, rgb('#1c1c20'), max(2, size // 6), rng)
    return img


def iron_block(size, rng):
    img = noise_image(size, rgb('#6a6a6e'), 8, rng)
    for x in range(size):
        img.putpixel((x, 0), jitter(rgb('#8a8a8e'), 8, rng))
        img.putpixel((x, size - 1), jitter(rgb('#3f3f43'), 8, rng))
    speckle(img, rgb('#7a4a32'), max(3, size // 3), rng)  # 锈迹
    return img


def gold_block(size, rng):
    img = noise_image(size, rgb('#8a7434'), 10, rng)
    speckle(img, rgb('#b39a4a'), max(4, size // 3), rng)
    speckle(img, rgb('#5a4a1e'), max(3, size // 4), rng)
    return img


def crafting_top(size, rng):
    img = planks(size, rng)
    line = rgb('#2e241a')
    for i in range(size):
        img.putpixel((i, size // 2), jitter(line, 6, rng))
        img.putpixel((size // 2, i), jitter(line, 6, rng))
    return img


def crafting_side(size, rng):
    img = planks(size, rng)
    for x in range(size):
        for y in range(max(1, size // 3), max(2, size // 3) + 2):
            img.putpixel((x, y), jitter(rgb('#3a2d21'), 6, rng))
    return img


def furnace_front(size, rng):
    img = stone(size, rng)
    dark = rgb('#222226')
    for x in range(size // 4, size - size // 4):
        for y in range(size // 2, size - size // 5):
            img.putpixel((x, y), jitter(dark, 6, rng))
    for x in range(size // 4, size - size // 4):
        img.putpixel((x, size // 2), jitter(rgb('#4a3a2a'), 6, rng))
    return img


# 枯木见下方「植被（烘焙光照）」一节。


def planks_palette(size, rng, base, dark, light):
    return planks_colored(size, rng, rgb(base), rgb(dark), rgb(light))


def glass_cracked(size, rng):
    img = glass(size, rng)
    px = img.load()
    # 更明显的裂纹：几条亮的折线
    for _ in range(max(3, size // 4)):
        x = rng.randrange(size)
        y = rng.randrange(size)
        dx = rng.choice((-1, 0, 1))
        dy = rng.choice((-1, 0, 1)) or 1
        for _ in range(rng.randrange(size // 2, size)):
            if 0 <= x < size and 0 <= y < size:
                px[x, y] = (220, 240, 250, rng.randrange(120, 200))
            x += dx
            y += dy
    # 缺角 / 破洞：把像素打成全透明
    for _ in range(max(2, size // 5)):
        cx = rng.randrange(size)
        cy = rng.randrange(size)
        r = rng.randint(1, max(1, size // 8))
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                if 0 <= xx < size and 0 <= yy < size and (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r:
                    px[xx, yy] = (0, 0, 0, 0)
    return img


def glass_pane_top(size, rng):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    edge = rgb('#93a6ad')
    mid = size // 2
    for x in range(size):
        img.putpixel((x, mid), (*jitter(edge, 10, rng), 210))
        if rng.random() < 0.25:
            img.putpixel((x, min(size - 1, mid + 1)), (*jitter(edge, 16, rng), 120))
    for _ in range(max(2, size // 6)):
        x = rng.randrange(size)
        img.putpixel((x, mid), (0, 0, 0, 0))
    return img


def circuit(size, rng, board, trace, pad):
    img = noise_image(size, rgb(board), 6, rng)
    for _ in range(max(6, size // 2)):
        x = rng.randrange(size)
        y = rng.randrange(size)
        horizontal = rng.random() < 0.5
        for _ in range(rng.randrange(size // 3, size)):
            if 0 <= x < size and 0 <= y < size:
                img.putpixel((x, y), jitter(rgb(trace), 10, rng))
                if rng.random() < 0.18 and x + 1 < size:
                    img.putpixel((x + 1, y), jitter(rgb(trace), 10, rng))
            x += 1 if horizontal else 0
            y += 0 if horizontal else 1
            if rng.random() < 0.12:
                horizontal = not horizontal
            if x >= size or y >= size:
                break
    for _ in range(max(3, size // 5)):
        x = rng.randrange(size - 1)
        y = rng.randrange(size - 1)
        for oy in range(2):
            for ox in range(2):
                img.putpixel((x + ox, y + oy), jitter(rgb(pad), 14, rng))
    return img


def solar_panel(size, rng):
    img = circuit(size, rng, '#1f2a30', '#3a5a5e', '#5f8a86')
    # 裂开的太阳能板：深缝 + 高光边
    for y in range(0, size, max(4, size // 3)):
        for x in range(size):
            img.putpixel((x, y), jitter(rgb('#0e1418'), 6, rng))
    crack(img, rgb('#0a0e10'), max(2, size // 6), rng)
    return img


def target_face(size, rng):
    img = noise_image(size, rgb('#5a4a3a'), 8, rng)
    cx = cy = (size - 1) / 2.0
    for y in range(size):
        for x in range(size):
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if d < size * 0.16:
                img.putpixel((x, y), jitter(rgb('#a02a22'), 10, rng))
            elif d < size * 0.30:
                img.putpixel((x, y), jitter(rgb('#c8bda8'), 8, rng))
            elif d < size * 0.44:
                img.putpixel((x, y), jitter(rgb('#8a2a22'), 10, rng))
    crack(img, rgb('#2e231a'), max(2, size // 6), rng)
    return img


def note_block(size, rng):
    img = planks_colored(size, rng, rgb('#4a3a2c'), rgb('#2e241a'), rgb('#5b4837'))
    for _ in range(max(4, size // 4)):
        x = rng.randrange(size - 1)
        y = rng.randrange(size - 1)
        for oy in range(2):
            for ox in range(2):
                img.putpixel((x + ox, y + oy), jitter(rgb('#8a7434'), 12, rng))
    return img


def copper_circuit(size, rng):
    img = circuit(size, rng, '#2f5a52', '#4f9a86', '#a8d8c0')
    speckle(img, rgb('#2a4a42'), max(4, size // 3), rng)
    return img


def cobweb(size, rng):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    px = img.load()
    color = (205, 205, 212, 185)
    c = (size - 1) / 2.0
    # 放射线
    for i in range(8):
        import math
        ang = i * math.pi / 4.0
        dx = math.cos(ang)
        dy = math.sin(ang)
        for r in range(1, size):
            x = int(round(c + dx * r))
            y = int(round(c + dy * r))
            if 0 <= x < size and 0 <= y < size:
                px[x, y] = (color[0], color[1], color[2], rng.randrange(120, 200))
    # 同心网
    for ring in range(2, size, max(3, size // 4)):
        steps = max(12, ring * 6)
        import math
        prev = None
        for k in range(steps + 1):
            a = k * 2.0 * math.pi / steps
            x = int(round(c + math.cos(a) * ring))
            y = int(round(c + math.sin(a) * ring))
            if prev and 0 <= x < size and 0 <= y < size and 0 <= prev[0] < size and 0 <= prev[1] < size:
                px[x, y] = (color[0], color[1], color[2], rng.randrange(100, 170))
            prev = (x, y)
    return img


def iron_bars(size, rng):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    bar = rgb('#6a6a6e')
    for x in range(size):
        if x % max(4, size // 4) in (1, 2):
            for y in range(size):
                img.putpixel((x, y), (*jitter(bar, 12, rng), 255))
    for x in range(size):
        img.putpixel((x, 0), (*jitter(rgb('#8a8a8e'), 8, rng), 255))
        img.putpixel((x, size - 1), (*jitter(rgb('#3f3f43'), 8, rng), 255))
    return img


def chain(size, rng):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    link = rgb('#5a5a60')
    step = max(4, size // 4)
    for y0 in range(0, size, step):
        wide = (y0 // step) % 2 == 0
        for y in range(y0, min(size, y0 + step)):
            if wide:
                xs = (size // 2 - 2, size // 2 + 2)
            else:
                xs = (size // 2 - 1, size // 2 + 1)
            for x in xs:
                if 0 <= x < size:
                    img.putpixel((x, y), (*jitter(link, 14, rng), 255))
    return img


def lantern(size, rng):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    px = img.load()
    frame = rgb('#4a4a50')
    glow = rgb('#ffb347')
    for x in range(size):
        for y in range(size):
            border = x < 2 or x >= size - 2 or y < 2 or y >= size - 2
            inner = 4 <= x < size - 4 and 4 <= y < size - 4
            if border:
                px[x, y] = (*jitter(frame, 10, rng), 255)
            elif inner:
                px[x, y] = (*jitter(glow, 26, rng), 235)
    # 提手
    for x in range(size // 3, size - size // 3):
        px[x, 0] = (*jitter(frame, 10, rng), 255)
    return img


def sculk(size, rng):
    img = noise_image(size, rgb('#101c22'), 8, rng)
    speckle(img, rgb('#1e3a44'), max(4, size // 2), rng)
    for _ in range(max(2, size // 6)):
        x = rng.randrange(size)
        y = rng.randrange(size)
        for _ in range(rng.randrange(size // 2, size)):
            if 0 <= x < size and 0 <= y < size:
                img.putpixel((x, y), jitter(rgb('#3f8a8a'), 20, rng))
            x += rng.choice((-1, 0, 1))
            y += rng.choice((-1, 0, 1))
    return img


def sculk_vein(size, rng):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    for _ in range(max(3, size // 4)):
        x = rng.randrange(size)
        y = rng.randrange(size)
        for _ in range(rng.randrange(size // 2, size)):
            if 0 <= x < size and 0 <= y < size:
                img.putpixel((x, y), (*jitter(rgb('#3f8a8a'), 24, rng), rng.randrange(180, 255)))
            x += rng.choice((-1, 0, 1))
            y += rng.choice((-1, 0, 1))
    return img


# --------------------------------------------------------------------------- 植被（烘焙光照）
#
# 草方块顶/侧、枯木与 9 种树叶共用同一套明暗规则。目的是把光照画进像素本身，
# 而不是指望方块光照模型替我们补：
#   1. 统一假想光源在左上（LIGHT_X/LIGHT_Y），每片叶簇、每根草叶都按球冠法线算受光量；
#   2. 叶簇按绘制先后记录高度，全部画完再按高度场补一层环境遮蔽 —— 被高处围住的像素变暗；
#   3. 迎光轮廓补一道微高光、背光侧压暗，于是叶簇有了体积，而不是一块平板色斑；
#   4. 所有几何都用环绕坐标（% size）绘制，平铺时接缝处仍然连续。
# 调色板纪律：枯黄、去饱和、偏暖灰；不用鲜艳荧光绿。
# 每张贴图拿到的都是 texture_rng(size, name) 给的独立随机源，所以改一种植被的画法
# 不会挪动其它贴图的像素。

LIGHT_X, LIGHT_Y = -0.70, -0.72   # 指向光源的单位向量：左上
HIGHLIGHT = rgb('#cfc49f')        # 迎光面的暖灰上限：再亮也不往白里烧

GRASS_TONES = ('#6a6f47', '#5a6139', '#76774a', '#4d5533')


def _clip(v):
    return 0 if v < 0 else (255 if v > 255 else int(round(v)))


def _lit(color, factor, rng, noise):
    """按受光系数取色：背光侧直接压暗，迎光侧向暖灰混合。

    单纯乘系数会把亮面推到 240+ 的惨白像素，枯黄的末日调子就没了；
    往一个暖灰上限混，高光始终留在"晒脱色的枯草"里。
    """
    if factor <= 1.0:
        return tuple(_clip(c * factor + rng.uniform(-noise, noise)) for c in color)
    base = _mix(color, HIGHLIGHT, min(0.60, (factor - 1.0) * 0.62))
    return tuple(_clip(c + rng.uniform(-noise, noise)) for c in base)


def _mix(a, b, t):
    return tuple(_clip(a[i] * (1.0 - t) + b[i] * t) for i in range(3))


class _Layers(object):
    """环绕画布：颜色 + 高度（越大越靠前）。坐标取模，所以画出来的东西天然能平铺。"""

    def __init__(self, size):
        self.size = size
        self.color = [[None] * size for _ in range(size)]
        self.h = [[-1] * size for _ in range(size)]

    def put(self, x, y, color, h):
        s = self.size
        self.color[y % s][x % s] = color
        self.h[y % s][x % s] = h

    def fill(self, tone, noise, rng):
        for y in range(self.size):
            for x in range(self.size):
                self.color[y][x] = _lit(tone, 1.0, rng, noise)
                self.h[y][x] = 0

    def to_image(self):
        s = self.size
        img = Image.new('RGBA', (s, s), (0, 0, 0, 0))
        px = img.load()
        for y in range(s):
            for x in range(s):
                c = self.color[y][x]
                if c is not None:
                    px[x, y] = (c[0], c[1], c[2], 255)
        return img


def _clump(layer, cx, cy, rx, ry, tone, h, rng, rough=0.30, rim=0.28, falloff=0.42):
    """一片叶簇：球冠法线受光 + 边缘被啃出锯齿 + 迎光侧微高光。"""
    rx = max(1, int(round(rx)))
    ry = max(1, int(round(ry)))
    # 径向抖动：把规整椭圆掰成有裂片/缺口的叶簇，否则一眼就是"圆球"
    ph1, ph2 = rng.uniform(0.0, 6.283), rng.uniform(0.0, 6.283)
    k1 = rng.choice((2, 3, 4))
    k2 = rng.choice((5, 6, 7))
    for dy in range(-ry, ry + 1):
        for dx in range(-rx, rx + 1):
            u = dx / float(rx)
            v = dy / float(ry)
            d2 = u * u + v * v
            if d2 > 1.69:
                continue
            ang = math.atan2(v, u)
            lim = 1.0 + 0.20 * math.sin(k1 * ang + ph1) + 0.13 * math.sin(k2 * ang + ph2)
            d = math.sqrt(d2)
            if d > lim:
                continue
            dn = d / lim
            if dn > 0.62 and rng.random() < rough * dn:   # 边缘啃掉，顺带留出透光缝
                continue
            ndl = u * LIGHT_X + v * LIGHT_Y               # 法线朝左上时为正
            factor = 1.0 + falloff * ndl
            if dn > 0.66 and ndl > 0.10 and rng.random() < 0.55:
                factor += rim                             # 迎光轮廓的微高光
            layer.put(cx + dx, cy + dy, _lit(tone, factor, rng, 5), h)


def _occlude(layer, strength=0.30):
    """按高度场补环境遮蔽：被更高的叶片围住的像素变暗，层叠就有了厚度。"""
    s = layer.size
    for y in range(s):
        for x in range(s):
            own = layer.h[y][x]
            c = layer.color[y][x]
            if own < 0 or c is None:
                continue
            occ = 0.0
            for oy in (-1, 0, 1):
                for ox in (-1, 0, 1):
                    if ox == 0 and oy == 0:
                        continue
                    if layer.h[(y + oy) % s][(x + ox) % s] > own:
                        # 光源在左上：左上的遮挡物挡光更狠
                        occ += 1.0 if (ox * LIGHT_X + oy * LIGHT_Y) > 0 else 0.6
            factor = 1.0 - strength * occ / 8.0
            layer.color[y][x] = tuple(_clip(ch * factor) for ch in c)


def _veins(layer, rng, count, dim=0.80, steps=(2, 4)):
    """在叶簇内部划几道短暗线：把大色块切成一片片叶子，否则只有"苔藓感"。"""
    s = layer.size
    dirs = ((1, 0), (0, 1), (1, 1), (1, -1))
    for _ in range(count):
        x, y = rng.randrange(s), rng.randrange(s)
        if layer.color[y][x] is None:
            continue
        dx, dy = dirs[rng.randrange(len(dirs))]
        for k in range(rng.randint(steps[0], steps[1])):
            xx, yy = x + dx * k, y + dy * k
            c = layer.color[yy % s][xx % s]
            if c is None:
                break
            layer.put(xx, yy, tuple(_clip(ch * dim) for ch in c), layer.h[yy % s][xx % s])


def _blade(layer, x, y, dx, steps, tone, h, rng):
    """一根草叶：向上长，梢部迎光更亮，根部压暗。"""
    for k in range(steps):
        f = 0.84 + 0.52 * (k / float(max(1, steps - 1)))
        layer.put(x + dx * (k // 2), y - k, _lit(tone, f, rng, 6), h + k)


def _thin_to(layer, target, rng):
    """按目标覆盖率从边缘啃像素：既是透光孔洞，也把 16x/32x 两套的叶密度拉齐。

    只啃边缘 —— 叶簇中间不会变成筛子，轮廓反而更像一片片叶子。按覆盖率而不是
    按比例削薄，是因为小尺寸的周长/面积比更大，按比例削会让 16x 明显比 32x 稀疏。
    """
    s = layer.size
    solid = sum(1 for y in range(s) for x in range(s) if layer.color[y][x] is not None)
    limit = int(round(s * s * target))
    if solid <= limit:
        return
    order = [(x, y) for y in range(s) for x in range(s)]
    # 反复扫：每一轮啃掉当前所有可啃的边缘，直到落进目标覆盖率
    while solid > limit:
        rng.shuffle(order)
        removed = 0
        for x, y in order:
            if solid <= limit:
                break
            if layer.color[y][x] is None:
                continue
            for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if layer.color[(y + oy) % s][(x + ox) % s] is None:
                    layer.color[y][x] = None
                    layer.h[y][x] = -1
                    solid -= 1
                    removed += 1
                    break
        if not removed:
            # 画面已经被铺满时没有可啃的边缘：先戳几处孔，下一轮再从孔里往外啃
            for _ in range(max(4, s // 2)):
                if solid <= limit:
                    break
                x, y = rng.randrange(s), rng.randrange(s)
                if layer.color[y][x] is not None:
                    layer.color[y][x] = None
                    layer.h[y][x] = -1
                    solid -= 1


def grass_top(size, rng):
    """草方块顶面：枯黄草皮 + 低频明暗分块 + 层层压着的草叶，顶面保持不透明。"""
    layer = _Layers(size)
    layer.fill(rgb('#545b36'), 12, rng)
    for _ in range(max(3, size // 3)):           # 低频明暗块：草皮分片受光
        tone = rgb(GRASS_TONES[rng.randrange(len(GRASS_TONES))])
        r = rng.randint(max(2, size // 4), max(3, size // 2))
        _clump(layer, rng.randrange(size), rng.randrange(size), r, r, tone, 1,
               rng, rough=0.45, rim=0.16, falloff=0.34)
    for _ in range(max(18, size * 3)):           # 草叶：一片一片往上长
        tone = _mix(rgb(GRASS_TONES[rng.randrange(len(GRASS_TONES))]),
                    rgb('#8d8657'), rng.random() * 0.55)
        _blade(layer, rng.randrange(size), rng.randrange(size),
               rng.choice((-1, 0, 0, 1)), rng.randint(2, max(3, size // 5)), tone, 2, rng)
    _veins(layer, rng, max(6, size), dim=0.82)   # 草缝的暗纹，免得糊成一片
    _occlude(layer, 0.34)
    for _ in range(max(4, size // 2)):           # 缝隙里的枯穗（暖灰，不能发白）
        _clump(layer, rng.randrange(size), rng.randrange(size), 1, 1,
               rgb('#8d8355'), 3, rng, rough=0.0, rim=0.0, falloff=0.0)
    return layer.to_image()


def grass_side(size, rng):
    """草方块侧面：上沿枯草层压在泥土上，草根处有接触阴影。"""
    # 泥土底直接用 dirt.png 的那份随机源：草方块侧脸的下半截与泥土方块逐像素一致，
    # 两者并排放时才不会出现"两种土"
    img = dirt(size, texture_rng(size, 'dirt')).convert('RGBA')
    px = img.load()
    base = max(2, size // 3)
    amp = max(1, size // 12)

    def depth_at(x):
        # 垂深是环上的正弦和：平铺时左右相接处不会突然断开
        t = (x % size) / float(size) * 2.0 * math.pi
        return base + int(round(amp * (0.6 * math.sin(t + 0.7)
                                       + 0.4 * math.sin(3.0 * t + 2.1))))

    hang = [rng.randint(1, max(1, size // 8)) if rng.random() < 0.45 else 0
            for _ in range(size)]

    for x in range(size):
        d = max(1, depth_at(x))
        total = min(size - 1, d + hang[x])
        col = 0.94 + 0.12 * rng.random()     # 每列整体明暗不同，免得草层成一条平带
        for y in range(total):
            if y < d:
                f = (0.86 + 0.34 * (1.0 - y / float(d))) * col      # 越靠上越迎光
                tone = rgb('#5f6640') if (x * 7 + y * 3) % 4 else rgb('#6e7048')
            else:
                f = (0.80 - 0.10 * (y - d)) * col                   # 垂下来的草叶更暗
                tone = rgb('#545d36')
            if rng.random() < 0.12:
                f *= 0.86                                            # 草层里的暗缝
            px[x, y] = (*_lit(tone, f, rng, 8), 255)
        left = depth_at(x - 1) + hang[x - 1]
        if total > left:                                         # 向左突出的草沿：迎光
            for y in range(max(0, left), total):
                c = px[x, y]
                px[x, y] = (_clip(c[0] * 1.12), _clip(c[1] * 1.12), _clip(c[2] * 1.08), 255)
        for y in (total, total + 1):                             # 草根下的接触阴影
            if y < size:
                c = px[x, y]
                k = 0.72 if y == total else 0.85
                px[x, y] = (_clip(c[0] * k), _clip(c[1] * k), _clip(c[2] * k), 255)
    for x in range(size):                                # 顶行是草皮被侧看的受光面
        c = px[x, 0]
        px[x, 0] = (_clip(c[0] * 1.14), _clip(c[1] * 1.14), _clip(c[2] * 1.10), 255)
    return img


def dead_bush(size, rng):
    """枯木：根部一簇，向上散成几根带岔的枯枝；枝梢迎光、交叠处靠高度场压暗。"""
    layer = _Layers(size)
    cx = size // 2
    base_y = size - max(1, size // 12)
    tones = ('#6f6040', '#5c4f36', '#84724c', '#4a4030')

    def walk(x, y, drift, steps, tone, h, split):
        for k in range(steps):
            f = 0.80 + 0.50 * min(1.0, k / float(max(1, steps - 1)))   # 枝梢迎光
            layer.put(x, y, _lit(tone, f, rng, 7), h + k)
            layer.put(x, y - 1, _lit(tone, f * 0.88, rng, 7), h + k)   # 两像素厚，枝才有肉
            if split and k > 1 and rng.random() < 0.34:
                walk(x, y, rng.choice((-1, 1)), max(2, steps // 2),
                     tone, h + k + 1, False)
            x += drift
            y -= 1
            if rng.random() < 0.30:
                drift = max(-1, min(1, drift + rng.choice((-1, 0, 1))))
            if y < 1 or x < 0 or x >= size:
                break

    for i in range(max(4, size // 2)):
        tone = rgb(tones[rng.randrange(len(tones))])
        walk(cx + rng.randint(-max(1, size // 8), max(1, size // 8)), base_y,
             rng.choice((-1, 0, 1)), rng.randint(max(4, size // 3), size - 2),
             tone, i, True)
    _occlude(layer, 0.35)
    return layer.to_image()


LEAF_STYLE = {
    # 阔叶与针叶的差异全在参数里：色调、簇大小与形状、密度、边缘疏松度、覆盖率
    # （cover 是削薄之后的目标不透明占比，两套分辨率取同一个值，密度才不会走样）
    'oak_leaves': dict(tones=('#626f3f', '#4e5a33', '#77814b', '#8a8557'),
                       accent='#9c8f5e', clumps=26, r=(1.6, 3.6), flat=1.00,
                       rough=0.34, cover=0.70),
    'spruce_leaves': dict(tones=('#3f5346', '#33443a', '#4d6353', '#5e6f5c'),
                          accent='#6d7a63', clumps=30, r=(1.2, 2.4), flat=1.00,
                          rough=0.42, cover=0.64, needle=True),
    'birch_leaves': dict(tones=('#6d7550', '#5a6141', '#828860', '#9a9a72'),
                         accent='#a8a67e', clumps=24, r=(1.4, 3.0), flat=1.00,
                         rough=0.40, cover=0.54),
    'jungle_leaves': dict(tones=('#4f6634', '#3e5128', '#657a45', '#7c8452'),
                          accent='#8a8f5c', clumps=26, r=(2.0, 4.2), flat=1.00,
                          rough=0.26, cover=0.82),
    'acacia_leaves': dict(tones=('#76703f', '#5e5a31', '#8d854c', '#9d9463'),
                          accent='#a89a67', clumps=26, r=(1.8, 3.4), flat=0.62,
                          rough=0.36, cover=0.68),
    'dark_oak_leaves': dict(tones=('#43502f', '#333d24', '#556139', '#656b41'),
                            accent='#77744a', clumps=26, r=(1.8, 3.8), flat=1.00,
                            rough=0.28, cover=0.78),
    'mangrove_leaves': dict(tones=('#5c6440', '#464c2f', '#6f7350', '#8a7a55'),
                            accent='#96825c', clumps=26, r=(1.6, 3.4), flat=1.00,
                            rough=0.34, cover=0.72),
    'azalea_leaves': dict(tones=('#5f6b48', '#4b5638', '#727a55', '#8f8471'),
                          accent='#a3907e', clumps=20, r=(1.5, 3.2), flat=1.00,
                          rough=0.36, cover=0.66),
    'cherry_leaves': dict(tones=('#8a705f', '#6f574a', '#a08477', '#b09a8a'),
                          accent='#bfae9c', clumps=24, r=(1.3, 2.9), flat=1.00,
                          rough=0.40, cover=0.58),
}


def leaf_tile(size, name, rng):
    spec = LEAF_STYLE[name]
    layer = _Layers(size)
    scale = size / 16.0
    lo, hi = spec['r']
    count = max(6, int(round(spec['clumps'] * scale * scale)))
    for i in range(count):
        rx = rng.uniform(lo, hi) * scale
        ry = rx * spec['flat'] * rng.uniform(0.82, 1.18)
        tone = _mix(rgb(spec['tones'][rng.randrange(len(spec['tones']))]),
                    rgb(spec['accent']), rng.random() * 0.32)
        _clump(layer, rng.randrange(size), rng.randrange(size), rx, ry,
               tone, i, rng, rough=spec['rough'], rim=0.24, falloff=0.46)
    if spec.get('needle'):
        # 针叶：成扇形的短针，针尖迎光（云杉的"针"感就在这里）
        for _ in range(count * 2):
            cx, cy = rng.randrange(size), rng.randrange(size)
            tone = rgb(spec['tones'][rng.randrange(len(spec['tones']))])
            dx = rng.choice((-1, 1))
            n = rng.randint(2, max(3, int(round(3 * scale))))
            for k in range(n):
                f = 0.80 + 0.55 * (k / float(max(1, n)))
                layer.put(cx + dx * k, cy - k, _lit(tone, f, rng, 5), count + k)
    _veins(layer, rng, max(4, count), dim=0.78)   # 叶脉/叶片分界，打散大色块
    _thin_to(layer, spec['cover'], rng)
    _occlude(layer, 0.32)
    return layer.to_image()


# --------------------------------------------------------------------------- 资源包装配

MODERN = {
    'stone': stone,
    'cobblestone': cobblestone,
    'dirt': dirt,
    'coarse_dirt': coarse_dirt,
    'grass_block_top': grass_top,
    'grass_block_side': grass_side,
    'gravel': gravel,
    'sand': sand,
    'sandstone_top': sandstone_top,
    'sandstone_side': sandstone_side,
    'sandstone_bottom': sandstone_top,
    'oak_planks': planks,
    'oak_log': log_side,
    'oak_log_top': log_top,
    'oak_leaves': lambda s_, r_: leaf_tile(s_, 'oak_leaves', r_),
    'spruce_leaves': lambda s_, r_: leaf_tile(s_, 'spruce_leaves', r_),
    'birch_leaves': lambda s_, r_: leaf_tile(s_, 'birch_leaves', r_),
    'jungle_leaves': lambda s_, r_: leaf_tile(s_, 'jungle_leaves', r_),
    'acacia_leaves': lambda s_, r_: leaf_tile(s_, 'acacia_leaves', r_),
    'dark_oak_leaves': lambda s_, r_: leaf_tile(s_, 'dark_oak_leaves', r_),
    'mangrove_leaves': lambda s_, r_: leaf_tile(s_, 'mangrove_leaves', r_),
    'azalea_leaves': lambda s_, r_: leaf_tile(s_, 'azalea_leaves', r_),
    'cherry_leaves': lambda s_, r_: leaf_tile(s_, 'cherry_leaves', r_),
    'mossy_cobblestone': cobblestone,
    'stone_bricks': lambda s, r: stone_bricks(s, r, False),
    'cracked_stone_bricks': lambda s, r: stone_bricks(s, r, True),
    'bricks': bricks,
    'glass': glass_cracked,
    'glass_pane_top': glass_pane_top,
    'bedrock': bedrock,
    'obsidian': obsidian,
    'netherrack': netherrack,
    'soul_sand': soul_sand,
    'blackstone': blackstone,
    'basalt_side': basalt_side,
    'basalt_top': blackstone,
    'deepslate': deepslate,
    'deepslate_top': deepslate,
    'iron_block': iron_block,
    'gold_block': gold_block,
    'coal_ore': lambda s, r: ore(s, r, '#2a2a2e'),
    'iron_ore': lambda s, r: ore(s, r, '#8a6a52'),
    'gold_ore': lambda s, r: ore(s, r, '#b39a4a'),
    'diamond_ore': lambda s, r: ore(s, r, '#5aa8a0'),
    'redstone_ore': lambda s, r: ore(s, r, '#a02a2a'),
    'lapis_ore': lambda s, r: ore(s, r, '#3a5a9a'),
    'crafting_table_top': crafting_top,
    'crafting_table_side': crafting_side,
    'crafting_table_front': crafting_side,
    'furnace_front': furnace_front,
    'furnace_side': stone,
    'furnace_top': stone,
    'dead_bush': dead_bush,
    'redstone_block': lambda s_, r_: circuit(s_, r_, '#3a1414', '#a02a2a', '#ff6a4a'),
    'observer_top': lambda s_, r_: circuit(s_, r_, '#24262c', '#3a5a6a', '#6ad0e0'),
    'observer_side': lambda s_, r_: circuit(s_, r_, '#2a2c32', '#3a4a5a', '#5aa0b0'),
    'daylight_detector_top': solar_panel,
    'target_top': target_face,
    'note_block': note_block,
    'copper_block': copper_circuit,
    'spruce_planks': lambda s_, r_: planks_palette(s_, r_, '#4a3a2a', '#2e2218', '#5b4835'),
    'birch_planks': lambda s_, r_: planks_palette(s_, r_, '#8a7a5a', '#5e523c', '#a89a76'),
    'jungle_planks': lambda s_, r_: planks_palette(s_, r_, '#5a4030', '#3a2a1e', '#6e5040'),
    'acacia_planks': lambda s_, r_: planks_palette(s_, r_, '#6a4430', '#442a1e', '#7e5640'),
    'dark_oak_planks': lambda s_, r_: planks_palette(s_, r_, '#3a2a1e', '#241a12', '#4a3828'),
    'crimson_planks': lambda s_, r_: planks_palette(s_, r_, '#5a2a3a', '#3a1a26', '#6e3a4a'),
    'warped_planks': lambda s_, r_: planks_palette(s_, r_, '#2a5a52', '#1a3a34', '#3a6e64'),
    'cobweb': cobweb,
    'iron_bars': iron_bars,
    'chain': chain,
    'lantern': lantern,
    'sculk': sculk,
    'sculk_vein': sculk_vein,
}

# 本次涉及的全部植被贴图（12 张）：草方块顶/侧、枯木、9 种树叶。
# 这份清单同时决定 build_pack 的日志与 build.gradle 要内嵌进 mod jar 的 16x 子集。
VEGETATION = (
    'grass_block_top', 'grass_block_side', 'dead_bush',
    'oak_leaves', 'spruce_leaves', 'birch_leaves', 'jungle_leaves',
    'acacia_leaves', 'dark_oak_leaves', 'mangrove_leaves', 'azalea_leaves',
    'cherry_leaves',
)

# 相对上一版新增的 8 种树叶（其余 4 张是原有植被贴图的重绘）
NEW_VEGETATION = (
    'spruce_leaves', 'birch_leaves', 'jungle_leaves', 'acacia_leaves',
    'dark_oak_leaves', 'mangrove_leaves', 'azalea_leaves', 'cherry_leaves',
)

# 旧版（1.12-）文件名 → 新版纹理名
LEGACY = {
    'stone': 'stone',
    'cobblestone': 'cobblestone',
    'dirt': 'dirt',
    'gravel': 'gravel',
    'sand': 'sand',
    'sandstone_top': 'sandstone_top',
    'sandstone_side': 'sandstone_side',
    'sandstone_bottom': 'sandstone_bottom',
    'planks_oak': 'oak_planks',
    'log_oak': 'oak_log',
    'log_oak_top': 'oak_log_top',
    'leaves_oak': 'oak_leaves',
    'leaves_spruce': 'spruce_leaves',
    'leaves_birch': 'birch_leaves',
    'leaves_jungle': 'jungle_leaves',
    'leaves_acacia': 'acacia_leaves',
    'leaves_big_oak': 'dark_oak_leaves',
    'leaves_mangrove': 'mangrove_leaves',
    'leaves_azalea': 'azalea_leaves',
    'leaves_cherry': 'cherry_leaves',
    'cobblestone_mossy': 'mossy_cobblestone',
    'bedrock': 'bedrock',
    'obsidian': 'obsidian',
    'netherrack': 'netherrack',
    'soul_sand': 'soul_sand',
    'stonebrick': 'stone_bricks',
    'stonebrick_cracked': 'cracked_stone_bricks',
    'brick': 'bricks',
    'glass': 'glass',
    'glass_pane_top': 'glass_pane_top',
    'iron_block': 'iron_block',
    'gold_block': 'gold_block',
    'coal_ore': 'coal_ore',
    'iron_ore': 'iron_ore',
    'gold_ore': 'gold_ore',
    'diamond_ore': 'diamond_ore',
    'redstone_ore': 'redstone_ore',
    'lapis_ore': 'lapis_ore',
    'crafting_table_top': 'crafting_table_top',
    'crafting_table_side': 'crafting_table_side',
    'crafting_table_front': 'crafting_table_front',
    'furnace_front_off': 'furnace_front',
    'furnace_side': 'furnace_side',
    'furnace_top': 'furnace_top',
    'grass_top': 'grass_block_top',
    'grass_side': 'grass_block_side',
    'deadbush': 'dead_bush',
    'redstone_block': 'redstone_block',
    'observer_top': 'observer_top',
    'observer_side': 'observer_side',
    'daylight_detector_top': 'daylight_detector_top',
    'target_top': 'target_top',
    'noteblock': 'note_block',
    'planks_spruce': 'spruce_planks',
    'planks_birch': 'birch_planks',
    'planks_jungle': 'jungle_planks',
    'planks_acacia': 'acacia_planks',
    'planks_big_oak': 'dark_oak_planks',
    'web': 'cobweb',
    'iron_bars': 'iron_bars',
}

PACK_META = {
    # 15 = 1.20.1 的格式，也是本包的基准版本。1.20.1 **只读 pack_format**、完全不读
    # supported_formats：写 4 会被判为"为旧版本制作"并从 options.txt 里移除
    # （实测日志：Removed resource pack file/apocalypse_16x ... no longer compatible）。
    # supported_formats 只在 1.20.2+ 生效，留着覆盖更新的版本。
    "pack": {
        "pack_format": 15,
        "supported_formats": {"min_inclusive": 4, "max_inclusive": 99},
        "description": "§5Apocalypse Zombies §8· §7Scorched 16x\n§8Cracked stone, ash, rust and dead grass"
    }
}

ICON = rgb('#4b4b50')


def build_icon(path):
    size = 64
    rng = random.Random(0xA90C)
    img = stone(size, rng)
    # 紫色裂纹 + 中央骷髅般的暗斑
    px = img.load()
    for _ in range(26):
        x = rng.randrange(8, size - 8)
        y = rng.randrange(8, size - 8)
        for k in range(rng.randint(3, 10)):
            if 0 <= x < size and 0 <= y < size:
                px[x, y] = jitter(rgb('#7a3fae'), 20, rng)
            x += rng.choice((-1, 0, 1))
            y += rng.choice((-1, 0, 1))
    img.save(path)


def texture_rng(size, name):
    """每张贴图一个独立随机源。

    种子只取决于分辨率和贴图名 —— 加一张新贴图、或改动某一张的取数次数，
    都不会挪动其它贴图的像素，所以重跑时改动能干净地限定在被改的那几张上。
    """
    return random.Random(0x4A0C + size * 7919 + zlib.crc32(name.encode('utf-8')))


def build_pack(target, size, description):
    block_dir = os.path.join(target, 'assets', 'minecraft', 'textures', 'block')
    legacy_dir = os.path.join(target, 'assets', 'minecraft', 'textures', 'blocks')
    if os.path.isdir(target):
        shutil.rmtree(target)
    os.makedirs(block_dir, exist_ok=True)
    os.makedirs(legacy_dir, exist_ok=True)

    # 第一趟：按 HEAD 的 MODERN 顺序、在同一条共享随机流上生成非植被贴图。
    # 4 个植被槽位在这里只调用 _legacy_stream.advance()，把共享流推到它历史上该在的位置
    # （原因见 _legacy_stream.py 顶部注释）—— 于是 61 张非植被贴图与 HEAD 逐字节相同。
    stream = random.Random(0x4A0C + size)
    for name, fn in MODERN.items():
        if name in VEGETATION:
            _legacy_stream.advance(name, size, stream)
            continue
        save(os.path.join(block_dir, name + '.png'), fn(size, stream))

    # 第二趟：12 张植被用每贴图独立种子重画（含烘焙光照），与共享流彻底解耦。
    for name in VEGETATION:
        save(os.path.join(block_dir, name + '.png'),
             MODERN[name](size, texture_rng(size, name)))
    for legacy, modern in LEGACY.items():
        shutil.copyfile(os.path.join(block_dir, modern + '.png'),
                        os.path.join(legacy_dir, legacy + '.png'))

    meta = json.loads(json.dumps(PACK_META))
    meta['pack']['description'] = description
    with open(os.path.join(target, 'pack.mcmeta'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write('\n')
    build_icon(os.path.join(target, 'pack.png'))
    print('built %s  (%dx%d)' % (target, size, size))
    print('  block/ %d png, blocks/ %d png' % (len(MODERN), len(LEGACY)))
    for name in VEGETATION:
        print('  %s  block/%s.png %dx%d'
              % ('new' if name in NEW_VEGETATION else 'veg', name, size, size))


def main():
    build_pack(os.path.join(ROOT, 'apocalypse_16x'), 16,
               "§5Apocalypse Zombies §8· §7Scorched 16x\n§8Cracked stone, ash, rust and dead grass")
    build_pack(os.path.join(ROOT, 'apocalypse_32x'), 32,
               "§5Apocalypse Zombies §8· §7Scorched 32x\n§8Cracked stone, ash, rust and dead grass")


if __name__ == '__main__':
    main()
