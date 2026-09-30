#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""骸骨射手「骨矢锁定」在真服务端上的验收 —— 走 RCON 打真目标，不靠读代码猜。

要证的五件事（每一件都能被「编译过、日志干净、游戏里却没生效」骗过去）：
  1. 无视护甲 / 保护附魔 / 抗性：目标穿满保护 IV 下界合金甲 + 抗性 V，一发 bone_lock
     该掉多少掉多少（标签级：`/damage` 直接打这个伤害类型，不经过 AI 与弹体）；
  2. 对照组：同数值的**普通**伤害在同样满防具下几乎被吃光 —— 证明 1 里的满额不是巧合；
  3. 技能真的会自己放：把射手丢到目标 10 格外，它起手并真的射出一支 bone_lock_arrow；
  4. 命中伤害 = 目标最大血量 × 0.25，且**无视无敌帧**：整段观测期用 `minecraft:generic`
     每 0.1 秒压一次无敌帧（该伤害在满防具下掉 0 血，所以不污染测量），骨矢落点仍然必须
     恰好掉 25.0 —— 1.20.1 的 hurt() 在 invulnerableTime > 10 时只结算「本次 − 上次」的
     差额（实测：先挨 1 点，骨矢 25 只掉 24.0），而这个分支没有任何 DamageTypeTags 能
     跳过（bypasses_cooldown 是 1.20.5+ 才加的），只有实体侧清零计数器才做得到。
  5. **看得见、走不到的目标也必须开火**：靶子放到 3 格高的石柱顶上（有视线、`createPath`
     的终点永远在地面 ⇒ 判据算「走不到」），射手仍必须在 45 秒内起手并射出骨矢。
     这条判据是**先红后绿**写出来的：修之前实测 45 秒一箭不放（目标表被空转占死），
     给调度器加上实体自选的「看得见就能打」射程之后才转绿。骨矢本身的伤害不看这条
     （第 4 条已经证过），这里只看**它有没有被允许开火**。

平台搭在 y=100、三格高屏障围墙的封闭斗场里（spawn 强加载区内），坐标全写死。
**围墙不是装饰**：射手自带 KeepDistanceGoal（7~18 格），没墙它会自己走下台子掉到地面，
之后既没视线也没法寻路，表现为「技能不放 / 放了不掉血」—— 三个 FAIL 全是这么来的。
**区域清场也不是装饰**：斗场里留着上一轮测试的 Boss（碰撞箱极大、常带 Invulnerable）
会把每一发骨矢都吃掉，同样表现成「放了技能却不掉血」。

用法：python tools/rcon_marksman_test.py
口令只从 run/server.properties 读取，不打印、不落盘。
"""
import os
import re
import socket
import struct
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROPERTIES = os.path.join(ROOT, "run", "server.properties")

TARGET_TAG = "BL_TGT"
GOLEM = "@e[tag=%s,limit=1]" % TARGET_TAG
ARROW = "apocalypse_zombies:bone_lock_arrow"
MARKSMAN = "apocalypse_zombies:marksman_skeleton"
PLATFORM = (0, 100, 0)
GOLEM_POS = (0, 101, 0)
MARKSMAN_POS = (10, 101, 0)
GEAR = {"head": "netherite_helmet", "chest": "netherite_chestplate",
        "legs": "netherite_leggings", "feet": "netherite_boots"}

# 第 5 条判据用的柱顶靶：地面在 y=100，柱子 101..103（3 格），靶子站 104。
# 3 格是精心选的：`PreyJudge.canPathTo` 的高度容差是 1 格，柱子再矮一格（2 格）就可能被判成
# 「走得到」（原版台阶/跳跃能上下），判据就不红了；再高也不会更红。
PILLAR_H = 3
PILLAR_TOP = (0, 101 + PILLAR_H, 0)


# --------------------------------------------------------------------------- RCON
def read_properties():
    props = {}
    with open(PROPERTIES, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                props[key.strip()] = value.strip()
    return props


class Rcon:
    def __init__(self, host, port, password, timeout=10.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        self.next_id = 1
        self._send(3, password)
        pid, _, _ = self._recv()
        if pid == -1:
            raise SystemExit("RCON 鉴权失败（口令不对）")

    def _send(self, ptype, body):
        payload = struct.pack("<ii", self.next_id, ptype) + body.encode("utf-8") + b"\x00\x00"
        self.sock.sendall(struct.pack("<i", len(payload)) + payload)
        self.next_id += 1

    def _recv(self):
        raw = b""
        while len(raw) < 4:
            raw += self.sock.recv(4 - len(raw))
        (length,) = struct.unpack("<i", raw)
        body = b""
        while len(body) < length:
            body += self.sock.recv(length - len(body))
        pid, ptype = struct.unpack("<ii", body[:8])
        return pid, ptype, body[8:-2].decode("utf-8", "replace")

    def cmd(self, command):
        self._send(2, command)
        _, _, text = self._recv()
        return text.strip()

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


# --------------------------------------------------------------------------- 工具
def health(rcon, who=GOLEM):
    """读实体血量；读不到返回 None。"""
    out = rcon.cmd("data get entity %s Health" % who)
    m = re.search(r"([-0-9.]+)[fd]?$", out.strip())
    return float(m.group(1)) if m else None


def max_health(rcon, who=GOLEM):
    """读最大血量。优先 /attribute：`/data get ... Attributes` 的响应很长会被截断，
    正则一失效就静默返回 None（判据跟着一起废）。两种字段顺序都兜一下。"""
    out = rcon.cmd("attribute %s minecraft:generic.max_health get" % who)
    m = re.search(r"value is ?([-0-9.]+)", out) or re.search(r"([-0-9.]+)\s*$", out)
    if m:
        return float(m.group(1))
    out = rcon.cmd("data get entity %s Attributes" % who)
    for pattern in (r'Base: ?([-0-9.]+)d?, ?Name: ?"minecraft:generic\.max_health"?',
                    r'Name: ?"minecraft:generic\.max_health"?, ?Base: ?([-0-9.]+)'):
        m = re.search(pattern, out)
        if m:
            return float(m.group(1))
    return None


def has_arrow(rcon):
    return "Test passed" in rcon.cmd("execute if entity @e[type=%s]" % ARROW)


def results(rows):
    print()
    print("=" * 84)
    print("骸骨射手「骨矢锁定」服务端实测 · tools/rcon_marksman_test.py")
    print("=" * 84)
    for name, ok, detail in rows:
        print("  %-28s %-5s %s" % (name, "PASS" if ok else "FAIL", detail))
    fails = [r for r in rows if not r[1]]
    print("-" * 84)
    print("合计 PASS %d / FAIL %d" % (len(rows) - len(fails), len(fails)))
    return 1 if fails else 0


class IFrameRefresher(threading.Thread):
    """后台把目标按在无敌帧里：每 0.1 秒打 1 点 minecraft:generic（独立 RCON 连接）。

    这一点伤害对满防具 + 抗性 V 的目标掉 0 血（对照组已证），所以不污染血量测量；
    它唯一的作用是让 hurt() 永远走「invulnerableTime > 10 ⇒ 只补差额」那一条分支。
    """

    def __init__(self, host, port, password, target):
        super().__init__(daemon=True)
        self.host, self.port, self.password, self.target = host, port, password, target
        self.stop_flag = threading.Event()
        self.hits = 0

    def run(self):
        try:
            rc = Rcon(self.host, self.port, self.password)
        except OSError:
            return
        try:
            while not self.stop_flag.is_set():
                rc.cmd("damage %s 1 minecraft:generic" % self.target)
                self.hits += 1
                self.stop_flag.wait(0.1)
        finally:
            rc.close()

    def stop(self):
        self.stop_flag.set()
        self.join(timeout=3)


def main():
    props = read_properties()
    port = int(props.get("rcon.port", "25575"))
    password = props.get("rcon.password", "")
    if not password:
        print("FAIL：run/server.properties 里没有 rcon.password")
        return 1
    try:
        rcon = Rcon("127.0.0.1", port, password)
    except OSError as exc:
        print("FAIL：连不上 RCON 127.0.0.1:%d（%s）—— 服务端起了吗？" % (port, exc))
        return 1

    rows = []
    rcon.cmd("gamerule sendCommandFeedback true")
    rcon.cmd("gamerule doMobLoot false")
    rcon.cmd("gamerule mobGriefing false")

    # ---------------------------------------------------------------- 布置
    print("布置：清场 → 搭台 → 目标 + 满防具 + 抗性 V")
    rcon.cmd("kill @e[type=%s]" % ARROW)
    rcon.cmd("kill @e[type=%s]" % MARKSMAN)
    rcon.cmd("kill @e[tag=%s]" % TARGET_TAG)
    # 区域清场：斗场半径内的所有非玩家实体。留着上一轮测试的 Boss（碰撞箱极大且常带
    # Invulnerable）会把每一发骨矢都吃掉，表现成「技能放了、目标不掉血」—— 实测踩过。
    rcon.cmd("kill @e[x=-24,y=90,z=-24,dx=48,dy=40,dz=48,type=!minecraft:player]")
    time.sleep(0.4)
    x, y, z = PLATFORM
    rcon.cmd("fill %d %d %d %d %d %d minecraft:stone" % (x - 4, y, z - 4, x + 12, y, z + 4))
    # 三格高屏障围墙：射手有 KeepDistanceGoal（7~18 格），没墙会自己走下台子掉到地面，
    # 之后既没视线也没法寻路 —— 三个 FAIL 全是这么来的，不是技能的问题。
    rcon.cmd("fill %d 101 %d %d 103 %d minecraft:barrier" % (x - 4, z - 4, x + 12, z - 4))
    rcon.cmd("fill %d 101 %d %d 103 %d minecraft:barrier" % (x - 4, z + 4, x + 12, z + 4))
    rcon.cmd("fill %d 101 %d %d 103 %d minecraft:barrier" % (x - 4, z - 4, x - 4, z + 4))
    rcon.cmd("fill %d 101 %d %d 103 %d minecraft:barrier" % (x + 12, z - 4, x + 12, z + 4))
    gx, gy, gz = GOLEM_POS
    rcon.cmd('summon minecraft:iron_golem %d %d %d {NoAI:1b,PersistenceRequired:1b,'
             'Tags:["%s"]}' % (gx, gy, gz, TARGET_TAG))
    time.sleep(0.5)
    for slot, item in GEAR.items():
        rcon.cmd('item replace entity %s armor.%s with minecraft:%s{Enchantments:['
                 '{id:"minecraft:protection",lvl:4}]}' % (GOLEM, slot, item))
    rcon.cmd("effect give %s minecraft:resistance 6000 4 true" % GOLEM)
    time.sleep(0.4)

    hp_max = max_health(rcon)
    hp0 = health(rcon)
    armor = rcon.cmd("data get entity %s ArmorItems" % GOLEM)
    print("     目标血量 %s（上限 %s）；防具：%s" %
          (hp0, hp_max, "已装备" if "netherite" in armor else "未装备（检查命令）"))

    # ---------------------------------------------------------------- 1) 标签级：护甲/附魔/抗性
    expected = round((hp_max or 100.0) * 0.25, 3)
    rcon.cmd("damage %s 25 apocalypse_zombies:bone_lock" % GOLEM)    # 此刻无 i-frames 干扰
    time.sleep(0.3)
    now = health(rcon)
    drop_tag = None if (hp0 is None or now is None) else round(hp0 - now, 3)
    rows.append(("无视护甲/附魔/抗性（标签级）",
                 drop_tag is not None and abs(drop_tag - 25.0) < 0.01,
                 "满防具 + 抗性 V 下打 25 点 bone_lock → 掉 %s（应恰好 25.0；标签没生效会只剩个位数）"
                 % drop_tag))

    # 满防具 + 抗性 V 下普通伤害应当几乎被吃掉，作为对照（证明防具确实生效）
    before = health(rcon)
    time.sleep(1.2)                                             # 等 i-frames 过
    rcon.cmd("damage %s 25 minecraft:generic" % GOLEM)
    time.sleep(0.3)
    after_v = health(rcon)
    drop_vanilla = None if (before is None or after_v is None) else round(before - after_v, 3)
    rows.append(("对照组：同数值普通伤害",
                 drop_vanilla is not None and drop_vanilla < 25.0,
                 "同样打 25 点普通伤害只掉 %s（防具/抗性真的在减伤，所以上面的 25 不是巧合）" % drop_vanilla))

    # ---------------------------------------------------------------- 3+4) 技能自放 + 伤害/无敌帧
    mx, my, mz = MARKSMAN_POS
    rcon.cmd("summon %s %d %d %d {PersistenceRequired:1b}" % (MARKSMAN, mx, my, mz))
    time.sleep(0.5)
    refresher = IFrameRefresher("127.0.0.1", port, password, GOLEM)
    refresher.start()                                               # 全程压着 i-frames
    time.sleep(0.3)
    saw_arrow = False
    biggest_drop = 0.0
    last_hp = health(rcon)
    deadline = time.time() + 60
    while time.time() < deadline:
        if has_arrow(rcon):
            saw_arrow = True
        hp_now = health(rcon)
        if hp_now is not None and last_hp is not None:
            biggest_drop = max(biggest_drop, round(last_hp - hp_now, 3))
            last_hp = hp_now
        if biggest_drop > 1.0:                                      # 已经看见这一发落地
            break
        time.sleep(0.25)
    refresher.stop()
    rows.append(("技能自行释放（射出骨矢）", saw_arrow,
                 "观察到 %s 实体：%s（观测期压制无敌帧 %d 次，单发最大掉血 %s）"
                 % (ARROW, "是" if saw_arrow else "否（60s 内没放技能）",
                    refresher.hits, "无" if biggest_drop <= 0 else biggest_drop)))
    rows.append(("命中伤害 = 血量 × 0.25 且无视无敌帧",
                 abs(biggest_drop - expected) < 0.01,
                 "无敌帧压满时单发掉血 %s（期望恰好 %s；只走差额结算的话会少掉「上次伤害」的 1.0）"
                 % (biggest_drop, expected)))

    # ---------------------------------------------------------------- 5) 柱顶靶：看得见、走不到
    # 这条判据针对的是**目标调度**而不是技能本身：射手对「看得见但走不到」的猎物原来会空转占死
    # 目标表（一箭不放）。修法是给调度器加实体自选的「看得见就能打」射程。
    print("第 5 条：靶子挪到 3 格石柱顶（有视线、判据算走不到），射手仍须开火")
    rcon.cmd("kill @e[type=%s]" % MARKSMAN)
    rcon.cmd("kill @e[type=%s]" % ARROW)
    rcon.cmd("kill @e[tag=%s]" % TARGET_TAG)
    time.sleep(0.5)
    rcon.cmd("fill %d %d %d %d %d %d minecraft:stone"
             % (x, y + 1, z, x, y + PILLAR_H, z))
    tx, ty, tz = PILLAR_TOP
    # 柱顶这只没有防具，得用 NBT 抬血量 —— 否则会被同一只射手的重箭打死，判据变成「靶死了」
    # 而不是「没开火」。
    rcon.cmd('summon minecraft:iron_golem %d %d %d {NoAI:1b,PersistenceRequired:1b,'
             'Health:600f,Attributes:[{Name:"minecraft:generic.max_health",Base:600}],'
             'Tags:["%s"]}' % (tx, ty, tz, TARGET_TAG))
    print("     靶子：%s（立柱 %d 格）；射手：%s"
          % (PILLAR_TOP, PILLAR_H, MARKSMAN_POS))
    t0 = time.time()
    rcon.cmd("summon %s %d %d %d {PersistenceRequired:1b}" % (MARKSMAN, mx, my, mz))
    saw_pillar_arrow = False
    while time.time() - t0 < 45:
        if has_arrow(rcon):
            saw_pillar_arrow = True
            break
        time.sleep(0.25)
    rows.append(("看得见走不到也开火（柱顶靶）", saw_pillar_arrow,
                 "%.1fs 内射出骨矢（靶子在柱顶、`createPath` 终点只到地面）"
                 % (time.time() - t0) if saw_pillar_arrow
                 else "45s 内一箭不放 —— 目标表被「走不到」的猎物空转占死（这条就是修前现场）"))

    rcon.cmd("kill @e[type=%s]" % MARKSMAN)
    rcon.cmd("kill @e[type=%s]" % ARROW)
    rcon.cmd("kill @e[tag=%s]" % TARGET_TAG)
    rcon.cmd("fill %d %d %d %d %d %d minecraft:air"
             % (x, y + 1, z, x, y + PILLAR_H, z))
    rcon.cmd("fill %d %d %d %d %d %d minecraft:air" % (x - 4, y, z - 4, x + 12, y, z + 4))
    rcon.cmd("fill %d 101 %d %d 103 %d minecraft:air" % (x - 4, z - 4, x + 12, z + 4))
    rcon.close()
    return results(rows)


if __name__ == "__main__":
    sys.exit(main())
