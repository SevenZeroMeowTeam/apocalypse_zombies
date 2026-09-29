# -*- coding: utf-8 -*-
"""1.1.27 出货：十字弩弓臂曲度 ↑（−0.30→−0.55）+ 展幅 +3%（4.42→4.55）+ 牙/箭道随动 +
Java 挂点常量同步（PULL_TRAVEL 1.85→1.95、CHANNEL −4.65→−5.30）。

断言重心：
  1. 版本号先落 gradle.properties，再由本脚本自己跑构建（不能反过来）。
  2. jar 内 mods.toml == 1.1.27（证明是新编译的）。
  3. CrossbowGeoModel.class 里 **有 1.95f、没有 1.85f**（Java 常量真的改进去了）。
  4. jar 内三个模型资源与 art/ 及 src/main/resources 逐字节相同（三处同步）。
  5. **镜像门禁**：四对左右部件 1:1 精确配对（2e-3 容差），集合非空先断言。
  6. x 包围盒对称（中心 0）+ 总宽落 60–65cm 带内。
  7. 布局签名：bolt_loaded 的 nock z == LATCH_Z == −4.10（牙后移真的生效）。
  8. 部署只动 apocalypse_zombies-* 前缀，其余模组逐个 md5 断「原样在位」。
"""
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODS = 'C:/Users/Administrator/Desktop/.minecraft/versions/1.20.1-Forge_47.4.23-2/mods'
OLD, NEW = '1.1.26', '1.1.27'
JAR = 'apocalypse_zombies-%s.jar' % NEW
PREFIX = 'apocalypse_zombies-'
LATCH_Z = -4.10
RES = {
    'assets/apocalypse_zombies/geo/crossbow.geo.json': 'art/crossbow/crossbow.geo.json',
    'assets/apocalypse_zombies/animations/crossbow.animation.json': 'art/crossbow/crossbow.animation.json',
    'assets/apocalypse_zombies/textures/models/crossbow.png': 'art/crossbow/crossbow.png',
}


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 16), b''):
            h.update(b)
    return h.hexdigest()


# ---------------------------------------------------------------- 1. 版本号 → 构建
gp = os.path.join(ROOT, 'gradle.properties')
with open(gp, 'r', encoding='utf-8', newline='') as fh:
    txt = fh.read()
assert 'mod_version=%s' % OLD in txt, 'gradle.properties 里不是 %s，先确认当前版本' % OLD
with open(gp, 'w', encoding='utf-8', newline='') as fh:
    fh.write(txt.replace('mod_version=%s' % OLD, 'mod_version=%s' % NEW))
print('[1] gradle.properties: %s -> %s' % (OLD, NEW))

print('[2] 构建中（gradlew.bat build）…')
r = subprocess.run([os.path.join(ROOT, 'gradlew.bat'), 'build', '--console=plain'],
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
names = zf.namelist()
assert 'META-INF/mods.toml' in names, 'jar 里没有 mods.toml'
toml = zf.read('META-INF/mods.toml').decode('utf-8', 'replace')
assert NEW in toml, 'mods.toml 里没有 %s —— jar 不是本次编译的' % NEW
print('[4] mods.toml 版本 = %s' % NEW)

cls = zf.read('com/apocalypse/zombies/client/model/CrossbowGeoModel.class')
assert struct.pack('>f', 1.95) in cls, 'CrossbowGeoModel.class 里没有 1.95f（PULL_TRAVEL 没进去）'
assert struct.pack('>f', 1.85) not in cls, 'CrossbowGeoModel.class 里还有 1.85f（改了没编译？）'
print('[5] Java 常量已进包：有 1.95f、无 1.85f')

for inside, art in RES.items():
    a = zf.read(inside)
    b = open(os.path.join(ROOT, art), 'rb').read()
    c = open(os.path.join(ROOT, 'src', 'main', 'resources', inside), 'rb').read()
    assert a == b, 'jar 内 %s 与 art/ 不一致' % inside
    assert a == c, 'jar 内 %s 与 src/main/resources 不一致' % inside
print('[6] 三个模型资源：jar == art == src 逐字节一致')

geo = json.loads(zf.read('assets/apocalypse_zombies/geo/crossbow.geo.json').decode('utf-8'))
B = {b['name']: b for b in geo['minecraft:geometry'][0]['bones']}


def raw(c):
    x, y, z = c['origin']
    sx, sy, sz = c['size']
    return (round(x, 3), round(y, 3), round(z, 3), round(sx, 3), round(sy, 3), round(sz, 3))


def mir(t):
    x, y, z, sx, sy, sz = t
    return (round(-(x + sx), 3), y, z, sx, sy, sz)


def close(p, q, tol=2e-3):
    return all(abs(u - v) <= tol for u, v in zip(p, q))


pairs = (('limb_l', 'limb_r', 9), ('cam_l', 'cam_r', 74), ('string_l', 'string_r', 2),
         ('cable_l', 'cable_r', 1))
for ln, rn, want in pairs:
    L = [raw(c) for c in B[ln]['cubes']]
    R = [raw(c) for c in B[rn]['cubes']]
    assert L and R, '断言集合非空：%s/%s 有一侧没有几何' % (ln, rn)
    assert len(L) == want and len(R) == want, '%s=%d %s=%d（期望各 %d）' % (ln, len(L), rn, len(R), want)
    used = set()
    for t in L:
        i = next((k for k, u in enumerate(R) if k not in used and close(mir(u), t)), None)
        assert i is not None, '%s 不成镜像：%r' % (ln, t)
        used.add(i)
    assert len(used) == len(R)
    print('[7] 镜像 %s/%s：%d 块 1:1 精确配对' % (ln, rn, len(L)))

xs = [c['origin'][0] for b in B.values() for c in b.get('cubes', [])]
xe = [c['origin'][0] + c['size'][0] for b in B.values() for c in b.get('cubes', [])]
lo, hi = min(xs), max(xe)
assert abs(lo + hi) < 2e-3, 'x 包围盒不对称（中心 %.4f）' % ((lo + hi) / 2.0)
w = hi - lo
assert 60.0 / 6.25 - 0.01 <= w <= 65.0 / 6.25 + 0.01, '总宽 %.2fu=%.1fcm 掉出 60–65cm 带' % (w, w * 6.25)
print('[8] x 包围盒 %.3f..%.3f 中心 %.4f，总宽 %.2fu = %.1fcm' % (lo, hi, (lo + hi) / 2.0, w, w * 6.25))

bolt = [raw(c) for c in B['bolt_loaded']['cubes']]
zmax = max(t[2] for t in bolt)
assert abs(zmax - LATCH_Z) < 1e-6, '箭矢尾端 z=%.3f，不等于 LATCH_Z=%.2f（牙没后移到位）' % (zmax, LATCH_Z)
print('[9] 布局签名：箭矢尾端 z = %.2f == LATCH_Z' % zmax)
zf.close()

# ---------------------------------------------------------------- 3. 部署
before = {}
for n in os.listdir(MODS):
    p = os.path.join(MODS, n)
    if os.path.isfile(p) and n.endswith('.jar') and not n.startswith(PREFIX):
        before[n] = md5(p)
print('[10] 部署前：其它模组 %d 个（将逐个断原样在位）' % len(before))

old_target = os.path.join(MODS, 'apocalypse_zombies-%s.jar' % OLD)
if os.path.isfile(old_target):
    bak = old_target + '.old.bak'
    if os.path.isfile(bak):
        os.remove(bak)
    os.rename(old_target, bak)
    print('[11] 旧包改名 %s -> %s' % (os.path.basename(old_target), os.path.basename(bak)))

shutil.copy2(jar, os.path.join(MODS, JAR))
deployed = os.path.join(MODS, JAR)
assert md5(deployed) == new_md5, '部署后 md5 不一致（拷坏了）'

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
print('=== 1.1.27 出货完成 ===')
print('    jar : %s' % JAR)
print('    md5 : %s' % new_md5)
print('    尺寸: %d 字节' % os.path.getsize(jar))
