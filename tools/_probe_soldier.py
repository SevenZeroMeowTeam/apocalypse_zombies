# -*- coding: utf-8 -*-
"""残兵（soldier_zombie）取证：两种兵分开测，直接数弹丸，判「到底开不开火」。

上一轮没锁变种，只能看到「绕着 11 格来回踱步、14 秒只掉 5 点血」。
这一轮用 NBT {AzVariant:0b/1b} 把变种钉死（readAdditionalSaveData 会读它），
再用 `execute if entity` 直接数 arrow / primed_tnt（RCON 会回 "Test passed, count: N"），
于是「有没有攻击」不再靠血条间接推断。
"""
import argparse
import re
import socket
import struct
import sys
import time

DATA = re.compile(r"has the following entity data: (.+)")


class Rcon:
    def __init__(self, host="127.0.0.1", port=25575, password="hermesprobe"):
        self.sock = socket.create_connection((host, port), timeout=15.0)
        self.sock.settimeout(15.0)
        self.rid = 0
        self._send(3, password)
        self._recv()

    def _send(self, kind, body):
        self.rid += 1
        p = struct.pack("<ii", self.rid, kind) + body.encode("utf-8") + b"\x00\x00"
        self.sock.sendall(struct.pack("<i", len(p)) + p)

    def _recv(self):
        raw = self.sock.recv(4)
        if len(raw) < 4:
            return ""
        n = struct.unpack("<i", raw)[0]
        buf = b""
        while len(buf) < n:
            c = self.sock.recv(n - len(buf))
            if not c:
                break
            buf += c
        return buf[8:-2].decode("utf-8", "replace")

    def cmd(self, command):
        self._send(2, command)
        return self._recv()

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def scalar(r, sel, path="Health"):
    m = DATA.search(r.cmd("data get entity %s %s" % (sel, path)))
    if not m:
        return None
    nums = re.findall(r"-?\d+\.?\d*[dDfF]?", m.group(1))
    return float(nums[0].rstrip("dDfF")) if nums else None


def vec(r, sel):
    m = DATA.search(r.cmd("data get entity %s Pos" % sel))
    if not m:
        return None
    nums = re.findall(r"-?\d+\.?\d*[dDfF]?", m.group(1))
    try:
        return [float(n.rstrip("dDfF")) for n in nums]
    except ValueError:
        return None


def count(r, sel):
    out = r.cmd("execute if entity %s" % sel)
    m = re.search(r"count:\s*(\d+)", out)
    return int(m.group(1)) if m else 0


def setup(r, y):
    r.cmd("gamerule doMobSpawning false")
    r.cmd("gamerule doMobLoot false")
    r.cmd("gamerule mobGriefing false")
    r.cmd("gamerule doDaylightCycle false")
    r.cmd("difficulty easy")
    r.cmd("time set midnight")
    r.cmd("forceload add -40 -40 40 40")
    for dy in (0, 1, 2):
        r.cmd("fill -25 %d -25 25 %d 25 minecraft:stone" % (int(y) - 1 - dy, int(y) - 1 - dy))
    r.cmd("fill -25 %d -25 25 %d 25 minecraft:air" % (int(y), int(y) + 4))
    r.cmd("kill @e[type=!minecraft:player,distance=..80]")


def run(r, variant, label, y, seconds, n):
    r.cmd("kill @e[tag=azs_mob]")
    r.cmd("kill @e[tag=azs_v]")
    r.cmd("kill @e[type=minecraft:arrow]")
    r.cmd("kill @e[type=minecraft:tnt]")
    r.cmd('summon minecraft:villager 0 %f 0 {NoAI:1b,Silent:1b,PersistenceRequired:1b,'
          'Health:4000.0f,Attributes:[{Name:"generic.max_health",Base:4000}],Tags:["azs_v"]}' % y)
    for i in range(n):
        r.cmd('summon apocalypse_zombies:soldier_zombie -14 %f %f {PersistenceRequired:1b,'
              'Silent:1b,AzVariant:%db,Tags:["azs_mob"]}' % (y, i * 5.0 - 2.5, variant))
    time.sleep(0.6)
    print("\n===== %s（AzVariant=%db，%d 只，距离 14）=====" % (label, variant, n))
    print("  t(s) | victimHP | mob:dist step | arrows | tnt")
    prev = {}
    hp0 = scalar(r, '@e[tag=azs_v,limit=1]')
    moved = 0.0
    t0 = time.time()
    while time.time() - t0 < seconds:
        t = time.time() - t0
        hp = scalar(r, '@e[tag=azs_v,limit=1]')
        arrows = count(r, "@e[type=minecraft:arrow]")
        tnts = count(r, "@e[type=minecraft:tnt]")
        parts = []
        # 一次命令取回全部位置（execute as @e 会逐实体回一行，顺序=实体 id 顺序=召唤顺序）
        out = r.cmd("execute as @e[tag=azs_mob] run data get entity @s Pos")
        for i, m in enumerate(re.finditer(r"\[(-?[\d.]+)d, (-?[\d.]+)d, (-?[\d.]+)d\]", out)):
            x, zz = float(m.group(1)), float(m.group(3))
            d = (x * x + zz * zz) ** 0.5
            step = d - prev[i] if i in prev else 0.0
            prev[i] = d
            if abs(step) > 1e-9:
                moved += abs(step)
            parts.append("m%d:%.2f %+.2f" % (i, d, step))
        print("  %4.2f | %8s | %s | %2d | %2d" % (t, hp, "  ".join(parts), arrows, tnts))
        time.sleep(0.5)
    hp1 = scalar(r, '@e[tag=azs_v,limit=1]')
    dmg = (hp0 - hp1) if (hp0 is not None and hp1 is not None) else None
    print("  → 受伤 %s / 累计位移 %.1f 格" % (dmg, moved))
    return dmg, moved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--y", type=float, default=120.0)
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    r = Rcon()
    setup(r, args.y)
    res = {}
    for variant, label in ((0, "弓手 archer"), (1, "爆破兵 sapper")):
        if args.only and args.only not in label:
            continue
        res[label] = run(r, variant, label, args.y, args.seconds, args.count)
    r.cmd("kill @e[tag=azs_mob]")
    r.cmd("kill @e[tag=azs_v]")
    r.close()
    print("\n=== 汇总 ===")
    for k, v in res.items():
        print("  %-14s 伤害=%s  位移=%.1f" % (k, v[0], v[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
