# -*- coding: utf-8 -*-
"""1.1.29 出货：AI 增强（自动锁敌 / 围猎包抄 / 村民逃跑+呼叫铁傀儡 / 骷髅超大跟踪箭 / 铁傀儡守卫）。

本轮没有几何、贴图、动画改动 —— 全部是 AI 与一个新弹射物实体。因此门禁重心从
「模型字节一致」换成「接线真的接上了、新类真的进包了、旧缺陷真被修掉了」。

改动清单：
  · 新增 event/MobAiEnhanced.java（@Mod.EventBusSubscriber，订阅 3 个事件）：
    同类仇恨传播 + 隔墙锁定 + 围猎 + 村民 Brain 改道 + 精英重箭 + 铁傀儡守卫。
  · 新增 entity/GiantArrow.java（继承 Arrow）+ entity/ai/GiantArrowGoal.java：
    超大号跟踪箭，缩放 2.5、伤害 10、击飞 3、限速转向 <=6 度/tick。
  · 新增 client/renderer/GiantArrowRenderer.java：复用原版箭贴图，绕原点缩放后
    沿视线回退 (scale-1)*0.675 格，保证放大后箭尖仍落在命中点上。
  · 新增 entity/ai/{SharedAggroGoal,ScentTargetGoal,SurroundGoal,SkirmishGoal,GolemGuardGoal}.java。
  · registry/ModEntities：注册 GIANT_ARROW；client/ClientModBusEvents：注册其渲染器。
  · Config：新增 ai_enhance 分节，28 个开关（默认保守，可一键关）。
  · 修掉一个预存缺陷：KeepDistanceGoal.canUse 原来只看「有没有目标」，于是它永久霸占
    MOVE —— 同实体上优先级更低的弓箭 Goal 一箭都放不出来（精英骸骨射手的弓是死的）。
    现在按距离判定，进环带即交还 MOVE。

断言重心：
  1. 版本号先落 gradle.properties，再由本脚本自己跑构建（不许沿用旧产物）。
  2. jar 内 mods.toml == 1.1.29。
  3. 新增的 9 个 .class 必须都在包里（少一个 = 某个子项静默没落地）。
  4. 新鲜度用「自己的标识符」证：MobAiEnhanced 里有 apocalypse_ai_range / hasRangedIdentity /
     onLivingTick；KeepDistanceGoal 里有 outOfBand；GiantArrow 里有 GiantSeeker。
  5. tools/check_ai_enhancements.py --selftest 全绿（含 9 条变异测试）。
  6. tools/check_gun_mobs.py 回归（1.1.24 的持枪身份不能被本轮 AI 覆盖）。
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
OLD, NEW = '1.1.28', '1.1.29'
JAR = 'apocalypse_zombies-%s.jar' % NEW
PREFIX = 'apocalypse_zombies-'

PKG = 'com/apocalypse/zombies/'
NEW_CLASSES = [
    'event/MobAiEnhanced.class',
    'entity/GiantArrow.class',
    'entity/ai/GiantArrowGoal.class',
    'entity/ai/SharedAggroGoal.class',
    'entity/ai/ScentTargetGoal.class',
    'entity/ai/SurroundGoal.class',
    'entity/ai/SkirmishGoal.class',
    'entity/ai/GolemGuardGoal.class',
    'client/renderer/GiantArrowRenderer.class',
]
# 新鲜度指纹：类文件里必须出现这些「自己的标识符」，证明打进包的是本轮编译结果
FINGERPRINTS = {
    'event/MobAiEnhanced.class': [b'apocalypse_ai_range', b'hasRangedIdentity', b'onLivingTick'],
    'entity/ai/SurroundGoal.class': [b'CHASE_WINDOW'],
    'entity/KeepDistanceGoal.class': [b'outOfBand'],
    'entity/GiantArrow.class': [b'GiantSeeker'],
    'client/renderer/GiantArrowRenderer.class': [b'TIP_AHEAD'],
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
    out = (r.stdout + r.stderr).decode('utf-8', 'replace')
    return r.returncode, out


# ---------------------------------------------------------------- 1. 版本号 -> 构建
gp = os.path.join(ROOT, 'gradle.properties')
with open(gp, 'r', encoding='utf-8', newline='') as fh:
    txt = fh.read()
assert 'mod_version=%s' % OLD in txt, 'gradle.properties 里不是 %s' % OLD
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
names = set(zf.namelist())
assert 'META-INF/mods.toml' in names, 'jar 里没有 mods.toml'
assert NEW in zf.read('META-INF/mods.toml').decode('utf-8', 'replace'), 'mods.toml 不是 %s' % NEW
print('[4] mods.toml 版本 = %s' % NEW)

missing = [c for c in NEW_CLASSES if (PKG + c) not in names]
assert not missing, 'jar 里缺这些新类：%r' % missing
print('[5] 新增 %d 个 .class 全在包里' % len(NEW_CLASSES))

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

rc, out = run_checker('check_gun_mobs.py')
if rc != 0:
    print(out.rstrip())
    sys.exit('check_gun_mobs.py 回归失败（exit %d）' % rc)
print('[8] check_gun_mobs.py 回归通过（1.1.24 持枪身份未被本轮 AI 覆盖）')

# ---------------------------------------------------------------- 4. 部署
old_target = os.path.join(MODS, 'apocalypse_zombies-%s.jar' % OLD)
new_target = os.path.join(MODS, JAR)

# 先探锁：游戏运行中 jar 会被独占，宁可在这里清楚报错，也不要拷到一半失败
if os.path.isfile(old_target):
    try:
        with open(old_target, 'r+b'):
            pass
    except PermissionError:
        sys.exit('[!] %s 被占用 —— 游戏还在运行。请完全退出客户端（含启动器）后重跑本脚本。'
                 % os.path.basename(old_target))

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
print('=== 1.1.29 出货完成 ===')
print('    jar : %s' % JAR)
print('    md5 : %s' % new_md5)
print('    尺寸: %d 字节' % os.path.getsize(jar))
print('    亮点: AI 增强 6 子项 + 超大跟踪箭；顺带修掉 KeepDistanceGoal 永久霸占 MOVE 的预存缺陷')
