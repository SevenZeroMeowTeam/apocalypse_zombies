"""通用「几何 + 贴图」软件预览器（纯标准库，不用 Blender、不用任何渲染器）。

为什么需要它：改完几何最该做的一件事是**看图**。项目里 Blender 被禁用，Blockbench 的
3D 视口又只在它有前台标签时才存在（MCP 建的项目不挂 UI，`document.getElementById('canvas')`
取不到）。所以这里自己写一个够用的正交软渲染：读 geo JSON + 贴图 PNG，逐面出图。

口径（必须写清楚，否则看图会看错）：
- **只渲染 rest 姿态**：Bedrock geo 的 `origin/size` 就是静置世界坐标，rest 下所有骨骼零旋转，
  所以这里**完全不需要骨骼链**（骨骼只在动画时起作用，动画用 bride_pose_probe.py 另查）。
- 正交投影，无透视；按面的平均相机深度排序后画（画家算法）—— 轴对齐方块足够。
- 背面剔除：面的法线与视线同向则跳过。
- 光照：固定方向光（左上前方）+ 面朝向系数，纯粹为了让人眼分得出体积。
- UV：按 Bedrock 各面的 u/v 走向贴，最近邻采样（要看清单个像素就放大）。

用法：
    python tools/model_preview.py art/soldier/soldier_zombie.geo.json \
        art/soldier/soldier_archer.png out.png "0,30,90" 900
"""
import json
import math
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bride_face_crop import read_png, write_png  # noqa: E402

# 面法线、面的两条边（u 轴、v 轴，v 轴按贴图向下为正）
FACE_VERTS = {
    "north": lambda x, y, z, w, h, d: [(x, y, z), (x + w, y, z), (x + w, y + h, z), (x, y + h, z)],
    "south": lambda x, y, z, w, h, d: [(x + w, y, z + d), (x, y, z + d), (x, y + h, z + d), (x + w, y + h, z + d)],
    "east":  lambda x, y, z, w, h, d: [(x + w, y, z), (x + w, y, z + d), (x + w, y + h, z + d), (x + w, y + h, z)],
    "west":  lambda x, y, z, w, h, d: [(x, y, z + d), (x, y, z), (x, y + h, z), (x, y + h, z + d)],
    "up":    lambda x, y, z, w, h, d: [(x, y + h, z + d), (x, y + h, z), (x + w, y + h, z), (x + w, y + h, z + d)],
    "down":  lambda x, y, z, w, h, d: [(x, y, z), (x, y, z + d), (x + w, y, z + d), (x + w, y, z)],
}
FACE_NORMAL = {"north": (0, 0, -1), "south": (0, 0, 1), "east": (1, 0, 0),
               "west": (-1, 0, 0), "up": (0, 1, 0), "down": (0, -1, 0)}
# 每个面的 (u 轴, v 轴)（v 轴指向贴图下方）= 该面对应的两条世界轴
FACE_AXES = {
    "north": ((1, 0, 0), (0, -1, 0)),
    "south": ((-1, 0, 0), (0, -1, 0)),
    "east":  ((0, 0, -1), (0, -1, 0)),
    "west":  ((0, 0, 1), (0, -1, 0)),
    "up":    ((1, 0, 0), (0, 0, -1)),
    "down":  ((1, 0, 0), (0, 0, 1)),
}
LIGHT = (0.38, 0.80, -0.46)   # 归一化后的固定方向光（左上、略偏前）


def norm(v):
    l = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / l for c in v)


LIGHT = norm(LIGHT)


def rot_z(v, deg):
    c, si = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [v[0] * c - v[1] * si, v[0] * si + v[1] * c, v[2]]


def rot_y(v, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (v[0] * c + v[2] * s, v[1], -v[0] * s + v[2] * c)


def rot_x(v, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (v[0], v[1] * c - v[2] * s, v[1] * s + v[2] * c)


class View:
    """一个视角：把世界坐标 → 屏幕坐标（正交）。"""

    def __init__(self, yaw, pitch, cx, cy, cz, scale):
        self.yaw, self.pitch, self.scale = yaw, pitch, scale
        self.c = (cx, cy, cz)

    def to_cam(self, p):
        v = (p[0] - self.c[0], p[1] - self.c[1], p[2] - self.c[2])
        v = rot_x(rot_y(v, self.yaw), self.pitch)
        return v

    def to_screen(self, p, ox, oy):
        v = self.to_cam(p)
        # 屏幕 x 取负：与 render() 一致（相机在 −z 侧朝 +z 看，相机右方是 −x）。
        # 早先这里写成 +v[0]，与真正画出来的图差一个水平镜像 —— 用它对位裁图会裁到镜像位置。
        return (ox - v[0] * self.scale, oy - v[1] * self.scale, v[2])


def load_geo(path):
    g = json.load(open(path, encoding="utf-8"))
    geo = g["minecraft:geometry"][0]
    cubes = []
    for b in geo["bones"]:
        for c in b.get("cubes", []):
            cubes.append((b["name"], c))
    return geo, cubes


# ── 姿态：按 .animation.json 把模型摆到某一时刻（单位与符号按 GeckoLib 源码）──
# GeckoLib 4.8.4 的事实（javap 反编译本机 geckolib-forge-1.20.1-4.8.4.jar + joined 客户端 jar，
# 不是猜的，2026-09-27 复核）：
#   * 平移 RenderUtils.translateMatrixToBone：translate(−posX/16, +posY/16, +posZ/16)
#     ⇒ **只有位置 x 取负**，y/z 不取；单位 u（1 = 1 模型像素 = 1/16 格）。
#   * 旋转 RenderUtils.rotateMatrixAroundBone：依次 mulPose(Axis.Z(rotZ))、Axis.Y(rotY)、
#     Axis.X(rotX)，**rot 值原样传入、一个都不取负**。Axis.<clinit> 把 f_252403_/f_252436_/
#     f_252529_ 绑到 m_252774_/m_253246_/m_253127_（= Quaternionf.rotationX/Y/Z(+angle)），
#     取负的 m_252978_/m_253050_/m_253156_ 只被 XN/YN/ZN 常量用到。
#     ⇒ 绕 +Y 的正角把 +X 转向 −Z（右手系），绕 +X 的正角把 +Y 转向 +Z。
#   * 结论：**rotation 三个分量一律原样使用**。2026-09-27 前这里按一条错注释把 x/y 取负，
#     于是所有「摆姿」预览图都前后/左右镜像 —— 「弦被画到弩前方」正是它造成的（几何数据
#     一直是对的）。`--selftest` 就是这条的守门人。
def load_hierarchy(geo):
    par, piv = {}, {}

    # 本工程的 geo 用 GeckoLib 支持的**平铺 + parent 字段**写法
    # （GeckoLib: loading/json/raw/Bone.java 读 "parent"，GeometryTree 据此建树），
    # 不是 Blockbench 的 children 嵌套。两种都认。
    flat = {}

    def walk(b, parent):
        par[b["name"]] = b.get("parent", parent)
        piv[b["name"]] = b.get("pivot", [0, 0, 0])
        flat[b["name"]] = b
        for c in b.get("children", []):
            walk(c, b["name"])

    for b in geo["bones"]:
        walk(b, None)
    for name in flat:                      # 平铺时再按 parent 补齐层级
        if par[name] is None and flat[name].get("parent"):
            par[name] = flat[name]["parent"]
    return par, piv


def chan_at(clip, bone, chan, t, default=None):
    """线性取值；在键时刻取值精确（所以核对姿态时挑键时刻看）。

    default：剪辑里没有该通道时用什么。rotation 要传骨骼在 geo 里的**静止旋转**
    （GeckoLib 每帧把骨骼恢复到 geo 基线、再叠动画键，所以没被动画的骨骼保持静止姿态；
    0 只在几何本身没写旋转时才对）。
    """
    keys = (clip.get("bones", {}).get(bone) or {}).get(chan)
    if not keys:
        return list(default) if default else [0.0, 0.0, 0.0]
    pts = sorted((float(k), v["post"]["vector"]) for k, v in keys.items())
    if t <= pts[0][0]:
        return list(pts[0][1])
    if t >= pts[-1][0]:
        return list(pts[-1][1])
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t0 <= t <= t1:
            f = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return [v0[i] + (v1[i] - v0[i]) * f for i in range(3)]
    return list(pts[-1][1])


HIDDEN_KEY = "__hidden__"      # 摆帧时 scale=0 的部件（游戏内隐藏）——预览同样剔除


def make_poses(geo, anim_json, clip_name, t):
    doc = json.load(open(anim_json, encoding="utf-8"))
    clip = doc["animations"][clip_name]
    par, piv = load_hierarchy(geo)
    flat = {}

    def _walk(b):
        flat[b["name"]] = b
        for c in b.get("children", []):
            _walk(c)

    for b in geo["bones"]:
        _walk(b)
    memo = {}

    def xf(name):
        if name in memo:
            return memo[name]
        P = (lambda v: v) if par[name] is None else xf(par[name])
        p = piv[name]
        pos = chan_at(clip, name, "position", t)
        rot = chan_at(clip, name, "rotation", t, default=flat[name].get("rotation"))
        px, py, pz = -pos[0], pos[1], pos[2]
        # rot_* 接受**度**（内部转弧度）；GeckoLib 原样使用三个分量，不做符号翻转
        rx, ry, rz = rot[0], rot[1], rot[2]

        def f(v, p=p, P=P, px=px, py=py, pz=pz, rx=rx, ry=ry, rz=rz):
            w = [v[0] - p[0], v[1] - p[1], v[2] - p[2]]
            w = rot_z(rot_y(rot_x(w, rx), ry), rz)
            return P([p[0] + w[0] + px, p[1] + w[1] + py, p[2] + w[2] + pz])

        memo[name] = f
        return f

    poses = {n: xf(n) for n in par}
    # scale=0 的部件（hand_l 手套 / bolt_loaded 箭）游戏内被隐藏，预览也必须剔除，
    # 否则摆帧图里会一直看到一只灰手套和一支箭躺在箭道上（台账 §判读坑）。
    # 注意 chan_at 对「没有该通道」返回 0，对 scale 来说那是错的 ⇒ 这里自己判空。
    hidden = set()
    for n in par:
        keys = ((clip.get("bones", {}).get(n) or {}).get("scale")) or {}
        if keys and max(abs(v) for v in chan_at(clip, n, "scale", t)) < 1e-9:
            hidden.add(n)
    poses[HIDDEN_KEY] = hidden
    return poses


def sample(tex, tu, tv):
    w, h, px = tex
    tu = max(0, min(w - 1, tu))
    tv = max(0, min(h - 1, tv))
    i = (tv * w + tu) * 4
    return px[i], px[i + 1], px[i + 2], px[i + 3]


def render(geo, cubes, tex, out, yaws=(0, 30, 90), imgsize=880, panel=560, super=1, posemap=None,
           tint=None):
    """把若干视角并排画进一张图，供人眼一次看完（正面 / 3-4 侧面 / 正侧）。

    tint：{骨骼名: (r,g,b)} —— 诊断用，把该骨骼的**实际绘制像素**换成纯色（仍乘原明暗、
    仍按贴图 alpha 镂空，所以范围与正常渲染逐像素一致，不会多画半个面）。
    """
    W = panel * len(yaws)
    H = imgsize
    bg = (58, 60, 66)
    img = [[bg + (255,) for _ in range(W)] for _ in range(H)]

    xs, ys, zs = [], [], []
    for _, c in cubes:
        o, s = c["origin"], c["size"]
        xs += [o[0], o[0] + s[0]]
        ys += [o[1], o[1] + s[1]]
        zs += [o[2], o[2] + s[2]]
    cx, cz = (min(xs) + max(xs)) / 2.0, (min(zs) + max(zs)) / 2.0
    top, bot = max(ys), min(ys)
    cy = (top + bot) / 2.0
    # 取景必须同时受「高度」与「水平尺度」约束：只看高度的话，扁长的物品（弓/弩/枪）
    # 会横向撑出画框被裁掉。水平方向用 XZ 外接半径 —— 视角要绕 Y 转，用半径才与 yaw
    # 无关，任何角度都不会出框。
    rad2 = 0.0
    for _, c in cubes:
        o, s = c["origin"], c["size"]
        dx = max(abs(o[0] - cx), abs(o[0] + s[0] - cx))
        dz = max(abs(o[2] - cz), abs(o[2] + s[2] - cz))
        rad2 = max(rad2, dx * dx + dz * dz)
    rad = (rad2 ** 0.5) or 1.0
    panel_w = W / float(len(yaws))
    scale = min((H * 0.82) / (top - bot), (panel_w * 0.82) / (2.0 * rad))

    for pi, yaw in enumerate(yaws):
        ox = panel * pi + panel / 2
        oy = H / 2
        view = View(yaw, 12.0, cx, cy, cz, scale)
        # 地面参考线（脚底那一层，用来判断有没有穿地/悬空）
        faces = []
        for bone, c in cubes:
            if posemap is not None and bone in posemap.get(HIDDEN_KEY, ()):
                continue      # 该帧 scale=0：游戏内隐藏，预览同样不画
            x, y, z = c["origin"]
            w, h, d = c["size"]
            for fname, verts in FACE_VERTS.items():
                if fname not in c.get("uv", {}):
                    continue
                quad = verts(x, y, z, w, h, d)
                n = list(FACE_NORMAL[fname])
                if posemap is not None:
                    # 摆了姿势就按变换后的四边形算真实法线，并关掉背面剔除
                    # （静态法线用在旋转后的肢体上会剔错面）
                    f = posemap.get(bone)
                    if f is not None:
                        quad = [f(p) for p in quad]
                    e1 = norm([quad[1][i] - quad[0][i] for i in range(3)])
                    e2 = norm([quad[3][i] - quad[0][i] for i in range(3)])
                    n = [e1[1] * e2[2] - e1[2] * e2[1],
                         e1[2] * e2[0] - e1[0] * e2[2],
                         e1[0] * e2[1] - e1[1] * e2[0]]
                    ctr = [(quad[0][i] + quad[2][i]) / 2.0 for i in range(3)]
                    if sum(n[i] * (quad[0][i] - ctr[i]) for i in range(3)) < 0:
                        n = [-v for v in n]
                cam = [view.to_cam(p) for p in quad]
                ncam = rot_x(rot_y(n, yaw), 12.0)
                if posemap is None and ncam[2] > -0.02:   # 背面（相机看向 -z）
                    continue
                uv = c["uv"][fname]
                u0, v0 = uv["uv"]
                uw, uh = uv["uv_size"]
                faces.append((sum(p[2] for p in cam) / 4.0, cam, fname, (u0, v0, uw, uh), n, ncam,
                              quad, bone))
        # 相机放在模型**正前方**（-z 侧）朝 +z 看：朝向相机的面 = 法线 z 分量为负。（下略）
        # 采样坐标必须按 FACE_AXES 声明的 u/v 方向算，不能按「四边形的顶点顺序」算 ——
        # 顶点顺序只是画多边形的顺序，与「贴图的 u/v 在模型里指哪」是两件事。早前把两者
        # 当成同一件事，于是所有竖直面（n/s/e/w）的贴图**上下翻着贴**：正面的脸渲染出来
        # 眼睛在下巴上、嘴唇在额头上（实测 2026-09-27，用一个上红下蓝的判定立方体重现）。
        # 现在按声明轴把世界坐标投到 u/v 上归一化，顶点顺序怎么排都不影响。
        # 深度：相机 z 越大越远 → 先画远的，所以按 z **降序**排序（早先写成升序，
        # 结果近面被先画、远面盖上去，yaw=0 显示的是背面）。
        faces.sort(key=lambda f: -f[0])
        for _, cam, fname, (u0, v0, uw, uh), n, ncam, quad, bone in faces:
            # 屏幕 x 取负：相机在 -z 侧朝 +z 看时，相机右方是 -x，所以世界的 +x
            # （角色的右手边）要落在画面**左侧**。早先写成 +p[0] 得到的是镜像图，
            # 拿它判断"东西在左手还是右手"会全部反过来。
            pts = [(ox - p[0] * scale, oy - p[1] * scale) for p in cam]
            lam = max(0.0, n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2])
            shade = 0.55 + 0.55 * lam
            ax_u, ax_v = FACE_AXES[fname]
            # 世界空间的 u/v 归一化范围（按声明轴投影，不依赖顶点顺序）
            us = [sum(v[i] * ax_u[i] for i in range(3)) for v in quad]
            vs = [sum(v[i] * ax_v[i] for i in range(3)) for v in quad]
            u0w, u1w = min(us), max(us)
            v0w, v1w = min(vs), max(vs)
            du = (u1w - u0w) or 1.0
            dv = (v1w - v0w) or 1.0
            # 面内两条边在世界空间的长度（= 贴图 u/v 方向的像素数）
            e1 = norm(ax_u)
            e2 = norm(ax_v)
            minx = max(0, int(min(p[0] for p in pts)))
            maxx = min(panel * (pi + 1), int(max(p[0] for p in pts)) + 1)
            miny = max(0, int(min(p[1] for p in pts)))
            maxy = min(H, int(max(p[1] for p in pts)) + 1)
            if maxx <= minx or maxy <= miny:
                continue
            # 前两个顶点定原点，用两条边做仿射插值
            p0, p1, _p2, p3 = pts
            ex = (p1[0] - p0[0], p1[1] - p0[1])
            ey = (p3[0] - p0[0], p3[1] - p0[1])
            det = ex[0] * ey[1] - ex[1] * ey[0]
            if abs(det) < 1e-6:
                continue
            for py in range(miny, maxy):
                for px_ in range(minx, maxx):
                    dx, dy = px_ + 0.5 - p0[0], py + 0.5 - p0[1]
                    a = (dx * ey[1] - dy * ey[0]) / det
                    b = (ex[0] * dy - ex[1] * dx) / det
                    if a < -0.001 or a > 1.001 or b < -0.001 or b > 1.001:
                        continue
                    # 屏幕(a,b) → 世界点（正交投影下与屏幕仿射同基）→ 声明轴归一化 → 贴图像素
                    wx = quad[0][0] + a * (quad[1][0] - quad[0][0]) + b * (quad[3][0] - quad[0][0])
                    wy = quad[0][1] + a * (quad[1][1] - quad[0][1]) + b * (quad[3][1] - quad[0][1])
                    wz = quad[0][2] + a * (quad[1][2] - quad[0][2]) + b * (quad[3][2] - quad[0][2])
                    su = wx * ax_u[0] + wy * ax_u[1] + wz * ax_u[2]
                    sv = wx * ax_v[0] + wy * ax_v[1] + wz * ax_v[2]
                    tu = u0 + ((su - u0w) / du) * uw
                    tv = v0 + ((sv - v0w) / dv) * uh
                    r, g, bl, al = sample(tex, int(tu), int(tv))
                    if al < 8:
                        continue
                    if tint is not None and bone in tint:
                        r, g, bl = tint[bone]
                    img[py][px_] = (int(min(255, r * shade)), int(min(255, g * shade)),
                                    int(min(255, bl * shade)), 255)
    flat = bytearray()
    for row in img:
        for px in row:
            flat.extend(px[:4])
    write_png(out, W, H, flat)
    return W, H


def selftest():
    """自检：用**本工具自己的变换**独立复核「满弦时弦内端落在爪面挂机点」这条几何事实。

    2026-09-27 的镜像缺陷（rotation 的 x/y 被错取负）会让这里两条断言全红 —— 它就是把弦
    画到弩身前方的元凶，而几何数据一直是对的。跑法：`python tools/model_preview.py --selftest`
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    geo_p = os.path.join(root, "art", "crossbow", "crossbow.geo.json")
    anim_p = os.path.join(root, "art", "crossbow", "crossbow.animation.json")
    gd = json.load(open(geo_p, encoding="utf-8"))["minecraft:geometry"][0]
    bones = {b["name"]: b for b in gd["bones"]}
    clip = json.load(open(anim_p, encoding="utf-8"))["animations"]["draw"]
    t_end = max(float(k) for ch in clip["bones"].values() for c in ch.values() for k in c)
    poses = make_poses(gd, anim_p, "draw", t_end)
    latch_z = bones["latch"]["pivot"][2]
    fails = []

    def pts_of(name):
        out = []
        for c in bones[name].get("cubes", []):
            o, s = c["origin"], c["size"]
            for dx in (0, s[0]):
                for dy in (0, s[1]):
                    for dz in (0, s[2]):
                        out.append(poses[name]([o[0] + dx, o[1] + dy, o[2] + dz]))
        return out

    print("draw 满弦 t=%.4fs  挂机点 z=%.2f" % (t_end, latch_z))
    print("（内端取弦方块最靠中线的那只角，天然比弦心靠前约半个弦厚 0.05u + 弦芯豁口 ⇒ 容差 0.18u）")
    for nm in ("string_l", "string_r"):
        inner = min(pts_of(nm), key=lambda q: abs(q[0]))
        d = inner[2] - latch_z
        ok = abs(d) <= 0.18
        print("  %-9s 内端 (%.3f, %.3f, %.3f)  弦z−挂机z = %+.3f  %s"
              % (nm, inner[0], inner[1], inner[2], d, "OK" if ok else "FAIL ← 弦被画到前方了"))
        if not ok:
            fails.append("%s 内端偏挂机点 %.3fu" % (nm, d))
    for nm in ("cam_l", "cam_r"):
        zs = [q[2] for q in pts_of(nm)]
        cz = (min(zs) + max(zs)) / 2.0
        ok = cz > -6.0
        print("  %-9s 满弦中心 z = %+.3f（静止 ≈ −6.2，应向后收）  %s"
              % (nm, cz, "OK" if ok else "FAIL ← 弓臂朝前了"))
        if not ok:
            fails.append("%s 满弦时没向后收（z=%.3f）" % (nm, cz))
    if fails:
        print("SELFTEST FAIL：" + "；".join(fails))
        return 2
    print("SELFTEST PASS：符号约定与 GeckoLib 一致（弦向内落在爪面、弓臂向后收）")
    return 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        return selftest()
    geo_path = sys.argv[1] if len(sys.argv) > 1 else "art/soldier/soldier_zombie.geo.json"
    tex_path = sys.argv[2] if len(sys.argv) > 2 else "art/soldier/soldier_archer.png"
    out = sys.argv[3] if len(sys.argv) > 3 else "art/soldier/_preview.png"
    yaws = [float(v) for v in (sys.argv[4] if len(sys.argv) > 4 else "0,30,90").split(",")]
    size = int(sys.argv[5]) if len(sys.argv) > 5 else 880
    # 可选：第 6/7/8 个参数 = 动画 json、剪辑名、时刻（秒）→ 摆成那一帧的姿势
    posemap = None
    if len(sys.argv) > 8:
        _gd = json.load(open(geo_path, encoding="utf-8"))["minecraft:geometry"][0]
        posemap = make_poses(_gd, sys.argv[6], sys.argv[7], float(sys.argv[8]))

    geo, cubes = load_geo(geo_path)
    tex = read_png(tex_path)
    tw, th = geo["description"]["texture_width"], geo["description"]["texture_height"]
    assert (tex[0], tex[1]) == (tw, th), f"贴图 {tex[0]}x{tex[1]} 与 geo 声明的 {tw}x{th} 不一致"
    W, H = render(geo, cubes, tex, out, yaws, size, posemap=posemap)
    pose = f"  姿态 {sys.argv[7]}@{sys.argv[8]}s" if posemap else ""
    print(f"{out}  {W}x{H}  骨骼 {len(geo['bones'])} / 体块 {len(cubes)} / 视角 {yaws}{pose}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
