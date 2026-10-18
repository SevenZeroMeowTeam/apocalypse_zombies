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
import os
import random
import shutil

from PIL import Image

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


def grass_top(size, rng):
    img = noise_image(size, rgb('#5b6440'), 14, rng)
    speckle(img, rgb('#6f7a4a'), max(5, size // 2), rng)
    speckle(img, rgb('#8a7f55'), max(3, size // 4), rng)  # 枯黄
    speckle(img, rgb('#3f452c'), max(4, size // 3), rng)
    return img


def grass_side(size, rng):
    img = dirt(size, rng)
    grass = rgb('#55603c')
    fringe = max(2, size // 6)
    for x in range(size):
        depth = fringe + rng.randint(-1, 2)
        for y in range(max(0, depth)):
            img.putpixel((x, y), jitter(grass, 12, rng))
        if depth < size:
            img.putpixel((x, min(size - 1, depth)), jitter(rgb('#3d4529'), 10, rng))
    return img


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


def leaves(size, rng):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    px = img.load()
    for _ in range(max(32, size * size // 2)):
        x = rng.randrange(size)
        y = rng.randrange(size)
        tone = rng.choice((rgb('#4f5c35'), rgb('#3e4a2a'), rgb('#6b6a3e'), rgb('#7a7040')))
        for oy in range(rng.randint(1, 4)):
            for ox in range(rng.randint(1, 4)):
                if x + ox < size and y + oy < size and rng.random() < 0.82:
                    px[x + ox, y + oy] = (*tone, 255)
    return img


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


def dead_bush(size, rng):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    px = img.load()
    color = rgb('#6b5a3a')
    x = size // 2
    y = size - 2
    for _ in range(size * 2):
        if 0 <= x < size and 0 <= y < size:
            px[x, y] = (*jitter(color, 16, rng), 255)
        x += rng.choice((-1, 0, 1))
        y += rng.choice((-1, 0))
        if y < 2:
            break
    return img


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
    'oak_leaves': leaves,
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
    "pack": {
        "pack_format": 4,
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


def build_pack(target, size, description):
    rng = random.Random(0x4A0C + size)
    block_dir = os.path.join(target, 'assets', 'minecraft', 'textures', 'block')
    legacy_dir = os.path.join(target, 'assets', 'minecraft', 'textures', 'blocks')
    if os.path.isdir(target):
        shutil.rmtree(target)
    os.makedirs(block_dir, exist_ok=True)
    os.makedirs(legacy_dir, exist_ok=True)

    for name, fn in MODERN.items():
        img = fn(size, rng)
        save(os.path.join(block_dir, name + '.png'), img)
    for legacy, modern in LEGACY.items():
        shutil.copyfile(os.path.join(block_dir, modern + '.png'),
                        os.path.join(legacy_dir, legacy + '.png'))

    meta = json.loads(json.dumps(PACK_META))
    meta['pack']['description'] = description
    with open(os.path.join(target, 'pack.mcmeta'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write('\n')
    build_icon(os.path.join(target, 'pack.png'))
    print('built', target)


def main():
    build_pack(os.path.join(ROOT, 'apocalypse_16x'), 16,
               "§5Apocalypse Zombies §8· §7Scorched 16x\n§8Cracked stone, ash, rust and dead grass")
    build_pack(os.path.join(ROOT, 'apocalypse_32x'), 32,
               "§5Apocalypse Zombies §8· §7Scorched 32x\n§8Cracked stone, ash, rust and dead grass")


if __name__ == '__main__':
    main()
