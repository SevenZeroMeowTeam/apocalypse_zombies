# -*- coding: utf-8 -*-
"""1.1.34 出货：修掉「美女僵尸不会攻击村民 / 铁傀儡 / 玩家」的目标死锁。

用户逐字请求：
    修复美女僵尸不会攻击村民，铁傀儡，玩家的问题
    她站在村民/铁傀儡旁边完全不动、既不放技能也不近战 → 这是我 dev 环境复现不出的另一种卡死

缺陷与修法（运行时取证见 tools/bride_aggro_probe.py --scenario perch）：

  · 现场：她锁上「看得见但走不到」的东西（柱顶村民 / 飞在天上的玩家）之后，目标表的
    TARGET 标志位被占死 —— 技能起手要视线、近战要距离、原版那三条目标（玩家 2 / 村民 3 /
    铁傀儡 3）全都起不来 ⇒ 站在村民/铁傀儡旁边一动不动。判据：修前冻结期受害者 0.0 伤害，
    修后 65.0（她照打 6 格外的铁傀儡）。
  · 根因：原版 TargetGoal 每 tick 把目标钉回去（setTarget），且 mustSee=false 只关掉
    「锁定后复检视线」、mustReach=false 连可达性都不查 ⇒ 锁上就永不放手；而原来的
    ScentTargetGoal 挂在 p0、两个参数也全是 false，会锁着够不着的玩家把整张表饿死。
  · 修法：删掉 ScentTargetGoal，换成 p0 之下的 PreyTargetGoal（优先级 1，在同伴传仇恨 0
    之下、原版玩家 2 之上）：按原版偏好顺序只在「用得上」的候选里选（用得上 = 走得到，
    判据 PreyJudge，补了原版没有的高度比较），没有可用猎物时占着 TARGET 但把目标置空。
    SharedAggroGoal 用同一套判据复核传给同伴的目标。
  · 特性不许修坏：目标失去视线但**走得到**时必须继续追（原设计的「隔墙摸过来」）——
    判据 `--scenario hide`：砌墙断视线后仍打 20.0。

断言重心：
  1. 版本号先落 gradle.properties，再由本脚本自己跑构建（不许沿用旧产物）。
  2. jar 内 mods.toml == 1.1.34。
  3. PreyJudge / PreyTargetGoal 进包，且 ScentTargetGoal **不在包里**（死锁源必须消失）。
  4. 新鲜度指纹：PreyTargetGoal 里有 canPathTo、SharedAggroGoal 里有 PreyJudge + usable。
  5. tools/check_ai_enhancements.py --selftest 全绿（含 14 条变异测试，5 条专钉本轮修法）。
  6. tools/check_bride_combat.py 回归（美女僵尸的技能幅度不受本轮影响）。
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
OLD, NEW = '1.1.33', '1.1.34'
JAR = 'apocalypse_zombies-%s.jar' % NEW
PREFIX = 'apocalypse_zombies-'

PKG = 'com/apocalypse/zombies/'
NEW_CLASSES = [
    'entity/ai/PreyJudge.class',
    'entity/ai/PreyTargetGoal.class',
]
# 死锁源：必须已经从包里消失
GONE_CLASSES = ['entity/ai/ScentTargetGoal.class']
# 新鲜度指纹：类文件里必须出现这些「自己的标识符」，证明打进包的是本轮编译结果
FINGERPRINTS = {
    'event/MobAiEnhanced.class': [b'PreyTargetGoal', b'apocalypse_ai_range'],
    'entity/ai/PreyTargetGoal.class': [b'anyPrey', b'PreyJudge'],
    # 只钉**自己的**标识符：Minecraft 的方法名会被 SRG 重映射掉（createPath -> m_XXXX_），
    # 打进包的原版名一个都不会在，钉了必然误报。
    'entity/ai/PreyJudge.class': [b'canPathTo', b'usable'],
    'entity/ai/SharedAggroGoal.class': [b'PreyJudge', b'usable'],
}


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

missing = [c for c in NEW_CLASSES if (PKG + c) not in names]
assert not missing, 'jar 里缺这些新类：%r' % missing
stale = [c for c in GONE_CLASSES if (PKG + c) in names]
assert not stale, '死锁源还在包里：%r（ScentTargetGoal 必须已被 PreyTargetGoal 取代）' % stale
print('[5] 新类 %d 个在包内；旧死锁源 %d 个已消失' % (len(NEW_CLASSES), len(GONE_CLASSES)))

for rel, needles in FINGERPRINTS.items():
    blob = zf.read(PKG + rel)
    for needle in needles:
        assert needle in blob, '%s 里没有 %r（打进包的不是本轮编译结果？）' % (rel, needle)
print('[6] 新鲜度指纹：%d 个类文件均含自己的标识符' % len(FINGERPRINTS))
zf.close()

# ---------------------------------------------------------------- 3. 校验器门禁
rc, out = run_checker('check_ai_enhancements.py', ('--selftest',))
print(out.rstrip())
if rc != 0:
    sys.exit('check_ai_enhancements.py 未通过（exit %d）' % rc)
print('[7] check_ai_enhancements.py --selftest 通过')

rc, out = run_checker('check_bride_combat.py')
if rc != 0:
    print(out.rstrip())
    sys.exit('check_bride_combat.py 回归失败（exit %d）' % rc)
print('[8] check_bride_combat.py 回归通过（她的技能幅度不受本轮目标层修复影响）')

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
        print('=== 1.1.34 构建完成，但**没有部署** ===')
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
print('[9] 部署前：其它模组 %d 个（将逐个断原样在位）' % len(before))

if os.path.isfile(old_target):
    bak = old_target + '.old.bak'
    if os.path.isfile(bak):
        os.remove(bak)
    os.rename(old_target, bak)
    print('[10] 旧包改名 %s -> %s' % (os.path.basename(old_target), os.path.basename(bak)))
else:
    print('[10] 旧包不在 mods 里（可能已改名），跳过')

shutil.copy2(jar, new_target)
assert md5(new_target) == new_md5, '部署后 md5 不一致（拷坏了）'

after = {}
for n in os.listdir(MODS):
    p = os.path.join(MODS, n)
    if os.path.isfile(p) and n.endswith('.jar') and not n.startswith(PREFIX):
        after[n] = md5(p)
assert before == after, '其它模组的 jar 被动过了！'
print('[11] 其它模组原样在位：%d 个 md5 全等' % len(after))

live = [n for n in os.listdir(MODS) if n.startswith(PREFIX) and n.endswith('.jar')]
assert live == [JAR], 'mods 里不该同时存在多个版本：%r' % (live,)
print('[12] mods 内唯一样本：%s' % live[0])

print()
print('=== 1.1.34 出货完成 ===')
print('    jar : %s' % JAR)
print('    md5 : %s' % new_md5)
print('    尺寸: %d 字节' % os.path.getsize(jar))
print('    修的是: 美女僵尸锁着「看得见够不着」的目标 ⇒ 整张目标表被饿死、站在村民/铁傀儡旁边一动不动')
