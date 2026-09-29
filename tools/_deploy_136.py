# -*- coding: utf-8 -*-
"""1.1.36 出货：十字弩右键 = 透明十字瞄准镜（方案 B）。

用户逐字请求：
    十字弩右键显示十字透明瞄准镜
    用户看图定稿：B（淡青镜片 + 细镜圈 + 双色十字）

改了什么（**只动 Java，模型资产一个字节没动**）：
  · GunItem          新增 `enum SightStyle { TELESCOPE, CLEAR_SIGHT }` + `default sightStyle()`
                     —— 追加式，现有四把枪零改动。
  · CrossbowItem     hasScopeOverlay() false -> true、sightStyle() -> CLEAR_SIGHT、
                     hidesModelWhileAimed() 保持 false（透明镜要看得见世界和弩身）。
  · GunAimState      新增 sightStyle() 转发（与 hasScopeOverlay() 同款）。
  · ClientEvents     renderScope 按镜种分派；新增 renderClearSight / renderRing /
                     renderClearReticle；新增 CLEAR_LENS_* / CLEAR_RIM_* / RETICLE_*
                     常量（与定稿 mock tools/sight_mock.py 逐项同源）。
  · check_crossbow_anim.py
                     新增两类断言：文件 §2 的「透明镜契约」（三条字面返回 + 客户端分派/绘制
                     必须在）与「观感同源」（mock 的颜色/透明度与 ClientEvents 常量逐项相等），
                     并已通过 6/6 咬齿测试（改坏任一处必 FAIL）。

断言重心：
  1. 版本号先落 gradle.properties，再由本脚本自己跑构建（不许沿用旧产物）。
  2. jar 内 mods.toml == 1.1.36。
  3. **资产三向对账**：jar 内 crossbow 的 geo / animation / png 与 art/crossbow/ 的 md5 逐字节相同，
     且与 1.1.35 出货时记录的 md5 逐字节相同 —— 本轮「模型零改动」的硬证据。
  4. 新鲜度指纹：geo 里有自己的现代总成标识符（latch / bolt_loaded / camera / cable_slide），
     动画里有 7 个冻结剪辑名 —— 打进包的不是旧一代十字弩。
  5. **新增：镜种进包**——GunItem$SightStyle.class 存在且含 CLEAR_SIGHT/TELESCOPE；
     CrossbowItem.class 含 CLEAR_SIGHT/sightStyle；GunAimState.class 含 sightStyle；
     ClientEvents.class 含 renderClearSight/renderRing/CLEAR_SIGHT。
     （自有类名与自有方法名不会被 SRG 重映射；原版名才会，所以这里钉的全是自己的符号。）
  6. tools/check_crossbow_anim.py 全过（契约 / Java 契约 / 音效 / 弦缆运动学 / 镜像 / 约定 /
     已知偏差 / 透明镜契约 / 观感同源）。
  7. 其余枪械校验器回归：gun_resources / awm_anim / mosin_anim / m1_reload / gun_mobs。
  8. 部署前探 jar 锁：游戏在跑就明确报错退出，绝不半路拷坏。
  9. 部署只动 apocalypse_zombies-* 前缀，其余模组逐个 md5 断「原样在位」。
"""
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODS = 'C:/Users/Administrator/Desktop/.minecraft/versions/1.20.1-Forge_47.4.23-2/mods'
OLD, NEW = '1.1.35', '1.1.36'
JAR = 'apocalypse_zombies-%s.jar' % NEW
PREFIX = 'apocalypse_zombies-'

RES = 'assets/apocalypse_zombies/'
# (jar 内路径, art/ 侧路径) —— 逐字节对账，本轮「没动模型」的硬证据
ASSETS = [
    (RES + 'geo/crossbow.geo.json', 'art/crossbow/crossbow.geo.json'),
    (RES + 'animations/crossbow.animation.json', 'art/crossbow/crossbow.animation.json'),
    (RES + 'textures/models/crossbow.png', 'art/crossbow/crossbow.png'),
]
# 1.1.35 出货时的模型三件套 md5：本轮必须逐字节不变（改的只有 Java）
MODEL_MD5 = {
    'art/crossbow/crossbow.geo.json': '48d6dceb60d052592e1c72db06c18425',
    'art/crossbow/crossbow.animation.json': '0bdf43755982813b9c1e9f9f9ef1812f',
    'art/crossbow/crossbow.png': 'b4c0e3f7913ed4443d47c03319f749ff',
}
EXTRA_PRESENT = [RES + 'models/item/crossbow.json']
# 1.1.36 新增：新镜种真的进包（类 + 自有符号名）
SIGHT_CLASSES = {
    'com/apocalypse/zombies/item/GunItem$SightStyle.class': [b'CLEAR_SIGHT', b'TELESCOPE'],
    'com/apocalypse/zombies/item/CrossbowItem.class': [b'CLEAR_SIGHT', b'sightStyle'],
    'com/apocalypse/zombies/client/GunAimState.class': [b'sightStyle'],
    'com/apocalypse/zombies/client/ClientEvents.class': [b'renderClearSight', b'renderRing', b'CLEAR_SIGHT'],
}
# 新鲜度指纹：必须是**自己的**标识符（原版名会被 SRG 重映射掉，钉了必然误报）
FINGERPRINTS = {
    RES + 'geo/crossbow.geo.json': [b'"latch"', b'"bolt_loaded"', b'"camera"', b'"cable_slide"'],
    RES + 'animations/crossbow.animation.json': [b'"static_idle"', b'"draw"', b'"shoot"',
                                                 b'"reload_tactical"', b'"ADS_up"', b'"ADS_down"',
                                                 b'"inspect"'],
}
CLIPS = 7


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

bad = []
for inner, local in ASSETS:
    assert inner in names, 'jar 里没有 %s' % inner
    jh = hashlib.md5(zf.read(inner)).hexdigest()
    lh = md5(os.path.join(ROOT, local))
    if jh != lh:
        bad.append((inner, jh, lh))
assert not bad, 'jar 内资产与 art/ 不一致：%r' % bad
print('[5] 资产三向对账：geo / animation / png 与 art/crossbow/ 逐字节相同')

stale = [(p, md5(os.path.join(ROOT, p)), want) for p, want in MODEL_MD5.items()
         if md5(os.path.join(ROOT, p)) != want]
assert not stale, '模型资产被改动了（本轮只该改 Java）：%r' % stale
print('[6] 模型零改动：三件套 md5 与 1.1.35 出货时逐字节相同')

missing = [p for p in EXTRA_PRESENT if p not in names]
assert not missing, 'jar 里缺：%r' % missing
print('[7] 物品模型 %s 在包内' % EXTRA_PRESENT[0].split('/')[-1])

for inner, needles in FINGERPRINTS.items():
    blob = zf.read(inner)
    for needle in needles:
        assert needle in blob, '%s 里没有 %r（打进包的不是现代重构那一版？）' % (inner, needle)
print('[8] 新鲜度指纹：现代总成标识符 + %d 个剪辑名齐备' % CLIPS)

missing_cls, missing_sym = [], []
for inner, needles in SIGHT_CLASSES.items():
    if inner not in names:
        missing_cls.append(inner)
        continue
    blob = zf.read(inner)
    missing_sym += [(inner, n) for n in needles if n not in blob]
assert not missing_cls, 'jar 里没有这些类：%r' % missing_cls
assert not missing_sym, '类里没有这些符号：%r' % missing_sym
print('[9] 镜种进包：SightStyle 类 + 4 个类的自有符号齐备（透明镜真的编进去了）')
zf.close()

# ---------------------------------------------------------------- 3. 校验器门禁
rc, out = run_checker('check_crossbow_anim.py')
print(out.rstrip()[-1400:])
if rc != 0:
    sys.exit('check_crossbow_anim.py 未通过（exit %d）' % rc)
print('[10] check_crossbow_anim.py 全过（含透明镜契约 / 观感同源 / 弦道走廊 / 镜像 / 已知偏差）')

for script in ('check_gun_resources.py', 'check_awm_anim.py', 'check_mosin_anim.py',
               'check_m1_reload.py', 'check_gun_mobs.py'):
    rc, out = run_checker(script)
    if rc != 0:
        print(out.rstrip()[-1500:])
        sys.exit('%s 回归失败（exit %d）' % (script, rc))
print('[11] 其余 5 个枪械校验器回归通过')

# ---------------------------------------------------------------- 4. 部署
old_target = os.path.join(MODS, 'apocalypse_zombies-%s.jar' % OLD)
new_target = os.path.join(MODS, JAR)

# 先探锁：游戏运行中 jar 会被独占，宁可在这里清楚报错，也不要拷到一半失败
if os.path.isfile(old_target):
    try:
        with open(old_target, 'r+b'):
            pass
    except PermissionError:
        print()
        print('=== 1.1.36 构建完成，但**没有部署** ===')
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
print('[12] 部署前：其它模组 %d 个（将逐个断原样在位）' % len(before))

if os.path.isfile(old_target):
    bak = old_target + '.old.bak'
    if os.path.isfile(bak):
        os.remove(bak)
    os.rename(old_target, bak)
    print('[13] 旧包改名 %s -> %s' % (os.path.basename(old_target), os.path.basename(bak)))
else:
    print('[13] 旧包不在 mods 里（可能已改名），跳过')

shutil.copy2(jar, new_target)
assert md5(new_target) == new_md5, '部署后 md5 不一致（拷坏了）'

after = {}
for n in os.listdir(MODS):
    p = os.path.join(MODS, n)
    if os.path.isfile(p) and n.endswith('.jar') and not n.startswith(PREFIX):
        after[n] = md5(p)
assert before == after, '其它模组的 jar 被动过了！'
print('[14] 其它模组原样在位：%d 个 md5 全等' % len(after))

live = [n for n in os.listdir(MODS) if n.startswith(PREFIX) and n.endswith('.jar')]
assert live == [JAR], 'mods 里不该同时存在多个版本：%r' % (live,)
print('[15] mods 内唯一样本：%s' % live[0])

print()
print('=== 1.1.36 出货完成 ===')
print('    jar : %s' % JAR)
print('    md5 : %s' % new_md5)
print('    尺寸: %d 字节' % os.path.getsize(jar))
print('    内容是: 十字弩右键透明十字瞄准镜（方案 B：淡青镜片 + 细镜圈 + 双色十字）')
