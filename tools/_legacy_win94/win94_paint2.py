# -*- coding: utf-8 -*-
"""win94 贴图 v2 —— UV 货架重排 + PIL 全量重喷(参考 PUBG 配色: 胡桃木/发蓝钢/抛光钢/黄铜)。
读 win94.bbmodel → 每方块6面按尺寸货架装箱到 512² → faces.uv 重写 → 逐面绘制 →
写回 textures[0].source(base64) 并另存预览 tools/win94_tex_v2.png。
"""
import json, os, math, base64, io, random
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BB = os.path.join(ROOT, 'win94.bbmodel')
PREVIEW = os.path.join(HERE, 'win94_tex_v2.png')
TEX = 512

# ---------- 材质基色 ----------
C = dict(
    walnut   =(110, 74, 42),  walnut_hi=(140, 100, 58), walnut_dk=(74, 48, 24),
    blued    =(46, 51, 58),   blued_hi =(86, 94, 104),  blued_dk =(24, 26, 30),
    steel    =(125, 132, 141),steel_hi =(184, 191, 200),steel_dk =(78, 84, 92),
    brass    =(176, 141, 87),  brass_hi =(214, 182, 128),brass_dk =(122, 92, 48),
    copper   =(156, 95, 51),   copper_hi=(201, 138, 90), copper_dk=(110, 62, 30),
    black    =(16, 18, 22),
    glass_c  =(184, 228, 242), glass_m  =(111, 168, 200),glass_e  =(46, 90, 116),
)

WOOD    = ('forearm_tip','forearm_mid','forearm_rear',
           'stock_wrist','stock_grip','stock_lowcomb','stock_shoulder',
           'stock_butt_upper','stock_butt_mid','stock_butt_lower','stock_toe')
CHECKER = ('forend_check_left','forend_check_right')
BRIGHT  = ('lever_pin','lever_arm','bolt_body_a','bolt_body_b','bolt_face',
           'extractor_claw','hammer_body','hammer_spur','carrier_plate','carrier_lifter',
           'trigger_blade','band_fore','mag_band_mid','mag_nose_cap','buttplate',
           'stock_latch','sling_swivel_front','sling_swivel_rear','side_plate_r',
           'side_plate_l','loading_gate','lever_pin_screw_r','lever_pin_screw_l',
           'big_screw_r','big_screw_l','small_screw_r1','small_screw_l1',
           'small_screw_r2','small_screw_l2','mount_front','mount_rear',
           'front_sight_base','front_sight_blade','receiver_front_ring',
           'receiver_tang_top','receiver_tang_bottom','scope_obj_rim','scope_eye_ring')
BLUED   = ('barrel_pipe_a','barrel_pipe_b','mag_tube_a','mag_tube_b',
           'receiver_top','receiver_left','receiver_right_a','receiver_right_b',
           'receiver_floor_front','receiver_floor_rear','receiver_front_bridge',
           'receiver_rear_block','scope_tube_a','scope_tube_b','scope_obj',
           'scope_eye','scope_turret_top','scope_turret_cap','scope_turret_side')
BLACK   = ('port_liner',)
BRASS   = ('cartridge_case_a','cartridge_case_b','cartridge_rim','shell_body_a',
           'shell_body_b','shell_rim')
COPPER  = ('cartridge_bullet_a','cartridge_bullet_b')

def base_color(name):
    if name in WOOD: return C['walnut']
    if name in CHECKER: return C['walnut_dk']
    if name in BRIGHT: return C['steel']
    if name in BLUED: return C['blued']
    if name in BLACK: return C['black']
    if name in BRASS: return C['brass']
    if name in COPPER: return C['copper']
    return C['steel']

FACE_LIGHT = {'up': 1.14, 'down': 0.80, 'north': 1.0, 'south': 0.96,
              'east': 0.90, 'west': 0.94}

def mul(c, k):
    return tuple(max(0, min(255, int(round(v * k)))) for v in c)

# ---------- UV 货架装箱 ----------
def pack(d, ppu):
    """返回 face->rect; 失败返回 None"""
    faces = []  # (cube, face, w_px, h_px)
    for e in d['elements']:
        f, t = e['from'], e['to']
        dims = [max(0.02, abs(t[i]-f[i])) for i in range(3)]
        sz = {  # 各面像素尺寸 (u,v)
            'north': (dims[0], dims[1]), 'south': (dims[0], dims[1]),
            'east':  (dims[2], dims[1]), 'west':  (dims[2], dims[1]),
            'up':    (dims[0], dims[2]), 'down':  (dims[0], dims[2]),
        }
        for k, (w, h) in sz.items():
            faces.append((e['name'], k,
                          max(2, int(round(w*ppu))), max(2, int(round(h*ppu)))))
    faces.sort(key=lambda x: -x[3])  # 按高降序
    shelf_y, shelf_h, x = 1, 0, 1
    rects = {}
    for name, k, w, h in faces:
        if x + w + 1 > TEX - 1:
            shelf_y += shelf_h + 1
            shelf_h, x = 0, 1
        if shelf_y + h + 1 > TEX - 1:
            return None
        rects[(name, k)] = (x, shelf_y, x+w, shelf_y+h)
        shelf_h = max(shelf_h, h)
        x += w + 1
    return rects

def main():
    d = json.load(open(BB, encoding='utf-8'))
    # 面积估算求 ppu
    area = 0.0
    for e in d['elements']:
        f, t = e['from'], e['to']
        w, h, dp = (abs(t[i]-f[i]) for i in range(3))
        area += 2*(w*h + w*dp + h*dp)
    ppu = 44
    rects = None
    while ppu >= 8:
        rects = pack(d, ppu)
        if rects: break
        ppu -= 1
    assert rects, '装箱失败'
    print('ppu=%d  faces=%d' % (ppu, len(rects)))

    # ---------- 贴图绘制 ----------
    img = Image.new('RGB', (TEX, TEX), mul(C['blued_dk'], 0.8))
    dr = ImageDraw.Draw(img)
    rng = random.Random(94)

    def px_noise(x0, y0, x1, y1, amp):
        for yy in range(y0, y1):
            for xx in range(x0, x1):
                n = rng.randint(-amp, amp)
                r, g, b = img.getpixel((xx, yy))
                img.putpixel((xx, yy), (max(0,min(255,r+n)), max(0,min(255,g+n)), max(0,min(255,b+n))))

    def streaks(x0, y0, x1, y1, col, along_u, n, amp=1):
        for i in range(n):
            if along_u:  # 水平纹(u向)
                yy = y0 + 1 + rng.randint(0, max(0, y1-y0-3))
                xx = x0 + rng.randint(0, 3)
                while xx < x1-1:
                    ln = rng.randint(3, 10)
                    dr.line([(xx, yy), (min(xx+ln, x1-1), yy)], fill=col)
                    yy = max(y0+1, min(y1-2, yy + rng.randint(-1, 1)))
                    xx += ln
            else:        # 垂直纹
                xx = x0 + 1 + rng.randint(0, max(0, x1-x0-3))
                yy = y0 + rng.randint(0, 3)
                while yy < y1-1:
                    ln = rng.randint(3, 10)
                    dr.line([(xx, yy), (xx, min(yy+ln, y1-1))], fill=col)
                    xx = max(x0+1, min(x1-2, xx + rng.randint(-1, 1)))
                    yy += ln

    for e in d['elements']:
        name = e['name']
        f, t = e['from'], e['to']
        w, h, dp = (abs(t[i]-f[i]) for i in range(3))
        base = base_color(name)
        for k in ('north','south','east','west','up','down'):
            x0, y0, x1, y1 = rects[(name, k)]
            dr.rectangle([x0, y0, x1-1, y1-1], fill=mul(base, FACE_LIGHT[k]))
            fw, fh = x1-x0, y1-y0

            # --- 通用质感 ---
            if name in WOOD:
                streaks(x0, y0, x1, y1, mul(C['walnut_dk'], 1.05), k in ('east','west'), max(2, fh//4))
                if rng.random() < 0.7:
                    streaks(x0, y0, x1, y1, mul(C['walnut_hi'], 1.0), k in ('east','west'), max(1, fh//7))
            elif name in CHECKER and k in ('east','west'):
                for ddx in range(-fh, fw, 3):
                    dr.line([(x0+ddx, y0), (x0+ddx+fh, y1-1)], fill=mul(C['walnut'], 0.7))
                    dr.line([(x0+ddx, y1-1), (x0+ddx+fh, y0)], fill=mul(C['walnut'], 0.75))
            elif name in BLUED:
                if k in ('up','east','west'):
                    streaks(x0, y0, x1, y1, mul(C['blued_hi'], 0.9), k == 'up' and 0 or 1, max(1, fh//6))
            elif name in BRIGHT and k in ('up','east','west'):
                streaks(x0, y0, x1, y1, mul(C['steel_hi'], 0.95), k == 'up' and 0 or 1, max(1, fh//7))
            elif name in BRASS:
                streaks(x0, y0, x1, y1, mul(C['brass_dk'], 1.0), 1, max(1, fh//5))
                if name.startswith('shell'):  # 弹壳烟熏
                    for _ in range(3):
                        sx = x0 + rng.randint(0, max(0, fw-3)); sy = y0 + rng.randint(0, max(0, fh-3))
                        dr.rectangle([sx, sy, sx+2, sy+2], fill=mul(C['brass_dk'], 0.55))
            elif name in COPPER:
                streaks(x0, y0, x1, y1, mul(C['copper_dk'], 1.0), 1, max(1, fh//5))

            # --- 特写细节 ---
            if name == 'muzzle_crown' and k == 'north':
                cx, cy = (x0+x1)//2, (y0+y1)//2
                r = int(min(fw, fh)*0.42)
                dr.ellipse([cx-r, cy-r, cx+r, cy+r], fill=C['black'])
                dr.ellipse([cx-r, cy-r, cx+r, cy+r], outline=mul(C['steel'], 0.9))
            if name == 'scope_eye' and k == 'south':   # 目镜玻璃
                cx, cy = (x0+x1)//2, (y0+y1)//2
                r = int(min(fw, fh)*0.45)
                dr.ellipse([cx-r, cy-r, cx+r, cy+r], fill=C['glass_m'])
                dr.ellipse([cx-r//2, cy-r//2, cx+r//2, cy+r//2], fill=C['glass_c'])
                dr.ellipse([cx-r, cy-r, cx+r, cy+r], outline=C['glass_e'])
                dr.rectangle([cx-r//3, cy-r//3, cx-r//3+1, cy-r//3+1], fill=(255,255,255))
            if name == 'scope_obj' and k == 'north':   # 物镜玻璃
                cx, cy = (x0+x1)//2, (y0+y1)//2
                r = int(min(fw, fh)*0.45)
                dr.ellipse([cx-r, cy-r, cx+r, cy+r], fill=C['glass_e'])
                dr.ellipse([cx-r//2, cy-r//2, cx+r//2, cy+r//2], fill=C['glass_m'])
                dr.ellipse([cx-r, cy-r, cx+r, cy+r], outline=mul(C['steel'], 0.85))
            if name == 'side_plate_r' and k == 'east' or name == 'side_plate_l' and k == 'west':
                cx, cy = (x0+x1)//2, (y0+y1)//2
                r = int(min(fw, fh)*0.46)
                dr.ellipse([cx-r, cy-r, cx+r, cy+r], fill=mul(C['steel'], 1.06))
                dr.ellipse([cx-r, cy-r, cx+r, cy+r], outline=C['steel_dk'])
                rr = int(r*0.55)
                dr.ellipse([cx-rr, cy-rr, cx+rr, cy+rr], outline=mul(C['steel_dk'], 0.9))
                dr.line([(cx-r//2, cy-r//3), (cx+r//2, cy+r//3)], fill=C['steel_dk'], width=2)
            if name == 'loading_gate' and k == 'east':  # 装弹门圆盘
                cx, cy = (x0+x1)//2, (y0+y1)//2
                r = int(min(fw, fh)*0.46)
                dr.ellipse([cx-r, cy-r, cx+r, cy+r], fill=mul(C['steel'], 0.95))
                dr.ellipse([cx-r, cy-r, cx+r, cy+r], outline=C['steel_dk'])
                dr.line([(cx, cy-r//2), (cx, cy+r//2)], fill=C['steel_dk'], width=2)
            if name.startswith('port_liner'):
                pass  # 保持近黑
            if name.startswith('small_screw') and k in ('east','west'):
                cx, cy = (x0+x1)//2, (y0+y1)//2
                r = max(2, int(min(fw, fh)*0.4))
                dr.ellipse([cx-r, cy-r, cx+r, cy+r], outline=C['steel_dk'])
                dr.line([(cx-r+1, cy), (cx+r-1, cy)], fill=C['steel_dk'])
            if name.startswith('big_screw') and k in ('east','west'):
                cx, cy = (x0+x1)//2, (y0+y1)//2
                r = max(3, int(min(fw, fh)*0.42))
                dr.ellipse([cx-r, cy-r, cx+r, cy+r], outline=C['steel_dk'])
                dr.line([(cx-r+1, cy-1), (cx+r-1, cy+1)], fill=C['steel_dk'], width=2)

    # 低幅噪点(全图统一颗粒)
    px_noise(0, 0, TEX, TEX, 5)

    # ---------- 写回 ----------
    eidx = {e['name']: e for e in d['elements']}
    for (name, k), r in rects.items():
        eidx[name]['faces'][k]['uv'] = [r[0], r[1], r[2], r[3]]

    buf = io.BytesIO()
    img.save(buf, 'PNG')
    b64 = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
    d['textures'][0]['source'] = b64
    json.dump(d, open(BB, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    img.save(PREVIEW)
    print('saved', BB, os.path.getsize(BB))
    print('preview', PREVIEW)

if __name__ == '__main__':
    main()
