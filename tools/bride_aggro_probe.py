# -*- coding: utf-8 -*-
"""「美女僵尸会不会打非怪物目标」的运行时判据（headless 服务端 + RCON）。

为什么必须走运行时：她的目标表是**继承原版僵尸**的（玩家 / 村民 / 铁傀儡 / 海龟），
源码里没有任何一处把它剥掉 —— 静态读到这一步就只能靠猜。而「不攻击」这类缺陷
在静态层面与「一切正常」长得一模一样（编译过、日志干净）。

三条判据设计（都是实测踩过之后补的）：

1. **伤害归属必须钉到她本人身上。** 她召出来的召奬会继承她的目标
   （`summonMinion` 里 `minion.arm(..., this.getTarget())`），于是「受害者掉血」这种
   笼统判据会把召奬的战绩算到她头上 —— 第一版就是这么误判成「会攻击 ✓」的：
   那几下 3.0 全是召奬打的，而她本人站在 10 格外一动没动。故每拍清场召奬。
2. **必须先跑对照相**（`--scenario control`，不召她）：否则无法排除伤害另有来源。
3. **单次伤害按「相邻两拍之差」算**，不能按「与初值之差」算 —— 后者会把同一次命中
   在后续每一拍重复打印，读起来像连击（第一版实际把它数成了 13 次命中）。

退出码约定：**0 = 该场景的期望被满足，2 = 没被满足**。注意期望方向逐场景不同 ——
`villager` / `golem` 期望「打到」（目标表还在），`control` 期望「打不到」（零掉血），
`perch` / `hide` 各看自己的修死锁判据。别把 0 当成唯一的通过码。

用法：
    python tools/bride_aggro_probe.py --scenario control  --seconds 12
    python tools/bride_aggro_probe.py --scenario villager --seconds 40
    python tools/bride_aggro_probe.py --scenario golem    --seconds 40
    python tools/bride_aggro_probe.py --scenario perch    --seconds 45 --trace
    python tools/bride_aggro_probe.py --scenario hide     --seconds 40 --trace

`hide` 是「特性没被修坏」那条判据：她先看见村民锁上，第 8 秒砌一堵 1x3 的墙断掉视线
（两侧留绕行通道）—— 目标是「失去视线但仍走得到」时，她必须继续绕过去打（这是原
`ScentTargetGoal` 的设计意图，修死锁时最容易被一起修坏的东西）。

`perch` 是「站在村民/铁傀儡旁边一动不动」的取证场景（不需要玩家）。三次演进记录：

    第一版「村民封死在石壳里、完全无视线」⇒ **她照样把 6 格外的铁傀儡打死**，
    说明 `mustSee=false` 只影响「锁定之后不再检查视线」，**获取仍然要视线**
    （视线的判据在 `TargetingConditions.forCombat()` 里，不是 mustSee 那个参数）。
    第二版「石壳上留观察窗给她视线」⇒ 仍然没锁上（窗口没真正打通视线）⇒ 判据
    不能靠几何估算，得让她**必须**看得见。

    第三版（本场景）：村民站在 **5 格高石柱顶**（`NoAI`，位置钉死），与「玩家飞在
    上方 / 站在屋顶 / 站在高台上」同形 —— **看得见（获取无碍）但够不着、也走不到**。
    原版村民目标 mustSee=false + mustReach=false ⇒ 锁上就永不释放；而它是 p3 里
    先添加的那条，抢到 TARGET 标志位后同优先级的铁傀儡目标就永远轮不上 ⇒ 她站在
    柱底发呆，旁边 6 格的铁傀儡一下都不打 —— 正是用户报的现象。
    到 `--release`（默认 0.55）成时 kill 掉柱顶村民拆锁：若伤害随即出现，即反证
    冻结期目标确被他占住（这就是判据的对照相）。
"""
import argparse
import math
import re
import socket
import struct
import sys
import time

VICTIM = {"villager": "minecraft:villager", "golem": "minecraft:iron_golem"}
VICTIM_AT = (-3.0, 100.0, 0.0)
BRIDE_AT = (3.0, 100.0, 0.0)
PERCH_AT = (-3.5, 105.0, 6.5)     # 柱顶村民：死锁源，她看得见、够不着
PILLAR_H = 5                      # 石柱高（近战上探只有 ~2.6 格）
MINION = "apocalypse_zombies:charmed_zombie"


class Rcon:
    """Source RCON 客户端（包体 <i len><i id><i type><body>\\0\\0）。"""

    def __init__(self, host="127.0.0.1", port=25575, password="hermesprobe", timeout=10.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.rid = 0
        if self._send(3, password) is None:
            raise SystemExit("RCON 鉴权失败（密码不对？）")

    def _send(self, ptype, body):
        self.rid += 1
        payload = struct.pack("<ii", self.rid, ptype) + body.encode("utf-8") + b"\x00\x00"
        self.sock.sendall(struct.pack("<i", len(payload)) + payload)
        head = self._recv(4)
        if not head:
            return None
        (length,) = struct.unpack("<i", head)
        data = self._recv(length)
        if len(data) < 10:
            return None
        rid, _type = struct.unpack("<ii", data[:8])
        return None if rid == -1 else data[8:-2].decode("utf-8", "replace")

    def _recv(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                break
            buf += chunk
        return buf

    def cmd(self, command):
        return (self._send(2, command) or "").strip()

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def health_of(rcon, tag):
    m = re.search(r":\s*([0-9.]+)f\s*$",
                  rcon.cmd("data get entity @e[tag=%s,limit=1] Health" % tag))
    return float(m.group(1)) if m else None


def pos_of(rcon, tag):
    out = rcon.cmd("data get entity @e[tag=%s,limit=1] Pos" % tag)
    m = re.search(r"\[\s*([-0-9.]+)d,\s*([-0-9.]+)d,\s*([-0-9.]+)d\s*\]", out)
    return tuple(float(g) for g in m.groups()) if m else None


def has_any(rcon, selector):
    return "Test failed" not in rcon.cmd("execute if entity %s" % selector)


def setup(rcon, victim_type, with_bride):
    for c in ("gamerule doMobSpawning false", "gamerule doDaylightCycle false",
              "gamerule mobGriefing false", "gamerule doMobLoot false",
              "difficulty hard", "time set noon", "weather clear",
              "kill @e[tag=probe_v]", "kill @e[tag=probe_b]",
              "kill @e[type=%s]" % MINION,
              "forceload add -16 -16 16 16",
              # 15x15 围栏：地板 + 实心块再掏空成 7 高内室（柱顶村民要留头顶空间，
              # 柱高 5 格才能让她「近战上探 ~2.6 格」也够不着）—— 跑不掉，几何固定
              "fill -8 99 -8 8 99 8 minecraft:stone",
              "fill -8 100 -8 8 107 8 minecraft:stone",
              "fill -7 100 -7 7 106 7 minecraft:air"):
        rcon.cmd(c)
    # 受害者 NoAI：它不该跑、也不该反击，才能把「她打不打」单独量出来
    rcon.cmd("summon %s %s %s %s {NoAI:1b,Silent:1b,PersistenceRequired:1b,"
             "CustomName:'\"probe\"',Tags:[\"probe_v\"]}"
             % ((victim_type,) + tuple("%.1f" % v for v in VICTIM_AT)))
    if with_bride:
        rcon.cmd("summon apocalypse_zombies:bride_zombie %s %s %s "
                 "{PersistenceRequired:1b,Tags:[\"probe_b\"]}"
                 % tuple("%.1f" % v for v in BRIDE_AT))
    time.sleep(0.6)


def perch_cell(rcon):
    """柱顶村民：看得见、走不到、够不着 —— 与「玩家飞在上方 / 站屋顶 / 站高台」同形。
    原版村民目标 mustSee=false + mustReach=false ⇒ 一旦锁上就永不释放。"""
    x, z = int(PERCH_AT[0]), int(PERCH_AT[2])
    rcon.cmd("fill %d 100 %d %d %d %d minecraft:stone"
             % (x, z, x, 100 + PILLAR_H - 1, z))
    rcon.cmd("summon minecraft:villager %s %s %s {NoAI:1b,Silent:1b,"
             "PersistenceRequired:1b,Tags:[\"probe_c\"]}"
             % tuple("%.1f" % v for v in PERCH_AT))


def run(scenario, seconds, step, trace=False, release=0.55, wall=8.0):
    with_bride = scenario != "control"
    perch = scenario == "perch"
    hide = scenario == "hide"
    if perch:
        victim_type = VICTIM["golem"]
    elif hide or not with_bride:
        victim_type = VICTIM["villager"]
    else:
        victim_type = VICTIM[scenario]
    rcon = Rcon()
    setup(rcon, victim_type, with_bride)
    if perch:
        perch_cell(rcon)
    released, dmg_locked = False, 0.0
    walled, dmg_wall = False, 0.0

    start = health_of(rcon, "probe_v")
    if start is None:
        rcon.close()
        raise SystemExit("受害者没召出来（%s）" % victim_type)
    if not with_bride:
        label = "对照（不召她）"
    elif perch:
        label = ("死锁取证：受害者 %s（%.1f 格）+ 柱顶村民（%.1f 格、高 %d 格，看得见够不着）"
                 % (victim_type.replace("minecraft:", ""),
                    math.dist(BRIDE_AT, VICTIM_AT),
                    math.dist(BRIDE_AT, PERCH_AT), PILLAR_H))
    elif hide:
        label = ("失去视线但仍走得到：受害者 %s（%.1f 格），第 %.0fs 砌墙断视线"
                 % (victim_type.replace("minecraft:", ""), math.dist(BRIDE_AT, VICTIM_AT), wall))
    else:
        label = "美女僵尸在场（每拍清场召奬）"
    print("受害者 %s 初始 %.1f HP；%s；起步间距 %.1f 格"
          % (victim_type, start, label,
             math.dist(BRIDE_AT, VICTIM_AT) if with_bride else 0.0))

    last, t0 = start, time.monotonic()
    hits, dists, minions_seen = [], [], False
    while time.monotonic() - t0 < seconds:
        if with_bride:
            minions_seen = minions_seen or has_any(rcon, "@e[type=%s]" % MINION)
            rcon.cmd("kill @e[type=%s]" % MINION)   # 每拍清场，伤害只可能来自她本人
        h = health_of(rcon, "probe_v")
        p = pos_of(rcon, "probe_b") if with_bride else None
        now = time.monotonic() - t0
        if perch and not released and now >= seconds * release:
            rcon.cmd("kill @e[tag=probe_c]")
            released, dmg_locked = True, round(start - last, 2)
            print("  %6.1fs  ✂ 拆锁：kill 柱顶村民 —— 冻结期受害者只掉 %.1f HP"
                  % (now, dmg_locked))
        if hide and not walled and now >= wall:
            # 3 格高 1 格厚的墙，两侧（z=±3）留绕行通道：视线断了，但她走得到
            rcon.cmd("fill -1 100 -2 -1 102 2 minecraft:stone")
            walled, dmg_wall = True, round(start - last, 2)
            print("  %6.1fs  ▣ 砌墙断视线（两侧可绕行）—— 到此受害者掉血 %.1f" % (now, dmg_wall))
        if h is None:
            print("%6.1fs 受害者已消失（被打死）" % now)
            last = 0.0
            break
        if p:
            dists.append(math.dist(p, VICTIM_AT))
        d = round(last - h, 2)
        if trace:
            print("    %6.1fs  HP %5.1f  Δ%+.1f  距受害者 %.2f 格%s%s"
                  % (now, h, -d, dists[-1] if dists else -1.0,
                     "  距柱顶村民 %.2f 格" % math.dist(p, PERCH_AT) if (perch and p) else "",
                     "  ← 命中" if d > 0 else ""))
        if d > 0:
            hits.append((now, d, dists[-1] if dists else float("nan")))
            print("  %6.1fs  命中 -%.1f HP（剩 %.1f）  她距受害者 %.2f 格"
                  % (now, d, h, hits[-1][2]))
        last = h
        time.sleep(step)

    gone = health_of(rcon, "probe_v") is None
    total = round(start - last, 2)
    print()
    print("=== %s" % label)
    print("    受害者掉血 %.1f%s" % (total, "，已死亡" if gone else ""))
    if dists:
        print("    她到受害者的距离：最近 %.2f / 最远 %.2f 格（%d 拍）"
              % (min(dists), max(dists), len(dists)))
    if hits:
        print("    命中 %d 次｜单次伤害 %s｜命中时距离 %s"
              % (len(hits), sorted({h[1] for h in hits}), ["%.1f" % h[2] for h in hits]))
    else:
        print("    一次命中都没有")
    if with_bride:
        print("    期间召出过召奬：%s（已每拍清场，不计入她的战绩）" % ("是" if minions_seen else "否"))
    if perch:
        after = round(total - dmg_locked, 2)
        print("    锁着够不着的村民期间掉血 %.1f（修前是 0.0 —— 那几十秒她一动不动）" % dmg_locked)
        print("    拆锁后掉血 %.1f；冻结期命中 %d 次"
              % (after, len([h for h in hits if h[0] < seconds * release])))
        fixed = dmg_locked > 0
        print("    结论：%s" % ("够不着的目标不再占住目标表（她照打铁傀儡）✓" if fixed
                            else "死锁仍在：够不着的目标占住了整张表 ✗"))
        rcon.close()
        return 0 if fixed else 2
    if hide:
        after = round(total - dmg_wall, 2)
        print("    砌墙前掉血 %.1f ／ 砌墙后掉血 %.1f" % (dmg_wall, after))
        kept = after > 0
        print("    结论：%s" % ("视线断了但仍走得到 ⇒ 她继续追着打 ✓（原「隔墙摸过来」的设计意图保住）"
                            if kept else "丢目标 ✗（把隔墙追击一起修坏了）"))
        rcon.close()
        return 0 if kept else 2
    if not with_bride:
        # 对照相的期望值是**反过来**的：她在场外 ⇒ 正确结果就是零掉血。
        # 早前这条走上面那个通用分支，于是「健康的对照相」被打印成「不攻击 ✗」并
        # 返回 2（accept.log / accept2.log / green.log / green2.log 四处都带着这个
        # 错），读日志的人会把一次通过的验收看成失败。判据的方向必须跟着场景走。
        clean = not hits
        print("    结论：%s" % ("对照相干净：她在场外、受害者零掉血 ⇒ 其它场景掉的血只能记在她头上 ✓"
                            if clean else "对照相就掉血 ⇒ 伤害另有来源，其它场景的结论全部作废 ✗"))
        rcon.close()
        return 0 if clean else 2
    print("    结论：%s" % ("会攻击 ✓" if hits else "不攻击 ✗"))
    rcon.close()
    return 0 if hits else 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="villager",
                    choices=["villager", "golem", "control", "perch", "hide"])
    ap.add_argument("--seconds", type=float, default=40.0)
    ap.add_argument("--step", type=float, default=0.4)
    ap.add_argument("--trace", action="store_true", help="打印每一拍（全帧轨迹）")
    ap.add_argument("--release", type=float, default=0.55,
                    help="perch 场景：跑到几成时 kill 柱顶村民拆锁（默认 0.55）")
    ap.add_argument("--wall", type=float, default=8.0,
                    help="hide 场景：第几秒砌墙断视线（默认 8s，墙两侧留绕行通道）")
    a = ap.parse_args()
    return run(a.scenario, a.seconds, a.step, a.trace, a.release, a.wall)


if __name__ == "__main__":
    sys.exit(main())
