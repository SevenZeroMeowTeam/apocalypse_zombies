# -*- coding: utf-8 -*-
"""1.1.35 出货：十字弩重构为「现代复合狩猎弩」（方案 A′）+ 预览工具符号缺陷修复。

用户逐字请求：
    这个弦的位置不对应该是向内不是向外        （附预览截图）

定性结论（详见 art/crossbow/DELIVERY.md §已知偏差 #10 与「预览工具符号约定复核」）：
  · **模型没错，错的是 tools/model_preview.py**。它照一条无出处的注释把动画 rotation 的
    x/y 取负 ⇒ 所有摆姿预览图前后/左右镜像，「弦被画到弓的前方（向外）」就是这么看出来的。
  · 取证：本机 geckolib-forge-1.20.1-4.8.4.jar 的 202 个类逐类 javap -c | grep fneg ——
    动画解析与写入路径一处取负都没有（仅 RenderUtils 对 position-x/pivot、ItemArmorGeoLayer
    转原版 ModelPart 取负；BakedAnimationsAdapter 里的 -1.0d 是 animation_length 缺省哨兵）。
  · 数据侧按世界坐标量：满弦时弓臂梢 x 4.63->4.37、z -7.67..-5.98 -> -7.21..-4.94（向内+向后收）、
    凸轮中心 z -6.20 -> -5.12、弦内端 (±0.011, 0.936, -3.399) = 挂机点前一弦厚 ⇒ 弦本来就是朝内走的。
  · 因此本轮 **不动模型一个字节**：art/ 与 src/ 的 geo/anim/png 三件套 md5 完全相同即以此为准。

本包的实质内容 = 自 1.1.34 之后累积的十字弩现代重构（现代勾爪总成、短托 + 拇指孔、垂直前握把、
脚踏环、长弯弓臂，几何断言 0.0u）以及工具链修复（model_preview 符号 + 新增 --selftest 守门人、
tools/crossbow_draw_diag.py 色标诊断）。

断言重心：
  1. 版本号先落 gradle.properties，再由本脚本自己跑构建（不许沿用旧产物）。
  2. jar 内 mods.toml == 1.1.35。
  3. **资产三向对账**：jar 内 crossbow 的 geo / animation / png 与 art/crossbow/ 的 md5 逐字节相同
     —— 这是本轮「没改模型」与「打进去的确是 art/ 那一版」的唯一硬证据。
  4. 新鲜度指纹：geo 里必须有自己的现代总成标识符（latch / bolt_loaded / camera），
     动画里必须有 7 个冻结剪辑名 —— 打进包的不是旧一代十字弩。
  5. tools/check_crossbow_anim.py 全过（契约 / Java 契约 / 音效 / 弦缆运动学 / 镜像 / 约定 /
     已知偏差），含弦道走廊零越界与爪前脸↔弦后脸 ≤0.05u 两条几何硬断言。
  6. 其余枪械校验器回归：gun_resources / awm_anim / mosin_anim / m1_reload / gun_mobs。
  7. 部署前探 jar 锁：游戏在跑就明确报错退出，绝不半路拷坏。
  8. 部署只动 apocalypse_zombies-* 前缀，其余模组逐个 md5 断「原样在位」。
"""
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODS = 'C:/Users/Administrator/Desktop/.minecraft/versions/1.20.1-Forge_47.4.23-2/mods'
OLD, NEW = '1.1.34', '1.1.35'
JAR = 'apocalypse_zombies-%s.jar' % NEW
PREFIX = 'apocalypse_zombies-'

RES = 'assets/apocalypse_zombies/'
# (jar 内路径, art/ 侧路径) —— 逐字节对账，本轮「没动模型」的硬证据
ASSETS = [
    (RES + 'geo/crossbow.geo.json', 'art/crossbow/crossbow.geo.json'),
    (RES + 'animations/crossbow.animation.json', 'art/crossbow/crossbow.animation.json'),
    (RES + 'textures/models/crossbow.png', 'art/crossbow/crossbow.png'),
]
EXTRA_PRESENT = [RES + 'models/item/crossbow.json']
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

missing = [p for p in EXTRA_PRESENT if p not in names]
assert not missing, 'jar 里缺：%r' % missing
print('[6] 物品模型 %s 在包内' % EXTRA_PRESENT[0].split('/')[-1])

for inner, needles in FINGERPRINTS.items():
    blob = zf.read(inner)
    for needle in needles:
        assert needle in blob, '%s 里没有 %r（打进包的不是现代重构那一版？）' % (inner, needle)
print('[7] 新鲜度指纹：现代总成标识符 + %d 个剪辑名齐备' % CLIPS)
zf.close()

# ---------------------------------------------------------------- 3. 校验器门禁
rc, out = run_checker('check_crossbow_anim.py')
print(out.rstrip()[-1200:])
if rc != 0:
    sys.exit('check_crossbow_anim.py 未通过（exit %d）' % rc)
print('[8] check_crossbow_anim.py 全过（含弦道走廊 / 爪前脸↔弦后脸 / 镜像 / 已知偏差）')

for script in ('check_gun_resources.py', 'check_awm_anim.py', 'check_mosin_anim.py',
               'check_m1_reload.py', 'check_gun_mobs.py'):
    rc, out = run_checker(script)
    if rc != 0:
        print(out.rstrip()[-1500:])
        sys.exit('%s 回归失败（exit %d）' % (script, rc))
print('[9] 其余 %d 个枪械校验器回归通过' % 5)

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
        print('=== 1.1.35 构建完成，但**没有部署** ===')
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
print('[10] 部署前：其它模组 %d 个（将逐个断原样在位）' % len(before))

if os.path.isfile(old_target):
    bak = old_target + '.old.bak'
    if os.path.isfile(bak):
        os.remove(bak)
    os.rename(old_target, bak)
    print('[11] 旧包改名 %s -> %s' % (os.path.basename(old_target), os.path.basename(bak)))
else:
    print('[11] 旧包不在 mods 里（可能已改名），跳过')

shutil.copy2(jar, new_target)
assert md5(new_target) == new_md5, '部署后 md5 不一致（拷坏了）'

after = {}
for n in os.listdir(MODS):
    p = os.path.join(MODS, n)
    if os.path.isfile(p) and n.endswith('.jar') and not n.startswith(PREFIX):
        after[n] = md5(p)
assert before == after, '其它模组的 jar 被动过了！'
print('[12] 其它模组原样在位：%d 个 md5 全等' % len(after))

live = [n for n in os.listdir(MODS) if n.startswith(PREFIX) and n.endswith('.jar')]
assert live == [JAR], 'mods 里不该同时存在多个版本：%r' % (live,)
print('[13] mods 内唯一样本：%s' % live[0])

print()
print('=== 1.1.35 出货完成 ===')
print('    jar : %s' % JAR)
print('    md5 : %s' % new_md5)
print('    尺寸: %d 字节' % os.path.getsize(jar))
print('    内容是: 十字弩现代复合重构（几何 0.0u 断言）+ 预览工具符号缺陷修复（弦朝内）')
