# -*- coding: utf-8 -*-
"""1.1.32 出货：美女僵尸全身位移复标定（动作不再只靠旋转撑着）。

这一版的坑都藏在「编译过、日志干净、游戏里看不出」的地方：
  * `EliteAbility` 走 ordinal 联网同步 ⇒ 新值插在中间会让别的精英施法状态错位；
  * 轮转被距离条件卡死 ⇒ 她在远处一个技能都不放（本轮专门加了跳过兜底）；
  * 投掷物误关重力 ⇒ 抛物线变直线，可躲性消失；
  * 少了渲染器 / 贴图 / lang ⇒ 客户端一个紫黑方块。
所以门禁是：先跑校验器（含变异测试）→ 生成器自校验 → 构建 → 用**产物内部**的
本模组标识符证明新代码真进了 jar → 最后才动 mods，且只动 apocalypse_zombies-* 一个前缀。

用法：python tools/_deploy_131.py
"""
import hashlib
import json
import io
import os
import shutil
import struct
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODS = 'C:/Users/Administrator/Desktop/.minecraft/versions/1.20.1-Forge_47.4.23-2/mods'
PROPS = os.path.join(ROOT, 'gradle.properties')
RES = os.path.join(ROOT, 'src', 'main', 'resources', 'assets', 'apocalypse_zombies')

OLD_VERSION = '1.1.31'
NEW_VERSION = '1.1.32'
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
print('1.1.32 出货 —— 美女僵尸：全身位移复标定（垫步/下跪/呼吸真的移动了）')
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
        (['python', 'tools/check_bride_combat.py'], '近战/远程两套技能断言'),
        (['python', 'tools/check_bride_combat.py', '--selftest'], '变异测试'),
        (['python', 'tools/check_gun_mobs.py'], '枪械弹道表回归'),
        (['python', 'tools/check_melee_and_mark.py'], '近身/走位/标记/免爆回归'),
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

# ---------------------------------------------------------------- 2. 几何 / 图集 / 剪辑（生成器是唯一出口）
print('\n[2] 生成器复跑（geo + 动画 + 图集 + 剪辑校验）')
for argv, label in (
        (['python', 'tools/bride_v2.py'], '几何 + 动画生成（含 1522 项自校验）'),
        (['python', 'tools/bride_v2_skin.py'], '512×512 图集生成'),
        (['python', 'tools/bride_clip_check.py'], '剪辑通道/时长校验'),
):
    code, _ = run(argv, label)
    if code != 0:
        fail('%s 未通过' % label)
    else:
        ok(label)

# 新写的 .java 不许带 UTF-8 BOM（带 BOM 会让 javac 在中文注释上报错）
bom = []
for base, _dirs, files in os.walk(os.path.join(ROOT, 'src')):
    for name in files:
        if name.endswith('.java'):
            path = os.path.join(base, name)
            with open(path, 'rb') as handle:
                if handle.read(3) == b'\xef\xbb\xbf':
                    bom.append(os.path.relpath(path, ROOT))
if bom:
    fail('这些 .java 带 UTF-8 BOM：%s' % ', '.join(bom))
else:
    ok('全仓库 .java 无 BOM')

# ---------------------------------------------------------------- 3. 贴图
print('\n[3] 花束投掷物贴图（16×16）')
texture = os.path.join(RES, 'textures', 'item', 'bouquet_dart.png')
if not os.path.exists(texture):
    fail('没有 %s' % texture)
else:
    with open(texture, 'rb') as handle:
        size = png_size(handle.read(24))
    if size != (16, 16):
        fail('贴图尺寸 %s，必须 16×16' % (size,))
    else:
        ok('bouquet_dart.png = 16×16（%d 字节）' % os.path.getsize(texture))
if failures:
    sys.exit(1)

# ---------------------------------------------------------------- 4. 版本号
print('\n[4] 抬版本号 %s → %s' % (OLD_VERSION, NEW_VERSION))
bumped = props.replace('mod_version=%s' % OLD_VERSION, 'mod_version=%s' % NEW_VERSION, 1)
with io.open(PROPS, 'w', encoding='utf-8', newline='') as handle:
    handle.write(bumped)
ok('gradle.properties 已抬到 %s' % NEW_VERSION)

# ---------------------------------------------------------------- 5. 构建
print('\n[5] 构建（脚本自己跑，不信任旧产物）')
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

# ---------------------------------------------------------------- 6. jar 内部门禁
print('\n[6] jar 内部：新类、新资源、新代码（按自己的标识符证明新鲜度）')
with zipfile.ZipFile(jar) as archive:
    names = set(archive.namelist())

    for entry in ('com/apocalypse/zombies/entity/BouquetProjectile.class',):
        if entry not in names:
            fail('jar 里没有 %s' % entry)
        else:
            ok(entry.rsplit('/', 1)[1])

    icon_entry = 'assets/apocalypse_zombies/textures/item/bouquet_dart.png'
    if icon_entry not in names:
        fail('jar 里没有贴图 %s' % icon_entry)
    else:
        size_in_jar = png_size(archive.read(icon_entry))
        if size_in_jar != (16, 16):
            fail('jar 内花束贴图尺寸 %s' % (size_in_jar,))
        else:
            ok('jar 内花束贴图 16×16')

    model_entry = 'assets/apocalypse_zombies/models/item/bouquet_dart.json'
    if model_entry not in names:
        fail('jar 里没有物品模型 %s' % model_entry)
    else:
        ok('物品模型 bouquet_dart.json')

    # 两段新剪辑必须真的进包 —— 几何/动画没更新的话，技能会「放出来但不动」
    anim_entry = 'assets/apocalypse_zombies/animations/bride_zombie.animation.json'
    if anim_entry not in names:
        fail('jar 里没有动画表 %s' % anim_entry)
    else:
        anim = archive.read(anim_entry)
        for clip, length in ((b'skill_veil_swipe', b'2.0'), (b'skill_flower_dart', b'1.8')):
            if clip not in anim:
                fail('jar 内动画表没有剪辑 %s' % clip.decode())
            elif b'"animation_length": ' + length not in anim and \
                    b'"animation_length":' + length not in anim:
                fail('jar 内 %s 的 animation_length 不是 %s' % (clip.decode(), length.decode()))
            else:
                ok('jar 内剪辑 %s（%ss）' % (clip.decode(), length.decode()))

        # 位移复标定必须进包：这几个振幅就是「动作不再只靠旋转撑着」的直接证据
        doc = json.loads(anim.decode('utf-8'))
        for clip, axis, want, why in (
                ('skill_veil_swipe', 2, 8.0, '近战垫步进身半格'),
                ('skill_veil_swipe', 0, 2.5, '转体横移'),
                ('skill_bridal_kiss', 2, 6.0, '拉近去吻'),
                ('skill_sacrifice', 1, 5.0, '真的跪下去'),
                ('idle', 1, 0.9, '呼吸起伏'),
        ):
            frames = doc['animations'][clip]['bones']['move']['position']
            peak = 0.0
            for frame in frames.values():
                vec = (frame.get('post') or frame.get('pre') or {}).get('vector') or []
                if len(vec) > axis and isinstance(vec[axis], (int, float)):
                    peak = max(peak, abs(vec[axis]))
            if abs(peak - want) > 1e-3:
                fail('jar 内 %s 的位移振幅 %.3f，应为 %.3f（%s 没进包）'
                     % (clip, peak, want, why))
            else:
                ok('jar 内 %s 位移振幅 %.2fu（%s）' % (clip, peak, why))

    manifest = archive.read('META-INF/mods.toml').decode('utf-8', errors='replace')
    if 'version="%s"' % NEW_VERSION not in manifest:
        fail('mods.toml 里的版本不是 %s' % NEW_VERSION)
    else:
        ok('mods.toml version = %s' % NEW_VERSION)

    # 只认「本次新引入、且属于本模组的」标识符。
    # 铁律：不许钉原版名 —— 生产 jar 被 SRG 重映射，原版字段/方法名在 jar 里搜不到。
    fingerprints = (
        ('com/apocalypse/zombies/entity/BrideZombie.class', b'ROTATION_SKIP_TICKS',
         '轮转跳过兜底（只在本类出现）'),
        ('com/apocalypse/zombies/entity/BrideZombie.class', b'SWIPE_HALF_ANGLE',
         '近战扇区半角常量'),
        ('com/apocalypse/zombies/entity/BrideZombie.class', b'DART_ARC_LIFT',
         '远程按距离抬瞄的常量'),
        ('com/apocalypse/zombies/entity/BrideZombie.class', b'skill_veil_swipe',
         '近战剪辑名'),
        ('com/apocalypse/zombies/entity/BrideZombie.class', b'skill_flower_dart',
         '远程剪辑名'),
        ('com/apocalypse/zombies/entity/BouquetProjectile.class', b'IMPACT_DAMAGE',
         '花束命中伤害常量'),
        ('com/apocalypse/zombies/entity/BouquetProjectile.class', b'POISON_TICKS',
         '花束中毒时长常量'),
        ('com/apocalypse/zombies/entity/EliteAbility.class', b'FLOWER_DART',
         '枚举新值（末尾追加）'),
        ('com/apocalypse/zombies/registry/ModEntities.class', b'bouquet_projectile',
         '实体注册名'),
        ('com/apocalypse/zombies/registry/ModItems.class', b'bouquet_dart',
         '物品注册名'),
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

# ---------------------------------------------------------------- 7. 部署
print('\n[7] 部署到 mods（只动 %s 这一个前缀）' % PREFIX)
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
# 游戏开着的话旧包会被锁住 —— 这里显式探一次，别把异常丢给 copy2 的堆栈
try:
    with open(target, 'a+'):
        pass
except OSError as exc:
    fail('mods 里的目标包被占用（游戏还开着？）：%s' % exc)
    sys.exit(1)
shutil.copy2(jar, target)
ok('复制 %s' % os.path.basename(jar))

# ---------------------------------------------------------------- 8. 部署后断言
print('\n[8] 部署后断言（断「意图」，不是断「文件数」）')
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
print('1.1.32 出货完成')
print('  产物：%s' % os.path.basename(jar))
print('  大小：%d 字节' % size)
print('  md5 ：%s' % deployed_md5)
