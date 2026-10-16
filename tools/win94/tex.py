# -*- coding: utf-8 -*-
"""win94 贴图 —— 按 model.py 的 UV 货架逐面绘制 512² 贴图，并经 MCP 装进工程。

读 build/win94/uvmap.json（每个面的矩形 + 材质），逐面：
  1) 铺材质底色 × 面朝向明暗（上亮下暗）
  2) 按材质加纹理：胡桃木木纹 / 发蓝钢拉丝 / 抛光钢渐变 / 黄铜氧化 / 镜片反光
输出：
  src/main/resources/assets/apocalypse_zombies/textures/item/win94.png（交付资源）
  build/win94/tex_preview.png（2× 放大自查）

用法：
  python tools/win94/tex.py            # 画图 + 上传
  python tools/win94/tex.py --paint    # 只画图，不动 Blockbench
"""
import json
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'tools'))
import bbmcp  # noqa: E402
import spec as S  # noqa: E402

UVMAP = ROOT / 'build' / 'win94' / 'uvmap.json'
OUT_TEX = ROOT / 'src' / 'main' / 'resources' / 'assets' / 'apocalypse_zombies' / 'textures' / 'item' / 'win94.png'
OUT_PREV = ROOT / 'build' / 'win94' / 'tex_preview.png'
W = H = S.TEX_W

BASE = S.MAT
FACE_LIGHT = {'up': 1.18, 'down': 0.70, 'north': 0.95, 'south': 1.05,
              'east': 0.86, 'west': 1.10}


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


def draw_wood(d, box, base, rnd, span_u=None, span_v=None):
    """胡桃木：底色 + 沿枪身长度方向（模型 z / u 轴）延伸的年轮线。

    纹路位置一律按**模型绝对坐标**算（span_u = 沿 uv-u 轴的模型跨度、span_v = 沿 v 轴的），
    不用贴图像素、不用随机数 —— 枪托是 16 段、护木是 4 段拼的，逐段独立随机纹会在侧面上
    显出"栅栏"竖纹；按绝对坐标画，相邻段在接缝处的纹路严丝合缝。
    年轮线沿 u 方向（枪身长度）延伸，线的疏密沿 v 方向（高度）排列。
    """
    x1, y1, x2, y2 = box
    w, h = max(1, x2 - x1), max(1, y2 - y1)
    a0, a1 = (float(span_u[0]), float(span_u[1])) if span_u else (0.0, float(w))
    b0, b1 = (float(span_v[0]), float(span_v[1])) if span_v else (0.0, float(h))
    du = (a1 - a0) / w if w else 1.0
    dv = (b1 - b0) / h if h else 1.0

    # 1) 沿长度方向的宽色带（木料的深浅变化），每 0.9 u 一条，跨段连续、对比要弱
    for k in range(int(math.ceil(a0 / 0.9)), int(math.floor(a1 / 0.9)) + 1):
        px = x1 + int(round((k * 0.9 - a0) / du))
        if x1 <= px < x2:
            f = 0.975 + 0.045 * math.sin(k * 0.7)
            d.line([(px, y1), (px, y2 - 1)], fill=shade(base, f) + (255,))
    # 2) 年轮细线：沿 u 方向（枪身长度）延伸，位置由绝对 v 决定，浅到像丝
    step = 0.13                                    # ≈8 mm 一条（太密会糊成鳞片/砖墙）
    for k in range(int(math.ceil(b0 / step)), int(math.floor(b1 / step)) + 1):
        py = y1 + int(round((k * step - b0) / dv))
        if y1 <= py < y2:
            f = 0.935 + 0.065 * (0.5 + 0.5 * math.sin(k * 1.31))
            d.line([(x1, py), (x2 - 1, py)], fill=shade(base, f) + (255,))
    # 3) 少量孔隙，位置同样按绝对坐标（跨段连续）
    step_p = 0.47
    for k in range(int(math.ceil(a0 / step_p)), int(math.floor(a1 / step_p)) + 1):
        px = x1 + int(round((k * step_p - a0) / du))
        if not (x1 <= px < x2):
            continue
        q = int(math.ceil(b0 / 0.37)) + (k % 3)
        py = y1 + int(round((q * 0.37 - b0) / dv))
        if y1 <= py < y2:
            d.point((px, py), fill=shade(base, 0.78) + (255,))


def draw_blued(d, box, base, rnd, span_v=None):
    """发蓝钢：竖向微渐变 + 拉丝横线（横线按模型 y 坐标等间距，多段件之间对得上）。"""
    x1, y1, x2, y2 = box
    h = max(1, y2 - y1)
    for yy in range(y1, y2):
        t = (yy - y1) / max(1, h - 1)
        d.line([(x1, yy), (x2 - 1, yy)], fill=shade(base, 1.14 - 0.22 * t) + (255,))
    b0, b1 = (span_v or [0.0, float(h)])
    dv = (b1 - b0) / h if h else 1.0
    step = 0.34                                     # 拉丝别太密，否则枪管一段段像竹节
    for k in range(int(math.ceil(b0 / step)), int(math.floor(b1 / step)) + 1):
        u = k * step
        py = y1 + int(round((u - b0) / dv))
        if y1 <= py < y2:
            d.line([(x1, py), (x2 - 1, py)], fill=shade(base, 1.14) + (255,))


def draw_steel(d, box, base, rnd):
    """抛光钢：中心亮带。"""
    x1, y1, x2, y2 = box
    h = max(1, y2 - y1)
    for yy in range(y1, y2):
        t = abs((yy - y1) / h - 0.5) * 2.0
        d.line([(x1, yy), (x2 - 1, yy)], fill=shade(base, 1.30 - 0.45 * t) + (255,))


def draw_metal_colored(d, box, base, rnd, hi=1.22, lo=0.78):
    x1, y1, x2, y2 = box
    h = max(1, y2 - y1)
    for yy in range(y1, y2):
        t = (yy - y1) / h
        d.line([(x1, yy), (x2 - 1, yy)], fill=shade(base, hi - (hi - lo) * t) + (255,))


def draw_lens(d, box, base, rnd):
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    for yy in range(y1, y2):
        for xx in range(x1, x2):
            dx = (xx + 0.5 - cx) / max(1e-6, (x2 - x1) / 2)
            dy = (yy + 0.5 - cy) / max(1e-6, (y2 - y1) / 2)
            r = min(1.0, (dx * dx + dy * dy) ** 0.5)
            d.point((xx, yy), fill=shade(base, 1.45 - 0.75 * r) + (255,))


def paint():
    uvmap = json.loads(UVMAP.read_text(encoding='utf-8'))
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rnd = random.Random(94)
    n = 0
    for f in uvmap['faces']:
        u1, v1, u2, v2 = f['uv']
        if u2 <= u1 or v2 <= v1:
            continue
        base = BASE.get(f['mat'], BASE['blued'])
        col = shade(base, FACE_LIGHT.get(f['face'], 1.0))
        d.rectangle([u1, v1, u2 - 1, v2 - 1], fill=col + (255,))
        mat = f['mat']
        su, sv = f.get('span_u'), f.get('span_v')
        if mat.startswith('walnut'):
            draw_wood(d, (u1, v1, u2, v2), col, rnd, su, sv)
        elif mat == 'steel':
            draw_steel(d, (u1, v1, u2, v2), col, rnd)
        elif mat in ('brass', 'brass_dark', 'copper'):
            draw_metal_colored(d, (u1, v1, u2, v2), col, rnd, hi=1.20, lo=0.74)
        elif mat == 'lens':
            draw_lens(d, (u1, v1, u2, v2), col, rnd)
        elif mat == 'blued_dark':
            draw_metal_colored(d, (u1, v1, u2, v2), col, rnd, hi=1.05, lo=0.80)
        else:
            draw_blued(d, (u1, v1, u2, v2), col, rnd, sv)
        n += 1
    OUT_TEX.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT_TEX)
    img.resize((W * 2, H * 2), Image.NEAREST).save(OUT_PREV)
    print(f'faces painted = {n}')
    print('tex  ->', OUT_TEX.relative_to(ROOT), OUT_TEX.stat().st_size, 'bytes')
    print('prev ->', OUT_PREV.relative_to(ROOT))
    return 0


DROP_JS = """
const n = Texture.all.length;
Texture.all.slice().forEach((t) => t.remove());
return { removed: n, left: Texture.all.length };
"""

# import_texture 用文件名当贴图名（win94.png），改回工程约定的短名。
RENAME_JS = """
const t = Texture.all[Texture.all.length - 1];
if (!t) return { error: 'no texture' };
const old = t.name;
t.name = 'win94';
return { old, now: t.name, w: t.width, h: t.height };
"""


def upload():
    # 导入时用**带时间戳的副本**：Blockbench（Electron）会按文件路径缓存图像，
    # 同名同路径重导时画布还显示旧贴图（实测截图字节完全相同）。
    import shutil
    import time
    tmp = OUT_PREV.parent / f'tex_import_{int(time.time() * 1000)}.png'
    shutil.copyfile(OUT_TEX, tmp)
    steps = [
        ('drop old textures', 'execute_script', {'code': DROP_JS}),
        ('import', 'import_texture', {'path': str(tmp.resolve()), 'name': 'win94'}),
        ('rename', 'execute_script', {'code': RENAME_JS}),
        ('apply to all cubes', 'apply_texture', {'texture': 'win94'}),
        ('refresh preview', 'execute_script', {'code':
         "try { Texture.all.forEach((t) => { if (t.img) t.img.src = t.img.src; }); } catch (e) {}\n"
         "try { Canvas.updateAll(); } catch (e) {}\n"
         "try { Preview.selected.render(); } catch (e) {}\n"
         "return { textures: Texture.all.map((t) => t.name), cubes: Cube.all.length };"}),
        ('check_model', 'check_model', {}),
    ]
    for label, action, params in steps:
        r = bbmcp.call(action, params, timeout=300)
        if not r.get('ok'):
            print(f'[{label}] FAIL :: {json.dumps(r, ensure_ascii=False)[:600]}')
            return 1
        out = r.get('result')
        brief = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
        print(f'[{label}] OK :: {brief[:300]}')
    return 0


def main():
    rc = paint()
    if rc or '--paint' in sys.argv:
        return rc
    return upload()


if __name__ == '__main__':
    sys.exit(main())
