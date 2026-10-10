import sys
import pathlib
"""1.1.74 出货：像玩家一样操作第一批 —— 开门/浮水导航 + 开路 + 搭桥 + 自己出门找目标 + 不跟丢（含 1.1.73 全部不回归）（猫耳娘 v4 内容不回退 —— 128² 皮肤 / 逐面 UV 装机 geo / 脸层 44×32）。

跑法（**游戏须完全关闭**）：
    py tools/_deploy_174.py --build        # 先 ./gradlew build 再出货
    py tools/_deploy_174.py                # 用 build/libs 里已构建好的包

判据（任一条不过就退出，不动 mods/）：
  1. 构建产物存在，且 jar 内 mods.toml 的 version == 1.1.74；
  2. 猫耳娘该有的东西：
     · geo/cat_girl.geo.json —— identifier geometry.cat_girl、贴图基准 128×128、
       31 骨 / 126 方块，且**每个 cube 用逐面 uv/uv_size**（v4 的盒式 UV 表达不了
       每块不同密度，必须逐面）；rest 姿态骨骼无旋转（骨骼一根都不许带 rotation）；
     · textures/entity/cat_girl.png 是 128×128；
     · animations/cat_girl.animation.json 在位，每条片段 animation_length > 0；
     · Java 侧 CatGirlEntity / CatGirlGeoModel / CatGirlGeoRenderer 在 jar 里；
  3. **不回归**：柯尔特 1878 仍在包里且规格未变（12 骨 / 87 方块 / 512² 基准 /
     8 条片段长度逐条等于 Java 常量）—— 1.1.71 的内容不许被这次改动冲掉；
  4. 工程门禁在**本机跑一遍**：tools/check_gun_resources.py 全绿才继续；
  5. 基线：mods/ 里当前那个包必须是本版或上一版（按**包内 mods.toml 版本**认）；
  6. 换包：旧包挪到 mods/ **同级** 的 mods_backup/（保 3 份），mods/ 里只留一个本模组包；
     其它模组 md5 必须全等，mods/ 下不许有子目录（Forge 会递归扫描 → 重复加载）。
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

VER = '1.1.74'
PREV = '1.1.73'
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
_ap = argparse.ArgumentParser(description='1.1.74 出货：玩家式操作（导航 / 开路 / 搭桥 / 找目标 / 跟随）')
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


print('=== 1/7 构建产物 ===')
if args.build or not os.path.exists(SRC):
    if args.build:
        print('  跑 ./gradlew build ...')
        rc = subprocess.call('gradlew.bat build --console=plain', shell=True, cwd='F:/mcmod')
        if rc != 0:
            print('  ★ 构建失败（exit %d）' % rc)
            raise SystemExit(1)
if not os.path.exists(SRC):
    print('  没有 %s —— 先跑 py tools/_deploy_174.py --build' % SRC)
    raise SystemExit(1)
src_md5, src_size = md5(SRC), os.path.getsize(SRC)
print('  %s\n  md5=%s  %d 字节' % (SRC, src_md5, src_size))

print('=== 2/7 包内自检：猫耳娘 v4 ===')
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
check('PLAYER_ROW_Y' in menusrc and 'HOTBAR_Y' in menusrc,
      '玩家 27 格回到面板内（原版 9 列布局）')

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
check('PLAYER_ROW_Y = 142' in menusrc and 'PANEL_HEIGHT = 226' in menusrc and 'HIDDEN_PLAYER_Y' not in menusrc,
      '玩家 27 格回到面板内（原版 9 列布局，面板 226）')
scr = open('F:/mcmod/src/main/java/com/apocalypse/zombies/client/gui/CatGirlTradeScreen.java', encoding='utf-8').read()
check('PLAYER_ROW_Y - 6' in scr, '玩家背包分隔线在')
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
check('CAT_GIRL_ALWAYS_DROPS' in work and 'NETHERITE_PICKAXE' in work,
      '砸什么都有掉（无视原版工具等级）')
mitsrc = open('F:/mcmod/src/main/java/com/apocalypse/zombies/registry/ModItems.java', encoding='utf-8').read()
check('love_coin' in mitsrc, '货币（爱心币）仍在')

print('=== 5/7 1.1.73：订做 / 盔甲层 / 熔炼 / 月亮三项 ===')
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

print('=== 4/7 1.1.74：像玩家一样操作（第一批）===')
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

print('=== 3/7 不回归：柯尔特 1878（1.1.71 内容不许被冲掉） ===')
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

print('=== 6/7 工程门禁（本机实跑） ===')
rc = subprocess.call(['py', 'tools/check_gun_resources.py'], cwd='F:/mcmod')
check(rc == 0, 'tools/check_gun_resources.py 全绿', 'exit %d' % rc)

print('=== 7/7 基线校验 + 换包 ===')
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
