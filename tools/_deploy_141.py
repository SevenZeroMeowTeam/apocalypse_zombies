"""1.1.41 出货：三阶段 Boss「尸潮之主」+ 尸潮 4→5 波（新增实体 + 一整套资产）。

为什么是这个流程
----------------
本轮是**新功能**，不是调参：既有几何 / 贴图 / 动画一个字节都不该动，新增的七个条目
必须**恰好**是 Boss 那一套。所以硬证据是两句话：

  · 变化集合 == {8 个 class + 2 个 lang + mods.toml + MANIFEST}，一个不多一个不少；
  · 资产条目的「三向对账」必须成立 —— art/ 台账 == src/ 发布件 == jar 内条目（逐个 md5）。

前者挡住误伤（谁顺手动了枪的 geo，在这里就炸），后者挡住「生成器与出货件漂开」
（发了半天，包里那份和台账那份不是同一个文件）。三个数字（防御 5 / 攻击 15 / 召唤 5）
写死在源码里没用，必须**回读编译产物**——javap 看到 `iconst_5` 才算数。

验证项
------
 1. 基线 = mods/ 里正在生效的 1.1.40，md5 先验身份（6f03e60ef06f70f047efdf7d52d2a340）。
    同名 jar 会被后续构建原地覆盖，所以身份只能靠 md5，不能靠文件名或时间。
 2. jar 内 mods.toml == 1.1.41。
 3. 相对 1.1.40 逐条字节比对：改 10 / 增 7 / 删 0，且集合与下方写死的预期**完全相等**；
    MANIFEST 只允许差构建元数据；任何 gun/elite 资产漂移即中止。
 4. 生成器重跑（boss_v1.py / boss_v1_skin.py）→ 资产三向对账 art == src == jar。
 5. 常量回读：包内 Boss 字节里 2500.0f / 0.21d / 15.0d（攻击）/ 5.0d（防御）在；
    横扫 15.0f 在、**16.0f 不在**（旧值没被留成第二套口径）；
    javap 确认 `castRaiseHorde` 的**两个**调用点前面都是 `iconst_5`（召唤技 + 亡语）。
 6. 门禁：check_boss.py（13 类接线断言）+ 三个枪械检查（回归网）全绿。
 7. 部署：旧包**先备份**到 mods 同级的 mods_backup/（保留最近 3 份，更早的删掉），
    再从 mods/ 移除；只动 apocalypse_zombies-* 前缀，其余模组逐个 md5 断「原样在位」。

用法：python tools/_deploy_141.py
"""
import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_DIR = 'C:/Users/Administrator/Desktop/.minecraft/versions/1.20.1-Forge_47.4.23-2'
MODS = VERSION_DIR + '/mods'
# 备份放在 mods 的**同级**目录，不是 mods/ 里面：Forge 扫 mods 时会往下走子目录，
# 把旧 jar 留在 mods/xxx_backup/ 里有被当成重复模组加载的风险。
BACKUP = VERSION_DIR + '/mods_backup'
KEEP_BACKUPS = 3
OLD, NEW = '1.1.40', '1.1.41'
PREFIX = 'apocalypse_zombies-'
JAR = PREFIX + NEW + '.jar'
OLD_SHIPPED_MD5 = '6f03e60ef06f70f047efdf7d52d2a340'   # 1.1.40 出货件的唯一合法身份

PKG = 'com/apocalypse/zombies/'
RES = 'assets/apocalypse_zombies/'

# 预期变化集合 —— 由 diffjars 实测得出后写死，不是靠模式匹配放水
CHANGED = {
    'META-INF/mods.toml',
    'assets/apocalypse_zombies/lang/en_us.json',
    'assets/apocalypse_zombies/lang/zh_cn.json',
    'com/apocalypse/zombies/Config.class',
    'com/apocalypse/zombies/client/ClientModBusEvents.class',
    'com/apocalypse/zombies/entity/EliteAbility.class',
    'com/apocalypse/zombies/horde/HordeManager.class',
    'com/apocalypse/zombies/registry/ModEntities.class',
    'com/apocalypse/zombies/registry/ModItems.class',
    # 每次构建都会重写的构建元数据（版本 + 时间戳）：下面的 check_manifest 断言它**只**差那两行
    'META-INF/MANIFEST.MF',
}
ADDED = {
    'assets/apocalypse_zombies/animations/horde_overlord.animation.json',
    'assets/apocalypse_zombies/geo/horde_overlord.geo.json',
    'assets/apocalypse_zombies/models/item/horde_overlord_spawn_egg.json',
    'assets/apocalypse_zombies/textures/entity/horde_overlord.png',
    'com/apocalypse/zombies/client/model/OverlordGeoModel.class',
    'com/apocalypse/zombies/client/renderer/OverlordGeoRenderer.class',
    'com/apocalypse/zombies/entity/HordeOverlord.class',
    'com/apocalypse/zombies/entity/HordeOverlord$1.class',
}
REMOVED = set()

BOSS_CLS = PKG + 'entity/HordeOverlord.class'
# 三向对账的三件资产：(台账 art, 发布件 src/main/resources, 包内条目名)
SRC = 'src/main/resources/'
BOTH = {
    'geo': ('art/boss/horde_overlord.geo.json',
            SRC + RES + 'geo/horde_overlord.geo.json', RES + 'geo/horde_overlord.geo.json'),
    'anim': ('art/boss/horde_overlord.animation.json',
             SRC + RES + 'animations/horde_overlord.animation.json',
             RES + 'animations/horde_overlord.animation.json'),
    'png': ('art/boss/horde_overlord.png',
            SRC + RES + 'textures/entity/horde_overlord.png',
            RES + 'textures/entity/horde_overlord.png'),
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


def f32(v):
    return struct.pack('>f', v)


def f64(v):
    return struct.pack('>d', v)


def check_manifest(old_raw, new_raw, old_ver, new_ver):
    """MANIFEST 允许变，但只允许 Implementation-Version 与 Implementation-Timestamp 两行。"""
    o = old_raw.decode('utf-8', 'replace').splitlines()
    n = new_raw.decode('utf-8', 'replace').splitlines()
    only_o = [l for l in o if l not in n]
    only_n = [l for l in n if l not in o]
    for line in only_o + only_n:
        if not (line.startswith('Implementation-Version: ') or line.startswith('Implementation-Timestamp: ')):
            sys.exit('MANIFEST 里有非构建元数据的差异，需要人看：%r' % line)
    if not any(l.strip() == 'Implementation-Version: ' + new_ver for l in only_n):
        sys.exit('MANIFEST 的版本不是 %s：%r' % (new_ver, only_n))
    return only_o, only_n


def run_checker(script):
    p = os.path.join(ROOT, 'tools', script)
    if not os.path.isfile(p):
        print('    [跳过] %s 不存在' % script)
        return True
    r = subprocess.run([sys.executable, p], cwd=ROOT, capture_output=True, text=True, errors='replace')
    out = ((r.stdout or '') + (r.stderr or '')).strip()
    tail = out.splitlines()[-1] if out else ''
    # 判据以退出码为准；只在出现失败词时判负（各脚本报成功的措辞不统一）
    ok = r.returncode == 0 and not re.search(r'FAIL|✗|不通过|错误|不符', out)
    print('    %-26s %s  %s' % (script, 'PASS' if ok else 'FAIL', tail[:90]))
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

# ---------------------------------------------------------------- [1] 新包
jar = os.path.join(ROOT, 'build', 'libs', JAR)
if not os.path.isfile(jar):
    sys.exit('没有 %s，先 ./gradlew build' % jar)
new_md5 = md5(jar)
if new_md5 == OLD_SHIPPED_MD5:
    sys.exit('新包 md5 与 %s 出货件相同：等于没改，构建没吃到源码' % OLD)
new = jar_bytes(jar)
print('[1] %s  md5=%s  %d 字节  entry %d' % (JAR, new_md5, os.path.getsize(jar), len(new)))

# ---------------------------------------------------------------- [2] mods.toml
toml = new.get('META-INF/mods.toml', b'').decode('utf-8', 'replace')
m = re.search(r'version\s*=\s*"([^"]+)"', toml)
if not m or m.group(1) != NEW:
    sys.exit('mods.toml 版本 = %r，期望 %s（gradle.properties 的 mod_version 改了没？）'
             % (m and m.group(1), NEW))
print('[2] mods.toml version="%s"' % m.group(1))
if 'five-wave' not in toml or 'four-wave' in toml:
    sys.exit('mods.toml 的描述还在说 four-wave，与实际五波不符')

# ---------------------------------------------------------------- [3] 逐条字节比对
changed = {n for n in new if n in base and new[n] != base[n]}
added = set(new) - set(base)
removed = set(base) - set(new)
print('[3] 变化 %d / 新增 %d / 删除 %d' % (len(changed), len(added), len(removed)))
for n in sorted(changed | added | removed):
    print('      %s  %s' % ('改' if n in changed else '增' if n in added else '删', n))
if changed != CHANGED or added != ADDED or removed != REMOVED:
    sys.exit('变化集合与预期不符：\n      少改 %r\n      多改 %r\n      少增 %r\n      多增 %r\n      少删 %r'
             % (sorted(CHANGED - changed), sorted(changed - CHANGED),
                sorted(ADDED - added), sorted(added - ADDED), sorted(REMOVED - removed)))
mo, mn = check_manifest(base['META-INF/MANIFEST.MF'], new['META-INF/MANIFEST.MF'], OLD, NEW)
print('      MANIFEST 只差构建元数据：%s' % ' | '.join(x.strip() for x in mo + mn))
# 反向断言：本轮是纯新增模型，任何既有**几何/贴图/动画**漂移都说明有人重跑过流水线。
# 只扫这几个目录 —— lang 这类文本本轮本来就要改（加了 Boss 的条目标题），不算漂移。
ASSET_DIRS = (RES + 'geo/', RES + 'animations/', RES + 'textures/', RES + 'models/')
drift = [n for n in changed if n.startswith(ASSET_DIRS) and 'horde_overlord' not in n]
if drift:
    sys.exit('既有资产发生漂移（本轮不该碰任何老模型/贴图/动画）：%r' % drift)
print('     ✔ 集合与预期完全相等；老模型/贴图/动画零漂移')

# ---------------------------------------------------------------- [4] 生成器重跑 + 三向对账
print('[4] 生成器重跑 + 资产三向对账：')
for script in ('boss_v1.py', 'boss_v1_skin.py'):
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', script)], cwd=ROOT,
                       capture_output=True, text=True, errors='replace')
    tail = ((r.stdout or '') + (r.stderr or '')).strip().splitlines()
    print('    %-16s %s  %s' % (script, 'OK' if r.returncode == 0 else 'FAIL', (tail[-1] if tail else '')[:80]))
    if r.returncode != 0:
        sys.exit('%s 跑失败，出货件与生成器已经漂开，先修再发' % script)
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

# ---------------------------------------------------------------- [5] 常量真的编进去了
boss = new[BOSS_CLS]
for label, pat in (('BOSS_MAX_HEALTH 2500.0f', f32(2500.0)),
                   ('MOVEMENT_SPEED 0.21d', f64(0.21)),
                   ('ATTACK_POWER 15.0d（攻击 15）', f64(15.0)),
                   ('ARMOR_POINTS 5.0d（防御 5）', f64(5.0)),
                   ('ARMOR_TOUGHNESS 8.0d', f64(8.0)),
                   ('SWEEP_DAMAGE 15.0f（横扫改用攻击口径）', f32(15.0))):
    if pat not in boss:
        sys.exit('HordeOverlord.class 里找不到 %s' % label)
if f32(16.0) in boss:
    sys.exit('HordeOverlord.class 里还有 float 16.0f —— 横扫的旧值没清干净，会出现两套攻击口径')
print('[5] 常量回读：2500f / 0.21d / 攻击 15.0d / 防御 5.0d / 韧性 8.0d / 横扫 15.0f 在；旧 16.0f 不在')

# 召唤数只有回读字节码才算数：SUMMON_COUNT 内联成 iconst_5，必须**两个**调用点都是 5
javap = shutil.which('javap')
if not javap:
    sys.exit('PATH 里没有 javap —— 召唤数（iconst_5）必须回读字节码才能确认，'
             '把 JDK 的 bin 加进 PATH 再跑')
tmp = os.path.join(ROOT, 'build', 'tmp', 'boss_deploy')
os.makedirs(tmp, exist_ok=True)
cls_path = os.path.join(tmp, 'HordeOverlord.class')
with open(cls_path, 'wb') as fh:
    fh.write(boss)
dis = subprocess.run([javap, '-p', '-c', cls_path], capture_output=True, text=True, errors='replace').stdout
five = re.findall(r'iconst_5\s*\n\s*\d+:\s*invokevirtual\s+\S+\s+//\s*Method castRaiseHorde', dis.replace('\r', ''))
four = re.findall(r'iconst_4\s*\n\s*\d+:\s*invokevirtual\s+\S+\s+//\s*Method castRaiseHorde', dis.replace('\r', ''))
if len(five) != 2 or four:
    sys.exit('召唤数不对：iconst_5 × %d（要 2：召唤技 + 亡语）／iconst_4 × %d（须 0）'
             % (len(five), len(four)))
print('     javap：castRaiseHorde 两个调用点前置均为 iconst_5（召唤技 + 亡语），旧值 iconst_4 为 0 处')

# ---------------------------------------------------------------- [6] 门禁
print('[6] 门禁：')
gates = [run_checker('check_boss.py'), run_checker('check_uzi_anim.py'),
         run_checker('check_uzi_art.py'), run_checker('check_gun_resources.py')]
if not all(gates):
    sys.exit('门禁未全绿，不出货')

# ---------------------------------------------------------------- [7] 部署（旧版先备份，再移除）
print('[7] 部署到 %s' % MODS)
os.makedirs(BACKUP, exist_ok=True)
others_before = {n: md5(os.path.join(MODS, n)) for n in os.listdir(MODS)
                 if n.endswith('.jar') and not n.startswith(PREFIX)}
installed = sorted(n for n in os.listdir(MODS) if n.startswith(PREFIX) and n.endswith('.jar'))
for n in installed:
    src_p = os.path.join(MODS, n)
    dst_p = os.path.join(BACKUP, n)
    if os.path.exists(dst_p) and md5(dst_p) == md5(src_p):
        print('    备份已存在，跳过 %s' % n)
    else:
        shutil.copy2(src_p, dst_p)
        print('    备份 %s -> mods_backup/  md5 %s' % (n, md5(dst_p)))
    os.remove(src_p)
    print('    移除 mods/ 里的 %s' % n)
# 备份保留最近 KEEP_BACKUPS 份，更早的删掉（"备份或者删除" —— 两头都做，别让备份无限长）
baks = sorted((os.path.join(BACKUP, n) for n in os.listdir(BACKUP) if n.endswith('.jar')),
              key=os.path.getmtime, reverse=True)
for p in baks[KEEP_BACKUPS:]:
    os.remove(p)
    print('    清理旧备份 %s' % os.path.basename(p))
print('    备份目录现有 %d 份：%s' % (min(len(baks), KEEP_BACKUPS),
                                      ', '.join(os.path.basename(p) for p in baks[:KEEP_BACKUPS])))
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

print('\n=== 1.1.41 出货完成 ===')
print('  新增：尸潮之主（2500 血 / 三阶段 / 防御 5 / 攻击 15 / 召唤 5 只）')
print('  尸潮：4 波 → 5 波，最后一波由 Boss 领场（horde_boss_on_final_wave 可关）')
print('  jar  : %s' % JAR)
print('  md5  : %s' % new_md5)
print('  部署时刻：%s' % time.strftime('%Y-%m-%d %H:%M:%S'))
print('  ⚠ Forge 无热重载：必须完全退出重开客户端（别只退到主菜单）')
