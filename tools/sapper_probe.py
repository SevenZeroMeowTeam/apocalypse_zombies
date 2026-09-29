# -*- coding: utf-8 -*-
"""「军装僵尸的两种兵各干各的活」的运行时判据（headless 服务端 + RCON）。

要证的两件事，静态都看不出来（代码编译得过、日志干净）：

    ① 爆破兵手里那包 TNT 是**看得见**的，而且他真的会「点燃 → 抛出去」
    ② 两种兵**不串门**：爆破兵不射箭、弓手不丢 TNT

第 ② 条是本轮的原始缺陷：两个远程 Goal 原来都不判变种，于是弓手也在丢 TNT、爆破兵也在
射箭（贴图却是两种兵）。第 ① 条只能靠运行时看：可见性在客户端渲染层（按变种显隐骨骼），
抛出去的东西是服务端实体 —— 一边要在图里看，一边要在世界里数。

口径纪律：
1. **变种必须显式指定**，不能靠 finalizeSpawn 抽签（50% 概率会让「弓手相」跑出 TNT，
   读成假红）。变种现在落盘（存盘键 AzVariant），所以 summon 时直接写进 NBT 就是确定的。
2. **判据是实体计数**：`primed_tnt` 与 `arrow` 的数量 —— 谁在丢/谁在射，数得出来，
   不靠「看起来像」。
3. **目标要真的够得着且看得见**：铁傀儡放在 9 格外（投掷射程 4~14、弓手射程内），
   且给它 NoAI —— 不让它跑来跑去把几何搞乱。

用法：
    python tools/sapper_probe.py --variant sapper --seconds 30
    python tools/sapper_probe.py --variant archer --seconds 30
"""
import argparse
import random
import socket
import struct
import sys
import time

SOLDIER = "apocalypse_zombies:soldier_zombie"
GOLEM = "minecraft:iron_golem"
# 两个点都必须在墙内（墙在 x,z = ±8）：第一版把铁傀儡放在 z=9.0 —— 墙外、走不到，
# 于是兵拿不到目标，整场只有那个世界性的 2 血/秒在掉血，读数全是假的。
SOLDIER_AT = (0.0, 100.0, -5.0)
GOLEM_AT = (0.0, 100.0, 5.0)
CLEAN = "kill @e[x=-32,y=72,z=-32,dx=64,dy=56,dz=64,type=!player]"


class Rcon:
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

    # TNT 实体的注册 id 是 `minecraft:tnt`（不是 primed_tnt —— 第一版就栽在这个名字上，
    # 于是「一颗都没丢」读成了模组的缺陷，实际是探针查错了实体）。
    # 计数一律限定在竞技场立方体内：`@e[type=arrow]` 数的是全世界，会数到场外怪的箭。
    ARENA = "x=-32,y=72,z=-32,dx=64,dy=56,dz=64"

    def count_in_arena(self, type_id):
        return self.count("@e[type=%s,%s]" % (type_id, self.ARENA))

    def count(self, selector):
        out = self.cmd("execute if entity %s" % selector)
        if "Test failed" in out:
            return 0
        digits = "".join(ch for ch in out.split("count:")[-1] if ch.isdigit())
        return int(digits) if digits else 0

    def health(self, selector):
        out = self.cmd("data get entity %s Health" % selector)
        for tok in out.replace("f", " ").split():
            try:
                return float(tok)
            except ValueError:
                pass
        return None

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def setup(rcon, tag, variant_id):
    for c in ("gamerule doMobSpawning false", "gamerule doDaylightCycle false",
              "gamerule mobGriefing false", "gamerule doMobLoot false",
              "difficulty hard", "time set noon", "weather clear",
              CLEAN,
              "forceload add -16 -16 16 16",
              "fill -8 99 -8 8 99 8 minecraft:stone",
              "fill -8 100 -8 8 106 8 minecraft:stone",
              "fill -7 100 -7 7 105 7 minecraft:air"):
        rcon.cmd(c)
    rcon.cmd("summon %s %s %s %s {PersistenceRequired:1b,AzVariant:%db,Tags:[\"%s\"]}"
             % ((SOLDIER,) + tuple("%.1f" % v for v in SOLDIER_AT) + (variant_id, tag)))
    rcon.cmd("summon %s %s %s %s {NoAI:1b,Silent:1b,PersistenceRequired:1b,Tags:[\"golem\"]}"
             % ((GOLEM,) + tuple("%.1f" % v for v in GOLEM_AT)))
    time.sleep(0.8)


def run(variant, seconds, step, trace=False):
    variant_id = 1 if variant == "sapper" else 0
    tag = "sol" + "%04d" % random.randint(0, 9999)
    rcon = Rcon()
    setup(rcon, tag, variant_id)

    soldier = "@e[tag=%s,limit=1]" % tag
    alive = rcon.count("@e[tag=%s]" % tag)
    print("=" * 78)
    print("变种 %s（AzVariant=%d）  时长 %ds" % (variant, variant_id, seconds))
    if not alive:
        print("  ⚠ 兵没起来 —— 探针自身没跑通，判据无效")
        rcon.close()
        return False

    tnt_seen, arrow_seen, tnt_total = 0, 0, 0
    golem_hp0 = rcon.health("@e[tag=golem,limit=1]")
    t0 = time.time()
    now = 0.0
    while now < seconds:
        now = time.time() - t0
        tnt = rcon.count_in_arena("minecraft:tnt")
        arrows = rcon.count_in_arena("minecraft:arrow")
        tnt_total += tnt
        if tnt and trace:
            print("  %6.1fs  场上 TNT=%d 箭=%d" % (now, tnt, arrows))
        tnt_seen = max(tnt_seen, tnt)
        arrow_seen = max(arrow_seen, arrows)
        time.sleep(step)

    golem_hp1 = rcon.health("@e[tag=golem,limit=1]")
    print("  出现过的 TNT 峰值 %d；箭峰值 %d" % (tnt_seen, arrow_seen))
    print("  铁傀儡血量 %s → %s" % (golem_hp0, golem_hp1))
    if variant == "sapper":
        ok = tnt_seen >= 1 and arrow_seen == 0
    else:
        ok = arrow_seen >= 1 and tnt_seen == 0
    print("  ⇒ %s" % ("通过" if ok else "不通过"))
    rcon.cmd("kill @e[tag=%s]" % tag)
    rcon.cmd("kill @e[tag=golem]")
    rcon.cmd("kill @e[type=minecraft:tnt]")
    rcon.close()
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, choices=["sapper", "archer"])
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--step", type=float, default=0.5)
    ap.add_argument("--trace", action="store_true")
    a = ap.parse_args()
    sys.exit(0 if run(a.variant, a.seconds, a.step, a.trace) else 1)


if __name__ == "__main__":
    main()
