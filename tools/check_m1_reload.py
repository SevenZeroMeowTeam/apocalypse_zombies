#!/usr/bin/env python3
"""M1 加兰德换弹/拉栓 机构自检 —— 按 US Army ARDEC 手册 §3.2 的真实动作顺序断言。

检查对象：
  src/main/resources/assets/apocalypse_zombies/animations/m1_garand.animation.json
  src/main/resources/assets/apocalypse_zombies/geo/m1_garand.geo.json
（导出空间：position -> [-x, y, z]，rotation -> [-x, -y, z]；z 不受翻转影响）

真机顺序（手册原话见 tools/m1_garand_bb_anim.js 头部）：
  ① 先把导气杆手柄拉到底（枪机后退）—— 未空仓时井口被枪机挡死，不拉就无法装卸漏夹
  ② 漏夹压入弹夹井直到卡住
  ③ 把手撤开，枪机被漏夹**自动释放**、自由前冲
  ④ 必要时用右手掌根拍拉机柄后端把枪机拍到位闭锁
半满漏夹（战术换弹）多一步机构：
  ①' 拉到底并**保持按住**（手册：Do not relax the rearward pressure … until after the clip has
      been removed），膛内那发活弹先被抛出去
  ②' 左手按下机匣**左侧**的漏夹卡榫销（clip_latch），残夹才脱出
  ③' 松卡榫 → 新夹压入 → 手撤离 → 枪机自由前冲
单发补弹（手册 "To load a single round"）：拉到底（抛掉膛内活弹）→ 手放一发送进膛 →
按托弹板 → 手扶着机柄让枪机**可控地**闭锁（不是自由前冲）。

行程：枪机面必须退过漏夹末弹底缘才有下一发的事 —— 最小量 = .30-06 全弹长 84.8mm ≈ 1.36u。
（2026-09 修：原来这里写死 1.10u 并注释成"模型几何上限"，实测机匣尾面 z=0.448、
 枪机组尾面 z=-1.760，全行程 1.36u 落点 -0.400，余量 0.85u —— 1.10u 只是当时动画取的值。）
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.normpath(os.path.join(
    HERE, "..", "src", "main", "resources", "assets", "apocalypse_zombies"))
ANIM = os.path.join(ASSETS, "animations", "m1_garand.animation.json")
GEO = os.path.join(ASSETS, "geo", "m1_garand.geo.json")

CARTRIDGE = 1.36          # .30-06 全弹长 84.8mm ≈ 1.36u：枪机行程的下限
BOLT_REAR = 1.36          # 枪机后退位（= 全行程）
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


def bolt_peak(anim):
    return max([v[2] for _, v in channel(anim, "bolt", "position")] or [0.0])


def appear_times(anim, bone):
    """scale 由 0(藏) 切到 1(现) 的时刻列表。"""
    out, prev = [], None
    for t, v in channel(anim, bone, "scale"):
        if prev is not None and prev < 0.5 and v[0] >= 0.5:
            out.append(t)
        prev = v[0]
    return out


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
    with open(GEO, "r", encoding="utf-8") as fh:
        geo = json.load(fh)["minecraft:geometry"][0]
    ok = True

    # ---- 几何余量：全行程落点不能戳出机匣尾面 -------------------------------
    print("== 几何：行程余量 ==")
    gb = {b["name"]: b for b in geo["bones"]}
    bolt_rear_z = max(c["origin"][2] + c["size"][2] for c in gb["bolt"]["cubes"])
    body_rear_z = max(c["origin"][2] + c["size"][2] for c in gb["body"]["cubes"])
    ok &= check("枪机走全行程后仍在机匣内（尾面不越界）",
                bolt_rear_z + BOLT_REAR <= body_rear_z + 0.05,
                f"枪机尾面 {bolt_rear_z:.3f} + {BOLT_REAR} <= 机匣尾面 {body_rear_z:.3f}")
    ok &= check("卡榫销在机匣左侧（+X，与真机一致：导气杆在 −X）",
                "clip_latch" in gb and min(c["origin"][0] for c in gb["clip_latch"]["cubes"]) > 0,
                f"clip_latch cubes={len(gb.get('clip_latch', {}).get('cubes', []))}")

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
        if seat is None:
            ok = False
            continue
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
        # ⑦ 抽手空档：漏夹卡住到枪机起步之间要留出人的手撤离时间（≥2 帧 = 1/12 s）
        ok &= check(f"{name}: 漏夹落位后有抽手空档（枪机不是同步起步）",
                    closed - seat >= 2 / 24 - TOL,
                    f"落位 {seat} → 起步 {closed}（{(closed-seat)*24:.0f} 帧）")
        # ⑧ 行程必须越得过末弹底缘
        pk = bolt_peak(a)
        ok &= check(f"{name}: 行程 ≥ 全弹长（越得过漏夹末弹底缘）",
                    pk >= CARTRIDGE - TOL, f"峰值 {pk:.3f} / 需要 {CARTRIDGE}")

    print("== reload_tactical 的卡榫机构（半满漏夹不会自己掉出来）==")
    ta = anims["reload_tactical"]
    lat = channel(ta, "clip_latch", "position")
    ok &= check("reload_tactical: 卡榫销有按下通道", bool(lat), f"{len(lat)} 个键")
    if lat:
        deepest = max(abs(v[0]) for _, v in lat)
        ok &= check("reload_tactical: 按入深度合理（0.02…0.10u，导出空间为负=向机匣内）",
                    0.02 <= deepest <= 0.10, f"最深 {deepest:.3f}u = {deepest*62.5:.1f}mm")
        ok &= check("reload_tactical: 卡榫末端回位（不留在按下状态）",
                    abs(lat[-1][1][0]) < 1e-6, f"末值 x={lat[-1][1][0]}")
        rear_start, rear_end, _ = bolt_rear_window(ta)
        press = min(t for t, v in lat if abs(v[0]) > 0.01)
        ok &= check("reload_tactical: 先拉到底才按得动卡榫", press >= rear_start - TOL,
                    f"按下 t={press} / 枪机后退 t={rear_start}")
    ok &= check("reload_tactical: 膛内活弹被抛出（casing 有出现时刻）",
                len(appear_times(ta, "casing")) >= 1,
                f"出现 {appear_times(ta, 'casing')}")

    print("== single_load（单发补弹）==")
    sl = anims.get("single_load")
    ok &= check("single_load: 段存在", sl is not None)
    if sl:
        ok &= check("single_load: 枪机走全行程", bolt_peak(sl) >= CARTRIDGE - TOL,
                    f"峰值 {bolt_peak(sl):.3f}")
        ok &= check("single_load: 井里的漏夹全程不可见（单发补弹不动漏夹）",
                    all(v[0] < 0.5 for _, v in channel(sl, "clip_in", "scale")),
                    f"clip_in scale={[round(v[0],2) for _, v in channel(sl, 'clip_in', 'scale')]}")
        ok &= check("single_load: 一次抛旧弹 + 一次送新弹（casing 两次出现）",
                    len(appear_times(sl, "casing")) == 2,
                    f"出现 {appear_times(sl, 'casing')}")
        ok &= check("single_load: 闭锁是可控的（落位前有减速键，不是一帧到位）",
                    len([1 for t, v in channel(sl, "bolt", "position")
                         if 0.02 < v[2] < BOLT_REAR - 0.02]) >= 2,
                    f"中间键 {[round(v[2],3) for _, v in channel(sl, 'bolt', 'position')]}")

    print("== shoot（半自动循环）==")
    sh = anims["shoot"]
    peak = bolt_peak(sh)
    ok &= check("shoot: 枪机循环走全行程（能越过漏夹末弹底缘）",
                peak >= CARTRIDGE - TOL, f"峰值 {peak}")

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
