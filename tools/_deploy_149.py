"""1.1.49 出货：莫辛-纳甘与 AWM 拉栓改成「柄往上抬 + 手随活骨柄心」。

跑法（**游戏须完全关闭**）：
    python tools/_deploy_149.py                 # 用 build/libs 里已构建好的包
    python tools/_deploy_149.py --build         # 先 ./gradlew build 再出货

判据（任一条不过就退出，不动 mods/）：
  1. 构建产物存在，且 jar 内 mods.toml 的 version == 1.1.49；
  2. 包内容是 1.1.49 该有的东西：
     · 莫辛、AWM 所有「动栓」片段的 bolt.rotation.z ≤ 0（柄往上抬；正号 = 压下去 = 穿模的旧 bug），
       且极值仍是 莫辛 80°/42°、AWM 60°（角度没被顺手改小）；
     · 莫辛 22 键 / 1.55px、AWM 1.932px 的后拉行程不变；
     · AWM 仍是 25 骨 / 417 方块（1.1.48 的几何没被碰）；
  3. 工程门禁在**本机跑一遍**：tools/check_bolt_grip.py（几何：抬升方向、柄心、穿模）与
     tools/bolt_lift_sign.py --check（剪辑与生成器里没有残留的正号）—— 全绿才继续；
  4. 基线：mods/ 里当前那个包必须是本版或上一版（按**包内 mods.toml 版本**认，md5 只用于日志）；
  5. 换包：旧包挪到 mods/ **同级** 的 mods_backup/（保 3 份），mods/ 里只留一个本模组包；
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

VER = '1.1.49'
PREV = '1.1.48'
SRC = 'F:/mcmod/build/libs/apocalypse_zombies-%s.jar' % VER
DEV = 'C:/Users/Administrator/Desktop/.minecraft/versions/1.20.1-Forge_47.4.23-2'
MODS, BACKUP = DEV + '/mods', DEV + '/mods_backup'
PREFIX = 'apocalypse_zombies-'
KEEP_BACKUPS = 3
A = 'assets/apocalypse_zombies/'

#: 已知的历史装机件（只用于日志里多一句说明）。md5 逐次构建会变（jar 里盖时间戳），
#: 所以基线判据是**内容**：包内 mods.toml 的版本号属于下面 ACCEPT 集合。
BASELINE = {}
#: 允许被覆盖的装机件版本：上一版，或本版本自己（重建后重发同一版）。
ACCEPT = (PREV, VER)

# 「有没有 java.exe」根本说明不了游戏在不在跑：Gradle 守护进程、VS Code 的 Gradle 语言服务
# 也全都叫 java.exe。只有命令行里带 forgeclient / forgeserver / net.minecraft.*.Main 的进程，
# 才是真正占着 mods/*.jar 的那个 JVM。
GAME_MARKERS = ('forgeclient', 'forgeserver', 'forgeuserdev',
                'net.minecraft.client.main.Main', 'net.minecraft.server.Main')

# 每把枪动栓的片段 + 期望的提柄角上限（度，取正号比较）。
BOLT_CLIPS = {
    'mosin_nagant': {'bolt': 80.0, 'inspect': 42.0, 'reload_empty': 80.0, 'reload_tactical': 80.0},
    'awm': {'bolt': 60.0, 'inspect': 60.0, 'inspect_empty': 60.0, 'reload_empty': 60.0,
            'static_bolt_caught': 60.0},
}

ok = True

_ap = argparse.ArgumentParser(description='1.1.49 出货：拉栓提柄方向 + 手随活骨柄心')
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


def z_values(clip):
    """一段剪辑里 bolt.rotation 的所有 z 值（导出空间，度）。"""
    out = []
    for key in (clip['bones'].get('bolt', {}).get('rotation') or {}).values():
        vec = (key.get('post') or key).get('vector') if isinstance(key, dict) else key
        if isinstance(vec, list) and len(vec) >= 3:
            out.append(float(vec[2]))
    return out


def peak_pull(clip):
    best = 0.0
    for key in (clip['bones'].get('bolt', {}).get('position') or {}).values():
        vec = (key.get('post') or key).get('vector') if isinstance(key, dict) else key
        if isinstance(vec, list) and len(vec) >= 3:
            best = max(best, abs(float(vec[2])))
    return round(best, 4)


print('=== 1/5 构建产物 ===')
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
    print('  没有 %s —— 先跑 python tools/_deploy_149.py --build' % SRC)
    raise SystemExit(1)
src_md5, src_size = md5(SRC), os.path.getsize(SRC)
print('  %s\n  md5=%s  %d 字节' % (SRC, src_md5, src_size))

print('=== 2/5 包内自检（1.1.49 该有的内容） ===')
with zipfile.ZipFile(SRC) as z:
    names = z.namelist()
    toml = z.read('META-INF/mods.toml').decode('utf-8', 'replace')
    anims = {g: json.loads(z.read(A + 'animations/%s.animation.json' % g))['animations']
             for g in BOLT_CLIPS}
    ag = json.loads(z.read(A + 'geo/awm.geo.json'))['minecraft:geometry'][0]
    jij = [n for n in names if 'jarjar' in n.lower()]
check('version="%s"' % VER in toml, 'mods.toml 版本 == %s' % VER,
      [l.strip() for l in toml.splitlines() if 'version=' in l][0])
for gun, want in BOLT_CLIPS.items():
    got = {c: max((abs(z) for z in z_values(anims[gun].get(c, {}))), default=0.0) for c in want}
    bad_sign = {c: [z for z in z_values(anims[gun].get(c, {})) if z > 1e-9] for c in want}
    bad_sign = {c: v for c, v in bad_sign.items() if v}
    check(not bad_sign, '%s：动栓片段无正号（柄往上抬）' % gun,
          '残留 %s' % bad_sign if bad_sign else '%d 条片段全为负' % len(want))
    for c, angle in want.items():
        check(abs(got[c] - angle) < 0.05, '%s.%s 提柄角仍是 %.0f°' % (gun, c, angle), got[c])
check(abs(peak_pull(anims['mosin_nagant']['bolt']) - 1.55) < 0.02,
      '莫辛 bolt 后拉 1.55px', peak_pull(anims['mosin_nagant']['bolt']))
check(abs(peak_pull(anims['awm']['bolt']) - 1.932) < 0.02,
      'AWM bolt 后拉 1.932px', peak_pull(anims['awm']['bolt']))
check(len(ag['bones']) == 25 and sum(len(b.get('cubes', [])) for b in ag['bones']) == 417,
      'AWM 25 骨 / 417 方块（1.1.48 几何未动）',
      '%d 骨 / %d 方块' % (len(ag['bones']), sum(len(b.get('cubes', [])) for b in ag['bones'])))
# 分发包（cleanJar）的 AWM 动画取自手工版，不走 assets/，所以单独守一道
with open('art/awm/awm.animation.handmade.bak.json', encoding='utf-8') as fh:
    hm = json.load(fh)['animations']
hm_bad = {c: [z for z in z_values(hm.get(c, {})) if z > 1e-9]
          for c in ('bolt', 'reload_empty', 'reload_tactical')}
check(not any(hm_bad.values()), 'cleanJar 用的手工版动画同样无正号（柄往上抬）',
      {c: v for c, v in hm_bad.items() if v} or 'bolt / reload_empty 全为负')
check(not jij, '本模组 jar 不含 jar-in-jar', '干净')

print('=== 3/5 工程门禁（几何 + 方向） ===')
for script, argv in (('tools/check_bolt_grip.py', []), ('tools/bolt_lift_sign.py', ['--check'])):
    try:
        r = subprocess.run([sys.executable, script] + argv, cwd='F:/mcmod',
                           capture_output=True, text=True, errors='replace', timeout=1800)
    except (OSError, subprocess.SubprocessError) as exc:
        check(False, '%s 跑不起来' % script, exc)
        continue
    tail = [l for l in (r.stdout or '').strip().splitlines() if l.strip()]
    check(r.returncode == 0, '%s 全绿' % script, tail[-1] if tail else '')
    if r.returncode != 0:
        for line in tail[-8:]:
            print('        %s' % line)

print('=== 4/5 换包到开发实例 ===')
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

print('=== 5/5 验收指引 ===')
print('  1) 完全退出再启动客户端（Forge 无热重载）')
print('  2) /give @s apocalypse_zombies:mosin_nagant')
print('     · 打一发后拉栓（右键/左键照旧）：栓柄应当**向上抬起**（旧版是往下压、扎进枪托里），')
print('       右手始终握在柄头球上，跟着柄一起抬起→后拉→推回，全程不脱手、不穿枪身')
print('     · R 空仓换弹：压完 5 发后，右手从机匣上方移到柄头，随柄一起回位')
print('     · inspect（右键长按/检视键）：柄抬 42°，手同样跟着')
print('  3) /give @s apocalypse_zombies:awm —— 拉栓 60°，柄上抬且手握住球头；')
print('     空仓换弹最后拉栓那一下同样握手')
print('  4) 网易客户端另跑 python tools/deploy_netease.py（本脚本只管开发实例）')
print()
print('结果：%s' % ('1.1.49 出货完成 ✓' if ok else '★ 存在失败项，mods/ 可能已被改动，请检查上面 [FAIL] 行'))
raise SystemExit(0 if ok else 1)
