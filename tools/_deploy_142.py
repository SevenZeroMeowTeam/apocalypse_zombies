"""1.1.42 出货：修掉让全屏文字变方框的 Boss 动画形状缺陷。

事故（1.1.41）
--------------
`logs/游戏日志 - 1.20.1-Forge_47.4.23-2.log`：

    08:27:01  [Render thread/INFO] [minecraft/Minecraft]: Caught error loading resourcepacks,
              removing all selected resourcepacks
    Caused by: com.google.gson.JsonParseException: Invalid keyframe data - expected array, found
              {"0.0":0.0,"0.375":1.6,...}
        at geckolib...BakedAnimationsAdapter.addBedrockKeyframes
    Caused by: GeckoLibException: apocalypse_zombies:animations/horde_overlord.animation.json

生成器的内部模型是按轴存的（{x: {t: v}, y: {...}}），`Clip.to_json()` 把这个结构
原样写盘。GeckoLib 只认「时间 → 三元向量」（裸数组，或含 vector / post / pre 的对象），
于是它把 `"x"` 当时间、把 `{"0.0": 0.0, ...}` 当值 → 抛异常。**异常抛在资源重载里**：
整次重载失败 → 客户端清空用户选中的资源包（options.txt 的 resourcePacks 变空）→
字体没能重建 → 全屏文字变方框。同一份日志里 awm / uzi / crossbow / bride / m1 / 莫辛
都正常加载，只有 Boss 这一个文件抛异常 —— 缺陷是**这个文件独有的**。

修法：`tools/boss_v1.py` 的 `to_json()` 在出口处把 x/y/z 合并成向量（按各轴自身的键
线性取样，线性插值对段中插点不变，动作逐帧等价），并新增「动画通道符合 GeckoLib 形状」
断言；`tools/check_boss.py` 与 `tools/check_gun_resources.py` 各加一道同样的闸门
（后者罩所有动画文件，CI 也会跑）。

验证项
------
 1. 基线 = mods/ 里正在生效的 1.1.41，md5 先验身份（2ab31881da9ce8344262be00bba4dc21）。
 2. jar 内 mods.toml == 1.1.42。
 3. 相对 1.1.41 逐条字节比对：只允许动 {Boss 动画 json, mods.toml, MANIFEST}。
    geo / 贴图 / Java 一个字节都不许变 —— 这是「只修动画形状」的硬证据。
 4. 生成器重跑幂等 + 资产三向对账（art == src == jar）。
 5. **GeckoLib 形状回读**：对 jar 里的动画条目逐通道校验（不是看源码，是看成品）。
 6. 门禁：check_boss / check_gun_resources（含新增的全家动画形状闸门）/ check_uzi_anim / check_uzi_art。
 7. 部署：旧包备份到 mods_backup/（保留 3 份）再从 mods/ 移除，装入 1.1.42。
 8. 附带修复：1.1.41 那次重载失败把用户的资源包从 options.txt 里清空了
    （resourcePacks:[]），脚本在**游戏未运行**时把它们写回去（只在这两项确实是空的时候动，
    不覆盖你自己选的组合）。

用法：python tools/_deploy_142.py
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_DIR = 'C:/Users/Administrator/Desktop/.minecraft/versions/1.20.1-Forge_47.4.23-2'
MODS = VERSION_DIR + '/mods'
BACKUP = VERSION_DIR + '/mods_backup'      # mods 同级：mods/ 的子目录会被 Forge 递归扫到
KEEP_BACKUPS = 3
OLD, NEW = '1.1.41', '1.1.42'
PREFIX = 'apocalypse_zombies-'
JAR = PREFIX + NEW + '.jar'
OLD_SHIPPED_MD5 = '2ab31881da9ce8344262be00bba4dc21'   # 1.1.41 出货件的唯一合法身份

PKG = 'com/apocalypse/zombies/'
RES = 'assets/apocalypse_zombies/'
SRC = 'src/main/resources/'
ANIM = RES + 'animations/horde_overlord.animation.json'

# 预期变化集合（由 diff 实测写死）：本次只修动画形状 + 版本号
CHANGED = {
    ANIM,
    'META-INF/mods.toml',
    'META-INF/MANIFEST.MF',      # 每次构建都重写，下面断言它只差构建元数据
}
ADDED = set()
REMOVED = set()

# 三向对账：(台账 art, 发布件 src, 包内条目名)
BOTH = {
    'geo': ('art/boss/horde_overlord.geo.json',
            SRC + RES + 'geo/horde_overlord.geo.json', RES + 'geo/horde_overlord.geo.json'),
    'anim': ('art/boss/horde_overlord.animation.json',
             SRC + ANIM, ANIM),
    'png': ('art/boss/horde_overlord.png',
            SRC + RES + 'textures/entity/horde_overlord.png',
            RES + 'textures/entity/horde_overlord.png'),
}

# 1.1.41 的重载失败把这两项从 options.txt 里清掉了；修好之后要还回去
PACKS_BEFORE_FIX = ['file/apocalypse_zombies-borrowed-assets.zip',
                    'file/Minecraft-Mod-Language-Modpack-Converted-1.20.1.zip']


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def jar_bytes(path):
    with zipfile.ZipFile(path) as zf:
        return {i.filename: zf.read(i.filename) for i in zf.infolist() if not i.is_dir()}


def game_running():
    try:
        out = subprocess.run(['tasklist'], capture_output=True, text=True, errors='replace').stdout
    except OSError:
        return None
    return 'java.exe' in out.lower()


def check_manifest(old_raw, new_raw, new_ver):
    o = old_raw.decode('utf-8', 'replace').splitlines()
    n = new_raw.decode('utf-8', 'replace').splitlines()
    diff = [l for l in o + n if l not in (o if l in n else n)]
    diff = [l for l in diff if l.strip()]
    for line in diff:
        if not (line.startswith('Implementation-Version: ')
                or line.startswith('Implementation-Timestamp: ')):
            sys.exit('MANIFEST 里有非构建元数据的差异，需要人看：%r' % line)
    if not any(l.strip() == 'Implementation-Version: ' + new_ver for l in diff):
        sys.exit('MANIFEST 的版本不是 %s：%r' % (new_ver, diff))
    return diff


def run_checker(script):
    p = os.path.join(ROOT, 'tools', script)
    if not os.path.isfile(p):
        print('    [跳过] %s 不存在' % script)
        return True
    r = subprocess.run([sys.executable, p], cwd=ROOT, capture_output=True, text=True, errors='replace')
    out = ((r.stdout or '') + (r.stderr or '')).strip()
    tail = out.splitlines()[-1] if out else ''
    ok = r.returncode == 0 and not re.search(r'FAIL|✗|不通过|错误|不符', out)
    print('    %-28s %s  %s' % (script, 'PASS' if ok else 'FAIL', tail[:80]))
    return ok


# --- GeckoLib 契约（BakedAnimationsAdapter 4.8.4）：通道 = 时间 → 三元向量 ---
def vector_ok(v):
    if isinstance(v, list):
        return len(v) == 3 and all(isinstance(n, (int, float)) for n in v)
    if isinstance(v, dict):
        if 'vector' in v:
            return vector_ok(v['vector'])
        if 'post' in v or 'pre' in v:
            return all(k not in v or vector_ok(v[k]) for k in ('post', 'pre'))
    return False


def anim_problems(raw_bytes):
    data = json.loads(raw_bytes.decode('utf-8'))
    bad = []
    for clip, body in (data.get('animations') or {}).items():
        for bone, chans in (body.get('bones') or {}).items():
            for chan, val in (chans or {}).items():
                if chan not in ('rotation', 'position', 'scale'):
                    bad.append('%s/%s 通道名 %r' % (clip, bone, chan))
                    continue
                if not isinstance(val, dict):
                    bad.append('%s/%s/%s 非对象' % (clip, bone, chan))
                    continue
                if 'vector' in val:
                    if not vector_ok(val['vector']):
                        bad.append('%s/%s/%s 常量非向量' % (clip, bone, chan))
                    continue
                for t, v in val.items():
                    try:
                        float(t)
                    except (TypeError, ValueError):
                        bad.append('%s/%s/%s 时间键 %r 非数字' % (clip, bone, chan, t))
                        break
                    if not vector_ok(v):
                        bad.append('%s/%s/%s@%s 非向量' % (clip, bone, chan, t))
                        break
    return bad


# ---------------------------------------------------------------- [0] 基线
base_path = None
for cand in sorted(os.listdir(MODS)):
    if cand.startswith(PREFIX) and cand.endswith('.jar'):
        p = os.path.join(MODS, cand)
        if md5(p) == OLD_SHIPPED_MD5:
            base_path = p
            break
if base_path is None:
    sys.exit('mods/ 里找不到 md5 == %s 的 %s 出货件，基线不成立' % (OLD_SHIPPED_MD5, OLD))
base = jar_bytes(base_path)
print('[0] 基线 %s = %s  条目 %d  md5 %s' % (OLD, os.path.basename(base_path), len(base), OLD_SHIPPED_MD5))
bad_base = anim_problems(base[ANIM])
if not bad_base:
    sys.exit('基线里的 Boss 动画居然是合规的 —— 说明基线不是出问题的那个 1.1.41，先查清楚')
print('    基线里的 Boss 动画确认带缺陷：%d 处（%s）' % (len(bad_base), bad_base[0]))

# ---------------------------------------------------------------- [1] 新包
jar = os.path.join(ROOT, 'build', 'libs', JAR)
if not os.path.isfile(jar):
    sys.exit('没有 %s，先 ./gradlew build' % jar)
new_md5 = md5(jar)
if new_md5 == OLD_SHIPPED_MD5:
    sys.exit('新包 md5 与 %s 相同：等于没改' % OLD)
new = jar_bytes(jar)
print('[1] %s  md5=%s  %d 字节' % (JAR, new_md5, os.path.getsize(jar)))

# ---------------------------------------------------------------- [2] mods.toml
toml = new.get('META-INF/mods.toml', b'').decode('utf-8', 'replace')
m = re.search(r'version\s*=\s*"([^"]+)"', toml)
if not m or m.group(1) != NEW:
    sys.exit('mods.toml 版本 = %r，期望 %s' % (m and m.group(1), NEW))
print('[2] mods.toml version="%s"' % m.group(1))

# ---------------------------------------------------------------- [3] 逐条字节比对
changed = {n for n in new if n in base and new[n] != base[n]}
added = set(new) - set(base)
removed = set(base) - set(new)
print('[3] 变化 %d / 新增 %d / 删除 %d' % (len(changed), len(added), len(removed)))
for n in sorted(changed | added | removed):
    print('      %s  %s' % ('改' if n in changed else '增' if n in added else '删', n))
if changed != CHANGED or added != ADDED or removed != REMOVED:
    sys.exit('变化集合与预期不符：\n      少改 %r\n      多改 %r\n      多增 %r\n      多删 %r'
             % (sorted(CHANGED - changed), sorted(changed - CHANGED),
                sorted(ADDED - added), sorted(removed - REMOVED)))
check_manifest(base['META-INF/MANIFEST.MF'], new['META-INF/MANIFEST.MF'], NEW)
print('     ✔ MANIFEST 只差构建元数据；几何/贴图/Java 零漂移（只动了动画 json）')

# ---------------------------------------------------------------- [4] 生成器重跑 + 三向对账
print('[4] 生成器重跑 + 资产三向对账：')
r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'boss_v1.py')], cwd=ROOT,
                   capture_output=True, text=True, errors='replace')
tail = ((r.stdout or '') + (r.stderr or '')).strip().splitlines()
print('    %-16s %s  %s' % ('boss_v1.py', 'OK' if r.returncode == 0 else 'FAIL', (tail[-1] if tail else '')[:80]))
if r.returncode != 0:
    sys.exit('生成器重跑失败：出货件与生成器已漂开')
for label, (art_rel, src_rel, jar_rel) in BOTH.items():
    art_p = os.path.join(ROOT, art_rel.replace('/', os.sep))
    src_p = os.path.join(ROOT, src_rel.replace('/', os.sep))
    for p in (art_p, src_p):
        if not os.path.isfile(p):
            sys.exit('三向对账缺文件：%s' % p)
    a, s, j = md5(art_p), md5(src_p), hashlib.md5(new[jar_rel]).hexdigest()
    if not (a == s == j):
        sys.exit('%s 三向不一致：art=%s src=%s jar=%s' % (label, a, s, j))
    print('    %-4s art == src == jar  %s' % (label, a))

# ---------------------------------------------------------------- [5] 形状回读（成品，不是源码）
bad_new = anim_problems(new[ANIM])
if bad_new:
    sys.exit('新包的 Boss 动画仍不合 GeckoLib 契约：%s' % bad_new[:4])
anim = json.loads(new[ANIM].decode('utf-8'))
channels = sum(len(bones) for body in anim['animations'].values() for bones in body['bones'].values())
print('[5] jar 内 Boss 动画：%d 段 / %d 条通道，全部为「时间 → [x,y,z]」，per-axis 嵌套 0 处'
      % (len(anim['animations']), channels))

# ---------------------------------------------------------------- [6] 门禁
print('[6] 门禁：')
gates = [run_checker('check_boss.py'), run_checker('check_gun_resources.py'),
         run_checker('check_uzi_anim.py'), run_checker('check_uzi_art.py')]
if not all(gates):
    sys.exit('门禁未全绿，不出货')

# ---------------------------------------------------------------- [7] 部署
print('[7] 部署到 %s' % MODS)
# Windows 会锁住正在被进程打开的 jar：游戏开着时 os.remove 会 WinError 32。
# 先探一次，别把「备份了但没移除」的半成品状态留下来。
if game_running():
    print('    ⚠ 游戏正在运行：mods/ 里的旧 jar 被客户端进程占着，Windows 不允许删。')
    print('      前面 0~6 项验证全部通过，只差「换文件 + 写回资源包」这一步。')
    print('      完全退出客户端（退到主菜单不算）后重跑：python tools/_deploy_142.py')
    sys.exit(2)
os.makedirs(BACKUP, exist_ok=True)
others_before = {n: md5(os.path.join(MODS, n)) for n in os.listdir(MODS)
                 if n.endswith('.jar') and not n.startswith(PREFIX)}
installed = sorted(n for n in os.listdir(MODS) if n.startswith(PREFIX) and n.endswith('.jar'))
for n in installed:
    src_p, dst_p = os.path.join(MODS, n), os.path.join(BACKUP, n)
    if os.path.exists(dst_p) and md5(dst_p) == md5(src_p):
        print('    备份已存在，跳过 %s' % n)
    else:
        shutil.copy2(src_p, dst_p)
        print('    备份 %s -> mods_backup/  md5 %s' % (n, md5(dst_p)))
    try:
        os.remove(src_p)
    except PermissionError:
        sys.exit('删不掉 %s：客户端进程还占着它。完全退出游戏后重跑本脚本。' % n)
    print('    移除 mods/ 里的 %s' % n)
baks = sorted((os.path.join(BACKUP, n) for n in os.listdir(BACKUP) if n.endswith('.jar')),
              key=os.path.getmtime, reverse=True)
for p in baks[KEEP_BACKUPS:]:
    os.remove(p)
    print('    清理旧备份 %s' % os.path.basename(p))
print('    备份目录现有 %d 份' % min(len(baks), KEEP_BACKUPS))
target = os.path.join(MODS, JAR)
shutil.copy2(jar, target)
if md5(target) != new_md5:
    sys.exit('部署后 md5 不一致（拷坏了）')
print('    放入 %s  md5 %s' % (JAR, md5(target)))
others_after = {n: md5(os.path.join(MODS, n)) for n in os.listdir(MODS)
                if n.endswith('.jar') and not n.startswith(PREFIX)}
if others_before != others_after:
    sys.exit('其它模组被动过：%r' % [n for n in others_before if others_before.get(n) != others_after.get(n)])
print('    其它模组原样在位：%d 个 md5 全等' % len(others_after))

# ---------------------------------------------------------------- [8] 把被清空的资源包还回去
opts = os.path.join(VERSION_DIR, 'options.txt')
running = game_running()
line_no, cur = None, None
if os.path.isfile(opts):
    lines = open(opts, encoding='utf-8', errors='replace').read().splitlines()
    for i, line in enumerate(lines):
        if line.startswith('resourcePacks:'):
            line_no, cur = i, line
            break
print('[8] options.txt 的资源包：%s' % (cur if cur else '(没找到 resourcePacks 行)'))
if running is None:
    print('    ⚠ 探测不到 java 进程，为安全不写 options.txt —— 请手动在「选项 → 资源包」里勾回：')
    print('      %s' % ' / '.join(PACKS_BEFORE_FIX))
elif running:
    print('    ⚠ 游戏正在运行：现在写 options.txt 会在退出时被覆盖，跳过。')
    print('      完全退出客户端后重跑本脚本，或在「选项 → 资源包」里勾回：')
    print('      %s' % ' / '.join(PACKS_BEFORE_FIX))
elif cur is None:
    print('    ⚠ 没找到 resourcePacks 行，未改动')
elif cur.strip() not in ('resourcePacks:[]', 'resourcePacks:[""]'):
    print('    你自己已经选过资源包了（%s），不覆盖' % cur.strip())
else:
    lines[line_no] = 'resourcePacks:[%s]' % ','.join('"%s"' % p for p in PACKS_BEFORE_FIX)
    with open(opts, 'w', encoding='utf-8', newline='') as fh:
        fh.write('\n'.join(lines) + '\n')
    check = open(opts, encoding='utf-8').read().splitlines()[line_no]
    if check != lines[line_no]:
        sys.exit('options.txt 写回后读出来不一致：%r' % check)
    print('    已写回并回读确认：%s' % check)

print('\n=== 1.1.42 出货完成 ===')
print('  修复：Boss 动画通道形状（per-axis 嵌套 → 时间→[x,y,z]）')
print('        1.1.41 因此丢掉资源包 → 字体没重建 → 全屏文字方框')
print('  jar  : %s' % JAR)
print('  md5  : %s' % new_md5)
print('  部署时刻：%s' % time.strftime('%Y-%m-%d %H:%M:%S'))
print('  ⚠ Forge 无热重载：必须完全退出重开客户端（别只退到主菜单）')
