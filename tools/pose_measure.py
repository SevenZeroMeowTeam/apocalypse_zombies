#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第一人称持枪姿态量算：把"枪在屏幕上的位置"和"开镜时瞄具对不对得上"算出来。

对应 美术规范.md 的"几何 → Java 常量"纪律：`GunPose.HIP_*`（手持落点）与
`<枪>Item.ADS_X/ADS_Y`（开镜抬枪位移）都必须是**从模型量出来的**，不许眼估。

链条（每一环都在本机反编译源码里核对过，不是凭记忆）:
    p_cam = T_base(±0.56, −0.52−0.6·equip, −0.72)      ItemInHandRenderer.applyItemArmTransform
          · S(firstPersonScale)                        WeaponHandGrip.apply
          · M_stance(aim)                              GunPose.matrix
          · T(display/16) · Rxy(display) · S(0.82)     ItemTransform.apply（translation ×0.0625）
          · T(−0.5,−0.5,−0.5)                          ItemRenderer.render（display 之后）
          · (px/16 + GeckoLib 的 T(+0.5,+0.51,+0.5))   GeoItemRenderer.preRender（在 itemRenderTranslations 之后）

要点（细节决定成败）:
  * display 的 translation 是**1/16 格**，且 `translate(i*x, y, z)` **不取反**（+Y 向上）
  * display 的旋转是 `rotationXYZ` = Rx·Ry·Rz，与骨骼的 Rz·Ry·Rx **相反**
  * `itemRenderTranslations` 抓在 GeckoLib 半格微调**之前**，所以微调要靠 GECKO_* 单独补
  * 开镜时 `GunPose` 只剩平移（hip 旋转按 k=1−aim 归零），但 **display 的那 2°/4° 还在**
    —— 它绕在姿态外侧，`GunPose` 归零的是它自己那一份，所以瞄具线并不与视轴平行。
    本脚本据此算出"要抵消的旋转"与"要补的平移"。
"""

import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
A = "src/main/resources/assets/apocalypse_zombies"

# GeckoLib 的半格微调（GeoItemRenderer.preRender，抓矩阵之后）
GECKO = (0.5, 0.51, 0.5)
# ItemRenderer 在 display 之后又平移了 −0.5：两者在本模型空间里几乎相消，只剩 +0.01
VANILLA_CENTER = (-0.5, -0.5, -0.5)
# 屏幕宽高比（NDC 的横向边缘在这里；纵向边缘恒为 ±1）
ASPECT = 16.0 / 9.0

GUNS = {
    "m1": {
        "label": "M1 加兰德（机械瞄具）",
        "java": "src/main/java/com/apocalypse/zombies/item/M1GarandItem.java",
        "model": f"{A}/models/item/m1_garand.json",
        "geo": f"{A}/geo/m1_garand.geo.json",
        # geo 空间（px）里瞄具线的两个点；下面有断言，模型改了会对不上而不是静默算错
        "rear": (0.0, 2.80, -1.67),     # 后照门孔心（body 上的环）
        "front": (0.0, 2.80, -12.72),   # 前准星刃顶（barrel，该方块顶面 = 2.80）
        "anchor_checks": [
            # (期望值, 实测值取法) —— 用来确认上面的锚点仍然对应几何
            ("rear_aperture_center_y", 2.80, 0.05),
            ("front_post_top_y", 2.80, 0.05),
        ],
    },
    "uzi": {
        "label": "Uzi（机械瞄具）",
        "java": "src/main/java/com/apocalypse/zombies/item/UziItem.java",
        "model": f"{A}/models/item/uzi.json",
        "geo": f"{A}/geo/uzi.geo.json",
        # geo 空间（px）瞄具线两点。两端同高 3.26 → 瞄具线与枪膛平行；此前前柱顶 3.45（穿出自己护环
        # 顶盖 3.26）、孔心 3.08，一高一低差 0.37u 就是那条 2.34° 的斜线。
        "rear": (0.0, 3.26, 4.36),      # 后照门窥孔片中心（sight_rear 内嵌 0.2×0.2 片，3.16–3.36）
        "front": (0.0, 3.26, -4.68),    # 前准星柱顶（sight_front 柱 origin y=2.78 高 0.48）
        "anchor_checks": [
            ("rear_aperture_center_y", 3.26, 0.05),
            ("front_post_top_y", 3.26, 0.05),
        ],
        # 手持落点表格用的参考点（geo px）：握把rest / 枪口
        "grip": (0.0, 0.50, 2.00),
        "muzzle": (0.0, 1.60, -8.90),
    },
    "awm": {
        "label": "AWM（光学瞄具）",
        "java": "src/main/java/com/apocalypse/zombies/item/AWMItem.java",
        "model": f"{A}/models/item/awm.json",
        "geo": f"{A}/geo/awm.geo.json",
        # 镜光轴：y 取 WeaponMount.SCOPE_PIVOT 的 3.15（与 scope 骨骼镜筒环的几何中心 3.15 互校），
        # z 取镜筒两端；轴上的点取哪两个都不影响结论（只要共线）
        "rear": (0.0, 3.15, -0.60),
        "front": (0.0, 3.15, -5.70),
        "anchors": ("sight", "scope"),   # 参考：镜光轴
        "scope_bone": "scope",
        "anchor_checks": [("scope_axis_y", 3.15, 0.05)],
    },
}


# --------------------------------------------------------------------------- 仿射
def T(v):
    return (((1, 0, 0), (0, 1, 0), (0, 0, 1)), tuple(float(x) for x in v))


def S(k):
    return (((k, 0, 0), (0, k, 0), (0, 0, k)), (0.0, 0.0, 0.0))


def Rx(d):
    c, s = math.cos(math.radians(d)), math.sin(math.radians(d))
    return (((1, 0, 0), (0, c, -s), (0, s, c)), (0.0, 0.0, 0.0))


def Ry(d):
    c, s = math.cos(math.radians(d)), math.sin(math.radians(d))
    return (((c, 0, s), (0, 1, 0), (-s, 0, c)), (0.0, 0.0, 0.0))


def Rz(d):
    c, s = math.cos(math.radians(d)), math.sin(math.radians(d))
    return (((c, -s, 0), (s, c, 0), (0, 0, 1)), (0.0, 0.0, 0.0))


def mul(a, b):
    (ar, at), (br, bt) = a, b
    r = tuple(tuple(sum(ar[i][k] * br[k][j] for k in range(3)) for j in range(3)) for i in range(3))
    t = tuple(sum(ar[i][k] * bt[k] for k in range(3)) + at[i] for i in range(3))
    return (r, t)


def apply(m, p):
    r, t = m
    return tuple(sum(r[i][k] * p[k] for k in range(3)) + t[i] for i in range(3))


# --------------------------------------------------------------------------- 读常量
def java_const(path, name, default=None):
    text = Path(ROOT, path).read_text(encoding="utf-8", errors="replace")
    m = re.search(r"\b" + name + r"\s*=\s*(-?\d+(?:\.\d+)?)F?\s*;", text)
    return float(m.group(1)) if m else default


def pose_consts():
    p = "src/main/java/com/apocalypse/zombies/client/weapon/GunPose.java"
    return {k: java_const(p, k) for k in
            ("HIP_YAW", "HIP_PITCH", "HIP_ROLL", "HIP_DX", "HIP_DY", "HIP_DZ",
             "MODEL_FOV_AIM", "MODEL_FOV_HIP")}


def gun_consts(cfg):
    c = {
        "FIRST_PERSON_SCALE": java_const(cfg["java"], "FIRST_PERSON_SCALE", 1.0),
        "ADS_X": java_const(cfg["java"], "ADS_X", 0.0),
        "ADS_Y": java_const(cfg["java"], "ADS_Y", 0.0),
        "ADS_Z": java_const(cfg["java"], "ADS_Z", 0.0),
        "AIMED_FOV": java_const(cfg["java"], "AIMED_FOV", 70.0),
    }
    disp = json.loads(Path(ROOT, cfg["model"]).read_text(encoding="utf-8"))
    fp = disp["display"]["firstperson_righthand"]
    c["disp_rot"] = fp["rotation"]
    c["disp_trans"] = [x / 16.0 for x in fp["translation"]]   # ItemTransform.Deserializer: ×0.0625
    c["disp_scale"] = fp["scale"][0]
    return c


# --------------------------------------------------------------------------- 链条
def display_matrix(c):
    """T(trans/16) · Rxyz(rot) · S(scale)"""
    m = mul(T(c["disp_trans"]), Rx(c["disp_rot"][0]))
    m = mul(m, Ry(c["disp_rot"][1]))
    m = mul(m, Rz(c["disp_rot"][2]))
    return mul(m, S(c["disp_scale"]))


def stance_matrix(g, aim, ads=(0.0, 0.0, 0.0), aim_rot=True):
    """GunPose.matrix：Rz(roll·a) · T(hip·k + ads·a) · R_hip(k) · R_fire · R_aim(a)

    最后一项是本脚本引入的**抵消旋转**（见文件头）：display 的 Rx·Ry 绕在姿态外侧，
    只把 hip 归零并不能让瞄具线与视轴平行，必须在最内侧乘上 R_disp⁻¹。
    """
    a, k = aim, 1.0 - aim
    m = T((g["HIP_DX"] * k + ads[0] * a, g["HIP_DY"] * k + ads[1] * a, g["HIP_DZ"] * k + ads[2] * a))
    # JOML Quaternionf.rotateXYZ(pitch, yaw, roll)（小角，两种结合次序的差是二阶量）
    hip = mul(Rx(-g["HIP_PITCH"] * k), Ry(-g["HIP_YAW"] * k))
    hip = mul(hip, Rz(-g["HIP_ROLL"] * k))
    m = mul(m, hip)
    if aim_rot:
        # R_disp⁻¹ = Ry(−yaw)·Rx(−pitch)，按 aim 渐入
        d = mul(Ry(-g_disp_rot[1] * a), Rx(-g_disp_rot[0] * a))
        m = mul(m, d)
    return m


g_disp_rot = (0.0, 0.0)


def camera_point(px, c, g, aim, ads=(0.0, 0.0, 0.0), include_display=True, aim_rot=True):
    """模型 px → 相机空间（格）。"""
    local = (px[0] / 16.0 + VANILLA_CENTER[0] + GECKO[0],
             px[1] / 16.0 + VANILLA_CENTER[1] + GECKO[1],
             px[2] / 16.0 + VANILLA_CENTER[2] + GECKO[2])
    p = local
    if include_display:
        p = apply(display_matrix(c), p)
    p = apply(stance_matrix(g, aim, ads, aim_rot), p)
    s = c["FIRST_PERSON_SCALE"]
    p = tuple(v * s for v in p)
    return (p[0] + 0.56, p[1] - 0.52, p[2] - 0.72)


def ndc(p, fov):
    """相机空间点 → 屏幕 NDC（x 右 / y 上，±1 为边缘）。透视投影，忽略宽高比。"""
    z = -p[2]
    if z <= 1e-4:
        return None
    half = math.tan(math.radians(fov / 2.0)) * z
    return (p[0] / half, p[1] / half)


def dir_from(p_from, p_to):
    d = tuple(p_to[i] - p_from[i] for i in range(3))
    n = math.sqrt(sum(v * v for v in d)) or 1.0
    return tuple(v / n for v in d)


def angle_off_axis(front, rear):
    """瞄具线相对视轴(−Z)的夹角（度）。0 = 完全平行，开镜时两个瞄具才会重合。"""
    d = dir_from(rear, front)
    cos = max(-1.0, min(1.0, -d[2]))
    return math.degrees(math.acos(cos)), d


# --------------------------------------------------------------------------- 主流程
def analyze(key):
    cfg = GUNS[key]
    g = pose_consts()
    c = gun_consts(cfg)
    global g_disp_rot
    g_disp_rot = c["disp_rot"]

    print("=" * 78)
    print(f"{cfg['label']}")
    print("=" * 78)
    print(f"  display.firstperson_righthand : rot={c['disp_rot']} trans={c['disp_trans']} "
          f"(原始 { [round(x,3) for x in c['disp_trans']] } 格) scale={c['disp_scale']}")
    print(f"  FIRST_PERSON_SCALE={c['FIRST_PERSON_SCALE']}  当前 ADS=({c['ADS_X']}, {c['ADS_Y']}, {c['ADS_Z']})")
    print(f"  hip: yaw={g['HIP_YAW']} pitch={g['HIP_PITCH']} roll={g['HIP_ROLL']} "
          f"d=({g['HIP_DX']}, {g['HIP_DY']}, {g['HIP_DZ']})")

    if not cfg["rear"] or not cfg["front"]:
        print("\n  ⚠ 未填瞄具锚点，先跑 --probe 打印候选")
        return

    rear, front = cfg["rear"], cfg["front"]

    # --- 校验锚点仍对应几何（该 z 处**存在**匹配的立方体即可，不能只看第一个）
    geo = json.loads(Path(ROOT, cfg["geo"]).read_text(encoding="utf-8"))["minecraft:geometry"][0]
    if cfg.get("scope_bone"):
        # 光学瞄具：镜筒是环片段（每片是薄条），轴线在**包络中心**而不是某个方块的中心
        seg = [(o[1], o[1] + sz[1]) for b in geo["bones"] if b["name"] == cfg["scope_bone"]
               for c in b.get("cubes", []) if (o := c.get("origin")) and (sz := c.get("size"))
               and abs(o[0] + sz[0] / 2.0) < 0.02]
        if seg:
            lo_y, hi_y = min(s[0] for s in seg), max(s[1] for s in seg)
            axis = (lo_y + hi_y) / 2.0
            if abs(axis - front[1]) > 0.06:
                print(f"  ⚠ 镜轴锚点 y={front[1]:.2f} 与 {cfg['scope_bone']} 骨环包络中心 {axis:.2f} 不符")
            else:
                print(f"  · 镜轴自检：{cfg['scope_bone']} 骨环包络 {lo_y:.3f}..{hi_y:.3f} → 轴心 "
                      f"{axis:.3f} ✓（锚点 {front[1]:.2f}）")
    else:
        for tag, anchor, picker in (
                ("后照门孔心", rear, lambda o, sz: o[1] + sz[1] / 2.0),
                ("前准星", front, lambda o, sz: o[1] + sz[1] / 2.0)):
            found, cand = False, []
            for b in geo["bones"]:
                for cube in b.get("cubes", []):
                    o, sz = cube.get("origin"), cube.get("size")
                    if not o or not sz:
                        continue
                    if abs(o[0] + sz[0] / 2.0 - anchor[0]) > 0.02:
                        continue
                    if abs(o[2] + sz[2] / 2.0 - anchor[2]) > 0.35:
                        continue
                    y = picker(o, sz)
                    cand.append((y, o[1], o[1] + sz[1]))
                    if tag.startswith("后照门") and abs(y - anchor[1]) < 0.05:
                        found = True
                    if tag.startswith("前准星") and abs(o[1] + sz[1] - anchor[1]) < 0.05:
                        found = True          # 刃顶
            if not found:
                print(f"  ⚠ {tag} 锚点 y={anchor[1]:.2f} 在该 z 处没有匹配的几何："
                      f"{[f'{y:.2f}' for y, _, _ in cand][:8]} —— 模型改过，请重填锚点")

    print("\n  --- 手持（aim=0）在屏幕上的位置（NDC，右缘 %+.2f / 下缘 −1.00）---" % ASPECT)
    grip_pt = cfg.get("grip", (0.0, 1.30, 0.60))
    muzzle_pt = cfg.get("muzzle", (0.0, 2.30, -13.60))
    for name, px in (("握把/原点", grip_pt), ("后照门孔心", rear), ("枪口", muzzle_pt)):
        p = camera_point(px, c, g, 0.0)
        n = ndc(p, g["MODEL_FOV_HIP"])
        inside = abs(n[1]) <= 1.0 and abs(n[0]) <= ASPECT
        print(f"    {name:12} 相机=({p[0]:+.3f}, {p[1]:+.3f}, {p[2]:+.3f}) 格   "
              f"NDC=({n[0]:+.3f}, {n[1]:+.3f}){'' if inside else '  ← 出画'}")

    print("\n  --- 开镜（aim=1）瞄具线 ---")
    for tag, aim_rot in (("现状(只归零 hip 旋转)", False), ("抵消 display 旋转后", True)):
        pr = camera_point(rear, c, g, 1.0, aim_rot=aim_rot)
        pf = camera_point(front, c, g, 1.0, aim_rot=aim_rot)
        deg, d = angle_off_axis(pf, pr)
        print(f"    {tag}:")
        print(f"      后照门=({pr[0]:+.3f},{pr[1]:+.3f},{pr[2]:+.3f})  前准星=({pf[0]:+.3f},{pf[1]:+.3f},{pf[2]:+.3f})")
        print(f"      瞄具线与视轴夹角 = {deg:.2f}°  （方向 {tuple(round(v,4) for v in d)}）")

    # --- 需要补的平移（在抵消旋转之后才有意义）
    p0 = camera_point(rear, c, g, 1.0, aim_rot=True)
    s = c["FIRST_PERSON_SCALE"]
    need = (-p0[0] / s, -p0[1] / s)
    print(f"\n  --- 结论 ---")
    print(f"    要抵消的 display 旋转 = Ry({-c['disp_rot'][1]:+}) · Rx({-c['disp_rot'][0]:+}) 度"
          f"  → GunItem.adsPitch()={c['disp_rot'][0]} / adsYaw()={c['disp_rot'][1]}")
    print(f"    需要 ADS_X = {need[0]:+.4f}   ADS_Y = {need[1]:+.4f}   （Java 现值 {c['ADS_X']:+.2f} / {c['ADS_Y']:+.2f}）")
    dx_err, dy_err = need[0] - c["ADS_X"], need[1] - c["ADS_Y"]
    if abs(dx_err) <= 0.001 and abs(dy_err) <= 0.001:
        print(f"    ✓ Java 常量与量算一致（残差 {dx_err:+.4f} / {dy_err:+.4f} 格）")
    else:
        print(f"    ✗ Java 常量与量算不符（差 {dx_err:+.4f} / {dy_err:+.4f} 格）—— 请把上面两个数写回")
    # 现状误差：用当前常量、不做旋转抵消
    pc = camera_point(rear, c, g, 1.0, ads=(c["ADS_X"], c["ADS_Y"], c["ADS_Z"]), aim_rot=False)
    deg_c = math.degrees(math.atan2(math.hypot(pc[0], pc[1]), -pc[2]))
    print(f"    现状下瞄具线离视轴的角距 = {deg_c:.2f}°（屏幕 FOV {g['MODEL_FOV_AIM']:.0f}° 时，"
          f"约为屏幕半高的 {deg_c / (g['MODEL_FOV_AIM'] / 2):.0%}）")
    print(f"    现状下瞄具线离视轴的垂直距离 = {math.hypot(pc[0], pc[1]):.3f} 格（≈ {math.hypot(pc[0], pc[1]) * 16:.1f} 模型 px）")

    # --- 手持建议：把枪往中间/往上挪多少
    print("\n  --- 手持落点（HIP_DX/HIP_DY）：NDC，画面右缘 = %+.2f、下缘 = −1.00 ---" % ASPECT)
    print(f"    {'HIP_DX':>7} {'HIP_DY':>7} | {'握把':>16} | {'后照门':>16}")
    for dx, dy in ((g["HIP_DX"], g["HIP_DY"]), (-0.06, 0.04), (-0.10, 0.06),
                   (-0.12, 0.07), (-0.14, 0.08), (-0.18, 0.08)):
        g2 = dict(g)
        g2["HIP_DX"], g2["HIP_DY"] = dx, dy
        pg = camera_point(grip_pt, c, g2, 0.0)
        pr = camera_point(rear, c, g2, 0.0)
        ng, nr = ndc(pg, g["MODEL_FOV_HIP"]), ndc(pr, g["MODEL_FOV_HIP"])
        tag = "  ← 当前" if (abs(dx - g["HIP_DX"]) < 1e-9 and abs(dy - g["HIP_DY"]) < 1e-9) else ""
        print(f"    {dx:+7.2f} {dy:+7.2f} | ({ng[0]:+.3f},{ng[1]:+.3f}) | "
              f"({nr[0]:+.3f},{nr[1]:+.3f}){tag}")


def probe(key):
    cfg = GUNS[key]
    geo = json.loads(Path(ROOT, cfg["geo"]).read_text(encoding="utf-8"))["minecraft:geometry"][0]
    print(f"=== {key} 的瞄具候选（x≈0、朝 −Z 的细长件）===")
    for b in geo["bones"]:
        hits = []
        for cube in b.get("cubes", []):
            o, sz = cube.get("origin"), cube.get("size")
            if not o or not sz:
                continue
            if abs(o[0] + sz[0] / 2.0) > 0.6:
                continue
            if sz[2] > 2.0 and sz[1] < 1.5:      # 沿 Z 长、不太厚
                hits.append((o[1], o[1] + sz[1], o[2] + sz[2] / 2.0, sz))
        if hits:
            print(f"  bone {b['name']}:")
            for y0, y1, zc, sz in sorted(hits, key=lambda h: h[2]):
                print(f"    y={y0:6.3f}..{y1:6.3f} (顶 {y1:6.3f})  z中心={zc:7.3f}  size={sz}")


def main():
    args = sys.argv[1:]
    keys = [k for k in GUNS if k in args] or ["m1", "awm"]
    for k in keys:
        if "--probe" in args:
            probe(k)
        else:
            analyze(k)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
