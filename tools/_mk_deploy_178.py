# -*- coding: utf-8 -*-
"""从 _deploy_177.py 生成 _deploy_178.py：换版本号 + 插入 1.1.78 那一节门禁。

一次性工具（生成完就可以删），产物 = tools/_deploy_178.py。
"""
import io
import pathlib
import re

SRC = pathlib.Path('F:/mcmod/tools/_deploy_177.py')
DST = pathlib.Path('F:/mcmod/tools/_deploy_178.py')

s = SRC.read_text(encoding='utf-8')

s = s.replace("VER = '1.1.77'", "VER = '1.1.78'")
s = s.replace("PREV = '1.1.76'", "PREV = '1.1.77'")
s = s.replace('1.1.77 出货：猫耳娘**自己做材料/物品**（「有没有」→「够不够」的补料记账 + 成品装备不进炉）（含 1.1.76 全部不回归）',
              '1.1.78 出货：**全功能镐子/工具**（什么都能挖、都有掉落，保护名单除外）+ **一键挖掘订单**'
              '（/apocalypse catgirl mine，范围/上限走配置）+ **就近去工作方块干活、缺则自己做**'
              '（含 1.1.77 全部不回归）')
s = s.replace("_ap = argparse.ArgumentParser(description='1.1.77 出货：她自己会做材料/物品')",
              "_ap = argparse.ArgumentParser(description='1.1.78 出货：全功能镐子 + 一键挖掘 + 工作方块')")

SECTION = """
print('=== 10/9 1.1.78：全功能镐子 / 一键挖掘 / 工作方块 ===')
_p = 'F:/mcmod/src/main/java/com/apocalypse/zombies/'
_cfg5 = open(_p + 'Config.java', encoding='utf-8').read()
for _k in ('"universal_tool"', '"mine_all"', '"mine_protected"', '"mine_radius"',
           '"mine_max_blocks"', '"station_use"', '"station_radius"', '"station_self_craft"'):
    check(_k in _cfg5, 'Config 有 1.1.78 项 %s' % _k)
check('defineInRange("mine_radius", 24, 4, 64)' in _cfg5, '范围默认 24（4~64）')
check('defineInRange("mine_max_blocks", 256, 1, 4096)' in _cfg5, '一键挖掘数量上限默认 256（1~4096）')
check('defineInRange("station_radius", 16, 2, 64)' in _cfg5, '工作方块搜索半径默认 16（2~64）')
check('"minecraft:bedrock"' in _cfg5, '保护名单里钉着基岩（她永远不挖）')
check('defineList("mine_protected"' in _cfg5 and '"minecraft:spawner"' in _cfg5,
      '保护名单是可增删的列表（默认含刷怪笼）')
check('define("universal_tool", true)' in _cfg5 and 'define("mine_all", true)' in _cfg5
      and 'define("station_use", true)' in _cfg5 and 'define("station_self_craft", true)' in _cfg5,
      '四个新开关默认开')

_hv = open(_p + 'entity/CatGirlHarvest.java', encoding='utf-8').read()
check('public static boolean isMineable(' in _hv and 'protectedExtra()' in _hv,
      '挖矿判定：白名单 + 保护名单')
check('forge", "ores"' in _hv, '矿石标签走 forge:ores（1.20.1 没有 minecraft:ores）')
check('public static boolean breakAndCollect(' in _hv and 'dropTool(' in _hv and 'proxyFor(' in _hv,
      '唯一的破坏出口：掉掉落 + 换对口工具 + 收进库存')
check('hasBlockEntity()' in _hv and 'FluidState' in _hv, '保护边界：方块实体 / 流体一律不碰')

_st = pathlib.Path('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/CatGirlStation.java')
_go = pathlib.Path('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/ai/CatGirlStationGoal.java')
check(_st.is_file() and _go.is_file(), 'CatGirlStation / CatGirlStationGoal 两个新类在源码里')
check(any(n.endswith('entity/CatGirlStation.class') for n in names), '进包：CatGirlStation.class')
check(any(n.endswith('entity/ai/CatGirlStationGoal.class') for n in names), '进包：CatGirlStationGoal.class')
_sts = _st.read_text(encoding='utf-8') if _st.is_file() else ''
check('canBeReplaced()' in _sts and 'isFaceSturdy' in _sts and 'hasBlockEntity()' in _sts,
      '放工作方块：只认可替换位置 + 实心支撑 + 无方块实体')
check('CRAFTING_TABLE' in _sts and 'FURNACE' in _sts and 'BLAST_FURNACE' in _sts,
      '认合成台 / 熔炉（含高炉 / 烟熏炉）')
_gos = _go.read_text(encoding='utf-8') if _go.is_file() else ''
check('CAT_GIRL_STATION_SELF_CRAFT' in _gos and 'CatGirlCrafting.selfMake' in _gos,
      '就近没有 → 她自己做（受 station_self_craft 约束）')
check('setStation(' in _gos and 'REACH' in _gos, '走到位才认下台子（到位后交给制作那一侧）')

_cr = open(_p + 'entity/CatGirlCrafting.java', encoding='utf-8').read()
check('public static CatGirlStation.Kind wantedWork(' in _cr,
      '只探需求、不动库存的「想去哪种台子」探测在')
check('public static Result selfMake(' in _cr, '她自己做一件进自己库存的入口在')
check('private static boolean atStation(' in _cr and 'CAT_GIRL_STATION_USE' in _cr,
      '站台门槛（station_use）在')
check('LAST_RUN.computeIfAbsent(cat.getUUID()' in _cr,
      '自动制作按**每个个体**记账（修掉「第二只永远不会做东西」）')
check('furnaceOnly' in _cr, '炉子专属才去熔炉（免得为铁锭跑去合成台干等）')

_ent5 = open(_p + 'entity/CatGirlEntity.java', encoding='utf-8').read()
check('new CatGirlStationGoal(this)' in _ent5, '工作方块目标已注册进 goalSelector')
check('public void orderMine(' in _ent5 and 'public void minedOne(' in _ent5
      and 'public boolean matchesMineOrder(' in _ent5,
      '一键挖掘订单：下单 / 记账 / 匹配 三件套在')
check('CatGirlMineBlock' in _ent5 and 'CatGirlMineLeft' in _ent5, '订单进 NBT（读档接着挖）')
check('public boolean isMineOrderTarget(' in _ent5, '订单目标判定在（含保护名单）')
check('stationNear(' in _ent5 and 'isAtStation(' in _ent5 and 'setStation(' in _ent5,
      '工作方块的就近查找（带缓存）/ 到位判定 / 认领 都在实体上')

_wb = open(_p + 'entity/ai/WorkBlockGoal.java', encoding='utf-8').read()
check('WorkBlockGoal.forOrder' in _ent5 and 'orderMode' in _wb and 'minedOne' in _wb,
      '一键挖掘复用劳作目标（订单没了目标立刻不成立）')
check('CAT_GIRL_MINE_RADIUS' in _wb and 'CAT_GIRL_WORK_RADIUS' in _wb,
      '找目标半径取 mine_radius / work_radius 的较大值')

_cmd5 = open(_p + 'command/ApocalypseCommand.java', encoding='utf-8').read()
check('Commands.literal("mine")' in _cmd5 and 'catgirlMine(' in _cmd5 and 'catgirlMineStop(' in _cmd5,
      '/apocalypse catgirl mine <方块id> [数量] 与 mine stop 在命令表里')
check('CAT_GIRL_MINE_MAX_BLOCKS' in _cmd5 and 'Math.min(count, max)' in _cmd5,
      '命令里的数量被配置上限夹住（写多大都越不过去）')
check('isProtected(state, CatGirlHarvest.protectedExtra())' in _cmd5,
      '保护名单里的方块直接拒单（基岩挖不了）')
check('hasBlockEntity()' in _cmd5, '容器 / 方块实体类方块拒单')
for _lf in ('en_us.json', 'zh_cn.json'):
    _ls = open('F:/mcmod/src/main/resources/assets/apocalypse_zombies/lang/' + _lf, encoding='utf-8').read()
    check('"cat_girl.mine.done"' in _ls, 'lang %s 有订单完成提示键' % _lf)

_rd = open('F:/mcmod/readme.md', encoding='utf-8').read()
check('| **当前版本** | `1.1.78` |' in _rd, 'readme 头表版本 == 1.1.78')
check('/apocalypse catgirl mine <方块id> [数量]' in _rd, 'readme 有 mine 指令')
check('/apocalypse catgirl mine stop' in _rd, 'readme 有 mine stop')
check('mine_max_blocks' in _rd and 'mine_radius' in _rd, 'readme 写明范围 / 上限两项配置')
"""

anchor = "print('=== 最后：工程门禁（本机实跑） ===')"
assert anchor in s, '锚点没找到'
s = s.replace(anchor, SECTION.strip() + '\n\n' + anchor, 1)

# 1.1.78 把「工具等级豁免 / always_drops」从 WorkBlockGoal 收拢进 CatGirlHarvest，
# 旧断言还指着老地址 —— 改指新家（行为没变，只是断言的坐标要跟上）。
_legacy = [
    ("check('CAT_GIRL_ALWAYS_DROPS' in work and 'NETHERITE_PICKAXE' in work,\n      '砸什么都有掉（无视原版工具等级）')",
     "_hv0 = open('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/CatGirlHarvest.java', encoding='utf-8').read()\n"
     "check('CAT_GIRL_ALWAYS_DROPS' in _hv0 and 'NETHERITE_PICKAXE' in _hv0 and 'dropTool(' in _hv0,\n"
     "      '砸什么都有掉（无视原版工具等级）—— 1.1.78 起规则在 CatGirlHarvest')"),
    ("check('harvestBlockHard' in _ent2 and 'NETHERITE_PICKAXE' in _ent2,\n      '开路走她自己的掉落规则（always_drops 不被绕开）')",
     "check('harvestBlockHard' in _ent2 and 'CatGirlHarvest.breakAndCollect' in _ent2,\n"
     "      '开路走她自己的掉落规则（always_drops 不被绕开）')"),
    ("check('public boolean isMineOrderTarget(' in _ent5, '订单目标判定在（含保护名单）')",
     "check('boolean isMineOrderTarget(' in _ent5, '订单目标判定在（含保护名单）')"),
]
for _old, _new in _legacy:
    assert _old in s, '旧断言没找到：%r' % _old[:60]
    s = s.replace(_old, _new, 1)

DST.write_text(s, encoding='utf-8')
print('写入 %s（%d 行 / %d 字节）' % (DST, s.count('\n') + 1, len(s)))
