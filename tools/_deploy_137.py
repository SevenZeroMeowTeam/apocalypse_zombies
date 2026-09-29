# -*- coding: utf-8 -*-
"""1.1.37 出货：Uzi 冲锋枪上下线（新增物品，全量 Java 接线）。

用户逐字请求：
    编译jar替换测试

改了什么（**新增一把枪**，其余四把 + 所有既有一字节不动）：
  · 资产  geo/uzi.geo.json（22 骨 / 185 体块 / 1110 面）、animations/uzi.animation.json
          （9 clip / 354 键）、textures/item/uzi.png（512×512）、models/item/uzi.json
  · Java  UziItem（全自动：按住连发、松手停火、空匣自停；DAMAGE_TYPE=uzi_bullet；
          BOLT_TICKS=26；FIRE_INTERVAL_TICKS=2 = 600 rpm）
          UziGeoModel（191 行契约：frame / capture / rightHand / leftHand）
          UziItemRenderer（一/三人称变换常量，由 tools/pose_measure.py uzi 量出）
          WeaponArms（renderUzi + UziItem 分支 + frame.invalidate）
          ModItems（注册 UZI + 创造标签）
          GunItem.SightStyle 不涉及（Uzi 铁瞄：hasScopeOverlay=false）
  · 数据  data/apocalypse_zombies/damage_type/uzi_bullet.json（独立伤害类型，**不加** bypasses_armor）
  · 语言  zh_cn / en_us：物品名 + 两条死亡信息

断言重心：
  1. 版本号先落 gradle.properties，再由本脚本自己跑构建（不许沿用旧产物）。
  2. jar 内 mods.toml == 1.1.37。
  3. **新增物品的硬证据**：新包相对 1.1.36 旧包，除 uzi 相关条目外**逐条字节全等**
     ——「其余四把枪和全部既有资产一字节没动」。
  4. **资产三向对账**：jar 内 uzi 三件套 == art/uzi/ == src/main/resources/，逐字节相同。
  5. 新鲜度指纹：geo 里有 Uzi 专属总成骨骼（sight_front / sight_rear / bolt / magazine /
     additional_magazine），动画里有 9 个冻结剪辑名 —— 打进包的不是占位模型。
  6. **类与符号进包**：UziItem / UziGeoModel / UziItemRenderer / ModItems 的自有符号必须齐
     （自有类名与自有方法名不会被 SRG 重映射，原版名才会，所以这里钉的全是自己的符号）。
  7. 伤害类型独立：uzi_bullet.json 在包内，且 **不在** bypasses_armor tag 里（AWM 专属）。
  8. check_uzi_anim.py + check_uzi_art.py 全过；其余 6 个校验器回归。
  9. 部署前探 jar 锁：游戏在跑就明确报错退出，绝不半路拷坏。
 10. 部署只动 apocalypse_zombies-* 前缀，其余模组逐个 md5 断「原样在位」。
"""
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODS = 'C:/Users/Administrator/Desktop/.minecraft/versions/1.20.1-Forge_47.4.23-2/mods'
OLD, NEW = '1.1.36', '1.1.37'
JAR = 'apocalypse_zombies-%s.jar' % NEW
PREFIX = 'apocalypse_zombies-'


def pick_baseline():
    """挑一个**干净**的 1.1.36 基线：必须是没被后续构建覆盖过的那一份。

    踩过的坑：build/libs 里同名 jar 会被后来的构建原地覆盖 —— 超时中断的那次构建把
    build/libs/1.1.36.jar 重建成含 uzi 资产的包（233 → 242 条），拿它当基线会让
    「其余零改动」这条断言永远为真。mods 目录里那份才是真正出货过的字节。
    """
    cands = [os.path.join(MODS, 'apocalypse_zombies-%s.jar' % OLD),
             os.path.join(ROOT, 'build', 'libs', 'apocalypse_zombies-%s.jar' % OLD)]
    for p in cands:
        if not os.path.isfile(p):
            continue
        with zipfile.ZipFile(p) as z:
            n = z.namelist()
        if any('uzi' in x.lower() for x in n):
            continue                     # 被污染，换下一个
        return p, n
    sys.exit('找不到干净的 %s 基线包（候选都被含 uzi 的构建覆盖过）：%r' % (OLD, cands))


OLDJAR, OLD_NAMES = pick_baseline()

SRC = 'src/main/resources/'
RES = 'assets/apocalypse_zombies/'
DATA = 'data/apocalypse_zombies/'
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
# 新增物品进包：类 + 自有符号
UZI_CLASSES = {
    'com/apocalypse/zombies/item/UziItem.class': [b'uzi_bullet', b'shoot_auto', b'shoot',
                                                  b'ADS_up', b'ADS_down', b'reload_empty'],
    'com/apocalypse/zombies/client/model/UziGeoModel.class': [b'rightHand', b'leftHand', b'capture',
                                                              b'GRIP'],
    'com/apocalypse/zombies/client/renderer/UziItemRenderer.class': [b'UziItemRenderer',
                                                                    b'MOVE_BONE', b'capture',
                                                                    b'TP_X_RIGHT'],
    'com/apocalypse/zombies/registry/ModItems.class': [b'uzi'],
    'com/apocalypse/zombies/client/weapon/WeaponArms.class': [b'renderUzi', b'UziItem'],
}
# 说明：这里只钉**自有**符号。原版覆写的方法名（例：BlockEntityWithoutLevelRenderer.renderByItem）
# 在构建时会被 SRG 重映射成 m_xxxxxx_，钉了必然误报 —— 本项目踩过这个坑。
CLIPS = 9
# 与 uzi 无关、必须与 1.1.36 逐条字节全等的包内前缀
UNTOUCHED_PREFIXES = ('assets/apocalypse_zombies/', 'data/apocalypse_zombies/',
                      'data/minecraft/')
# 路径里不含 "uzi" 但本轮**确实有意改动**的条目（新增物品必然要加语言键）
EXPECTED_CHANGED = {RES + 'lang/zh_cn.json', RES + 'lang/en_us.json'}


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 16), b''):
            h.update(b)
    return h.hexdigest()


def run_checker(script, extra=()):
    cmd = [sys.executable, os.path.join(ROOT, 'tools', script)] + list(extra)
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True)
    return r.returncode, (r.stdout + r.stderr).decode('utf-8', 'replace')


# ---------------------------------------------------------------- 0. 旧包基线
old_zip = zipfile.ZipFile(OLDJAR)
old_names = set(OLD_NAMES)
print('[0] 基线 %s  条目 %d 个（已自检：不含任何 uzi 条目）'
      % (OLDJAR.replace(ROOT + os.sep, ''), len(old_names)))

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

# ---- 3. 新增物品：显式列出「本轮新增的条目」，其余必须与旧包逐条全等
added = sorted(n for n in names - old_names if 'uzi' in n.lower())
removed = sorted(n for n in old_names - names)
changed = []
for n in sorted(names & old_names):
    if not n.startswith(UNTOUCHED_PREFIXES):
        continue
    if 'uzi' in n.lower():
        continue          # uzi 相关本轮本来就可能改
    if zf.read(n) != old_zip.read(n):
        changed.append(n)
unexpected = [n for n in changed if n not in EXPECTED_CHANGED]
assert not unexpected, '本节应「除 uzi 外零改动」，但这些条目变了：%r' % unexpected[:12]
assert set(changed) == EXPECTED_CHANGED, ('有意改动的条目集合应恰为语言文件，实际 %r'
                                          % sorted(set(changed) - EXPECTED_CHANGED or changed))
print('[5] 新增 uzi 条目 %d 个；其余资产/数据条目逐条字节全等（仅两套语言文件有意增键）'
      % len(added))
print('    新增：%s' % ', '.join(added[:8]) + (' …' if len(added) > 8 else ''))
if removed:
    print('    消失（预期为空）：%r' % removed[:8])
    sys.exit('旧包里有条目在新包里消失，先查清再说')

# ---- 4. 资产三向对账：jar == art/uzi/ == src
for p in [a[1] for a in ASSETS]:
    d = os.path.dirname(os.path.join(ROOT, p))
    if not os.path.isdir(d):
        os.makedirs(d)
    srcp = os.path.join(ROOT, [a[2] for a in ASSETS if a[1] == p][0])
    if not os.path.isfile(os.path.join(ROOT, p)) or md5(os.path.join(ROOT, p)) != md5(srcp):
        shutil.copy2(srcp, os.path.join(ROOT, p))
        print('[6] 归档到 %s' % p)

bad = []
for inner, local, srcp in ASSETS:
    assert inner in names, 'jar 里没有 %s' % inner
    jh = hashlib.md5(zf.read(inner)).hexdigest()
    lh = md5(os.path.join(ROOT, local))
    sh = md5(os.path.join(ROOT, srcp))
    if not (jh == lh == sh):
        bad.append((inner, jh, lh, sh))
assert not bad, 'jar / art / src 三向不一致：%r' % bad
print('[7] 资产三向对账：geo / animation / png —— jar == art/uzi/ == src，逐字节相同')
print('    md5  %s' % md5(os.path.join(ROOT, ASSETS[0][1])))

missing = [p for p in EXTRA_PRESENT if p not in names]
assert not missing, 'jar 里缺：%r' % missing
print('[8] 物品模型 / 两套语言 / 伤害类型 json 均在包内')

for inner, needles in FINGERPRINTS.items():
    blob = zf.read(inner)
    for needle in needles:
        assert needle in blob, '%s 里没有 %r（打进包的不是 Uzi 那一版？）' % (inner, needle)
print('[9] 新鲜度指纹：4 个 Uzi 总成骨骼 + %d 个剪辑名齐备' % CLIPS)

missing_cls, missing_sym = [], []
for inner, needles in UZI_CLASSES.items():
    if inner not in names:
        missing_cls.append(inner)
        continue
    blob = zf.read(inner)
    missing_sym += [(inner, n) for n in needles if n not in blob]
assert not missing_cls, 'jar 里没有这些类：%r' % missing_cls
assert not missing_sym, '类里没有这些符号：%r' % missing_sym
print('[10] 类与符号进包：UziItem / UziGeoModel / UziItemRenderer / ModItems / WeaponArms 齐')
zf.close()
old_zip.close()

# ---- 5. 伤害类型独立：不在 bypasses_armor 里
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
        print('=== 1.1.37 构建完成，但**没有部署** ===')
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
print('=== 1.1.37 出货完成 ===')
print('    jar : %s' % JAR)
print('    md5 : %s' % new_md5)
print('    尺寸: %d 字节' % os.path.getsize(jar))
print('    内容是: Uzi 冲锋枪（22 骨 / 9 clip / 1110 面 / 全自动 600 rpm / 铁瞄）')
