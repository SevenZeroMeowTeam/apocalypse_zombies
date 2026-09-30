"""1.1.45 出货：远程怪可 opt-in「看得见就能打」——骸骨射手不再对柱顶 / 塔上的目标一箭不放。

本次改动（相对 1.1.44）
--------------------
* 新增 `entity/ai/SightFiring`：实体级 opt-in 接口，只一个 `double sightFiringRange()`（≤0 = 不启用）。
* `entity/ai/PreyJudge`：`usable` 判序改为 `inRange`(便宜的那半) → 贴脸(3 格) → **看得见就能打** →
  `reachable`；`sightFiring()` = `mob instanceof SightFiring` && range>0 && dist²≤range² && `hasLineOfSight`。
* `entity/MarksmanSkeleton`：`implements EliteMob, GeoEntity, SightFiring`；新增 5 个射程常量
  （`BOW_RANGE=24` / `LOCK_MIN_RANGE=6` / `LOCK_MAX_RANGE=26` / `GIANT_ARROW_MIN_RANGE=6` /
  `GIANT_ARROW_MAX_RANGE=32`），三件武器的入参与 `sightFiringRange()` 全部改用这批常量（去字面量）。
* **资产零改动**：本版一个 geo / anim / png、一条数据包、一张伤害类型都不动 —— 第 [3] 项把这条钉死。

修法边界（为什么只这么改）
------------------------
* 真因是**目标调度器**，不是技能：`MobAiEnhanced` 是全局事件钩子，给所有 `Monster` 挂了
  `SharedAggroGoal(p0)` 与 `PreyTargetGoal(p1)`；后者只在「走得到」（`PreyJudge.canPathTo`，
  高度容差 1 格）时认这个猎物，够不着的猎物让它空转占住 TARGET 标志 ⇒ 排在 p3 的玩家/铁傀儡目标
  永远起不来，`getTarget()` 恒 null —— 表现成「45 秒一箭不放」。
* **不改 `EliteMob.hasTargetInRange`**：技能起手本来就要求视线 ✓，问题不在技能。
* 放宽是**实体自己 opt-in**（对齐既有 `MobAiEnhanced.hasRangedIdentity` 身份钩子范式）⇒
  爆炸半径 = 「谁实现谁才算」，近战怪零影响；**无权无条件放宽 `reachable`**（那是死锁现场）。
* **同源约束**：`sightFiringRange()` 必须与三件武器入参同一批常量 —— 报小了退回死锁、报大了会锁上
  打不到的目标，且两种情况都是**静默**的（不报错）。`check_marksman.py` 的 c6 钉住三条不变量，
  并做过负向双向验证（抠 `instanceof` 守卫 / 颠倒 `reachable` 与 `sightFiring` 判序都必红）。

实测验收（`tools/rcon_marksman_test.py`，headless 服务端 + RCON，**5/5 PASS**，第 ⑤ 条先红后绿）
  ① 满防具（保护 IV 下界合金）+ 抗性 V 的铁傀儡打 25 点 `bone_lock` → 掉 **25.0**（标签级绕过）
  ② 对照组：同样 25 点 `minecraft:generic` → 掉 **0.0**（证明防具真在减伤）
  ③ 目标 10 格外，射手自行起手并射出 `bone_lock_arrow`
  ④ 全程每 0.1 秒压制无敌帧（该伤害在满防具下掉 0 血，零噪声），骨矢仍恰好掉 **25.0**
     —— 没做 `invulnerableTime = 0` 就是 24.0
  ⑤ **柱顶靶**（柱高 3 格、柱顶无甲铁傀儡）：修前 **45 秒一箭不放** → 修后 **1.8 秒**射出骨矢

验证项（本脚本逐条跑）
--------------------
 1. 基线 = mods/ 里正在生效的 1.1.44，md5 先验身份（39b7db93d4d054bb5e2d06276634c165）。
 2. jar 内 mods.toml == 1.1.45。
 3. 相对 1.1.44 逐条字节比对：变化集合必须**恰好**是 5 改 / 1 增 / 0 删，且**资产零漂移**
    （本版只动 AI 调度那两个类 + 一个嵌套类 + 版本号，一个 geo/anim/png 都不许变）。
 4. 资产三向对账（art/marksman == src == jar）＋ 数据包契约（bone_lock + 5 张绕过标签，
    且**不得**出现 1.20.1 不存在的 `bypasses_cooldown.json`）。
 5. 门禁：check_marksman / check_bride_combat / check_boss / check_gun_resources。
 6. 部署：旧包备份到 mods_backup/（保留 3 份）再从 mods/ 移除，装入 1.1.45；其它模组 md5 全等。

用法：python tools/_deploy_145.py
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
OLD, NEW = '1.1.44', '1.1.45'
PREFIX = 'apocalypse_zombies-'
JAR = PREFIX + NEW + '.jar'
OLD_SHIPPED_MD5 = '39b7db93d4d054bb5e2d06276634c165'   # 1.1.44 出货件的唯一合法身份

PKG = 'com/apocalypse/zombies/'
RES = 'assets/apocalypse_zombies/'
SRC = 'src/main/resources/'
ANIM = RES + 'animations/marksman_skeleton.animation.json'
GEO = RES + 'geo/marksman_skeleton.geo.json'
PNG = RES + 'textures/entity/marksman_skeleton.png'

# 预期变化集合（由 build 实测写死）。本版**只动 AI 调度那条线**：
#   * MarksmanSkeleton / MarksmanSkeleton$MarksmanHooks —— 加 implements + 5 个射程常量、去字面量
#   * PreyJudge —— usable 判序 + sightFiring() 实现
#   * META-INF/mods.toml —— 版本号 1.1.44 → 1.1.45
#   * META-INF/MANIFEST.MF —— 每次构建都重写，下面断言它只差构建元数据
# 注：META-INF/NOTICE.md **这一版不再出现在变化集合里** —— 1.1.44 的出货件已经带上了工作树里那份
# （网易产出线那次改动），本次 NOTICE.md 内容与基线逐字节相同，脚本会显式核这一条。
CHANGED = {
    'META-INF/mods.toml',
    'META-INF/MANIFEST.MF',
    PKG + 'entity/MarksmanSkeleton.class',
    PKG + 'entity/MarksmanSkeleton$MarksmanHooks.class',
    PKG + 'entity/ai/PreyJudge.class',
}
ADDED = {
    PKG + 'entity/ai/SightFiring.class',
}
REMOVED = set()

# 三向对账：(台账 art, 发布件 src, 包内条目名)
BOTH = {
    'geo': ('art/marksman/marksman_skeleton.geo.json', SRC + GEO, GEO),
    'anim': ('art/marksman/marksman_skeleton.animation.json', SRC + ANIM, ANIM),
    'png': ('art/marksman/marksman_skeleton.png', SRC + PNG, PNG),
}

# 数据包契约：骨矢必须自带的绕过标签（其中 bypasses_invulnerability 只管实体 Invulnerable 标志，
# 无敌帧另由代码清零计数解决 —— 见 1.1.44 的文件头第 1 条）
TAGS = ['bypasses_armor', 'bypasses_resistance', 'bypasses_enchantments',
        'bypasses_shield', 'bypasses_invulnerability']
FORBIDDEN_TAGS = ['bypasses_cooldown']      # 1.20.1 不存在，写进来 = 整个标签被静默丢弃


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def jar_bytes(path):
    with zipfile.ZipFile(path) as zf:
        return {i.filename: zf.read(i.filename) for i in zf.infolist() if not i.is_dir()}


# 「有没有 java.exe」根本说明不了游戏在不在跑：Gradle 守护进程、VS Code 的 Gradle 语言服务器
# 也全都叫 java.exe。2026-09-30 就是被这个卡住的 —— 三个 java.exe 让本函数永远返回 True，
# 于是部署一直 sys.exit(2)，试玩还在跑坏掉的旧包。只有命令行里带 forgeclient / forgeserver /
# net.minecraft.*.Main 的进程，才是真正占着 mods/*.jar 的那个 JVM。
GAME_MARKERS = ('forgeclient', 'forgeserver', 'forgeuserdev',
                'net.minecraft.client.main.Main', 'net.minecraft.server.Main')


def game_running():
    """True=游戏在跑，False=没在跑，None=探测不出来（保守，不写 options.txt）。"""
    ps = ('Get-CimInstance Win32_Process -Filter "Name=\'java.exe\'" | '
          'ForEach-Object { $_.CommandLine }')
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', ps],
                           capture_output=True, text=True, errors='replace', timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    out = (r.stdout or '').lower()
    return any(m.lower() in out for m in GAME_MARKERS)


def lock_holders(path):
    """谁占着 path？用 Windows 重启管理器（RstrtMgr）—— 资源管理器那句「该文件正在被另一个
    程序使用」背后就是这套接口。2026-09-30 踩到的就是这一类：游戏早关了，jar 却被**压缩软件**
    开着，os.remove 抛 WinError 32，脚本只喊「客户端进程还占着它」，真实占用者是 Bandizip。"""
    if os.name != 'nt':
        return []
    import ctypes
    import uuid
    from ctypes import wintypes

    class UniqueProcess(ctypes.Structure):
        _fields_ = [('dwProcessId', wintypes.DWORD),
                    ('ProcessStartTime', wintypes.FILETIME)]

    class ProcessInfo(ctypes.Structure):
        _fields_ = [('Process', UniqueProcess),
                    ('strAppName', wintypes.WCHAR * 256),
                    ('strServiceShortName', wintypes.WCHAR * 64),
                    ('ApplicationType', wintypes.DWORD),
                    ('AppStatus', wintypes.DWORD),
                    ('TSSessionId', wintypes.DWORD),
                    ('bRestartable', wintypes.BOOL)]

    try:
        rm = ctypes.WinDLL('rstrtmgr')
        session = wintypes.DWORD()
        if rm.RmStartSession(ctypes.byref(session), 0, ctypes.c_wchar_p(str(uuid.uuid4()))) != 0:
            return []
        try:
            if rm.RmRegisterResources(session, 1, (ctypes.c_wchar_p * 1)(path),
                                      0, None, 0, None) != 0:
                return []
            needed, count, reasons = wintypes.DWORD(0), wintypes.DWORD(0), wintypes.DWORD(0)
            rc = rm.RmGetList(session, ctypes.byref(needed), ctypes.byref(count), None,
                              ctypes.byref(reasons))
            if rc not in (0, 234) or needed.value == 0:      # 234 = ERROR_MORE_DATA
                return []
            infos = (ProcessInfo * needed.value)()
            count = wintypes.DWORD(needed.value)
            if rm.RmGetList(session, ctypes.byref(needed), ctypes.byref(count), infos,
                            ctypes.byref(reasons)) != 0:
                return []
            return [(infos[i].Process.dwProcessId, infos[i].strAppName)
                    for i in range(count.value)]
        finally:
            rm.RmEndSession(session)
    except OSError:
        return []


def jar_locked(path):
    """能改名就说明「能删能换」，返回 None；被占返回占用者清单。"""
    probe = path + '.lockprobe'
    try:
        os.rename(path, probe)
    except PermissionError:
        return lock_holders(path) or [(-1, '(重启管理器也问不出来，可能存在裸句柄)')]
    except OSError:
        return None          # 文件不在之类，交给后面的步骤自己报错
    os.rename(probe, path)
    return None


def report_lock(path, indent='    '):
    held = jar_locked(path)
    if held:
        print('%s⚠ %s 正被下面这些进程占着，Windows 不允许删/替换它：' % (indent, os.path.basename(path)))
        for pid, app in held:
            print('%s    pid=%s  %s' % (indent, pid, app))
        print('%s  关掉它们再重跑（压缩软件/编辑器开着 jar、资源管理器预览、客户端没退干净……）' % indent)
    return held


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
    # 判据以退出码为准；文本扫描只认**非零**计数（`合计：PASS 13 / FAIL 0` 里的 “FAIL 0” 不是失败，
    # 1.1.44 出货第一次跑就是被这个误判拦下的）。
    ok = r.returncode == 0 and not re.search(r'FAIL\s*[1-9]|✗|不通过|错误|不符', out)
    print('    %-28s %s  %s' % (script, 'PASS' if ok else 'FAIL', tail[:80]))
    return ok


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
# 基线自检：1.1.44 已经是「骸骨射手换 GeckoLib 真骨骼 + 骨矢锁定」那一版 —— 有 geo/anim/bone_lock，
# 但**还没有** SightFiring（本版才加的）；调度器 PreyJudge 必须早就在（本版只是改它）。
for want in (GEO, ANIM, 'data/apocalypse_zombies/damage_type/bone_lock.json',
             PKG + 'entity/BoneLockArrow.class', PKG + 'entity/ai/PreyJudge.class'):
    if want not in base:
        sys.exit('基线里缺 %s —— 基线不是 1.1.44，先查清楚' % want)
if PKG + 'entity/ai/SightFiring.class' in base:
    sys.exit('基线里已经有 SightFiring.class —— 基线不是 1.1.44，先查清楚')
print('    基线确认是「已含 marksman geo/anim/bone_lock、尚无 SightFiring」的 1.1.44')

# ---------------------------------------------------------------- [1] 新包
jar = os.path.join(ROOT, 'build', 'libs', JAR)
if not os.path.isfile(jar):
    sys.exit('没有 %s，先 ./gradlew clean build' % jar)
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
print('[3] 变化 %d / 新增 %d / 删除 %d  （预期 %d / %d / %d）'
      % (len(changed), len(added), len(removed), len(CHANGED), len(ADDED), len(REMOVED)))
for n in sorted(changed | added | removed):
    print('      %s  %s' % ('改' if n in changed else '增' if n in added else '删', n))
if changed != CHANGED or added != ADDED or removed != REMOVED:
    sys.exit('变化集合与预期不符：\n      少改 %r\n      多改 %r\n      少增 %r\n      多增 %r\n      少删 %r\n      多删 %r'
             % (sorted(CHANGED - changed), sorted(changed - CHANGED),
                sorted(ADDED - added), sorted(added - ADDED),
                sorted(REMOVED - removed), sorted(removed - REMOVED)))
check_manifest(base['META-INF/MANIFEST.MF'], new['META-INF/MANIFEST.MF'], NEW)
# **资产零漂移**：本版只动 AI 调度，geo / anim / png / 数据包一个字节都不许变
ASSET_RE = re.compile(r'\.(png|json|txt|mcmeta|ogg|lang)$')
DRIFT = [n for n in sorted(changed | added | removed) if ASSET_RE.search(n)]
if DRIFT:
    sys.exit('本版声明「资产零改动」，却动了这些：%r' % DRIFT)
if base.get('META-INF/NOTICE.md') != new.get('META-INF/NOTICE.md'):
    sys.exit('META-INF/NOTICE.md 与 1.1.44 不一致 —— 变化集合里没它，内容却变了（构建混入了工作树改动？）')
print('    ✔ MANIFEST 只差构建元数据；NOTICE.md 与基线逐字节相同；'
      'geo/anim/png/数据包**零改动**，全部差异落在 AI 调度那三个类与版本号上')

# ---------------------------------------------------------------- [4] 三向对账 + 数据包契约
print('[4] 资产三向对账 + 数据包契约：')
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

dmg = json.loads(new['data/apocalypse_zombies/damage_type/bone_lock.json'].decode('utf-8'))
print('    bone_lock 伤害类型字段：%s' % ', '.join(sorted(dmg)))
for tag in TAGS:
    entry = 'data/minecraft/tags/damage_type/%s.json' % tag
    if entry not in new:
        sys.exit('缺标签文件 %s' % entry)
    values = json.loads(new[entry].decode('utf-8')).get('values') or []
    if 'apocalypse_zombies:bone_lock' not in values:
        sys.exit('%s 里没有 apocalypse_zombies:bone_lock：%r' % (tag, values))
for bad in FORBIDDEN_TAGS:
    if 'data/minecraft/tags/damage_type/%s.json' % bad in new:
        sys.exit('出现了 1.20.1 不存在的标签 %s.json —— 整个标签会被静默丢弃' % bad)
print('    5 张绕过标签都含 bone_lock；没有 1.20.1 不存在的标签名')

# ---------------------------------------------------------------- [5] 门禁
print('[5] 门禁：')
gates = [run_checker('check_marksman.py'), run_checker('check_bride_combat.py'),
         run_checker('check_boss.py'), run_checker('check_gun_resources.py')]
if not all(gates):
    sys.exit('门禁未全绿，不出货')

# ---------------------------------------------------------------- [6] 部署
print('[6] 部署到 %s' % MODS)
if game_running():
    print('    ⚠ 游戏正在运行：mods/ 里的旧 jar 被客户端进程占着，Windows 不允许删。')
    print('      前面 0~5 项验证全部通过，只差「换文件」这一步。')
    print('      完全退出客户端（退到主菜单不算）后重跑：python tools/_deploy_145.py')
    sys.exit(2)
os.makedirs(BACKUP, exist_ok=True)
others_before = {n: md5(os.path.join(MODS, n)) for n in os.listdir(MODS)
                 if n.endswith('.jar') and not n.startswith(PREFIX)}
installed = sorted(n for n in os.listdir(MODS) if n.startswith(PREFIX) and n.endswith('.jar'))
blocked = {n: report_lock(os.path.join(MODS, n)) for n in installed}
if any(blocked.values()):
    print('    前面 0~5 项验证全部通过，只差「换文件」这一步。')
    sys.exit(2)
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
        report_lock(src_p, indent='      ')
        sys.exit('删不掉 %s：上面那个进程还占着它。关掉之后重跑本脚本。' % n)
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

# ---------------------------------------------------------------- [7] options.txt 的资源包
# 1.1.41 的资源重载失败把用户的资源包清空过一次（resourcePacks:[]）；这里只在它**确实是空**时
# 写回旧值，不覆盖你自己选的组合。
PACKS_BEFORE_FIX = ['file/apocalypse_zombies-borrowed-assets.zip',
                    'file/Minecraft-Mod-Language-Modpack-Converted-1.20.1.zip']
opts = os.path.join(VERSION_DIR, 'options.txt')
running = game_running()
lines = []
line_no, cur = None, None
if os.path.isfile(opts):
    lines = open(opts, encoding='utf-8', errors='replace').read().splitlines()
    for i, line in enumerate(lines):
        if line.startswith('resourcePacks:'):
            line_no, cur = i, line
            break
print('[7] options.txt 的资源包：%s' % (cur if cur else '(没找到 resourcePacks 行)'))
if running is None:
    print('    ⚠ 探测不到 java 进程，为安全不写 options.txt —— 请手动在「选项 → 资源包」里勾回：')
    print('      %s' % ' / '.join(PACKS_BEFORE_FIX))
elif running:
    print('    ⚠ 游戏正在运行：现在写 options.txt 会在退出时被覆盖，跳过。')
elif cur is None:
    print('    ⚠ 没找到 resourcePacks 行，未改动')
elif cur.strip() not in ('resourcePacks:[]', 'resourcePacks:[""]'):
    print('    你自己已经选过资源包了（%s），不覆盖' % cur.strip())
else:
    assert line_no is not None          # 与 cur 同时赋值，此处必非 None
    idx = line_no
    lines[idx] = 'resourcePacks:[%s]' % ','.join('"%s"' % p for p in PACKS_BEFORE_FIX)
    with open(opts, 'w', encoding='utf-8', newline='') as fh:
        fh.write('\n'.join(lines) + '\n')
    check = open(opts, encoding='utf-8').read().splitlines()[idx]
    if check != lines[idx]:
        sys.exit('options.txt 写回后读出来不一致：%r' % check)
    print('    已写回并回读确认：%s' % check)

print('\n=== 1.1.45 出货完成 ===')
print('  内容：远程怪可 opt-in「看得见就能打」（新增 SightFiring 接口 + PreyJudge 判序）')
print('        骸骨射手不再对柱顶/塔上等「走不到」的目标一箭不放；近战怪零影响，资产零改动')
print('  jar  : %s' % JAR)
print('  md5  : %s' % new_md5)
print('  部署时刻：%s' % time.strftime('%Y-%m-%d %H:%M:%S'))
print('  ⚠ Forge 无热重载：必须完全退出重开客户端（别只退到主菜单）')
print('  ⚠ 进游戏后自查（这次要试的就是「走不到也能打」）：')
print('     1) 平地：/summon apocalypse_zombies:marksman_skeleton ~ ~ ~，退到 10 格外等它举弓 ——')
print('        一发骨矢应扣掉你最大血量的 25%')
print('     2) 柱顶：搭 3 格高的柱子站上去（或 /setblock 叠三格），射手应**约 2 秒内**射出骨矢；')
print('        修前是 45 秒一箭不放')
