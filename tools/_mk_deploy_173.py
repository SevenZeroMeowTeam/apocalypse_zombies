# -*- coding: utf-8 -*-
"""从 _deploy_172.py 派生 _deploy_173.py：升版本 + 追加 1.1.73 判据块。"""
from pathlib import Path

NL = chr(10)
src = Path('tools/_deploy_172.py').read_text(encoding='utf-8')

src = src.replace('"""1.1.72 出货：猫耳娘配方表（自动同步原版 + 全部模组配方）',
                  '"""1.1.73 出货：订做指定物品 + 盔甲渲染层 + 内部熔炉 + 月亮三项（含 1.1.72 全部不回归）', 1)
src = src.replace("VER = '1.1.72'", "VER = '1.1.73'", 1)
src = src.replace("PREV = '1.1.71'", "PREV = '1.1.72'", 1)
src = src.replace("description='1.1.72 出货：猫耳娘 v4'", "description='1.1.73 出货：订做 / 盔甲层 / 熔炼 / 月亮'", 1)
src = src.replace('  1. 构建产物存在，且 jar 内 mods.toml 的 version == 1.1.72；',
                  '  1. 构建产物存在，且 jar 内 mods.toml 的 version == 1.1.73；', 1)
src = src.replace('py tools/_deploy_166.py --build        # 先 ./gradlew build 再出货',
                  'py tools/_deploy_173.py --build        # 先 ./gradlew build 再出货', 1)
src = src.replace('py tools/_deploy_166.py                # 用 build/libs 里已构建好的包',
                  'py tools/_deploy_173.py                # 用 build/libs 里已构建好的包', 1)
src = src.replace('先跑 py tools/_deploy_166.py --build', '先跑 py tools/_deploy_173.py --build', 1)
src = src.replace('print(\'=== 3/5 不回归', 'print(\'=== 3/6 不回归', 1)
src = src.replace("print('=== 4/5 工程门禁（本机实跑） ===')", "print('=== 5/6 工程门禁（本机实跑） ===')", 1)
src = src.replace("print('=== 5/5 基线校验 + 换包 ===')", "print('=== 6/6 基线校验 + 换包 ===')", 1)

BLOCK = '''print('=== 4/6 1.1.73：订做 / 盔甲层 / 熔炼 / 月亮三项 ===')
cfgsrc = open('F:/mcmod/src/main/java/com/apocalypse/zombies/Config.java', encoding='utf-8').read()
for _k in ('"craft_fee"', '"smelt"', '"armor_render"', '"blood_moon_spawn"',
           '"blood_moon_spawn_interval"', '"blood_moon_spawn_count"'):
    check(_k in cfgsrc, 'Config 有 1.1.73 开关 %s' % _k)
craft = open('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/CatGirlCrafting.java',
             encoding='utf-8').read()
check('TransientCraftingContainer' in craft and 'recipe.matches(grid, level)' in craft,
      '3x3 摆放：配方形状铺进网格 + 原版 matches 点头')
check('craftOrder' in craft and 'NO_MATERIALS' in craft and 'NO_COINS' in craft,
      '订做：材料不足/币不足分别给结论')
check('smeltOne' in craft and 'RecipeType.SMELTING' in craft and 'AbstractFurnaceBlockEntity.isFuel' in craft,
      '内部熔炉：走原版冶炼配方 + 燃料判定')
check('BuiltInRegistries.ITEM.getOptional' in craft, '按物品 id 查物品（命令用）')
cmenusrc = open('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/menu/CatGirlTradeMenu.java',
                encoding='utf-8').read()
check('orderInput' in cmenusrc and 'orderResult' in cmenusrc and 'updateOrder' in cmenusrc,
      '界面下单槽：样品 → 成品（取走再续单）')
check('getCraftFee' in cmenusrc, '界面能显示手续费')
cmdsrc = open('F:/mcmod/src/main/java/com/apocalypse/zombies/command/ApocalypseCommand.java',
              encoding='utf-8').read()
check('Commands.literal("craft")' in cmdsrc and 'StringArgumentType.word()' in cmdsrc,
      '/apocalypse catgirl craft <物品id> [数量] 在')
for _lf in ('en_us.json', 'zh_cn.json'):
    _ls = open('F:/mcmod/src/main/resources/assets/apocalypse_zombies/lang/' + _lf, encoding='utf-8').read()
    check('"cat_girl.trade.order"' in _ls and '"cat_girl.order.no_materials"' in _ls,
          'lang %s 有下单相关键' % _lf)
_layer = pathlib.Path('F:/mcmod/src/main/java/com/apocalypse/zombies/client/renderer/CatGirlArmorLayer.java')
check(_layer.is_file(), 'CatGirlArmorLayer.java 在')
_ls2 = _layer.read_text(encoding='utf-8') if _layer.is_file() else ''
check('HumanoidModel' in _ls2 and 'prepMatrixForBone' in _ls2 and 'armorCutoutNoCull' in _ls2
      and 'PLAYER_INNER_ARMOR' in _ls2 and 'PLAYER_OUTER_ARMOR' in _ls2,
      '盔甲层：原版网格（内/外层）贴到她的骨骼')
check('"head"' in _ls2 and '"right_arm"' in _ls2 and '"left_leg"' in _ls2 and '"right_foot"' in _ls2,
      '盔甲层覆盖 头/身/双臂/双腿/双脚')
_rsrc = open('F:/mcmod/src/main/java/com/apocalypse/zombies/client/renderer/CatGirlGeoRenderer.java',
             encoding='utf-8').read()
check('new CatGirlArmorLayer(this)' in _rsrc, '渲染器挂上盔甲层')
check('CatGirlArmorLayer.class' in names, '盔甲层类进包')
_mo = open('F:/mcmod/src/main/java/com/apocalypse/zombies/moon/MoonEvent.java', encoding='utf-8').read()
for _hex, _name in (('0x55AAFF', 'BLUE_MOON'), ('0x88CCFF', 'SUPER_BLUE_MOON'),
                    ('0xFF5555', 'BLOOD_MOON'), ('0xFFE055', 'YELLOW_MOON'),
                    ('0xFFCC55', 'SUPER_YELLOW_MOON'), ('0xCC44FF', 'SUPER_BLOOD_MOON')):
    check(_hex in _mo, '月相 tint 对齐 CD：%s = %s' % (_name, _hex))
_mm = open('F:/mcmod/src/main/java/com/apocalypse/zombies/moon/MoonEventManager.java',
           encoding='utf-8').read()
check('spawnBloodMoonWave' in _mm and 'isBloodMoon()' in _mm,
      '血月主动刷怪（isBloodMoon 闸门 + 节流）')
check('EntityType.ZOMBIE.create' in _mm and 'finalizeSpawn' in _mm,
      '刷的是原版僵尸并走 finalizeSpawn（吃尸潮倍率）')

'''
anchor = "print('=== 3/6 不回归"
assert anchor in src
src = src.replace(anchor, BLOCK + anchor, 1)
src = src.replace("print('=== 2/5 包内自检：猫耳娘 v4 ===')", "print('=== 2/6 包内自检：猫耳娘 v4 ===')", 1)
src = src.replace("print('=== 1/5 构建产物 ===')", "print('=== 1/6 构建产物 ===')", 1)
Path('tools/_deploy_173.py').write_text(src, encoding='utf-8')
print('_deploy_173.py 生成：%d 字节' % len(src))
