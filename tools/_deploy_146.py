"""1.1.46 出货：修复尸潮之主「没有第 3 阶段」+ 追加 4 个技能。

本次改动（相对 1.1.45）
--------------------
* **真因不是阶段机，是技能轮转被一个死槽位锁死**：`ROTATION_PHASE_3` 里那一格
  `BONE_VOLLEY` 的起手门槛是「目标 ≥ 4 格」，而打近战 Boss 的唯一打法就是贴脸 ⇒
  该槽永远起不了手；轮转索引只在技能**结束**时前进 ⇒ 整张表卡住，表现成「Boss 站着不动、
  第 3 阶段一招都不放」（实测：铁傀儡活着贴到 1.5 格，`rot=3/5 cast=NONE` 空转 10s+ 后再无动作）。
* `entity/EliteAbilityDriver`：新增「干等上限 → 换槽」兜底（`Hooks.starvationTicks()` 默认 40t，
  `Hooks.onStarved()` 让子类换槽）；`onEnd` 改为把**刚播完的那一招**传给 `onEnd(finished)`
  （原来只看 `entryAbility != NONE` 就清空，会吞掉挂起等机会的入场技）。
* `entity/HordeOverlord`：`ability()` 只在入场技能真的起手时才插队（否则它自己会挡住轮转）；
  亡语收尾改用「只清负面效果」（`removeAllEffects()` 每轮一次清掉血怒那 4 条 buff =
  玩家眼里「第 3 阶段打着打着变回大僵尸」）；`debugStatus()` 加 `starved`。
* `entity/AbstractEliteZombie` / `entity/BrideZombie`：跟随驱动器签名同步（美女僵尸自己的
  本地跳过逻辑保留不动，不叠加新钩子）。
* `command/ApocalypseCommand`：`/apocalypse boss` 念出阶段机私有状态
  （`phase/cast@tick/entry/rot/rage/wail/starved`）—— headless 探针的唯一读出口。
* **4 个新技能**（枚举末尾追加，`byId` 的 ordinal 不变）：`CAGE_SLAM` 尸笼坠击（Phase 2+，
  正前方 9×5 格直线 18 伤害 + 减速 + 沿线的 6 根骨刺）、`PLAGUE_MIST` 疫雾（Phase 2+，
  铺 8 格 `AreaEffectCloud` 毒雾，僵尸对中毒免疫 ⇒ 只伤活人）、`SOUL_DRAIN` 汲魂（Phase 3，
  10 格内每个活体抽 7 点 + 虚弱，按 1.5× 反哺自己，单次上限 240）、`HORDE_SCREECH` 尸潮尖啸
  （Phase 3，16 格击退 + 8s 失明 + 再召 3 只）。轮转表 Phase 2 由 4 槽 → 5 槽、Phase 3 由 5 槽 → 9 槽。
* 资产：只动 `horde_overlord.animation.json`（8 段 → 12 段）与两条 lang。**geo / png 零改动**（本版不碰几何）。

实测验收（headless 专用服务端 + RCON）
  ① 贴脸 Phase 3 采样 90s：8 招全部出现（含 4 招新的）；`starved` 涨到 3 ⇒ 换槽路径真的走了；
     最长空窗 3.5s = 「技能间隔 24t + 干等上限 40t + 采样 0.5s」的理论最坏值（旧缺陷是 8~12s 且不恢复）。
  ② 副作用逐条对表：傀儡依次吃到 weakness / blindness / poison / slowness / wither；骨刺 6 根、
     雾团 1 个、僵尸数 11；**Boss 血量在无外因下三次自增**（汲魂 1.5× 反哺）。
  ③ 跨 630 亡语线：`wail=true` → `entry=DEATH_WAIL` 被消费 → 傀儡吃 wither，**血怒 4 条 buff 仍在**。
  ④ 回归：骸骨射手 `tools/rcon_marksman_test.py` **5/5 PASS**（共享驱动器改动没伤它）。

验证项（本脚本逐条跑）
--------------------
 1. 基线 = mods/ 里正在生效的 1.1.45，md5 先验身份（79b845e4bab9b29d53168cfd0e6c2512）。
 2. jar 内 mods.toml == 1.1.46。
 3. 相对 1.1.45 逐条字节比对：必须恰好 14 改 / 0 增 / 0 删，且**资产只许动动画 JSON + 两条 lang**
    （geo/png 出现在变化集合里就是几何被动过，立刻停）；`META-INF/NOTICE.md` 与基线逐字节相同。
 4. 生成器自校验（`tools/boss_v1.py`）→ 三向对账（art/boss == src == jar：geo / anim / png）。
 5. 包内断言：新包动画 12 段且含 4 个新剪辑名；`HordeOverlord.class` 含 4 个新剪辑字面量与 `starved`；
    `EliteAbilityDriver.class` 含 `onStarved`；基线里这几样**必须都没有**。
 6. 门禁：check_boss / check_bride_combat / check_marksman / check_gun_resources。
 7. 部署：旧包备份到 mods_backup/（保留 3 份）再从 mods/ 移除，装入 1.1.46；其它模组 md5 全等。
 8. options.txt 的资源包：只在它确实是空的时候写回，不覆盖你自己选的组合。

用法：python tools/_deploy_146.py
"""
import hashlib
import io
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
OLD, NEW = '1.1.45', '1.1.46'
PREFIX = 'apocalypse_zombies-'
JAR = PREFIX + NEW + '.jar'
OLD_SHIPPED_MD5 = '79b845e4bab9b29d53168cfd0e6c2512'   # 1.1.45 出货件的唯一合法身份

PKG = 'com/apocalypse/zombies/'
RES = 'assets/apocalypse_zombies/'
SRC = 'src/main/resources/'
ANIM = RES + 'animations/horde_overlord.animation.json'
GEO = RES + 'geo/horde_overlord.geo.json'
PNG = RES + 'textures/entity/horde_overlord.png'

#: 1.1.46 新增的 4 个剪辑（顺序 = 枚举里追加的顺序）
NEW_CLIPS = ['skill_cage', 'skill_mist', 'skill_drain', 'skill_screech']

# 预期变化集合（由 build 实测写死）：14 改 / 0 增 / 0 删
CHANGED = {
    'META-INF/mods.toml',
    'META-INF/MANIFEST.MF',
    ANIM,
    RES + 'lang/en_us.json',
    RES + 'lang/zh_cn.json',
    PKG + 'command/ApocalypseCommand.class',
    PKG + 'entity/AbstractEliteZombie.class',
    PKG + 'entity/AbstractEliteZombie$ZombieHooks.class',
    PKG + 'entity/BrideZombie.class',
    PKG + 'entity/EliteAbility.class',
    PKG + 'entity/EliteAbilityDriver.class',
    PKG + 'entity/EliteAbilityDriver$Hooks.class',
    PKG + 'entity/HordeOverlord.class',
    PKG + 'entity/HordeOverlord$1.class',
}
ADDED = set()
REMOVED = set()

#: 本版允许变动的资产白名单 —— 几何（geo/png）不许出现，本版不碰模型
ASSET_ALLOWED = {ANIM, RES + 'lang/en_us.json', RES + 'lang/zh_cn.json'}
ASSET_RE = re.compile(r'\.(png|json|txt|mcmeta|ogg|lang)$')

# 三向对账：(台账 art, 发布件 src, 包内条目名)
BOTH = {
    'geo': ('art/boss/horde_overlord.geo.json', SRC + GEO, GEO),
    'anim': ('art/boss/horde_overlord.animation.json', SRC + ANIM, ANIM),
    'png': ('art/boss/horde_overlord.png', SRC + PNG, PNG),
}


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def jar_bytes(path):
    with zipfile.ZipFile(path) as zf:
        return {i.filename: zf.read(i.filename) for i in zf.infolist() if not i.is_dir()}


def clip_names(raw):
    return sorted(json.loads(raw.decode('utf-8'))['animations'])


# 「有没有 java.exe」根本说明不了游戏在不在跑：Gradle 守护进程、VS Code 的 Gradle 语言服务器
# 也全都叫 java.exe。只有命令行里带 forgeclient / forgeserver / net.minecraft.*.Main 的进程，
# 才是真正占着 mods/*.jar 的那个 JVM。
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
    程序使用」背后就是这套接口。游戏早关了 jar 却被压缩软件开着时，os.remove 只会抛
    WinError 32，光看 java.exe 是查不出来的。"""
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
        print('%s⚠ %s 正被下面这些进程占着，Windows 不允许删/替换它：'
              % (indent, os.path.basename(path)))
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
    r = subprocess.run([sys.executable, p], cwd=ROOT, capture_output=True, text=True,
                       errors='replace')
    out = ((r.stdout or '') + (r.stderr or '')).strip()
    tail = out.splitlines()[-1] if out else ''
    # 判据以退出码为准；文本扫描只认**非零**计数（`合计：PASS 13 / FAIL 0` 里的 “FAIL 0” 不是失败）。
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
print('[0] 基线 %s = %s  条目 %d  md5 %s' % (OLD, os.path.basename(base_path), len(base),
                                            OLD_SHIPPED_MD5))
# 基线自检：1.1.45 已经是「骸骨射手看得见就能打」那一版 —— 有 SightFiring，但 Boss 那边
# **还没有**第 7~10 条技能枚举、没有轮转兜底、动画只有 8 段。
for want in ('com/apocalypse/zombies/entity/ai/SightFiring.class', GEO, ANIM,
             PKG + 'entity/HordeOverlord.class'):
    if want not in base:
        sys.exit('基线里缺 %s —— 基线不是 1.1.45，先查清楚' % want)
old_clips = clip_names(base[ANIM])
if len(old_clips) != 8:
    sys.exit('基线的 Boss 动画不是 8 段而是 %d 段：%r' % (len(old_clips), old_clips))
if any(c in base[ANIM].decode('utf-8') for c in NEW_CLIPS):
    sys.exit('基线里已经有新剪辑了 —— 基线不是 1.1.45，先查清楚')
if b'onStarved' in base[PKG + 'entity/EliteAbilityDriver.class']:
    sys.exit('基线的驱动器里已经有 onStarved —— 基线不是 1.1.45，先查清楚')
if b'starved' in base[PKG + 'entity/HordeOverlord.class']:
    sys.exit('基线的 HordeOverlord 里已经有 starved —— 基线不是 1.1.45，先查清楚')
print('    基线确认是「8 段动画、无新技能、驱动器无 onStarved、HordeOverlord 无 starved」的 1.1.45')

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
    print('      %s %s' % ('改' if n in changed else '增' if n in added else '删', n))
if changed != CHANGED or added != ADDED or removed != REMOVED:
    sys.exit('变化集合与预期不符：\n      少改 %r\n      多改 %r\n      少增 %r\n      多增 %r\n      少删 %r\n      多删 %r'
             % (sorted(CHANGED - changed), sorted(changed - CHANGED),
                sorted(ADDED - added), sorted(added - ADDED),
                sorted(REMOVED - removed), sorted(removed - REMOVED)))
check_manifest(base['META-INF/MANIFEST.MF'], new['META-INF/MANIFEST.MF'], NEW)
# 资产白名单：本版只许动 Boss 动画 JSON + 两条 lang，**几何（geo/png）零改动**
drift = {n for n in changed | added | removed if ASSET_RE.search(n)}
if drift - ASSET_ALLOWED:
    sys.exit('本版声明「不碰几何」，却动了白名单外的资产：%r' % sorted(drift - ASSET_ALLOWED))
if GEO in changed or PNG in changed:
    sys.exit('geo/png 出现在变化集合里 —— 本版不应改动模型几何，先查清楚')
if base.get('META-INF/NOTICE.md') != new.get('META-INF/NOTICE.md'):
    sys.exit('META-INF/NOTICE.md 与 1.1.45 不一致 —— 变化集合里没它，内容却变了（构建混入了工作树改动？）')
print('    ✔ MANIFEST 只差构建元数据；NOTICE.md 与基线逐字节相同；'
      '资产只动动画 JSON + 两条 lang，geo/png 零改动')

# ---------------------------------------------------------------- [4] 生成器 + 三向对账
print('[4] 生成器自校验 + 资产三向对账：')
if not run_checker('boss_v1.py'):
    sys.exit('生成器自校验没过，不出货（geo/anim 与生成器输出不一致）')
for label, (art_rel, src_rel, jar_rel) in BOTH.items():
    art_p = os.path.join(ROOT, art_rel.replace('/', os.sep))
    src_p = os.path.join(ROOT, src_rel.replace('/', os.sep))
    for p in (art_p, src_p):
        if not os.path.isfile(p):
            sys.exit('三向对账缺文件：%s' % p)
    a, s, j = md5(art_p), md5(src_p), hashlib.md5(new[jar_rel]).hexdigest()
    if not (a == s == j):
        sys.exit('%s 三向不一致：art=%s src=%s jar=%s' % (label, a, s, j))
    if label == 'anim' and a != s:
        sys.exit('动画被改过却没同步到发布件')
    print('    %-4s art == src == jar  %s' % (label, a))

# ---------------------------------------------------------------- [5] 包内断言
print('[5] 包内契约：')
clips = clip_names(new[ANIM])
if len(clips) != 12 or not set(NEW_CLIPS) <= set(clips):
    sys.exit('新包动画不是 12 段 / 缺新剪辑：%r' % clips)
print('    动画 %d 段，含新剪辑 %s' % (len(clips), ', '.join(NEW_CLIPS)))
boss_cls = new[PKG + 'entity/HordeOverlord.class']
driver_cls = new[PKG + 'entity/EliteAbilityDriver.class']
ability_cls = new[PKG + 'entity/EliteAbility.class']
missing = [c for c in NEW_CLIPS if c.encode() not in boss_cls]
if missing:
    sys.exit('HordeOverlord.class 里缺剪辑名字面量：%r（常量没接上？）' % missing)
if b'starved' not in boss_cls:
    sys.exit('HordeOverlord.class 里没有 starved —— 阶段机读出口没接上')
if b'onStarved' not in driver_cls or b'starvationTicks' not in driver_cls:
    sys.exit('EliteAbilityDriver.class 里没有 onStarved / starvationTicks —— 换槽兜底没编进去')
for enum_name in ('CAGE_SLAM', 'PLAGUE_MIST', 'SOUL_DRAIN', 'HORDE_SCREECH'):
    if enum_name.encode() not in ability_cls:
        sys.exit('EliteAbility.class 里没有 %s' % enum_name)
# 旧的四条不许丢（append-only 的语义：只加不删）
for enum_name in ('BOSS_SWEEP', 'BONE_VOLLEY', 'RAISE_HORDE', 'GROUND_QUAKE',
                  'BLOOD_RAGE', 'DEATH_WAIL', 'VEIL_CHOP'):
    if enum_name.encode() not in ability_cls:
        sys.exit('EliteAbility.class 里丢了旧枚举 %s（append-only 被破坏）' % enum_name)
print('    4 个新剪辑字面量 + starved + onStarved/starvationTicks + 新旧 11 条枚举全在')
for lang in ('en_us', 'zh_cn'):
    entry = json.loads(new[RES + 'lang/%s.json' % lang].decode('utf-8'))
    if 'command.apocalypse_zombies.boss.none' not in entry:
        sys.exit('%s.json 缺 /apocalypse boss 的提示文案' % lang)
print('    中英双语都带 /apocalypse boss 的文案')

# ---------------------------------------------------------------- [6] 门禁
print('[6] 门禁：')
gates = [run_checker('check_boss.py'), run_checker('check_bride_combat.py'),
         run_checker('check_marksman.py'), run_checker('check_gun_resources.py')]
if not all(gates):
    sys.exit('门禁未全绿，不出货')

# ---------------------------------------------------------------- [7] 部署
print('[7] 部署到 %s' % MODS)
if game_running():
    print('    ⚠ 游戏正在运行：mods/ 里的旧 jar 被客户端进程占着，Windows 不允许删。')
    print('      前面 0~6 项验证全部通过，只差「换文件」这一步。')
    print('      完全退出客户端（退到主菜单不算）后重跑：python tools/_deploy_146.py')
    sys.exit(2)
os.makedirs(BACKUP, exist_ok=True)
others_before = {n: md5(os.path.join(MODS, n)) for n in os.listdir(MODS)
                 if n.endswith('.jar') and not n.startswith(PREFIX)}
installed = sorted(n for n in os.listdir(MODS) if n.startswith(PREFIX) and n.endswith('.jar'))
blocked = {n: report_lock(os.path.join(MODS, n)) for n in installed}
if any(blocked.values()):
    print('    前面 0~6 项验证全部通过，只差「换文件」这一步。')
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
print('    备份目录现有 %d 份：%s'
      % (min(len(baks), KEEP_BACKUPS),
         ', '.join(os.path.basename(p) for p in baks[:KEEP_BACKUPS])))
target = os.path.join(MODS, JAR)
shutil.copy2(jar, target)
if md5(target) != new_md5:
    sys.exit('部署后 md5 不一致（拷坏了）')
print('    放入 %s  md5 %s' % (JAR, md5(target)))
others_after = {n: md5(os.path.join(MODS, n)) for n in os.listdir(MODS)
                if n.endswith('.jar') and not n.startswith(PREFIX)}
if others_before != others_after:
    sys.exit('其它模组被动过：%r'
             % [n for n in others_before if others_before.get(n) != others_after.get(n)])
print('    其它模组原样在位：%d 个 md5 全等' % len(others_after))

# ---------------------------------------------------------------- [8] options.txt 的资源包
# 1.1.41 的资源重载失败把用户的资源包清空过一次（resourcePacks:[]）；这里只在它**确实是空**时
# 写回旧值，不覆盖你自己选的组合。
PACKS_BEFORE_FIX = ['file/apocalypse_zombies-borrowed-assets.zip',
                    'file/Minecraft-Mod-Language-Modpack-Converted-1.20.1.zip']
opts = os.path.join(VERSION_DIR, 'options.txt')
running = game_running()
lines = []
line_no, cur = None, None
if os.path.isfile(opts):
    lines = io.open(opts, encoding='utf-8', errors='replace').read().splitlines()
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
elif cur is None:
    print('    ⚠ 没找到 resourcePacks 行，未改动')
elif cur.strip() not in ('resourcePacks:[]', 'resourcePacks:[""]'):
    print('    你自己已经选过资源包了（%s），不覆盖' % cur.strip())
else:
    assert line_no is not None          # 与 cur 同时赋值，此处必非 None
    lines[line_no] = 'resourcePacks:[%s]' % ','.join('"%s"' % p for p in PACKS_BEFORE_FIX)
    with io.open(opts, 'w', encoding='utf-8', newline='') as fh:
        fh.write('\n'.join(lines) + '\n')
    check = io.open(opts, encoding='utf-8').read().splitlines()[line_no]
    if check != lines[line_no]:
        sys.exit('options.txt 写回后读出来不一致：%r' % check)
    print('    已写回并回读确认：%s' % check)

print('\n=== 1.1.46 出货完成 ===')
print('  内容：修复尸潮之主「没有第 3 阶段」（轮转死锁）＋ 追加 4 个技能（尸笼坠击 / 疫雾 / 汲魂 / 尸潮尖啸）')
print('  jar  : %s' % JAR)
print('  md5  : %s' % new_md5)
print('  部署时刻：%s' % time.strftime('%Y-%m-%d %H:%M:%S'))
print('  ⚠ Forge 无热重载：必须完全退出重开客户端（别只退到主菜单）')
print('  ⚠ 进游戏后自查（贴脸打，就能看到修复）：')
print('     1) /summon apocalypse_zombies:horde_overlord ~ ~1 ~ 召出它，再 /apocalypse boss 看阶段机状态')
print('     2) /damage @e[type=apocalypse_zombies:horde_overlord,limit=1] 2900 minecraft:generic 直接进第 3 阶段')
print('     3) 贴脸站 10 秒：应连出尸笼坠击 / 疫雾（脚下毒雾）/ 汲魂（它回血）/ 尸潮尖啸（击退+失明）')
print('        修前这里是「站着不动、一招不放」')
print('     4) 血怒那 4 条 buff 在亡语后仍在（不再被清）')
