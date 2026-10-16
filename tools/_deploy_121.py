#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1.2.1 出货：铜装备兼容补丁 —— 与 [硬核生存] hcsurvival 同形同料的重复配方，运行期剔掉外家那几条。

本版内容：新增 `compat/CopperGearRecipeCompat`（FORGE 总线，配方加载完成后把「形状指纹与本模组
铜装备配方逐格等价、产物却不是本模组物品」的配方从 RecipeManager 里 replaceRecipes 剔除）
+ 新配置 `compat.copper_recipe_dedup`（默认 true，配置总数 170 → 171）
+ 新门禁 `tools/check_hcsurvival_conflict.py`（把 Java 的指纹规则离线复刻成 Python，拿真 jar 验）。

  * **症状**（用户两张截图）：合成台 3x3 里摆着正确的铜头盔 / 铜靴图案，产物格是空的；
    REI 的配方面板里摆着同一张配方。用户口径：「所有铜制武器、工具、物品无法合成」。
  * **根因**：hcsurvival 用**同一套原版图案 + 同一材料 minecraft:copper_ingot** 注册了同名的九件
    铜装备（斧 / 锄同样是 _1/_2 一对镜像摆法），与本模组九件的 canonical 图案逐格等价。
    1.20.1 的 `RecipeManager.getRecipeFor` 是
    `byType(type).values().stream().filter(matches).findFirst()` —— 按内部 Map 迭代顺序取第一条
    命中（HashMap 顺序），两条一模一样的配方里**只有一条可能被合成台用到**，另一条等于不存在。
  * **修法**：运行期结构化判定（配方类型 + 宽 x 高 + 逐格材料集合；**shaped 按左右镜像归一**，
    因为原版 matches 对同一个图案会同时试正摆与镜像摆，图案 P 与镜像(P) 的两条配方接受的是同一批
    网格、互为竞争者），只对本模组那九件的指纹建表，主命名空间不是本模组又撞进这张表的才剔 ——
    不写死 hcsurvival 的配方 id，换个同形冲突的模组照样拦得住。

跑法（*游戏须完全关闭*）：
    py tools/_deploy_121.py --build        # 先 ./gradlew build 再出货
    py tools/_deploy_121.py                # 用 build/libs 里已构建好的包
    py tools/_deploy_121.py --no-install   # 只跑判据，不动 mods/

判据（任一条不过就退出，不动 mods/）：
  1. 构建产物存在、包内 mods.toml 版本 == 1.2.1；
  2. 包内有 CopperGearRecipeCompat（含匿名监听器类），且编译产物里真的引用了
     replaceRecipes 与「形状指纹」那几条调用、UTF-8 日志前缀也在；
  3. 源码里：镜像归一（joinRows + compareTo）、配置开关读取、失败只 warn 不抛都在；
  4. 三条门禁在本机实跑全绿：check_hcsurvival_conflict.py（真 jar 对照）、check_recipes.py、
     check_gun_resources.py；
  5. 新配置：Config 有 compat 段与 copper_recipe_dedup（默认 true）；
  6. 文档：readme 有 1.2.1 条目与头表、配置计数 171、gradle.properties / mod.toml == 1.2.1；
  7. 基线：mods/ 里当前那个包必须是本版或上一版（按包内 mods.toml 版本认）；
  8. 换包：旧包挪到 mods/ 同级 mods_backup/（保 3 份），mods/ 里只留一个本模组包；
     其它模组 md5 必须全等；mods/ 下不许有子目录（Forge 会递归扫描 → 重复加载）；
     游戏客户端没在跑（PCL/Forge 启动器的命令行标记一并认，只认主类会漏判）。
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import zipfile

VER = '1.2.1'
PREV = '1.2.0'
ACCEPT = (PREV, VER)
ROOT = 'F:/mcmod/apocalypse_zombies-main'
SRC = ROOT + '/build/libs/apocalypse_zombies-%s.jar' % VER
DEV = 'F:/.minecraft/versions/1.20.1-Forge_47.4.27'
MODS, BACKUP = DEV + '/mods', DEV + '/mods_backup'
PREFIX = 'apocalypse_zombies-'
KEEP_BACKUPS = 3
CLIENT_MARKERS = ('net.minecraft.client.main.main', 'launchtarget forgeclient',
                  'fml.forgeversion', 'assetsindex')

ok = True
REPORT = []


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def check(cond, label, detail=None):
    global ok
    line = ('  ✓' if cond else '  ✗') + ' ' + label
    if detail is not None:
        line += '  [%s]' % (detail,)
    print(line)
    REPORT.append((bool(cond), label))
    if not cond:
        ok = False
    return bool(cond)


def jar_version(path):
    with zipfile.ZipFile(path) as z:
        txt = z.read('META-INF/mods.toml').decode('utf-8', 'replace')
    # 根 mod.toml 是模板，打出来的是展开后的 `version="…"`（没有 mod_version= 前缀）
    m = re.search(r'^version\s*=\s*"([^"]+)"', txt, re.M) or \
        re.search(r'mod_version\s*=\s*"([^"]+)"', txt)
    return m.group(1) if m else '?'


def game_state():
    """探测游戏是否在跑；探测失败返回 (None, None) 按未在跑处理。"""
    # PowerShell/wmic 的输出在中文 Windows 上是 GBK，text=True 默认按 UTF-8 解会把读线程
    # 直接抛 UnicodeDecodeError（探针本身还能用，但会糊一屏红字）—— 钉成 replace 解码。
    def run(cmd):
        return subprocess.run(cmd, capture_output=True, text=True, timeout=45,
                              encoding='utf-8', errors='replace').stdout.lower()
    try:
        out = run(['wmic', 'process', 'where', "name='javaw.exe'", 'get', 'CommandLine'])
        if 'commandline' in out or 'net.minecraft' in out:
            return (any(m in out for m in CLIENT_MARKERS), 'server' in out)
    except Exception:
        pass
    try:
        ps = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'javaw.exe' -or "
              "$_.Name -eq 'java.exe' } | ForEach-Object { $_.CommandLine }")
        out = run(['powershell', '-NoProfile', '-Command', ps])
        if 'commandline' in out or 'net.minecraft' in out or '.jar' in out:
            return (any(m in out for m in CLIENT_MARKERS), 'server' in out)
    except Exception:
        pass
    return (None, None)


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--no-install', action='store_true')
    ap.add_argument('--allow-dev-server', action='store_true')
    args = ap.parse_args()

    if args.build:
        print('=== 0/9 构建 ===')
        _cmd = os.environ.get('COMSPEC') or r'C:\Windows\System32\cmd.exe'
        rc = subprocess.call([_cmd, '/c', 'gradlew.bat', 'build', '--console=plain'], cwd=ROOT)
        check(rc == 0, './gradlew build exit 0', 'exit %d' % rc)

    print('=== 1/9 产物与版本 ===')
    check(os.path.isfile(SRC), '构建产物存在', SRC)
    if not os.path.isfile(SRC):
        raise SystemExit(1)
    check(jar_version(SRC) == VER, '包内 mods.toml 版本 == %s' % VER, jar_version(SRC))

    print('=== 2/9 包内 class 与调用 ===')
    with zipfile.ZipFile(SRC) as z:
        names = set(z.namelist())
        blobs = {}
        for n in names:
            if n.startswith('com/apocalypse/zombies/compat/'):
                blobs[n] = z.read(n)
    check('com/apocalypse/zombies/compat/CopperGearRecipeCompat.class' in names,
          '包内有 CopperGearRecipeCompat')
    anon = [n for n in names if n.startswith('com/apocalypse/zombies/compat/CopperGearRecipeCompat$')]
    check(bool(anon), '匿名监听器类在（PreparableReloadListener 的实现）', anon)
    main_cls = blobs.get('com/apocalypse/zombies/compat/CopperGearRecipeCompat.class', b'')
    check(b'm_44024_' in main_cls, '编译产物引用 replaceRecipes（m_44024_ = 重铺配方表）')
    check(b'getRecipeWidth' in main_cls and b'getRecipeHeight' in main_cls,
          '编译产物引用 getRecipeWidth / getRecipeHeight（宽高进指纹）')
    check('铜装备兼容'.encode('utf-8') in main_cls, '日志前缀「铜装备兼容」在（UTF-8 字符串常量）')
    with zipfile.ZipFile(SRC) as z:
        cfg_cls = z.read('com/apocalypse/zombies/Config.class')
    check(b'copper_recipe_dedup' in cfg_cls, 'Config.class 里有新配置键 copper_recipe_dedup')
    check(b'compat' in cfg_cls, 'Config.class 里有 compat 段名')

    print('=== 3/9 源码接线 ===')
    src = open(ROOT + '/src/main/java/com/apocalypse/zombies/compat/CopperGearRecipeCompat.java',
               encoding='utf-8').read()
    check('joinRows' in src and 'compareTo(mirrored)' in src,
          'shaped 指纹按左右镜像归一（正摆 / 镜像摆取字典序小的那个）')
    check('Config.COPPER_RECIPE_DEDUP.get()' in src, '开关真的被读（关掉就回到原样）')
    check('replaceRecipes' in src, '剔除走 RecipeManager.replaceRecipes（不是私有反射）')
    check('catch (Exception e)' in src and 'warn' in src,
          '任何意外只记 warn、配方表保持原样（不把世界加载搞崩）')
    check('barrier.wait(Unit.INSTANCE)' in src,
          '等 PreparationBarrier 再动手（否则跑在 RecipeManager.apply 之前，配方还是空的）')
    check('MinecraftForge.EVENT_BUS.register' in src, 'FORGE 总线显式注册')
    _main = open(ROOT + '/src/main/java/com/apocalypse/zombies/ApocalypseZombies.java',
                 encoding='utf-8').read()
    check('CopperGearRecipeCompat.register()' in _main, '主类构造里接线')
    _cfg = open(ROOT + '/src/main/java/com/apocalypse/zombies/Config.java', encoding='utf-8').read()
    check('"copper_recipe_dedup", true' in _cfg, '默认 true')

    print('=== 4/9 门禁实跑 ===')
    for script in ('check_hcsurvival_conflict.py', 'check_recipes.py', 'check_gun_resources.py'):
        rc = subprocess.call([sys.executable, ROOT + '/tools/' + script], cwd=ROOT)
        check(rc == 0, '%s 全绿' % script, 'exit %d' % rc)

    print('=== 5/9 文档 ===')
    rd = open(ROOT + '/readme.md', encoding='utf-8').read()
    check('### 1.2.1 —' in rd, 'readme 有 1.2.1 条目')
    check('| **当前版本** | `1.2.1` |' in rd, 'readme 头表 == 1.2.1')
    check('全部 171 项配置' in rd, 'readme 写明图形界面共 171 项')
    check('copper_recipe_dedup' in rd and 'check_hcsurvival_conflict.py' in rd,
          'readme 写清开关与新门禁')
    check('findFirst' in rd and '镜像' in rd, 'readme 写清根因（findFirst=顺序取一条）与镜像归一')
    check('mod_version=1.2.1' in open(ROOT + '/gradle.properties', encoding='utf-8').read(),
          'gradle.properties == 1.2.1')
    check('mod_version = "1.2.1"' in open(ROOT + '/mod.toml', encoding='utf-8').read(),
          'mod.toml == 1.2.1')

    print('=== 6/9 基线校验 ===')
    if not os.path.isdir(MODS):
        check(False, 'mods/ 存在', MODS)
        raise SystemExit(1)
    jars = [f for f in os.listdir(MODS) if f.lower().endswith('.jar')]
    subdirs = [f for f in os.listdir(MODS) if os.path.isdir(os.path.join(MODS, f))]
    mine = [f for f in jars if f.startswith(PREFIX)]
    others = [f for f in jars if not f.startswith(PREFIX)]
    check(not subdirs, 'mods/ 下无子目录', subdirs or '干净')
    check(len(mine) == 1, 'mods/ 里只有 1 个本模组包', mine)
    client, devsrv = game_state()
    check(client is not True, '游戏客户端没在跑',
          '探测失败=按未在跑处理' if client is None else ('在跑！' if client else '未在跑'))
    if devsrv and not args.allow_dev_server:
        check(False, '无头开发服没在跑（要放行加 --allow-dev-server）', '在跑')
    base_ver = jar_version(os.path.join(MODS, mine[0])) if mine else '?'
    check(base_ver in ACCEPT, '基线包版本 ∈ %s（按包内 mods.toml 认）' % (ACCEPT,), base_ver)
    other_md5 = {f: md5(os.path.join(MODS, f)) for f in others}

    print('=== 7/9 换包 ===')
    if args.no_install:
        print('  --no-install：只跑到这里')
        raise SystemExit(0 if ok else 1)
    if not ok:
        print('\n★ 有判据未通过 —— 未改动 mods/。')
        raise SystemExit(1)
    os.makedirs(BACKUP, exist_ok=True)
    if mine and os.path.basename(SRC) != mine[0]:
        shutil.move(os.path.join(MODS, mine[0]), os.path.join(BACKUP, mine[0]))
        print('  换包：%s → mods_backup/' % mine[0])
    shutil.copy2(SRC, os.path.join(MODS, os.path.basename(SRC)))
    print('  新包：%s' % os.path.basename(SRC))
    backups = sorted([f for f in os.listdir(BACKUP) if f.startswith(PREFIX)],
                     key=lambda f: [int(x) for x in re.findall(r'\d+', f)])
    for f in backups[:-KEEP_BACKUPS]:
        os.remove(os.path.join(BACKUP, f))
        print('  清理旧备份：%s' % f)

    print('=== 8/9 换包后复核 ===')
    now = {f: md5(os.path.join(MODS, f)) for f in os.listdir(MODS) if f.lower().endswith('.jar')}
    check(all(now.get(f) == m for f, m in other_md5.items()),
          '其它模组 md5 全等（没被误伤）', '%d 个' % len(others))
    check(jar_version(os.path.join(MODS, os.path.basename(SRC))) == VER, '装机包版本 == %s' % VER)

    print('=== 9/9 实机复核提示 ===')
    print('  装机完成。进游戏后：开一次合成台摆铜头盔图案 → 产物格应出本模组铜头盔；')
    print('  日志里应有一行「[铜装备兼容] 剔除 11 条与本模组铜装备同形的重复配方（…）」。')
    print('\n★ 出货完成：mods/ = %s' % [f for f in now if f.startswith(PREFIX)])
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
