#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""玩家生命上限（Config.PLAYER_MAX_HEALTH）的静态校验。

为什么值得单开一个校验器：这条改动的失效方式全是**编译得过、上线才炸**的：

  * UUID 写成 `UUID.randomUUID()` —— 每次登录换一个 ID ⇒ 永久修饰符一路叠加，
    进三次游戏血量 20 → 100 → 180。编译没问题，测试也测不出（得多登录几次）。
  * 运算写成 `MULTIPLY_TOTAL` —— 不是「+80」而是「×5」，而且**乘在已经乘过的值上**，
    第二次登录 100 → 500。同一类错，后果更狠。
  * 修饰符用 `addTransientModifier` —— 存不进玩家 NBT，每次读档都重新套一遍。
  * 回血写成 `player.setHealth(getMaxHealth())` —— 每次进游戏白送一次满血治疗。
  * 忘了 `EVENT_BUS.register(CommonEvents.class)` —— `@SubscribeEvent` 根本不会触发，
    配置改了没反应，但日志里一个错都不报。

跑法：python tools/check_player_health.py
"""

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "src/main/java/com/apocalypse/zombies/Config.java")
EVENTS = os.path.join(ROOT, "src/main/java/com/apocalypse/zombies/event/CommonEvents.java")

VANILLA_BASE = 20
EXPECTED_DEFAULT = 100
EXPECTED_BONUS = EXPECTED_DEFAULT - VANILLA_BASE

failures = []
notes = []


def read(path):
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def need(cond, why):
    if cond:
        notes.append("OK   " + why)
    else:
        failures.append(why)


def find(pattern, text, group=1):
    m = re.search(pattern, text, re.S)
    return m.group(group) if m else None


def main():
    cfg = read(CONFIG)
    evt = read(EVENTS)

    # ---- Config：声明 + 定义 + 默认值 + 取值范围 -----------------------------
    need(re.search(r"ForgeConfigSpec\.IntValue\s+PLAYER_MAX_HEALTH", cfg),
         "Config 里有 PLAYER_MAX_HEALTH 字段")
    default = find(r'defineInRange\(\s*"player_max_health"\s*,\s*(\d+)', cfg)
    need(default is not None, "Config 里注册了 player_max_health 这个键")
    if default is not None:
        notes.append("     默认值 = %s" % default)
        need(int(default) == EXPECTED_DEFAULT,
             "默认值 = %d（期望 %d）" % (int(default), EXPECTED_DEFAULT))
    rng = re.search(r'defineInRange\(\s*"player_max_health"\s*,\s*[^,]+,\s*([\d.]+)\s*,\s*([\d.]+)', cfg)
    if rng:
        notes.append("     取值区间 = %s .. %s" % (rng.group(1), rng.group(2)))
        # 下界必须能填回原版值：填 20 = 关掉，否则玩家没法退回默认体验
        need(float(rng.group(1)) <= VANILLA_BASE,
             "区间下界 ≤ %d（填 %d 等于关闭这条改动）" % (VANILLA_BASE, VANILLA_BASE))
        need(float(rng.group(2)) >= 100,
             "区间上界 ≥ 100（否则默认值自己就越界）")

    # ---- 修饰符 ID 必须写死 ------------------------------------------------
    need("UUID.fromString(" in evt, "生命修饰符用写死的 UUID（UUID.fromString）")
    need("UUID.randomUUID(" not in evt,
         "没有用 UUID.randomUUID()（用了就会每次登录叠一层）")
    m = re.search(r'private static final UUID\s+\w*HEALTH\w*\s*=\s*\r?\n?\s*UUID\.fromString\("([^"]+)"\)', evt, re.S)
    need(m is not None, "能找到生命修饰符的 ID 常量声明")
    if m:
        notes.append("     修饰符 UUID = %s" % m.group(1))

    # ---- 运算方式与存续性 --------------------------------------------------
    need("AttributeModifier.Operation.ADDITION" in evt,
         "用 ADDITION 运算（MULTIPLY 会在已乘过的值上再乘，第二层就爆）")
    need("addPermanentModifier" in evt,
         "用 addPermanentModifier（transient 存不进玩家 NBT，每次读档重套）")

    # ---- 差值必须由「目标 - 原版基础值」算出来，不能写死 80 ----------------
    need(re.search(r"Config\.PLAYER_MAX_HEALTH\.get\(\)\s*-\s*\w+\.getBaseValue\(\)", evt),
         "差值按「配置值 - 属性基础值」算，而不是硬编码 %d" % EXPECTED_BONUS)
    need("getBaseValue" in evt, "读的是属性基础值（不是当前上限）")

    # ---- 两条事件链都要挂上 ------------------------------------------------
    need("PlayerLoggedInEvent" in evt, "登录事件里有挂钩")
    need(re.search(r"applyPlayerHealth\s*\(\s*player\s*\)", evt),
         "登录时调用 applyPlayerHealth")
    need(re.search(r"PlayerEvent\.Clone", evt),
         "挂了 Clone 事件（死亡重生 / 换维度会重建玩家实体，属性要重新确认）")
    need(re.search(r"@SubscribeEvent\s*\r?\n\s*public static void onPlayerClone", evt),
         "Clone 处理器带 @SubscribeEvent 注解")

    # ---- 血量按比例换算，不是无条件回满 ------------------------------------
    need(re.search(r"before\s*/\s*beforeMax", evt),
         "血量按「旧血/旧上限」的比例换算（无条件回满 = 每次进游戏白送治疗）")
    need("setHealth(player.getMaxHealth())" not in evt.replace(" ", ""),
         "没有写死 setHealth(getMaxHealth()) 这种无条件回满")

    # ---- 类必须在事件总线上注册，否则 @SubscribeEvent 全是死代码 ----------
    common = read(os.path.join(ROOT, "src/main/java/com/apocalypse/zombies/event/CommonEvents.java"))
    bus = None
    for name in ("CommonEvents.java", "ApocalypseZombies.java", "ModEvents.java"):
        path = os.path.join(ROOT, "src/main/java/com/apocalypse/zombies")
        for dirpath, _, files in os.walk(path):
            if name in files:
                txt = read(os.path.join(dirpath, name))
                if re.search(r"EVENT_BUS\.register\(\s*CommonEvents\.class\s*\)", txt) or \
                   re.search(r"register\(\s*CommonEvents\.class\s*\)", txt):
                    bus = os.path.join(dirpath, name)
    need(bus is not None, "CommonEvents.class 注册在 EVENT_BUS 上（否则 @SubscribeEvent 不触发）")
    if bus:
        notes.append("     注册处 = %s" % os.path.relpath(bus, ROOT))

    # ---- 数值合理性 --------------------------------------------------------
    notes.append("")
    notes.append("数值：原版基础 %d + 修饰符 %+d = %d" % (VANILLA_BASE, EXPECTED_BONUS, EXPECTED_DEFAULT))
    notes.append("      一份 100 血 = 50 颗心，原版 HUD 每行 10 颗 ⇒ 会占 5 行")
    notes.append("      本模组枪伤是照 20 血玩家调的（弩 6 / 莫辛 8.5 / 加兰德 7.5 / AWM 12，")
    notes.append("      怪物版再砍半）⇒ 100 血等于是把整体威胁压到 1/5，属于有意为之的加强。")

    for line in notes:
        print(line)
    print()
    if failures:
        print("FAIL %d 项：" % len(failures))
        for f in failures:
            print("  - " + f)
        return 1
    print("全部通过（玩家生命上限 = %d）" % EXPECTED_DEFAULT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
