"""

**基线何时重取**：只要有一处**刻意**的值改动落在裙摆族（含根段）上，基线就会失真 ——
当时（1.1.18）它证明的是"拆链重构"的等价性；1.1.19 加了相位包络并修了缺轴填 0 的坑，
根段的值被**故意**改了（旧值全是被误填的 0），于是重新取基线。这个工具的长期用途是
守住"以后别无意中动到裙摆几何"，不是守住某一版数值。
裙摆改造的**等价性证明器**：把一组 (geo, anim) 里裙摆族所有体块的世界角点算出来，做哈希。

为什么需要它：裙摆拆链的做法是把中/下两层环的板**移到子骨**上。骨骼继承的数学保证
「子骨零旋转时，板的世界位置与原来完全相同」—— 但这要靠**数跑出来**，不能靠推理签字。
于是：改造前跑一次存基线，改造后跑一次比对，**必须逐块逐帧完全一致**。

数学口径（与 bride_pose_probe.py 同）：
- 每根骨绕**自己的 pivot** 旋转；世界旋转 R = R_parent · R_local，世界 pivot 位置
  loc = loc_parent + R_parent · (P - P_parent)。
- 体块顶点 v（模型空间绝对值）的世界位置 = loc + R · (v - P)。
- 静止时 R=I、loc=P ⇒ 顶点原样不动（这就是「换父骨不改外观」的根据）。

用法：
    python tools/bride_skirt_check.py                                # 用当前 geo/anim 跑
    python tools/bride_skirt_check.py --save art/bride/_skirt_base.json
    python tools/bride_skirt_check.py --cmp  art/bride/_skirt_base.json
"""
import ast
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bride_pose_probe import rotm, apply, sample   # 复用同一套变换数学

GEO = "art/bride/bride_zombie.geo.json"
ANIM = "art/bride/bride_zombie.animation.json"
FAMILY = ("skirt", "skirt2", "skirt3", "hem_r", "hem_r2", "hem_r3",
          "hem_l", "hem_l2", "hem_l3", "train", "train2")
SAMPLES = 24      # 每个剪辑等距采样帧数（含首末）


def corners(origin, size):
    x, y, z = origin
    w, h, d = size
    return [[x + (w if i & 1 else 0), y + (h if i & 2 else 0), z + (d if i & 4 else 0)]
            for i in range(8)]


def table(geopath, animpath):
    geo = json.load(open(geopath, encoding="utf-8"))
    anim = json.load(open(animpath, encoding="utf-8"))
    bones = {b["name"]: b for b in geo["minecraft:geometry"][0]["bones"]}
    out = {}
    for clip, clipd in anim["animations"].items():
        rot = {}
        for bn, ch in clipd.get("bones", {}).items():
            r = ch.get("rotation")
            if r:
                rot[bn] = {float(k): (v["post"]["vector"] if isinstance(v, dict) else v)
                           for k, v in r.items()}
        length = float(clipd["animation_length"])

        def world(bn, t, cache):
            if bn in cache:
                return cache[bn]
            b = bones[bn]
            piv = b.get("pivot", [0, 0, 0])
            rr = rot.get(bn)
            R = rotm(*(sample(rr, t) if rr else [0.0, 0.0, 0.0]))
            loc = [float(piv[i]) for i in range(3)]
            par = b.get("parent")
            if par and par in bones:
                PR, PL = world(par, t, cache)
                pp = bones[par].get("pivot", [0, 0, 0])
                d = [piv[i] - pp[i] for i in range(3)]
                loc = [PL[i] + apply(PR, d)[i] for i in range(3)]
                R = [[sum(PR[i][k] * R[k][j] for k in range(3)) for j in range(3)]
                     for i in range(3)]
            cache[bn] = (R, loc)
            return cache[bn]

        for f in range(SAMPLES):
            t = length * f / (SAMPLES - 1)
            cache = {}
            for bn in FAMILY:
                if bn not in bones:
                    continue
                b = bones[bn]
                piv = [float(v) for v in b.get("pivot", [0, 0, 0])]
                R, loc = world(bn, t, cache)
                for ci, c in enumerate(b.get("cubes", [])):
                    # 键里**不能带骨名**：本次改造就是要换父骨。用体块自身的 origin+size 做身份，
                    # 这样"同一块板换了骨"仍然对得上，才能真正证明"位置没动"。
                    ident = f"{clip}|{c['origin']}|{c['size']}"
                    for vi, v in enumerate(corners(c["origin"], c["size"])):
                        d = [v[i] - piv[i] for i in range(3)]
                        wp = [loc[i] + apply(R, d)[i] for i in range(3)]
                        out[f"{ident}|{vi}|{f}"] = [round(q, 4) for q in wp]
    return out


def main():
    args = sys.argv[1:]
    geo, anim = GEO, ANIM
    save = cmp_ = None
    if "--save" in args:
        save = args[args.index("--save") + 1]
    if "--cmp" in args:
        cmp_ = args[args.index("--cmp") + 1]
    if "--geo" in args:
        geo = args[args.index("--geo") + 1]
    if "--anim" in args:
        anim = args[args.index("--anim") + 1]

    cur = table(geo, anim)
    print(f"裙摆族角点表：{len(cur)} 条（剪辑 × 骨 × 体块 × 顶点 × 帧）")
    if save:
        json.dump(cur, open(save, "w", encoding="utf-8"), sort_keys=True)
        print(f"基线已存 -> {save}")
    if cmp_:
        base = json.load(open(cmp_, encoding="utf-8"))
        missing = set(base) - set(cur)
        added = set(cur) - set(base)

        def ring(key):
            """按体块的 y 区间判断它属于哪一层环：上环 9.8~13.2 / 中环 7.6~10.0 / 蕾丝 6.9~7.8。"""
            o = ast.literal_eval(key.split("|")[1])
            s = ast.literal_eval(key.split("|")[2])
            y0, y1 = o[1], o[1] + s[1]      # 顶面 = origin_y + size_y（别把 size[1] 当顶面）
            if y0 >= 9.7 and y1 > 10.1:
                return "上环(根段,应零偏差)"
            if y0 >= 7.5 and y1 > 7.9:
                return "中环(第2段)"
            return "下层/蕾丝(第3段)"

        groups = {}
        for k in set(base) & set(cur):
            d = max(abs(base[k][i] - cur[k][i]) for i in range(3))
            g = groups.setdefault(ring(k), [0.0, 0.0])
            g[0] = max(g[0], d)
            g[1] += d
        print(f"对比 {cmp_}：共同键 {len(set(base) & set(cur))} / "
              f"新增 {len(added)} / 消失 {len(missing)}")
        for g, (mx, tot) in sorted(groups.items()):
            print(f"  {g:22s} 最大偏差 {mx:.6f}u")
        bad = groups.get("上环(根段,应零偏差)", [0.0])[0] > 1e-4
        for g, (mx, tot) in groups.items():
            if g.startswith("上环") and mx > 1e-4:
                bad = True
        if added:
            print("  新增键示例:", sorted(added)[:2])
        if missing:
            print("  消失键示例:", sorted(missing)[:2])
        print("等价性:", "不通过 —— 根段被动了" if bad else
              "通过（根段逐块逐帧零偏差；中/下层偏差=设计滞后）")
        sys.exit(1 if (bad or missing) else 0)


if __name__ == "__main__":
    main()
