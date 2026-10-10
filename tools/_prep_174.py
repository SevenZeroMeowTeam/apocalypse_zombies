# -*- coding: utf-8 -*-
"""1.1.74 出货准备：升版本（gradle.properties + readme）+ 从 _deploy_173.py 派生 _deploy_174.py。"""
import re
from pathlib import Path

NL = chr(10)
ROOT = Path('F:/mcmod')
VER, PREV = '1.1.74', '1.1.73'
fails = []

# ---------------------------------------------------------------- gradle.properties
gp = ROOT / 'gradle.properties'
s = gp.read_text(encoding='utf-8')
if VER in s:
    print('(1) gradle.properties 已是 %s' % VER)
else:
    s2 = re.sub(r'mod_version\s*=\s*' + re.escape(PREV), 'mod_version=%s' % VER, s, count=1)
    if s2 == s:
        fails.append('gradle.properties 里没找到 mod_version=%s' % PREV)
    else:
        gp.write_text(s2, encoding='utf-8')
        print('(1) gradle.properties mod_version → %s' % VER)

# ---------------------------------------------------------------- readme
rd = ROOT / 'readme.md'
s = rd.read_text(encoding='utf-8')
if ('### %s ' % VER) in s:
    print('(2) readme 已有 %s 段' % VER)
else:
    sec = NL.join([
        '### %s — 2026-10-10' % VER,
        '',
        '**她会走路了：开门、浮水、绕开挡路的、自己跨过坑，还会跟着你不被甩掉。**',
        '',
        '- **导航换成玩家式**（`CatGirlNavigation`）：原版跟班用的默认导航把门当墙、把水当死路 ——',
        '  现在她能推开门走过去、落水会浮着走、也不绕太阳。',
        '- **开路**（`CatGirlClearWayGoal`）：导航走不通时，砸掉挡路的自然方块（原木/树叶/土/沙/圆石类/雪），',
        '  掉落照旧走她那一套（含 `always_drops`）。**绝不碰**箱子·熔炉·工作台这类带方块实体的、也不碰门；',
        '  硬度 3.0 以上（黑曜石/残骸）不砸。开关 `clear_way`。',
        '- **搭桥**（`CatGirlBridgeGoal`）：正前方是坑（深谷/水/岩浆）时，用**她自己背包里**的实心方块铺一格落脚点，',
        '  铺完重算路径。背包里没砖就不过去 —— 和你一样。开关 `bridge`。',
        '- **自己出门找目标**：搜索半径取 `work_radius` 与新的 `autonomy_radius`（默认 32）的较大值，',
        '  所以老存档里写死 12 也不会把她关在院子里。',
        '- **不跟丢**：跟随速度走 `follow_speed`（默认 1.3，原版跟班 1.15），主人跑起来时她能跟上；',
        '  主人离她超过 `autonomy_radius` 时她先跟人再干活。',
        '',
        '### %s — 2026-10-10' % PREV,
    ])
    if '### %s — 2026-10-10' % PREV not in s:
        fails.append('readme 里找不到 1.1.73 段锚点')
    else:
        s = s.replace('### %s — 2026-10-10' % PREV, sec, 1)
        # 头表当前版本行
        lines = s.split(NL)
        hit = False
        for i, line in enumerate(lines):
            if line.startswith('| **当前版本** |') and PREV in line:
                lines[i] = line.replace(PREV, VER, 1)
                hit = True
                break
        if not hit:
            fails.append('readme 头表「当前版本」行没找到 %s' % PREV)
        rd.write_text(NL.join(lines), encoding='utf-8')
        print('(2) readme：+ ### %s 段 + 头表 → %s' % (VER, VER))

# ---------------------------------------------------------------- 派生 _deploy_174.py
src = (ROOT / 'tools/_deploy_173.py').read_text(encoding='utf-8')
src = src.replace('"""1.1.73 出货：订做指定物品 + 盔甲渲染层 + 内部熔炉 + 月亮三项（含 1.1.72 全部不回归）',
                  '"""1.1.74 出货：像玩家一样操作第一批 —— 开门/浮水导航 + 开路 + 搭桥 + 自己出门找目标 + 不跟丢（含 1.1.73 全部不回归）', 1)
src = src.replace("VER = '1.1.73'", "VER = '1.1.74'", 1)
src = src.replace("PREV = '1.1.72'", "PREV = '1.1.73'", 1)
src = src.replace("description='1.1.73 出货：订做 / 盔甲层 / 熔炼 / 月亮'",
                  "description='1.1.74 出货：玩家式操作（导航 / 开路 / 搭桥 / 找目标 / 跟随）'", 1)
src = src.replace('  1. 构建产物存在，且 jar 内 mods.toml 的 version == 1.1.73；',
                  '  1. 构建产物存在，且 jar 内 mods.toml 的 version == 1.1.74；', 1)
src = src.replace('py tools/_deploy_173.py', 'py tools/_deploy_174.py')
for a, b in (('1/6', '1/7'), ('2/6', '2/7'), ('3/6', '3/7'), ('4/6', '5/7'),
             ('5/6', '6/7'), ('6/6', '7/7')):
    src = src.replace(a, b)

BLOCK = '''print('=== 4/7 1.1.74：像玩家一样操作（第一批）===')
_cw = pathlib.Path('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/ai/CatGirlClearWayGoal.java')
_br = pathlib.Path('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/ai/CatGirlBridgeGoal.java')
_nv = pathlib.Path('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/ai/CatGirlNavigation.java')
check(_nv.is_file() and _cw.is_file() and _br.is_file(), '导航 / 开路 / 搭桥三个新类在源码里')
for _c in ('entity/ai/CatGirlNavigation.class', 'entity/ai/CatGirlClearWayGoal.class',
           'entity/ai/CatGirlBridgeGoal.class'):
    check(any(n.endswith(_c) for n in names), '进包：%s' % _c.split('/')[-1])
_ent2 = open('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/CatGirlEntity.java',
             encoding='utf-8').read()
check('createNavigation' in _ent2 and 'CatGirlNavigation(this, level)' in _ent2,
      '实体已换成玩家式导航（开门 / 浮水）')
check('CatGirlClearWayGoal(this)' in _ent2 and 'CatGirlBridgeGoal(this)' in _ent2,
      '开路 / 搭桥已注册进 goalSelector')
check('Config.CAT_GIRL_FOLLOW_SPEED.get()' in _ent2, '跟随速度走 Config.follow_speed')
check('harvestBlockHard' in _ent2 and 'NETHERITE_PICKAXE' in _ent2,
      '开路走她自己的掉落规则（always_drops 不被绕开）')
_cws = _cw.read_text(encoding='utf-8') if _cw.is_file() else ''
check('hasBlockEntity()' in _cws and 'MAX_HARDNESS' in _cws and 'defaultDestroyTime' in _cws,
      '开路边界：无方块实体 + 硬度上限')
check('BlockTags.LOGS' in _cws and 'BlockTags.DIRT' in _cws and 'Blocks.GRAVEL' in _cws,
      '开路白名单是自然方块')
check('Goal.Flag.MOVE' in _cws, '开路抢 MOVE 标记（拿不到就干不了活）')
_brs = _br.read_text(encoding='utf-8') if _br.is_file() else ''
check('BlockItem' in _brs and 'getGoods()' in _brs and 'shrink(1)' in _brs,
      '搭桥只用她自己背包里的方块并扣掉')
check('canBeReplaced' in _brs, '搭桥只在空格上落脚（不乱铺）')
_cfg2 = open('F:/mcmod/src/main/java/com/apocalypse/zombies/Config.java', encoding='utf-8').read()
for _k in ('"autonomy_radius"', '"clear_way"', '"bridge"', '"follow_speed"'):
    check(_k in _cfg2, 'Config 有 1.1.74 开关 %s' % _k)
_wbg = open('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/ai/WorkBlockGoal.java',
            encoding='utf-8').read()
check('CAT_GIRL_AUTONOMY_RADIUS' in _wbg, '找目标半径取 work_radius/autonomy_radius 的较大值')
check('getOwner()' in _wbg and 'leash' in _wbg, '主人跑远先跟人（牵引闸门）')

'''
anchor = "print('=== 3/7 不回归"
if anchor not in src:
    fails.append('派生脚本里找不到不回归段锚点')
else:
    src = src.replace(anchor, BLOCK + anchor, 1)
(Root := ROOT / 'tools/_deploy_174.py').write_text(src, encoding='utf-8')
print('(3) _deploy_174.py 生成（%d 字节）' % len(src))

print(NL + ('全部命中' if not fails else '失败 %d 条：' % len(fails)))
for f in fails:
    print('  [FAIL] ' + f)
(ROOT / 'build' / 'p174_note.txt').write_text(NL.join(fails), encoding='utf-8')
