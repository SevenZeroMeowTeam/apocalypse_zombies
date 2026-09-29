"""相位包络的**效果对比器**：把"包络前"与"包络后"两份 animation.json 比一遍。

量什么：对一个布料链，子段的观感由两件事决定 ——
1. **峰值**：末段摆得开不开（包络的 `amp` 段）；
2. **收招残尾**：主体已经回零、子段还挂着多少（包络的 `rest` 段要把它压下去）。
   算法：在主体幅度 < 峰值 10% 的那些采样点里，取子段绝对值的平均。

用法：python tools/bride_env_report.py [基线 animation.json] [新 animation.json]
"""
import json
import sys
from collections import defaultdict

CHAINS = {
    "veil": ["veil", "veil2", "veil3", "veil4"],
    "hair_fall": ["hair_fall", "hair_fall2", "hair_fall3"],
    "hair_side": ["hair_side_l", "hair_side_l2"],
    "train": ["train", "train2"],
    "skirt": ["skirt", "skirt2", "skirt3"],
    "hem_r": ["hem_r", "hem_r2", "hem_r3"],
    "hem_l": ["hem_l", "hem_l2", "hem_l3"],
}
N = 60      # 每个剪辑等距采样点数


def vec(v):
    return v["post"]["vector"] if isinstance(v, dict) else v


def ser(ks, i=0):
    return sorted((float(t), vec(v)[i]) for t, v in ks.items())


def interp(kv, t):
    if not kv:
        return 0.0
    if t <= kv[0][0]:
        return kv[0][1]
    if t >= kv[-1][0]:
        return kv[-1][1]
    for (t0, v0), (t1, v1) in zip(kv, kv[1:]):
        if t0 <= t <= t1:
            f = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return v0 + (v1 - v0) * f
    return 0.0


def measure(clipd, bones):
    """返回 (末段峰值, 归零相位)。

    归零相位 = 末段**最后一次**超过自己峰值 10% 的时刻 / 剪辑长度。
    这个量对整体幅度是**不变的**（全段等比放大不会改变它），所以它只反映"时序"：
    包络把收招段压下去时，末段会更早跌出 10% ⇒ 相位变小 = 收招提前归零。

    （早期版本用「主体安静窗口内的平均|末段|」当指标，它会同时被"摆得更大"污染，
    峰值一升它就跟着升，读数完全读不出收招时序 —— 指标必须对幅度不变才能只看时序。）
    """
    sub = ser(clipd["bones"][bones[-1]]["rotation"])
    if not sub:
        return 0.0, 0.0
    L = float(clipd["animation_length"])
    pk = max(abs(v) for _, v in sub)
    if pk < 1e-9:
        return 0.0, 0.0
    last = 0.0
    for f in range(240 + 1):
        t = L * f / 240
        if abs(interp(sub, t)) > 0.10 * pk:
            last = t
    return pk, last / L


def main():
    a = sys.argv[1] if len(sys.argv) > 1 else "art/bride/_bak_118/bride_zombie.animation.json"
    b = sys.argv[2] if len(sys.argv) > 2 else "art/bride/bride_zombie.animation.json"
    old = json.load(open(a, encoding="utf-8"))["animations"]
    new = json.load(open(b, encoding="utf-8"))["animations"]

    print("相位包络前后（x 轴）：末段峰值 ↑ = 甩得更开；归零相位 ↓ = 收招提前归零")
    print(f'{"剪辑":20s}{"链":11s}{"末段峰值 前→后":>19s}{"归零相位 前→后":>19s}')
    tot = defaultdict(float)
    for clip, cv in sorted(new.items()):
        if cv.get("loop"):
            continue
        for cname, bones in CHAINS.items():
            if bones[-1] not in cv.get("bones", {}) or bones[-1] not in old.get(clip, {}).get("bones", {}):
                continue
            if max((abs(v) for _, v in ser(cv["bones"][bones[0]]["rotation"])), default=0.0) < 0.01:
                continue
            p0, t0 = measure(old[clip], bones)
            p1, t1 = measure(new[clip], bones)
            print(f'{clip:20s}{cname:11s}{p0:7.2f} →{p1:7.2f}{"":4s}{t0:7.3f} →{t1:7.3f}')
            for k, v in (("p0", p0), ("p1", p1), ("t0", t0), ("t1", t1)):
                tot[k] += v
    print(f'{"合计":20s}{"":11s}{tot["p0"]:7.2f} →{tot["p1"]:7.2f}{"":4s}'
          f'{tot["t0"]:7.3f} →{tot["t1"]:7.3f}')
    loops = [c for c, v in new.items() if v.get("loop")]
    # 注意：不能拿整个循环剪辑比。**包络**不碰循环剪辑（`penv = None if c.loop`），
    # 但生成器修掉「按轴分别写键时缺轴填 0」后，循环剪辑里其它骨的值也会被修正
    # （那些是**刻意**的值修复，不是包络泄漏）。所以这里只核"子段在包络维度没被碰"：
    # 循环剪辑里所有骨的**键时刻集合**必须与包络前逐位一致。
    def keytimes(d):
        return {b: sorted(float(k) for k in cv.get("rotation", {}))
                for b, cv in (d.get("bones") or {}).items()}
    same = all(keytimes(old.get(c) or {}) == keytimes(new.get(c) or {}) for c in loops)
    print(f"循环剪辑 {loops} 键时刻未动（包络不碰循环）: {same}")
    # 值层面的差异只允许出现在"旧值为 0（缺轴填 0 的坑）且新值≠0"的点上
    drift = []
    for c in loops:
        ob, nb = (old.get(c) or {}).get("bones", {}), (new.get(c) or {}).get("bones", {})
        for b in set(ob) | set(nb):
            for i in range(3):      # ser(ks, i) 给的是第 i 个分量的一维序列
                o = dict(ser(ob.get(b, {}).get("rotation", {}), i))
                n = dict(ser(nb.get(b, {}).get("rotation", {}), i))
                for t in set(o) & set(n):
                    if abs(o[t] - n[t]) > 1e-6:
                        drift.append((c, b, t, i, o[t], n[t]))
    bad = [d for d in drift if not (abs(d[4]) < 1e-9 and abs(d[5]) > 1e-9)]
    print(f"循环剪辑值差异 {len(drift)} 处，其中非「缺轴填 0」修复 {len(bad)} 处")
    print("结论:", "包络生效（峰值↑且残尾↓）"
          if tot["p1"] > tot["p0"] and tot["t1"] < tot["t0"] else "**未达预期，查 amp/rest**")


if __name__ == "__main__":
    main()
