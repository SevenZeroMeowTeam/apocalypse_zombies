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
    'iron_sword': ['X', 'X', '#'],
    'iron_helmet': ['XXX', 'X X'],
    'iron_chestplate': ['X X', 'XXX', 'XXX'],
    'iron_leggings': ['XXX', 'X X', 'X X'],
    'iron_boots': ['X X', 'X X'],
}

#: 归一后的角色符号：材料（锭）/ 木棍 / 空
MATERIAL = 'copper_ingot'
STICK = 'stick'

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
