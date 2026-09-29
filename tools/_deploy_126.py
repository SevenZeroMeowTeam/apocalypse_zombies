# -*- coding: utf-8 -*-
"""1.1.26 出货：十字弩左右凸轮/弓臂改成**精确镜像**（修「模型不完整、错位」）。

本次**没有任何 Java 改动**，只重生成三个模型资源（geo / animation / png），
因此断言重心全部压在模型上：

  1. **镜像门禁（本次的核心断言）** —— 四对左右部件必须逐块成精确镜像。
     改前：凸轮 74 块里有 46 块找不到镜像对应、最大偏 0.14u（左 x 起点 −4.905 vs
     右 −5.045，块尺寸 0.292 vs 0.096）⇒ 两个凸轮根本是两个形状；弓臂也有 6/9 块对不上。
     根因：`cam_wheel()` 的偏心半径 r = CAM_R0 + CAM_DR·cos(a) 在 a=0° 取极大，
     鼓包**恒指向 +x**，于是右轮朝外（对）、左轮朝内（错），弦槽凸榫/缆柱/辐条
     也全按绝对角度摆放 —— 左右是「平移副本」而不是镜像。
     修法：`mirror_side(src, dst)` 把右侧几何按 x=0 平面精确镜像到左侧。

  2. **整机 x 包围盒必须对称**（中心 0.000）。改前 −4.91..+5.04 中心偏 0.065u，
     就是「错位」的量化形态。

  3. **总宽必须落进参考图给的 60~65cm**（1u=6.25cm）。改前 9.11u=57cm（README §6.2
     自己记为已知偏差），镜像后 10.09u≈63.1cm —— 顺带修掉了那条偏差。

  4. **动画必须逐字节未变** —— 这次是几何修复，一旦动画被动过就说明改错了地方
     （静止剪辑/动作剪辑一个字都不该变）。

部署纪律（1.1.23 在这里出过事）：只动 `apocalypse_zombies-*` 前缀的包；断言断「意图」
（我自己的版本唯一 + 其它模组数量与名单一个不少）；版本号改完由脚本自己跑构建。
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import zipfile

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODS = r"C:/Users/Administrator/Desktop/.minecraft/versions/1.20.1-Forge_47.4.23-2/mods"
PREFIX = 'apocalypse_zombies-'
OLD_VERSION = '1.1.25'
NEW_VERSION = '1.1.26'
GEO_ART = 'art/crossbow/crossbow.geo.json'
GEO_JAR = 'assets/apocalypse_zombies/geo/crossbow.geo.json'
ANIM_ART = 'art/crossbow/crossbow.animation.json'
ANIM_JAR = 'assets/apocalypse_zombies/animations/crossbow.animation.json'
BAK_ANIM = 'art/crossbow/_bak_before_fix/crossbow.animation.json'
SIDES = (('limb_l', 'limb_r', 9), ('cam_l', 'cam_r', 74),
         ('string_l', 'string_r', 2), ('cable_l', 'cable_r', 1))


def md5(data):
    return hashlib.md5(data).hexdigest()


# --- 0) 先做模型侧门禁（构建前就该全绿）---
geo_art = open(GEO_ART, 'rb').read()
anim_art = open(ANIM_ART, 'rb').read()
g = json.loads(geo_art.decode('utf-8'))['minecraft:geometry'][0]
B = {b['name']: b for b in g['bones']}
allc = [c for b in g['bones'] for c in b.get('cubes', [])]


def raw(c):
    x, y, z = c['origin']
    sx, sy, sz = c['size']
    return (round(x, 3), round(y, 3), round(z, 3), round(sx, 3), round(sy, 3), round(sz, 3))


def mir_raw(t):
    """把「已取出的原始元组」按 x=0 平面镜像。"""
    x, y, z, sx, sy, sz = t
    return (round(-(x + sx), 3), y, z, sx, sy, sz)


def close(t1, t2, tol=2e-3):
    return all(abs(a - b) <= tol for a, b in zip(t1, t2))


try:                                   # 仓库 .py 是 CRLF，按二进制比就对了
    assert anim_art == open(BAK_ANIM, 'rb').read(), '动画被改动了！本次是纯几何修复'
except IOError:
    print('  （没有动画基线可比，跳过）')
print('  动画与改前基线逐字节一致 OK')

# 逐块一对一配对（严格双射）。不能按 3 位小数的集合差判 —— 生成器按 4 位小数写盘，
# 镜像要算 -(x+sx)，末位会差 0.001，集合比较会误报。
for ln, rn, expect in SIDES:
    lc = [raw(c) for c in B.get(ln, {}).get('cubes', [])]
    rc = [raw(c) for c in B.get(rn, {}).get('cubes', [])]
    assert lc, '%s 没有几何（空集合上的“镜像通过”是假通过）' % ln
    assert rc, '%s 没有几何' % rn
    assert len(lc) == expect and len(rc) == expect, \
        '%s/%s 块数不是 %d：%d/%d' % (ln, rn, expect, len(lc), len(rc))
    used, bad = set(), []
    for t in lc:
        hit = next((i for i, u in enumerate(rc)
                    if i not in used and close(mir_raw(u), t)), None)
        if hit is None:
            bad.append(t)
        else:
            used.add(hit)
    print('  %-9s(%3d) vs %-9s(%3d)  配对 %d/%d，不成镜像 %d 块'
          % (ln, len(lc), rn, len(rc), len(used), len(rc), len(bad)))
    for t in bad[:3]:
        print('     对不上:', t)
    assert not bad and len(used) == len(rc), \
        '%s 与 %s 不成精确镜像（%d 块对不上）' % (ln, rn, len(bad))

xs = [x for c in allc for x in (c['origin'][0], c['origin'][0] + c['size'][0])]
lo, hi = min(xs), max(xs)
print('  整机 x 包围盒 %.3f .. %.3f  中心 %.3f  宽 %.3fu = %.1fcm'
      % (lo, hi, (lo + hi) / 2.0, hi - lo, (hi - lo) * 6.25))
assert abs(lo + hi) < 2e-3, 'x 包围盒不对称（中心 %.4f）—— 正是“错位”的量化形态' % ((lo + hi) / 2.0)
assert 9.6 - 1e-6 <= hi - lo <= 10.4 + 1e-6, '总宽 %.2fu 不在参考要求的 60~65cm 内' % (hi - lo)
print('  方块 %d / 骨 %d' % (len(allc), len(B)))
assert len(allc) == 501 and len(B) == 21, '体块/骨骼数与基线不符：%d/%d' % (len(allc), len(B))

# 静止剪辑的通道集合必须原样（5 条：body/move/scope/hand_l/bolt_loaded）
anim = json.loads(anim_art.decode('utf-8'))['animations']
idle_ch = set()
for b, ch in anim['static_idle']['bones'].items():
    for k in ch:
        idle_ch.add('%s.%s' % (b, k))
assert idle_ch == {'body.rotation', 'bolt_loaded.scale', 'hand_l.scale',
                   'move.position', 'scope.rotation'}, '静止剪辑通道变了：%s' % sorted(idle_ch)
print('  静止剪辑 5 条通道未变 OK；剪辑共 %d 段' % len(anim))

# --- 1) 版本号（幂等）---
gp = 'gradle.properties'
props = io.open(gp, encoding='utf-8', newline='').read()
if 'mod_version=%s' % NEW_VERSION in props:
    print('版本已是 %s（幂等跳过）' % NEW_VERSION)
else:
    assert 'mod_version=%s' % OLD_VERSION in props, 'gradle.properties 版本不是 %s' % OLD_VERSION
    io.open(gp, 'w', encoding='utf-8', newline='').write(
        props.replace('mod_version=%s' % OLD_VERSION, 'mod_version=%s' % NEW_VERSION))
    print('版本 %s -> %s' % (OLD_VERSION, NEW_VERSION))

# --- 2) 构建 ---
proc = subprocess.run(['gradlew.bat', 'build', '--console=plain'], stdout=subprocess.PIPE,
                      stderr=subprocess.STDOUT)
try:
    text = proc.stdout.decode('gbk')
except UnicodeDecodeError:
    text = proc.stdout.decode('utf-8', 'replace')
if proc.returncode != 0:
    for line in text.splitlines():
        if 'error:' in line or '错误:' in line:
            print(' ', line.strip()[:180])
    raise SystemExit('构建失败，未部署')
print('BUILD SUCCESSFUL')

# --- 3) 产物校验 ---
jar = 'build/libs/apocalypse_zombies-%s.jar' % NEW_VERSION
assert os.path.exists(jar), '没有构建产物 ' + jar
zf = zipfile.ZipFile(jar)
blob = b''.join(zf.read(n) for n in zf.namelist() if n.endswith('.class'))
for tag, needle in (('十字弩物品类', b'CrossbowItem'),
                    ('十字弩几何模型类', b'CrossbowGeoModel'),
                    ('第一人称手臂系统', b'WeaponHandGrip')):
    assert needle in blob, '%s 不在包里，产物不是新编译的' % tag
    print('  %-18s 命中' % tag)
# 「新编译」的铁证：jar 内 mods.toml 的版本号必须是本版
toml = [n for n in zf.namelist() if n.endswith('mods.toml')]
assert toml, 'jar 里没有 mods.toml'
head = zf.read(toml[0]).decode('utf-8', 'replace')
assert NEW_VERSION in head, 'jar 内 mods.toml 不是 %s，产物不是新编译的' % NEW_VERSION
print('  mods.toml 版本 = %s OK' % NEW_VERSION)
for name, art in ((GEO_JAR, geo_art), (ANIM_JAR, anim_art)):
    assert name in zf.namelist(), 'jar 里没有 %s' % name
    jar_bytes = zf.read(name)
    print('  %-52s art md5 %s' % (name, md5(art)))
    assert jar_bytes == art, '%s 不是 art/ 下刚生成的那份 —— 模型没进包' % name
print('  OK jar 内的 geo/animation 与 art/ 下逐字节相同')

# --- 4) 部署：只碰自己的包 ---
before = sorted(f for f in os.listdir(MODS) if f.endswith('.jar'))
others = [f for f in before if not f.startswith(PREFIX)]
print('部署前 mods 内 jar：共 %d 个，其中其它模组 %d 个' % (len(before), len(others)))
for name in before:
    if name.startswith(PREFIX):
        shutil.move(os.path.join(MODS, name), os.path.join(MODS, name + '.old.bak'))
        print('  自己旧版本停用 ->', name + '.old.bak')
shutil.copy2(jar, os.path.join(MODS, os.path.basename(jar)))

after = sorted(f for f in os.listdir(MODS) if f.endswith('.jar'))
after_others = [f for f in after if not f.startswith(PREFIX)]
mine = [f for f in after if f.startswith(PREFIX)]
build_md5 = md5(open(jar, 'rb').read())
mods_md5 = md5(open(os.path.join(MODS, os.path.basename(jar)), 'rb').read())
print('build/libs md5 =', build_md5)
print('mods     md5 =', mods_md5)
assert build_md5 == mods_md5, '部署后 md5 不一致（可能被游戏占用，需完全重启后再部署）'
assert mine == [os.path.basename(jar)], '生效版本不唯一：%s' % mine
assert after_others == others, '其它模组被动过了！before=%s after=%s' % (others, after_others)
print('OK 已部署 %s；其它 %d 个模组原样在位。' % (os.path.basename(jar), len(after_others)))
