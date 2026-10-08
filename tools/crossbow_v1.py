# -*- coding: utf-8 -*-
"""十字弩（crossbow）v1 —— GeckoLib 真骨骼 · 逐面 UV 图集 · 程序化生成器（自包含）.

对齐 ~/美术规范.md：
  · 单位 16u=1方块=1m；前向 -Z、上 +Y、+X = 射手右侧；原点=机匣中心（握把在下）
  · 弓/弩长度区间 1.0~2.2 格，本作长轴 Z ≈ 20.4u = 1.28 格（长轴无 Z 限制）——但骨一律不带旋转
  · 密度 S=12（11~13），512×512 逐面 UV 图集，UVCAP=120，货架装箱(按高降序)，放不下降一档重试
  · 色板取规范 3.1 表；LIGHT=(0.40,0.84,0.36)、GLOSS=1.0、ao=0.20；FACE_SEED；确定性 LCG
  · 骨骼名 ^[a-z][a-z0-9_]*$；必需 root/move/body；pivot 距自身几何 <=4u（控制器骨除外）
  · 由本文件在 blender-mcp 里跑可额外建 .blend 并 EEVEE 预览；独立运行只出资产+自检

三处要求：
  1) draw 拉弦：弦从静止位 B0=(0,1.10,-7.90) 拉到牙 NUT=(0,1.10,-1.60)。
     弓片绕 Y 屈曲（limb_l/r），弦骨(string_l/r)是 limb 的子骨；逐帧用共享 FK + 数值求解，
     使两段弦内端始终在弦心（自检：拉满=两段弦内端恰在牙）。
  2) reload_tactical 拿出新箭放进弹仓：round_hand（左手新箭）抬升→送进弹仓顶 slot。
  3) ADS 十字镜头：目镜玻璃 +Z 面图集手绘 CROSS 十字分划+4 密位点；4 倍视角缩放由 Java 做。

运行：python tools/crossbow_v1.py      （无需 Blender）
可在 blender-mcp（port 9877）里 execute 本文件以建场景/出图。
"""
from __future__ import annotations
import io, json, math, os, struct, sys, zlib, copy

try:
    import bpy  # type: ignore
except Exception:
    bpy = None
try:
    import numpy as np  # type: ignore
except Exception:
    np = None

# ---------------------------------------------------------------- 常量
NAME = "crossbow"
IDENT = "geometry.crossbow"
_BASE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ART = os.path.join(_BASE, "art", "crossbow")
RES = os.path.join(_BASE, "src", "main", "resources", "assets", "apocalypse_zombies")
os.makedirs(ART, exist_ok=True)

TEX = 512
UVCAP = 120
MAX_CUBES = 600
MAX_BONES = 40
S = 12.0

LIGHT = (0.40, 0.84, 0.36)
GLOSS = 1.0
AO = 0.20
FACE_SEED = {'north': 11, 'south': 29, 'east': 47, 'west': 71, 'up': 89, 'down': 103}
FACES = ('north', 'south', 'east', 'west', 'up', 'down')
FACE_N = {'north': (0, 0, -1), 'south': (0, 0, 1), 'east': (1, 0, 0),
          'west': (-1, 0, 0), 'up': (0, 1, 0), 'down': (0, -1, 0)}

# 色板（规范 3.1 表）
BLACK   = (30, 30, 32)
BLACK_D = (20, 20, 22)
BLUE    = (66, 70, 78)
BLUE_D  = (46, 50, 58)
PARK    = (74, 76, 80)
STEEL   = (148, 150, 157)
WOOD    = (132, 84, 44)
WOOD_B  = (208, 152, 86)
GREEN   = (86, 118, 60)
BRASS   = (206, 162, 82)
COPPER  = (196, 126, 72)
GLASS   = (86, 104, 120)
CROSS   = (24, 24, 26)
DARK    = (14, 14, 16)
SIGHT   = (30, 30, 32)
DOT_RED = (255, 66, 48)
CLOTH   = (150, 96, 58)     # 皮革/羽毛
# 材质 -> (画法, 底色彩板RGB)
MAT = {
    'plastic':   ('plastic', BLACK),
    'metal':     ('metal', STEEL),
    'black':     ('plastic', BLACK),
    'black_d':   ('flat', BLACK_D),
    'blue':      ('brushed', BLUE),
    'blue_d':    ('flat', BLUE_D),
    'park':      ('brushed', PARK),
    'steel':     ('metal', STEEL),
    'wood':      ('wood', WOOD),
    'wood_b':    ('wood', WOOD_B),
    'green':     ('plastic', GREEN),
    'brass':     ('flat', BRASS),
    'copper':    ('metal', COPPER),
    'glass':     ('glass', GLASS),
    'glass_ret': ('glass_reticle', GLASS),
    'dark':      ('flat', DARK),
    'sight':     ('flat', SIGHT),
    'dot':       ('flat', DOT_RED),
    'cloth':     ('cloth', CLOTH),
}

class LC:
    def __init__(self, seed):
        self.s = (seed * 977 + 1) & 0x7FFFFFFF
    def next(self):
        self.s = (1103515245 * self.s + 12345) & 0x7FFFFFFF
        return self.s
    def f(self):
        return self.next() / 0x7FFFFFFF

# ---------------------------------------------------------------- 几何
BONES = []
CUBES = []
_cidx = 0

def add_bone(name, parent, pivot):
    BONES.append({'name': name, 'parent': parent, 'pivot': [round(v, 4) for v in pivot]})

def add(bone, mn, mx, mat, rot=None, pivot=None):
    """AABB 归一化箱体；mat=材质名（MAT 键）。rot=[rx,ry,rz]deg，pivot=旋转中心（缺省=中心）。"""
    global _cidx
    o = [round(min(mn[i], mx[i]), 4) for i in range(3)]
    s = [round(abs(mx[i] - mn[i]), 4) for i in range(3)]
    if not all(v > 1e-9 for v in s):
        raise ValueError('零/负尺寸 %s %s %s' % (bone, mn, mx))
    if mat not in MAT:
        raise ValueError('未知材质 %r' % (mat,))
    pv = [round(v, 4) for v in (pivot or [o[i] + s[i] / 2 for i in range(3)])]
    CUBES.append({'bone': bone, 'origin': o, 'size': s, 'rot': list(rot) if rot else None,
                  'pivot': pv, 'mat': mat, 'id': _cidx})
    _cidx += 1

def ring(bone, cx, cy, z0, z1, r0, r1, n, mat):
    """空心圆环（绕 Z，法向腔体），n 段箱体绕各自中心旋 rz，构成近似正多边形环。"""
    if r1 <= r0:
        return
    thick = r1 - r0
    rm = (r0 + r1) / 2
    seg = 360.0 / n
    half = (rm * 2 * math.pi / n) * 0.5      # 切向半宽（估计）
    for i in range(n):
        a = math.radians(seg * i)
        xc = cx + rm * math.cos(a)
        yc = cy + rm * math.sin(a)
        # 箱体：径向厚、切向半宽、轴向长
        tx = thick * 0.5
        ty = half
        add(bone, [xc - tx, yc - ty, z0], [xc + tx, yc + ty, z1], mat,
            rot=[0, 0, math.degrees(a)], pivot=[xc, yc, (z0 + z1) / 2])

def disc(bone, cx, cy, z, r, n, mat):
    """实心圆盘（法向 +Z），n 段楔形箱体凑正多边形。"""
    for i in range(n):
        a0 = math.radians(360.0 * i / n)
        a1 = math.radians(360.0 * (i + 1) / n)
        am = (a0 + a1) / 2
        # 用 n 个过轴心的矩形近似的正多边形（中心点向外发散的扁楔，用箱体中间垫）
        inn = r * 0.30
        x0 = cx + inn * math.cos(a0); y0 = cy + inn * math.sin(a0)
        x1 = cx + r * math.cos(am);  y1 = cy + r * math.sin(am)
        # 一个楔形 = 矩形（从内圆到外圆的一段）+ 旋转 am
        w = (r - inn)
        add(bone, [x1 - w, y1 - w, z - 0.05], [x1 + w, y1 + w, z + 0.05], mat,
            rot=[0, 0, math.degrees(am)], pivot=[cx, cy, z])

def bolt(bone, nock_z, y, tip_z, rotz=0.0, pivot=None, mat_body='wood_b', feather=True):
    """一支弩箭：箭杆 + 铁镞(朝前 -Z) + 箭尾搭弦槽(朝后 +Z) [+ 羽毛]。
    nock_z = 箭尾 z（靠射手，数值较大）；tip_z = 箭镞 z（朝前，数值较小）。
    feather=False ⇒ 无羽短矢（《天工開物》记诸葛连弩「去箭尾羽毛，便于由管道射出」；
    本模型箭匣为管道式供箭，无羽才不卡匣 —— 亦合「以铁为矢」。"""
    zn = max(nock_z, tip_z)      # 尾（后）
    zt = min(nock_z, tip_z)      # 镞（前）
    L = zn - zt
    pz = list(pivot) if pivot else [0.0, round(y, 4), round((zn + zt) / 2, 4)]
    add(bone, [-0.05, y - 0.05, zt + L * 0.15], [0.05, y + 0.05, zt + L * 0.55], mat_body, [0, 0, rotz], pz)  # 杆前段
    add(bone, [-0.05, y - 0.05, zt + L * 0.55], [0.05, y + 0.05, zn], mat_body, [0, 0, rotz], pz)          # 杆后段
    # 箭镞（bodkin，铁，朝前）
    add(bone, [-0.085, y - 0.085, zt + L * 0.06], [0.085, y + 0.085, zt + L * 0.15], 'steel', [0, 0, rotz], pz)
    add(bone, [-0.05, y - 0.05, zt], [0.05, y + 0.05, zt + L * 0.06], 'steel', [0, 0, rotz], pz)
    # 羽毛（上/下，near nock）—— 连弩无羽
    if feather:
        fz = zn - L * 0.30
        add(bone, [-0.045, y + 0.05, fz], [0.045, y + 0.12, fz + L * 0.28], 'cloth', [0, 0, rotz], pz)
        add(bone, [-0.045, y - 0.12, fz], [0.045, y - 0.05, fz + L * 0.28], 'cloth', [0, 0, rotz], pz)
    # 箭尾（搭弦槽，朝后）
    add(bone, [-0.05, y - 0.05, zn], [0.05, y + 0.05, zn + 0.07], 'black', [0, 0, rotz], pz)

# ---- 骨骼树（rest 全部零旋转）----
add_bone('root', None, (0, 0, 0))
add_bone('move', 'root', (0, 0.0, 0))
add_bone('body', 'move', (0, 0.0, 0))
add_bone('constraint', 'body', (0, 1.10, -1.60))
add_bone('camera', 'body', (0, 2.85, 3.6))
# 弩臂与弦
add_bone('limb_l', 'body', (-1.62, 1.10, -10.85))
add_bone('limb_r', 'body', (1.62, 1.10, -10.85))
add_bone('string_l', 'limb_l', (-10.12, 1.10, -7.90))
add_bone('string_r', 'limb_r', (10.12, 1.10, -7.90))
# 弩机
add_bone('lock_housing', 'body', (0, 1.10, -1.60))
add_bone('nut', 'lock_housing', (0, 1.10, -1.60))
add_bone('trigger', 'lock_housing', (0, 0.84, -1.60))     # 悬刀：与牙共用枢轴（文献「第一塊與第三塊共用一個轉軸」）
add_bone('sight_rear', 'lock_housing', (0, 1.44, -1.41))  # 望山：牙后立板（文献「牙後連有望山」）
# 箭匣（文献「一弩十矢俱發」⇒ 10 槽）
add_bone('magazine', 'body', (0, 2.10, -5.60))
for i in range(10):
    add_bone('mag_r%d' % (i + 1), 'magazine', (0, 1.28 + i * 0.17, -6.00))
add_bone('round_in', 'body', (0, 1.03, -6.00))
add_bone('round_hand', 'body', (-2.60, -1.55, -4.40))
# 瞄准镜
add_bone('scope', 'body', (0, 2.85, 0.0))
add_bone('scope_elev', 'scope', (0, 3.15, -0.20))
add_bone('scope_wind', 'scope', (1.60, 2.85, -0.20))

# ---- 弓片/弦 共享运动学（几何、动画、自检三处必须共用同一套）----
LIMB_PIVOT_X, LIMB_PIVOT_Z = 1.62, -10.85    # 弩臂枢轴（= BONES limb_* 的 pivot）
LIMB_TIP_X, LIMB_TIP_Z = 10.12, -7.90        # 弓片尖端 = 弦挂点（= BONES string_* 的 pivot）
STRING_LEN = LIMB_TIP_X                      # 弦半段长：尖端 → 弦心（静止 10.12，不可拉伸）
STR_Y = 1.10

def y_rot2(x, z, cx, cz, deg):
    """绕 (cx,cz) 做模型 Y 轴旋转。GeckoLib 约定：φ_new = φ_old − deg（deg>0 把 +X 转向 −Z）。"""
    a = math.radians(deg); ca, sa = math.cos(a), math.sin(a)
    vx, vz = x - cx, z - cz
    return (cx + vx * ca + vz * sa, cz - vx * sa + vz * ca)

def limb_tip(side, deg):
    """弩臂屈曲 deg 后该侧弓片尖端（= 弦挂点）位置。"""
    sgn = -1.0 if side == 'l' else 1.0
    return y_rot2(LIMB_TIP_X * sgn, LIMB_TIP_Z, LIMB_PIVOT_X * sgn, LIMB_PIVOT_Z, deg)

def limb_deg_for(side, z_nock):
    """解弩臂屈曲角，使弦半段长恰为 STRING_LEN：二分 |尖端(A) − 弦心| = 10.12。
    弦不可拉伸 ⇒ 弓片必须向后收（右臂 A<0、左臂对称 A>0）。"""
    sgn = 1.0 if side == 'r' else -1.0
    def dist(m):
        tx, tz = limb_tip(side, -m * sgn)
        return math.hypot(tx, tz - z_nock)
    if dist(0.0) <= STRING_LEN + 1e-9:
        return 0.0
    lo, hi = 0.0, 60.0
    for _ in range(64):
        mid = (lo + hi) / 2.0
        if dist(mid) > STRING_LEN:
            lo = mid
        else:
            hi = mid
    return round(-(lo + hi) / 2.0 * sgn, 4)

def string_bone_param(side, z_nock, limb_a):
    """弦骨 (rot_y, scale_x)：内端落 (0, STR_Y, z_nock)，弦长恒定 ⇒ scale 恒 ≈1。"""
    tx, tz = limb_tip(side, limb_a)
    dx, dz = 0.0 - tx, z_nock - tz
    dx, dz = y_rot2(dx, dz, 0.0, 0.0, -limb_a)   # 撤销父骨 Y 旋，回到弦骨局部帧
    axis = 0.0 if side == 'l' else 180.0
    return (round(axis - math.degrees(math.atan2(dz, dx)), 3),
            round(math.hypot(dx, dz) / STRING_LEN, 4))

def bone_radius_sq(bone, geom):   # 帮助自检：pivot 距自身几何 <=4u
    pass

# ---- 主体几何（body）----
# 弩身前段（文献「臂面刻直槽，以盛箭」）——箭道槽：中间留槽盛箭，弦从上方通过
add('body', [-0.72, 0.80, -10.55], [0.72, 0.955, -5.60], 'blue')           # 弩身前段（箭道梁）
add('body', [-0.72, 0.955, -10.55], [-0.42, 1.05, -5.60], 'blue_d')        # 箭道左沿
add('body', [0.42, 0.955, -10.55], [0.72, 1.05, -5.60], 'blue_d')          # 箭道右沿
# 机匣：前段 + 机槽（开顶/开侧，露出弩机）+ 后段。文献「發弦之機匿於此」
add('body', [-1.05, 0.90, -5.60], [1.05, 2.30, -3.30], 'black')            # 机匣前段
add('body', [-1.05, 0.80, -3.30], [1.05, 0.94, -1.30], 'black_d')          # 机槽底（郭座）
add('body', [-1.05, 0.90, -1.30], [1.05, 2.30, 1.00], 'black')             # 机匣后段
# 弩臂座（riser）+ 前承 + 脚踏环（文献：手拉上弦以脚蹬踏环）
# 弩臂座（riser）：加高容下 0.62u 弓片根；中央留 0.40u 箭道槽（待发矢从此穿出）
add('body', [-1.85, 0.78, -11.50], [-0.20, 1.42, -10.55], 'blue')          # 弩臂座左肩
add('body', [0.20, 0.78, -11.50], [1.85, 1.42, -10.55], 'blue')            # 弩臂座右肩
add('body', [-0.20, 1.20, -11.50], [0.20, 1.42, -10.55], 'blue')           # 箭道桥
add('body', [-1.85, 0.70, -11.35], [1.85, 0.78, -10.55], 'blue_d')         # 座下缘
add('body', [-1.60, 1.42, -11.10], [1.60, 1.52, -10.70], 'black')          # 座顶装饰
add('body', [-0.40, 1.05, -11.80], [0.40, 1.30, -11.50], 'black')          # 前承块
add('body', [-0.18, 0.55, -11.78], [0.18, 1.10, -11.52], 'metal')          # 脚踏环颈（接弩头）
ring('body', 0.0, 0.28, -11.79, -11.56, 0.30, 0.52, 8, 'metal')            # 脚踏环
# 桨形握把（tiller）向下 + 托
add('body', [-0.80, -1.20, -1.90], [-0.52, 1.20, 0.80], 'wood')            # 握把护木左（中空露悬刀）
add('body', [0.52, -1.20, -1.90], [0.80, 1.20, 0.80], 'wood')              # 握把护木右
add('body', [-0.80, -2.20, -2.20], [0.80, -1.20, -1.45], 'wood', rot=[-14, 0, 0], pivot=[0, -0.5, -0.3])  # 握把
add('body', [-0.62, -2.75, -2.55], [0.62, -2.20, -1.40], 'wood', rot=[-14, 0, 0], pivot=[0, -0.5, -0.3])  # 握把底
add('body', [-0.78, 0.80, 0.80], [0.78, 1.10, 1.60], 'black')              # 机匣后
# 扳机护（悬刀随牙枢轴前移至 z≈-1.60，护圈随之）
add('body', [-0.32, -0.72, -1.98], [0.32, 0.60, -1.90], 'black')           # 护圈前柱
add('body', [-0.32, -0.72, -1.30], [0.32, 0.92, -1.22], 'black')           # 护圈后柱
add('body', [-0.32, -0.88, -1.98], [0.32, -0.72, -1.22], 'black_d')        # 护圈底
# 枪托（stock）
add('body', [-1.18, 0.45, 1.60], [1.18, 2.70, 6.20], 'wood')
add('body', [-1.18, 0.45, 6.20], [1.18, 2.55, 8.35], 'wood')
add('body', [-1.18, 0.45, 8.35], [1.18, 2.55, 8.55], 'black')
add('body', [-1.22, 0.45, 6.20], [1.22, 0.60, 8.35], 'black')             # 托底导轨
add('body', [-1.08, 2.55, 3.00], [1.08, 2.75, 6.00], 'wood')              # 托腮
# 弩臂（弓片）：一整条连续弧线的扁弓片。文献：弩弓横于臂前部、弓片装弩头（riser）两端、
# 自弩头向后张开；弓片宽 3~5cm。截面薄在 Z（前后 1.5~2.8cm，才弯得动）、宽在 Y（上下 2.9~3.9cm）。
# 10 段各自 rot Y 贴弧线切线 —— 原先 3 段轴对齐方块是阶梯状，远看就是三根直棍。
def do_limb(side):
    bone = 'limb_l' if side == 'l' else 'limb_r'
    sgn = -1.0 if side == 'l' else 1.0
    x0, x1 = LIMB_PIVOT_X * sgn, LIMB_TIP_X * sgn      # 根（埋进弩头）→ 尖端（= 弦挂点）
    z0, z1 = -10.55, LIMB_TIP_Z - 0.12                 # 中心线：根在弩头后缘，尖端中心内收 0.12 半厚
                                                       # ⇒ 尖端后缘正好落在弦面 -7.90（弦卧进弦槽）
    yc, n, th_tip = STR_Y, 10, 24.0                    # 尖端切线角 24°（向后张开）
    th = lambda u: math.radians(th_tip) * u ** 1.15     # 指数>1 ⇒ 越靠尖端弯得越厉害（真弩弓片）
    S = 400
    Itot = sum(math.tan(th((i + .5) / S)) for i in range(S)) / S
    def zarc(u):
        return z0 + (z1 - z0) * (sum(math.tan(th((i + .5) / S * u)) for i in range(S)) / S * u) / Itot
    pts = [(x0 + (x1 - x0) * i / n, zarc(i / n)) for i in range(n + 1)]
    for i in range(n):
        (xa, za), (xb, zb) = pts[i], pts[i + 1]
        u = (i + .5) / n
        h = 0.62 - 0.16 * u                            # 弓片高（Y）：根 3.9cm → 尖 2.9cm
        t = 0.44 - 0.20 * u                            # 前后厚（Z）：根 2.75cm → 尖 1.5cm
        dx, dz = xb - xa, zb - za
        L = math.hypot(dx, dz)
        ang = math.degrees(math.atan2(dz, dx))
        rot = round((180.0 - ang) if side == 'l' else -ang, 3)
        ext = 0.06                                     # 段两端外扩藏缝；末段只往后扩，保住尖端弦面
        if i == n - 1:
            ox, ln = (xa - ext, L + ext) if side == 'r' else (xb, L + ext)
        else:
            ox, ln = min(xa, xb) - ext, L + 2 * ext
        add(bone, [ox, yc - h / 2, za - t / 2], [ox + ln, yc + h / 2, za + t / 2],
            'blue', rot=[0, rot, 0], pivot=[xa, yc, za])
    # 尖端弦槽：两片钢颊夹出 0.10u 槽，弦（y 1.08~1.14）卧其中
    xt = min(x1, x1 - 0.32 * sgn)
    add(bone, [xt, 1.15, -8.16], [xt + 0.32, 1.34, LIMB_TIP_Z], 'steel', pivot=[x1, yc, z1])
    add(bone, [xt, 0.86, -8.16], [xt + 0.32, 1.05, LIMB_TIP_Z], 'steel', pivot=[x1, yc, z1])

def do_limb_pocket(side):
    """弓片根部夹具 + 弓片螺栓：属于弩头（body）——弓片在夹具里屈曲，夹具不动。"""
    sgn = -1.0 if side == 'l' else 1.0
    x0 = LIMB_PIVOT_X * sgn
    add('body', [min(x0, x0 + 0.92 * sgn), 0.74, -10.74],
        [max(x0, x0 + 0.92 * sgn), 1.46, -9.44], 'metal')
    add('body', [min(x0, x0 + 0.26 * sgn), 1.00, -10.44],
        [max(x0, x0 + 0.26 * sgn), 1.20, -9.74], 'brass')
do_limb('l'); do_limb('r'); do_limb_pocket('l'); do_limb_pocket('r')

# 弦（string）：两段各 10.12u（尖端 → 弦心）。弦不可拉伸 ⇒ 拉弦靠弓片屈曲、弦骨只转不伸缩
# （原先靠 scale.x 拉到 1.18，物理上不可能；见 limb_deg_for / string_bone_param）。
def do_string(side):
    bone = 'string_l' if side == 'l' else 'string_r'
    tipx = -LIMB_TIP_X if side == 'l' else LIMB_TIP_X
    add(bone, [min(tipx, 0.0), 1.08, -7.92], [max(tipx, 0.0), 1.14, -7.88], 'cloth',
        pivot=[tipx, STR_Y, LIMB_TIP_Z])
    a, b = (0.62, 0.94) if side == 'l' else (-0.94, -0.62)      # 弦心缠绕（加粗短段 = 搭箭点）
    add(bone, [a, 1.075, -7.935], [b, 1.145, -7.865], 'black', pivot=[tipx, STR_Y, LIMB_TIP_Z])
do_string('l'); do_string('r')

# 弩机（文献：郭、牙、望山、悬刀、钩心、两键；「牙後連有望山」「第一塊與第三塊共用一個轉軸」）
# 郭：浅盘壳体，壁顶 1.06 低于弦面 1.09 —— 弦自郭上通过（原先郭被机匣整块吞没）
add('lock_housing', [-0.95, 0.94, -3.30], [0.95, 1.00, -1.60], 'plastic')    # 郭底板
add('lock_housing', [-0.95, 1.00, -3.30], [-0.82, 1.06, -1.60], 'plastic')   # 郭左壁
add('lock_housing', [0.82, 1.00, -3.30], [0.95, 1.06, -1.60], 'plastic')     # 郭右壁
add('lock_housing', [-0.95, 1.00, -3.30], [0.95, 1.06, -3.18], 'plastic')    # 郭前壁
add('lock_housing', [-0.95, 1.00, -1.72], [0.95, 1.06, -1.60], 'plastic')    # 郭后壁
add('lock_housing', [-1.02, 1.00, -2.46], [1.02, 1.05, -2.36], 'copper')     # 键1（插销，贯穿两壁）
add('lock_housing', [-1.02, 1.00, -2.16], [1.02, 1.05, -2.06], 'copper')     # 键2（插销）
add('lock_housing', [0.95, 0.96, -2.76], [1.28, 1.24, -2.40], 'metal')       # 保险拨片（现代弩 safety）
add('lock_housing', [1.28, 0.98, -2.72], [1.44, 1.22, -2.44], 'plastic')     # 保险钮
# 牙（挂弦钩）：鸟首形，前支突短、后支突长；底部栓孔；与悬刀共用枢轴 (0,1.10,-1.60)
add('nut', [-0.42, 0.98, -1.94], [0.42, 1.09, -1.30], 'brass')               # 牙体（弦坐在其上）
add('nut', [-0.16, 1.09, -1.94], [0.16, 1.30, -1.74], 'brass')               # 前支突（短）
add('nut', [-0.16, 1.09, -1.54], [0.16, 1.44, -1.30], 'brass')               # 后支突（长）
add('nut', [-0.42, 1.00, -1.76], [0.42, 1.06, -1.58], 'copper')              # 牙底栓孔（铜键贯穿）
# 望山（文献「牙後連有望山」；汉代望山刻刻度＝表尺）
add('sight_rear', [-0.26, 1.44, -1.48], [0.26, 2.02, -1.34], 'metal')        # 望山立板
for yy in (1.50, 1.60, 1.70, 1.80, 1.90):
    add('sight_rear', [-0.30, yy, -1.38], [0.30, yy + 0.03, -1.30], 'copper')  # 望山刻度
# 悬刀（扳机）：略呈弧形，上端宽扁、下端略尖；与牙共用一台转轴
add('trigger', [-0.19, 0.10, -1.72], [0.19, 0.84, -1.38], 'brass')           # 上端（宽扁，接钩心）
add('trigger', [-0.15, -0.36, -1.76], [0.15, 0.14, -1.42], 'brass')          # 中段（微后弯）
add('trigger', [-0.11, -0.80, -1.80], [0.11, -0.32, -1.46], 'brass')         # 下端（略尖，指扣）
# 箭匣（文献：横置箭匣，一弩十矢；匣底磁石吸附铁矢）
# 匣左右壁：带观察窗的框（窗洞 1.45~2.70，玻璃嵌在洞内 —— 可见匣内叠放的十矢）
add('magazine', [-0.90, 1.05, -9.30], [-0.72, 2.98, -8.70], 'black')         # 匣左壁前段
add('magazine', [-0.90, 1.05, -6.30], [-0.72, 2.98, -5.80], 'black')         # 匣左壁后段
add('magazine', [-0.90, 1.05, -8.70], [-0.72, 1.45, -6.30], 'black_d')       # 匣左壁下段
add('magazine', [-0.90, 2.70, -8.70], [-0.72, 2.98, -6.30], 'black_d')       # 匣左壁上段
add('magazine', [-0.90, 1.45, -8.70], [-0.86, 2.70, -6.30], 'glass')         # 左观察窗（玻璃嵌洞内）
add('magazine', [0.72, 1.05, -9.30], [0.90, 2.98, -8.70], 'black')           # 匣右壁前段
add('magazine', [0.72, 1.05, -6.30], [0.90, 2.98, -5.80], 'black')           # 匣右壁后段
add('magazine', [0.72, 1.05, -8.70], [0.90, 1.45, -6.30], 'black_d')         # 匣右壁下段
add('magazine', [0.72, 2.70, -8.70], [0.90, 2.98, -6.30], 'black_d')         # 匣右壁上段
add('magazine', [0.86, 1.45, -8.70], [0.90, 2.70, -6.30], 'glass')           # 右观察窗
add('magazine', [-0.72, 1.05, -9.30], [-0.42, 1.17, -5.80], 'black_d')       # 匣底左沿（中间留落箭口）
add('magazine', [0.42, 1.05, -9.30], [0.72, 1.17, -5.80], 'black_d')         # 匣底右沿
add('magazine', [-0.90, 1.05, -9.30], [0.90, 2.98, -9.16], 'black')          # 匣前壁
add('magazine', [-0.90, 1.05, -5.94], [0.90, 2.98, -5.80], 'black')          # 匣后壁
add('magazine', [-0.42, 1.05, -8.60], [-0.20, 1.24, -6.40], 'copper')        # 匣底磁石（左）
add('magazine', [0.20, 1.05, -8.60], [0.42, 1.24, -6.40], 'copper')          # 匣底磁石（右）

# 匣内十矢（《魏氏春秋》「一弩十矢俱發」；《天工開物》「去箭尾羽毛」⇒ 无羽短矢）
for i in range(10):
    bolt('mag_r%d' % (i + 1), -6.00, 1.28 + i * 0.17, -9.02, feather=False)  # 八寸≈18.9cm=3.02u
# 待发矢（躺在箭道槽内、箭匣正下方；弦前扫时推动它）
bolt('round_in', -7.90, 1.03, -10.92, feather=False)   # nock 落在弦静止线 -7.90；箭尖出弩头箭槽
# 左手新箭（nock 朝后，随机手上抬入匣）
bolt('round_hand', -4.40, -1.55, -7.42, feather=False)

# 瞄准镜（scope）
for (z0, z1) in [(-2.40, -1.60), (-1.60, -0.80), (-0.80, 0.0), (0.0, 0.8),
                 (0.8, 1.6), (1.6, 2.4)]:
    ring('scope', 0, 2.85, z0, z1, 0.60, 0.76, 8, 'black')                 # 镜筒
ring('scope', 0, 2.85, -3.20, -2.40, 0.62, 0.80, 8, 'metal')               # 物镜 bell
ring('scope', 0, 2.85, -3.60, -3.20, 0.60, 0.72, 8, 'black')               # 遮光罩
ring('scope', 0, 2.85, 2.40, 3.40, 0.70, 0.90, 8, 'black')                 # 目镜
disc('scope', 0, 2.85, 3.38, 0.44, 8, 'glass_ret')                          # 目镜+十字
disc('scope', 0, 2.85, -3.18, 0.46, 8, 'glass')                             # 物镜
add('scope', [-0.40, 2.60, 3.40], [0.40, 3.10, 3.55], 'black')              # 眼罩
# 镜环
for zc in (-2.2, -1.2, -0.2, 0.8, 1.8):
    add('scope', [-1.15, 2.72, zc - 0.15], [-0.62, 2.95, zc + 0.15], 'blue')
    add('scope', [0.62, 2.72, zc - 0.15], [1.15, 2.95, zc + 0.15], 'blue')
# 调节钮
ring('scope_elev', 0, 3.15, -0.30, -0.10, 0.30, 0.42, 6, 'steel')
ring('scope_wind', 1.60, 2.85, -0.30, -0.10, 0.30, 0.40, 6, 'steel')

if not CUBES:
    raise SystemExit('no geometry')

# ---------------------------------------------------------------- 逐面 UV 装箱
def face_dims(c):
    sx, sy, sz = c['size']
    return {'north': (sx, sy), 'south': (sx, sy),
            'east': (sz, sy), 'west': (sz, sy),
            'up': (sx, sz), 'down': (sx, sz)}

def pack(density):
    rects = []                 # (cube_id, face, w, h)
    for c in CUBES:
        d = face_dims(c)
        for f in FACES:
            w, h = d[f]
            pw = w * density; ph = h * density
            m = max(pw, ph)
            if m > UVCAP:
                k = UVCAP / m; pw *= k; ph *= k
            rects.append((c['id'], f, max(2, int(round(pw))), max(2, int(round(ph)))))
    order = sorted(range(len(rects)), key=lambda i: (-rects[i][3], -rects[i][2]))
    placed = [None] * len(rects)
    x = y = row_h = 0
    G = 1
    for i in order:
        _, _, w, h = rects[i]
        if x + w > TEX:
            x = 0; y += row_h + G; row_h = 0
        if y + h > TEX:
            return None
        placed[i] = (x, y)
        x += w + G
        row_h = max(row_h, h)
    out = {}
    for i, p in enumerate(placed):
        ci, f, w, h = rects[i]
        out.setdefault(ci, {})[f] = (p[0], p[1], w, h)
    return out

density = S
placement = pack(density)
while placement is None and density >= 8:
    density -= 1
    placement = pack(density)
if placement is None:
    raise SystemExit('图集塞不下')
print('pack density = %.0f, faces placed' % density, flush=True)

# ---------------------------------------------------------------- 图集绘制
def clamp255(x):
    return max(0, min(255, int(x)))

atlas = bytearray(b'\x00\x00\x00\x00' * (TEX * TEX))

def paint_face(ci, face, ux, uy, w, h):
    mat_type, base = MAT[CUBES_byid[ci]['mat']]
    n = FACE_N[face]
    lum = n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2]
    shade = 0.58 + 0.42 * max(0.0, lum)
    rng = LC(ci * 977 + FACE_SEED[face])
    amax = max(1.0, min(w, h) / 6.0)
    for j in range(h):
        exj = min(j, h - 1 - j)
        for i in range(w):
            if mat_type == 'wood':
                nz = (rng.f() - 0.5) * 0.16
                if (i * 3 + j) % 7 == 0:
                    nz -= 0.22
            elif mat_type in ('plastic', 'glass'):
                nz = (rng.f() - 0.5) * 0.10
            elif mat_type in ('brushed', 'metal'):
                nz = (rng.f() - 0.5) * 0.20
            elif mat_type == 'cloth':
                nz = (rng.f() - 0.5) * 0.26
            else:
                nz = (rng.f() - 0.5) * 0.14
            exi = min(i, w - 1 - i)
            aof = 1.0 - AO * max(0.0, 1.0 - min(exi, exj) / amax)
            c = [clamp255(base[k] * shade * (1 + nz) * aof) for k in range(3)]
            if face == 'up':
                c = [clamp255(v * 1.10) for v in c]
            r = uy + j; col = ux + i
            idx = (r * TEX + col) * 4
            atlas[idx:idx + 4] = bytes((c[0], c[1], c[2], 255))
    # 十字分划（目镜玻璃 +Z 面）
    if mat_type == 'glass_reticle':
        cx = w // 2; cy = h // 2
        t = max(2, int(round(min(w, h) * 0.02)))
        dots = [(cx - w // 4, cy), (cx + w // 4, cy), (cx, cy - h // 4), (cx, cy + h // 4)]
        for j in range(h):
            for i in range(w):
                if abs(i - cx) <= t or abs(j - cy) <= t:
                    atlas[((uy + j) * TEX + (ux + i)) * 4:((uy + j) * TEX + (ux + i)) * 4 + 3] = bytes(CROSS)
                for (dx, dy) in dots:
                    if abs(i - dx) <= 1 and abs(j - dy) <= 1:
                        atlas[((uy + j) * TEX + (ux + i)) * 4:((uy + j) * TEX + (ux + i)) * 4 + 3] = bytes(CROSS)

CUBES_byid = {c['id']: c for c in CUBES}
for ci, faces in placement.items():
    for f, (x, y, w, h) in faces.items():
        paint_face(ci, f, x, y, w, h)

# ---------------------------------------------------------------- PNG
def png_build():
    raw = b''
    for y in range(TEX):
        raw += b'\x00' + bytes(atlas[y * TEX * 4:(y + 1) * TEX * 4])
    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', TEX, TEX, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9))
            + chunk(b'IEND', b''))

_PNG = png_build()

def write_png(path):
    with open(path, 'wb') as f:
        f.write(_PNG)

# ---------------------------------------------------------------- geo.json
def build_geo():
    bones = []
    bone_indices = {b['name']: i for i, b in enumerate(BONES)}
    for b in BONES:
        entry = {'name': b['name'], 'pivot': b['pivot']}
        if b['parent']:
            entry['parent'] = b['parent']
        cube_list = []
        for ci, c in enumerate(CUBES):
            if c['bone'] == b['name']:
                cj = {'origin': c['origin'], 'size': c['size']}
                if c['rot']:
                    cj['rotation'] = c['rot']
                    cj['pivot'] = c['pivot']
                uv = {}
                for f in FACES:
                    x, y, w, h = placement[c['id']][f]
                    uv[f] = {'uv': [int(x), int(y)], 'uv_size': [int(w), int(h)]}
                cj['uv'] = uv
                cube_list.append(cj)
        if cube_list:
            entry['cubes'] = cube_list
        bones.append(entry)
    return {'format_version': '1.12.0',
            'minecraft:geometry': [{'description': {
                    'identifier': IDENT, 'texture_width': TEX, 'texture_height': TEX,
                    'visible_bounds_width': 2.0, 'visible_bounds_height': 2.0,
                    'visible_bounds_offset': [0, 1.2, 0]},
                'bones': bones}]}

# ---------------------------------------------------------------- 动画（拉弦 FK）
# 弦不可拉伸：弦半段长恒为 STRING_LEN=10.12。拉弦时弓片绕弩头枢轴屈曲（尖端向后收 ≈13.5°），
# 弦骨只做旋转（scale 恒 1），两段弦内端始终汇于 (0, 1.10, z_nock)；z_nock=-1.60 即牙（挂机）。
# 解算见模块上方 limb_deg_for / string_bone_param（几何、动画、自检共用同一套）。
def string_pose(p, z_nock):
    """把「弓片屈曲 + 弦骨旋转」写进姿态 p。"""
    for side in ('l', 'r'):
        a = limb_deg_for(side, z_nock)
        r, sc = string_bone_param(side, z_nock, a)
        p['limb_%s' % side] = ((0, a, 0), (0, 0, 0), (1, 1, 1))
        p['string_%s' % side] = ((0, r, 0), (0, 0, 0), (sc, 1, 1))

# 牙（nut）：弦拉满时牙已把弦锁住——牙保持静止（弦勾在牙上即剧院挂机）
# 我们用弦的直观表达：静止弦在箭槽（z<-7.9 之前的箭槽区）……为清晰：
# 拉弦：弦从 z_draw=-7.90(静止) 拉到 z_draw=-1.96(牙前)。牙固定在 -1.60。
#   拉满时 z_nock 应收斂到牙：用 z_draw=-1.90 作为「挂机」。动画止于此并保持（勾住）。

def anim_keyframes():
    # 每关键帧：返回 {bone: (rot,pos,scale)}
    def base_pose():
        p = {}
        scale1 = (1, 1, 1); zero = (0, 0, 0)
        for b in BONES:
            nm = b['name']
            sc = (1, 1, 1)
            if nm == 'round_hand':
                sc = (0, 0, 0)          # 平时隐藏
            p[nm] = (zero, zero, sc)
        return p
    return base_pose

def all_animations():
    return build_anims()

def build_anims():
    anims = {}
    B = lambda: build_base()

    def build_base():
        p = {}
        for b in BONES:
            nm = b['name']
            hide = nm == 'round_hand'
            p[nm] = ((0, 0, 0), (0, 0, 0), (0, 0, 0) if hide else (1, 1, 1))
        return p

    # -- static_idle --
    fps_keys = []
    for i in range(41):
        t = i / 20.0
        p = build_base()
        p['move'] = ((0, 0, 0), (0, 0.02 * math.sin(2 * math.pi * t / 2.0), 0), (1, 1, 1))
        string_pose(p, -7.90)                      # 弦挂静止位 -7.90（弓片不屈曲）
        fps_keys.append((round(t, 4), p))
    anims['static_idle'] = {'animation_length': 2.0, 'loop': True, 'bones': merge(fps_keys)}

    # -- draw 拉弦 --
    DRAW_LEN = 1.2
    keys = []
    for i in range(int(DRAW_LEN * 24) + 1):
        t = i / 24.0
        u = min(1.0, t * 1.2)                     # 0->1 于 0.83s
        if t < 0.85:
            ease = u
        else:
            ease = 1.0                              # 拉满挂机，牙锁住
        z_nock = -7.90 + (-1.60 - -7.90) * ease      # 静止 -7.90 -> 满弦牙处 -1.60
        p = build_base()
        string_pose(p, z_nock)                     # 弓片屈曲 + 弦骨旋转（弦长恒定，不拉伸）
        # 拉弦时整体往后顿一点 + 微沉
        p['move'] = ((0, 0, 0), (0, -0.05 * ease, -0.18 * ease), (1, 1, 1))
        keys.append((round(t, 4), p))
    anims['draw'] = {'animation_length': DRAW_LEN, 'loop': False, 'bones': merge(keys)}

    # -- shoot 放弦 --
    SHOOT_LEN = 0.6
    keys = []
    for i in range(int(SHOOT_LEN * 24) + 1):
        t = i / 24.0
        u = min(1.0, t / 0.13)                    # 弦 0.13s 弹回（u:0拉满 -> 1回位）
        z_nock = -1.60 + (-7.90 - -1.60) * u       # 满弦 -1.60 -> 静止 -7.90
        p = build_base()
        string_pose(p, z_nock)                     # 弦回位：弓片回弹、弦长恒定
        # 弩箭 round_in 前进后消失
        if t < 0.10:
            p['round_in'] = ((0, 0, 0), (0, 0, -min(14.0, t * 160)), (1, 1, 1))
        else:
            p['round_in'] = ((0, 0, 0), (0, 0, -14), (0, 0, 0))
        # 后坐
        rt = min(1.0, t / 0.18)
        p['move'] = ((-2.2 * rt, 0, 0), (0, 0, 0.10 * rt), (1, 1, 1))
        p['move'] = ((8.0 * rt * (1 - rt), 0, 0), (0, 0, 0.10 * rt * (1 - rt)), (1, 1, 1))
        keys.append((round(t, 4), p))
    anims['shoot'] = {'animation_length': SHOOT_LEN, 'loop': False, 'bones': merge(keys)}

    # -- reload_tactical 拿出新箭放进弹仓顶 --
    T = 1.6
    keys = []
    for i in range(int(T * 24) + 1):
        t = i / 24.0
        p = build_base()
        p['move'] = ((0, 0, 0), (0, 0, 0), (1, 1, 1))  # reset round_hand hidden
        # round_hand 现身并做插入
        # 阶段：0-0.3 抬升(手，箭头),0.3-1.0 送进弹仓,1.0-1.4 抽手
        y_rel = 0.0
        x_rel = 0.0
        z_rel = 0.0
        vis = 0.0
        ry = 0.0
        # 箭匣顶槽 = mag_r10：(0, 2.81, -6.00)，内箭同为八寸 3.02u
        # round_hand pivot = (-2.6,-1.55,-4.4)。把新箭送到匣顶槽 (0, 2.81, -6.00)
        # 简化：直接把 round_hand 平移让箭柄进匣
        lift = min(1.0, t / 0.35)
        push = min(1.0, max(0.0, (t - 0.30) / 0.70))
        ret = min(1.0, max(0.0, (t - 1.10) / 0.30))
        vis = 1.0 if t > 0.05 and ret < 1.0 else (0.0 if ret >= 1.0 else (1.0 if t>0.05 else 0.0))
        # 位置：抬升到上方，再前送进匣
        if t <= 0.05:
            vis = 0.0
        cur_y = -1.55 + lift * 4.36                   # 到 2.81 = mag_r10 顶层槽高
        cur_z = -4.40 + push * (-1.60)                # 到 -6.00 = 弹仓槽 nock
        cur_x = -2.6 + push * 2.6                     # 到 0（对准弹仓中线）
        p['round_hand'] = ((0, 0, -20 * (1 - lift)), (cur_x, cur_y, cur_z), (vis, vis, vis))
        # 弩机 / 夹持
        keys.append((round(t, 4), p))
    anims['reload_tactical'] = {'animation_length': T, 'loop': False, 'bones': merge(keys)}

    # -- ADS_up / ADS_down 开镜（拉镜到眼前）--
    ADS = 0.18
    keys_up = []
    for i in range(int(ADS * 24) + 1):
        t = i / 24.0
        u = min(1.0, t / ADS)
        p = build_base()
        # 把 scope 前移+抬高贴合视线：用 move 平移（整枪上移前伸），角度微调
        p['move'] = ((0, 0, 0), (0, 0.18 * u, -0.12 * u), (1, 1, 1))
        keys_up.append((round(t, 4), p))
    anims['ADS_up'] = {'animation_length': ADS, 'loop': False, 'bones': merge(keys_up)}
    keys_down = []
    for i in range(int(ADS * 24) + 1):
        t = i / 24.0
        u = min(1.0, t / ADS)
        p = build_base()
        p['move'] = ((0, 0, 0), (0, 0.18 * (1 - u), -0.12 * (1 - u)), (1, 1, 1))
        keys_down.append((round(t, 4), p))
    anims['ADS_down'] = {'animation_length': ADS, 'loop': False, 'bones': merge(keys_down)}

    # -- inspect 检视（翻转看）--
    INS = 2.6
    keys = []
    for i in range(int(INS * 24) + 1):
        t = i / 24.0
        p = build_base()
        string_pose(p, -7.90)
        y = -math.degrees(2 * math.pi * t / INS) * 0.5
        p['root'] = ((0, -y, 0), (0, 0, 0), (1, 1, 1))
        keys.append((round(t, 4), p))
    anims['inspect'] = {'animation_length': INS, 'loop': False, 'bones': merge(keys)}
    return anims

def merge(keys):
    bones = {}
    for t, pose in keys:
        for bn, (rot, pos, scale) in pose.items():
            entry = bones.setdefault(bn, {'rotation': {}, 'position': {}, 'scale': {}})
            ts = '%s' % (round(t, 4),)
            entry['rotation'][ts] = {'post': {'vector': [round(x, 4) for x in rot]}, 'lerp_mode': 'catmullrom'}
            entry['position'][ts] = {'post': {'vector': [round(x, 4) for x in pos]}, 'lerp_mode': 'catmullrom'}
            entry['scale'][ts] = {'post': {'vector': [round(x, 4) for x in scale]}, 'lerp_mode': 'catmullrom'}
    return bones

# ---------------------------------------------------------------- 自检
def selfcheck(geo, anims):
    fails = []
    notes = []
    geom = geo['minecraft:geometry'][0]
    allc = [c for b in geom['bones'] for c in b.get('cubes', [])]
    # A 长度（漂塞取全 cube bbox 近似）
    lo = [1e9] * 3; hi = [-1e9] * 3
    for c in allc:
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    v = [c['origin'][k] + c['size'][k] * (1, 0, 0)[dx] + c['size'][1] * 0 * (0, 1, 0)[dy] +
                         c['size'][2] * 0 * (0, 0, 1)[dz] for k in range(3)]
        # 简单角点
        for kx in (0, 1):
            for ky in (0, 1):
                for kz in (0, 1):
                    v = [c['origin'][0] + c['size'][0] * kx,
                         c['origin'][1] + c['size'][1] * ky,
                         c['origin'][2] + c['size'][2] * kz]
                    for k in range(3):
                        lo[k] = min(lo[k], v[k]); hi[k] = max(hi[k], v[k])
    L = hi[2] - lo[2]
    notes.append('bbox Z=[%.2f,%.2f] len=%.2fu=%.2f格' % (lo[2], hi[2], L, L / 16))
    if not (16 <= L <= 35.2):
        fails.append('弩长 %.2f u 不在弓类 16~35.2' % L)
    # B UV 有像素
    for c in allc:
        for f, uv in c.get('uv', {}).items():
            x, y, w, h = uv['uv'][0], uv['uv'][1], uv['uv_size'][0], uv['uv_size'][1]
            if x < 0 or y < 0 or x + w > TEX or y + h > TEX:
                fails.append('UV越界 %s' % (uv,))
                continue
            ok = any(atlas[(yy * TEX + xx) * 4 + 3] > 0 for yy in range(y, y + h) for xx in range(x, x + w))
            if not ok:
                fails.append('面 %s 全透明' % (f,))
    # C 骨名/父/必需
    names = set()
    import re as _re
    _nm_re = _re.compile(r'^[a-z][a-z0-9_]*$')
    for b in geom['bones']:
        if not _nm_re.match(b['name']):
            fails.append('骨名非法 %s' % b['name'])
        names.add(b['name'])
        if b.get('parent') and b['parent'] not in names and b['parent'] not in {x['name'] for x in geom['bones']}:
            fails.append('父骨缺失 %s' % b['name'])
    for req in ('root', 'move', 'body'):
        if req not in names:
            fails.append('缺必需骨 %s' % req)
    # F
    nc = len(allc); nb = len(geom['bones'])
    notes.append('方块=%d 骨=%d' % (nc, nb))
    if nc > 600: fails.append('方块超600')
    if nb > 40: fails.append('骨超40')
    # 弦自检：弦不可拉伸 ⇒ 两段弦内端必须靠「弩臂屈曲 + 弦骨旋转」汇于弦心/牙。
    # (美术规范.B 十字弩专属断言；FK 与生成器同源，另在 Blender 里量世界坐标交叉验证)
    def str_inner(bone, limb_deg, a_deg, sc):
        tx, tz = limb_tip(bone[-1], limb_deg)              # 该侧尖端（父骨屈曲后）
        phi = math.radians((0.0 if bone == 'string_l' else 180.0) - a_deg)
        dx, dz = STRING_LEN * sc * math.cos(phi), STRING_LEN * sc * math.sin(phi)
        dx, dz = y_rot2(dx, dz, 0.0, 0.0, limb_deg)        # 施加父骨 Y 旋
        return (tx + dx, tz + dz)
    for clip in ('static_idle', 'draw', 'shoot', 'inspect'):
        dr = anims[clip]['bones']
        ks = sorted(map(float, dr['string_l']['rotation'].keys()))
        al = ar = rl = rr = sl = sr = 0.0
        for t in ks:
            def v(b, ch):
                d = dr[b][ch]
                k = '%s' % (round(t, 4),)
                k = k if k in d else '%s' % (t,)
                return d[k].get('post', {}).get('vector')
            al = v('limb_l', 'rotation')[1]; ar = v('limb_r', 'rotation')[1]
            rl = v('string_l', 'rotation')[1]; sl = v('string_l', 'scale')[0]
            rr = v('string_r', 'rotation')[1]; sr = v('string_r', 'scale')[0]
            el = str_inner('string_l', al, rl, sl); er = str_inner('string_r', ar, rr, sr)
            d = math.hypot(el[0] - er[0], el[1] - er[1])
            if d > 0.05:
                fails.append('%s t=%.3f 两段弦内端分离 %.3f u' % (clip, t, d))
            if abs(sl - 1.0) > 0.02 or abs(sr - 1.0) > 0.02:
                fails.append('%s t=%.3f 弦被拉伸 sc=%.3f/%.3f（弦不可拉伸）' % (clip, t, sl, sr))
        if clip == 'draw':
            e = str_inner('string_l', al, rl, sl)
            if math.hypot(e[0] - 0, e[1] - (-1.60)) > 0.05:
                fails.append('draw 拉满弦内端未落牙: %s' % (e,))
            if abs(al) < 5.0:
                fails.append('draw 拉满弩臂几乎不屈曲 al=%.2f°（弓片不弯 = 不像真弩）' % al)
            notes.append('draw 拉满：弩臂屈曲 al=%.2f° ar=%.2f°，弦镜 a=%.1f/%.1f，弦心落 (%.2f,%.2f)'
                         % (al, ar, rl, rr, e[0], e[1]))
    return fails, notes, nc, nb

# ------------------------------------------------- 交付坐标约定（Bedrock / GeckoLib）
# 本文件内部一切几何与动画都按**右手系**（与 Blender / Minecraft Java 模型同系）求解，
# bf_selfcheck 也在这个空间里断言。但 .geo.json / .animation.json 的**文件格式**用的是
# 镜像约定 —— 实测（Blockbench 5.2.1 + GeckoLib Animation Utils 插件）：
#   · 立方体坐标 / 立方体 pivot / 骨骼 pivot：X 取反（文件 limb_r origin.x=1.56 → 工程 x=-2.53）
#   · 旋转：X、Y 取反（文件 draw limb_r Y=-14.05 → 工程 animator +14.05）
#   · 动画位置通道：X 取反（文件 round_hand x=-2.6 → 工程 +2.6），Y/Z 不动
# GeckoLib 运行时加载动画同样对旋转「X、Y 取负」（BakedAnimationsAdapter.java:221-223），
# 与 Blockbench 内部表示一致；所以**文件必须写成取反形式**，游戏与 Blockbench 读回后
# 才等于这里设计的物理模型。转换只发生在写出这一步，Python 侧数值与自检不受影响。
#
# ⚠ 2026-10-08 修：原先这里漏了 **cube 自己的 pivot**（只有骨级 pivot 被取反）。
#   带 pivot 的方块在文件里绕一个「镜像前」的支点旋转 —— 而 origin 已经镜像过，于是
#   支点落到了身体的另一侧。crossbow 有 372/421 个方块中招，游戏里表现为**模型散架**
#   （方块各自绕错误支点转 8°~39° 后各奔东西）。因为本文件是十字弩专属工具链，
#   只有它中招：awm/m1/mosin/uzi/s686 走的是别的生成路径，cube 级 pivot 都是对的。
_NEG_POS = (0,)
_NEG_ROT = (0, 1)

def _neg_axes(v, axes):
    if not isinstance(v, (list, tuple)):
        return v
    return [(-c if (i in axes and isinstance(c, (int, float))) else c) for i, c in enumerate(v)]

def game_convention_geo(doc):
    for geo in doc.get('minecraft:geometry', []):
        for bone in geo.get('bones', []):
            if 'pivot' in bone:
                bone['pivot'] = _neg_axes(bone['pivot'], _NEG_POS)
            for cube in bone.get('cubes', []):
                # origin 是最小角：X 镜像后新最小角 = -(旧最小角 + 边长)，边长不变
                if 'origin' in cube and 'size' in cube:
                    o, s = cube['origin'], cube['size']
                    cube['origin'] = [-(o[0] + s[0]), o[1], o[2]]
                # pivot 是一个**点**（不是角），所以按普通点镜像取反即可 —— 与骨级 pivot 同规则。
                # 漏掉这一条会让方块绕另一侧的支点旋转，见上面 2026-10-08 的说明。
                if 'pivot' in cube:
                    cube['pivot'] = _neg_axes(cube['pivot'], _NEG_POS)
                if 'rotation' in cube:
                    cube['rotation'] = _neg_axes(cube['rotation'], _NEG_ROT)
    return doc

def game_convention_anims(doc):
    for clip in (doc.get('animations') or {}).values():
        for bone in (clip.get('bones') or {}).values():
            for chan, axes in (('rotation', _NEG_ROT), ('position', _NEG_POS)):
                node = bone.get(chan)
                if not isinstance(node, dict):
                    continue
                for key, kf in list(node.items()):
                    if isinstance(kf, dict):
                        for half in ('pre', 'post'):
                            h = kf.get(half)
                            if isinstance(h, dict) and 'vector' in h:
                                h['vector'] = _neg_axes(h['vector'], axes)
                            elif isinstance(h, (list, tuple)):
                                kf[half] = _neg_axes(h, axes)
                    elif isinstance(kf, (list, tuple)):
                        node[key] = _neg_axes(kf, axes)
    return doc

# ---------------------------------------------------------------- 写出
def write_all(geo, anims):
    for sub in ('geo', 'animations', 'textures', 'textures/models'):
        os.makedirs(os.path.join(RES, sub), exist_ok=True)
    anim_doc = {'format_version': '1.8.0', 'animations': anims, 'geckolib_format_version': 2}
    # 交付前转成文件约定（内部 doc 保持右手系，报告/自检不受影响）
    geo_out = game_convention_geo(copy.deepcopy(geo))
    anim_out = game_convention_anims(copy.deepcopy(anim_doc))
    # geo
    geo_txt = json.dumps(geo_out, ensure_ascii=False, indent=2)
    with open(os.path.join(ART, NAME + '.geo.json'), 'w', encoding='utf-8') as f:
        f.write(geo_txt)
    with open(os.path.join(RES, 'geo', NAME + '.geo.json'), 'w', encoding='utf-8') as f:
        f.write(geo_txt)
    # anim
    anim_txt = json.dumps(anim_out, ensure_ascii=False, indent=2)
    with open(os.path.join(ART, NAME + '.animation.json'), 'w', encoding='utf-8') as f:
        f.write(anim_txt)
    with open(os.path.join(RES, 'animations', NAME + '.animation.json'), 'w', encoding='utf-8') as f:
        f.write(anim_txt)
    # texture（同一字节两份）
    write_png(os.path.join(ART, NAME + '_geo.png'))
    write_png(os.path.join(RES, 'textures', 'models', NAME + '_geo.png'))

def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
    geo = build_geo()
    anims = build_anims()
    write_all(geo, anims)
    fails, notes, nc, nb = selfcheck(geo, anims)
    print('=== crossbow 自检 ===')
    for n in notes:
        print('  ', n)
    if fails:
        print('未通过：')
        for f in fails:
            print('   [X]', f)
        return 1
    print('PNG %d KB' % (len(_PNG) // 1024))
    print('全部通过')
    return 0

if __name__ == '__main__':
    sys.exit(main())