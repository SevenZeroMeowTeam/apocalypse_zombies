#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""猫耳娘「全功能工具 + 一键挖掘 + 去工作方块」铁证探针（1.1.78）。

和不看代码的 1.1.77 探针一个思路：只认**世界里真的变了什么** ——
她库存（CatGirlGoods）多了什么、场上的方块少了几个。

    阶段 M · 全功能工具 / 一键挖掘
        给她一把**木镐**（故意最低档），场地摆 3×3 钻石矿，下单 4 块
        期望：矿石少 4 格、**钻石进她库存**（木镐也挖得下钻石矿 = 按方块该用的工具结算掉落）

    阶段 B · 保护名单
        场地摆 3×3 基岩，下单 4 块
        期望：一块都挖不动（订单对保护名单里的方块不成立），她也不崩

    阶段 S · 工作方块
        只给原木（她自己得先做木板、再攒出合成台）
        期望：场地里**出现她自己放下的合成台**，并用它做出成品工具

几个踩过的坑（写在探针里，省得下次再踩）：

  1. 下单不能分两条 `data modify` 写：`CatGirlMineBlock` 只有在她「手上有订单且还没挖完」
     时才跟着存档走，先写方块名、下一条再写数量时，第二次 load() 看到的是**没有方块名的
     快照** → 走 else 分支把订单清掉。必须一条 `data merge entity <e> {...}` 一起写。
  2. 命令是 RCON 发的，执行点在原点：`@e[...,limit=1]` 取「离执行点最近的那只」，
     而场上有历次探针留下的猫耳娘（它们还会一只只往下掉）。tag 必须**每跑一次换一个**，
     否则写数据写给老的那只、读也读老的那只，整场跟鬼影说话。
  3. 场地要自己清出来、再铺**厚**地板（她自主挖矿会一路往下挖穿薄地板掉进洞里）。
  4. `execute if block` 数方块时 y 要显式给 —— 别拿新场地的 x/z 配老场地的 y，
     数出来的是上层残留的那批矿。

用法（游戏须完全关闭；服务端 ./gradlew runServer 起着，RCON 口令读 run/server.properties）：
    python tools/rcon_catgirl_mine_probe.py
"""
import glob
import os
import re
import socket
import struct
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROPERTIES = os.path.join(ROOT, "run", "server.properties")
LOG = os.path.join(ROOT, "run", "logs", "latest.log")
CRASH = os.path.join(ROOT, "run", "crash-reports")
REPORT = os.path.join(ROOT, "run", "catgirl_mine_probe_report.txt")

GIRL_TYPE = "apocalypse_zombies:cat_girl"
# tag 每跑一次、每个阶段都换一个（见文件头坑 2）：tag 会随实体进存档，
# 上一阶段的她（常常正卡在自己挖的洞里往下掉）如果同名，`limit=1` 取最近的，
# 就可能写数据写给老的、读也读老的那只。
TAG = "cg%s%d" % ("init", os.getpid())
GIRL = "@e[type=%s,tag=%s,limit=1]" % (GIRL_TYPE, TAG)

ARENA = (400, 120, 400)      # 自己清出来的一块空地（别用主城附近：有洞、有历次残留）
PLATFORM_DEPTH = 20          # 地板厚度：她自主挖矿会往下挖，薄地板会被挖穿掉走
HALF = 16                    # 场地半径
SAMPLE_INTERVAL = 1.5

JOB_NAMES = {0: "FOLLOW", 1: "LUMBER", 2: "MINE", 3: "FIGHT"}


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


def value(out):
    """把 `X has the following entity data: ...` 里的值抠出来。"""
    return out.split("data: ", 1)[1].strip() if "data: " in out else out


def goods(rcon):
    """读她库存（CatGirlGoods）→ {物品 id: 个数}。读不到返回 None。"""
    out = value(rcon.cmd("data get entity %s CatGirlGoods" % GIRL))
    if not out.startswith("["):
        return None
    counts = {}
    for item_id, count in re.findall(r'id:\s*"([^"]+)"[^}]*Count:\s*(\d+)b', out):
        counts[item_id] = counts.get(item_id, 0) + int(count)
    return counts


def give(rcon, items):
    """直接写她的库存（Slot 从 0 起）。items = [(id, count), ...]"""
    body = ",".join('{Slot:%db,id:"%s",Count:%db}' % (i, item_id, count)
                    for i, (item_id, count) in enumerate(items))
    rcon.cmd("data modify entity %s CatGirlGoods set value [%s]" % (GIRL, body))


def order(rcon, block_id, count):
    """下单：**一条 data merge** 写订单 + 切工种（见文件头坑 1）。

    为什么不用 `/apocalypse catgirl mine`：那条命令要玩家当执行者（找最近的主人），
    RCON 是控制台，没有玩家。写 NBT 走的是她的 load()，和读档接着挖是同一条路 ——
    命令那条路干了两件事：orderMine / setJob(MINE)，这里照做（数量上限由命令按配置夹，
    探针不测那一层）。

    工种必须一起写：WorkBlockGoal.canUse() 第一行就是「不是 MINE 工种就返回 false」。
    """
    rcon.cmd('data merge entity %s {CatGirlMineBlock:"%s",CatGirlMineLeft:%d,CatGirlJob:2}'
             % (GIRL, block_id, count))


def job(rcon):
    raw = value(rcon.cmd("data get entity %s CatGirlJob" % GIRL))
    return JOB_NAMES.get(int(raw), "?%s" % raw) if raw.isdigit() else "?"


def pos(rcon):
    out = value(rcon.cmd("data get entity %s Pos" % GIRL))
    nums = re.findall(r"(-?\d+\.\d+)d", out)
    return tuple(float(n) for n in nums[:3]) if len(nums) >= 3 else None


def fresh_girl(rcon, phase):
    """换一只干净的猫耳娘 + 清掉落物（上局的掉落物会被新那只捡走，断言会假绿）。

    每个阶段用**自己的 tag**（见文件头坑 2）—— 上一阶段那只常常正卡在自己挖的洞里，
    同名的话 `limit=1` 会读到它。
    """
    global TAG, GIRL
    TAG = "cg%s%d" % (phase, os.getpid())
    GIRL = "@e[type=%s,tag=%s,limit=1]" % (GIRL_TYPE, TAG)
    x, y, z = ARENA
    for tagged in ("init", "M", "B", "S"):
        rcon.cmd("kill @e[type=%s,tag=cg%s%d]" % (GIRL_TYPE, tagged, os.getpid()))
    time.sleep(0.4)
    # 每阶段重铺地板：上一阶段那只常常已经挖出一条竖井，直接在她头上召唤会掉进井里
    # （曾经读到 y=116.6 的召唤后位置 —— 那不是「场地有问题」，是上一阶段的洞）。
    box_fill(rcon, "minecraft:stone", x - HALF, y - PLATFORM_DEPTH, z - HALF, x + HALF, y - 1, z + HALF)
    box_fill(rcon, "minecraft:air", x - HALF, y, z - HALF, x + HALF, y + 7, z + HALF)
    time.sleep(0.5)
    rcon.cmd("execute positioned %d %d %d run kill @e[type=minecraft:item,distance=..64]" % (x, y, z))
    rcon.cmd("execute positioned %d %d %d run kill @e[type=minecraft:xp_orb,distance=..64]" % (x, y, z))
    time.sleep(0.3)
    rcon.cmd('summon %s %d %d %d {PersistenceRequired:1b,Tags:["%s"]}' % (GIRL_TYPE, x, y, z, TAG))
    time.sleep(1.0)
    rcon.cmd("tp %s %d %d %d" % (GIRL, x, y, z))       # 站定（别让她从别处飘过来）
    time.sleep(0.5)
    here = pos(rcon)
    if here is None or max(abs(here[0] - x), abs(here[1] - y), abs(here[2] - z)) > 3:
        raise SystemExit("场地异常：召唤后她在 %s，不在 %s —— 先查场地，别拿这种数据下结论。"
                         % (here, ARENA))


def cell(cx, cz, half=1, y=None):
    """算出 (2*half+1)² 的方块坐标。"""
    y = ARENA[1] if y is None else y
    return [(x, y, z)
            for x in range(cx - half, cx + half + 1)
            for z in range(cz - half, cz + half + 1)]


def place(rcon, block_id, coords):
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    zs = [c[2] for c in coords]
    rcon.cmd("fill %d %d %d %d %d %d %s"
             % (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs), block_id))


def box_fill(rcon, block_id, x1, y1, z1, x2, y2, z2):
    rcon.cmd("fill %d %d %d %d %d %d %s" % (x1, y1, z1, x2, y2, z2, block_id))


def count_at(rcon, block_id, coords):
    """逐格 `execute if block` 数还有几格是这种方块。"""
    n = 0
    for (x, y, z) in coords:
        if "passed" in rcon.cmd("execute if block %d %d %d %s" % (x, y, z, block_id)).lower():
            n += 1
    return n


def clear_count(rcon, block_id, x1, y1, z1, x2, y2, z2):
    """把盒子里的这种方块全换成空气，返回换掉了几个。

    比逐格 `execute if block` 快一个数量级（一条命令扫完整个盒子），
    而且不依赖「她一定站在台子旁边」。
    """
    out = rcon.cmd("fill %d %d %d %d %d %d minecraft:air replace %s"
                   % (x1, y1, z1, x2, y2, z2, block_id))
    m = re.search(r"(\d+) block", out)
    return int(m.group(1)) if m else 0


def sample(rcon, seconds, emit, label="库存"):
    """采样：返回 (最后一拍, 见过的物品 id 集合, 每样物品的峰值个数)。"""
    last, seen, peak = None, set(), {}
    for i in range(int(seconds / SAMPLE_INTERVAL)):
        time.sleep(SAMPLE_INTERVAL)
        counts = goods(rcon)
        if counts is None:
            emit("  !! 读不到她的库存（她还在吗？）")
            continue
        last = counts
        seen.update(counts)
        for item_id, count in counts.items():
            peak[item_id] = max(peak.get(item_id, 0), count)
        summary = " ".join("%s x%d" % (k.split(":")[-1], v) for k, v in sorted(counts.items()))
        p = pos(rcon)
        emit("  t+%4.1fs  %s：%s%s"
             % ((i + 1) * SAMPLE_INTERVAL, label, summary or "（空）",
                "" if p is None else "  | 位置 (%.0f,%.0f,%.0f)" % p))
    return last, seen, peak


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
    rcon.cmd("kill @e[type=%s]" % GIRL_TYPE)              # 历次探针留下的野猫耳娘
    rcon.cmd("forceload add %d %d %d %d" % (x - 40, z - 40, x + 40, z + 40))
    rcon.cmd("gamerule doMobLoot false")
    rcon.cmd("gamerule doMobSpawning false")
    rcon.cmd("gamerule doDaylightCycle false")
    rcon.cmd("gamerule randomTickSpeed 0")
    rcon.cmd("gamerule doTileDrops true")                 # 掉落要真掉，才看得出来
    rcon.cmd("time set noon")
    # 场地：厚石头地板 + 清空上半部
    box_fill(rcon, "minecraft:stone", x - HALF, y - PLATFORM_DEPTH, z - HALF, x + HALF, y - 1, z + HALF)
    box_fill(rcon, "minecraft:air", x - HALF, y, z - HALF, x + HALF, y + 7, z + HALF)
    time.sleep(1.0)

    emit("=" * 100)
    emit("猫耳娘「全功能工具 / 一键挖掘 / 工作方块」探针（1.1.78）")
    emit("=" * 100)
    emit("只认两件事：她库存真的多了什么（CatGirlGoods）、场上方块真的少了几个。")
    emit("场地：(%d,%d,%d) 起 %d×%d，地板厚 %d 格（她自主挖矿会往下挖，薄了会掉走）；"
         "这只用 tag `%s` 钉住。" % (x, y, z, HALF * 2 + 1, HALF * 2 + 1, PLATFORM_DEPTH, TAG))
    emit()
    verdicts = []

    # ---------------- 阶段 M：木镐 + 钻石矿订单 ----------------
    emit("-" * 100)
    emit("阶段 M · 全功能工具：给她**木镐**，下单挖钻石矿 x4（原版木镐挖钻石矿 = 一个都不掉）")
    emit("-" * 100)
    fresh_girl(rcon, "M")
    ores = cell(x + 3, z + 1, half=1, y=y)
    place(rcon, "minecraft:diamond_ore", ores)
    give(rcon, [("minecraft:wooden_pickaxe", 1)])
    emit("  场地：%d 格钻石矿 @ (%d..%d, %d, %d..%d)；她的工具：木镐"
         % (len(ores), x + 2, x + 4, y, z, z + 2))
    emit("  起始库存：%s" % " ".join("%s x%d" % (k.split(":")[-1], v)
                                     for k, v in sorted((goods(rcon) or {}).items())))
    order(rcon, "minecraft:diamond_ore", 4)
    time.sleep(0.5)
    emit("  下单：minecraft:diamond_ore x4（一条 data merge：方块名 + 剩 4 + 工种 MINE）")
    emit("  回读：方块=%s 剩=%s 工种=%s"
         % (value(rcon.cmd("data get entity %s CatGirlMineBlock" % GIRL)),
            value(rcon.cmd("data get entity %s CatGirlMineLeft" % GIRL)), job(rcon)))
    after, seen, peak = sample(rcon, 60, emit)
    if after is None:
        emit("  !! 采样期间读不到她的库存 —— 阶段 M 无效")
        rcon.close()
        return 1
    left = count_at(rcon, "minecraft:diamond_ore", ores)
    # 认「钻石类物品」而不是只认 minecraft:diamond：她会把刚到手的三颗钻石当场做成钻石靴
    # （t+13.5s 那一拍就是 diamond_boots x1），再只盯钻石个数会把自己骗成 FAIL。
    got = peak.get("minecraft:diamond", 0)
    diamond_items = sorted(i for i in peak if i.startswith("minecraft:diamond"))
    emit()
    m1 = left < len(ores)
    m2 = got > 0 or bool(diamond_items)
    m3 = "minecraft:diamond" in seen
    emit("  M1 矿石真的少了：%d → %d 格  %s"
         % (len(ores), left, "通过" if m1 else "**失败：一格都没挖**"))
    emit("  M2 **钻石进了她库存**（木镐也挖得下）：钻石峰值 %d 个%s  %s"
         % (got, ("，还见过 " + " ".join(diamond_items)) if diamond_items else "",
            "通过" if m2 else "**失败：没有钻石 = 全功能工具/掉落没生效**"))
    emit("  M3 全程见过钻石（不只是最后一拍）：%s" % ("通过" if m3 else "**失败**"))
    verdicts += [("M1 挖得动", m1), ("M2 有掉落（木镐）", m2), ("M3 全程见过", m3)]

    # ---------------- 阶段 B：保护名单 ----------------
    emit()
    emit("-" * 100)
    emit("阶段 B · 保护名单：场地摆 3×3 基岩，下单挖基岩 x4")
    emit("-" * 100)
    fresh_girl(rcon, "B")
    beds = cell(x + 3, z + 1, half=1, y=y)
    place(rcon, "minecraft:bedrock", beds)
    order(rcon, "minecraft:bedrock", 4)
    emit("  场地：%d 格基岩；下单：minecraft:bedrock x4" % len(beds))
    sample(rcon, 20, emit)
    beds_left = count_at(rcon, "minecraft:bedrock", beds)
    emit()
    b1 = beds_left == len(beds)
    emit("  B1 一块基岩都没少：%d/%d  %s"
         % (beds_left, len(beds), "通过" if b1 else "**失败：她挖到基岩了**"))
    verdicts += [("B1 基岩挖不动", b1)]

    # ---------------- 阶段 S：工作方块 ----------------
    emit()
    emit("-" * 100)
    emit("阶段 S · 工作方块：只给原木（她得先做木板，再凑出合成台）")
    emit("-" * 100)
    fresh_girl(rcon, "S")
    # 场地里早就有的台子先清掉 —— 否则 S1 找到的是上一局留下的，断言假绿
    rcon.cmd("fill %d %d %d %d %d %d minecraft:air replace minecraft:crafting_table"
             % (x - HALF, y - 1, z - HALF, x + HALF, y + 3, z + HALF))
    rcon.cmd("fill %d %d %d %d %d %d minecraft:air replace minecraft:furnace"
             % (x - HALF, y - 1, z - HALF, x + HALF, y + 3, z + HALF))
    rcon.cmd("execute positioned %d %d %d run kill @e[type=minecraft:item,distance=..64]" % (x, y, z))
    give(rcon, [("minecraft:oak_log", 12)])
    emit("  起始库存：oak_log x12（场地里旧的合成台/熔炉已清干净）")
    after_s, seen_s, _ = sample(rcon, 75, emit)
    # 台子检测用 fill-replace 数（一条命令扫全盒子，比她脚边逐格问快得多；
    # 盒子往地下延伸到 y-PLATFORM_DEPTH：她常一路挖下去，台子可能在她挖的竖井底）。
    table = clear_count(rcon, "minecraft:crafting_table", x - HALF, y - PLATFORM_DEPTH, z - HALF,
                        x + HALF, y + 4, z + HALF)
    furnace = clear_count(rcon, "minecraft:furnace", x - HALF, y - PLATFORM_DEPTH, z - HALF,
                          x + HALF, y + 4, z + HALF)
    emit()
    s1 = table > 0 or furnace > 0
    emit("  S1 场地里出现她自己放的工作方块：合成台 %d 个、熔炉 %d 个  %s"
         % (table, furnace, "通过" if s1 else "**失败：没自己搭台子**"))
    s2 = any(re.search(r"_(pickaxe|axe|sword|shovel|hoe)$", i) for i in seen_s)
    emit("  S2 做出了成品工具：%s" % ("通过" if s2 else "**失败：没做出工具**"))
    s3 = any(i.endswith("_planks") or i == "minecraft:stick" for i in seen_s)
    emit("  S3 会自己做中间材料（木板/木棍）：%s" % ("通过" if s3 else "**失败**"))
    verdicts += [("S1 自己搭台子", s1), ("S2 做出工具", s2), ("S3 中间材料", s3)]

    # ---------------- 日志 / 崩溃 ----------------
    emit()
    emit("-" * 100)
    bad = []
    try:
        with open(LOG, encoding="utf-8", errors="replace") as fh:
            tail = fh.readlines()[-4000:]
        for line in tail:
            if re.search(r"cat_girl.*(Exception|Error)", line) or "自动制作/熔炼这一拍失败" in line:
                bad.append(line.strip()[:200])
    except OSError:
        pass
    new_crash = sorted(set(glob.glob(os.path.join(CRASH, "crash-*.txt"))) - crash_before)
    d1, d2 = not bad, not new_crash
    emit("  D1 她自己的异常行：%s" % ("没有" if d1 else "%d 行（见下）" % len(bad)))
    for line in bad[:5]:
        emit("      %s" % line)
    emit("  D2 新增 crash-report：%s" % ("没有" if d2 else new_crash))
    verdicts += [("D1 无异常", d1), ("D2 无崩溃", d2)]

    emit()
    emit("=" * 100)
    ok = sum(1 for _, v in verdicts if v)
    emit("结论：%d/%d 通过" % (ok, len(verdicts)))
    for name, v in verdicts:
        emit("  %s %s" % ("[OK  ]" if v else "[FAIL]", name))
    emit("=" * 100)

    with open(REPORT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("报告：%s" % REPORT)
    rcon.cmd("kill @e[type=%s,tag=%s]" % (GIRL_TYPE, TAG))
    rcon.cmd("save-all flush")
    rcon.close()
    return 0 if ok == len(verdicts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
