import sys
import pathlib
"""1.1.83 出货：**挖掘数字**（瞄着矿脉，准星下方报「会连挖几格」；与描边同一份数字，
到 max_blocks 上限时补一句「已到上限」；顺手把「潜行只砸一格」收进共用判定，
修掉 1.1.82 里「蹲着还给你画一整簇」的谎）
（含 1.1.82 的玩家挖掘高亮 / 1.1.81 的玩家一键挖掘 / 1.1.80 的 36 格库存与手持方向，全部不回归）
（含 1.1.79 的图形配置界面 / 一键挖掘上限 64 / id 参数修复全部不回归）
（猫耳娘 v4 内容不回退 —— 128² 皮肤 / 逐面 UV 装机 geo / 脸层 44×32）。

跑法（**游戏须完全关闭**）：
    py tools/_deploy_183.py --build        # 先 ./gradlew build 再出货
    py tools/_deploy_183.py                # 用 build/libs 里已构建好的包

判据（任一条不过就退出，不动 mods/）：
  1. 构建产物存在，且 jar 内 mods.toml 的 version == 1.1.83；
  2. 猫耳娘该有的东西：
     · geo/cat_girl.geo.json —— identifier geometry.cat_girl、贴图基准 128×128、
       31 骨 / 126 方块，且**每个 cube 用逐面 uv/uv_size**；rest 姿态骨骼无旋转；
     · textures/entity/cat_girl.png 是 128×128；
     · animations/cat_girl.animation.json 在位，每条片段 animation_length > 0；
     · Java 侧 CatGirlEntity / CatGirlGeoModel / CatGirlGeoRenderer 在 jar 里；
  3. 1.1.83 本体（源码级 + 包内级）：
     · 数字 = 客户端 HUD（VeinMineHighlighter.renderCount，纯观感，可单独关）；
     · 份数取自与描边同一份缓存（不会框 12 个、数字说 11），含瞄准的那一格；
     · 只报 2 格以上；撞 max_blocks 时文案带「已到上限」；lang 中英各一份；
     · 配置 [player_mine] count 默认 true；该段 12 项、总数 169；
  4. **不回归**：1.1.82 的高亮描边 / 画的一定是真会砸的；
     1.1.81 的破坏即连带 / 深板岩认亲 / 潜行只挖一格；
     1.1.80 的 36 格库存 / 手持物品基准旋转 / mine_depth 与 prospect；
     柯尔特 1878 仍在包里且规格未变（12 骨 / 87 方块 / 512² 基准 / 8 条片段长度逐条等于 Java 常量）；
  5. 工程门禁在**本机跑一遍**：tools/check_gun_resources.py 全绿才继续；
  6. 基线：mods/ 里当前那个包必须是本版或上一版（按**包内 mods.toml 版本**认）；
  7. 换包：旧包挪到 mods/ **同级** 的 mods_backup/（保 3 份），mods/ 里只留一个本模组包；
     其它模组 md5 必须全等，mods/ 下不许有子目录（Forge 会递归扫描 → 重复加载）。

(下面为原文，未改)
"""




import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import zipfile

VER = '1.1.83'
PREV = '1.1.82'
SRC = 'F:/mcmod/build/libs/apocalypse_zombies-%s.jar' % VER
DEV = 'F:/.minecraft/versions/1.20.1-Forge_47.4.26'
MODS, BACKUP = DEV + '/mods', DEV + '/mods_backup'
PREFIX = 'apocalypse_zombies-'
KEEP_BACKUPS = 3
A = 'assets/apocalypse_zombies/'
ACCEPT = (PREV, VER)

CLIENT_MARKERS = ('net.minecraft.client.main.Main',)
DEV_SERVER_MARKERS = ('forgeclient', 'forgeserver', 'forgeuserdev', 'net.minecraft.server.Main')

#: 猫耳娘 v4 规格
CG_BONES, CG_CUBES, CG_TEX = 31, 126, (128, 128)
#: 柯尔特 1878 规格（回归护栏）
COLT_CLIPS = {'static_idle': 2.0, 'draw': 0.8, 'shoot': 0.6, 'bolt': 1.4,
              'reload_tactical': 3.0, 'reload_empty': 3.6, 'ADS_up': 0.22, 'ADS_down': 0.18}
COLT_BONES, COLT_CUBES, COLT_TEX = 12, 87, (512, 512)
CG_JAVA = ('com/apocalypse/zombies/entity/CatGirlEntity.class',
           'com/apocalypse/zombies/client/model/CatGirlGeoModel.class',
           'com/apocalypse/zombies/client/renderer/CatGirlGeoRenderer.class')

ok = True
_ap = argparse.ArgumentParser(description='1.1.83 出货：挖掘数字（准星下方报会连挖几格）')
_ap.add_argument('--build', action='store_true', help='先跑 ./gradlew build 再出货')
_ap.add_argument('--allow-dev-server', action='store_true', help='放行无头开发服在跑')
args = _ap.parse_args()


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def check(cond, label, detail=None):
    global ok
    ok = ok and bool(cond)
    tail = ('  —— %s' % (detail,)) if detail not in (None, '', []) else ''
    print('  %s %s%s' % ('[OK  ]' if cond else '[FAIL]', label, tail))
    return bool(cond)


def jar_version(path):
    with zipfile.ZipFile(path) as z:
        toml = z.read('META-INF/mods.toml').decode('utf-8', 'replace')
    m = re.search(r'^version\s*=\s*"([^"]+)"', toml, re.M)
    return m.group(1) if m else '?'


def game_state():
    ps = ('Get-CimInstance Win32_Process -Filter "Name=\'java.exe\'" | '
          'ForEach-Object { $_.CommandLine }')
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', ps],
                           capture_output=True, text=True, errors='replace', timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None, None
    if r.returncode != 0:
        return None, None
    t = (r.stdout or '').lower()
    return (any(m.lower() in t for m in CLIENT_MARKERS),
            any(m.lower() in t for m in DEV_SERVER_MARKERS))


def png_size(blob):
    if blob[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    return struct.unpack('>II', blob[16:24])


print('=== 1/9 构建产物 ===')
if args.build or not os.path.exists(SRC):
    if args.build:
        print('  跑 ./gradlew build ...')
        rc = subprocess.call('gradlew.bat build --console=plain', shell=True, cwd='F:/mcmod')
        if rc != 0:
            print('  ★ 构建失败（exit %d）' % rc)
            raise SystemExit(1)
if not os.path.exists(SRC):
    print('  没有 %s —— 先跑 py tools/_deploy_183.py --build' % SRC)
    raise SystemExit(1)
src_md5, src_size = md5(SRC), os.path.getsize(SRC)
print('  %s\n  md5=%s  %d 字节' % (SRC, src_md5, src_size))

print('=== 2/9 包内自检：猫耳娘 v4 ===')
with zipfile.ZipFile(SRC) as z:
    names = z.namelist()
    toml = z.read('META-INF/mods.toml').decode('utf-8', 'replace')
    geo = json.loads(z.read(A + 'geo/cat_girl.geo.json'))['minecraft:geometry'][0]
    anim = json.loads(z.read(A + 'animations/cat_girl.animation.json'))['animations']
    png = z.read(A + 'textures/entity/cat_girl.png') if A + 'textures/entity/cat_girl.png' in names else b''
    colt = json.loads(z.read(A + 'geo/colt_1878.geo.json'))['minecraft:geometry'][0]
    colta = json.loads(z.read(A + 'animations/colt_1878.animation.json'))['animations']
    colt_png = z.read(A + 'textures/item/colt_1878.png') if A + 'textures/item/colt_1878.png' in names else b''
    jij = [n for n in names if 'jarjar' in n.lower()]

check('version="%s"' % VER in toml, 'mods.toml 版本 == %s' % VER,
      [l.strip() for l in toml.splitlines() if 'version=' in l][0])
desc = geo.get('description', {})
check(desc.get('identifier') == 'geometry.cat_girl', 'geo identifier == geometry.cat_girl',
      desc.get('identifier'))
check((desc.get('texture_width'), desc.get('texture_height')) == CG_TEX,
      'geo 贴图基准 %d×%d' % CG_TEX, '%s×%s' % (desc.get('texture_width'), desc.get('texture_height')))
bones = geo.get('bones', [])
cubes = sum(len(b.get('cubes', [])) for b in bones)
check(len(bones) == CG_BONES and cubes == CG_CUBES,
      'geo %d 骨 / %d 方块' % (CG_BONES, CG_CUBES), '%d 骨 / %d 方块' % (len(bones), cubes))
dirty = [b['name'] for b in bones if b.get('rotation')]
check(not dirty, 'rest 姿态骨骼无旋转（铁律）', dirty or '%d 根全零' % len(bones))
facewise = 0
for b in bones:
    for c in b.get('cubes', []):
        uv = c.get('uv')
        if isinstance(uv, dict) and all(isinstance(v, dict) and 'uv' in v for v in uv.values()):
            facewise += 1
check(facewise == CG_CUBES, '每块逐面 uv/uv_size（v4 必须，%d/%d）' % (facewise, CG_CUBES))
sz = png_size(png) if png else None
check(sz == CG_TEX, 'textures/entity/cat_girl.png 是 %d×%d' % CG_TEX, sz)
bad_clip = {k: (v.get('animation_length') if isinstance(v, dict) else None)
            for k, v in anim.items() if not (isinstance(v, dict) and (v.get('animation_length') or 0) > 0)}
check(anim and not bad_clip, 'cat_girl 动画 %d 条，长度均 > 0' % len(anim), sorted(anim.keys()))
miss_java = [p for p in CG_JAVA if p not in names]
check(not miss_java, '猫耳娘 Java 类在 jar 内（实体/模型/渲染器）', miss_java or '3/3')
check(not jij, '本模组 jar 不含 jar-in-jar', '干净')

# ---- 月亮事件：日历表必须与 Crafting Dead 的 MoonEventType.forDay 逐条一致 ----
# 这张表就是从 CD 抄过来的；改动必须两边一起动，所以在这里钉死防漂移。
cdmoon = {6: 'BLUE_MOON', 7: 'SUPER_BLUE_MOON', 13: 'BLOOD_MOON',
          20: 'YELLOW_MOON', 21: 'SUPER_YELLOW_MOON', 27: 'SUPER_BLOOD_MOON'}
check('com/apocalypse/zombies/moon/MoonEvent.class' in names
      and 'com/apocalypse/zombies/event/CommonEvents.class' in names,
      '月亮事件类进包（MoonEvent / CommonEvents）')
msrc = open('F:/mcmod/src/main/java/com/apocalypse/zombies/moon/MoonEvent.java',
            encoding='utf-8').read()
mi = msrc.find('forDay(')
got = {int(m.group(1)): m.group(2) for m in re.finditer(
    r'm\s*==\s*(\d+)\s*\)\s*\{?\s*return\s+([A-Z_]+)', msrc[mi:mi + 1600])}
check(got == cdmoon, '月亮日历与 Crafting Dead 逐条一致（%d 天有事件）' % len(cdmoon), got)

# ---- 猫耳娘交互：两套 lang 必须都有「未认主 / 非主人」提示键（这次修复的对外表现）----
for lf in ('en_us.json', 'zh_cn.json'):
    lp = 'F:/mcmod/src/main/resources/assets/apocalypse_zombies/lang/' + lf
    ls = open(lp, encoding='utf-8').read()
    check('"cat_girl.not_tame"' in ls and '"cat_girl.not_owner"' in ls,
          'lang %s 有未认主/非主人提示键' % lf)
menusrc = open('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/menu/CatGirlTradeMenu.java',
               encoding='utf-8').read()
check('PLAYER_ROW_Y' in menusrc and 'HOTBAR_Y' in menusrc and 'goodsSlotY' in menusrc,
      '库存槽位坐标与玩家行常量都在（1.1.80 起：她 36 格在面板内、玩家 27 格在面板外）')

# ---- 工具即指令：映射函数 / 弓目标 / 外显提示键都在 ----
cgsrc = open('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/CatGirlEntity.java',
             encoding='utf-8').read()
check('public static Job jobForTool(' in cgsrc, '工具→工种 映射函数在')
check('CatGirlBowGoal' in cgsrc, '弓的远程目标已注册')
check('countArrows' in cgsrc, '箭袋计数在（供「她没箭了」提示）')
check(pathlib.Path('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/ai/CatGirlBowGoal.java').exists(),
      'CatGirlBowGoal.java 在')
for lf in ('en_us.json', 'zh_cn.json'):
    ls = open('F:/mcmod/src/main/resources/assets/apocalypse_zombies/lang/' + lf, encoding='utf-8').read()
    check('"cat_girl.job.from_tool"' in ls and '"cat_girl.bow.need_arrows"' in ls,
          'lang %s 有工具→工种 / 箭袋提示键' % lf)

# ---- 配方表：表在、与当前游戏一致（真同步）、读取器与命令都进了包 ----
import subprocess
tbl = pathlib.Path('F:/mcmod/src/main/resources/data/apocalypse_zombies/cat_girl/recipes.json')
check(tbl.is_file() and tbl.stat().st_size > 10000, '装机配方表在（%s KB）' % (tbl.stat().st_size // 1024 if tbl.is_file() else 0))
sync = subprocess.run([sys.executable, 'F:/mcmod/tools/cat_girl_recipes_sync.py', '--check'],
                      capture_output=True, text=True, cwd='F:/mcmod')
check(sync.returncode == 0, '配方表与当前游戏一致（--check 通过）—— %s' % (sync.stdout.strip() or sync.stderr.strip())[:120])
cgsrc2 = open('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/CatGirlRecipeTable.java', encoding='utf-8').read()
check('cat_girl/recipes.json' in cgsrc2, '读取器指向装机配方表')
cmdsrc = open('F:/mcmod/src/main/java/com/apocalypse/zombies/command/ApocalypseCommand.java', encoding='utf-8').read()
check('"catgirl"' in cmdsrc and 'recipeReport' in cmdsrc, '/apocalypse catgirl recipes 命令在')

# ---- 1.1.72：无敌不死 / 弓弩蓄力 / 界面布局 / 尾巴摆动 ----
entsrc = open('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/CatGirlEntity.java', encoding='utf-8').read()
cfgsrc = open('F:/mcmod/src/main/java/com/apocalypse/zombies/Config.java', encoding='utf-8').read()
check('CAT_GIRL_INVULNERABLE' in cfgsrc and '"invulnerable"' in cfgsrc, 'Config 有全无敌开关（默认开）')
check('CAT_GIRL_INVULNERABLE' in entsrc and 'guardImmortal' in entsrc and 'public void kill()' in entsrc,
      '本体全无敌 + /kill 与虚空兜底')
bow = open('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/ai/CatGirlBowGoal.java', encoding='utf-8').read()
check('BOW_DRAW = 20' in bow and 'CROSSBOW_LOAD = 25' in bow, '弓 20 tick 满弦 / 弩 25 tick 装填')
menusrc = open('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/menu/CatGirlTradeMenu.java', encoding='utf-8').read()
check('PANEL_HEIGHT = 226' in menusrc
      and 'GOODS_HOTBAR_Y = GOODS_Y + GOODS_BACKPACK / 9 * SLOT_PITCH + 4' in menusrc,
      '她的 4 行排布在（背包 3 行 + 物品栏 1 行，面板仍 226）')
scr = open('F:/mcmod/src/main/java/com/apocalypse/zombies/client/gui/CatGirlTradeScreen.java', encoding='utf-8').read()
check('cat_girl.trade.stock' in scr and 'CatGirlTradeMenu.goodsSlotY(i)' in scr,
      '界面按同一个槽位算法标价格（菜单 / 界面同源）')
import json as _json
_anim = _json.load(open('F:/mcmod/src/main/resources/assets/apocalypse_zombies/animations/cat_girl.animation.json', encoding='utf-8'))['animations']
_tails = [_anim['idle']['bones'].get('tail%d' % i) for i in (1, 2, 3, 4)] + [_anim['walk']['bones'].get('tail%d' % i) for i in (1, 2, 3, 4)]
check(all(t and len(t['rotation']) == 5 for t in _tails), '尾巴 4 节 x 5 关键帧相位波（idle + walk）')

# ---- 1.1.72：拾取 / 自制 / 自动换装（含盔甲）/ 无耐久 / 砸矿必掉 ----
cfgsrc = open('F:/mcmod/src/main/java/com/apocalypse/zombies/Config.java', encoding='utf-8').read()
for _k in ('"pickup"', '"auto_equip"', '"auto_craft"', '"no_durability"', '"always_drops"'):
    check(_k in cfgsrc, 'Config 有开关 %s' % _k)
entsrc = open('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/CatGirlEntity.java', encoding='utf-8').read()
check('pickupNearby' in entsrc and 'wantsToPickUp' in entsrc and 'pickUpItem' in entsrc,
      '她会捡地上的东西进自己库存')
check('ensureMainHand' in entsrc and 'ensureArmor' in entsrc and 'takeBest' in entsrc,
      '伐木换斧 / 挖矿换镐 / 战斗换剑 + 穿盔甲')
check('keepGearPristine' in entsrc, '装备不吃耐久（主手/盔甲/库存一律修满）')
check('CatGirlCrafting.tick' in entsrc, '自制/熔炼节拍已接进 aiStep')
craft = open('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/CatGirlCrafting.java', encoding='utf-8').read()
check('isHerCraftable' in craft and 'RecipeType.CRAFTING' in craft and 'getIngredients' in craft,
      '自制走原版配方表（工具/武器/盔甲/箭白名单）')
work = open('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/ai/WorkBlockGoal.java', encoding='utf-8').read()
_hv0 = open('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/CatGirlHarvest.java', encoding='utf-8').read()
check('CAT_GIRL_ALWAYS_DROPS' in _hv0 and 'NETHERITE_PICKAXE' in _hv0 and 'dropTool(' in _hv0,
      '砸什么都有掉（无视原版工具等级）—— 1.1.78 起规则在 CatGirlHarvest')
mitsrc = open('F:/mcmod/src/main/java/com/apocalypse/zombies/registry/ModItems.java', encoding='utf-8').read()
check('love_coin' in mitsrc, '货币（爱心币）仍在')

print('=== 5/9 1.1.73：订做 / 盔甲层 / 熔炼 / 月亮三项 ===')
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
check('Commands.literal("craft")' in cmdsrc and 'ResourceLocationArgument.id()' in cmdsrc,
      '/apocalypse catgirl craft <物品id> [数量] 在（1.1.79 起 id 走 ResourceLocationArgument）')
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
check(any(n.endswith('CatGirlArmorLayer.class') for n in names), '盔甲层类进包')
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

print('=== 6/9 1.1.74：像玩家一样操作（第一批）===')
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
check('harvestBlockHard' in _ent2 and 'CatGirlHarvest.breakAndCollect' in _ent2,
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

print('=== 3/9 1.1.75：像玩家一样操作（第二批 · 脑子）===')
_p = 'F:/mcmod/src/main/java/com/apocalypse/zombies/'
for _c in ('entity/ai/CatGirlNeedGoal.class', 'entity/ai/CatGirlEscortGoal.class',
           'entity/ai/CatGirlContainerGoal.class'):
    check(any(n.endswith(_c) for n in names), '进包：%s' % _c.split('/')[-1])
_ent3 = open(_p + 'entity/CatGirlEntity.java', encoding='utf-8').read()
for _g in ('new CatGirlNeedGoal(this)', 'new CatGirlEscortGoal(this)', 'new CatGirlContainerGoal(this)'):
    check(_g in _ent3, '已注册目标：%s' % _g[4:-6])
check('applyPlayerJob' in _ent3 and 'this.autoJob = false' in _ent3,
      '玩家切工种 → 关掉这个个体的自动模式（手动优先）')
check('isAutoJob' in _ent3 and 'getStorage' in _ent3 and 'setStorage' in _ent3,
      '自主开关 / 储物点访问器在实体上')
check('CatGirlAutoJob' in _ent3 and 'CatGirlChest' in _ent3, '这两个状态进 NBT（读档不丢）')
check('!tag.contains("CatGirlAutoJob")' in _ent3, '老存档默认落在安全那一侧（自动开、没绑箱子）')
check(_ent3.count('applyPlayerJob') >= 3, '两处玩家交互（给工具 / 空手右键）都改走 applyPlayerJob')
_need = open(_p + 'entity/ai/CatGirlNeedGoal.java', encoding='utf-8').read()
check('EnumSet' not in _need and 'setFlags' not in _need, '需求 Goal 不占 MOVE/LOOK 执行权')
check('Job.FIGHT' in _need and 'Job.LUMBER' in _need and 'Job.MINE' in _need and 'Job.FOLLOW' in _need,
      '四种需求都在（打 / 伐木 / 挖矿 / 跟随）')
check('AllyJudge.isHorde' in _need, '认敌复用她那一套判据（不会把友军当敌人）')
check('Config.CAT_GIRL_AUTO_JOB' in _need and 'isAutoJob()' in _need, '需求 Goal 受开关 + 手动模式双重约束')
_ct = open(_p + 'entity/ai/CatGirlContainerGoal.java', encoding='utf-8').read()
check('Config.CAT_GIRL_CHEST' in _ct and 'getStorage()' in _ct, '容器 Goal 受开关约束且只认储物点')
check('pos == null' in _ct and 'instanceof Container container' in _ct,
      '没绑储物点 / 那儿不是容器 → 什么都不做')
check('countIn(chest, stack.getItem()) == 0' in _ct, '成品每种至少留一件（不会把唯一那把镐子存走）')
check('Tags.Items.ORES' in _ct and 'WANT_ORES' in _ct, '缺矿时从储物点取一组矿石')
_esc = open(_p + 'entity/ai/CatGirlEscortGoal.java', encoding='utf-8').read()
check('getLastHurtByMob' in _esc and 'Config.CAT_GIRL_ESCORT' in _esc, '护卫只认「主人被打」这个信号')
_cmd = open(_p + 'command/ApocalypseCommand.java', encoding='utf-8').read()
check('catgirlAuto' in _cmd and 'catgirlChest' in _cmd, '两个新子命令在命令表里')
check('Commands.literal("auto")' in _cmd and 'Commands.literal("chest")' in _cmd, '命令字面量 auto / chest 已注册')
_cfg3 = open(_p + 'Config.java', encoding='utf-8').read()
for _k in ('"auto_job"', '"chest"', '"escort"'):
    check(_k in _cfg3, 'Config 有 1.1.75 开关 %s' % _k)

print('=== 4/9 不回归：柯尔特 1878（1.1.71 内容不许被冲掉） ===')
cdesc = colt.get('description', {})
cbones = colt.get('bones', [])
ccubes = sum(len(b.get('cubes', [])) for b in cbones)
check(cdesc.get('identifier') == 'geometry.colt_1878', 'colt geo identifier',
      cdesc.get('identifier'))
check((cdesc.get('texture_width'), cdesc.get('texture_height')) == COLT_TEX,
      'colt 贴图基准 %d×%d' % COLT_TEX,
      '%s×%s' % (cdesc.get('texture_width'), cdesc.get('texture_height')))
check(len(cbones) == COLT_BONES and ccubes == COLT_CUBES,
      'colt %d 骨 / %d 方块' % (COLT_BONES, COLT_CUBES), '%d 骨 / %d 方块' % (len(cbones), ccubes))
csz = png_size(colt_png) if colt_png else None
check(csz == COLT_TEX, 'colt 贴图是 %d×%d' % COLT_TEX, csz)
got = {k: (v.get('animation_length') if isinstance(v, dict) else None) for k, v in colta.items()}
bad_len = {k: (got.get(k), w) for k, w in COLT_CLIPS.items() if abs((got.get(k) or -1) - w) > 1e-6}
check(sorted(colta.keys()) == sorted(COLT_CLIPS.keys()) and not bad_len,
      'colt 8 条片段长度逐条等于 Java 常量', bad_len or '8/8')

print('=== 8/9 1.1.76 不回归：崩溃修复 + 本地 AI 助理 ===')
_p = 'F:/mcmod/src/main/java/com/apocalypse/zombies/'
# —— 崩溃修复：那张 3x3 必须配菜单
_craft = open(_p + 'entity/CatGirlCrafting.java', encoding='utf-8').read()
check('new TransientCraftingContainer(new GridMenu(), 3, 3)' in _craft,
      '她的 3x3 配了空壳菜单（不再传 null）')
check('new TransientCraftingContainer(null' not in _craft,
      '源码里已无「传 null 菜单」的老写法（那就是崩溃根因）')
check('extends AbstractContainerMenu' in _craft and 'GridMenu' in _craft,
      '空壳菜单在（slotsChanged 走默认空实现，不碰真实窗口）')
check('catch (RuntimeException e)' in _craft and 'LOGGER.error' in _craft,
      '自动制作/熔炼那一拍有兜底（异常只记日志）')
_menu = open(_p + 'entity/menu/CatGirlTradeMenu.java', encoding='utf-8').read()
check('LOGGER.error' in _menu, '下单路径（跑在服务端 tick 里）也有兜底')
check('TransientCraftingContainer(this, 3, 3)' in _menu,
      '菜单自己的 3x3 仍然挂在真菜单上（没被顺手改坏）')
# —— AI 助理：类进包
for _c in ('ai/OllamaWire.class', 'ai/LocalAiClient.class', 'ai/CatGirlAiPrompt.class',
           'ai/CatGirlAiActions.class'):
    check(any(n.endswith(_c) for n in names), '进包：%s' % _c.split('/')[-1])
# —— AI 助理：纪律
_wire = open(_p + 'ai/OllamaWire.java', encoding='utf-8').read()
check('import net.minecraft' not in _wire,
      'OllamaWire 不碰 Minecraft 类（所以能拿裸 JVM 对着真模型测同一份字节码）')
check('ACTIONS = List.of("none", "say", "set_job", "craft")' in _wire,
      '动作白名单在代码里写死（模型说什么都不越界）')
check('degraded' in _wire and 'stripThink' in _wire,
      '坏回包统一降级 + 思考标签剥除')
_client = open(_p + 'ai/LocalAiClient.java', encoding='utf-8').read()
check('server.execute(' in _client, 'HTTP 在工作线程、结果回投主线程')
check('COOLDOWN_MS' in _client and 'FAIL_LIMIT' in _client, '连续失败熔断')
check('CAT_GIRL_AI_ENDPOINT' in _client and 'CAT_GIRL_AI_MODEL' in _client,
      '端点/模型走配置')
check('sendAsync' in _client, '请求是异步发的（不阻塞调用它的那一步）')
_acts = open(_p + 'ai/CatGirlAiActions.java', encoding='utf-8').read()
check('CatGirlRecipeTable.find' in _acts
      and ('isHerMakeable' in _acts or 'isHerCraftable' in _acts),
      '合成要过「配方表 + 她的白名单」两道')
check('teleport' not in _acts and 'addItem' not in _acts and 'setHealth' not in _acts,
      '第一版没有「凭空给物品 / 传送 / 加血」这类动作')
_cfg4 = open(_p + 'Config.java', encoding='utf-8').read()
check('"model", "fableforge-ai/nexus-coder:q4_k_m"' in _cfg4, '默认模型 = qwen2 1.5B')
check('"endpoint", "http://127.0.0.1:11434"' in _cfg4, '默认只连本机')
check('"actions", true' in _cfg4 and '"enabled", true' in _cfg4, 'AI 两个开关在配置里')
_cmd4 = open(_p + 'command/ApocalypseCommand.java', encoding='utf-8').read()
check('Commands.literal("ai")' in _cmd4 and 'catgirlAi(' in _cmd4,
      '/apocalypse catgirl ai <一句话> 在命令表里')
check('catgirlAiStatus' in _cmd4, '有 ai status 自检出口')
# —— 真端点实跑：用线上那份源码编出字节码，对着真 Ollama 跑
print('  —— 真模型实跑（Ollama + 线上那份 OllamaWire）')
_gson = 'F:/.minecraft/libraries/com/google/code/gson/gson/2.10.1/gson-2.10.1.jar'
if not os.path.exists(_gson):
    check(False, 'gson jar 在（门禁用例要它编译）', _gson)
else:
    os.makedirs('F:/mcmod/build/aiw', exist_ok=True)
    _rc = subprocess.call('javac -encoding UTF-8 -J-Duser.language=en -d build/aiw -cp "%s" '
                          'src/main/java/com/apocalypse/zombies/ai/OllamaWire.java '
                          'tools/ai_wire_test/OllamaWireTest.java' % _gson,
                          shell=True, cwd='F:/mcmod')
    check(_rc == 0, '门禁用例编译通过（编的就是线上那份 OllamaWire）')
    if _rc == 0:
        _run = subprocess.run('java -cp "build/aiw;%s" OllamaWireTest' % _gson,
                              shell=True, cwd='F:/mcmod', capture_output=True, text=True,
                              errors='replace', timeout=900)
        _lines = [l.strip() for l in (_run.stdout or '').splitlines() if l.strip()]
        check(_run.returncode == 0, '真 Ollama 端点上 12 项全过',
              _lines[-1] if _lines else (_run.stderr or '')[:120])
        for _l in _lines:
            if '她的回话' in _l or _l.startswith('动作：'):
                print('       ' + _l)

print('=== 9/9 1.1.77：她真的会自己做材料/物品 ===')
_p = 'F:/mcmod/src/main/java/com/apocalypse/zombies/'
_craft = open(_p + 'entity/CatGirlCrafting.java', encoding='utf-8').read()
# —— 根因 1：「有没有」必须升级成「够不够」
check('private static int countMatching(' in _craft,
      '有「库存里这种料有几个」的计数（不再是只看有没有）')
check('private static Map<String, Need> needsOf(' in _craft,
      '有「一条配方每种料各要几个」的需求表（同一种料占几格就是几个）')
check(_craft.count('for (Need need : needsOf(recipe).values())') >= 3,
      '三处补料链都改成按需求记账（makeInto / fillMissing / smeltNeeded）',
      '%d 处' % _craft.count('for (Need need : needsOf(recipe).values())'))
check('while (countMatching(goods, need.want) < need.required)' in _craft,
      '缺几个补几个（while 到够为止，不是补一次就算）')
check('if (countMatching(goods, need.want) <= before)' in _craft,
      '补了但没变多就撤退（防在这圈空转）')
# —— 根因 2：不许把自己的成品装备丢进炉子
check('!isHerCraftable(stack)' in _craft,
      '成品装备不进炉（原始「铁装烧成铁粒」不再烧掉她的剑/甲）')
# —— fill 不再「有就不补」（那正是量不足的成因）
check('注意：这里**不能**「已经有就不补」' in _craft,
      'fill 里的「已经有就跳过」已删（调用方要的是凑够）')
# —— 不靠猜：配方表仍是唯一来源
check('getRecipeManager().getAllRecipesFor(RecipeType.CRAFTING)' in _craft,
      '配方来自服务端的真实配方表（RecipeManager，不是写死的菜单）')
check(not any(s in _craft for s in ('minecraft:diamond', 'minecraft:netherite', 'minecraft:emerald')),
      '没有「凭空变物」的硬编码物品菜单（钻石/下界合金/绿宝石都不在源码里）')
# —— 可复跑的实机探针在
_probe = pathlib.Path('F:/mcmod/tools/rcon_catgirl_craft_probe.py')
check(_probe.is_file(), '实机探针 tools/rcon_catgirl_craft_probe.py 在')
_ps = _probe.read_text(encoding='utf-8') if _probe.is_file() else ''
check('A5 镐斧剑齐活' in _ps, '探针含「镐/斧/剑齐活」断言（做一件就收手会被抓）')
check('minecraft:item,distance=..64' in _ps or 'type=minecraft:item,distance=..64' in _ps,
      '探针开跑前清场地掉落物（否则上局尸体掉落会假绿）')
check('\u4e0d\u70e7' in _ps or '不烧自己装备' in _ps or 'WASTE' in _ps,
      '探针含「不烧自己的东西」断言')
# —— AI 路径同样走白名单
_acts = open(_p + 'ai/CatGirlAiActions.java', encoding='utf-8').read()
check('CatGirlRecipeTable.find' in _acts and 'CatGirlCrafting.isHerMakeable' in _acts
      and 'CatGirlCrafting.craftOrder' in _acts,
      'AI 下单路径也走「配方表 + 她的白名单」（校验完才 craftOrder 扣她库存）')

print('=== 10/9 1.1.78：全功能镐子 / 一键挖掘 / 工作方块 ===')
_p = 'F:/mcmod/src/main/java/com/apocalypse/zombies/'
_cfg5 = open(_p + 'Config.java', encoding='utf-8').read()
for _k in ('"universal_tool"', '"mine_all"', '"mine_protected"', '"mine_radius"',
           '"mine_max_blocks"', '"station_use"', '"station_radius"', '"station_self_craft"'):
    check(_k in _cfg5, 'Config 有 1.1.78 项 %s' % _k)
check('defineInRange("mine_radius", 24, 4, 64)' in _cfg5, '范围默认 24（4~64）')
check('defineInRange("mine_max_blocks", 64, 1, 64)' in _cfg5, '一键挖掘数量上限默认 64（1~64）')
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
check('boolean isMineOrderTarget(' in _ent5, '订单目标判定在（含保护名单）')
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
check('| **当前版本** | `1.1.83` |' in _rd, 'readme 头表版本 == 1.1.83')
check('/apocalypse catgirl mine <方块id> [数量]' in _rd, 'readme 有 mine 指令')
check('/apocalypse catgirl mine stop' in _rd, 'readme 有 mine stop')
check('mine_max_blocks' in _rd and 'mine_radius' in _rd, 'readme 写明范围 / 上限两项配置')

print('=== 11/9 1.1.79：图形配置界面 + 一键挖掘上限 64 ===')
_p = 'F:/mcmod/src/main/java/com/apocalypse/zombies/'
_cfg6 = open(_p + 'Config.java', encoding='utf-8').read()
check('defineInRange("mine_max_blocks", 64, 1, 64)' in _cfg6,
      '一键挖掘上限默认 64、范围 1~64（用户口径：上限 64 个）')
check('public static java.util.List<ForgeConfigSpec.ConfigValue<?>> values()' in _cfg6
      and 'getDeclaredFields()' in _cfg6,
      'Config.values() 按声明顺序反射列配置项（界面照着它排，不赌 nightconfig 叶子类型）')

_scr = pathlib.Path('F:/mcmod/src/main/java/com/apocalypse/zombies/client/gui/ApocalypseConfigScreen.java')
_reg = pathlib.Path('F:/mcmod/src/main/java/com/apocalypse/zombies/client/ModConfigScreens.java')
check(_scr.is_file() and _reg.is_file(), '配置界面两个新类在源码里')
check(any(n.endswith('client/gui/ApocalypseConfigScreen.class') for n in names),
      '进包：ApocalypseConfigScreen.class')
check(any(n.endswith('client/ModConfigScreens.class') for n in names), '进包：ModConfigScreens.class')
_scs = _scr.read_text(encoding='utf-8') if _scr.is_file() else ''
check('extends Screen' in _scs and 'Config.values()' in _scs,
      '界面本体：Screen + 直接读 Config.values()（列的就是那 151 项）')
check('Config.SPEC.save()' in _scs, '点「完成」写回同一份 TOML（不是第二套配置）')
check('case BOOL' in _scs and 'case NUM' in _scs and 'case LIST' in _scs and 'case TEXT' in _scs,
      '布尔 / 数字 / 列表 / 文本 各有对口控件')
check('mouseScrolled' in _scs, '滚轮翻页（151 项一屏放不下）')
check('stash()' in _scs, '翻页前先把输入框抄回行草稿（否则滚一下就丢字）')
check('cat_girl.config.bad_number' in _scs, '填错就提示，整屏不半途写坏')
check('getDefault()' in _scs and 'resetDefaults' in _scs, '有「恢复默认」')
_regs = _reg.read_text(encoding='utf-8') if _reg.is_file() else ''
check('registerExtensionPoint(' in _regs and 'ConfigScreenHandler.ConfigScreenFactory' in _regs,
      '挂在「模组列表 → 配置」按钮上（ConfigScreenFactory 扩展点）')
_main = open(_p + 'ApocalypseZombies.java', encoding='utf-8').read()
check('DistExecutor.unsafeRunWhenOn(Dist.CLIENT' in _main, '注册走 DistExecutor —— 专用服务器上不加载客户端类')
check('ModConfigScreens::register' in _main, '服务器分支永不触碰那个类（连加载都不会）')
# 这一条是 1.1.79 实机撞出来的：构造阶段读配置值 → IllegalStateException: Cannot get config value
# before config is loaded → 专用服务器直接起不来。
check('onConfigLoaded(ModConfigEvent.Loading event)' in _main
      and 'modBus.addListener(this::onConfigLoaded)' in _main,
      '运行期真值在「配置已 load」的回调里读（构造里读会抛 Cannot get config value before config is loaded）')
check('LOGGER.info("Cat girl mining: mine_max_blocks=' in _main,
      '启动日志写出夹完的运行期真值（实机探针认这一行）')
check('Config registry: {} entries' in _main and 'Config.values().size()' in _main,
      '启动自检写出枚举器真机数出的项数')
_probe = pathlib.Path('F:/mcmod/tools/rcon_catgirl_config_probe.py')
check(_probe.is_file() and '--stage' in _probe.read_text(encoding='utf-8'),
      '1.1.79 实机探针在位（两段跑：default / clamped）')
_cmd = open(_p + 'command/ApocalypseCommand.java', encoding='utf-8').read()
check('getId(context, "block")' in _cmd and 'getId(context, "item")' in _cmd,
      'mine 的方块参数与 craft 的物品参数都换成 ResourceLocationArgument ——'
      ' StringArgumentType 的不带引号形式不收 `minecraft:` 前缀（实机报 trailing data），'
      ' 而提示里让你写的正是 `minecraft:diamond_pickaxe` 那种 id')
check('StringArgumentType.word()' not in _cmd,
      '整条命令树里没有残留的 word() 参数（就是那个老 bug 的根）')
for _lf in ('en_us.json', 'zh_cn.json'):
    _ls = open('F:/mcmod/src/main/resources/assets/apocalypse_zombies/lang/' + _lf, encoding='utf-8').read()
    for _k in ('cat_girl.config.title', 'cat_girl.config.done', 'cat_girl.config.cancel',
               'cat_girl.config.reset', 'cat_girl.config.on', 'cat_girl.config.off',
               'cat_girl.config.saved', 'cat_girl.config.bad_number'):
        check('"%s"' % _k in _ls, 'lang %s 有 %s' % (_lf, _k))

_rd6 = open('F:/mcmod/readme.md', encoding='utf-8').read()
check('### 1.1.79 —' in _rd6, 'readme 有 1.1.79 更新日志条目')
check('默认 64' in _rd6 and 'cat_girl.mine_max_blocks' in _rd6, 'readme 写明上限默认 64')
check('配置' in _rd6 and '图形界面' in _rd6, 'readme 写明「模组列表 → 配置」图形界面')
check('mine_radius' in _rd6, 'readme 仍写明范围配置项')

print('=== 12/9 1.1.80：库存 36 格 + 手里的东西方向 ===')
_p = 'F:/mcmod/src/main/java/com/apocalypse/zombies/'
_ent8 = open(_p + 'entity/CatGirlEntity.java', encoding='utf-8').read()
check('public static final int GOODS_HOTBAR = 9;' in _ent8
      and 'public static final int GOODS_BACKPACK = 27;' in _ent8
      and 'public static final int GOODS_SIZE = GOODS_HOTBAR + GOODS_BACKPACK;' in _ent8,
      '她 36 格 = 物品栏 9 + 背包 27（与玩家同款排布）')
check('new SimpleContainer(GOODS_SIZE)' in _ent8, '库存容器真按 36 格建（不是只改常量）')
_menu8 = open(_p + 'entity/menu/CatGirlTradeMenu.java', encoding='utf-8').read()
check('GOODS_COUNT = CatGirlEntity.GOODS_SIZE' in _menu8, '菜单槽位数跟着 36 走')
check('public static int goodsSlotX(int index)' in _menu8
      and 'public static int goodsSlotY(int index)' in _menu8,
      '槽位坐标只有一个算法（菜单与界面共用，不许两份）')
check('if (index < CatGirlEntity.GOODS_HOTBAR)' in _menu8,
      '物品栏 9 格排最后一行（背包 27 在上面三行）')
check('PLAYER_ROW_Y = 10000' in _menu8, '玩家 27 格移出面板（槽位仍注册，shift 搬货照旧）')
_scr8 = open(_p + 'client/gui/CatGirlTradeScreen.java', encoding='utf-8').read()
check('getGoods().getItem(i)' in _scr8 and 'goodsSlotY(i)' in _scr8,
      '界面把价格标在每格右下角（36 格都标）')
check('GOODS_HOTBAR_Y - 3' in _scr8, '背包 / 物品栏之间画了分组细线')
for _lf in ('en_us.json', 'zh_cn.json'):
    _ls = open('F:/mcmod/src/main/resources/assets/apocalypse_zombies/lang/' + _lf, encoding='utf-8').read()
    check('cat_girl.trade.stock' in _ls and '%1$s' in _ls and '%2$s' in _ls,
          'lang %s 的库存标题带两个参数（27 / 9）' % _lf)

_ren8 = open(_p + 'client/renderer/CatGirlGeoRenderer.java', encoding='utf-8').read()
check('poseStack.mulPose(Axis.XP.rotationDegrees(-90.0F))' in _ren8
      and 'poseStack.mulPose(Axis.YP.rotationDegrees(180.0F))' in _ren8,
      '补上原版 ItemInHandLayer 的手部基准旋转（XP -90 / YP 180）—— 缺它就是「方向不对」')
check('renderStackForBone' in _ren8 and 'THIRD_PERSON_RIGHT_HAND' in _ren8
      and 'THIRD_PERSON_LEFT_HAND' in _ren8,
      '物品在手骨骼矩阵里自己画（左右手两条 display 上下文都在）')
check('Config.CAT_GIRL_HELD_ITEM_MIRROR' in _ren8, '镜像开关接在渲染器上')
check('ITEM_BONE = "item_righthand"' in _ren8, '挂点骨骼仍是 geo 里的 item_righthand')

_cfg8 = open(_p + 'Config.java', encoding='utf-8').read()
for _k in ('"mine_depth"', '"mine_order_depth"', '"prospect"', '"prospect_tries"',
           '"prospect_step"', '"held_item_mirror"'):
    check(_k in _cfg8, 'Config 有 1.1.80 项 %s' % _k)
check('defineInRange("mine_depth", 1, 0, 8)' in _cfg8, '自主挖矿默认只下探 1 格（0~8）')
check('defineInRange("mine_order_depth", 6, 0, 16)' in _cfg8, '订单允许下探 6 格（0~16）')
check('define("prospect", true)' in _cfg8, '探矿默认开')
check('defineInRange("prospect_tries", 6, 1, 32)' in _cfg8, '空手 6 次就回主人身边')
check('defineInRange("prospect_step", 8, 2, 32)' in _cfg8, '探点步长 8 格')
check('define("held_item_mirror", false)' in _cfg8, '镜像默认关（= 原版右手拿法）')

_wb8 = open(_p + 'entity/ai/WorkBlockGoal.java', encoding='utf-8').read()
check('CAT_GIRL_MINE_ORDER_DEPTH.get() : Config.CAT_GIRL_MINE_DEPTH.get()' in _wb8,
      '自主 / 订单两条下探深度分开取（订单是主人点名的活）')
check('Config.CAT_GIRL_PROSPECT.get()' in _wb8 and 'CAT_GIRL_PROSPECT_TRIES' in _wb8
      and 'CAT_GIRL_PROSPECT_STEP' in _wb8, '探矿三件套都接在劳作目标里')

# —— 包内级：新配置项的字面量必须真进了 Config.class
with zipfile.ZipFile(SRC) as _z:   # 上面的 with 早退出了，这里单独再开一次
    _cfgcls = _z.read('com/apocalypse/zombies/Config.class') if 'com/apocalypse/zombies/Config.class' in names else b''
for _lit in (b'mine_depth', b'mine_order_depth', b'prospect_step', b'held_item_mirror'):
    check(_lit in _cfgcls, 'Config.class 内含配置名字面量 %s' % _lit.decode())

_rd8 = open('F:/mcmod/readme.md', encoding='utf-8').read()
check('### 1.1.80 —' in _rd8, 'readme 有 1.1.80 更新日志条目')
check('36 格' in _rd8 and '背包 27' in _rd8, 'readme 写明库存 36 格（背包 27 + 物品栏 9）')
check('held_item_mirror' in _rd8, 'readme 写明手持物品镜像开关')
check('mine_depth' in _rd8 and 'prospect' in _rd8, 'readme 写明不垂直下挖 + 探矿两项')

print('=== 13/9 1.1.81：玩家一键挖掘（破坏即连带同种矿石） ===')
_vm9 = open(_p + 'event/PlayerVeinMine.java', encoding='utf-8').read()
check('import net.minecraftforge.event.level.BlockEvent;' in _vm9
      and 'BlockEvent.BreakEvent event' in _vm9,
      '挂在原版破坏事件上（不是按键 / 不是命令）')
check('Bus.FORGE' in _vm9 and '@SubscribeEvent' in _vm9, 'FORGE 总线订阅，服务端判定')
check('Config.PLAYER_MINE_ENABLED.get()' in _vm9, '总开关读配置')
check('player.isShiftKeyDown()' in _vm9 and 'PLAYER_MINE_SNEAK_DISABLES' in _vm9,
      '潜行时只挖一格（经典 veinminer 手感）')
check('CatGirlHarvest.isMineable' in _vm9 and 'CatGirlHarvest.isOre' in _vm9,
      '安全判定与她那边共用一套（容器/方块实体/保护名单一律不碰）')
check('deepslateTwin' in _vm9 and 'deepslate_' in _vm9,
      '深板岩变种算同一簇（iron_ore ↔ deepslate_iron_ore）')
check('tool.isCorrectToolForDrops(originState)' in _vm9, '工具不对口就不连带（require_correct_tool）')
check('hurtAndBreak' in _vm9, '连带出来的每格扣耐久')
check('Block.getDrops(state, level, pos, be, player, tool)' in _vm9,
      '掉落走原版 getDrops（附魔/时运/精准采集都算数）')
check('level.destroyBlock(pos, false)' in _vm9, '销毁时不重复掉东西（我们自己发产物）')
check('getInventory().add' in _vm9 and 'player.drop(drop, false)' in _vm9,
      '产物进背包，塞不下掉在脚下')
check('clampMax' in _vm9 and 'Math.min(value, 64)' in _vm9, '上限硬夹到 64')

_har9 = open(_p + 'entity/CatGirlHarvest.java', encoding='utf-8').read()
check('public static boolean isOre(BlockState state)' in _har9,
      'CatGirlHarvest 暴露 isOre（forge:ores 标签）给玩家那条链复用')

_cfg9 = open(_p + 'Config.java', encoding='utf-8').read()
import re as _re9
_n9 = len(_re9.findall(r'public static final ForgeConfigSpec\.[A-Za-z<>?,\s\.]+?\s+[A-Z_0-9]+\s*;', _cfg9))
check(_n9 == 169, '配置项总数 169（1.1.80 的 157 + 玩家一键挖掘 10 + 高亮 1 + 数字 1）', '实得 %d' % _n9)
check('\"player_mine\"' in _cfg9, '新段落 player_mine')
check('define(\"enabled\", true)' in _cfg9, '玩家一键挖掘默认开启')
check('defineInRange(\"targets\", 0, 0, 2)' in _cfg9, '默认只连带矿石（targets 0，域 0~2）')
check('defineInRange(\"radius\", 16, 4, 64)' in _cfg9, '半径默认 16（4~64）')
check('defineInRange(\"max_blocks\", 64, 1, 64)' in _cfg9, '上限默认 64（1~64，与 1.1.79 同口径）')
check('define(\"vein_only\", true)' in _cfg9, '默认只连带连通矿脉')
check('define(\"require_correct_tool\", true)' in _cfg9, '默认要求工具对口')
check('define(\"consume_durability\", true)' in _cfg9, '默认扣耐久')
check('define(\"sneak_disables\", true)' in _cfg9, '默认潜行只挖一格')
check('define(\"to_inventory\", true)' in _cfg9, '默认产物进背包')
check('defineList(\"protected\", List.of()' in _cfg9, '追加保护名单（默认空）')
for _k9 in ('PLAYER_MINE_ENABLED', 'PLAYER_MINE_TARGETS', 'PLAYER_MINE_RADIUS',
            'PLAYER_MINE_MAX_BLOCKS', 'PLAYER_MINE_VEIN_ONLY', 'PLAYER_MINE_REQUIRE_TOOL',
            'PLAYER_MINE_DURABILITY', 'PLAYER_MINE_SNEAK_DISABLES', 'PLAYER_MINE_TO_INVENTORY',
            'PLAYER_MINE_PROTECTED'):
    check(_k9 in _cfg9, 'Config 有字段 %s' % _k9)

with zipfile.ZipFile(SRC) as _z9:
    _vmcls = _z9.read('com/apocalypse/zombies/event/PlayerVeinMine.class') \
        if 'com/apocalypse/zombies/event/PlayerVeinMine.class' in names else b''
    _cfgcls9 = _z9.read('com/apocalypse/zombies/Config.class') \
        if 'com/apocalypse/zombies/Config.class' in names else b''
check(_vmcls != b'', 'PlayerVeinMine.class 进包了')
for _lit9 in (b'player_mine', b'targets', b'vein_only', b'require_correct_tool',
              b'consume_durability', b'sneak_disables', b'to_inventory'):
    check(_lit9 in _cfgcls9, 'Config.class 内含配置名字面量 %s' % _lit9.decode())

_rd9 = open('F:/mcmod/readme.md', encoding='utf-8').read()
check('### 1.1.81 —' in _rd9, 'readme 有 1.1.81 更新日志条目')
check('player_mine' in _rd9 and '一键挖掘' in _rd9, 'readme 写明玩家一键挖掘')
check('targets' in _rd9 and 'sneak_disables' in _rd9 and 'deepslate' in _rd9,
      'readme 写明 targets / 潜行 / 深板岩认亲')
check('全部 169 项配置' in _rd9, 'readme 写明图形界面共 169 项')

print('=== 13/10 1.1.82：玩家挖掘高亮（描边跟着「真的会砸的」走） ===')
_hl = open(_p + 'client/renderer/VeinMineHighlighter.java', encoding='utf-8').read()
check('RenderLevelStageEvent' in _hl and 'AFTER_TRANSLUCENT_BLOCKS' in _hl,
      '高亮挂在渲染阶段事件上（客户端逐帧画）')
check('PlayerVeinMine.preview(' in _hl,
      '选块复用服务端同一份 preview —— 画出来的框 = 真的会砸的')
check('RenderType.lines()' in _hl and 'endVertex()' in _hl,
      '线框走 RenderType.lines（描边，不是贴图）')
check('Config.PLAYER_MINE_HIGHLIGHT' in _hl and 'Config.PLAYER_MINE_ENABLED' in _hl,
      '高亮本身可配置关掉（纯观感）')
check('renderBuffers().bufferSource()' in _hl and 'endBatch' in _hl,
      '1.20.1 借主渲染缓冲并即时 flush（该版事件不带 MultiBufferSource）')
check('cachedPos' in _hl and 'cachedKey' in _hl, '瞄准格/配置没变就不重算（不卡）')
check('target.equals(pos)' in _hl, '不画瞄准那一格（留给原版黑框，避免同像素打架）')

_ce = open(_p + 'client/ClientEvents.java', encoding='utf-8').read()
check('VeinMineHighlighter.render(event)' in _ce,
      'ClientEvents 每帧调用高亮（客户端类，服务端不加载）')

_vm10 = open(_p + 'event/PlayerVeinMine.java', encoding='utf-8').read()
check('public static List<BlockPos> preview(' in _vm10,
      'PlayerVeinMine.preview 是「会砸哪些」的唯一出口（服务端 + 客户端共用）')
check('LevelReader' in _vm10 and 'ServerLevel level' in _vm10,
      '同一份逻辑兼容 ServerLevel 与客户端 ClientLevel')

_cfg10 = open(_p + 'Config.java', encoding='utf-8').read()
import re as _re10
_n10 = len(_re10.findall(r'public static final ForgeConfigSpec\.[A-Za-z<>?,\s\.]+?\s+[A-Z_0-9]+\s*;', _cfg10))
check(_n10 == 169, '配置项总数 169（1.1.81 的 167 + 高亮 1 + 数字 1）', '实得 %d' % _n10)
check('define("highlight", true)' in _cfg10, 'highlight 默认 true（开启）')
check('PLAYER_MINE_HIGHLIGHT' in _cfg10, 'Config 有字段 PLAYER_MINE_HIGHLIGHT')

with zipfile.ZipFile(SRC) as _z10:
    _n10l = _z10.namelist()
    _hlname = 'com/apocalypse/zombies/client/renderer/VeinMineHighlighter.class'
    _hlcls = _z10.read(_hlname) if _hlname in _n10l else b''
    _cfgcls10 = _z10.read('com/apocalypse/zombies/Config.class')
    _vmcls10 = _z10.read('com/apocalypse/zombies/event/PlayerVeinMine.class')
check(_hlcls != b'', 'VeinMineHighlighter.class 进包了')
check(b'highlight' in _cfgcls10, 'Config.class 内含配置名字面量 highlight')
check(b'preview' in _vmcls10, 'PlayerVeinMine.class 里有 preview（服务端/客户端共用出口）')

_rd10 = open('F:/mcmod/readme.md', encoding='utf-8').read()
check('### 1.1.82 —' in _rd10, 'readme 有 1.1.82 更新日志条目')
check('高亮' in _rd10 and 'highlight' in _rd10, 'readme 写明高亮与配置项')
check('全部 169 项配置' in _rd10, 'readme 写明图形界面共 169 项')
print('=== 14/10 1.1.83：挖掘数字（准星下方报「会连挖几格」） ===')
_hl2 = open(_p + 'client/renderer/VeinMineHighlighter.java', encoding='utf-8').read()
check('public static void renderCount(GuiGraphics graphics, Minecraft minecraft)' in _hl2,
      'renderCount 是数字的出口（HUD 阶段画）')
check('hud.apocalypse_zombies.vein_count' in _hl2,
      '数字走 lang 词条（中英各一份）')
check('hud.apocalypse_zombies.vein_count_capped' in _hl2 and 'PLAYER_MINE_MAX_BLOCKS' in _hl2,
      '到 max_blocks 上限时补一句「已到上限」')
check('Component.translatable(' in _hl2, '用可翻译组件，不写死字符串')
check('minecraft.screen != null' in _hl2,
      '开着背包/箱子时不往准星上贴字')
check('graphics.guiWidth() / 2 - minecraft.font.width(text) / 2' in _hl2,
      '数字水平居中于准星')
check('COUNT_OFFSET_Y' in _hl2, '数字画在准星下方（不压准星）')
check('Config.PLAYER_MINE_COUNT' in _hl2, '数字有自己的开关（与描边各管各的）')
check('ensureCache(minecraft)' in _hl2 and _hl2.count('ensureCache(') >= 3,
      '描边与数字共用同一份缓存（不会框 12 个、数字说 11）')
check('cached.size() <= 1' in _hl2, '只报 2 格以上（一格时原版本来就这样）')

# 潜行那条谎：判定必须收在 preview 这个共用出口里
check('preview(LevelReader level, BlockPos origin, ItemStack tool, boolean sneaking)' in
      open(_p + 'event/PlayerVeinMine.java', encoding='utf-8').read(),
      'preview 收下 sneaking —— 客户端才可能算出「潜行只砸一格」')
check('player.isShiftKeyDown()' in _hl2 and 'Config.PLAYER_MINE_SNEAK_DISABLES' in _hl2,
      '缓存键含潜行状态（蹲下立刻重算）')

_lg = open('F:/mcmod/src/main/resources/assets/apocalypse_zombies/lang/zh_cn.json',
           encoding='utf-8').read()
_lg_en = open('F:/mcmod/src/main/resources/assets/apocalypse_zombies/lang/en_us.json',
              encoding='utf-8').read()
check('hud.apocalypse_zombies.vein_count' in _lg and '会连挖 %s 格' in _lg,
      'zh_cn 有「会连挖 %s 格」')
check('hud.apocalypse_zombies.vein_count_capped' in _lg, 'zh_cn 有「已到上限」那条')
check('hud.apocalypse_zombies.vein_count' in _lg_en, 'en_us 也有（不是只有中文能看）')

_cfg11 = open(_p + 'Config.java', encoding='utf-8').read()
import re as _re11
_n11 = len(_re11.findall(
    r'public static final ForgeConfigSpec\.[A-Za-z<>?,\s\.]+?\s+[A-Z_0-9]+\s*;', _cfg11))
check(_n11 == 169, '配置项总数 169（1.1.82 的 168 + 数字 1）', '实得 %d' % _n11)
check('define("count", true)' in _cfg11, 'count 默认 true（开启）')
check('PLAYER_MINE_COUNT' in _cfg11, 'Config 有字段 PLAYER_MINE_COUNT')

with zipfile.ZipFile(SRC) as _z11:
    _n11l = _z11.namelist()
    _hlcls2 = _z11.read('com/apocalypse/zombies/client/renderer/VeinMineHighlighter.class')
    _cfgcls11 = _z11.read('com/apocalypse/zombies/Config.class')
    _lgcls = _z11.read('assets/apocalypse_zombies/lang/zh_cn.json').decode('utf-8')
check(b'renderCount' in _hlcls2, 'VeinMineHighlighter.class 里有 renderCount')
check(b'count' in _cfgcls11, 'Config.class 内含配置名字面量 count')
check('会连挖' in _lgcls, 'lang 词条进包了（不是只在源码里）')

_ce11 = open(_p + 'client/ClientEvents.java', encoding='utf-8').read()
check('VeinMineHighlighter.renderCount(graphics, minecraft)' in _ce11,
      'ClientEvents 每帧调数字（渲染与 HUD 都挂上了）')

_rd11 = open('F:/mcmod/readme.md', encoding='utf-8').read()
check('### 1.1.83 —' in _rd11, 'readme 有 1.1.83 更新日志条目')
check('`count`' in _rd11 and '会连挖' in _rd11, 'readme 写明 count 与数字文案')
check('全部 169 项配置' in _rd11, 'readme 写明图形界面共 169 项')
print('=== 最后：工程门禁（本机实跑） ===')
rc = subprocess.call(['py', 'tools/check_gun_resources.py'], cwd='F:/mcmod')
check(rc == 0, 'tools/check_gun_resources.py 全绿', 'exit %d' % rc)

print('=== 8/9 基线校验 + 换包 ===')
if not os.path.isdir(MODS):
    check(False, 'mods/ 存在', MODS)
    raise SystemExit(1)
jars = [f for f in os.listdir(MODS) if f.lower().endswith('.jar')]
subdirs = [f for f in os.listdir(MODS) if os.path.isdir(os.path.join(MODS, f))]
mine = [f for f in jars if f.startswith(PREFIX)]
others = [f for f in jars if not f.startswith(PREFIX)]
check(not subdirs, 'mods/ 下无子目录（Forge 会递归扫描）', subdirs or '干净')
check(len(mine) == 1, 'mods/ 里只有 1 个本模组包', mine)
client, devsrv = game_state()
check(client is not True, '游戏客户端没在跑', '探测失败=按未在跑处理'
      if client is None else ('在跑！' if client else '未在跑'))
if devsrv and not args.allow_dev_server:
    check(False, '无头开发服没在跑（要放行加 --allow-dev-server）', '在跑')
base_ver = jar_version(os.path.join(MODS, mine[0])) if mine else '?'
check(base_ver in ACCEPT, '基线包版本 ∈ %s（按包内 mods.toml 认）' % (ACCEPT,), base_ver)
other_md5 = {f: md5(os.path.join(MODS, f)) for f in others}

if not ok:
    print('\n★ 有判据未通过 —— 未改动 mods/。')
    raise SystemExit(1)

os.makedirs(BACKUP, exist_ok=True)
old = os.path.join(MODS, mine[0])
shutil.move(old, os.path.join(BACKUP, mine[0]))
shutil.copy2(SRC, os.path.join(MODS, os.path.basename(SRC)))
print('  换包：%s → mods_backup/；新包 %s' % (mine[0], os.path.basename(SRC)))

backups = sorted([f for f in os.listdir(BACKUP) if f.startswith(PREFIX)],
                 key=lambda f: [int(x) for x in re.findall(r'\d+', f)])
for f in backups[:-KEEP_BACKUPS]:
    os.remove(os.path.join(BACKUP, f))
    print('  清理旧备份：%s' % f)

now = {f: md5(os.path.join(MODS, f)) for f in os.listdir(MODS) if f.lower().endswith('.jar')}
same = all(now.get(f) == m for f, m in other_md5.items())
check(same, '其它模组 md5 全等（没被误伤）', '%d 个' % len(others))
check(jar_version(os.path.join(MODS, os.path.basename(SRC))) == VER, '装机包版本 == %s' % VER)
print('\n★ 出货完成：mods/ = %s' % [f for f in now if f.startswith(PREFIX)])
raise SystemExit(0 if ok else 1)
