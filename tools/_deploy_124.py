# -*- coding: utf-8 -*-
"""1.1.24 出货：版本号 + 构建产物校验 + 部署。

部署纪律（上一次就是在这里出的事）：
  * **只动 `apocalypse_zombies-*` 前缀的包** —— mods 是共享目录，别人的包不属于我；
  * 断言断的是**意图**：我自己的版本唯一 + 其它模组的数量与名单一个不少，
    而不是「目录里只剩我的包」那种把 bug 当验收条件的写法。
"""
import hashlib
import io
import os
import re
import shutil
import zipfile

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODS = r"C:/Users/Administrator/Desktop/.minecraft/versions/1.20.1-Forge_47.4.23-2/mods"
PREFIX = 'apocalypse_zombies-'
OLD_VERSION = '1.1.23'
NEW_VERSION = '1.1.24'


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

# --- 2) 构建（放在改完版本号之后自己跑，顺序就不会再错） ---
import subprocess

proc = subprocess.run(['gradlew.bat', 'build', '--console=plain'], stdout=subprocess.PIPE,
                      stderr=subprocess.STDOUT)
log = proc.stdout
try:
    text = log.decode('gbk')          # gradle 日志是 GBK，直接 utf-8 会炸
except UnicodeDecodeError:
    text = log.decode('utf-8', 'replace')
if proc.returncode != 0:
    for line in text.splitlines():
        if 'error:' in line or '错误:' in line:
            print(' ', line.strip()[:180])
    raise SystemExit('构建失败，未部署')
print('BUILD SUCCESSFUL')

# --- 3) 产物校验：我自己写的标识符必须在包里 ---
jar = 'build/libs/apocalypse_zombies-%s.jar' % NEW_VERSION
assert os.path.exists(jar), '没有构建产物 ' + jar
blob = b''.join(zipfile.ZipFile(jar).read(n) for n in zipfile.ZipFile(jar).namelist()
                if n.endswith('.class'))
for tag, needle in (('子弹实体', b'BulletProjectile'),
                    ('开火 Goal', b'GunAttackGoal'),
                    ('怪物弹道表', b'GunProfile'),
                    ('配枪事件类', b'GunArmedMobs'),
                    ('精英配枪配置键', b'elite_gun_chance'),
                    ('普通僵尸配枪配置键', b'zombie_gun_chance')):
    state = '命中' if needle in blob else '缺失'
    print('  %-18s %s' % (tag, state))
    # 覆盖原版方法的坑在这里不适用：上面全是本项目自己的标识符，不会被重混淆
    assert needle in blob, '%s 不在包里，产物不是新编译的' % tag

# --- 3) 部署：只碰自己的包 ---
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
# 断「意图」：我的版本唯一，别人的一个不少（不是「目录里只剩我的包」）
assert mine == [os.path.basename(jar)], '生效版本不唯一：%s' % mine
assert after_others == others, '其它模组被动过了！before=%s after=%s' % (others, after_others)
print('OK 已部署 %s；其它 %d 个模组原样在位。' % (os.path.basename(jar), len(after_others)))
