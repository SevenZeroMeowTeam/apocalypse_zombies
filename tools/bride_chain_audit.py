"""布料链的**曲线层面**审计（纯标准库）。

包络/滞后包络改造动的是动画曲线，不再是几何 —— 所以验收也得换到曲线维度。这里查五条：

A. 收招归零：非循环剪辑里，每条链的**根段与子段**在 t=0 与 t=length 处三轴必须**恰好 0**
   （铁律：技能剪辑收招时布料必须回中位，否则残摆留在下一帧）。
B. 循环首尾等值：循环剪辑（idle/walk）里每个链通道在 0 与 length 处数值必须**逐位相等**。
C. 键序单调且有最小键距：滞后映射可能把键压缩到一起甚至**倒挂**（先归零再跳回 = 抽搐）。
   逐键核 `t` 严格递增，并报告最小键距（历史故障：4ms）。
D. 左右镜像：`hair_side_l*` vs `hair_side_r*`、`hem_l*` vs `hem_r*` 必须互为镜像
   （镜像 = 绕 x 轴转同号、绕 y/z 反号，即 `(x,-y,-z)`；`(-x,y,z)` 一并算出来做对照）。
E. 链确实接上了：非循环剪辑里子段的**键时刻**必须与根段不同（滞后 > 0 的直接证据），
   否则说明那条链根本没走到 `chain_oneshot`（静默跳过）。

判据自测（改判据后必跑）：把当前动画复制一份、往某条链子段注入一个"8ms 后、值 0°"的伪键，
用 `BRIDE_ANIM=<副本> python tools/bride_chain_audit.py <clip>` 复跑 —— C 必须报出速度尖峰、
D 必须报出单侧镜像偏差。实测：C 报 `16.0×中位（Δt=8ms, Δv=2.15°）`、D 报 `2.162°`。
**C 项不要写成"键距 < 15ms 就报"**：三轴时间取并集后会自然出现 4ms 级的插值伪键（Δv≈0），
那种一律是误报；真故障是"键距极小而 Δv 很大"。

用法：
    python tools/bride_chain_audit.py            # 全部
    python tools/bride_chain_audit.py skill_veil_snare
"""
import json
import sys

import os
ANIM = os.environ.get("BRIDE_ANIM", "art/bride/bride_zombie.animation.json")
CHAINS = {
    "veil": ["veil", "veil2", "veil3", "veil4"],
    "hair_fall": ["hair_fall", "hair_fall2", "hair_fall3"],
    "hair_side_l": ["hair_side_l", "hair_side_l2"],
    "hair_side_r": ["hair_side_r", "hair_side_r2"],
    "train": ["train", "train2"],
    "skirt": ["skirt", "skirt2", "skirt3"],
    "hem_l": ["hem_l", "hem_l2", "hem_l3"],
    "hem_r": ["hem_r", "hem_r2", "hem_r3"],
}
PAIRS = [("hair_side_l", "hair_side_r"), ("hem_l", "hem_r")]
TOL_ZERO = 1e-6
TOL_GAP = 0.015


def rot(ch):
    """通道 → {t: [x,y,z]}（只取 rotation）。"""
    out = {}
    for t, v in (ch or {}).get("rotation", {}).items():
        vec = v["post"]["vector"] if isinstance(v, dict) else v
        out[float(t)] = [float(x) for x in vec]
    return out


def at(ks, t):
    ts = sorted(ks)
    if not ts:
        return [0.0, 0.0, 0.0]
    if t <= ts[0]:
        return ks[ts[0]]
    if t >= ts[-1]:
        return ks[ts[-1]]
    for a, b in zip(ts, ts[1:]):
        if a <= t <= b:
            f = 0.0 if b == a else (t - a) / (b - a)
            return [ks[a][i] + (ks[b][i] - ks[a][i]) * f for i in range(3)]
    return [0.0, 0.0, 0.0]


def main():
    want = sys.argv[1:]
    anim = json.load(open(ANIM, encoding="utf-8"))["animations"]
    bad = {"A": [], "B": [], "C": [], "D": [], "E": []}
    gaplo = (9e9, None)
    for clip, clipd in anim.items():
        if want and clip not in want:
            continue
        L = float(clipd["animation_length"])
        loop = bool(clipd.get("loop"))
        bones = clipd.get("bones", {})
        for cname, segs in CHAINS.items():
            present = [s for s in segs if s in bones]
            if not present:
                continue
            # A 收招归零
            if not loop:
                for s in present:
                    ks = rot(bones[s])
                    if not ks:
                        continue
                    for t in (0.0, L):
                        v = at(ks, t)
                        if max(abs(x) for x in v) > TOL_ZERO:
                            bad["A"].append((clip, s, t, [round(x, 3) for x in v]))
            # B 循环首尾等值
            else:
                for s in present:
                    ks = rot(bones[s])
                    if not ks:
                        continue
                    v0, v1 = ks.get(0.0), ks.get(L)
                    if v0 is None or v1 is None:
                        bad["B"].append((clip, s, "缺端点键", None))
                    elif max(abs(v0[i] - v1[i]) for i in range(3)) > 1e-9:
                        bad["B"].append((clip, s, "端点不等", [round(x, 3) for x in (v0 + v1)]))
            # C 键序单调 + **速度尖峰**（键距小本身不是问题：三轴时间取并集后必然出现
            # 4ms 级的插值伪键，其 Δv≈0。真会抽搐的是"键距极小而 Δv 很大"= 速度尖峰，
            # 历史故障 44 对就是这种：中间被插进一个 0，两侧是 20°）。
            for s in present:
                ks = rot(bones[s])
                ts = sorted(ks)
                spd = []
                for a, b in zip(ts, ts[1:]):
                    if b - a <= 1e-9:
                        bad["C"].append((clip, s, "键重复/倒挂", (a, b)))
                        continue
                    dv = max(abs(ks[b][i] - ks[a][i]) for i in range(3))
                    spd.append((dv / (b - a), a, b - a, dv))
                    if b - a < gaplo[0]:
                        gaplo = (b - a, (clip, s, a, b))
                if spd:
                    rates = sorted(x[0] for x in spd)
                    med = rates[len(rates) // 2] or 1e-9
                    for r, a, dt_, dv in spd:
                        if dt_ < 0.03 and r > 5.0 * med and dv > 0.5:
                            bad["C"].append((clip, s, f"速度尖峰 {r/med:.1f}×中位（Δt={dt_*1000:.0f}ms, Δv={dv:.2f}°）", a))
            # E 链接上了（非循环：子段键时刻 ≠ 根段）
            if not loop and len(present) > 1:
                rt = set(rot(bones[present[0]]))
                for s in present[1:]:
                    st = set(rot(bones[s]))
                    if st and st != rt:
                        continue
                    bad["E"].append((clip, s, "子段键时刻与根段完全相同（滞后没生效？）", None))
    # D 左右镜像
    for clip, clipd in anim.items():
        if want and clip not in want:
            continue
        bones = clipd.get("bones", {})
        for lc, rc in PAIRS:
            for i in range(len(CHAINS[lc])):
                ls, rs = CHAINS[lc][i], CHAINS[rc][i]
                if ls not in bones or rs not in bones:
                    continue
                lk, rk = rot(bones[ls]), rot(bones[rs])
                dev_m, dev_alt = 0.0, 0.0
                for t in sorted(set(lk) | set(rk)):
                    lv, rv = at(lk, t), at(rk, t)
                    dev_m = max(dev_m, max(abs(lv[0] - rv[0]), abs(lv[1] + rv[1]), abs(lv[2] + rv[2])))
                    dev_alt = max(dev_alt, max(abs(lv[0] + rv[0]), abs(lv[1] - rv[1]), abs(lv[2] - rv[2])))
                if dev_m > 0.05:
                    bad["D"].append((clip, f"{ls}|{rs}", f"镜像最大偏差 {dev_m:.3f}°（对照 (-x,y,z) 偏差 {dev_alt:.3f}°）", None))
    for k, title in (("A", "A 收招归零"), ("B", "B 循环首尾等值"), ("C", "C 键序单调/键距"),
                     ("D", "D 左右镜像"), ("E", "E 链确实接上")):
        print(f"{title}: {len(bad[k])} 处问题")
        for row in bad[k][:6]:
            print("   ", row)
    print(f"\n全局最小键距 {gaplo[0]:.4f}s  @ {gaplo[1]}")
    n = sum(len(v) for v in bad.values())
    print("审计结论:", "全部通过" if n == 0 else f"**{n} 处待查**")
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main())
