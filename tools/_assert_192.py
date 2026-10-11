print('=== 8/12 1.1.92：一整套铜装备（剑 / 镐 / 锄 / 头盔 / 胸甲 / 护腿 / 靴） ===')
# 三条口径是玩家点名的，这里对原版数值逐条验：
#   ① 耐久比石高；② 武器伤害与石一样；③ 护甲比皮革高、比铁低（落在整套总和上）。
# 另外查七件物品的「五件套」——注册 / 模型 / 贴图 / lang / 配方，缺一样就是物品栏里的紫黑方块。
import json as _json
import re as _re

# 原版参照值（1.20.1 Tiers / ArmorMaterials），钉成常量：谁改了铜，这里就得跟着解释一遍
_STONE_USES, _STONE_DMG, _STONE_SPEED, _STONE_ENCH = 131, 1.0, 4.0, 5
_LEATHER_DEF, _IRON_DEF, _COPPER_DEF = 7, 15, 10

_ITEMS = ('copper_sword', 'copper_pickaxe', 'copper_hoe',
          'copper_helmet', 'copper_chestplate', 'copper_leggings', 'copper_boots')
_RES = 'F:/mcmod/src/main/resources/assets/apocalypse_zombies'

# ---- ① 工具档 ----
_tiers = open('F:/mcmod/src/main/java/com/apocalypse/zombies/registry/ModTiers.java',
              encoding='utf-8').read()
check('public static final Tier COPPER = new ForgeTier(' in _tiers, 'ModTiers 里有 COPPER 这一档')
# 参数之间的行尾注释要先剥掉，否则 \s* 跨不过 "// 耐久：石 131 → 高"
_m = _re.search(r'new ForgeTier\((.*?)\);', _tiers, _re.S)
_args = _re.sub(r'//[^\n]*', '', _m.group(1)) if _m else ''
_nums = _re.findall(r'\d+(?:\.\d+)?', _args)
check(len(_nums) >= 5, 'ForgeTier 的五个数值能从源码里读出来', str(_nums))
if len(_nums) >= 5:
    _lvl, _uses, _speed, _dmg, _ench = (int(_nums[0]), int(_nums[1]), float(_nums[2]),
                                        float(_nums[3]), int(_nums[4]))
    check(_uses > _STONE_USES, '① 铜工具耐久 %d 比石 %d 高' % (_uses, _STONE_USES))
    check(abs(_dmg - _STONE_DMG) < 1e-6,
          '② 铜攻击加成 %g 与石 %g 相同（⇒ 铜剑伤害 == 石剑）' % (_dmg, _STONE_DMG))
    check(_lvl == 1, '挖掘等级同石（能挖铁矿石、挖不动钻石）')
    check(_STONE_SPEED < _speed < 6.0, '效率 %.1f 落在石 %.1f 与铁 6.0 之间' % (_speed, _STONE_SPEED))
    check(_STONE_ENCH < _ench < 14, '附魔性 %d 落在石 %d 与铁 14 之间' % (_ench, _STONE_ENCH))
check('Items.COPPER_INGOT' in _tiers, '修复材料是铜锭')
check('BlockTags.NEEDS_STONE_TOOL' in _tiers, '可采方块标签与等级 1 配套（NEEDS_STONE_TOOL）')

# ---- ③ 护甲材质 ----
_arm = open('F:/mcmod/src/main/java/com/apocalypse/zombies/registry/ModArmorMaterials.java',
            encoding='utf-8').read()
check('implements ArmorMaterial' in _arm, '铜甲是自建 ArmorMaterial')
for _slot, _v in (('HELMET', 2), ('CHESTPLATE', 4), ('LEGGINGS', 3), ('BOOTS', 1)):
    check('case %s -> %d;' % (_slot, _v) in _arm, '③ 护甲值 %s = %d' % (_slot, _v))
check(_LEATHER_DEF < _COPPER_DEF < _IRON_DEF,
      '③ 整套护甲合计 %d 落在皮革 %d 与铁 %d 之间' % (_COPPER_DEF, _LEATHER_DEF, _IRON_DEF))
check('return type.getDurability' not in _arm,
      '没再用 1.20.1 不存在的 ArmorItem.Type.getDurability(int)（那是 1.20.5 才加的）')
check('case HELMET -> 11;' in _arm and 'case BOOTS -> 13;' in _arm,
      '耐久按部位写明基础值（头 11 / 胸 16 / 腿 15 / 靴 13）')
check('ApocalypseZombies.MOD_ID + ":" + name' in _arm,
      '穿戴贴图名带命名空间（copper_layer_1/2.png 才对得上）')

# ---- 五件套 ----
_items = open('F:/mcmod/src/main/java/com/apocalypse/zombies/registry/ModItems.java',
              encoding='utf-8').read()
for _n in _ITEMS:
    check('ITEMS.register("%s"' % _n in _items, '注册了 %s' % _n)
check('CreativeModeTabs.TOOLS_AND_UTILITIES' in _items, '镐与锄进了工具页')
for _c in ('COPPER_SWORD', 'COPPER_HELMET', 'COPPER_CHESTPLATE', 'COPPER_LEGGINGS', 'COPPER_BOOTS'):
    check('event.accept(%s);' % _c in _items, '%s 进了创造页' % _c)

_ARMOURY = ('helmet', 'chestplate', 'leggings', 'boots')
for _n in _ITEMS:
    _mj = _json.load(open('%s/models/item/%s.json' % (_RES, _n), encoding='utf-8'))
    _want = 'minecraft:item/generated' if any(k in _n for k in _ARMOURY) else 'minecraft:item/handheld'
    check(_mj.get('parent') == _want, '%s 的模型 parent = %s' % (_n, _want))
    check(_mj['textures']['layer0'] == 'apocalypse_zombies:item/' + _n,
          '%s 的模型指向自己的贴图' % _n)
    check(os.path.isfile('%s/textures/item/%s.png' % (_RES, _n)), '%s 的物品贴图在' % _n)
for _n in ('copper_layer_1', 'copper_layer_2'):
    check(os.path.isfile('%s/textures/models/armor/%s.png' % (_RES, _n)),
          '穿戴图层 %s.png 在（文件名必须与 getName() 一致）' % _n)

for _lang, _names in (('zh_cn', ('铜剑', '铜镐', '铜锄', '铜头盔', '铜胸甲', '铜护腿', '铜靴')),
                      ('en_us', ('Copper Sword', 'Copper Pickaxe', 'Copper Hoe', 'Copper Helmet',
                                 'Copper Chestplate', 'Copper Leggings', 'Copper Boots'))):
    _lj = _json.load(open('%s/lang/%s.json' % (_RES, _lang), encoding='utf-8'))
    for _k, _v in zip(_ITEMS, _names):
        check(_lj.get('item.apocalypse_zombies.' + _k) == _v,
              '%s 里 %s = %s' % (_lang, _k, _v))

for _n in _ITEMS:
    _rj = _json.load(open('F:/mcmod/src/main/resources/data/apocalypse_zombies/recipes/%s.json'
                          % _n, encoding='utf-8'))
    check(_rj['type'] == 'minecraft:crafting_shaped', '%s 是有序合成' % _n)
    check(_rj['result']['item'] == 'apocalypse_zombies:' + _n, '%s 的产物指向自己' % _n)
    check('minecraft:copper_ingot' in {v['item'] for v in _rj['key'].values()},
          '%s 用铜锭合成' % _n)

# ---- 文档 ----
_rd = open('F:/mcmod/readme.md', encoding='utf-8').read()
check('### 1.1.92 —' in _rd, 'readme 有 1.1.92 条目')
check('| **当前版本** | `1.1.92` |' in _rd, 'readme 头表 == 1.1.92')
_w7 = open('F:/mcmod/docs/wiki/07-出货与版本管理.md', encoding='utf-8').read()
check('## 1.1.92 ——' in _w7, 'wiki 07 有 1.1.92 小节')
_w6 = open('F:/mcmod/docs/wiki/06-工具脚本手册.md', encoding='utf-8').read()
check('copper_gear_art.py' in _w6, 'wiki 06 收录了贴图生成器')
_w2 = open('F:/mcmod/docs/wiki/02-代码与资源地图.md', encoding='utf-8').read()
check('ModTiers' in _w2 and 'ModArmorMaterials' in _w2, 'wiki 02 记了两个新注册表')
