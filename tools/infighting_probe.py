# -*- coding: utf-8 -*-
"""「敌对生物之间不会互相攻击」的运行时判据（headless 服务端 + RCON）。

为什么必须走运行时：这条规则落在 `LivingAttackEvent` 上（伤害入口），而「伤害有没有发生」
在静态层面完全看不出来 —— 代码编译得过、日志干净，判不出来。更要紧的是它的**因果是反的**：
不是怪想打对方，而是被打的那个被原版 `HurtByTargetGoal` 记了仇。所以判据必须同时量两件事：

    ① 伤害有没有打进去
    ② 打完有没有起内斗（**攻击者**的血量 —— 同伴回击的唯一可观测落点）

四条口径纪律（前三条是 bride_aggro_probe 的教训，第四条是本轮踩出来的）：

1. **判据取命令返回值，不取血量差。** `damage` 命令打不进去时原版回的是
   `Target is invulnerable to the given damage type` —— 那正是 `LivingEntity#hurt` 返回
   false 的说法（Forge 在 hurt 开头调 `onLivingAttack`，事件被取消就 return false）。
   返回值只反映这一发，血量会被别的来源污染。
2. **伤害归属要显式指定来源**（`by <entity>`）：与原版 `LastHurtByMob` 走同一条链，
   不靠站位猜。
3. **必须有对照相**：`mod_off` 相要看到伤害确实打得进去、攻击者确实掉血（内斗被复现），
   否则「打不进去」可能只是命令压根没执行（假绿）；`control` 相（村民受害者）证明规则
   没有把怪变成瞎子。
4. **标签必须每次运行唯一。** 第一版用固定标签 `p_v` 配 `limit=1`：旧测试遗留的一只
   *露天晒太阳* 的僵尸顶着同一个标签留在场外，与场内靶离命令原点的距离相近 ⇒ 选择器在
   两个实体之间跳，读出来的「掉血 / HurtByTimestamp」全是对不上号的噪声（实测把场外那只
   的燃烧掉血当成了场内伤害）。现在每轮唯一后缀 + 区域清场。

用法（每个相位都要先改配置再重启服务端，Forge 的 common 配置是启动时读的）：

    python tools/infighting_probe.py --scenario mod       --seconds 20   # no_infighting=true
    python tools/infighting_probe.py --scenario mod_off   --seconds 20   # no_infighting=false
    python tools/infighting_probe.py --scenario vanilla   --seconds 20   # 原版互殴：默认照旧
    python tools/infighting_probe.py --scenario vanilla   --seconds 20 --global
    python tools/infighting_probe.py --scenario control   --seconds 20   # 村民受害者：必须照打
    python tools/infighting_probe.py --scenario aoe       --seconds 40   # 爆破兵 TNT（阶段 ③ 之后）

`--expect` 覆盖默认期望（`landed` / `blocked`）；相位配错了直接报红，不会读出假绿。
"""
import argparse
import random
import re
import socket
import struct
import sys
import time

SOLDIER = "apocalypse_zombies:soldier_zombie"
ZOMBIE = "minecraft:zombie"
SKELETON = "minecraft:skeleton"
VILLAGER = "minecraft:villager"
GOLEM = "minecraft:iron_golem"
SAPPER_AT = (2.0, 100.0, 0.0)
VICTIM_AT = (4.0, 100.0, 0.0)
GOLEM_AT = (4.0, 100.0, 5.0)
ZOMBIES_AT = [(0.0, 100.0, 1.0), (0.0, 100.0, -1.0), (1.5, 100.0, 0.0)]
# 竞技场清场：以 y=100 为中心的一大块立方体，只留玩家（探针里没有玩家）。
# 不清场就会重演第 4 条纪律里那个污染事故。
ARENA_CLEAN = "kill @e[x=-32,y=72,z=-32,dx=64,dy=56,dz=64,type=!player]"


class Rcon:
    """Source RCON 客户端（包体 <i len><i id><i type><body>\\0\\0）。"""

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

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def health_of(rcon, tag):
    m = re.search(r":\s*([0-9.]+)f\s*$",
                  rcon.cmd("data get entity @e[tag=%s,limit=1] Health" % tag))
    return float(m.group(1)) if m else None


def setup(rcon, scenario, tag):
    for c in ("gamerule doMobSpawning false", "gamerule doDaylightCycle false",
              "gamerule mobGriefing false", "gamerule doMobLoot false",
              "difficulty hard", "time set noon", "weather clear",
              ARENA_CLEAN,
              "forceload add -16 -16 16 16",
              "fill -8 99 -8 8 99 8 minecraft:stone",
              "fill -8 100 -8 8 106 8 minecraft:stone",
              "fill -7 100 -7 7 105 7 minecraft:air",
              # 4 格高的隔断 + 1 格门洞：把「源」与「靶」分在两侧，互相看得见、
              # 走得到，但不会自己挤到一起（否则「谁先动手」不可控）
              "fill 3 100 -3 3 103 3 minecraft:stone",
              "fill 3 100 0 3 103 0 minecraft:air"):
        rcon.cmd(c)

    def summon(kind, at, extra, tag_name):
        return rcon.cmd("summon %s %.1f %.1f %.1f {%s,Tags:[\"%s\"]}"
                        % ((kind,) + tuple(at) + (extra, tag_name)))

    if scenario == "aoe":
        # 爆破兵 + 它自己的同类围观（友军误伤的现实几何）+ 铁傀儡当目标
        summon(SOLDIER, SAPPER_AT, "PersistenceRequired:1b", tag["src"])
        summon(GOLEM, GOLEM_AT, "NoAI:1b,Silent:1b,PersistenceRequired:1b", tag["v"])
        for at in ZOMBIES_AT:
            summon(ZOMBIE, at, "PersistenceRequired:1b", tag["z"])
    else:
        source = SOLDIER if scenario in ("mod", "mod_off") else SKELETON
        victim = VILLAGER if scenario == "control" else ZOMBIE
        # 源 NoAI：不让它自己动，把「谁打谁」完全交给命令钉死
        summon(source, SAPPER_AT, "NoAI:1b,Silent:1b,PersistenceRequired:1b", tag["src"])
        summon(victim, VICTIM_AT, "PersistenceRequired:1b", tag["v"])
        if scenario == "control":
            # 村民相再补三只僵尸：规则若不生效，僵尸必须照旧把村民咬死（反证没瞎）
            for at in ZOMBIES_AT:
                summon(ZOMBIE, at, "PersistenceRequired:1b", tag["z"])
    time.sleep(0.8)


def scenario_config(scenario, global_on):
    """相位 → (期望现象, 说明)。"""
    if scenario == "mod":
        return "blocked", "本模组的怪打同伴（应被拦）"
    if scenario == "mod_off":
        return "landed", "配置关掉后重跑（内斗必须复现）"
    if scenario == "vanilla":
        if global_on:
            return "blocked", "原版怪打原版怪（global=true：也应被拦）"
        return "landed", "原版怪打原版怪（默认：不拦，照旧互殴）"
    if scenario == "aoe":
        return "blocked", "爆破兵 TNT 落在同类脚边（默认不伤同伴）"
    if scenario == "control":
        return "landed", "僵尸打村民（这条规则不该管）"
    raise SystemExit("未知场景 %s" % scenario)


def run(scenario, seconds, step, trace=False, expect=None, global_on=False):
    run_id = "%04d" % random.randint(0, 9999)
    tag = {"src": "psrc" + run_id, "v": "pv" + run_id, "z": "pz" + run_id}
    want, label = scenario_config(scenario, global_on)
    if expect:
        want = expect

    rcon = Rcon()
    setup(rcon, scenario, tag)

    start = {k: health_of(rcon, t) for k, t in tag.items()}
    print("=" * 78)
    print("场景 %s  期望=%s  时长 %ds  (标签后缀 %s)" % (scenario, want, seconds, run_id))
    print("  %s" % label)
    print("  开局血量: 源=%s 靶=%s" % (fmt(start["src"]), fmt(start["v"])))
    if start["v"] is None or start["src"] is None:
        print("  ⚠ 实体没起来 —— 探针自身没跑通，判据无效")
        rcon.close()
        return False

    landed, blocked, attempts, unexpected = 0, 0, 0, 0
    dmg_source = 0.0
    prev_src = start["src"]
    t0 = time.time()
    now = 0.0
    while now < seconds:
        now = time.time() - t0
        if scenario in ("mod", "mod_off", "vanilla", "control"):
            out = rcon.cmd('damage @e[tag=%s,limit=1] 4 minecraft:player_attack '
                           'by @e[tag=%s,limit=1]' % (tag["v"], tag["src"]))
            attempts += 1
            if "Applied" in out:
                landed += 1
                if trace:
                    print("  %6.1fs  %s" % (now, out))
            elif "invulnerable" in out:
                blocked += 1
            else:
                unexpected += 1
                print("  %6.1fs  ⚠ 命令没按预期执行: %s" % (now, out))
        cur = health_of(rcon, tag["src"])
        if cur is not None and prev_src is not None and cur < prev_src:
            delta = prev_src - cur
            dmg_source += delta
            print("  %6.1fs  ⚑ 源掉血 %.2f（累计 %.2f）—— 同伴回击了" % (now, delta, dmg_source))
        prev_src = cur
        time.sleep(step)

    end = {k: health_of(rcon, t) for k, t in tag.items()}
    print("  结束血量: 源=%s 靶=%s" % (fmt(end["src"]), fmt(end["v"])))

    if scenario == "aoe":
        if start["z"] is not None and end["z"] is not None:
            zombie_damage = start["z"] - end["z"]
        else:
            zombie_damage = 0.0
        print("  同类掉血 %.1f；爆破兵掉血 %.1f" % (zombie_damage, dmg_source))
        ok = zombie_damage <= 0.001 and dmg_source <= 0.001
    else:
        print("  施加 %d 次：打进去 %d、被拦 %d、异常 %d；源累计掉血 %.1f"
              % (attempts, landed, blocked, unexpected, dmg_source))
        retaliated = dmg_source > 0.001
        if scenario == "control":
            ok = landed >= 1                       # 村民必须照旧挨打（规则不许把怪变瞎）
        elif want == "blocked":
            ok = landed == 0 and blocked >= max(1, attempts // 2)
        else:
            ok = landed >= 1 and (retaliated or unexpected == 0)
    print("  ⇒ %s（期望 %s）" % ("通过" if ok else "不通过", want))
    for t in tag.values():
        rcon.cmd("kill @e[tag=%s]" % t)
    rcon.close()
    return ok


def fmt(v):
    return "None" if v is None else "%.1f" % v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True,
                    choices=["mod", "mod_off", "vanilla", "aoe", "control"])
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--step", type=float, default=1.0)
    ap.add_argument("--trace", action="store_true")
    ap.add_argument("--global", dest="global_on", action="store_true",
                    help="该相位跑在 ai_enhance.no_infighting_global=true 的配置上")
    ap.add_argument("--expect", choices=["landed", "blocked"], default=None)
    a = ap.parse_args()
    ok = run(a.scenario, a.seconds, a.step, a.trace, a.expect, a.global_on)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
