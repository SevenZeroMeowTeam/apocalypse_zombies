# -*- coding: utf-8 -*-
"""铜装备贴图：把原版铁质装备贴图做「铁 → 铜」的色调映射。

为什么拿铁做底：铜这一档的定位是「比石强、比铁弱」，要的是**金属感**；皮革底图是布/皮质感，
套上铜色也不像铜器。映射只换色相、保留明暗 —— 铁的高光仍是高光、暗部仍是暗部，整体从灰变铜。

产出 9 张（原版源 → 模组目标）：

    textures/item/iron_sword.png        → textures/item/copper_sword.png
    textures/item/iron_pickaxe.png      → textures/item/copper_pickaxe.png
    textures/item/iron_hoe.png          → textures/item/copper_hoe.png
    textures/item/iron_helmet.png       → textures/item/copper_helmet.png
    textures/item/iron_chestplate.png   → textures/item/copper_chestplate.png
    textures/item/iron_leggings.png     → textures/item/copper_leggings.png
    textures/item/iron_boots.png        → textures/item/copper_boots.png
    textures/models/armor/iron_layer_1.png → textures/models/armor/copper_layer_1.png
    textures/models/armor/iron_layer_2.png → textures/models/armor/copper_layer_2.png

最后两张是**穿在身上**的图层，文件名必须与 `ModArmorMaterials.getName()` 对得上
（`apocalypse_zombies:copper` ⇒ `copper_layer_1.png` / `copper_layer_2.png`）。

跑法：python tools/copper_gear_art.py
"""

import os
import struct
import zipfile
import zlib

CLIENT_JAR = ('C:/Users/Administrator/.gradle/caches/forge_gradle/'
              'minecraft_repo/versions/1.20.1/client.jar')
ART = 'F:/mcmod/art/copper'
RES = 'F:/mcmod/src/main/resources/assets/apocalypse_zombies'

# 铁贴图的主色 → 铜。乘法映射：逐通道按 目标/基准 缩放，明暗关系原样保留。
IRON = (0xD8, 0xD8, 0xD8)
COPPER = (0xC8, 0x71, 0x37)

PAIRS = [
    ('textures/item/iron_sword.png', 'textures/item/copper_sword.png'),
    ('textures/item/iron_pickaxe.png', 'textures/item/copper_pickaxe.png'),
    ('textures/item/iron_hoe.png', 'textures/item/copper_hoe.png'),
    ('textures/item/iron_helmet.png', 'textures/item/copper_helmet.png'),
    ('textures/item/iron_chestplate.png', 'textures/item/copper_chestplate.png'),
    ('textures/item/iron_leggings.png', 'textures/item/copper_leggings.png'),
    ('textures/item/iron_boots.png', 'textures/item/copper_boots.png'),
    ('textures/models/armor/iron_layer_1.png', 'textures/models/armor/copper_layer_1.png'),
    ('textures/models/armor/iron_layer_2.png', 'textures/models/armor/copper_layer_2.png'),
]


def read_png(data):
    """解 PNG → (w, h, bytearray RGBA)。支持 8 位 灰度/RGB/调色板/RGBA，非隔行。"""
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('不是 PNG')
    pos = 8
    idat = b''
    w = h = depth = ctype = None
    plte = trns = None
    while pos < len(data):
        ln = struct.unpack('>I', data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if typ == b'IHDR':
            w, h, depth, ctype, _comp, _filt, inter = struct.unpack('>IIBBBBB', body)
            if depth != 8:
                raise ValueError('只支持 8 位色深（实得 %d）' % depth)
            if inter != 0:
                raise ValueError('不支持隔行 PNG')
        elif typ == b'PLTE':
            plte = body
        elif typ == b'tRNS':
            trns = body
        elif typ == b'IDAT':
            idat += body
        elif typ == b'IEND':
            break
    raw = zlib.decompress(idat)
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    stride = w * channels
    out = bytearray(w * h * 4)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if f == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif f == 3:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif f == 4:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                pp = a + b - c
                pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 0xFF
        for x in range(w):
            o = (y * w + x) * 4
            if ctype == 6:
                out[o:o + 4] = line[x * 4:x * 4 + 4]
            elif ctype == 2:
                out[o:o + 3] = line[x * 3:x * 3 + 3]
                out[o + 3] = 255
            elif ctype == 3:
                idx = line[x]
                out[o:o + 3] = plte[idx * 3:idx * 3 + 3]
                out[o + 3] = trns[idx] if (trns and idx < len(trns)) else 255
            elif ctype == 0:
                g = line[x]
                out[o:o + 4] = bytes((g, g, g, 255))
            elif ctype == 4:
                g, a = line[x * 2], line[x * 2 + 1]
                out[o:o + 4] = bytes((g, g, g, a))
        prev = line
    return w, h, out


def write_png(path, w, h, rgba):
    """写 8 位 RGBA PNG（filter 0）。"""
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += rgba[y * w * 4:(y + 1) * w * 4]

    def chunk(typ, body):
        return (struct.pack('>I', len(body)) + typ + body
                + struct.pack('>I', zlib.crc32(typ + body) & 0xFFFFFFFF))

    blob = (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(bytes(raw), 9))
            + chunk(b'IEND', b''))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(blob)


def copperize(rgba):
    """铁 → 铜：逐通道按 COPPER/IRON 缩放，明暗保留；全透明像素不动。"""
    out = bytearray(rgba)
    for i in range(0, len(rgba), 4):
        if rgba[i + 3] == 0:
            continue
        for c in range(3):
            out[i + c] = min(255, rgba[i + c] * COPPER[c] // IRON[c])
    return out


def main():
    z = zipfile.ZipFile(CLIENT_JAR)
    print('== 铜装备贴图（铁 → 铜色调映射）==')
    for src, dst in PAIRS:
        w, h, rgba = read_png(z.read('assets/minecraft/' + src))
        cu = copperize(rgba)
        write_png(os.path.join(RES, dst), w, h, cu)
        write_png(os.path.join(ART, os.path.basename(dst)), w, h, cu)
        opaque = sum(1 for i in range(3, len(cu), 4) if cu[i] > 0)
        print('  %-34s %2dx%-3d → %-34s 不透明像素 %d'
              % (src.split('/')[-1], w, h, dst.split('/')[-1], opaque))
    print('共 %d 张（含穿在身上的 _layer_1/_layer_2）' % len(PAIRS))


if __name__ == '__main__':
    main()
