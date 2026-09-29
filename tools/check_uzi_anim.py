#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Uzi 动画校验门禁 —— 把"看起来没问题"换成可执行的不变量。

用法:  python tools/check_uzi_anim.py
退出码: 0 = 全部通过; 1 = 有条目 FAIL

为什么这些检查必须存在：
  1. 动画里的骨骼名写错不会报错 —— GeckoLib 找不到骨头就静静什么都不动。
  2. 关键帧时间超过 animation_length 会被静默截断，动作永远播不完。
  3. 结尾不回静止姿态，切回 static_idle 时会有残影式的跳变。
  4. 弹匣如果没真的脱出握把，换弹看起来就是"弹匣在原地抖动"。
  5. additional_magazine 一旦被 K 帧，TaCZ 会崩游戏。
  6. casing（弹壳）不显式 scale 0 就会被永远挂在枪上。
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "src", "main", "resources", "assets", "apocalypse_zombies")
GEO = os.path.join(ASSETS, "geo", "uzi.geo.json")
ANIM = os.path.join(ASSETS, "animations", "uzi.animation.json")

# Java 侧按键名取（UziItem.ANIM_*）：本轮交付全部 9 个。
REQUIRED = {"static_idle": True, "draw": False, "shoot": False, "shoot_auto": False, "bolt": False,
            "reload_tactical": False, "reload_empty": False,
            "ADS_up": False, "ADS_down": False}

# 只有这些 clip 会推拉枪机；static_idle 的职责恰恰是把枪机钉在静止位，
# draw 只把枪机从后方释放一次，也算一次循环。
CYCLES_BOLT = {"bolt", "reload_tactical", "reload_empty", "shoot", "draw", "shoot_auto"}
# 会抛壳的 clip。其余 clip 的弹壳必须显式 scale 0 藏起来。
# shoot_auto 刻意不抛壳：2 帧太短，弹壳飞不出去就重置，抛壳改由 Java 侧撒粒子。
EJECTS = {"bolt", "shoot"}
# 只有这些 clip 换弹匣。
RELOAD_CLIPS = {"reload_tactical", "reload_empty"}
# 纯姿态过渡 clip：只许动 move/body，别的一律钉住防混合漂移。
POSE_ONLY = {"ADS_up", "ADS_down"}

LOOPS = {"static_idle"}                      # 允许 loop 的 clip
REST_ZERO_POS = ("move", "bolt", "magazine")  # 静止时 position 必须为 0
REST_ZERO_ROT = ("move", "body", "magazine", "trigger_group")

fails = []
anims = {}          # main() 填充，供 report() 打印计数


def fail(m):
    fails.append(m)


def box(c):
    o, s = c["origin"], c["size"]
    lo = [o[i] if s[i] >= 0 else o[i] + s[i] for i in range(3)]
    hi = [o[i] + s[i] if s[i] >= 0 else o[i] for i in range(3)]
    return lo, hi


def bone_bbox(bones, name):
    b = next((x for x in bones if x["name"] == name), None)
    if not b or not b.get("cubes"):
        return None
    lo = [1e9] * 3
    hi = [-1e9] * 3
    for c in b["cubes"]:
        clo, chi = box(c)
        for i in range(3):
            lo[i], hi[i] = min(lo[i], clo[i]), max(hi[i], chi[i])
    return lo, hi


def chan_keys(bone, ch):
    """{'0.0': {'post': {...}, 'lerp_mode': ...}} -> {0.0: [x,y,z]}"""
    out = {}
    for t, k in bone.get(ch, {}).items():
        e = k.get("post", k)
        if "pre" in k and "post" not in k:
            e = k["pre"]
        v = e.get("vector")
        if v is not None:
            out[float(t)] = v
    return out


REF_M1 = os.path.join(ASSETS, "animations", "m1_garand.animation.json")
REF_CROSSBOW = os.path.join(ASSETS, "animations", "crossbow.animation.json")


def ref_chan(path, clip, bone, ch):
    """读参考枪（m1_garand / crossbow）里某个 clip 的某个通道 -> {time: [x,y,z]}。

    参考文件是 **文件空间**（游戏直接读它），是符号约定的事实标准。
    """
    if not os.path.isfile(path):
        return {}
    d = json.load(open(path, encoding="utf-8")).get("animations", {}).get(clip, {})
    b = d.get("bones", {}).get(bone, {})
    out = {}
    for t, k in b.get(ch, {}).items():
        if not isinstance(k, dict):
            continue
        try:
            f = float(t)
        except (TypeError, ValueError):
            continue
        e = k.get("post", k)
        if "pre" in k and "post" not in k:
            e = k["pre"]
        if isinstance(e, dict) and "vector" in e:
            out[f] = list(e["vector"])
    return out


def at(chan, t):
    """取离 t 最近的键值，通道为空时返回 None。"""
    if not chan:
        return None
    return chan[min(chan, key=lambda x: abs(x - t))]


UZI_ITEM = os.path.join(ROOT, "src", "main", "java", "com", "apocalypse", "zombies",
                        "item", "UziItem.java")


def java_fire_interval():
    """从 UziItem.java 读连发间隔（tick）；读不到返回 None 并记 FAIL。

    跨语言硬不变量：动画的连发循环长度必须等于 Java 的射击间隔。两者一旦漂移，
    枪机要么在复进前被打断（间隔 < 循环），要么每发之间空转一帧（间隔 > 循环）——
    两种都只在游戏里肉眼可见，脚本必须替人盯住。
    """
    if not os.path.isfile(UZI_ITEM):
        fail("缺少 Java 接线 UziItem.java —— 只有资源没有 Java，游戏里拿不到枪")
        return None
    m = re.search(r"FIRE_INTERVAL_TICKS\s*=\s*(\d+)", open(UZI_ITEM, encoding="utf-8").read())
    if not m:
        fail("UziItem.java 里找不到 FIRE_INTERVAL_TICKS")
        return None
    return int(m.group(1))


def main():
    global anims
    for p in (GEO, ANIM):
        if not os.path.isfile(p):
            fail("缺少 " + p)
    if fails:
        return report()

    geo = json.load(open(GEO, encoding="utf-8"))["minecraft:geometry"][0]
    gbones = geo["bones"]
    gnames = {b["name"] for b in gbones}
    d = json.load(open(ANIM, encoding="utf-8"))
    anims = d.get("animations", {})

    # ---------------------------------------------------------------- 头部契约
    if d.get("format_version") != "1.8.0":
        fail("format_version 应为 1.8.0（美术规范 五.1），实为 %r" % d.get("format_version"))
    for name, want_loop in REQUIRED.items():
        if name not in anims:
            fail("缺少 clip %s（Java 常量按键名取）" % name)

    # ---------------------------------------------------------------- 逐 clip
    for name, a in anims.items():
        L = a.get("animation_length")
        bones = a.get("bones", {})
        if name in LOOPS:
            if not a.get("loop"):
                fail("%s 必须 loop" % name)
        else:
            if a.get("loop") in (True, "loop"):
                fail("%s 不应 loop" % name)

        for bn, chans in bones.items():
            if bn not in gnames:
                fail("%s: 骨骼 %r 在 geo 里不存在 —— GeckoLib 会静默不动" % (name, bn))
            if bn == "additional_magazine":
                fail("%s: 动画了 additional_magazine（TaCZ 会崩游戏）" % name)
            for ch in chans:
                if ch not in ("rotation", "position", "scale"):
                    fail("%s.%s: 未知通道 %r" % (name, bn, ch))

        end_pose = {}
        for bn, chans in bones.items():
            for ch, raw in chans.items():
                ks = chan_keys(chans, ch)
                if not ks:
                    fail("%s.%s.%s 没有关键帧" % (name, bn, ch))
                    continue
                tmax = max(ks)
                if tmax > L + 1e-9:
                    fail("%s.%s.%s 最后一帧 %.4f 超过 clip 长度 %.4f" % (name, bn, ch, tmax, L))
                if min(ks) > 1e-9:
                    fail("%s.%s.%s 缺少 t=0 起始帧" % (name, bn, ch))
                for t, k in chans[ch].items():
                    e = k.get("post", k)
                    if e.get("lerp_mode") not in ("catmullrom", None):
                        fail("%s.%s.%s@%s 插值异常 %r" % (name, bn, ch, t, e.get("lerp_mode")))
                end_pose[(bn, ch)] = ks[tmax]

        # 结尾必须回到静止姿态，否则切回 static_idle 会跳变。
        # 例外：ADS 是**过渡** clip —— ADS_up 结束在瞄准姿态、ADS_down 起始就在瞄准姿态，
        # 它们本来就该停在非零位；链路正确性由下面的 ADS 接力检查负责。
        if name not in POSE_ONLY:
            for bn in REST_ZERO_POS:
                if (bn, "position") in end_pose and any(abs(v) > 1e-6 for v in end_pose[(bn, "position")]):
                    fail("%s: 结尾 %s.position=%s 未回零" % (name, bn, end_pose[(bn, "position")]))
            for bn in REST_ZERO_ROT:
                if (bn, "rotation") in end_pose and any(abs(v) > 1e-6 for v in end_pose[(bn, "rotation")]):
                    fail("%s: 结尾 %s.rotation=%s 未回零" % (name, bn, end_pose[(bn, "rotation")]))
        if ("casing", "scale") in end_pose and end_pose[("casing", "scale")] != [0, 0, 0]:
            fail("%s: 结尾弹壳 scale=%s，应保持 [0,0,0] 藏起来" % (name, end_pose[("casing", "scale")]))

        # bolt 是自由枪机：只能沿 +Z 直线后退，不许有 x/y 漂移
        bp = chan_keys(bones.get("bolt", {}), "position")
        if bp:
            xz = [v for v in bp.values()]
            if any(abs(v[0]) > 1e-6 or abs(v[1]) > 1e-6 for v in xz):
                fail("%s: bolt 位移出现 x/y 分量，直动式枪机只能沿 Z 走" % name)
            travel = max(v[2] for v in xz)
            if name in CYCLES_BOLT:
                if travel <= 0.2:
                    fail("%s: bolt 行程只有 %.2fu，太小看不出来" % (name, travel))
                else:
                    print("%-18s bolt 行程 %.2fu (%.0f mm)" % (name, travel, travel * 62.5))

        # 弹壳：不使用时必须全程 scale 0；bolt/shoot 里必须真的飞出去
        cs = chan_keys(bones.get("casing", {}), "scale")
        if name in EJECTS:
            if not cs or max(v[0] for v in cs.values()) < 0.5:
                fail("%s: 弹壳从未出现（scale 峰值 %.2f）" % (name, max((v[0] for v in cs.values()), default=0)))
            else:
                print("%-18s 弹壳抛出 ✓" % name)
        elif cs and any(v[0] > 0.01 for v in cs.values()):
            fail("%s: 弹壳被显示出来了（只有 %s 才该抛壳）" % (name, "/".join(sorted(EJECTS))))

        # 弹匣脱出：最低点必须让匣顶降到握把底之下，否则只是"原地抖动"
        gb = bone_bbox(gbones, "grip")
        mb = bone_bbox(gbones, "magazine")
        if gb and mb:
            grip_bottom = gb[0][1]
            mag_top = mb[1][1]
            mp = chan_keys(bones.get("magazine", {}), "position")
            if mp and name in RELOAD_CLIPS:
                low = min(v[1] for v in mp.values())
                need = mag_top - grip_bottom          # 要让匣顶降到握把底需要下移这么多
                if low < -0.02:
                    if mag_top + low > grip_bottom + 1e-6:
                        fail("%s: 弹匣只下移 %.2fu，匣顶(%.2f)仍在握把底(%.2f)之上 —— 没脱出"
                             % (name, low, mag_top + low, grip_bottom))
                    else:
                        print("%-18s 弹匣脱出 ✓ 下移 %.2fu，匣顶降至 %.2f（握把底 %.2f）"
                              % (name, low, mag_top + low, grip_bottom))
                else:
                    fail("%s: 弹匣没有位移，换弹不成立" % name)

        # 空仓换弹：新匣插入前弹带必须是空的，插入后必须满
        if name == "reload_empty":
            for rb in ("mag_r1", "mag_r2", "mag_r3"):
                ks = chan_keys(bones.get(rb, {}), "scale")
                if not ks:
                    fail("reload_empty: %s 无 scale 关键帧" % rb)
                    continue
                ts = sorted(ks)
                if ks[ts[0]][0] > 0.01:
                    fail("reload_empty: %s 起始不是空的" % rb)
                if ks[ts[-1]][0] < 0.99:
                    fail("reload_empty: %s 结尾没装满" % rb)
                fill = next((t for t in ts if ks[t][0] > 0.99), None)
                seat = min((t for t, v in chan_keys(bones.get("magazine", {}), "position").items()
                            if abs(v[1]) < 1e-6 and t > 0.2), default=None)
                if fill is not None and seat is not None and fill < seat - 0.05:
                    fail("reload_empty: %s 在弹匣入位(%.2f)之前就装满了(%.2f)" % (rb, seat, fill))
            print("%-18s 三层弹带 空->满 时序 ✓" % name)

        # ------------------------------------------------------ draw：从画面下方抬起 + 闭锁上膛
        if name == "draw":
            mp = chan_keys(bones.get("move", {}), "position")
            if not mp:
                fail("draw: move 无 position 关键帧")
            else:
                y0 = mp[min(mp)][1]
                if y0 > -1.0:
                    fail("draw: 起始 move.position.y=%.2f，枪没有从画面下方抬起" % y0)
                else:
                    print("draw 起始 move.y=%+.2fu（从下方入画）✓" % y0)
            bp = chan_keys(bones.get("bolt", {}), "position")
            if bp:
                ts = sorted(bp)
                if bp[ts[0]][2] < 0.3:
                    fail("draw: 枪机起始只挂在 %.2fu，看不出\"释放枪机上膛\"这一手" % bp[ts[0]][2])
                if abs(bp[ts[-1]][2]) > 1e-6:
                    fail("draw: 枪机结尾 %.2fu 没复进闭锁" % bp[ts[-1]][2])

        # ------------------------------------------------------ shoot：自由枪机循环必须够快
        if name == "shoot":
            bp = chan_keys(bones.get("bolt", {}), "position")
            if bp:
                peak_t = max(bp, key=lambda t: bp[t][2])
                closed_t = next((t for t in sorted(bp) if t > peak_t and abs(bp[t][2]) < 1e-6), None)
                if peak_t > 0.12 or closed_t is None or closed_t > 0.25:
                    fail("shoot: 枪机 %.3fs 到顶 / %s 复进 —— 不像自由枪机（应 ≤0.12s / ≤0.25s）"
                         % (peak_t, closed_t))
                else:
                    print("shoot 枪机循环 %.0fms 到顶 / %.0fms 复进 ✓ 自由枪机"
                          % (peak_t * 1000, closed_t * 1000))

        # ------------------------------------------------------ shoot_auto：连发紧凑循环
        # 连发不是"每 2 tick 重播一次 shoot"：shoot 的枪机循环要 0.208s，2 tick 重播会在
        # 枪机复进前一刀截断，看起来像卡在后位抽搐。连发必须有自己的循环，而且必须线性 ——
        # 2 帧的区间里 catmullrom 会把枪机甩过 1.05 的机械止点再弹回来。
        if name == "shoot_auto":
            for bn, chans in bones.items():
                for ch, raw in chans.items():
                    for t, k in raw.items():
                        e = k.get("post", k)
                        if isinstance(e, dict) and "lerp_mode" in e:
                            fail("shoot_auto.%s.%s@%s 写了 lerp_mode=%r —— 2 帧循环必须线性插值，"
                                 "catmullrom 会冲过枪机机械止点" % (bn, ch, t, e["lerp_mode"]))
            bp = chan_keys(bones.get("bolt", {}), "position")
            if bp:
                travel = max(v[2] for v in bp.values())
                if abs(travel - 1.05) > 1e-6:
                    fail("shoot_auto: 枪机行程 %.3fu != 手动拉栓的 1.05u —— 连发与手拉不是同一根枪机"
                         % travel)
            # 循环长度必须正好压在 Java 的连发间隔上，否则要么丢帧要么空转。
            want = java_fire_interval()
            if want is not None:
                have = round(L * 20)
                if have != want:
                    fail("shoot_auto 长度 %d tick 与 UziItem.FIRE_INTERVAL_TICKS=%d 不一致 —— "
                         "连发时枪机动作与射击节奏会错位" % (have, want))
                else:
                    print("shoot_auto 循环 %d tick == Java FIRE_INTERVAL_TICKS=%d ✓（%d rpm，线性）"
                          % (have, want, round(1200.0 / have)))

        # ------------------------------------------------------ ADS：纯姿态过渡，别的骨骼必须钉住
        if name in POSE_ONLY:
            for bn, chans in bones.items():
                if bn in ("move", "body"):
                    continue
                for ch in chans:
                    vals = chan_keys(chans, ch)
                    exp = [1, 1, 1] if bn.startswith("mag_r") and ch == "scale" else [0, 0, 0]
                    if any(v != list(exp) for v in vals.values()):
                        fail("%s: 过渡 clip 动了 %s.%s（混合时会被别的动作拖漂）" % (name, bn, ch))
                if len(chan_keys(chans, "position")) > 1 or \
                   (chan_keys(chans, "scale") and len(chan_keys(chans, "scale")) > 1):
                    fail("%s: %s 有多个关键帧，过渡 clip 里应当只有一个常量帧" % (name, bn))
            if len(bones.get("move", {}).get("position", {})) != 5:
                fail("%s: move.position 应有 5 个关键帧（1/24s 步长）" % name)

    # ---------------------------------------------------------------- ADS 互逆
    # ADS_down 必须是 ADS_up 的严格倒放：否则抬手/收枪两条曲线不对称，
    # 松开右键的瞬间枪会跳一下。
    if "ADS_up" in anims and "ADS_down" in anims:
        for bn in ("move", "body"):
            for ch in ("position", "rotation"):
                up = chan_keys(anims["ADS_up"].get("bones", {}).get(bn, {}), ch)
                dn = chan_keys(anims["ADS_down"].get("bones", {}).get(bn, {}), ch)
                if not up or not dn:
                    continue
                su = [v for _, v in sorted(up.items())]
                sd = [v for _, v in sorted(dn.items())]
                if su != list(reversed(sd)):
                    fail("ADS_up/ADS_down 的 %s.%s 不互为倒放" % (bn, ch))
                else:
                    print("ADS %-14s %d 键与 ADS_down 互为倒放 ✓" % (bn + "." + ch, len(su)))
                # 接力：ADS_up 的终态必须正好是 ADS_down 的起始态，
                # 否则松开右键的那一刻枪会瞬移回静止位。
                if su[0] != sd[-1]:
                    fail("ADS 接力断点 %s.%s：ADS_down 起始 %s != ADS_up 终态 %s"
                         % (bn, ch, sd[0], su[-1]))
        # ADS_down 必须把枪带回静止姿态（它是"退出瞄准"的收尾）
        for bn in ("move",):
            v = at(chan_keys(anims["ADS_down"].get("bones", {}).get(bn, {}), "position"), 0.18)
            if v and any(abs(x) > 1e-6 for x in v):
                fail("ADS_down 结尾 %s.position=%s 没回到静止位" % (bn, v))
        for bn in ("move", "body"):
            v = at(chan_keys(anims["ADS_down"].get("bones", {}).get(bn, {}), "rotation"), 0.18)
            if v and any(abs(x) > 1e-6 for x in v):
                fail("ADS_down 结尾 %s.rotation=%s 没回到静止位" % (bn, v))
        print("ADS_up 终态 -> ADS_down 起始 接力衔接 ✓；ADS_down 收在静止位 ✓")

    # ---------------------------------------------------------------- 符号与参考枪一致
    # 导出器在 作者空间 -> 文件空间 之间把 rotation.x/y 取反（position 只取反 x），
    # 于是"照抄参考文件里的数值"会把整段动作镜像：枪口该上跳却下压、抛壳该右手边却跑到左边。
    # 这里直接拿 m1_garand / crossbow 的文件空间数值当标准，逐通道比符号。
    def uchan(clip, bone, ch):
        return chan_keys(anims.get(clip, {}).get("bones", {}).get(bone, {}), ch)

    def pick(chan, comp, mode="peak"):
        if not chan:
            return None
        t = max(chan, key=lambda k: abs(chan[k][comp])) if mode == "peak" else max(chan)
        return chan[t][comp]

    def us(clip, bone, ch, comp, mode="peak"):
        return pick(uchan(clip, bone, ch), comp, mode)

    def rs(path, clip, bone, ch, comp, mode="peak"):
        return pick(ref_chan(path, clip, bone, ch), comp, mode)

    def same(label, mine, ref):
        if mine is None or ref is None:
            return
        if mine * ref < 0:
            fail("%s：符号与参考枪相反（uzi %+.2f vs 参考 %+.2f）—— 动作被镜像了"
                 % (label, mine, ref))
        else:
            print("%-26s uzi %+8.2f / 参考 %+8.2f ✓" % (label, mine, ref))

    same("shoot 后座枪口俯仰", us("shoot", "move", "rotation", 0),
         rs(REF_M1, "shoot", "move", "rotation", 0))
    same("shoot 后座枪身俯仰", us("shoot", "body", "rotation", 0),
         rs(REF_M1, "shoot", "body", "rotation", 0))
    same("bolt 拉栓枪口俯仰", us("bolt", "move", "rotation", 0),
         rs(REF_M1, "bolt", "move", "rotation", 0))
    same("bolt 拉栓枪身俯仰", us("bolt", "body", "rotation", 0),
         rs(REF_M1, "bolt", "body", "rotation", 0))
    same("draw 抬起枪口俯仰", us("draw", "move", "rotation", 0),
         rs(REF_M1, "draw", "move", "rotation", 0))
    same("ADS_up 终态枪身俯仰", us("ADS_up", "body", "rotation", 0, "end"),
         rs(REF_CROSSBOW, "ADS_up", "body", "rotation", 0, "end"))
    same("抛壳横向 casing.x", us("shoot", "casing", "position", 0),
         rs(REF_M1, "shoot", "casing", "position", 0))
    same("抛壳翻滚 casing.rot.x", us("shoot", "casing", "rotation", 0),
         rs(REF_M1, "shoot", "casing", "rotation", 0))

    # ---------------------------------------------------------------- 骨骼零旋转（静态几何铁律）
    for b in gbones:
        r = b.get("rotation") or (0, 0, 0)
        if any(abs(v) > 1e-9 for v in r):
            fail("骨骼 %s 带静态旋转（铁律：骨骼一根都不许带旋转）" % b["name"])

    return report()


def report():
    for f in fails:
        print("FAIL  " + f)
    if fails:
        print("\nCHECK FAIL：%d 项" % len(fails))
        return 1
    print("\nCHECK PASS：Uzi 动画符合契约（%d 个 clip：换弹 / 拉栓 / 拔枪 / 开火 / ADS）" % len(anims))
    return 0


if __name__ == "__main__":
    sys.exit(main())
