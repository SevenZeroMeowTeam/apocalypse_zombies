# -*- coding: utf-8 -*-
"""1.1.25 出货：头纱波浪扇贝下摆 + 玩家生命上限 100。

部署纪律（1.1.23 在这里出过事）：
  * **只动 `apocalypse_zombies-*` 前缀的包** —— mods 是共享目录，别人的包不属于我；
  * 断言断的是**意图**：我自己的版本唯一 + 其它模组的数量与名单一个不少；
  * 版本号改完**由本脚本自己跑构建**，避免再犯「先构建后改版本号」。

本次特有的两条硬断言：
  1. 生命上限的**固定 UUID 字面量**必须在 jar 的常量池里 —— 这条改动最狠的失效方式是
     UUID 变成随机值，每次登录叠一层（20 → 100 → 180），编译毫无异常；
  2. jar 里的头纱 geo 必须与 art/ 目录下刚生成的那份**逐字节相同** —— 否则就是
     「代码更新了、模型没进包」，进游戏还是直板下摆，而构建日志一切正常。
"""
import hashlib
import io
import os
import shutil
import subprocess
import zipfile

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODS = r"C:/Users/Administrator/Desktop/.minecraft/versions/1.20.1-Forge_47.4.23-2/mods"
PREFIX = 'apocalypse_zombies-'
OLD_VERSION = '1.1.24'
NEW_VERSION = '1.1.25'
GEO_ART = 'art/bride/bride_zombie.geo.json'
GEO_JAR = 'assets/apocalypse_zombies/geo/bride_zombie.geo.json'


def md5(path):
    return hashlib.md5(open(path, 'rb').read()).hexdigest()


# --- 1) 版本号（幂等） ---
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
log = proc.stdout
try:
    text = log.decode('gbk')          # gradle 日志是 GBK
except UnicodeDecodeError:
    text = log.decode('utf-8', 'replace')
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

# 3a) 本次改动的代码标识符（都是本项目自己的名字，不会被重混淆成 SRG）
for tag, needle in (('生命上限配置字段', b'PLAYER_MAX_HEALTH'),
                    ('生命上限配置键', b'player_max_health'),
                    ('套用生命上限的方法', b'applyPlayerHealth'),
                    ('生命修饰符 UUID 字面量', b'7f4a2c81-9e35-4d6b-8c10-2a5e6b3f9d47'),
                    ('上一版的子弹实体', b'BulletProjectile')):
    state = '命中' if needle in blob else '缺失'
    print('  %-22s %s' % (tag, state))
    assert needle in blob, '%s 不在包里，产物不是新编译的' % tag

# 3b) 模型资源必须与刚生成的那份一致（"代码更新了、模型没进包"是本项目的老坑）
art_geo = open(GEO_ART, 'rb').read()
assert GEO_JAR in zf.namelist(), 'jar 里没有 %s' % GEO_JAR
jar_geo = zf.read(GEO_JAR)
print('  geo art/ md5 =', hashlib.md5(art_geo).hexdigest())
print('  geo jar  md5 =', hashlib.md5(jar_geo).hexdigest())
assert art_geo == jar_geo, 'jar 里的头纱 geo 与 art/ 下不是同一份 —— 模型没进包'

import json

g = json.loads(jar_geo.decode('utf-8'))['minecraft:geometry'][0]
bones = g['bones']
cubes = [c for b in bones for c in b.get('cubes', [])]
print('  geo 骨骼 %d / 体块 %d' % (len(bones), len(cubes)))
assert len(bones) == 49, '骨骼数变了（%d != 49）：下摆应挂在既有 veil4 骨上，不该新增骨骼' % len(bones)
assert len(cubes) == 149, '体块数不是 149（直板下摆那份是 140）'
# 下摆扇贝的坐标签名：只数**头纱那一层**（z 起点 4.2、厚度 1.2）里
# y0 = 19.6-0.4 与 19.6-1.2 的方块，正好 6 + 3 = 9 块。
# 不能对全模型按 y 分桶 —— 裙摆和腿脚也有 y0 落在 18.4/19.2 的方块。
hem = [c for c in cubes
       if abs(c['origin'][2] - 4.2) < 1e-6 and abs(c['size'][2] - 1.2) < 1e-6
       and c['origin'][1] < 19.6]
ys = {}
for c in hem:
    ys[round(c['origin'][1], 2)] = ys.get(round(c['origin'][1], 2), 0) + 1
print('  下摆齿（头纱层内）y0=19.2 ->%d 块, y0=18.4 ->%d 块' % (ys.get(19.2, 0), ys.get(18.4, 0)))
assert len(hem) == 9, '下摆齿不是 9 块：%d' % len(hem)
assert ys.get(19.2, 0) == 6, '0.4u 短齿不是 6 块：%d' % ys.get(19.2, 0)
assert ys.get(18.4, 0) == 3, '1.2u 长齿不是 3 块：%d' % ys.get(18.4, 0)
assert min(c['origin'][1] for c in hem) == 18.4, '下摆最低点不是 18.4'
print('  OK jar 内的头纱是带波浪扇贝下摆的那一版（最低点 18.4u）')

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

build_md5, mods_md5 = md5(jar), md5(os.path.join(MODS, os.path.basename(jar)))
print('build/libs md5 =', build_md5)
print('mods     md5 =', mods_md5)
assert build_md5 == mods_md5, '部署后 md5 不一致（可能被游戏占用，需完全重启后再部署）'
assert mine == [os.path.basename(jar)], '生效版本不唯一：%s' % mine
assert after_others == others, '其它模组被动过了！before=%s after=%s' % (others, after_others)
print('OK 已部署 %s；其它 %d 个模组原样在位。' % (os.path.basename(jar), len(after_others)))
