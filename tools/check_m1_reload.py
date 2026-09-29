#!/usr/bin/env python3
"""M1 加兰德换弹/拉栓 机构自检 —— 按 US Army ARDEC 手册 §3.2 的真实动作顺序断言。

检查对象：src/main/resources/assets/apocalypse_zombies/animations/m1_garand.animation.json
（导出空间：position -> [-x, y, z]，rotation -> [-x, -y, z]；z 不受翻转影响）

真机顺序（手册原话见 tools/m1_garand_bb_anim.js 头部）：
  ① 先把导气杆手柄拉到底（枪机后退）—— 未空仓时井口被枪机挡死，不拉就无法装卸漏夹
  ② 漏夹压入弹夹井直到卡住
  ③ 松手，枪机被漏夹**自动释放**、自由前冲
  ④ 必要时用右手掌根拍拉机柄后端把枪机拍到位闭锁
配套的合理值：枪机行程必须够越过漏夹末弹底缘（模型受几何限制取 1.10u，见 README 待办）
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ANIM = os.path.normpath(os.path.join(
    HERE, "..", "src", "main", "resources", "assets", "apocalypse_zombies",
    "animations", "m1_garand.animation.json"))

BOLT_REAR = 1.10          # 枪机后退位（模型几何上限）
TOL = 0.02


def channel(anim, bone, chan):
    """返回 [(t, [x,y,z]), ...]，静态缩写也算一个点。"""
    ch = anim["bones"].get(bone, {}).get(chan)
    if not ch:
        return []
    if "vector" in ch:
        return [(0.0, ch["vector"])]
    out = []
    for t, ent in ch.items():
        v = (ent.get("post") or ent.get("pre") or ent)["vector"]
        out.append((float(t), v))
    return sorted(out, key=lambda kv: kv[0])


def value_at(points, t):
    """线性取值（足够做顺序断言）。"""
    if not points:
        return None
    prev = points[0]
    for pt in points:
        if pt[0] >= t:
            if pt[0] == prev[0]:
                return pt[1]
            k = (t - prev[0]) / (pt[0] - prev[0])
            return [prev[1][i] + (pt[1][i] - prev[1][i]) * k for i in range(3)]
        prev = pt
    return points[-1][1]


def bolt_z_at(anim, t):
    pts = channel(anim, "bolt", "position")
    return value_at(pts, t)[2]


def bolt_rear_window(anim):
    """返回枪机处于后退位的时间区间 [start, end]。"""
    pts = channel(anim, "bolt", "position")
    inside = [t for t, v in pts if abs(v[2] - BOLT_REAR) < TOL]
    flat_start = flat_end = None
    for i in range(len(pts) - 1):
        if abs(pts[i][1][2] - BOLT_REAR) < TOL and abs(pts[i + 1][1][2] - BOLT_REAR) < TOL:
            flat_start = pts[i][0] if flat_start is None else flat_start
            flat_end = pts[i + 1][0]
    if flat_start is None:
        return None
    return (flat_start, flat_end, inside)


def clip_seat_time(anim, clip_visible_from):
    """新漏夹被压到井底（z 回到 0）的时刻。"""
    for t, v in channel(anim, "clip_in", "position"):
        if t >= clip_visible_from and abs(v[2]) < 1e-6:
            return t
    return None


def clip_visible_from(anim):
    """以 scale 从 0 变 1 的那一帧作为"新漏夹出现"时刻。"""
    prev = None
    for t, v in channel(anim, "clip_in", "scale"):
        if prev is not None and prev < 0.5 and v[0] >= 0.5:
            return t
        prev = v[0]
    return 0.0


def check(name, cond, detail=""):
    print(("  [OK]  " if cond else "  [FAIL]") + f" {name}" + (f" —— {detail}" if detail else ""))
    return cond


def main():
    with open(ANIM, "r", encoding="utf-8") as fh:
        anims = json.load(fh)["animations"]
    ok = True

    for name in ("reload_empty", "reload_tactical"):
        a = anims[name]
        print(f"== {name} ==")
        rear = bolt_rear_window(a)
        if not check(f"{name}: 枪机存在后退位 {BOLT_REAR}u", rear is not None):
            ok = False
            continue
        rear_start, rear_end, _ = rear

        # ① 起手必须先拉到底（不能 t=0 就在后退位，否则枪机瞬移）
        z0 = bolt_z_at(a, 0.0)
        ok &= check(f"{name}: 起手枪机在闭锁位（不是瞬移）", abs(z0) < TOL,
                    f"z(0)={z0:.3f}")
        # ② 拉到底发生在换弹动作的前段
        ok &= check(f"{name}: 0.35s 内完成拉到后退位", rear_start <= 0.35,
                    f"到位 t={rear_start}")
        # ③ 枪机后退期间漏夹才出现/压入
        cv = clip_visible_from(a)
        ok &= check(f"{name}: 漏夹出现时枪机已在后退位", cv >= rear_start - TOL,
                    f"漏夹出现 t={cv} / 枪机后退 t={rear_start}")
        # ④ 枪机必须一直挂住到漏夹卡住
        seat = clip_seat_time(a, cv)
        ok &= check(f"{name}: 漏夹卡到位时枪机仍在后退位",
                    seat is not None and seat <= rear_end + TOL,
                    f"漏夹卡住 t={seat} / 枪机保持到 t={rear_end}")
        # ⑤ 之后枪机才自行前冲（不是人工拉放：t>rear_end 才回到 0）
        closed = min([t for t, v in channel(a, "bolt", "position")
                      if t > rear_end and abs(v[2]) < TOL] or [99])
        ok &= check(f"{name}: 卡住之后枪机才前冲闭锁", closed < 99 and closed > rear_end,
                    f"闭锁 t={closed}")
        # ⑥ 前冲过程中有一个"停一下再拍到位"的节拍（手册第四步）
        mid = [v[2] for t, v in channel(a, "bolt", "position")
               if rear_end < t < closed - 0.02]
        ok &= check(f"{name}: 自由前冲分段（含拍到位节拍）", len(mid) >= 1,
                    f"中间键 {[round(x,3) for x in mid]}")

    print("== shoot（半自动循环）==")
    sh = anims["shoot"]
    peak = max(v[2] for _, v in channel(sh, "bolt", "position"))
    ok &= check("shoot: 枪机循环走全行程（能越过漏夹末弹底缘）",
                abs(peak - BOLT_REAR) < TOL, f"峰值 {peak}")

    print("== 全局：不得使用整体缩放（规范：动画必须骨骼驱动）==")
    bad = []
    for name, a in anims.items():
        for bone, chans in a["bones"].items():
            for chan, ch in chans.items():
                if chan != "scale":
                    continue
                vals = [v for _, v in channel(a, bone, chan)]
                for v in vals:
                    if v[0] not in (0, 1) or v[1] not in (0, 1) or v[2] not in (0, 1):
                        bad.append((name, bone, v))
    ok &= check("scale 通道只出现 0/1（藏件用，非整体缩放）", not bad, str(bad[:3]))

    print()
    print("全部通过" if ok else "存在失败项")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
