# -*- coding: utf-8 -*-
"""1.1.38 出货：瞄具线归零 + 五把枪打完自动换弹。

用户逐字请求：
    验连发/空匣停火/两套换弹；2.34° 瞄具线要修，所有武器添加打完自动换弹，手持武器需要看见2只手

改了什么（**只动这五把枪 + Uzi 的瞄具几何**，其余条目一字节不动）：
  · Uzi 瞄具几何（真源 tools/uzi_bb_gen.js:197,205）
      sf_post 柱顶   3.45 -> 3.26   —— 原先比自己的护环顶盖（sf_hood_top 下沿 3.26）高 0.13，
                                        柱戳穿护环，是真缺陷
      sr_ap  孔心    3.08 -> 3.26   —— 片体 3.16–3.36，仍在 sr_leaf(≤3.38) 与护耳(≤3.46) 内
    改后瞄具线两端同高 3.26、与枪膛平行；pose_measure 报 0.00° 离轴（原 2.34°）。
    几何重跑重掷骨骼 UUID，动画已按台账第 53 条随之重建。
  · UziItem.ADS_Y  0.3118 -> 0.3015（孔心抬高 0.18u 后重新量算，残差 0.0000）
  · 五把枪 inventoryTick 新增「打空立刻自动换弹」：弹匣空、动作空闲、未上锁时自行 beginReload。
    位置在「已排定动作处理完之后」，所以 M1 照常叮（叮声本就在 reload_empty 片段里）、
    栓动枪照常循环枪机，才轮到换弹。只对**手持**生效（selected）。
  · 五把枪 tryFire 空匣分支新增「扣扳机也触发换弹」（用户要的二者都要），干响一声照旧。
  · 未动：连发节奏、空匣停火、拉栓、两套换弹片段与它们的按键绑定。

断言重心：
  1. 基线必须是**真正出货过的** 1.1.37 字节（md5 钉死在 e0d32981…），防止拿被本轮构建
     覆盖过的同名 jar 当基线让比对失去意义。
  2. 版本号先落 gradle.properties，再由本脚本自己跑构建（不许沿用旧产物）。
  3. jar 内 mods.toml == 1.1.38。
  4. **本轮改动的硬证据**：新包相对 1.1.37 逐条字节比对，变化的条目必须**恰为**
     5 把枪的 class + uzi 三件套 + mods.toml；少一条（没改进去）或多一条（误伤别处）都退出。
  5. **数值指纹**（这一版专属，防止打进旧几何/旧常量的包）：
     geo 里 sf_post 顶 = 3.26、sr_ap 孔心 = 3.26；UziItem.class 含 0.3015f 的 IEEE754 字节
     且**不含** 0.3118f。
  6. 资产三向对账：jar 内 uzi 三件套 == art/uzi/ == src/main/resources/，逐字节相同。
  7. 6 把枪的校验器（uzi art/anim + 其余 6 个）全过。
  8. 部署前探 jar 锁：游戏在跑就明确报错退出，绝不半路拷坏。
  9. 部署只动 apocalypse_zombies-* 前缀，其余模组逐个 md5 断「原样在位」。
"""
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODS = 'C:/Users/Administrator/Desktop/.minecraft/versions/1.20.1-Forge_47.4.23-2/mods'
OLD, NEW = '1.1.37', '1.1.38'
JAR = 'apocalypse_zombies-%s.jar' % NEW
PREFIX = 'apocalypse_zombies-'
# 1.1.37 出货件的 md5（本轮基线的唯一合法身份）
OLD_SHIPPED_MD5 = 'e0d329810177c0fc0dd65560e4b9a978'

RES = 'assets/apocalypse_zombies/'
DATA = 'data/apocalypse_zombies/'
SRC = 'src/main/resources/'
# (jar 内路径, art/ 侧路径, src 侧路径) —— 三向逐字节对账
ASSETS = [
    (RES + 'geo/uzi.geo.json', 'art/uzi/uzi.geo.json', SRC + RES + 'geo/uzi.geo.json'),
    (RES + 'animations/uzi.animation.json', 'art/uzi/uzi.animation.json',
     SRC + RES + 'animations/uzi.animation.json'),
    (RES + 'textures/item/uzi.png', 'art/uzi/uzi.png', SRC + RES + 'textures/item/uzi.png'),
]
EXTRA_PRESENT = [
    RES + 'models/item/uzi.json',
    RES + 'lang/zh_cn.json',
    RES + 'lang/en_us.json',
    DATA + 'damage_type/uzi_bullet.json',
]
# 新鲜度指纹：必须是**自己的**标识符（原版名会被 SRG 重映射掉，钉了必然误报）
FINGERPRINTS = {
    RES + 'geo/uzi.geo.json': [b'"sight_front"', b'"sight_rear"', b'"bolt"', b'"magazine"',
                               b'"additional_magazine"'],
    RES + 'animations/uzi.animation.json': [b'"static_idle"', b'"draw"', b'"shoot"',
                                            b'"shoot_auto"', b'"bolt"', b'"reload_tactical"',
                                            b'"reload_empty"', b'"ADS_up"', b'"ADS_down"'],
}
CLIPS = 9
# 五把枪的 class（本轮确实改了）
GUN_CLASSES = [
    'com/apocalypse/zombies/item/UziItem.class',
    'com/apocalypse/zombies/item/M1GarandItem.class',
    'com/apocalypse/zombies/item/MosinNagantItem.class',
    'com/apocalypse/zombies/item/AWMItem.class',
    'com/apocalypse/zombies/item/CrossbowItem.class',
]
# 允许变化的条目：5 把枪的 class（含其内部类 X$1.class —— javac 为 switch-map 生成，
# 主类一变它就变）+ uzi 三件套 + 版本清单（MANIFEST 可能带版本行）
GUN_CLASS_PREFIXES = tuple(c[:-len('.class')] for c in GUN_CLASSES)
ALLOWED_CHANGED = set(GUN_CLASSES) | {
    RES + 'geo/uzi.geo.json',
    RES + 'animations/uzi.animation.json',
    RES + 'textures/item/uzi.png',
    'META-INF/mods.toml',
    'META-INF/MANIFEST.MF',
    'META-INF/maven/com.apocalypse.zombies/apocalypse_zombies/pom.properties',
}


def entry_allowed(n):
    """只放行 5 把枪自己的条目，以及「主类名 + $」的内部类。

    用 '$' 卡住后缀：否则 UziItemRenderer.class 会因为前缀是 UziItem 而被误放行。
    """
    if n in ALLOWED_CHANGED:
        return True
    return n.endswith('.class') and any(n.startswith(p + '$') for p in GUN_CLASS_PREFIXES)

# 必须变化的条目（少一条就说明改动没进包）
MUST_CHANGE = set(GUN_CLASSES) | {RES + 'geo/uzi.geo.json', RES + 'textures/item/uzi.png',
                                  'META-INF/mods.toml'}
# 数值指纹
F_OLD_ADS = struct.pack('>f', 0.3118)
F_NEW_ADS = struct.pack('>f', 0.3015)
POST_TOP_Y, APERTURE_CENTER_Y = 3.26, 3.26


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 16), b''):
            h.update(b)
    return h.hexdigest()


def run_checker(script):
    cmd = [sys.executable, os.path.join(ROOT, 'tools', script)]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True)
    return r.returncode, (r.stdout + r.stderr).decode('utf-8', 'replace')


def pick_baseline():
    """挑 1.1.37 基线：md5 必须是真正出货过的字节。

    踩过的坑（1.1.37 那次）：build/libs 里同名 jar 会被后来的构建原地覆盖 —— 超时中断的那次
    构建把 build/libs/1.1.36.jar 重建成含 uzi 资产的包，拿它当基线会让「零改动」断言永远为真。
    本脚本直接用 md5 钉身份，被覆盖过的候选自动落选。
    """
    cands = [os.path.join(MODS, 'apocalypse_zombies-%s.jar' % OLD),
             os.path.join(ROOT, 'build', 'libs', 'apocalypse_zombies-%s.jar' % OLD)]
    for p in cands:
        if os.path.isfile(p) and md5(p) == OLD_SHIPPED_MD5:
            with zipfile.ZipFile(p) as z:
                return p, z.namelist()
    sys.exit('找不到 md5 == %s 的 %s 基线：%r\n（被后续构建覆盖过就不能当基线）'
             % (OLD_SHIPPED_MD5, OLD, cands))


OLDJAR, OLD_NAMES = pick_baseline()

# ---------------------------------------------------------------- 0. 旧包基线
old_zip = zipfile.ZipFile(OLDJAR)
old_names = set(OLD_NAMES)
print('[0] 基线 %s  条目 %d 个  md5 %s（== 1.1.37 出货件）'
      % (OLDJAR.replace(ROOT + os.sep, ''), len(old_names), OLD_SHIPPED_MD5))

# ---------------------------------------------------------------- 1. 版本号 -> 构建
gp = os.path.join(ROOT, 'gradle.properties')
with open(gp, 'r', encoding='utf-8', newline='') as fh:
    txt = fh.read()
if 'mod_version=%s' % NEW in txt:
    print('[1] gradle.properties 已是 %s' % NEW)
else:
    assert 'mod_version=%s' % OLD in txt, 'gradle.properties 里既不是 %s 也不是 %s' % (OLD, NEW)
    with open(gp, 'w', encoding='utf-8', newline='') as fh:
        fh.write(txt.replace('mod_version=%s' % OLD, 'mod_version=%s' % NEW))
    print('[1] gradle.properties: %s -> %s' % (OLD, NEW))

print('[2] 构建中（gradlew build --offline）…')
r = subprocess.run([os.path.join(ROOT, 'gradlew.bat'), 'build', '--offline', '--console=plain'],
                   cwd=ROOT, capture_output=True)
log = r.stdout.decode('gbk', 'replace') + r.stderr.decode('gbk', 'replace')
if 'BUILD SUCCESSFUL' not in log:
    print(log[-4000:])
    sys.exit('构建失败（上面是日志尾部）')
print('    BUILD SUCCESSFUL')

jar = os.path.join(ROOT, 'build', 'libs', JAR)
assert os.path.isfile(jar), '没有产物 %s（失败构建会留旧包，不可当出货件）' % jar
new_md5 = md5(jar)
print('[3] %s  md5=%s  %d 字节' % (JAR, new_md5, os.path.getsize(jar)))

# ---------------------------------------------------------------- 2. jar 内容门禁
zf = zipfile.ZipFile(jar)
names = set(zf.namelist())
assert 'META-INF/mods.toml' in names, 'jar 里没有 mods.toml'
assert NEW in zf.read('META-INF/mods.toml').decode('utf-8', 'replace'), 'mods.toml 不是 %s' % NEW
print('[4] mods.toml 版本 = %s' % NEW)

# ---- 3. 逐条字节比对：变化的必须恰为「5 把枪 + uzi 三件套 + 版本清单」
added = sorted(names - old_names)
removed = sorted(old_names - names)
changed = sorted(n for n in (names & old_names) if zf.read(n) != old_zip.read(n))
unexpected = [n for n in changed if not entry_allowed(n)]
assert not unexpected, '这些条目不该变：%r' % unexpected[:12]
assert not added, '不该有新增条目：%r' % added[:12]
assert not removed, '不该有条目消失：%r' % removed[:12]
missed = sorted(MUST_CHANGE - set(changed))
assert not missed, '这些条目本该变化却没变（改动没进包）：%r' % missed
print('[5] 相对 1.1.37 变化的条目 %d 个，全部在预期集合内：' % len(changed))
for n in changed:
    print('      %s' % n)

# ---- 4. 数值指纹（本版专属）
geo_blob = zf.read(RES + 'geo/uzi.geo.json')
gz = json.loads(geo_blob.decode('utf-8'))
post_top = ap_center = None
for geo_ in gz['minecraft:geometry']:
    for b in geo_.get('bones', []):
        for c in b.get('cubes', []):
            o, s = c.get('origin'), c.get('size')
            if b.get('name') == 'sight_front' and abs(s[1] - 0.48) < 0.01 and abs(o[1] - 2.78) < 0.01:
                post_top = o[1] + s[1]
            if b.get('name') == 'sight_rear' and abs(s[1] - 0.20) < 0.01 and abs(o[1] - 3.16) < 0.01:
                ap_center = o[1] + s[1] / 2.0
assert post_top is not None and abs(post_top - POST_TOP_Y) < 0.01, \
    '前准星柱顶不是 %s（是 %r）—— 打进包的是旧几何' % (POST_TOP_Y, post_top)
assert ap_center is not None and abs(ap_center - APERTURE_CENTER_Y) < 0.01, \
    '后照门孔心不是 %s（是 %r）—— 打进包的是旧几何' % (APERTURE_CENTER_Y, ap_center)
uzi_cls = zf.read('com/apocalypse/zombies/item/UziItem.class')
assert F_NEW_ADS in uzi_cls, 'UziItem.class 里没有新 ADS_Y=0.3015f 的字节'
assert F_OLD_ADS not in uzi_cls, 'UziItem.class 里还有旧 ADS_Y=0.3118f 的字节'
print('[6] 数值指纹：前柱顶 %.2f / 孔心 %.2f（两端同高，瞄具线平行枪膛）；'
      'UziItem.class 含 0.3015f 且不含 0.3118f' % (post_top, ap_center))

# ---- 5. 资产三向对账：jar == art/uzi/ == src
for p in [a[1] for a in ASSETS]:
    d = os.path.dirname(os.path.join(ROOT, p))
    if not os.path.isdir(d):
        os.makedirs(d)
    srcp = os.path.join(ROOT, [a[2] for a in ASSETS if a[1] == p][0])
    if not os.path.isfile(os.path.join(ROOT, p)) or md5(os.path.join(ROOT, p)) != md5(srcp):
        shutil.copy2(srcp, os.path.join(ROOT, p))
        print('[7] 归档到 %s' % p)

bad = []
for inner, local, srcp in ASSETS:
    assert inner in names, 'jar 里没有 %s' % inner
    jh = hashlib.md5(zf.read(inner)).hexdigest()
    lh = md5(os.path.join(ROOT, local))
    sh = md5(os.path.join(ROOT, srcp))
    if not (jh == lh == sh):
        bad.append((inner, jh, lh, sh))
assert not bad, 'jar / art / src 三向不一致：%r' % bad
print('[8] 资产三向对账：geo / animation / png —— jar == art/uzi/ == src，逐字节相同')
print('    md5  %s' % md5(os.path.join(ROOT, ASSETS[0][1])))

missing = [p for p in EXTRA_PRESENT if p not in names]
assert not missing, 'jar 里缺：%r' % missing
print('[9] 物品模型 / 两套语言 / 伤害类型 json 均在包内')

for inner, needles in FINGERPRINTS.items():
    blob = zf.read(inner)
    for needle in needles:
        assert needle in blob, '%s 里没有 %r（打进包的不是 Uzi 那一版？）' % (inner, needle)
print('[10] 新鲜度指纹：4 个 Uzi 总成骨骼 + %d 个剪辑名齐备' % CLIPS)

zf.close()
old_zip.close()

# ---- 6. 伤害类型独立：不在 bypasses_armor 里
zf = zipfile.ZipFile(jar)
ba = 'data/minecraft/tags/damage_type/bypasses_armor.json'
assert ba in zf.namelist(), 'jar 里没有 %s' % ba
body = zf.read(ba).decode('utf-8', 'replace')
assert 'uzi_bullet' not in body, 'uzi_bullet 混进了 bypasses_armor（那是 AWM 专属的穿透护甲）'
zf.close()
print('[11] 伤害类型独立：uzi_bullet 在包内，且未混入 bypasses_armor')

# ---------------------------------------------------------------- 3. 校验器门禁
for script in ('check_uzi_anim.py', 'check_uzi_art.py'):
    rc, out = run_checker(script)
    print(out.rstrip()[-1200:])
    if rc != 0:
        sys.exit('%s 未通过（exit %d）' % (script, rc))
print('[12] check_uzi_anim.py + check_uzi_art.py 全过')

for script in ('check_gun_resources.py', 'check_awm_anim.py', 'check_mosin_anim.py',
               'check_m1_reload.py', 'check_gun_mobs.py', 'check_crossbow_anim.py'):
    rc, out = run_checker(script)
    if rc != 0:
        print(out.rstrip()[-1500:])
        sys.exit('%s 回归失败（exit %d）' % (script, rc))
print('[13] 其余 6 个枪械校验器回归通过')

# ---------------------------------------------------------------- 4. 部署
old_target = os.path.join(MODS, 'apocalypse_zombies-%s.jar' % OLD)
new_target = os.path.join(MODS, JAR)

if os.path.isfile(old_target):
    try:
        with open(old_target, 'r+b'):
            pass
    except PermissionError:
        print()
        print('=== %s 构建完成，但**没有部署** ===' % NEW)
        print('    jar : %s' % jar)
        print('    md5 : %s' % new_md5)
        print('    原因: %s 被占用（游戏或启动器还开着）' % os.path.basename(old_target))
        print('    退出客户端后重跑本脚本即可完成部署（不会半路拷坏）。')
        sys.exit(3)

before = {}
for n in os.listdir(MODS):
    p = os.path.join(MODS, n)
    if os.path.isfile(p) and n.endswith('.jar') and not n.startswith(PREFIX):
        before[n] = md5(p)
print('[14] 部署前：其它模组 %d 个（将逐个断原样在位）' % len(before))

if os.path.isfile(old_target):
    bak = old_target + '.old.bak'
    if os.path.isfile(bak):
        os.remove(bak)
    os.rename(old_target, bak)
    print('[15] 旧包改名 %s -> %s' % (os.path.basename(old_target), os.path.basename(bak)))
else:
    print('[15] 旧包不在 mods 里（可能已改名），跳过')

shutil.copy2(jar, new_target)
assert md5(new_target) == new_md5, '部署后 md5 不一致（拷坏了）'

after = {}
for n in os.listdir(MODS):
    p = os.path.join(MODS, n)
    if os.path.isfile(p) and n.endswith('.jar') and not n.startswith(PREFIX):
        after[n] = md5(p)
assert before == after, '其它模组的 jar 被动过了！'
print('[16] 其它模组原样在位：%d 个 md5 全等' % len(after))

live = [n for n in os.listdir(MODS) if n.startswith(PREFIX) and n.endswith('.jar')]
assert live == [JAR], 'mods 里不该同时存在多个版本：%r' % (live,)
print('[17] mods 内唯一样本：%s' % live[0])

print()
print('=== %s 出货完成 ===' % NEW)
print('    jar : %s' % JAR)
print('    md5 : %s' % new_md5)
print('    尺寸: %d 字节' % os.path.getsize(jar))
print('    内容是: 瞄具线归零（两端 3.26，0.00° 离轴）+ 五把枪打完自动换弹（含空匣扣扳机也触发）')
