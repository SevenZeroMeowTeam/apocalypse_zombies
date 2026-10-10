# -*- coding: utf-8 -*-
"""「看得见却走不到」判据取证：靶子放 3 格石柱顶。

复现的是 MarksmanSkeleton 修掉的那条老病（它的 javadoc：3 格石柱顶上的靶子，45 秒一箭不放）。
对照组用**没实现 SightFiring 的原版僵尸**跑同一场景：它应该站在柱子下干瞪眼（伤害恒 0）；
残兵现在声明了 sightFiringRange()，应当在柱下开火（伤害 > 0）。同一次运行同一场景，
差异只能来自实体自己声明的射程，不来自场景。
"""
import re
import sys
import time

sys.path.insert(0, "tools")
from _probe_soldier import Rcon, scalar, count, setup  # noqa: E402

PILLAR = 3


def build(r, y):
    setup(r, y)
    r.cmd("fill -3 %d -3 3 %d 3 minecraft:stone" % (int(y) - 1, int(y) - 1 + PILLAR - 1))
    r.cmd("fill -3 %d -3 3 %d 3 minecraft:air" % (int(y), int(y) + 4))


def run(r, kind, label, y, seconds, n=2):
    r.cmd("kill @e[tag=azp_mob]")
    r.cmd("kill @e[tag=azp_v]")
    r.cmd("kill @e[type=minecraft:arrow]")
    r.cmd('summon minecraft:villager 0 %f 0 {NoAI:1b,Silent:1b,PersistenceRequired:1b,'
          'Health:4000.0f,Attributes:[{Name:"generic.max_health",Base:4000}],Tags:["azp_v"]}'
          % (y + PILLAR))
    for i in range(n):
        r.cmd('summon %s -12 %f %f {PersistenceRequired:1b,Silent:1b,AzVariant:0b,Tags:["azp_mob"]}'
              % (kind, y, i * 5.0 - 2.5))
    time.sleep(0.6)
    hp0 = scalar(r, '@e[tag=azp_v,limit=1]')
    print("\n===== %s（靶子在 %d 格石柱顶，看得见走不到）=====" % (label, PILLAR))
    print("  t(s) | victimHP | arrows | mob 位移增量")
    t0 = time.time()
    prev = {}
    while time.time() - t0 < seconds:
        t = time.time() - t0
        hp = scalar(r, '@e[tag=azp_v,limit=1]')
        arrows = count(r, "@e[type=minecraft:arrow]")
        out = r.cmd("execute as @e[tag=azp_mob] run data get entity @s Pos")
        moved = []
        for i, m in enumerate(re.finditer(r"\[(-?[\d.]+)d, (-?[\d.]+)d, (-?[\d.]+)d\]", out)):
            pos = (float(m.group(1)), float(m.group(3)))
            if i in prev:
                moved.append("%.2f" % ((abs(pos[0] - prev[i][0]) ** 2 + abs(pos[1] - prev[i][1]) ** 2) ** 0.5))
            else:
                moved.append("--")
            prev[i] = pos
        print("  %4.2f | %8s | %2d | %s" % (t, hp, arrows, "  ".join(moved)))
        time.sleep(0.5)
    hp1 = scalar(r, '@e[tag=azp_v,limit=1]')
    dmg = (hp0 - hp1) if (hp0 is not None and hp1 is not None) else None
    print("  → 伤害 = %s" % dmg)
    return dmg


def main():
    y = 120.0
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 18.0
    r = Rcon()
    build(r, y)
    res = {}
    res["原版僵尸(对照)"] = run(r, "minecraft:zombie", "原版僵尸（无 SightFiring）", y, secs)
    res["残兵弓手(已修)"] = run(r, "apocalypse_zombies:soldier_zombie", "残兵弓手（已实现 SightFiring）", y, secs)
    r.cmd("kill @e[tag=azp_mob]")
    r.cmd("kill @e[tag=azp_v]")
    r.close()
    print("\n=== 汇总：柱顶靶子受到的伤害 ===")
    for k, v in res.items():
        print("  %-18s %s" % (k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
