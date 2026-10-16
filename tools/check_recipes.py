# -*- coding: utf-8 -*-
"""配方图案门禁 —— 铜装备的合成形状必须与 1.20.1 原版同件（iron_*）逐格一致。

为什么需要它：1.1.103 想把铜斧压窄成两列，顺手把第 2 行的锭 / 棍写反（"SX"），又把本来正确的
铜锄镜像了（"S " / "S "）—— 配方书里显示的形状是错的，玩家照原版布局也合不出来
（用户 2026-10-16 报「配方表错误」，截图里正是那张铜斧表）。这类错「看着像对的」，只有逐格
比对才拦得住。图案不手抄：**从游戏 jar 里读原版** `data/minecraft/recipes/iron_*.json`，
按「材料 / 木棍 / 空」归一后与 mod 的图案比较（键名 X/S 与 X/# 的差异不影响）。

用法：
    python tools/check_recipes.py                 # 默认用本机游戏 jar
    python tools/check_recipes.py --jar <path>     # 指定 jar
    （jar 找不到时退回内置表 —— 该表 2026-10-16 从 1.20.1 原版逐条读出，仅供离线兜底）
"""
import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOD_RECIPES = ROOT / 'src' / 'main' / 'resources' / 'data' / 'apocalypse_zombies' / 'recipes'
DEFAULT_JAR = Path('F:/.minecraft/versions/1.20.1-Forge_47.4.27/1.20.1-Forge_47.4.27.jar')

#: mod 的铜装备 → 原版参照件（形状一一对应）
PAIRS = {
    'copper_axe': 'iron_axe',
    'copper_hoe': 'iron_hoe',
    'copper_pickaxe': 'iron_pickaxe',
    'copper_shovel': 'iron_shovel',
    'copper_sword': 'iron_sword',
    'copper_helmet': 'iron_helmet',
    'copper_chestplate': 'iron_chestplate',
    'copper_leggings': 'iron_leggings',
    'copper_boots': 'iron_boots',
}

#: 离线兜底（2026-10-16 从 1.20.1 游戏 jar 的 data/minecraft/recipes/iron_*.json 读出）
FALLBACK = {
    'iron_axe': ['XX', 'X#', ' #'],
    'iron_hoe': ['XX', ' #', ' #'],
    'iron_pickaxe': ['XXX', ' # ', ' # '],
    'iron_shovel': ['X', '#', '#'],
    'iron_sword': ['X', 'X', '#'],
    'iron_helmet': ['XXX', 'X X'],
    'iron_chestplate': ['X X', 'XXX', 'XXX'],
    'iron_leggings': ['XXX', 'X X', 'X X'],
    'iron_boots': ['X X', 'X X'],
}

#: 归一后的角色符号：材料（锭）/ 木棍 / 空
MATERIAL = 'copper_ingot'
STICK = 'stick'

#: 「短木棍版」条件配方：图案与 canonical 逐格相同，只有手柄槽换成硬核生存的短木棍。
#: —— 用条件而不是把手柄槽改成物品标签，是因为 1.20.1 的原版 TagLoader 遇到标签里引用
#: **不存在的物品**时会把**整条标签**丢掉（"Couldn't load tag … missing references"），
#: 没装硬核生存的玩家会连带丢掉全部铜工具配方；条件配方是 Forge 在**解析之前**就跳过的，
#: 物品 id 根本不会被解析，装与不装都安全。
SHORT_STICK_TOOLS = ('copper_axe', 'copper_hoe', 'copper_pickaxe', 'copper_shovel', 'copper_sword')
HCS_ITEM = 'hcsurvival:short_stick'
MOD_LOADED_CONDITION = {'type': 'forge:mod_loaded', 'modid': 'hcsurvival'}

problems = []
notes = []


def ok(msg):
    notes.append(msg)


def bad(msg):
    problems.append(msg)


def roles(recipe, material):
    """把一张 shaped 配方归一成「M / S / 空」的网格；出现「材料 + 木棍」以外的键时返回 None。"""
    key = recipe.get('key') or {}
    role = {}
    for sym, val in key.items():
        item = (val or {}).get('item') or (val or {}).get('tag') or ''
        item = str(item).split(':')[-1]
        if item == material:
            role[sym] = 'M'
        elif item == STICK:
            role[sym] = 'S'
        else:
            return None
    out = []
    for row in recipe.get('pattern') or []:
        out.append(''.join(' ' if ch == ' ' else role.get(ch, '?') for ch in row))
    return out


def load_vanilla(jar):
    """从游戏 jar 里读原版配方（含 key）；读不到返回 None（调用方退回内置表）。"""
    try:
        with zipfile.ZipFile(jar) as zf:
            found = {}
            for vanilla in set(PAIRS.values()):
                found[vanilla] = json.loads(zf.read('data/minecraft/recipes/%s.json' % vanilla))
            return found
    except Exception as e:                                    # noqa: BLE001
        print('（读不到游戏 jar：%s —— 退回内置表）' % e)
        return None


def main():
    ap = argparse.ArgumentParser(description='铜装备配方图案门禁（与原版逐格对齐）')
    ap.add_argument('--jar', default=str(DEFAULT_JAR), help='游戏 jar 路径')
    args = ap.parse_args()

    jar = Path(args.jar)
    vanilla = load_vanilla(jar) if jar.exists() else None
    source = '游戏 jar' if vanilla else '内置兜底表'
    if vanilla is None:
        vanilla = {k: {'key': {'X': {'item': 'minecraft:iron_ingot'},
                               'S': {'item': 'minecraft:stick'}},
                       'pattern': v} for k, v in FALLBACK.items()}
        if not jar.exists():
            print('（%s 不存在 —— 退回内置表）' % jar)

    # 「短木棍版」条件配方：图案与 canonical 逐格相同，只有手柄槽换成 hcsurvival:short_stick，
    # 且必须挂 forge:mod_loaded:hcsurvival（没装就是 Forge 直接跳过，物品 id 不会被解析）。
    for tool in SHORT_STICK_TOOLS:
        canon = json.loads((MOD_RECIPES / ('%s.json' % tool)).read_text(encoding='utf-8'))
        path = MOD_RECIPES / ('%s_short_stick.json' % tool)
        if not path.exists():
            bad('缺短木棍版条件配方 %s_short_stick.json' % tool)
            continue
        v = json.loads(path.read_text(encoding='utf-8'))
        if v.get('pattern') != canon.get('pattern'):
            bad('%s_short_stick：图案 %s 与 canonical %s 不一致'
                % (tool, v.get('pattern'), canon.get('pattern')))
        elif (v.get('result') or {}) != (canon.get('result') or {}):
            bad('%s_short_stick：产出与 canonical 不一致' % tool)
        elif MOD_LOADED_CONDITION not in (v.get('conditions') or []):
            bad('%s_short_stick：缺 forge:mod_loaded:hcsurvival 条件（没装硬核生存时会解析失败）' % tool)
        elif json.dumps(v.get('key') or {}, sort_keys=True).count(HCS_ITEM) != 1:
            bad('%s_short_stick：手柄槽应恰好引用一次 %s' % (tool, HCS_ITEM))
        else:
            ok('%s_short_stick == canonical 图案 + 短木棍手柄（挂 hcsurvival 条件）' % tool)

    # 总规矩：任何**引用外家物品**的配方都必须带条件 —— 1.20.1 里引用不存在的物品 = 整条配方解析失败。
    for path in sorted(MOD_RECIPES.glob('*.json')):
        rec = json.loads(path.read_text(encoding='utf-8'))
        blob = json.dumps(rec, ensure_ascii=False)
        foreign = set()
        for val in (rec.get('key') or {}).values():
            item = (val or {}).get('item') if isinstance(val, dict) else None
            if isinstance(item, str) and not item.startswith(('minecraft:', 'apocalypse_zombies:')):
                foreign.add(item)
        if foreign and not (rec.get('conditions') or []):
            bad('%s 引用了外家物品 %s 却没有 conditions —— 缺了那个模组时整条配方会解析失败'
                % (path.name, sorted(foreign)))
    ok('外家物品（%s）只出现在带条件的配方里' % HCS_ITEM)

    for mod_name, vanilla_name in PAIRS.items():
        path = MOD_RECIPES / ('%s.json' % mod_name)
        if not path.exists():
            bad('缺配方文件 %s.json' % mod_name)
            continue
        recipe = json.loads(path.read_text(encoding='utf-8'))

        want = roles(vanilla[vanilla_name], 'iron_ingot')
        got = roles(recipe, MATERIAL)
        if want is None:
            bad('原版 %s 的键不是「铁锭 + 木棍」—— 门禁的参照失效，去看看原版数据' % vanilla_name)
            continue

        result = ((recipe.get('result') or {}).get('item') or '')
        if result != 'apocalypse_zombies:%s' % mod_name:
            bad('%s：产出是 %s（应为 apocalypse_zombies:%s）' % (mod_name, result, mod_name))
            continue
        if got is None:
            bad('%s：键里出现了「%s / %s」以外的材料（只能是铜锭 + 木棍）' % (mod_name, MATERIAL, STICK))
            continue
        if got != want:
            bad('%s：图案 %s 与原版 %s %s 不一致 —— 配方书会显示错误形状、照原版布局也合不出来'
                % (mod_name, got, vanilla_name, want))
        else:
            ok('%s == 原版 %s（%s）' % (mod_name, vanilla_name, '/'.join(want)))

        # 镜像变体（可选）：存在时必须是 canonical 图案的**精确左右镜像**，键与产出一致。
        # ——1.1.103~108 的错误图案把镜像摆法"教"给了玩家，补变体让两种摆法都能合（hcsurvival 同思路）。
        mirror_path = MOD_RECIPES / ('%s_mirror.json' % mod_name)
        if mirror_path.exists():
            m = json.loads(mirror_path.read_text(encoding='utf-8'))
            want_mirror = [row[::-1] for row in recipe['pattern']]
            if m.get('pattern') != want_mirror:
                bad('%s_mirror：图案 %s 不是 %s 的左右镜像（应为 %s）'
                    % (mod_name, m.get('pattern'), mod_name, want_mirror))
            elif (m.get('result') or {}) != (recipe.get('result') or {}):
                bad('%s_mirror：产出 %s 与 %s 不一致' % (mod_name, m.get('result'), mod_name))
            elif (m.get('key') or {}) != (recipe.get('key') or {}):
                bad('%s_mirror：键与 %s 不一致' % (mod_name, mod_name))
            else:
                ok('%s_mirror == %s 的左右镜像（两种摆法都能合）' % (mod_name, mod_name))

    print('=== 配方图案门禁（对照 %s）===' % source)
    for n in notes:
        print('  ·', n)
    if problems:
        print('\n%d 条不通过：' % len(problems))
        for p in problems:
            print('  [x]', p)
        return 1
    print('\n全部通过：%d 张铜装备配方与原版逐格一致' % len(PAIRS))
    return 0


if __name__ == '__main__':
    sys.exit(main())
