# -*- coding: utf-8 -*-
"""临时取证：怪物「行走 / 攻击」在无玩家服务端上的可测量判据。

为什么这么测：`SurroundGoal` 每 40 tick 才重发一次 moveTo（走完就停在那儿等下一拍），
而它又占着 MOVE 标记 —— 如果它霸着通道不放手，僵尸会呈现「走两步停一下」并且永远
走不进近战距离（不会攻击）。这两件事都能从**位置-时间曲线**上读出来：
  * 匀速推进 ⇒ 每拍位移接近常数
  * 走走停停 ⇒ 位移序列出现 0 值台阶
  * 霸占 MOVE 不交还 ⇒ 距离长时间停在 engage(=6) 附近不肯收敛

判据：每 0.25 秒采一次位置与受害者血量，跑 N 秒。
"""
import argparse
import re
import socket
import struct
import sys
import time

R = re.compile(r"has the following entity data: (.+)")


class Rcon:
    def __init__(self, host="127.0.0.1", port=25575, password="hermesprobe", timeout=10.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        self.rid = 0
        self._send(3, password)
        self._recv()

    def _send(self, kind, body):
        self.rid += 1
        payload = struct.pack("<ii", self.rid, kind) + body.encode("utf-8") + b"\x00\x00"
        self.sock.sendall(struct.pack("<i", len(payload)) + payload)
        return self.rid

    def _recv(self):
        raw = self.sock.recv(4)
        if len(raw) < 4:
            return ""
        length = struct.unpack("<i", raw)[0]
        data = b""
        while len(data) < length:
            chunk = self.sock.recv(length - len(data))
            if not chunk:
                break
            data += chunk
        return data[8:-2].decode("utf-8", "replace")

    def cmd(self, command):
        self._send(2, command)
        return self._recv()

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def vec(rcon, selector, path="Pos"):
    out = rcon.cmd("data get entity %s %s" % (selector, path))
    m = R.search(out)
    if not m:
        return None
    nums = re.findall(r"-?\d+\.?\d*[dDfF]?", m.group(1))
    try:
        return [float(n.rstrip("dDfF")) for n in nums]
    except ValueError:
        return None


def scalar(rcon, selector, path):
    out = rcon.cmd("data get entity %s %s" % (selector, path))
    m = R.search(out)
    if not m:
        return None
    nums = re.findall(r"-?\d+\.?\d*[dDfF]?", m.group(1))
    return float(nums[0].rstrip("dDfF")) if nums else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=16.0)
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--distance", type=float, default=14.0)
    ap.add_argument("--y", type=float, default=100.0)
    ap.add_argument("--mob", default="minecraft:zombie")
    ap.add_argument("--keep-mobs", action="store_true")
    args = ap.parse_args()

    rcon = Rcon()
    y = args.y
    cx, cz = 0.0, 0.0

    # ---- 场地：34x34 石台，避免地形干扰判据
    rcon.cmd("gamerule doMobSpawning false")
    rcon.cmd("gamerule doMobLoot false")
    rcon.cmd("gamerule mobGriefing false")
    rcon.cmd("gamerule doDaylightCycle false")
    rcon.cmd("gamerule doWeatherCycle false")
    rcon.cmd("difficulty easy")
    rcon.cmd("time set midnight")
    rcon.cmd("forceload add -32 -32 32 32")
    for dy in (0, 1):
        rcon.cmd("fill %d %d %d %d %d %d minecraft:stone"
                 % (-17, int(y) - 1 - dy, -17, 17, int(y) - 1 - dy, 17))
    rcon.cmd("fill -17 %d -17 17 %d 17 minecraft:air" % (int(y), int(y) + 3))
    rcon.cmd("kill @e[type=!minecraft:player,distance=..64]")

    # ---- 受害者：NoAI 村民（看得见、走得到，唯一合法猎物）
    # 血量拉到 4000 —— 目的是让它**打不死**：这样怪物必须持续「走到身边并挥击」，
    # 「走不进去 / 走进去又退出」都会留在位置-时间曲线上，不会因为猎物秒死而掩盖症状。
    victim = "azprobe_victim"
    rcon.cmd('summon minecraft:villager %f %f %f {NoAI:1b,Silent:1b,PersistenceRequired:1b,'
             'CustomName:\'"victim"\',Health:4000.0f,'
             'Attributes:[{Name:"generic.max_health",Base:4000}],Tags:["%s"]}' % (cx, y, cz, victim))

    # ---- 被观察的怪：N 只，同一条线上等距铺开（避免互相挡路干扰判据）
    for i in range(args.count):
        zx = -args.distance
        zz = -(args.count - 1) * 2.0 + i * 4.0
        rcon.cmd('summon %s %f %f %f {PersistenceRequired:1b,Silent:1b,'
                 'Tags:["azprobe_mob"],CustomName:\'"m%d"\',CustomNameVisible:0b}'
                 % (args.mob, zx, y, zz, i))

    time.sleep(1.0)
    print("mobs alive: %s" % rcon.cmd("execute if entity @e[tag=azprobe_mob] run say ok"))
    print("victim hp : %s" % scalar(rcon, '@e[tag=%s,limit=1]' % victim, "Health"))

    t0 = time.time()
    prev = {}
    print("\n t(s) | victimhp | mob | dist | step")
    print("-" * 44)
    while time.time() - t0 < args.seconds:
        hp = scalar(rcon, '@e[tag=%s,limit=1]' % victim, "Health")
        elapsed = time.time() - t0
        pos = None
        for i in range(args.count):
            # 用 CustomName 精确定位单只
            pos = vec(rcon, '@e[tag=azprobe_mob,name=m%d,limit=1]' % i, "Pos")
            if pos is None:
                continue
            dist = ((pos[0] - cx) ** 2 + (pos[2] - cz) ** 2) ** 0.5
            step = ""
            if i in prev:
                step = "%.3f" % (((pos[0] - prev[i][0]) ** 2 + (pos[2] - prev[i][2]) ** 2) ** 0.5)
            prev[i] = pos
            print("%5.2f | %8s | m%d  | %5.2f | %s" % (elapsed, hp, i, dist, step))
        time.sleep(0.25)

    print("\nfinal victim hp: %s" % scalar(rcon, '@e[tag=%s,limit=1]' % victim, "Health"))
    if not args.keep_mobs:
        rcon.cmd("kill @e[tag=azprobe_mob]")
        rcon.cmd("kill @e[tag=%s]" % victim)
    rcon.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
