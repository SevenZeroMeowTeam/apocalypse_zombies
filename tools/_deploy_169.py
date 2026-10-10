import pathlib
"""1.1.69 出货：猫耳娘「工具即指令」（斧→伐木 / 镐→挖矿 / 剑·弓→打怪 + 弓会放箭）（猫耳娘 v4 内容不回退 —— 128² 皮肤 / 逐面 UV 装机 geo / 脸层 44×32）。

跑法（**游戏须完全关闭**）：
    py tools/_deploy_166.py --build        # 先 ./gradlew build 再出货
    py tools/_deploy_166.py                # 用 build/libs 里已构建好的包

判据（任一条不过就退出，不动 mods/）：
  1. 构建产物存在，且 jar 内 mods.toml 的 version == 1.1.69；
  2. 猫耳娘该有的东西：
     · geo/cat_girl.geo.json —— identifier geometry.cat_girl、贴图基准 128×128、
       31 骨 / 126 方块，且**每个 cube 用逐面 uv/uv_size**（v4 的盒式 UV 表达不了
       每块不同密度，必须逐面）；rest 姿态骨骼无旋转（骨骼一根都不许带 rotation）；
     · textures/entity/cat_girl.png 是 128×128；
     · animations/cat_girl.animation.json 在位，每条片段 animation_length > 0；
     · Java 侧 CatGirlEntity / CatGirlGeoModel / CatGirlGeoRenderer 在 jar 里；
  3. **不回归**：柯尔特 1878 仍在包里且规格未变（12 骨 / 87 方块 / 512² 基准 /
     8 条片段长度逐条等于 Java 常量）—— 1.1.68 的内容不许被这次改动冲掉；
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

VER = '1.1.69'
PREV = '1.1.68'
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
_ap = argparse.ArgumentParser(description='1.1.69 出货：猫耳娘 v4')
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


print('=== 1/5 构建产物 ===')
if args.build or not os.path.exists(SRC):
    if args.build:
        print('  跑 ./gradlew build ...')
        rc = subprocess.call(['./gradlew', 'build', '--console=plain'], cwd='F:/mcmod')
        if rc != 0:
            print('  ★ 构建失败（exit %d）' % rc)
            raise SystemExit(1)
if not os.path.exists(SRC):
    print('  没有 %s —— 先跑 py tools/_deploy_166.py --build' % SRC)
    raise SystemExit(1)
src_md5, src_size = md5(SRC), os.path.getsize(SRC)
print('  %s\n  md5=%s  %d 字节' % (SRC, src_md5, src_size))

print('=== 2/5 包内自检：猫耳娘 v4 ===')
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
check('HIDDEN_PLAYER_Y' in menusrc and 'HOTBAR_Y' in menusrc,
      '她的界面把玩家 27 格藏在面板外、只留快捷栏')

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

print('=== 3/5 不回归：柯尔特 1878（1.1.68 内容不许被冲掉） ===')
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

print('=== 4/5 工程门禁（本机实跑） ===')
rc = subprocess.call(['py', 'tools/check_gun_resources.py'], cwd='F:/mcmod')
check(rc == 0, 'tools/check_gun_resources.py 全绿', 'exit %d' % rc)

print('=== 5/5 基线校验 + 换包 ===')
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
