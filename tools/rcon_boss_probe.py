#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""尸潮之主铁证探针（1.1.46：轮转「死槽位」死锁修复 + 四个新技能）。

每条断言都绑一个 RCON 能读到的副作用，不读私有字段、不靠翻日志：

    阶段机      /apocalypse boss 直接念 phase / cast / entry / rot / rage / wail / starved
    横扫        傀儡掉血
    踏地        傀儡吃 MOVEMENT_SLOWDOWN 且掉血
    骨刺        场上出现 apocalypse_zombies:giant_arrow
    召唤        场上僵尸数 +5（封顶 5）
    亡语        傀儡吃 WITHER + 僵尸变多 + **血怒那 4 条 buff 必须还在**
    尸笼坠击    出现 giant_arrow（6 根垂直落下）+ 傀儡吃 slowness
    汲魂        傀儡吃 WEAKNESS + **Boss 自己回血**
    疫雾        场上出现 minecraft:area_effect_cloud 实体
    尸潮尖啸    傀儡吃 BLINDNESS + 僵尸数 +3

两个坑（都踩过，别再犯）：
1. `ActiveEffects` 的 NBT 里 Id 是 `Id: 5`，**没有 `b` 后缀**。写成 `Id:(\\d+)b` 永远匹配不到，
   会把「有 buff」误报成「无 buff」。
2. 别用一次性大伤害跨阶段：多段 `damage` 求和会一击秒杀 Boss，阶段机来不及走。
   本探针只做「一次性掉到目标区间」，采样期间不再补刀。

用法：python tools/rcon_boss_probe.py
"""
import os
import re
import socket
import struct
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROPERTIES = os.path.join(ROOT, "run", "server.properties")
REPORT = os.path.join(ROOT, "run", "boss_probe_report.txt")

BOSS_TYPE = "apocalypse_zombies:horde_overlord"
BOSS = "@e[type=%s,limit=1]" % BOSS_TYPE
GOLEM = "@e[type=minecraft:iron_golem,limit=1]"
ARENA = (0, 100, 0)

#: 铁傀儡离 Boss 的水平距离（格）。2 格 = 近战距离：骨刺齐射的「≥4 格」永远不成立，
#: 正是 1.1.46 修的那个死锁场景。
GOLEM_OFFSET = 2

#: buff id → 名字（1.20.1 的 MobEffect id），只为报表好读
EFFECT_NAMES = {1: "speed", 2: "slowness", 5: "strength", 11: "resistance", 12: "fire_res",
                15: "blindness", 18: "weakness", 19: "poison", 20: "wither"}

#: 血怒（Phase 3 入场）应当留下的四条
RAGE_BUFFS = {"strength", "speed", "resistance", "fire_res"}

SAMPLE_INTERVAL = 0.5
SAMPLE_COUNT = 180

#: Phase 3 轮转表里贴脸时应当出现的招（骨刺齐射够不着，本来就该被跳过）
EXPECTED = ["BOSS_SWEEP", "GROUND_QUAKE", "RAISE_HORDE", "CAGE_SLAM", "SOUL_DRAIN",
            "PLAGUE_MIST", "HORDE_SCREECH", "DEATH_WAIL"]


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
    def __init__(self, host, port, password, timeout=20.0):
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


def scalar(rcon, who, field):
    m = re.search(r":\s*([-0-9.]+)", rcon.cmd("data get entity %s %s" % (who, field)))
    return float(m.group(1)) if m else None


def effects(rcon, who):
    """返回 (原始串, {效果名})。Id 形如 `Id: 5`，无 b 后缀。"""
    out = rcon.cmd("data get entity %s ActiveEffects" % who)
    ids = [int(x) for x in re.findall(r"\bId:\s*(\d+)", out)]
    return out, {EFFECT_NAMES.get(i, "id%d" % i) for i in ids}


def count(rcon, selector):
    """选择器命中多少实体。`execute if entity` 的反馈里带 count。"""
    out = rcon.cmd("execute if entity %s" % selector)
    m = re.search(r"count:\s*(\d+)", out)
    if m:
        return int(m.group(1))
    return 1 if "Test passed" in out else 0


def parse_status(rcon):
    """`/apocalypse boss` → dict（阶段机的唯一读出口，见 HordeOverlord.debugStatus()）。"""
    out = rcon.cmd("apocalypse boss")
    m = re.search(r"phase=(\d+)/(\d+) hp=([\d.]+)/([\d.]+) cast=(\w+)@(-?\d+) entry=(\w+) "
                  r"rot=(\d+)/(\d+) rage=(\w+) wail=(\w+) starved=(\d+)", out)
    if not m:
        return None
    return {"phase": int(m.group(1)), "hp": float(m.group(3)), "max_hp": float(m.group(4)),
            "cast": m.group(5), "entry": m.group(7), "rot": int(m.group(8)),
            "rot_len": int(m.group(9)), "rage": m.group(10) == "true",
            "wail": m.group(11) == "true", "starved": int(m.group(12))}


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
        print("FAIL：连不上 RCON 127.0.0.1:%d（%s）" % (port, exc))
        return 1

    lines = []

    def emit(text=""):
        print(text)
        lines.append(text)

    x, y, z = ARENA
    for sel in ("@e[type=%s]" % BOSS_TYPE, "@e[type=minecraft:iron_golem]",
                "@e[type=minecraft:zombie]", "@e[type=apocalypse_zombies:giant_arrow]",
                "@e[type=minecraft:area_effect_cloud]"):
        rcon.cmd("kill %s" % sel)
    rcon.cmd("gamerule doMobLoot false")
    rcon.cmd("gamerule doDaylightCycle false")
    rcon.cmd("time set noon")
    rcon.cmd("fill %d %d %d %d %d %d minecraft:stone" % (x - 16, y, z - 16, x + 16, y, z + 16))
    time.sleep(0.5)
    rcon.cmd("summon %s %d %d %d {PersistenceRequired:1b}" % (BOSS_TYPE, x, y + 1, z))
    rcon.cmd("summon minecraft:iron_golem %d %d %d {NoAI:1b,PersistenceRequired:1b,Invulnerable:0b,"
             "Health:4000f,Attributes:[{Name:\"minecraft:generic.max_health\",Base:4000}]}"
             % (x + GOLEM_OFFSET, y + 1, z))
    time.sleep(1.5)

    emit("=" * 100)
    emit("尸潮之主铁证探针 —— 轮转死锁修复 + 四个新技能")
    emit("=" * 100)
    emit("场景：Boss @ %s，铁傀儡贴到 +%d 格 —— 近战距离，骨刺齐射的 ≥4 格门槛永远不成立。"
         % (ARENA, GOLEM_OFFSET))
    emit("出生状态：%s" % rcon.cmd("apocalypse boss"))
    emit("")

    # ---- 一次性打到 Phase 3（1300 < 1400），等入场链跑完 ----
    rcon.cmd("damage %s 2900 minecraft:generic" % BOSS)
    emit("打到 1300/4200（Phase 3 区间），等入场链（Phase2 踏地 → Phase3 血怒）…")
    time.sleep(12)
    st = parse_status(rcon)
    if st is None:
        emit("FAIL：读不到 Boss 状态（服务端没起好？）")
        rcon.close()
        return 1
    _, boss_fx = effects(rcon, BOSS)
    emit("入场完成：phase=%d hp=%.1f rage=%s buff=%s"
         % (st["phase"], st["hp"], st["rage"], ",".join(sorted(boss_fx)) or "无"))
    if st["phase"] != 3:
        emit("!! 期望 phase=3，实际 %d —— 阶段机有问题" % st["phase"])
    emit("")

    # ---- 采样：贴脸 Phase 3 轮转 ----
    emit("采样 %d × %.1fs（贴脸 Phase 3 轮转；cast=NONE 连续超过 3s 视为卡死）"
         % (SAMPLE_COUNT, SAMPLE_INTERVAL))
    emit("%-6s %-14s %-6s %-8s %-8s %-26s %-6s %-4s %-5s %s"
         % ("t(s)", "cast", "rot", "starved", "BossHP", "傀儡buff", "骨刺", "雾", "僵尸", "傀儡HP"))
    seen = {}
    mute_run = 0
    mute_max = 0.0
    mute_at = 0.0
    first_starved = None
    for i in range(SAMPLE_COUNT):
        time.sleep(SAMPLE_INTERVAL)
        st = parse_status(rcon)
        if st is None:
            continue
        t = (i + 1) * SAMPLE_INTERVAL
        _, golem_fx = effects(rcon, GOLEM)
        golem_hp = scalar(rcon, GOLEM, "Health")
        arrows = count(rcon, "@e[type=apocalypse_zombies:giant_arrow]")
        clouds = count(rcon, "@e[type=minecraft:area_effect_cloud]")
        zombies = count(rcon, "@e[type=minecraft:zombie]")
        cast = st["cast"]
        if cast != "NONE" and cast not in seen:
            seen[cast] = t
        if st["starved"] and first_starved is None:
            first_starved = (t, st["starved"])
        if cast == "NONE":
            mute_run += 1
            if mute_run * SAMPLE_INTERVAL > mute_max:
                mute_max = mute_run * SAMPLE_INTERVAL
                mute_at = t
        else:
            mute_run = 0
        emit("%-6.1f %-14s %d/%-4d %-8d %-8.1f %-26s %-6d %-4d %-5d %s"
             % (t, cast, st["rot"], st["rot_len"], st["starved"], st["hp"],
                ",".join(sorted(golem_fx)) or "-", arrows, clouds, zombies,
                ("%.0f" % golem_hp) if golem_hp is not None else "死"))
        if st["hp"] <= 0:
            emit("!! Boss 被打死，终止采样")
            break

    # ---- 结算 ----
    emit("")
    emit("=" * 100)
    emit("结论")
    emit("=" * 100)
    emit("1) 轮转死锁：cast 连续为 NONE 的最长窗口 = %.1fs（t=%.1fs）" % (mute_max, mute_at))
    emit("   理论最坏值 = 技能间隔 24t(1.2s) + 干等上限 40t(2.0s) + 采样精度 0.5s = 3.7s")
    emit("   判定：> 4.0s 才算死锁（旧缺陷是 8~12s 且永不恢复）→ %s"
         % ("通过" if mute_max <= 4.0 else "**仍然卡死**"))
    emit("   死槽位跳过计数 starved：%s"
         % ("采样期间涨到 %d，说明「够不着就跳过」这条路真的走了" % first_starved[1]
            if first_starved else "全程为 0（贴脸时骨刺齐射应当被跳过才对）"))
    emit("")
    emit("2) Phase 3 出现的技能（%d 种）：" % len(seen))
    for name, t in sorted(seen.items(), key=lambda kv: kv[1]):
        emit("      %-14s 首次于 t=%.1fs" % (name, t))
    missing = [n for n in EXPECTED if n not in seen]
    emit("   应当出现：%s" % ("全部出现" if not missing else "缺 " + ",".join(missing)))
    emit("   （BONE_VOLLEY 贴脸够不着，本来就该被跳过）")
    emit("")

    # ---- 亡语 & 血怒 buff 存活 ----
    emit("-" * 100)
    emit("3) 亡语对照：把 Boss 打到 620（跨 630 亡语线），看 wail 是否触发、血怒 buff 是否被清")
    _, before = effects(rcon, BOSS)
    st = parse_status(rcon)
    if st is None:
        emit("   FAIL：读不到 Boss 状态")
        rcon.close()
        return 1
    emit("   亡语前：hp=%.1f wail=%s buff=%s" % (st["hp"], st["wail"], ",".join(sorted(before)) or "无"))
    # 补刀必须按「实际掉血」收敛：血怒带抗性 I，raw 伤害会被削 20%，
    # 按 1:1 算会停在 630 以上，亡语根本不会触发（踩过）。
    for _ in range(6):
        if st["hp"] <= 600 or st["wail"]:
            break
        hp_before = st["hp"]
        rcon.cmd("damage %s %d minecraft:generic" % (BOSS, int(hp_before - 600)))
        time.sleep(1.2)
        st = parse_status(rcon)
        if st is None:
            break
        emit("   补刀 %.0f → 实际掉到 %.1f（吸收 %.0f）"
             % (hp_before - 600, st["hp"], hp_before - 600 - (hp_before - st["hp"])))
    for k in range(14):
        time.sleep(1.0)
        st = parse_status(rcon)
        if st is None:
            break
        _, now = effects(rcon, BOSS)
        emit("   t+%-2ds hp=%-7.1f wail=%-5s cast=%-13s buff=%s"
             % (k + 1, st["hp"], st["wail"], st["cast"], ",".join(sorted(now)) or "无"))
        if st["wail"] and now:
            break
    _, after = effects(rcon, BOSS)
    emit("   亡语后 buff = %s" % (",".join(sorted(after)) or "无"))
    emit("   判定：%s（血怒那 4 条必须还在；被清光说明 removeAllEffects() 又回来了）"
         % ("通过" if RAGE_BUFFS <= after else "**血怒被清掉了：%s 丢失**"
            % ",".join(sorted(RAGE_BUFFS - after))))

    with open(REPORT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("\n报表已落盘：%s" % REPORT)
    rcon.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
