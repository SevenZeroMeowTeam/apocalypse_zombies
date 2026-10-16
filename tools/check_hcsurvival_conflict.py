# -*- coding: utf-8 -*-
"""铜装备「同形配方」冲突门禁 —— 验证 CopperGearRecipeCompat 的判定规则真的拦得住硬核生存那套。

为什么需要它：`[硬核生存] hcsurvival` 用**同一套原版图案 + 同一材料（minecraft:copper_ingot）**
注册了同名的九件铜装备。1.20.1 的 `RecipeManager.getRecipeFor` 是 findFirst（HashMap 顺序），
两条会命中同一批网格的配方里只有一条能被合成台用到，另一条等于不存在 —— 玩家摆对图案可能拿到
硬核生存那件，也可能什么都拿不到。本模组的修法是运行期把「与本模组铜装备配方**抢同一批网格**、
产物却不是本模组」的配方剔掉（`com/apocalypse_zombies/compat/CopperGearRecipeCompat.java`）。

这个门禁做的是**同一套判定规则的离线复刻**：
  * 逐格材料集合：`{"item": …}` / `{"tag": …}` / 数组简写都归一成「这一格能接受的物品 id 集合」；
    1.2.2 起另有一组「短木棍版」条件配方（`copper_*_short_stick.json`，图案相同、手柄换成
    `hcsurvival:short_stick`、挂 `forge:mod_loaded:hcsurvival`），本门禁会一并核对它们的图案与条件；
  * 两条配方「抢同一批网格」⟺ 类型 / 尺寸相同、逐格材料集合**两两有交集**；shaped 源版 matches
    对同一个图案会同时试正摆与镜像摆，所以连镜像摆法也要比一遍。

四条断言：
  1. 本模组 11 张铜装备配方（9 件 + 斧/锄镜像）都读得出来，其中 7 张带手柄槽；
  2. hcsurvival 的 11 张铜装备配方**每一条**都与本模组某条配方抢同一批网格（= 运行期会被剔除）；
  3. 本模组的 canonical 与镜像变体互为竞争者（说明判定不是退化的空集）；
  4. 判定**有边界**：抽 hcsurvival 的非铜装备配方（晾肉架 / 绷带 / 粗制火把…）验证它们一条都不抢。

判定规则改动而这里没跟着改 → 至少一条断言会红。

用法：
    python tools/check_hcsurvival_conflict.py            # 默认去开发机实例里找 hcsurvival 的 jar
    python tools/check_hcsurvival_conflict.py --jar <path>
    （jar 找不到时退回内置兜底表 —— 该表 2026-10-16 从 hcsurvival-0.19.2 逐条读出，仅供离线兜底）
"""
import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOD_RECIPES = ROOT / 'src' / 'main' / 'resources' / 'data' / 'apocalypse_zombies' / 'recipes'
DEV_MODS = Path('F:/.minecraft/versions/1.20.1-Forge_47.4.27/mods')

#: 本模组的铜装备（canonical + 镜像变体），与 CopperGearRecipeCompat.COPPER_GEAR 同名
OURS = ['copper_sword', 'copper_pickaxe', 'copper_axe', 'copper_hoe', 'copper_shovel',
        'copper_helmet', 'copper_chestplate', 'copper_leggings', 'copper_boots',
        'copper_axe_mirror', 'copper_hoe_mirror']

#: hcsurvival 的铜装备配方（11 张：9 件 + 斧/锄的 _1/_2 两摆）
HCS_RECIPES = ['copper_axe_1', 'copper_axe_2', 'copper_boots', 'copper_chestplate',
               'copper_helmet', 'copper_hoe_1', 'copper_hoe_2', 'copper_leggings',
               'copper_pickaxe', 'copper_shovel', 'copper_sword']

#: 不该被规则碰到的外家配方（抽样；任意一张判为竞争者都说明判定越界了）
HCS_UNTOUCHED = ['drying_rack', 'bandage_1', 'crude_torch', 'fiber_string_1']

MATERIAL = 'minecraft:copper_ingot'
STICK = 'minecraft:stick'

#: 离线兜底：2026-10-16 从 hcsurvival-0.19.2 的 data/hcsurvival/recipes/*.json 读出（X=铜锭 S=木棍）
FALLBACK_HCS = {
    'copper_axe_1': ['XX', 'XS', ' S'],
    'copper_axe_2': ['XX', 'SX', 'S '],
    'copper_boots': ['X X', 'X X'],
    'copper_chestplate': ['X X', 'XXX', 'XXX'],
    'copper_helmet': ['XXX', 'X X'],
    'copper_hoe_1': ['XX', ' S', ' S'],
    'copper_hoe_2': ['XX', 'S ', 'S '],
    'copper_leggings': ['XXX', 'X X', 'X X'],
    'copper_pickaxe': ['XXX', ' S ', ' S '],
    'copper_shovel': ['X', 'S', 'S'],
    'copper_sword': ['X', 'X', 'S'],
}

problems = []
notes = []


def ok(msg):
    notes.append(msg)


def bad(msg):
    problems.append(msg)


def cell_items(val, handle_values):
    """一个 key 值 → 这一格能接受的物品 id 集合；认不出来返回 None。

    `handle_values` 保留为空参数位（早前的手柄标签方案已废弃：1.20.1 的原版 TagLoader 遇到标签里
    引用不存在的物品会把整条标签丢掉，没装硬核生存的玩家会连带丢掉全部铜工具配方 —— 现在改用
    `copper_*_short_stick.json` 那组「短木棍版」条件配方）。
    """
    if isinstance(val, dict):
        if 'item' in val and isinstance(val['item'], str):
            return [val['item']]
        return None                                       # tag / 别的写法：判定不覆盖，返回 None 让人肉看
    if isinstance(val, list) and all(isinstance(v, str) for v in val):
        return list(val)                                  # 数组简写
    return None


def cells_of(recipe, handle_values):
    """shaped 配方 → (高, 宽, [逐格物品集合])；不是 shaped / 材料认不出来返回 None。"""
    if not isinstance(recipe, dict) or recipe.get('type') != 'minecraft:crafting_shaped':
        return None
    role = {}
    for sym, val in (recipe.get('key') or {}).items():
        items = cell_items(val, handle_values)
        if items is None:
            return None
        role[sym] = frozenset(items)
    rows = [r for r in (recipe.get('pattern') or [])]
    if not rows:
        return None
    width = max(len(r) for r in rows)
    cells = []
    for r in rows:
        for ch in r.ljust(width):
            cells.append(frozenset() if ch == ' ' else role.get(ch, frozenset({'?'})))
    return (len(rows), width, cells)


def rows_of_symbols(rows, handle_values):
    """兜底表（X=铜锭 S=木棍）→ 同一套 (高, 宽, cells) 结构。"""
    width = max(len(r) for r in rows)
    cells = []
    for r in rows:
        for ch in r.ljust(width):
            if ch == ' ':
                cells.append(frozenset())
            elif ch == 'X':
                cells.append(frozenset({MATERIAL}))
            elif ch == 'S':
                cells.append(frozenset({STICK}))
            else:
                return None
    return (len(rows), width, cells)


def overlap(a, b, mirror):
    """逐格（可选镜像）比集合：两边都空 = 一致；一边空一边有 = 不一致；都有则要求有交集。

    注意 `frozenset().isdisjoint(frozenset())` 是 True（空集与任何集合都"不相交"），
    所以空槽必须单独判 —— 否则头盔 / 胸甲这类带空格的图案会被整条判成"不抢同一批网格"。
    """
    height, width, ca = a
    _, _, cb = b
    for row in range(height):
        for col in range(width):
            # 镜像只作用在 a 一侧：拿 a 的镜像摆法去对 b 的正摆法
            i = row * width + (width - 1 - col if mirror else col)
            j = row * width + col
            x, y = ca[i], cb[j]
            if len(x) == 0 or len(y) == 0:
                if len(x) != len(y):
                    return False
                continue
            if x.isdisjoint(y):
                return False
    return True


def competes(a, b):
    """两条配方是否抢同一批网格：尺寸相同 + 逐格有交集（正摆或镜像摆）。"""
    if a is None or b is None or a[0] != b[0] or a[1] != b[1]:
        return False
    return overlap(a, b, False) or overlap(a, b, True)


def load_hcs(jar, handle_values):
    """从 hcsurvival 的 jar 里读铜装备与抽样配方；读不到返回 None（调用方退回内置表）。"""
    try:
        with zipfile.ZipFile(jar) as zf:
            def read(name):
                return json.loads(zf.read('data/hcsurvival/recipes/%s.json' % name))
            gear = {name: cells_of(read(name), handle_values) for name in HCS_RECIPES}
            other = {name: cells_of(read(name), handle_values) for name in HCS_UNTOUCHED}
            return gear, other
    except Exception as e:                                    # noqa: BLE001
        print('（读不到 hcsurvival jar：%s —— 退回内置表）' % e)
        return None


def main():
    ap = argparse.ArgumentParser(description='铜装备同形配方冲突门禁')
    ap.add_argument('--jar', default=None, help='hcsurvival 的 jar 路径（默认自动找开发机实例）')
    args = ap.parse_args()

    handle_values = []          # 手柄标签方案已废弃，见 cell_items 的说明

    jar = Path(args.jar) if args.jar else None
    if jar is None:
        cands = sorted(DEV_MODS.glob('*hcsurvival*.jar')) if DEV_MODS.is_dir() else []
        jar = cands[0] if cands else None

    loaded = load_hcs(jar, handle_values) if jar and jar.exists() else None
    if loaded:
        print('对照来源：%s' % jar.name)
        hcs_gear, hcs_other = loaded
    else:
        print('对照来源：内置兜底表（2026-10-16 从 hcsurvival-0.19.2 读出）')
        if jar is None:
            print('（实例 mods/ 里没找到 hcsurvival 的 jar）')
        hcs_gear = {n: rows_of_symbols(r, handle_values) for n, r in FALLBACK_HCS.items()}
        hcs_other = {}

    ours = {}
    for name in OURS:
        path = MOD_RECIPES / ('%s.json' % name)
        if not path.exists():
            bad('缺本模组配方 %s.json' % name)
            continue
        cells = cells_of(json.loads(path.read_text(encoding='utf-8')), handle_values)
        if cells is None:
            bad('本模组 %s.json 不是可判定的 shaped 配方（铜锭 / 手柄标签）' % name)
            continue
        ours[name] = cells

    # 断言 1：本模组 11 张都读得出来，其中 7 张带手柄槽
    handled = [n for n in ours if any(len(c) and 'minecraft:copper_ingot' not in c for c in ours[n][2])]
    if len(ours) == len(OURS) and len(handled) == 7:
        ok('本模组 %d 张铜装备配方全部可判定，其中 %d 张带手柄槽' % (len(ours), len(handled)))
    else:
        bad('本模组配方数不对：可判定 %d / %d，带手柄 %d（应为 7）'
            % (len(ours), len(OURS), len(handled)))

    # 断言 2：hcsurvival 每一条都与本模组某条抢同一批网格
    caught, miss = [], []
    for name, cells in sorted(hcs_gear.items()):
        if cells is None:
            bad('hcsurvival %s 不是可判定的 shaped 配方 —— 判定规则不覆盖它' % name)
            continue
        (caught if any(competes(cells, mine) for mine in ours.values()) else miss).append(name)
    if len(caught) == len(HCS_RECIPES) and not miss:
        ok('hcsurvival %d 张铜装备配方全部与本模组抢同一批网格（运行期会被剔除）' % len(caught))
    else:
        bad('漏判 hcsurvival 配方：%s' % (miss or '（张数对不上）'))

    # 断言 2b：「短木棍版」条件配方 —— 图案与 canonical 相同、手柄是短木棍、挂 hcsurvival 条件
    for tool in ('copper_axe', 'copper_hoe', 'copper_pickaxe', 'copper_shovel', 'copper_sword'):
        path = MOD_RECIPES / ('%s_short_stick.json' % tool)
        if not path.exists():
            bad('缺短木棍版条件配方 %s_short_stick.json' % tool)
            continue
        rec = json.loads(path.read_text(encoding='utf-8'))
        cells = cells_of(rec, handle_values)
        canon = ours.get(tool)
        cond_ok = {'type': 'forge:mod_loaded', 'modid': 'hcsurvival'} in (rec.get('conditions') or [])
        hint_ok = cells is not None and any('hcsurvival:short_stick' in c for c in cells[2])
        diffs = [] if (cells is None or canon is None) else [
            (a, b) for a, b in zip(cells[2], canon[2]) if set(a) != set(b)]
        if cells is None or canon is None or cells[:2] != canon[:2]:
            bad('%s_short_stick：尺寸与 canonical 不一致' % tool)
        elif not diffs:
            bad('%s_short_stick：与 canonical 完全一样（手柄槽没换成短木棍）' % tool)
        elif any(not (set(a) == {'hcsurvival:short_stick'} and set(b) == {STICK}) for a, b in diffs):
            bad('%s_short_stick：除「木棍 → 短木棍」之外的格子也动了' % tool)
        elif not cond_ok:
            bad('%s_short_stick：缺 forge:mod_loaded:hcsurvival 条件' % tool)
        elif not hint_ok:
            bad('%s_short_stick：手柄槽不是 hcsurvival:short_stick' % tool)
        else:
            ok('%s_short_stick：图案同 canonical，手柄 = 短木棍，挂 hcsurvival 条件' % tool)

    # 断言 3：canonical 与镜像变体互为竞争者（判定不是退化的）
    for base in ('copper_axe', 'copper_hoe'):
        mirror = base + '_mirror'
        if base in ours and mirror in ours and competes(ours[base], ours[mirror]):
            ok('%s 与 %s 互为竞争者（镜像摆法判得出来）' % (base, mirror))
        else:
            bad('%s 与 %s 没有被判为竞争者 —— 镜像口径失效' % (base, mirror))

    # 断言 4：规则有边界 —— 抽样的非铜装备配方一条都不抢
    if hcs_other:
        leaked = [n for n, cells in hcs_other.items()
                  if cells is not None and any(competes(cells, mine) for mine in ours.values())]
        if leaked:
            bad('规则越界：hcsurvival 的非铜装备配方被判为竞争者 → %s' % leaked)
        else:
            ok('抽样 %d 张 hcsurvival 非铜装备配方全部不受影响' % len(hcs_other))
    else:
        print('（无 jar，跳过「规则有边界」的抽样断言）')

    print()
    for line in notes:
        print('  ✓ %s' % line)
    if problems:
        print()
        for line in problems:
            print('  ✗ %s' % line)
        print('\nFAIL：铜装备同形配方门禁未过（%d 条）' % len(problems))
        return 1
    print('\nOK：铜装备同形配方门禁全绿。')
    return 0


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    sys.exit(main())
