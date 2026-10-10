# -*- coding: utf-8 -*-
"""1.1.75 出货准备：升版本（gradle.properties + readme）+ 从 _deploy_174.py 派生 _deploy_175.py。"""
import re
from pathlib import Path

NL = chr(10)
ROOT = Path("F:/mcmod")
VER, PREV = "1.1.75", "1.1.74"
fails = []

# ---------------------------------------------------------------- gradle.properties
gp = ROOT / "gradle.properties"
s = gp.read_text(encoding="utf-8")
if VER in s:
    print("(1) gradle.properties 已是 %s" % VER)
else:
    s2 = re.sub(r"mod_version\s*=\s*" + re.escape(PREV), "mod_version=%s" % VER, s, count=1)
    if s2 == s:
        fails.append("gradle.properties 里没找到 mod_version=%s" % PREV)
    else:
        gp.write_text(s2, encoding="utf-8")
        print("(1) gradle.properties mod_version → %s" % VER)

# ---------------------------------------------------------------- readme
rd = ROOT / "readme.md"
s = rd.read_text(encoding="utf-8")
if ("### %s " % VER) in s:
    print("(2) readme 已有 %s 段" % VER)
else:
    sec = NL.join([
        "### %s — 2026-10-10" % VER,
        "",
        "**她有脑子了：自己看着背包和周围挑活干、会把多余的成品收进你指定的箱子、你挨打时贴过来站位。**",
        "",
        "- **自主模式**（`CatGirlNeedGoal`）：每 2 秒看一眼 —— 有敌人在主人身边就上（FIGHT）、",
        "  背包里原木不足 8 就伐木、矿石不足 8 就挖矿、都不缺就跟着你。它<b>只改工种、不抢执行权</b>，",
        "  所以不会和战斗/劳作打架。你一动手切工种（给工具 / 空手右键），这个个体就自动关掉自动模式 ——",
        "  你要它砍树时它不会自作主张跑去挖矿。`/apocalypse catgirl auto` 再打开。开关 `auto_job`。",
        "- **用容器**（`CatGirlContainerGoal`）：把**多余的成品**（工具/武器/盔甲/弓弩/盾，每种至少留一件）",
        "  收进你给它绑的储物点；背包里矿石少于 4 时从那里取一组接着熔炼。",
        "  储物点用 `/apocalypse catgirl chest` 绑定（她 6 格内最近的容器）、`chest clear` 解绑 ——",
        "  **没绑她一个容器都不碰**（原版分不出哪个箱子是玩家的）。开关 `chest`。",
        "- **护卫**（`CatGirlEscortGoal`）：主人被攻击时贴到主人与攻击者之间站住。原版跟随只在主人离得远时",
        "  才动，挨贴脸时她是看戏的 —— 这条补上「挨打 → 立刻靠过去」。打谁仍由目标选择器决定。开关 `escort`。",
        "- **两个新命令**：`/apocalypse catgirl auto`（开关自主模式）、`/apocalypse catgirl chest [clear]`（绑定/解绑储物点）。",
        "",
        "### %s — 2026-10-10" % PREV,
    ])
    marker = "### %s — 2026-10-10" % PREV
    if marker not in s:
        fails.append("readme 里找不到 1.1.74 段锚点")
    else:
        s = s.replace(marker, sec, 1)
        lines = s.split(NL)
        hit = False
        for i, line in enumerate(lines):
            if line.startswith("| **当前版本** |") and PREV in line:
                lines[i] = line.replace(PREV, VER, 1)
                hit = True
                break
        if not hit:
            fails.append("readme 头表「当前版本」行没找到 %s" % PREV)
        rd.write_text(NL.join(lines), encoding="utf-8")
        print("(2) readme：+ ### %s 段 + 头表 → %s" % (VER, VER))

# ---------------------------------------------------------------- 派生 _deploy_175.py
T = ROOT / "tools/_deploy_174.py"
src = T.read_text(encoding="utf-8")
src = src.replace(
    '"""1.1.74 出货：像玩家一样操作第一批 —— 开门/浮水导航 + 开路 + 搭桥 + 自己出门找目标 + 不跟丢（含 1.1.73 全部不回归）',
    '"""1.1.75 出货：像玩家一样操作第二批 —— 自主选题 + 用容器 + 护卫 + 两个新命令（含 1.1.74 全部不回归）', 1)
src = src.replace("VER = '1.1.74'", "VER = '1.1.75'", 1)
src = src.replace("PREV = '1.1.73'", "PREV = '1.1.74'", 1)
src = src.replace("description='1.1.74 出货：玩家式操作（导航 / 开路 / 搭桥 / 找目标 / 跟随）'",
                  "description='1.1.75 出货：自主 / 容器 / 护卫'", 1)
src = src.replace("  1. 构建产物存在，且 jar 内 mods.toml 的 version == 1.1.74；",
                  "  1. 构建产物存在，且 jar 内 mods.toml 的 version == 1.1.75；", 1)
src = src.replace("py tools/_deploy_174.py", "py tools/_deploy_175.py")
for a, b in (("1/7", "1/8"), ("2/7", "2/8"), ("3/7", "4/8"), ("4/7 1.1.74", "5/8 1.1.74"),
             ("5/7", "6/8"), ("6/7", "7/8"), ("7/7", "8/8"), ("6/8 1.1.73", "5/8 1.1.73"), ("5/8 1.1.74", "6/8 1.1.74")):
    src = src.replace(a, b)

BLOCK = NL.join([
    "print('=== 3/8 1.1.75：像玩家一样操作（第二批 · 脑子）===')",
    "_p = 'F:/mcmod/src/main/java/com/apocalypse/zombies/'",
    "for _c in ('entity/ai/CatGirlNeedGoal.class', 'entity/ai/CatGirlEscortGoal.class',",
    "           'entity/ai/CatGirlContainerGoal.class'):",
    "    check(any(n.endswith(_c) for n in names), '进包：%s' % _c.split('/')[-1])",
    "_ent3 = open(_p + 'entity/CatGirlEntity.java', encoding='utf-8').read()",
    "for _g in ('new CatGirlNeedGoal(this)', 'new CatGirlEscortGoal(this)', 'new CatGirlContainerGoal(this)'):",
    "    check(_g in _ent3, '已注册目标：%s' % _g[4:-6])",
    "check('applyPlayerJob' in _ent3 and 'this.autoJob = false' in _ent3,",
    "      '玩家切工种 → 关掉这个个体的自动模式（手动优先）')",
    "check('isAutoJob' in _ent3 and 'getStorage' in _ent3 and 'setStorage' in _ent3,",
    "      '自主开关 / 储物点访问器在实体上')",
    "check('CatGirlAutoJob' in _ent3 and 'CatGirlChest' in _ent3, '这两个状态进 NBT（读档不丢）')",
    "check('!tag.contains(\"CatGirlAutoJob\")' in _ent3, '老存档默认落在安全那一侧（自动开、没绑箱子）')",
    "check(_ent3.count('applyPlayerJob') >= 3, '两处玩家交互（给工具 / 空手右键）都改走 applyPlayerJob')",
    "_need = open(_p + 'entity/ai/CatGirlNeedGoal.java', encoding='utf-8').read()",
    "check('EnumSet' not in _need and 'setFlags' not in _need, '需求 Goal 不占 MOVE/LOOK 执行权')",
    "check('Job.FIGHT' in _need and 'Job.LUMBER' in _need and 'Job.MINE' in _need and 'Job.FOLLOW' in _need,",
    "      '四种需求都在（打 / 伐木 / 挖矿 / 跟随）')",
    "check('AllyJudge.isHorde' in _need, '认敌复用她那一套判据（不会把友军当敌人）')",
    "check('Config.CAT_GIRL_AUTO_JOB' in _need and 'isAutoJob()' in _need, '需求 Goal 受开关 + 手动模式双重约束')",
    "_ct = open(_p + 'entity/ai/CatGirlContainerGoal.java', encoding='utf-8').read()",
    "check('Config.CAT_GIRL_CHEST' in _ct and 'getStorage()' in _ct, '容器 Goal 受开关约束且只认储物点')",
    "check('pos == null' in _ct and 'instanceof Container container' in _ct,",
    "      '没绑储物点 / 那儿不是容器 → 什么都不做')",
    "check('countIn(chest, stack.getItem()) == 0' in _ct, '成品每种至少留一件（不会把唯一那把镐子存走）')",
    "check('Tags.Items.ORES' in _ct and 'WANT_ORES' in _ct, '缺矿时从储物点取一组矿石')",
    "_esc = open(_p + 'entity/ai/CatGirlEscortGoal.java', encoding='utf-8').read()",
    "check('getLastHurtByMob' in _esc and 'Config.CAT_GIRL_ESCORT' in _esc, '护卫只认「主人被打」这个信号')",
    "_cmd = open(_p + 'command/ApocalypseCommand.java', encoding='utf-8').read()",
    "check('catgirlAuto' in _cmd and 'catgirlChest' in _cmd, '两个新子命令在命令表里')",
    "check('Commands.literal(\"auto\")' in _cmd and 'Commands.literal(\"chest\")' in _cmd, '命令字面量 auto / chest 已注册')",
    "_cfg3 = open(_p + 'Config.java', encoding='utf-8').read()",
    "for _k in ('\"auto_job\"', '\"chest\"', '\"escort\"'):",
    "    check(_k in _cfg3, 'Config 有 1.1.75 开关 %s' % _k)",
    "",
    "",
])
anchor = "print('=== 4/8 不回归"
if anchor not in src:
    fails.append("派生脚本里找不到不回归段锚点 %s" % anchor)
else:
    src = src.replace(anchor, BLOCK + anchor, 1)
(ROOT / "tools/_deploy_175.py").write_text(src, encoding="utf-8")
print("(3) _deploy_175.py 生成（%d 字节）" % len(src))

print(NL + ("全部命中" if not fails else "失败 %d 条：" % len(fails)))
for f in fails:
    print("  [FAIL] " + f)
(ROOT / "build" / "p175_prep_note.txt").write_text(NL.join(fails), encoding="utf-8")
