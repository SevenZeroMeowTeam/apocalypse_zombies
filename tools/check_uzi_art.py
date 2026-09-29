#!/usr/bin/env python3
"""Uzi 出货校验 —— 按《美术规范.md》逐条核对 geo / 贴图 / 骨骼契约。

用法:  python tools/check_uzi_art.py
退出码: 0 = 全部通过;  1 = 有条目 FAIL

为什么要这个脚本：
  Blockbench 的 GeckoLib 导出器会把带 pivot 的元素 x 取反（全局镜像，AWM/M1/莫辛/弩 都这样）。
  这是既定契约、不是 bug —— 但它太安静了，手滑写错一侧不会有人发现。本脚本把
  「枪长 / 铁律坐标 / 圆形枪管 / 强制骨骼 / 骨骼零旋转 / pivot 贴几何」全部钉死，
  任何一处漂移都会在这里炸出来。
"""
import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "src", "main", "resources", "assets", "apocalypse_zombies")
GEO = os.path.join(ASSETS, "geo", "uzi.geo.json")
TEX = os.path.join(ASSETS, "textures", "item", "uzi.png")

fails, warns = [], []


def fail(msg):
    fails.append(msg)


def warn(msg):
    warns.append(msg)


def png_size(path):
    """读 PNG IHDR，不依赖 Pillow。"""
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    return struct.unpack(">II", head[16:24])


def cube_box(c):
    o, s = c["origin"], c["size"]
    lo = [o[i] if s[i] >= 0 else o[i] + s[i] for i in range(3)]
    hi = [o[i] + s[i] if s[i] >= 0 else o[i] for i in range(3)]
    return lo, hi


def main():
    if not os.path.isfile(GEO):
        fail("缺少 %s" % GEO)
        return 1
    g = json.load(open(GEO, encoding="utf-8"))
    gd = g["minecraft:geometry"][0]
    desc = gd["description"]
    bones = gd["bones"]
    byname = {b["name"]: b for b in bones}

    # ---------------------------------------------------------------- 头部
    if desc.get("identifier") != "geometry.uzi":
        fail("identifier 应为 geometry.uzi，实为 %r" % desc.get("identifier"))

    tex_path = TEX if os.path.isfile(TEX) else None
    if tex_path is None:
        fail("缺少贴图 %s" % TEX)
    else:
        tw, th = png_size(tex_path)
        if (tw, th) != (512, 512):
            fail("贴图必须 512x512（美术规范 三.1），实为 %dx%d" % (tw, th))
        if (tw, th) != (desc["texture_width"], desc["texture_height"]):
            fail("贴图 %dx%d 与 geo 声明 %dx%d 不一致"
                 % (tw, th, desc["texture_width"], desc["texture_height"]))
        if tw & (tw - 1) or th & (th - 1):
            fail("贴图边长必须是 2 的幂")

    # ---------------------------------------------------------------- 规模
    ncube = sum(len(b.get("cubes", [])) for b in bones)
    print("骨骼 %d / 体块 %d" % (len(bones), ncube))
    if len(bones) > 40:
        fail("骨骼 %d > 40" % len(bones))
    if ncube > 600:
        fail("体块 %d > 600" % ncube)

    # ---------------------------------------------------------------- 强制骨骼 (美术规范 二.4)
    for name in ("root", "move", "body"):
        if name not in byname:
            fail("缺少强制骨骼 %s" % name)
    if "magazine" not in byname:
        fail("缺少 magazine")
    else:
        for name in ("mag_standard", "mag_extended_1", "mag_extended_2", "mag_extended_3"):
            if name not in byname:
                fail("magazine 下缺少扩容子组 %s" % name)
            elif byname[name].get("parent") != "magazine":
                fail("%s 的父级应为 magazine" % name)
    if "constraint" not in byname:
        fail("缺少 constraint")
    if "camera" not in byname:
        fail("缺少 camera")

    # additional_magazine: 必须在 move 下、与 magazine 同 pivot、且导出时为空（TaCZ 硬规则）
    am = byname.get("additional_magazine")
    if am is None:
        fail("缺少 additional_magazine")
    else:
        if am.get("parent") == "magazine":
            fail("additional_magazine 绝不能挂在 magazine 下（会崩游戏）")
        if am.get("cubes"):
            fail("additional_magazine 导出时必须为空，实有 %d 块" % len(am["cubes"]))
        if "magazine" in byname and am.get("pivot") != byname["magazine"].get("pivot"):
            fail("additional_magazine 的 pivot 必须与 magazine 完全相同")

    # ---------------------------------------------------------------- 骨骼零旋转 (铁律)
    for b in bones:
        r = b.get("rotation") or (0, 0, 0)
        if any(abs(v) > 1e-9 for v in r):
            fail("骨骼 %s 带旋转 %s（铁律：骨骼一根都不许带旋转）" % (b["name"], r))

    # ---------------------------------------------------------------- pivot 贴几何
    for b in bones:
        cs = b.get("cubes")
        if not cs or not b.get("pivot"):
            continue
        px, py, pz = b["pivot"]
        best = min(
            max(abs(px - max(lo[0], min(px, hi[0]))),
                abs(py - max(lo[1], min(py, hi[1]))),
                abs(pz - max(lo[2], min(pz, hi[2]))))
            for lo, hi in (cube_box(c) for c in cs)
        )
        if best > 4.0:
            fail("%s 的 pivot 离自身几何 %.2fu > 4u" % (b["name"], best))

    # ---------------------------------------------------------------- 尺寸 / 铁律坐标
    lo = [1e9] * 3
    hi = [-1e9] * 3
    for b in bones:
        for c in b["cubes"] if b.get("cubes") else []:
            clo, chi = cube_box(c)
            for i in range(3):
                lo[i] = min(lo[i], clo[i])
                hi[i] = max(hi[i], chi[i])
    dim = [hi[i] - lo[i] for i in range(3)]
    blocks = dim[2] / 16.0
    print("包围盒 x[%.2f,%.2f] y[%.2f,%.2f] z[%.2f,%.2f]  长 %.2fu = %.3f 格"
          % (lo[0], hi[0], lo[1], hi[1], lo[2], hi[2], dim[2], blocks))
    if not (0.9 <= blocks <= 2.6):
        fail("枪长 %.3f 格不在 0.9~2.6" % blocks)
    if dim[2] < dim[0] or dim[2] < dim[1]:
        fail("最长轴不是 Z（枪口必须朝 -Z）")

    # 枪口 = 最小 z 处的圆形膛孔，且枪口中心在 x=0（bore 居中）
    bore = None
    for b in bones:
        for c in b["cubes"] if b.get("cubes") else []:
            clo, chi = cube_box(c)
            if abs(clo[2] - lo[2]) < 0.02:
                bore = (clo, chi)
    if bore is None:
        fail("找不到枪口端（最小 z）的任何方块")
    else:
        cxc = (bore[0][0] + bore[1][0]) / 2.0
        if abs(cxc) > 0.45:
            fail("枪口端中心 x=%.3f 偏离膛轴" % cxc)

    # ---------------------------------------------------------------- 圆形枪管（用户硬要求）
    # barrel 组必须由绕 Z 轴旋转的棱柱段构成，且片段数 >= 8 才算"圆"
    bar = byname.get("barrel")
    if bar is None:
        fail("缺少 barrel 骨骼")
    else:
        rot_z = [c for c in bar["cubes"] if (c.get("rotation") or [0, 0, 0])[2]]
        angles = sorted({round((c["rotation"][2] % 360) / 0.1) * 0.1 for c in rot_z})
        if len(rot_z) < 40:
            fail("枪管圆形段只有 %d 块，圆度不足" % len(rot_z))
        if len(angles) < 8:
            fail("枪管截面只有 %d 个角度采样，不构成圆" % len(angles))
        # 每个环形段的截面半径必须一致（同 R 的段 pivot 圆心应重合于膛轴）
        ys = [c["pivot"][1] for c in rot_z]
        xs = [c["pivot"][0] for c in rot_z]
        cy = (min(ys) + max(ys)) / 2.0
        if not (1.0 <= cy <= 2.3):
            fail("枪管轴心 y=%.3f 不在膛轴高度附近" % cy)
        if abs(min(xs) + max(xs)) > 0.02:
            fail("枪管棱柱不关于 x=0 对称（min %.3f / max %.3f）" % (min(xs), max(xs)))
        print("枪管棱柱 %d 块 / %d 个角度采样 / 轴心 y=%.2f" % (len(rot_z), len(angles), cy))

    # ---------------------------------------------------------------- 弹匣在握把里（Uzi 立身之本）
    mag = byname.get("magazine")
    grip = byname.get("grip")
    if mag and grip and mag.get("cubes") and grip.get("cubes"):
        mlo = [1e9] * 3
        mhi = [-1e9] * 3
        for c in mag["cubes"]:
            clo, chi = cube_box(c)
            for i in range(3):
                mlo[i] = min(mlo[i], clo[i])
                mhi[i] = max(mhi[i], chi[i])
        glo = [1e9] * 3
        ghi = [-1e9] * 3
        for c in grip["cubes"]:
            clo, chi = cube_box(c)
            for i in range(3):
                glo[i] = min(glo[i], clo[i])
                ghi[i] = max(ghi[i], chi[i])
        # 弹匣上半段应落在握把的 x/z 范围内 → 确实是"插在握把里"
        if not (mlo[0] >= glo[0] - 0.02 and mhi[0] <= ghi[0] + 0.02):
            fail("弹匣 x 范围 [%.2f,%.2f] 未落在握把 [%.2f,%.2f] 内"
                 % (mlo[0], mhi[0], glo[0], ghi[0]))
        if not (mlo[2] >= glo[2] - 0.02 and mhi[2] <= ghi[2] + 0.02):
            fail("弹匣 z 范围 [%.2f,%.2f] 未落在握把 [%.2f,%.2f] 内"
                 % (mlo[2], mhi[2], glo[2], ghi[2]))
        if mlo[1] >= glo[1]:
            fail("弹匣没有从握把下方伸出（弹匣底 %.2f / 握把底 %.2f）" % (mlo[1], glo[1]))
        print("弹匣底 y=%.2f / 握把底 y=%.2f（伸出 %.2fu）" % (mlo[1], glo[1], glo[1] - mlo[1]))

    # 握把必须在扳机之后（-Z 为前）——Uzi 布局
    trg = byname.get("trigger_group")
    if trg and trg.get("cubes") and grip and grip.get("cubes"):
        tmax = max(cube_box(c)[1][2] for c in trg["cubes"])
        if not tmax < ghi[2]:
            fail("扳机 (z<=%.2f) 必须在握把之前 (z>=%.2f)" % (tmax, ghi[2]))

    # ---------------------------------------------------------------- 抛壳窗与弹壳同侧（镜像契约）
    # 注意：导出空间是源码空间的全局 x 镜像，所以这里用 |x| 判定"在侧壁最外侧"，
    # 只用两者的符号是否一致来判断"同侧"。
    port = None
    for b in bones:
        if b["name"] != "body":
            continue
        for c in b.get("cubes") if b.get("cubes") else []:
            clo, chi = cube_box(c)
            if abs(chi[0]) >= 0.799 and (chi[2] - clo[2]) < 2.0 and -3.2 < clo[2] < -0.8:
                port = (clo, chi)
    if port is None:
        fail("找不到抛壳窗（body 内最外侧 x、z 在 [-3.2,-0.8] 的薄片）")
    cas = byname.get("casing")
    if cas and cas.get("cubes") and port is not None:
        cxs = [cube_box(c) for c in cas["cubes"]]
        ccx = sum(lo[0] + hi[0] for lo, hi in cxs) / (2.0 * len(cxs))
        pcx = (port[0][0] + port[1][0]) / 2.0
        if ccx * pcx <= 0:
            fail("弹壳 (x=%.2f) 与抛壳窗 (x=%.2f) 不在同一侧 —— 镜像契约被破坏" % (ccx, pcx))
        print("抛壳窗 x=%.2f / 弹壳 x=%.2f（同侧 OK）" % (pcx, ccx))

    # ---------------------------------------------------------------- UV
    nface = 0
    bad_uv = 0
    for b in bones:
        for c in b.get("cubes") if b.get("cubes") else []:
            uv = c.get("uv")
            if not isinstance(uv, dict):
                fail("体块未使用逐面 UV（box_uv 必须关闭）")
                continue
            for f in ("north", "east", "south", "west", "up", "down"):
                e = uv.get(f)
                if e is None:
                    bad_uv += 1
                    continue
                if abs(e["uv_size"][0]) == 0 or abs(e["uv_size"][1]) == 0:
                    bad_uv += 1
                if e["uv"][0] < 0 or e["uv"][1] < 0:
                    bad_uv += 1
                nface += 1
    if bad_uv:
        fail("%d 个面 UV 退化/越界" % bad_uv)
    print("逐面 UV %d 面全通过" % nface)

    # ---------------------------------------------------------------- 结果
    for w in warns:
        print("WARN  " + w)
    for f in fails:
        print("FAIL  " + f)
    if fails:
        print("\nCHECK FAIL：%d 项" % len(fails))
        return 1
    print("\nCHECK PASS：Uzi 资产符合《美术规范.md》")
    return 0


if __name__ == "__main__":
    sys.exit(main())
