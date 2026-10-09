"""1.1.62 出货：修好柯尔特 1878 的折开动作（绕错轴）与枪托台阶。

跑法（**游戏须完全关闭**）：
    python tools/_deploy_162.py                 # 用 build/libs 里已构建好的包
    python tools/_deploy_162.py --build         # 先 ./gradlew build 再出货

判据（任一条不过就退出，不动 mods/）：
  1. 构建产物存在，且 jar 内 mods.toml 的 version == 1.1.62；
  2. 包内容是 1.1.62 该有的东西：
     · geo/colt_1878.geo.json —— identifier geometry.colt_1878、512² 贴图基准、
       12 骨 / 87 方块、rest 姿态无旋转（骨骼一根都不许带 rotation）；
     · animations/colt_1878.animation.json —— 8 条片段且**长度逐条等于 Java 常量**
       （draw 0.8 / shoot 0.6 / bolt 1.4 / reload_tactical 3.0 / reload_empty 3.6 /
        static_idle 2.0 / ADS_up 0.22 / ADS_down 0.18）；
       外露双锤必须真动：shoot 与 bolt/reload_* 的 hammer_l 通道值 == S686 的 hammer 曲线
       （[0,+30,+30,-3,0] / [0,+26,+26,-4,0]，符号为正 —— 负号是锤子往机匣里倒的错版）；
     · textures/item/colt_1878.png 是 512×512；
     · models/item/colt_1878.json、data/.../damage_type/colt_1878_bullet.json 在位，
       两套 lang 都有物品名与死亡信息；
  3. 工程门禁在**本机跑一遍**：tools/check_gun_resources.py（7 把枪全绿）与
     tools/colt_1878_install.js（规范化自检）—— 全绿才继续；
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
import struct
import subprocess
import sys
import zipfile

VER = '1.1.62'
PREV = '1.1.61'
SRC = 'F:/mcmod/build/libs/apocalypse_zombies-%s.jar' % VER
DEV = 'F:/.minecraft/versions/1.20.1-Forge_47.4.26'
MODS, BACKUP = DEV + '/mods', DEV + '/mods_backup'
PREFIX = 'apocalypse_zombies-'
KEEP_BACKUPS = 3
A = 'assets/apocalypse_zombies/'

#: 允许被覆盖的装机件版本：上一版，或本版本自己（重建后重发同一版）。
ACCEPT = (PREV, VER)

#: 真客户端标记 —— 一旦在跑就没得商量：Forge 无热重载，换包必须等它完全退出。
CLIENT_MARKERS = ('net.minecraft.client.main.Main',)
#: gradle 起的东西（runClient / runServer / gameTest）。runServer 与 gameTest 是无头测试服，
#: 跑的是 build/classes + runs/ 自己的目录，**不锁实例 mods/ 里的 jar**，所以允许用
#: --allow-dev-server 明确放行（默认仍拒绝）。runClient 同时命中 CLIENT_MARKERS，照样拦。
DEV_SERVER_MARKERS = ('forgeclient', 'forgeserver', 'forgeuserdev', 'net.minecraft.server.Main')

#: 片段名 -> 期望长度（秒）。与 Colt1878Item 的 *_TICKS 逐一对应（tick = 秒 × 20）。
CLIPS = {
    'static_idle': 2.0, 'draw': 0.8, 'shoot': 0.6, 'bolt': 1.4,
    'reload_tactical': 3.0, 'reload_empty': 3.6, 'ADS_up': 0.22, 'ADS_down': 0.18,
}
#: 外露双锤：这些片段必须驱动 hammer_l，且向量必须等于 S686 的 hammer 曲线（正号）。
HAMMER = {
    'shoot': [0.0, 30.0, 30.0, -3.0, 0.0],
    'bolt': [0.0, 26.0, 26.0, -4.0, 0.0],
    'reload_tactical': [0.0, 26.0, 26.0, -4.0, 0.0],
    'reload_empty': [0.0, 26.0, 26.0, -4.0, 0.0],
}
BONES, CUBES = 12, 87

ok = True
_ap = argparse.ArgumentParser(description='1.1.62 出货：柯尔特 1878 折开动作修复')
_ap.add_argument('--build', action='store_true', help='先跑 ./gradlew build 再出货')
_ap.add_argument('--allow-dev-server', action='store_true',
                 help='放行"无头开发服（runServer/gameTest）在跑"这一种情况；'
                      '它跑的是 build/classes、不锁实例 mods/ 里的 jar。真客户端在跑仍拒绝。')
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
    with zipfile.ZipFile(path) as z:
        toml = z.read('META-INF/mods.toml').decode('utf-8', 'replace')
    m = re.search(r'^version\s*=\s*"([^"]+)"', toml, re.M)
    return m.group(1) if m else '?'


def game_state():
    """探测 java.exe：(客户端在跑, 无头开发服在跑)。探测不了就返回 (None, None)。"""
    ps = ('Get-CimInstance Win32_Process -Filter "Name=\'java.exe\'" | '
          'ForEach-Object { $_.CommandLine }')
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', ps],
                           capture_output=True, text=True, errors='replace', timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None, None
    if r.returncode != 0:
        return None, None
    text = (r.stdout or '').lower()
    return (any(m.lower() in text for m in CLIENT_MARKERS),
            any(m.lower() in text for m in DEV_SERVER_MARKERS))


def png_size(blob):
    """PNG 的宽高在 IHDR 里（偏移 16/20，大端）。"""
    if blob[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    return struct.unpack('>II', blob[16:24])


def hammer_vecs(clip):
    """一段剪辑里 hammer_l 的 rotation.x 序列（导出空间，度）。"""
    h = (clip.get('bones') or {}).get('hammer_l') or {}
    rot = h.get('rotation') or {}
    out = []
    for _, key in sorted(rot.items(), key=lambda kv: float(kv[0])):
        vec = (key.get('post') or key).get('vector') if isinstance(key, dict) else key
        if isinstance(vec, list) and len(vec) >= 3:
            out.append(round(float(vec[0]), 4))
    return out


print('=== 1/5 构建产物 ===')
if args.build or not os.path.exists(SRC):
    if args.build:
        print('  跑 ./gradlew build ...')
        rc = subprocess.call(['./gradlew', 'build', '--console=plain'], cwd='F:/mcmod')
        if rc != 0:
            print('  ★ 构建失败（exit %d）' % rc)
            raise SystemExit(1)
if not os.path.exists(SRC):
    print('  没有 %s —— 先跑 python tools/_deploy_162.py --build' % SRC)
    raise SystemExit(1)
src_md5, src_size = md5(SRC), os.path.getsize(SRC)
print('  %s\n  md5=%s  %d 字节' % (SRC, src_md5, src_size))

print('=== 2/5 包内自检（1.1.62 该有的内容） ===')
with zipfile.ZipFile(SRC) as z:
    names = z.namelist()
    toml = z.read('META-INF/mods.toml').decode('utf-8', 'replace')
    geo = json.loads(z.read(A + 'geo/colt_1878.geo.json'))['minecraft:geometry'][0]
    anim = json.loads(z.read(A + 'animations/colt_1878.animation.json'))['animations']
    png = z.read(A + 'textures/item/colt_1878.png') if A + 'textures/item/colt_1878.png' in names else b''
    item_json = A + 'models/item/colt_1878.json' in names
    dt = 'data/apocalypse_zombies/damage_type/colt_1878_bullet.json' in names
    lang_keys = {}
    for lf in ('zh_cn', 'en_us'):
        try:
            lang_keys[lf] = json.loads(z.read(A + 'lang/%s.json' % lf))
        except KeyError:
            lang_keys[lf] = {}
    jij = [n for n in names if 'jarjar' in n.lower()]

check('version="%s"' % VER in toml, 'mods.toml 版本 == %s' % VER,
      [l.strip() for l in toml.splitlines() if 'version=' in l][0])
desc = geo.get('description', {})
check(desc.get('identifier') == 'geometry.colt_1878', 'geo identifier == geometry.colt_1878',
      desc.get('identifier'))
check(desc.get('texture_width') == 512 and desc.get('texture_height') == 512,
      'geo 贴图基准 512×512', '%s×%s' % (desc.get('texture_width'), desc.get('texture_height')))
bones = geo.get('bones', [])
cubes = sum(len(b.get('cubes', [])) for b in bones)
check(len(bones) == BONES and cubes == CUBES, 'geo %d 骨 / %d 方块' % (BONES, CUBES),
      '%d 骨 / %d 方块' % (len(bones), cubes))
dirty = [b['name'] for b in bones if b.get('rotation')]
check(not dirty, 'rest 姿态骨骼无旋转（铁律）', dirty or '12 根全零')
sz = png_size(png) if png else None
check(sz == (512, 512), 'textures/item/colt_1878.png 是 512×512', sz)
got = {k: (v.get('animation_length') if isinstance(v, dict) else None) for k, v in anim.items()}
check(sorted(anim.keys()) == sorted(CLIPS.keys()), '8 条片段名齐',
      sorted(anim.keys()))
bad_len = {k: (got.get(k), want) for k, want in CLIPS.items() if abs((got.get(k) or -1) - want) > 1e-6}
check(not bad_len, '片段长度逐条等于 Java 常量', bad_len or '（tick 换算见 Colt1878Item）')
for clip, want in HAMMER.items():
    vals = hammer_vecs(anim.get(clip, {}))
    check(vals == want, '%s.hammer_l == S686 的 hammer 曲线（正号）' % clip,
          vals if vals != want else want)
check(item_json, 'models/item/colt_1878.json 在位')
check(dt, 'damage_type/colt_1878_bullet.json 在位')
for lf, t in lang_keys.items():
    need = ('item.apocalypse_zombies.colt_1878', 'death.attack.colt_1878_bullet')
    miss = [k for k in need if k not in t]
    check(not miss, '%s：物品名 + 死亡信息齐' % lf, miss or need[0])
check(not jij, '本模组 jar 不含 jar-in-jar', '干净')

print('=== 3/5 工程门禁 ===')
for argv in (['python3', 'tools/check_gun_resources.py'], ['node', 'tools/colt_1878_install.js']):
    script = argv[1]
    try:
        r = subprocess.run(argv, cwd='F:/mcmod', capture_output=True, text=True,
                           errors='replace', timeout=1800)
    except (OSError, subprocess.SubprocessError) as exc:
        check(False, '%s 跑不起来' % script, exc)
        continue
    tail = [l for l in (r.stdout or '').strip().splitlines() if l.strip()]
    good = r.returncode == 0 and not any('[FAIL]' in l for l in tail)
    check(good, '%s 全绿' % script, tail[-1] if tail else '')
    if not good:
        for line in tail[-8:]:
            print('        %s' % line)

print('=== 4/5 换包到开发实例 ===')
client, dev = game_state()
check(client is not True, '客户端没在跑（命令行带 net.minecraft.client.main.Main 的 java.exe）',
      '未探测到' if client is None else ('★ 客户端在跑，先完全退出' if client else '没在跑'))
if client:
    raise SystemExit(1)
if dev and not args.allow_dev_server:
    check(False, '无头开发服在跑 —— 加 --allow-dev-server 可放行',
          '★ 它在跑 build/classes、不锁实例 jar；默认仍拒绝')
    raise SystemExit(1)
check(not dev or args.allow_dev_server, '无头开发服在跑（已显式放行）',
      '★ 探到 gradle 测试服，按 --allow-dev-server 继续' if dev else '没在跑')
before = {n: md5(os.path.join(MODS, n)) for n in os.listdir(MODS) if n.endswith('.jar')}
mine = [n for n in before if n.startswith(PREFIX)]
if not check(len(mine) == 1, 'mods/ 里只有一个本模组包', mine):
    raise SystemExit(1)
cur = mine[0]
cur_ver = jar_version(os.path.join(MODS, cur))
check(cur_ver in ACCEPT, '基线：装机件版本在可覆盖集合内', '%s 包内版本 %s' % (cur, cur_ver))
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
print('  2) /give @s apocalypse_zombies:colt_1878')
print('     · 铁瞄、2 发、每扣一次扳机 1 发、1 秒一发；潜行扣扳机 = 双管齐射')
print('     · 打空后按 R：折开换弹 3.6 s（比 S686 慢），合膛后补满 2 发')
print('     · 空膛时扣扳机 = 折开检查（bolt 1.4 s），左上角不会卡动作')
print('  3) 僵尸 0.2% 那个枪械档现在有七把枪（含教练枪）')
print()
print('结果：%s' % ('1.1.62 出货完成 ✓' if ok else '★ 存在失败项，mods/ 可能已被改动，请检查上面 [FAIL] 行'))
raise SystemExit(0 if ok else 1)
