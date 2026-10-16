# -*- coding: utf-8 -*-
"""win94 贴图离线重喷：按元素名映射色板，逐面 UV 填色 + 方向渐变 + 木纹/防滑纹。"""
import json, base64, io, os, random
import numpy as np
from PIL import Image

SRC = os.path.join(os.path.dirname(__file__), '..', 'win94.bbmodel')
d = json.load(open(SRC, encoding='utf-8'))

# ---- 色板 ----
BLUED      = (66, 70, 78)     # 发蓝钢
BLUED_DARK = (46, 50, 58)     # 暗发蓝
BLACK      = (30, 30, 32)     # 黑件
POLISHED   = (148, 150, 157)  # 抛光钢
WALNUT     = (132, 84, 44)    # 胡桃木
BIRCH      = (208, 152, 86)   # 蜜色桦木
BRASS      = (206, 162, 82)   # 黄铜
BRASS_DARK = (170, 130, 62)   # 旧黄铜（抛出壳）
COPPER     = (196, 126, 72)   # 铜被甲
LENS       = (86, 104, 120)   # 镜片
BORE       = (14, 14, 16)     # 膛孔黑

def mat_of(name):
    n = name
    if n.startswith(('stock_butt', 'stock_mid', 'stock_neck')): return WALNUT, 'wood'
    if n.startswith(('forearm_body', 'forearm_tip', 'forearm_swell', 'forearm_nose')): return WALNUT, 'wood'
    if n.startswith('forearm_check'): return (118, 72, 38), 'check'
    if n.startswith(('buttplate', 'stock_latch')): return BLACK, 'metal'
    if n.startswith('sling_swivel'): return BLACK, 'metal'
    if n.startswith(('barrel_pipe', 'mag_tube')): return BLUED, 'metal'
    if n.startswith(('muzzle_crown',)): return BLUED_DARK, 'metal'
    if n.startswith(('mag_cap',)): return BLUED_DARK, 'metal'
    if n.startswith('mag_cap_screw'): return POLISHED, 'metal'
    if n.startswith(('band_muzzle', 'band_fore')): return BLUED_DARK, 'metal'
    if n.startswith(('front_sight',)): return BLUED_DARK, 'metal'
    if n.startswith(('receiver_tang',)): return BLUED_DARK, 'metal'
    if n.startswith('receiver_'): return BLUED, 'metal'
    if n.startswith('loading_gate'): return BLUED_DARK, 'metal'
    if n.startswith(('lever_pin_screw', 'big_side_screw', 'small_screw')): return POLISHED, 'metal'
    if n.startswith('ejector_ramp'): return POLISHED, 'metal'
    if n.startswith(('bolt_body', 'bolt_face', 'bolt_shroud', 'extractor')): return POLISHED, 'metal'
    if n.startswith('hammer_'): return BLUED_DARK, 'metal'
    if n.startswith(('lever_loop', 'lever_arm', 'lever_pin')): return BLUED, 'metal'
    if n.startswith('carrier_plate'): return BLUED_DARK, 'metal'
    if n.startswith('carrier_lifter'): return POLISHED, 'metal'
    if n.startswith('cartridge_case'): return BRASS, 'metal'
    if n.startswith('cartridge_rim'): return BRASS, 'metal'
    if n.startswith('cartridge_bullet'): return COPPER, 'metal'
    if n.startswith('shell_'): return BRASS_DARK, 'metal'
    if n.startswith('trigger'): return BLUED_DARK, 'metal'
    if n.startswith(('scope_tube', 'scope_eye', 'scope_turret')): return BLACK, 'metal'
    if n.startswith(('scope_obj_rim', 'scope_eye_ring')): return BLACK, 'metal'
    if n.startswith('scope_obj'): return BLACK, 'metal'
    if n.startswith(('mount_ring', 'mount_base')): return BLACK, 'metal'
    return BLUED, 'metal'

# 特殊面：膛口/镜片
SPECIAL_FACE = {
    ('muzzle_crown_a', 'north'): (BORE, 'flat'),
    ('scope_obj_a', 'north'): (LENS, 'lens'),
}

W, H = 512, 512
rng = random.Random(94)
noise = (np.random.default_rng(94).random((H, W, 1)) * 2 - 1) * 3.0  # ±3

img = np.zeros((H, W, 3), dtype=np.float64)

FACE_SHADE = {'up': 1.12, 'down': 0.75, 'north': 0.92, 'south': 1.0, 'east': 1.0, 'west': 0.88}

for e in d['elements']:
    base, style = mat_of(e['name'])
    for fn, f in e['faces'].items():
        uv = f.get('uv')
        if not uv: continue
        u0, v0, u1, v1 = [int(round(x)) for x in uv]
        u0, u1 = max(0, min(u0, u1)), max(0, max(u0, u1))
        v0, v1 = max(0, min(v0, v1)), max(0, max(v0, v1))
        if u1 <= u0 or v1 <= v0: continue
        key = (e['name'], fn)
        if key in SPECIAL_FACE:
            color, kind = SPECIAL_FACE[key]
            reg = np.zeros((v1 - v0, u1 - u0, 3))
            reg[:, :] = color
            if kind == 'lens':
                hh, ww = reg.shape[:2]
                yy, xx = np.mgrid[0:hh, 0:ww]
                cy, cx = hh / 2, ww / 2
                r = np.sqrt(((yy - cy) / max(cy, 1)) ** 2 + ((xx - cx) / max(cx, 1)) ** 2)
                glint = np.clip(1.25 - r, 0, 1)[..., None] * 55
                reg = reg * (0.75 + 0.5 * np.clip(1 - r, 0, 1)[..., None]) + glint
            img[v0:v1, u0:u1] = np.clip(reg, 0, 255)
            continue
        shade = FACE_SHADE.get(fn, 1.0)
        reg = np.zeros((v1 - v0, u1 - u0, 3))
        reg[:, :] = base
        hh, ww = reg.shape[:2]
        if fn not in ('up', 'down'):
            grad = np.linspace(1.06, 0.93, hh)[:, None]  # 上亮下暗
            reg = reg * grad[..., None]
        reg = reg * shade
        if style == 'wood':
            # 木纹：沿长轴的暗色条纹
            axis = 0 if hh >= ww else 1
            n_streak = max(2, (hh if axis == 0 else ww) // 5)
            for _ in range(n_streak):
                p = rng.randrange(hh if axis == 0 else ww)
                m = 0.88 + rng.random() * 0.08
                if axis == 0: reg[p:min(p + 2, hh), :] *= m
                else: reg[:, p:min(p + 2, ww)] *= m
        elif style == 'check':
            # 防滑格纹：2px 交替
            for p in range(0, hh, 2):
                reg[p::2, :] *= 0.80
            for p in range(0, ww, 2):
                reg[:, p::2] *= 0.88
        else:
            # 金属：细抛光横线（低幅度）
            if style == 'metal' and base == POLISHED:
                for p in range(0, hh, 3):
                    reg[p::3, :] *= 1.04
        reg = reg + noise[v0:v1, u0:u1]
        img[v0:v1, u0:u1] = np.clip(reg, 0, 255)

out = Image.fromarray(img.astype(np.uint8), 'RGB')
buf = io.BytesIO()
out.save(buf, 'PNG')
data = base64.b64encode(buf.getvalue()).decode()
d['textures'][0]['source'] = 'data:image/png;base64,' + data
json.dump(d, open(SRC, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('texture repainted, dataurl len', len(data), 'file', os.path.getsize(SRC))
