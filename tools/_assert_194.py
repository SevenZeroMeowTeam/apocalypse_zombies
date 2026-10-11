print('=== 10/14 1.1.94：铜装备补齐铜斧 ===')
# 1.1.92 那批只做了剑/镐/锄 + 四件甲，漏了斧。这里除了查铜斧自己的「五件套」，还要盯住那条
# **最容易抄错**的数值 —— 斧抄的是石斧（9 点），不是石剑（5 点）：
#   原版 STONE_AXE = new AxeItem(Tiers.STONE, 7.0F, -3.2F) ⇒ 1 + 7 + 1 = 9
#   原版 STONE_SWORD = new SwordItem(Tiers.STONE, 3, -2.4F) ⇒ 1 + 3 + 1 = 5
import json as _json
import re as _re

_RES = 'F:/mcmod/src/main/resources/assets/apocalypse_zombies'
_items = open('F:/mcmod/src/main/java/com/apocalypse/zombies/registry/ModItems.java',
              encoding='utf-8').read()

check('ITEMS.register("copper_axe"' in _items, '注册了 copper_axe')
check('event.accept(COPPER_AXE);' in _items, '铜斧进了创造页')

# 数值：AxeItem(Tier, 伤害修正, 攻速修正)
_m = _re.search(r'new AxeItem\(ModTiers\.COPPER,\s*([\d.]+)F,\s*(-[\d.]+)F', _items)
check(_m is not None, '铜斧的 AxeItem 参数能从源码里读出来')
if _m:
    _dmg, _spd = float(_m.group(1)), float(_m.group(2))
    check(abs(_dmg - 7.0) < 1e-6,
          '铜斧伤害修正 %g == 石斧的 7.0（⇒ 都是 1+7+1 = 9 点，与石斧完全一致）' % _dmg)
    check(abs(_spd - (-3.2)) < 1e-6, '铜斧攻速修正 %g == 石斧的 -3.2' % _spd)
check('Tiers.STONE' not in _items, '没有误用原版 Tiers（铜走自己的 ModTiers.COPPER）')
check('new AxeItem(ModTiers.COPPER' in _items, '铜斧用铜那一档的 Tier（耐久/效率/挖掘等级随之）')

# 五件套
_mj = _json.load(open('%s/models/item/copper_axe.json' % _RES, encoding='utf-8'))
check(_mj['parent'] == 'minecraft:item/handheld', '铜斧模型走 handheld（与另三件工具一致）')
check(_mj['textures']['layer0'] == 'apocalypse_zombies:item/copper_axe', '模型指向自己的贴图')
check(os.path.isfile('%s/textures/item/copper_axe.png' % _RES), '铜斧贴图在')
for _lang, _v in (('zh_cn', '铜斧'), ('en_us', 'Copper Axe')):
    _lj = _json.load(open('%s/lang/%s.json' % (_RES, _lang), encoding='utf-8'))
    check(_lj.get('item.apocalypse_zombies.copper_axe') == _v, '%s 里 copper_axe = %s' % (_lang, _v))
_rj = _json.load(open('F:/mcmod/src/main/resources/data/apocalypse_zombies/recipes/copper_axe.json',
                      encoding='utf-8'))
check(_rj['type'] == 'minecraft:crafting_shaped', '铜斧是有序合成')
check(_rj['pattern'] == ['XXX', 'XSX', ' S '], '配方是原版斧形（三锭 + 两棍）', str(_rj['pattern']))
check(_rj['result']['item'] == 'apocalypse_zombies:copper_axe', '产物指向自己')
check('minecraft:copper_ingot' in {v['item'] for v in _rj['key'].values()}, '用铜锭合成')

# 生成器的映射表也得有它，否则下次重跑贴图会漏掉这一张
_art = open('F:/mcmod/tools/copper_gear_art.py', encoding='utf-8').read()
check("'textures/item/iron_axe.png', 'textures/item/copper_axe.png'" in _art,
      '贴图生成器映射表里有 iron_axe → copper_axe')
check(_art.count("'textures/item/copper_") == 8,
      '映射表覆盖 8 件物品贴图（1.1.92 的 7 件 + 斧）',
      '实得 %d' % _art.count("'textures/item/copper_"))

# 上一版那七件别在这次改动里被碰坏：全库铜装备共 8 件
for _n in ('copper_sword', 'copper_pickaxe', 'copper_hoe', 'copper_axe',
           'copper_helmet', 'copper_chestplate', 'copper_leggings', 'copper_boots'):
    check('ITEMS.register("%s"' % _n in _items, '铜装备 %s 仍在册' % _n)
check(_items.count('event.accept(COPPER_') == 8, '八件铜装备都进了创造页',
      '实得 %d' % _items.count('event.accept(COPPER_'))

# 文档
_rd = open('F:/mcmod/readme.md', encoding='utf-8').read()
check('### 1.1.94 —' in _rd, 'readme 有 1.1.94 条目')
check('| **当前版本** | `1.1.94` |' in _rd, 'readme 头表 == 1.1.94')
check('## 1.1.94 ——' in open('F:/mcmod/docs/wiki/07-出货与版本管理.md', encoding='utf-8').read(),
      'wiki 07 有 1.1.94 小节')
check('铜斧' in open('F:/mcmod/docs/wiki/02-代码与资源地图.md', encoding='utf-8').read(),
      'wiki 02 记了铜斧')
