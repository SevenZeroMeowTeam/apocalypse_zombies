# -*- coding: utf-8 -*-
"""原版工具配方「屏障假配方」恢复门禁 —— 验证 VanillaToolRecipeRestorer 真的修得住硬核生存那一手。

背景：`[硬核生存] hcsurvival` 把 `data/minecraft/recipes/` 下的原版配方整个换成「1 个屏障」
（生存里拿不到 = 永远合不出来），把玩家推向它自己的燧石工具链。0.19.2 实测被禁的是
石质全套 5 件 + 木斧 / 木镐 / 木锄 3 件；铁制与木剑 / 木锹它没动。

本模组的修法（`compat/VanillaToolRecipeRestorer.java`）：配方加载完成后，把 minecraft 命名空间下
「每个非空材料格都只认屏障」的假配方换成代码重建的原版真配方（图案 / 材料 / 产物逐格照抄原版），
认不得的直接剔除。运行期替换是确定性的 —— 不赌两个模组写同一条 `minecraft:recipes/xxx.json` 时
资源栈顺序谁赢。

四条断言：
  1. Java 的重建表 TOOL_SPECS 与内置期望表（原版 1.20.1 逐格抄出的 15 件）完全一致 ——
     图案错一行、材料错一格都过不去（图案类错误只有逐格比对才拦得住，本项目已经吃过两次亏）；
  2. hcsurvival jar 里「屏障假配方」的清单**每一条**都在重建表里（= 运行期会被换成真配方，
     而不是被剔掉完事）；当前应为石 5 + 木 3 共 8 条；
  3. 找得到原版 jar 时，重建表再与原版 jar 里的真 JSON 逐格核一遍（防 MC 版本漂移）；
  4. hcsurvival 没有碰铁制 / 木剑 / 木锹的配方（它们本来就能合成，不该被本恢复器多手）。

判定规则或原版图案改动而这里没跟着改 → 至少一条断言会红。

用法：
    python tools/check_vanilla_recipe_restore.py            # 自动找 hcsurvival jar 与原版 jar
    python tools/check_vanilla_recipe_restore.py --hcs-jar <path> [--vanilla-jar <path>]
    （hcsurvival jar 找不到时退回内置兜底表 —— 2026-10-24 从 hcsurvival-0.19.2 逐条读出）
"""
import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEV_INSTANCE = Path('F:/.minecraft/versions/1.20.1-Forge_47.4.27')
RESTORER = ROOT / 'src' / 'main' / 'java' / 'com' / 'apocalypse' / 'zombies' / 'compat' / 'VanillaToolRecipeRestorer.java'

#: 内置期望表：原版 1.20.1 jar 的 data/minecraft/recipes/*.json 逐格抄出（X=材料 #=木棍）。
#: material: planks → #minecraft:planks 标签；stone → #minecraft:stone_tool_materials 标签；iron → minecraft:iron_ingot。
EXPECTED = {
    'wooden_sword':   ('planks', ['X', 'X', '#']),
    'wooden_pickaxe': ('planks', ['XXX', ' # ', ' # ']),
    'wooden_axe':     ('planks', ['XX', 'X#', ' #']),
    'wooden_shovel':  ('planks', ['X', '#', '#']),
    'wooden_hoe':     ('planks', ['XX', ' #', ' #']),
    'stone_sword':    ('stone', ['X', 'X', '#']),
    'stone_pickaxe':  ('stone', ['XXX', ' # ', ' # ']),
    'stone_axe':      ('stone', ['XX', 'X#', ' #']),
    'stone_shovel':   ('stone', ['X', '#', '#']),
    'stone_hoe':      ('stone', ['XX', ' #', ' #']),
    'iron_sword':     ('iron', ['X', 'X', '#']),
    'iron_pickaxe':   ('iron', ['XXX', ' # ', ' # ']),
    'iron_axe':       ('iron', ['XX', 'X#', ' #']),
    'iron_shovel':    ('iron', ['X', '#', '#']),
    'iron_hoe':       ('iron', ['XX', ' #', ' #']),
}

#: 2026-10-24 从 hcsurvival-0.19.2 的 data/minecraft/recipes/*.json 读出的屏障假配方清单（离线兜底）。
FALLBACK_DEAD = {
    'stone_axe', 'stone_hoe', 'stone_pickaxe', 'stone_shovel', 'stone_sword',
    'wooden_axe', 'wooden_hoe', 'wooden_pickaxe',
}

#: hcsurvival 没禁的「邻居们」——断言 4 的对照组（它们要还活着，才说明玩家能靠原版链爬到铁器）。
MUST_SURVIVE = {'iron_pickaxe', 'iron_axe', 'iron_sword', 'iron_shovel', 'iron_hoe',
                'wooden_sword', 'wooden_shovel'}

MATERIAL_JSON = {
    'planks': {'tag': 'minecraft:planks'},
    'stone': {'tag': 'minecraft:stone_tool_materials'},
    'iron': {'item': 'minecraft:iron_ingot'},
}
STICK_JSON = {'item': 'minecraft:stick'}

failures = []


def ok(msg):
    print('  [门禁] ✓', msg)


def fail(msg):
    failures.append(msg)
    print('  [门禁] ✗', msg)


def parse_java_table():
    """从 VanillaToolRecipeRestorer.java 里把 TOOL_SPECS 逐行抠出来（一行一条，正则核对）。"""
    src = RESTORER.read_text(encoding='utf-8')
    pat = re.compile(r'new ToolSpec\("([a-z_]+)", (PLANKS|STONE|IRON)((?:, "[^"]*")+)\)')
    table = {}
    for m in pat.finditer(src):
        rid, material, rows_blob = m.group(1), m.group(2).lower(), m.group(3)
        rows = re.findall(r'"([^"]*)"', rows_blob)
        if rid in table:
            fail('重建表里 %s 出现两次' % rid)
        table[rid] = (material, rows)
    if not table:
        fail('没在 %s 里解析到任何 ToolSpec —— 正则与 Java 表不同步了' % RESTORER.name)
    return table


def barrier_gated_from_jar(jar):
    """jar 的 data/minecraft/recipes/ 下「每个材料格都只认屏障」的配方 id 集合（与 Java 判定同口径）。"""
    dead = set()
    with zipfile.ZipFile(jar) as zf:
        for name in zf.namelist():
            if not name.startswith('data/minecraft/recipes/') or not name.endswith('.json'):
                continue
            try:
                recipe = json.loads(zf.read(name).decode('utf-8'))
            except Exception:
                continue
            cells = []
            if recipe.get('type') == 'minecraft:crafting_shaped':
                cells = list(recipe.get('key', {}).values())
            elif recipe.get('type') == 'minecraft:crafting_shapeless':
                cells = list(recipe.get('ingredients', []))
            if not cells:
                continue
            if all(isinstance(c, dict) and c.get('item') == 'minecraft:barrier' and 'tag' not in c
                   for c in cells):
                dead.add(Path(name).stem)
    return dead


def check_table_vs_expected(table):
    if set(table) != set(EXPECTED):
        fail('重建表与期望表的条目集不一致：只差 %s / 多 %s'
             % (sorted(set(EXPECTED) - set(table)), sorted(set(table) - set(EXPECTED))))
        return
    for rid, (material, rows) in EXPECTED.items():
        got = table.get(rid)
        if got != (material, rows):
            fail('%s 重建表 %s ≠ 期望 %s（图案 / 材料逐格都要对）' % (rid, got, (material, rows)))
    if not failures:
        ok('断言 1：重建表 15 件与原版 1.20.1 期望表逐格一致')


def check_dead_covered(dead):
    if not dead:
        fail('hcsurvival 里一条屏障假配方都没找到 —— 它改版了？判定口径失效？')
        return
    known = set(EXPECTED)
    unknown = dead - known
    if unknown:
        fail('屏障假配方里有重建表不认识的：%s —— 请把它们的原版图案补进 ToolSpec，'
             '否则运行期只会剔除（玩家依旧合不出来）' % sorted(unknown))
    else:
        ok('断言 2：屏障假配方 %s 全部能被重建表恢复（共 %d 条）' % (sorted(dead), len(dead)))
    expect_now = FALLBACK_DEAD
    if dead != expect_now:
        print('  [门禁] ⚠ 本轮假配方清单与 0.19.2 兜底表不同（%s vs %s）—— hcsurvival 改版了，'
              '确认是有意变更后更新 FALLBACK_DEAD' % (sorted(dead), sorted(expect_now)))


def check_vs_vanilla_jar(vanilla_jar, table):
    if vanilla_jar is None or not vanilla_jar.exists():
        print('  [门禁] ⚠ 找不到原版 jar，断言 3 跳过（离线兜底表此时就是真值来源）')
        return
    with zipfile.ZipFile(vanilla_jar) as zf:
        for rid, (material, rows) in table.items():
            name = 'data/minecraft/recipes/%s.json' % rid
            try:
                recipe = json.loads(zf.read(name).decode('utf-8'))
            except KeyError:
                fail('原版 jar 里没有 %s —— MC 版本变了？' % name)
                continue
            if recipe.get('pattern') != rows:
                fail('%s 原版图案 %s ≠ 重建表 %s' % (rid, recipe.get('pattern'), rows))
            if recipe.get('key', {}).get('X') != MATERIAL_JSON[material]:
                fail('%s 原版材料 %s ≠ 重建表 %s' % (rid, recipe.get('key', {}).get('X'), MATERIAL_JSON[material]))
            if recipe.get('key', {}).get('#') != STICK_JSON:
                fail('%s 手柄槽不是木棍：%s' % (rid, recipe.get('key', {}).get('#')))
            if recipe.get('result', {}).get('item') != 'minecraft:%s' % rid:
                fail('%s 产物不是自己：%s' % (rid, recipe.get('result')))
    if not failures:
        ok('断言 3：重建表 15 件与原版 jar 真实配方逐格一致（%s）' % vanilla_jar.name)


def check_neighbors_untouched(dead, jar):
    if jar is None or not jar.exists():
        return
    overridden = set()
    with zipfile.ZipFile(jar) as zf:
        for name in zf.namelist():
            if name.startswith('data/minecraft/recipes/') and name.endswith('.json'):
                overridden.add(Path(name).stem)
    survivors = MUST_SURVIVE & overridden
    if survivors:
        fail('hcsurvival 覆盖了本该活着的原版配方：%s —— 铁制 / 木剑木锹链条被动过了，'
             '请核对并按需扩充重建表' % sorted(survivors))
    else:
        ok('断言 4：铁制 5 件 + 木剑 / 木锹未被 hcsurvival 触碰（本来就能合成，恢复器不掺和）')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--hcs-jar', default=None)
    ap.add_argument('--vanilla-jar', default=None)
    args = ap.parse_args()

    print('== 原版工具配方恢复门禁 ==')
    table = parse_java_table()
    check_table_vs_expected(table)

    hcs = Path(args.hcs_jar) if args.hcs_jar else None
    if hcs is None and DEV_INSTANCE.is_dir():
        cands = sorted(DEV_INSTANCE.glob('mods/*hcsurvival*.jar'))
        hcs = cands[0] if cands else None
    if hcs is not None and hcs.exists():
        print('对照来源（hcsurvival）：%s' % hcs.name)
        dead = barrier_gated_from_jar(hcs)
    else:
        print('（找不到 hcsurvival jar —— 用 0.19.2 的兜底表）')
        dead = set(FALLBACK_DEAD)
    check_dead_covered(dead)
    check_neighbors_untouched(dead, hcs)

    vanilla = Path(args.vanilla_jar) if args.vanilla_jar else None
    if vanilla is None and DEV_INSTANCE.is_dir():
        cands = sorted(p for p in DEV_INSTANCE.glob('*.jar') if re.match(r'1\.20\.1-Forge', p.name))
        vanilla = cands[0] if cands else None
    check_vs_vanilla_jar(vanilla, table)

    if failures:
        print('\n门禁失败：%d 条' % len(failures))
        return 1
    print('\n门禁全绿。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
