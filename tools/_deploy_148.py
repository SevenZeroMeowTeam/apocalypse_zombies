"""1.1.48 出货：AWM 几何/贴图换代（源 F:/apt/9217 工程）+ M1 加兰德末发与「井盖」按真机重做（甲+乙）。

跑法（**游戏须完全关闭**）：
    python tools/_deploy_148.py                 # 用 build/libs 里已构建好的包
    python tools/_deploy_148.py --build         # 先 ./gradlew build 再出货

判据（任一条不过就退出，不动 mods/）：
  1. 构建产物存在，且 jar 内 mods.toml 的 version == 1.1.48；
  2. 包内容是 1.1.48 该有的东西：
     · M1（甲+乙）：8 段剪辑（含 shoot_last 1.2 s、single_load 1.5 s）、14 骨（**无 cover**、
       含 clip_latch）、所有剪辑无 cover 通道、枪机全行程 1.36u、本模组 jar 无 jar-in-jar；
     · AWM（换代）：25 骨 / 417 方块，枪口仍在 z=-18.02；
  3. 基线：mods/ 里当前那个包必须是本版或上一版（按**包内 mods.toml 版本**认，md5 只用于日志）；
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

VER = '1.1.48'
PREV = '1.1.47'
SRC = 'F:/mcmod/build/libs/apocalypse_zombies-%s.jar' % VER
DEV = 'C:/Users/Administrator/Desktop/.minecraft/versions/1.20.1-Forge_47.4.23-2'
MODS, BACKUP = DEV + '/mods', DEV + '/mods_backup'
PREFIX = 'apocalypse_zombies-'
KEEP_BACKUPS = 3
A = 'assets/apocalypse_zombies/'

#: 已知的历史装机件（只用于日志里多一句说明）。md5 逐次构建会变（jar 里盖时间戳），
#: 所以基线判据是**内容**：包内 mods.toml 的版本号属于下面 ACCEPT 集合。
BASELINE = {
    'd497d18df51a36357438ce07de7d3004': '1.1.48 预览构建（AWM 换代、M1 甲+乙之前）',
    '3f301c03916a8bd051bc8f2093968815': '1.1.46 初版（换弹压入件修复前）',
}
#: 允许被覆盖的装机件版本：上一版，或本版本自己（重建后重发同一版）。
ACCEPT = (PREV, VER)

# 「有没有 java.exe」根本说明不了游戏在不在跑：Gradle 守护进程、VS Code 的 Gradle 语言服务器
# 也全都叫 java.exe。只有命令行里带 forgeclient / forgeserver / net.minecraft.*.Main 的进程，
# 才是真正占着 mods/*.jar 的那个 JVM。
GAME_MARKERS = ('forgeclient', 'forgeserver', 'forgeuserdev',
                'net.minecraft.client.main.Main', 'net.minecraft.server.Main')

ok = True

_ap = argparse.ArgumentParser(description='1.1.48 出货：AWM 换代 + M1 末发/井盖真机化')
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


def game_running():
    """True=游戏在跑，False=没在跑，None=探测不出来（保守）。"""
    ps = ('Get-CimInstance Win32_Process -Filter "Name=\'java.exe\'" | '
          'ForEach-Object { $_.CommandLine }')
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', ps],
                           capture_output=True, text=True, errors='replace', timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return any(m.lower() in (r.stdout or '').lower() for m in GAME_MARKERS)


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
    print('  没有 %s —— 先跑 python tools/_deploy_148.py --build' % SRC)
    raise SystemExit(1)
src_md5, src_size = md5(SRC), os.path.getsize(SRC)
print('  %s\n  md5=%s  %d 字节' % (SRC, src_md5, src_size))

print('=== 2/4 包内自检（1.1.48 该有的内容） ===')
with zipfile.ZipFile(SRC) as z:
    names = z.namelist()
    toml = z.read('META-INF/mods.toml').decode('utf-8', 'replace')
    anim = json.loads(z.read(A + 'animations/m1_garand.animation.json'))['animations']
    geo = json.loads(z.read(A + 'geo/m1_garand.geo.json'))['minecraft:geometry'][0]
    ag = json.loads(z.read(A + 'geo/awm.geo.json'))['minecraft:geometry'][0]
    jij = [n for n in names if 'jarjar' in n.lower()]
m1_bones = [b['name'] for b in geo['bones']]
clips = sorted(anim)
check('version="%s"' % VER in toml, 'mods.toml 版本 == %s' % VER,
      [l.strip() for l in toml.splitlines() if 'version=' in l][0])
check(clips == ['bolt', 'draw', 'reload_empty', 'reload_tactical', 'shoot', 'shoot_last',
                'single_load', 'static_idle'], 'M1 八段剪辑齐全（含 shoot_last）', clips)
check(abs(anim['shoot_last']['animation_length'] - 1.2) < 1e-9, 'shoot_last 1.2 s',
      anim['shoot_last']['animation_length'])
check(abs(anim['single_load']['animation_length'] - 1.5) < 1e-9, 'single_load 1.5 s',
      anim['single_load']['animation_length'])
check(len(m1_bones) == 14 and 'clip_latch' in m1_bones and 'cover' not in m1_bones,
      'M1 14 骨：有 clip_latch、无 cover', '%d 骨 %s' % (len(m1_bones), m1_bones))
check(not [n for n, c in anim.items() if 'cover' in c.get('bones', {})],
      '所有剪辑里都没有 cover 通道')
for clip in ('bolt', 'shoot', 'reload_empty', 'reload_tactical', 'shoot_last'):
    check(abs(peak_travel(anim[clip]) - 1.36) < 0.02, '%s 全行程 1.36u' % clip, peak_travel(anim[clip]))
# 末发必须挂在后退位（末值 1.36，不像 shoot 那样回位）
last_keys = sorted(anim['shoot_last']['bones']['bolt']['position'].items(), key=lambda kv: float(kv[0]))
last_z = abs((last_keys[-1][1].get('post') or last_keys[-1][1]).get('vector', [0, 0, 0])[2])
check(abs(last_z - 1.36) < 0.02, 'shoot_last 末值仍挂在后退位（不回位）', last_z)
check(len(ag['bones']) == 25 and sum(len(b.get('cubes', [])) for b in ag['bones']) == 417,
      'AWM 25 骨 / 417 方块（9217 换代几何）',
      '%d 骨 / %d 方块' % (len(ag['bones']), sum(len(b.get('cubes', [])) for b in ag['bones'])))
check(not jij, '本模组 jar 不含 jar-in-jar', '干净')
check(any('textures/' in n and 'm1_garand' in n for n in names), 'M1 贴图在包内',
      len([n for n in names if 'm1_garand' in n]))

print('=== 3/4 换包到开发实例 ===')
running = game_running()
check(running is not True, '游戏没在跑（命令行带 forgeclient/forgeserver 的 java.exe）',
      '未探测到' if running is None else ('★ 游戏在跑，先完全退出' if running else '没在跑'))
if running:
    raise SystemExit(1)
before = {n: md5(os.path.join(MODS, n)) for n in os.listdir(MODS) if n.endswith('.jar')}
mine = [n for n in before if n.startswith(PREFIX)]
if not check(len(mine) == 1, 'mods/ 里只有一个本模组包', mine):
    raise SystemExit(1)
cur = mine[0]
cur_ver = jar_version(os.path.join(MODS, cur))
check(cur_ver in ACCEPT, '基线：装机件版本在可覆盖集合内',
      '%s 包内版本 %s%s' % (cur, cur_ver,
                            '（' + BASELINE[before[cur]] + '）' if before[cur] in BASELINE else ''))
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
check(others == {n: m for n, m in after.items() if not n.startswith(PREFIX)},
      '其它 %d 个模组 md5 全等' % len(others))
check(not any(os.path.isdir(os.path.join(MODS, n)) for n in os.listdir(MODS)), 'mods/ 下没有子目录')

backups = sorted((n for n in os.listdir(BACKUP) if n.startswith(PREFIX) and n.endswith('.jar')),
                 key=lambda n: os.path.getmtime(os.path.join(BACKUP, n)), reverse=True)
for old in backups[KEEP_BACKUPS:]:
    os.remove(os.path.join(BACKUP, old))
    print('  备份超 3 份，删最旧：%s（GitHub Release 上还能取）' % old)
check(len([n for n in os.listdir(BACKUP) if n.startswith(PREFIX)]) <= KEEP_BACKUPS,
      'mods_backup/ 保 %d 份' % KEEP_BACKUPS, sorted(os.listdir(BACKUP)))

print('=== 4/4 验收指引 ===')
print('  1) 完全退出再启动客户端（Forge 无热重载）')
print('  2) /give @s apocalypse_zombies:m1_garand')
print('     · 打到第 8 发（最后一发）：枪机退到底**挂在后面不回位**、空漏夹当场「叮」出井口，')
print('       1.2 s 后自动接空仓换弹（起手就已经是后退位，新夹压下 → 枪机自行前冲闭锁）')
print('     · 空仓换弹：右手不再去拉导气杆，直接压夹 → 落位后向右上甩开让开枪机')
print('     · 半满 R：左手离开护木、拇指按左侧卡榫销（0.29 s 那一下同步）→ 残夹脱出 → 新夹 → 前冲')
print('     · 机匣顶部**没有盖**：装好夹能直接看见顶上那一发（旧版这里有一根横杆、还要抬 34mm）')
print('  3) /give @s apocalypse_zombies:awm —— 9217 工程的新几何与新贴图（25 骨 / 417 方块）')
print('  4) 网易客户端另跑 python tools/deploy_netease.py（本脚本只管开发实例）')
print()
print('结果：%s' % ('1.1.48 出货完成 ✓' if ok else '★ 存在失败项，mods/ 可能已被改动，请检查上面 [FAIL] 行'))
raise SystemExit(0 if ok else 1)
