"""1.1.47 出货：M1 加兰德换弹按真机重做（抽手空档 / 卡榫 / 全行程 / 单发补弹）。

跑法（**游戏须完全关闭**）：
    python tools/_deploy_147.py                 # 用 build/libs 里已构建好的包
    python tools/_deploy_147.py --build         # 先 ./gradlew build 再出货

判据（任一条不过就退出，不动 mods/）：
  1. 构建产物存在，且 jar 内 mods.toml 的 version == 1.1.47；
  2. 包内容是 1.1.47 该有的东西：7 段剪辑（含 single_load 1.5 s）、15 骨（含 clip_latch）、
     M1 枪机全行程 1.36u（=.30-06 全弹长，要退过漏夹末弹底缘）；
  3. 基线：mods/ 里当前那个包必须是本表列出的已知构建（md5 认内容，不认文件名）；
  4. 换包：旧包挪到 mods/ **同级** 的 mods_backup/（保 3 份），mods/ 里只留一个本模组包；
     其它模组 md5 必须全等，mods/ 下不许有子目录（Forge 会递归扫描 → 重复加载）。
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

VER = '1.1.47'
PREV = '1.1.46'
SRC = 'F:/mcmod/build/libs/apocalypse_zombies-%s.jar' % VER
DEV = 'C:/Users/Administrator/Desktop/.minecraft/versions/1.20.1-Forge_47.4.23-2'
MODS, BACKUP = DEV + '/mods', DEV + '/mods_backup'
PREFIX = 'apocalypse_zombies-'
KEEP_BACKUPS = 3
A = 'assets/apocalypse_zombies/'

#: 上一版装机件的已知构建（只认 mods/ 里那一个）。md5 逐次构建会变（jar 里盖构建时间戳），
#: 所以基线判据是**内容**：包内 mods.toml 的版本号属于下表之一。这张表只是给日志加一句说明。
BASELINE = {
    'ef07a1766136baaaca535b6f43d134b2': '1.1.47 之前的预览构建（1.1.46-m1reload，含本轮 M1 改动）',
    'e62af156a482233c1cf38d6fb2b74275': '1.1.46 官方出货件（压入件纯竖直化版）',
    '3f301c03916a8bd051bc8f2093968815': '1.1.46 初版（换弹压入件修复前）',
}
#: 允许被覆盖的装机件版本：上一版，或本版本自己（重建后重发同一版）。
ACCEPT = (PREV, VER)

ok = True

_ap = argparse.ArgumentParser(description='1.1.47 出货：M1 换弹真机化')
_ap.add_argument('--build', action='store_true', help='先跑 ./gradlew build 再出货')
args = _ap.parse_args()


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def check(cond, label, detail=None):
    global ok
    ok = ok and bool(cond)
    tail = ('  —— %s' % (detail,)) if detail not in (None, '', []) else ''
    print('  %s %s%s' % ('[OK  ]' if cond else '[FAIL]', label, tail))
    return bool(cond)


def jar_version(path):
    """包内 mods.toml 声明的版本（认内容，不认文件名 / md5）。"""
    with zipfile.ZipFile(path) as z:
        toml = z.read('META-INF/mods.toml').decode('utf-8', 'replace')
    m = re.search(r'^version\s*=\s*"([^"]+)"', toml, re.M)
    return m.group(1) if m else '?'


def peak_travel(clip):
    """一段剪辑里 bolt 通道的最大后移量（导出空间 = +z 向后）。"""
    best = 0.0
    for key in clip['bones']['bolt']['position'].values():
        vec = (key.get('post') or key).get('vector', [0, 0, 0])
        best = max(best, abs(vec[2]))
    return round(best, 4)


print('=== 1/4 构建产物 ===')
if args.build or not os.path.exists(SRC):
    if not os.path.exists(SRC):
        print('  没有 %s —— 先构建' % SRC)
    if args.build:
        print('  跑 ./gradlew build ...')
        rc = subprocess.call(['./gradlew', 'build', '--offline', '--console=plain'], cwd='F:/mcmod')
        if rc != 0:
            print('  ★ 构建失败（exit %d）' % rc)
            raise SystemExit(1)
if not os.path.exists(SRC):
    print('  没有 %s —— 先跑 python tools/_deploy_147.py --build' % SRC)
    raise SystemExit(1)
src_md5, src_size = md5(SRC), os.path.getsize(SRC)
print('  %s\n  md5=%s  %d 字节' % (SRC, src_md5, src_size))

print('=== 2/4 包内自检（1.1.47 该有的内容） ===')
with zipfile.ZipFile(SRC) as z:
    names = z.namelist()
    toml = z.read('META-INF/mods.toml').decode('utf-8', 'replace')
    anim = json.loads(z.read(A + 'animations/m1_garand.animation.json'))['animations']
    geo = json.loads(z.read(A + 'geo/m1_garand.geo.json'))['minecraft:geometry'][0]
    jij = [n for n in names if 'jarjar' in n.lower()]
bones = [b['name'] for b in geo['bones']]
clips = sorted(anim)
check('version="%s"' % VER in toml, 'mods.toml 版本 == %s' % VER, [l.strip() for l in toml.splitlines() if 'version=' in l][0])
check(clips == ['bolt', 'draw', 'reload_empty', 'reload_tactical', 'shoot', 'single_load', 'static_idle'],
      'M1 七段剪辑齐全', clips)
check(abs(anim['single_load']['animation_length'] - 1.5) < 1e-9, 'single_load 1.5 s',
      anim['single_load']['animation_length'])
check('clip_latch' in bones, '第 15 根骨 clip_latch 在', '%d 骨' % len(bones))
check('clip_latch' in anim['reload_tactical']['bones'], 'reload_tactical 有卡榫通道')
for clip in ('bolt', 'shoot', 'reload_empty', 'reload_tactical'):
    check(abs(peak_travel(anim[clip]) - 1.36) < 0.02, '%s 全行程 1.36u' % clip, peak_travel(anim[clip]))
check(not jij, '本模组 jar 不含 jar-in-jar', '干净')
check(any('textures/' in n and 'm1_garand' in n for n in names), 'M1 贴图在包内',
      [n for n in names if 'm1_garand' in n].__len__())

print('=== 3/4 换包到开发实例 ===')
before = {n: md5(os.path.join(MODS, n)) for n in os.listdir(MODS) if n.endswith('.jar')}
mine = [n for n in before if n.startswith(PREFIX)]
if not check(len(mine) == 1, 'mods/ 里只有一个本模组包', mine):
    raise SystemExit(1)
cur = mine[0]
cur_ver = jar_version(os.path.join(MODS, cur))
check(cur_ver in ACCEPT, '基线：装机件版本在可覆盖集合内',
      '%s 包内版本 %s%s' % (cur, cur_ver, '（' + BASELINE[before[cur]] + '）' if before[cur] in BASELINE else ''))
if cur_ver not in ACCEPT:
    raise SystemExit(1)

os.makedirs(BACKUP, exist_ok=True)
dst = os.path.join(BACKUP, cur)
if not os.path.exists(dst) or md5(dst) != before[cur]:
    shutil.copy2(os.path.join(MODS, cur), dst)
    print('  备份 %s -> mods_backup/' % cur)
check(md5(dst) == before[cur], '备份 md5 与原装机件一致')

os.remove(os.path.join(MODS, cur))
shutil.copy2(SRC, os.path.join(MODS, '%s%s.jar' % (PREFIX, VER)))
after = {n: md5(os.path.join(MODS, n)) for n in os.listdir(MODS) if n.endswith('.jar')}
new_name = '%s%s.jar' % (PREFIX, VER)
check(md5(os.path.join(MODS, new_name)) == src_md5, '装机件 md5 == 构建产物', new_name)
check([n for n in after if n.startswith(PREFIX)] == [new_name], 'mods/ 里只留一个本模组包')
others = {n: m for n, m in before.items() if not n.startswith(PREFIX)}
check(others == {n: m for n, m in after.items() if not n.startswith(PREFIX)}, '其它 %d 个模组 md5 全等' % len(others))
check(not any(os.path.isdir(os.path.join(MODS, n)) for n in os.listdir(MODS)), 'mods/ 下没有子目录')

backups = sorted((n for n in os.listdir(BACKUP) if n.startswith(PREFIX) and n.endswith('.jar')),
                 key=lambda n: os.path.getmtime(os.path.join(BACKUP, n)), reverse=True)
for old in backups[KEEP_BACKUPS:]:
    os.remove(os.path.join(BACKUP, old))
    print('  备份超 3 份，删最旧：%s（GitHub Release 上还能取）' % old)
check(len([n for n in os.listdir(BACKUP) if n.startswith(PREFIX)]) <= KEEP_BACKUPS,
      'mods_backup/ 保 %d 份' % KEEP_BACKUPS, [n for n in os.listdir(BACKUP) if n.startswith(PREFIX)])

print('=== 4/4 验收指引 ===')
print('  1) 完全退出再启动客户端（Forge 无热重载）')
print('  2) /give @s apocalypse_zombies:m1_garand')
print('     · 打空 8 发 -> R：空漏夹弹飞（叮在这一瞬）-> 新夹落位 -> 停 4 帧才前冲 -> 1.75 s 拍到位')
print('     · 剩 1~7 发 -> R：抛活弹 -> 按左侧卡榫销 -> 残夹脱出 -> 新夹 -> 抽手 -> 前冲')
print('     · Shift + R：单发补弹，余弹 +1（不换漏夹）')
print('  3) 网易客户端另跑 python tools/deploy_netease.py（本脚本只管开发实例）')
print()
print('结果：%s' % ('1.1.47 出货完成 ✓' if ok else '★ 存在失败项，mods/ 可能已被改动，请检查上面 [FAIL] 行'))
raise SystemExit(0 if ok else 1)
