# -*- coding: utf-8 -*-
"""临时取证：目标死亡后，怪物还能不能再锁一个「新」目标并打上去？

为什么这么测：玩家死亡 = 怪物的目标对象变成「死了的实体」，随后玩家重生是一个**新实体**。
在无客户端的服务端上，把这件事同构成「村民#1 被杀死 → 立刻在原地放村民#2」：
判据与目标类型无关（{@code PreyTargetGoal} 只认「活着的可用猎物」），所以如果怪在这条
同构链上卡住不复锁，就是「玩家死后怪不打人」的同一根因。

判据：
  * victim#2 掉血 ⇒ 复锁成功（TARGET 通道没被死目标占死）
  * victim#2 血量不动、怪在附近发呆/乱走 ⇒ 复锁失败（死目标把通道占死）
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


def scalar(rcon, selector, path="Health"):
    out = rcon.cmd("data get entity %s %s" % (selector, path))
    m = R.search(out)
    if not m:
        return None
    nums = re.findall(r"-?\d+\.?\d*[dDfF]?", m.group(1))
    return float(nums[0].rstrip("dDfF")) if nums else None


def vec(rcon, selector):
    out = rcon.cmd("data get entity %s Pos" % selector)
    m = R.search(out)
    if not m:
        return None
    nums = re.findall(r"-?\d+\.?\d*[dDfF]?", m.group(1))
    try:
        return [float(n.rstrip("dDfF")) for n in nums]
    except ValueError:
        return None


def summon_victim(rcon, tag, x, y, z, custom):
    rcon.cmd('summon minecraft:villager %f %f %f {NoAI:1b,Silent:1b,PersistenceRequired:1b,'
             'CustomName:\'"%s"\',Tags:["%s"]}' % (x, y, z, custom, tag))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=45.0)
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--distance", type=float, default=14.0)
    ap.add_argument("--y", type=float, default=120.0)
    args = ap.parse_args()

    rcon = Rcon()
    y, cx, cz = args.y, 0.0, 0.0

    rcon.cmd("gamerule doMobSpawning false")
    rcon.cmd("gamerule doMobLoot false")
    rcon.cmd("gamerule mobGriefing false")
    rcon.cmd("gamerule doDaylightCycle false")
    rcon.cmd("difficulty easy")
    rcon.cmd("time set midnight")
    rcon.cmd("forceload add -32 -32 32 32")
    for dy in (0, 1):
        rcon.cmd("fill %d %d %d %d %d %d minecraft:stone"
                 % (-17, int(y) - 1 - dy, -17, 17, int(y) - 1 - dy, 17))
    rcon.cmd("fill -17 %d -17 17 %d 17 minecraft:air" % (int(y), int(y) + 3))
    rcon.cmd("kill @e[type=!minecraft:player,distance=..64]")

    summon_victim(rcon, "azp_v1", cx, y, cz, "victim1")
    for i in range(args.count):
        rcon.cmd('summon minecraft:zombie %f %f %f {PersistenceRequired:1b,Silent:1b,'
                 'CustomName:\'"m%d"\',Tags:["azp_mob"]}' % (-args.distance, y, i * 4.0 - 4.0, i))
    time.sleep(1.0)

    print("phase 1 —— 打活村民（基线，必须掉血）")
    hp1 = scalar(rcon, '@e[tag=azp_v1,limit=1]')
    print("  victim1 hp start: %s" % hp1)
    t0 = time.time()
    while time.time() - t0 < 25:
        hp = scalar(rcon, '@e[tag=azp_v1,limit=1]')
        if hp is None:
            print("  victim1 hp: 已死亡/移除（用了 %.1fs）" % (time.time() - t0))
            break
        if hp < (hp1 or 20.0) - 0.01:
            print("  victim1 hp: %s  ← 挨打了，基线通过" % hp)
            break
        time.sleep(0.25)
    else:
        print("  victim1 hp: 未掉血  ← 基线不成立，后续判据无意义")

    # 清场重来：保证「死目标」是唯一变量 —— 直接把吸血鬼杀掉，怪物手里留着它的尸体引用
    rcon.cmd("kill @e[tag=azp_v1]")
    time.sleep(1.0)
    print("\nphase 2 —— victim#1 已死，原地放 victim#2，看怪会不会复锁")
    summon_victim(rcon, "azp_v2", cx, y, cz, "victim2")
    time.sleep(0.5)
    hp2 = scalar(rcon, '@e[tag=azp_v2,limit=1]')
    print("  victim2 hp start: %s" % hp2)

    prev = {}
    t0 = time.time()
    hit_at = None
    while time.time() - t0 < args.seconds:
        hp = scalar(rcon, '@e[tag=azp_v2,limit=1]')
        line = "  t=%5.2f hp=%s" % (time.time() - t0, hp)
        for i in range(args.count):
            pos = vec(rcon, '@e[tag=azp_mob,name=m%d,limit=1]' % i)
            if pos is None:
                continue
            dist = ((pos[0] - cx) ** 2 + (pos[2] - cz) ** 2) ** 0.5
            step = ""
            if i in prev:
                step = " step=%.2f" % (((pos[0] - prev[i][0]) ** 2 + (pos[2] - prev[i][2]) ** 2) ** 0.5)
            prev[i] = pos
            line += "  m%d:%.2f%s" % (i, dist, step)
        if hp is not None and hp < (hp2 or 20.0) - 0.01 and hit_at is None:
            hit_at = time.time() - t0
            line += "   ←←← victim2 掉血了：复锁成功"
        if hp is None and hit_at is not None:
            print(line)
            print("  victim2 被打死（%.1fs）—— 复锁整条链通过" % (time.time() - t0))
            break
        print(line)
        time.sleep(0.5)

    print("\n结论：%s" % ("复锁成功（死目标没有占死 TARGET 通道）" if hit_at is not None
                        else "复锁失败 —— 怪物在 victim2 旁边但一下都不打"))
    rcon.cmd("kill @e[tag=azp_mob]")
    rcon.cmd("kill @e[tag=azp_v2]")
    rcon.close()
    return 0 if hit_at is not None else 1


if __name__ == "__main__":
    sys.exit(main())
