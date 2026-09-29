# -*- coding: utf-8 -*-
"""1.1.30 出货：持枪怪近身切近战 + 走位射击 + 死亡标记 + 投掷怪免爆。

这一版全是「代码对、编译过、游戏里没反应」的类型，所以门禁比平时多：
先跑校验器（含变异测试），再用**构建产物内部**的字符串证明新代码真的进了 jar，
最后才动 mods 目录 —— 且只动 apocalypse_zombies-* 这一个前缀。

用法：python tools/_deploy_130.py
"""
import hashlib
import io
import os
import re
import shutil
import struct
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODS = 'C:/Users/Administrator/Desktop/.minecraft/versions/1.20.1-Forge_47.4.23-2/mods'
PROPS = os.path.join(ROOT, 'gradle.properties')

OLD_VERSION = '1.1.29'
NEW_VERSION = '1.1.30'
PREFIX = 'apocalypse_zombies-'

failures = []


def fail(message):
    failures.append(message)
    print('  [门禁] ✗', message)


def ok(message):
    print('  [门禁] ✓', message)


def decode(raw):
    return raw.decode('gbk', errors='replace')


def run(argv, label):
    print('--- %s' % label)
    proc = subprocess.run(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    text = decode(proc.stdout)
    tail = [line for line in text.splitlines() if line.strip()][-6:]
    for line in tail:
        print('     ', line)
    return proc.returncode, text


def md5(path):
    digest = hashlib.md5()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def png_size(blob):
    if blob[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    return struct.unpack('>II', blob[16:24])


print('=' * 70)
print('1.1.30 出货 —— 近身切近战 / 走位射击 / 死亡标记 / 投掷怪免爆')
print('=' * 70)

# ---------------------------------------------------------------- 0. 入口不变量
print('\n[0] 入口不变量：gradle.properties 必须还停在上一版')
with io.open(PROPS, encoding='utf-8', newline='') as handle:
    props = handle.read()
if 'mod_version=%s' % OLD_VERSION not in props:
    fail('gradle.properties 不是 %s（是不是上次出货没回退？）' % OLD_VERSION)
    sys.exit(1)
ok('mod_version = %s' % OLD_VERSION)

# ---------------------------------------------------------------- 1. 校验器
print('\n[1] 静态校验（含变异测试）')
for argv, label in (
        (['python', 'tools/check_melee_and_mark.py'], '近身/走位/标记/免爆 断言'),
        (['python', 'tools/check_melee_and_mark.py', '--selftest'], '变异测试'),
        (['python', 'tools/check_gun_mobs.py'], '枪械弹道表回归'),
        (['python', 'tools/check_ai_enhancements.py'], 'AI 增强回归'),
        (['python', 'tools/check_player_health.py'], '玩家血量回归'),
):
    code, _ = run(argv, label)
    if code != 0:
        fail('%s 未通过' % label)
    else:
        ok(label)
if failures:
    print('\n校验器阶段就不过，不构建。')
    sys.exit(1)

# ---------------------------------------------------------------- 2. 图标
print('\n[2] 死亡标记图标（重新生成 + 尺寸）')
code, _ = run(['python', 'tools/death_mark_icon.py'], '生成 18×18 图标')
icon = os.path.join(ROOT, 'src', 'main', 'resources', 'assets', 'apocalypse_zombies',
                    'textures', 'mob_effect', 'death_mark.png')
if code != 0 or not os.path.exists(icon):
    fail('图标没生成出来')
else:
    with open(icon, 'rb') as handle:
        size = png_size(handle.read(24))
    if size != (18, 18):
        fail('图标尺寸 %s，必须是 18×18' % (size,))
    else:
        ok('death_mark.png = 18×18')
if failures:
    sys.exit(1)

# ---------------------------------------------------------------- 3. 版本号
print('\n[3] 抬版本号 %s → %s' % (OLD_VERSION, NEW_VERSION))
bumped = props.replace('mod_version=%s' % OLD_VERSION, 'mod_version=%s' % NEW_VERSION, 1)
with io.open(PROPS, 'w', encoding='utf-8', newline='') as handle:
    handle.write(bumped)
ok('gradle.properties 已抬到 %s' % NEW_VERSION)

# ---------------------------------------------------------------- 4. 构建
print('\n[4] 构建（脚本自己跑，不信任旧产物）')
code, text = run(['gradlew.bat', 'build', '--console=plain'], 'gradlew build')
if 'BUILD SUCCESSFUL' not in text:
    fail('构建失败')
    for line in text.splitlines():
        if '错误' in line or 'error:' in line.lower():
            print('     !', line)
    sys.exit(1)
ok('BUILD SUCCESSFUL')

jar = os.path.join(ROOT, 'build', 'libs', '%s%s.jar' % (PREFIX, NEW_VERSION))
if not os.path.exists(jar):
    fail('没有产物 %s' % jar)
    sys.exit(1)
size = os.path.getsize(jar)
if size < 1_500_000:
    fail('产物只有 %d 字节，不像完整构建' % size)
ok('产物 %s（%d 字节）' % (os.path.basename(jar), size))

# ---------------------------------------------------------------- 5. jar 内部门禁
print('\n[5] jar 内部：新类、新资源、新代码（按自己的标识符证明新鲜度）')
with zipfile.ZipFile(jar) as archive:
    names = set(archive.namelist())

    for entry in ('com/apocalypse/zombies/effect/DeathMarkEffect.class',
                  'com/apocalypse/zombies/registry/ModEffects.class',
                  'com/apocalypse/zombies/event/DeathMarkHandler.class'):
        if entry not in names:
            fail('jar 里没有 %s' % entry)
        else:
            ok(entry.rsplit('/', 1)[1])

    icon_entry = 'assets/apocalypse_zombies/textures/mob_effect/death_mark.png'
    if icon_entry not in names:
        fail('jar 里没有图标 %s' % icon_entry)
    else:
        size_in_jar = png_size(archive.read(icon_entry))
        if size_in_jar != (18, 18):
            fail('jar 内图标尺寸 %s' % (size_in_jar,))
        else:
            ok('jar 内图标 18×18')

    manifest = archive.read('META-INF/mods.toml').decode('utf-8', errors='replace')
    if 'version="%s"' % NEW_VERSION not in manifest:
        fail('mods.toml 里的版本不是 %s' % NEW_VERSION)
    else:
        ok('mods.toml version = %s' % NEW_VERSION)

    # 只认「本次新引入、且属于本模组的」标识符 —— 覆写原版方法的改动骗不过这一条。
    # 铁律：不许钉原版名。生产 jar 被 SRG 重映射（isInvulnerableTo → m_6673_、
    # IS_EXPLOSION/DAMAGE_INDICATOR 之类原版名在 jar 里根本搜不到），
    # 钉原版名会永远判失败。所以原版调用点旁边必须有本模组自己的命名常量。
    fingerprints = (
        ('com/apocalypse/zombies/entity/GunAttackGoal.class', b'blindTicks',
         '走位射击的让位计数器'),
        ('com/apocalypse/zombies/entity/GunAttackGoal.class', b'strafeSign',
         '左右交替的侧移方向'),
        ('com/apocalypse/zombies/event/DeathMarkHandler.class', b'DEATH_MARK_MAX_STACKS',
         '死亡标记叠层上限（只在本类出现）'),
        ('com/apocalypse/zombies/registry/ModEffects.class', b'death_mark',
         '效果注册名'),
        ('com/apocalypse/zombies/entity/SoldierZombie.class', b'EXPLOSION_IMMUNITY',
         '爆炸免伤的分类常量'),
        ('com/apocalypse/zombies/effect/DeathMarkEffect.class', b'MARK_PARTICLE',
         '标记的挨打粒子常量'),
    )
    for entry, needle, why in fingerprints:
        if entry not in names:
            fail('jar 里没有 %s' % entry)
            continue
        if needle not in archive.read(entry):
            fail('%s 里没有 %r（%s）⇒ 这个改动没进 jar' % (entry.rsplit('/', 1)[1],
                                                       needle.decode(), why))
        else:
            ok('%s 内含 %s（%s）' % (entry.rsplit('/', 1)[1], needle.decode(), why))

if failures:
    print('\njar 门禁不过，不动 mods 目录。')
    sys.exit(1)

# ---------------------------------------------------------------- 6. 部署
print('\n[6] 部署到 mods（只动 %s 这一个前缀）' % PREFIX)
before = {}
for name in os.listdir(MODS):
    if name.endswith('.jar'):
        before[name] = md5(os.path.join(MODS, name))
others_before = {k: v for k, v in before.items() if not k.startswith(PREFIX)}
print('     部署前 mods 内 .jar %d 个（其中非本模组 %d 个）'
      % (len(before), len(others_before)))

old_jar = os.path.join(MODS, '%s%s.jar' % (PREFIX, OLD_VERSION))
if os.path.exists(old_jar):
    backup = old_jar + '.old.bak'
    if os.path.exists(backup):
        os.remove(backup)
    os.rename(old_jar, backup)
    ok('旧包 %s%s.jar → .old.bak' % (PREFIX, OLD_VERSION))
else:
    ok('没有旧包 %s%s.jar（已经改过名）' % (PREFIX, OLD_VERSION))

target = os.path.join(MODS, os.path.basename(jar))
shutil.copy2(jar, target)
ok('复制 %s' % os.path.basename(jar))

# ---------------------------------------------------------------- 7. 部署后断言
print('\n[7] 部署后断言（断「意图」，不是断「文件数」）')
live = sorted(name for name in os.listdir(MODS)
              if name.startswith(PREFIX) and name.endswith('.jar'))
if live != ['%s%s.jar' % (PREFIX, NEW_VERSION)]:
    fail('mods 里 %s 前缀的活包是 %s，预期恰好一个是 %s%s.jar'
         % (PREFIX, live, PREFIX, NEW_VERSION))
else:
    ok('mods 里唯一样本：%s' % live[0])

others_after = {}
for name in os.listdir(MODS):
    if name.endswith('.jar') and not name.startswith(PREFIX):
        others_after[name] = md5(os.path.join(MODS, name))
if others_after != others_before:
    fail('别的模组被动过了（部署前 %d 个 / 部署后 %d 个）'
         % (len(others_before), len(others_after)))
else:
    ok('另外 %d 个模组 md5 全部未变' % len(others_after))

deployed_md5 = md5(target)
if deployed_md5 != md5(jar):
    fail('复制到 mods 的 jar 与构建产物 md5 不一致')
else:
    ok('mods 内样本 md5 与产物一致')

print('\n' + '=' * 70)
if failures:
    print('出货失败：%d 条门禁不过' % len(failures))
    for item in failures:
        print('  -', item)
    sys.exit(1)
print('1.1.30 出货完成')
print('  产物：%s' % os.path.basename(jar))
print('  大小：%d 字节' % size)
print('  md5 ：%s' % deployed_md5)
print('  位置：%s' % target)
print('=' * 70)
