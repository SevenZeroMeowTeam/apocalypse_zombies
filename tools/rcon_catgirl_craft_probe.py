#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""猫耳娘「自己做材料 / 自己做物品」铁证探针。

为什么要有这个探针：这功能以前的验收只看代码 —— 结果 1.1.76 实测她在有原木有圆石的情况下
**一件东西都做不出来**（石镐要木棍，木棍不在白名单里，她连木板都不会劈）。所以这里不看代码，
只看**她库存里真的多出来了什么**：道具的进出全走 NBT（CatGirlGoods），一条断言绑一个副作用。

两个阶段，各自独立（阶段间杀她重召，避免上一阶段的装备干扰「同类只做最好的那件」）：

    阶段 A · 合成链：给 原木 12 + 圆石 12
        期望：出现木板/木棍（**她会自己做材料**），并出现木/石质成品（镐/斧/剑/锹/锄）
        期望：原木 或 圆石 的总数下降（材料真的被吃掉了，不是凭空变出来的）

    阶段 B · 熔炼链：给 铁矿 9 + 煤 6 + 原木 6
        期望：出现铁锭（内部熔炉真的烧了）
        期望：出现铁质成品（铁镐/铁斧/铁剑…）—— 这条要**先烧锭再做出成品**，两层都得通

另外读日志：出现 "cat_girl 自动制作/熔炼这一拍失败" 或新的 crash-report 就是 FAIL。

用法（游戏须完全关闭，服务端由 ./gradlew runServer 起着）：
    python tools/rcon_catgirl_craft_probe.py
"""
import glob
import os
import re
import socket
import struct
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROPERTIES = os.path.join(ROOT, "run", "server.properties")
LOG = os.path.join(ROOT, "run", "logs", "latest.log")
CRASH = os.path.join(ROOT, "run", "crash-reports")
REPORT = os.path.join(ROOT, "run", "catgirl_craft_probe_report.txt")

GIRL_TYPE = "apocalypse_zombies:cat_girl"
GIRL = "@e[type=%s,limit=1]" % GIRL_TYPE
ARENA = (0, 101, 0)

PLANKS = re.compile(r"minecraft:\w*_?planks")
TOOLISH = re.compile(r"_(pickaxe|axe|sword|shovel|hoe)$")
TOOLISH_SUFFIX = re.compile(r"_(pickaxe|axe|sword|shovel|hoe)$")
IRON_TOOL = re.compile(r"minecraft:iron_(pickaxe|axe|sword|shovel|hoe)$")
WOODSTONE_TOOL = re.compile(r"minecraft:(wooden|stone)_(pickaxe|axe|sword|shovel|hoe)$")

# 「越烧越亏」的产物：她不该把玩家给的方块料烧成石头/平滑石，更不该把自己的装备烧成粒。
# 1.1.76 实测她在干这两件事 —— 这条断言就是给它上锁。
WASTE = re.compile(r"minecraft:(stone|smooth_stone|deepslate|charcoal|"
                   r"\w+_nugget|brick|nether_brick|glass|terracotta)$")

SAMPLE_INTERVAL = 1.5


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
    def __init__(self, host, port, password, timeout=30.0):
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


def goods(rcon):
    """读她库存（CatGirlGoods）→ {物品 id: 个数}。她不在场上返回 None。

    注意：原版 `data get` 只回值、**不回路径名**（形如
    `Cat Girl has the following entity data: [{id: "minecraft:oak_log", Count: 12b}]`），
    所以这里不能靠 "CatGirlGoods" 这个字样判断，只能靠「有没有解析出错」。
    """
    out = rcon.cmd("data get entity %s CatGirlGoods" % GIRL)
    if "No entity was found" in out or "No such element" in out or "Unable to" in out:
        return None
    counts = {}
    for item_id, count in re.findall(r'\{[^}]*id:\s*"([^"]+)"[^}]*Count:\s*(\d+)b', out):
        counts[item_id] = counts.get(item_id, 0) + int(count)
    return counts


def give(rcon, items):
    """直接写她的库存（Slot 从 0 起）。items = [(id, count), ...]"""
    body = ",".join('{Slot:%db,id:"%s",Count:%db}' % (i, item_id, count)
                    for i, (item_id, count) in enumerate(items))
    rcon.cmd("data modify entity %s CatGirlGoods set value [%s]" % (GIRL, body))


def fresh_girl(rcon):
    """换一只干净的猫耳娘，并且**把场地清干净**。

    为什么必须清场：上一只被 kill 时会把库存掉一地，新的这只走两步就全捡起来 ——
    实测 1.5 秒内"手里凭空多出 7 个铁锭 + 1 把铁剑"，于是「她会不会自己烧铁」这种
    断言全被地上的垃圾骗过去了（连 B4 报的那 1 个铁粒也是上局的掉落物，不是她烧的）。
    """
    rcon.cmd("kill @e[type=%s]" % GIRL_TYPE)
    time.sleep(0.4)
    rcon.cmd("execute positioned %d %d %d run kill @e[type=minecraft:item,distance=..64]"
             % tuple(ARENA))
    time.sleep(0.4)
    rcon.cmd("summon %s %d %d %d {PersistenceRequired:1b}" % (GIRL_TYPE, *ARENA))
    time.sleep(1.0)


def total(counts, pred):
    return sum(n for item_id, n in counts.items() if pred(item_id))


def has(counts, pred):
    return any(pred(item_id) for item_id in counts)


def sample(rcon, seconds, emit):
    """采样：每 SAMPLE_INTERVAL 打一行她库存的摘要。

    返回 (最后一拍 counts, 全程出现过的 id 集合) —— 断言必须看**全程**：
    她做出来的东西可能下一秒就被消耗（木板变成木棍、工具上手持），只看最后一拍会误判成"没做"。
    """
    last = None
    seen = set()
    rounds = int(seconds / SAMPLE_INTERVAL)
    for i in range(rounds):
        time.sleep(SAMPLE_INTERVAL)
        counts = goods(rcon)
        if counts is None:
            emit("  !! 读不到她的库存（她还在吗？）")
            continue
        last = counts
        seen.update(counts)
        summary = " ".join("%s x%d" % (k.split(":")[-1], v)
                           for k, v in sorted(counts.items()))
        emit("  t+%4.1fs  %s" % ((i + 1) * SAMPLE_INTERVAL, summary or "（空）"))
    return last, seen


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

    crash_before = set(glob.glob(os.path.join(CRASH, "crash-*.txt")))
    lines = []

    def emit(text=""):
        print(text)
        lines.append(text)

    x, y, z = ARENA
    rcon.cmd("gamerule doMobLoot false")
    rcon.cmd("gamerule doDaylightCycle false")
    rcon.cmd("gamerule doMobSpawning false")
    rcon.cmd("gamerule randomTickSpeed 0")
    rcon.cmd("time set noon")
    rcon.cmd("forceload add -32 -32 32 32")
    rcon.cmd("fill %d %d %d %d %d %d minecraft:stone"
             % (x - 16, y - 1, z - 16, x + 16, y - 1, z + 16))
    time.sleep(0.5)

    emit("=" * 100)
    emit("猫耳娘「自己做材料 / 自己做物品」探针")
    emit("=" * 100)
    emit("她库存 = CatGirlGoods（NBT），本探针只认它；服务端每 40t 跑一次 auto_craft、每 60t 跑一次 smelt。")
    emit()

    verdicts = []

    # ---------------- 阶段 A：原木 + 圆石 → 木板/木棍 → 木/石装备 ----------------
    emit("-" * 100)
    emit("阶段 A · 合成链：原木 12 + 圆石 12（她**没有**木板也没有木棍，得自己做出来）")
    emit("-" * 100)
    fresh_girl(rcon)
    give(rcon, [("minecraft:oak_log", 12), ("minecraft:cobblestone", 12)])
    base = goods(rcon) or {}
    emit("  起始库存：%s" % " ".join("%s x%d" % (k.split(":")[-1], v)
                                     for k, v in sorted(base.items())))
    after, seen = sample(rcon, 45, emit)
    if after is None:
        emit("  !! 采样期间读不到她的库存 —— 她没在场上，阶段 A 无效")
        rcon.close()
        return 1

    logs_before = base.get("minecraft:oak_log", 0)
    logs_after = after.get("minecraft:oak_log", 0)
    cobble_before = base.get("minecraft:cobblestone", 0)
    cobble_after = after.get("minecraft:cobblestone", 0)
    emit()
    a1 = any(PLANKS.search(i) or i == "minecraft:stick" for i in seen)
    emit("  A1 她自己做出了中间材料（木板 / 木棍）：%s"
         % ("通过" if a1 else "**失败：一块木板一根木棍都没有**"))
    a2 = any(WOODSTONE_TOOL.search(i) for i in seen)
    emit("  A2 做出了木/石质成品（镐/斧/剑/锹/锄）：%s"
         % ("通过" if a2 else "**失败：没有成品**"))
    a3 = (logs_after < logs_before) or (cobble_after < cobble_before)
    emit("  A3 材料真的被吃掉了（原木 %d→%d、圆石 %d→%d）：%s"
         % (logs_before, logs_after, cobble_before, cobble_after,
            "通过" if a3 else "**失败：材料一个没少，东西却多出来了**"))
    a4 = not any(WASTE.search(i) for i in seen)
    emit("  A4 没有拿玩家的方块料做减法（石头/平滑石/炭/粒…）：%s"
         % ("通过" if a4 else "**失败：出现了 %s**"
            % sorted(i for i in seen if WASTE.search(i))))
    # A5：她自己那份要的是「摘有摘的、劈有劈的、打有打的」—— 不能做出一件就收手。
    # 1.1.76 实测：她做出 1 把铁锹之后 50 秒不动（料够、镐斧剑一件没做）。
    got_kinds = {m.group(1) for i in seen for m in [TOOLISH_SUFFIX.search(i)] if m}
    a5 = {"pickaxe", "axe", "sword"} <= got_kinds
    emit("  A5 镐/斧/剑 都做出来了（不是做一件就收手）：%s（做出过 %s）"
         % ("通过" if a5 else "**失败：只有 %s**" % sorted(got_kinds), sorted(got_kinds)))
    verdicts += [("A1 自己做材料", a1), ("A2 自己做成品", a2),
                 ("A3 材料被消耗", a3), ("A4 不烧玩家的方块料", a4),
                 ("A5 镐斧剑齐活", a5)]
    emit()

    # ---------------- 阶段 B：铁矿 + 煤 + 原木 → 铁锭 → 铁装备 ----------------
    emit("-" * 100)
    emit("阶段 B · 熔炼链：铁矿 9 + 煤 6 + 原木 6（铁锭她自己烧，烧完还得做出成品）")
    emit("-" * 100)
    fresh_girl(rcon)
    give(rcon, [("minecraft:iron_ore", 9), ("minecraft:coal", 6), ("minecraft:oak_log", 6)])
    base = goods(rcon) or {}
    emit("  起始库存：%s" % " ".join("%s x%d" % (k.split(":")[-1], v)
                                     for k, v in sorted(base.items())))
    after, seen = sample(rcon, 60, emit)
    if after is None:
        emit("  !! 采样期间读不到她的库存 —— 她没在场上，阶段 B 无效")
        rcon.close()
        return 1
    emit()
    b1 = after.get("minecraft:iron_ingot", 0) > 0 or "minecraft:iron_ingot" in seen
    emit("  B1 铁锭是她自己烧出来的（全程出现过铁锭）：%s"
         % ("通过" if b1 else "**失败：一个铁锭都没有**"))
    b2 = any(IRON_TOOL.match(i) for i in seen)
    emit("  B2 做出了铁质成品（先烧锭、再做成件，两层都通）：%s"
         % ("通过" if b2 else "**失败：没有铁制成品**"))
    b3 = after.get("minecraft:iron_ore", 0) < base.get("minecraft:iron_ore", 0)
    emit("  B3 铁矿被消耗（%d→%d）：%s"
         % (base.get("minecraft:iron_ore", 0), after.get("minecraft:iron_ore", 0),
            "通过" if b3 else "**失败：矿石没动**"))
    b4 = not any(WASTE.search(i) for i in seen)
    emit("  B4 没有把成品/方块料烧成下脚料（粒/炭/石头…）：%s"
         % ("通过" if b4 else "**失败：出现了 %s**"
            % sorted(i for i in seen if WASTE.search(i))))
    verdicts += [("B1 自己烧锭", b1), ("B2 自己做出铁装备", b2),
                 ("B3 矿石被消耗", b3), ("B4 不烧自己的装备", b4)]
    emit()

    # ---------------- 日志 & crash ----------------
    emit("-" * 100)
    emit("日志 / 崩溃检查")
    emit("-" * 100)
    bad = 0
    if os.path.exists(LOG):
        with open(LOG, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        n = text.count("cat_girl 自动制作/熔炼这一拍失败")
        bad += n
        emit("  「自动制作/熔炼这一拍失败」出现 %d 次：%s" % (n, "通过" if n == 0 else "**失败**"))
    crash_after = set(glob.glob(os.path.join(CRASH, "crash-*.txt"))) - crash_before
    emit("  %d 个新 crash-report（服务端没被带走）：%s"
         % (len(crash_after), "通过" if not crash_after else "**失败：%s**" % sorted(crash_after)))
    verdicts += [("C1 无自动制作异常", bad == 0), ("C2 无新崩溃", not crash_after)]

    emit()
    emit("=" * 100)
    ok = all(v for _, v in verdicts)
    for name, passed in verdicts:
        emit("  %s %s" % ("[OK  ]" if passed else "[FAIL]", name))
    emit("=" * 100)
    emit("结论：%s" % ("全部通过 —— 她会自己做材料、自己做物品、自己烧锭了" if ok else "**有断言没过，见上**"))

    with open(REPORT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("\n报表已落盘：%s" % REPORT)
    rcon.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
