#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1.2.3 出货：「产物槽空」真因落定 —— 存档开着 doLimitedCrafting，而本模组从来没写过配方解锁。

先说更正：1.2.2 那句「真凶 = 玩家拿错短木棍」是探针落地【之前】的推测。探针实测推翻了它 ——
玩家摆的就是原版木棍（`4=minecraft:stick 7=minecraft:stick`），服务端 getRecipesFor 也每次都命中、
能装配出 copper_axe x1，产物槽却始终是空的。真因在服务端源码链上：

  * `CraftingMenu.slotChangedCraftingGrid` 里有一道闸：
    `RecipeHolder.setRecipeUsed(Level, ServerPlayer, Recipe)` —— 配方不是 special 的、
    世界开着 `doLimitedCrafting`、且**配方不在玩家配方书里** ⇒ 返回 false ⇒ **产物被整个丢弃**
    （assemble 的结果压根不写进产物槽）；「匹配成功」与「产物槽有东西」是前后两道工序；
  * 该存档 GameRules 里确有 `doLimitedCrafting = true`（level.dat 解出来的）；
  * 能合成的模组（craftingdead / farmersdelight）都带了「配方解锁进度」，原版物品也早被原版进度
    解锁（连 minecraft:copper_block 都有）—— 唯独本模组的配方书条目数是 0。

本版：
  1. `data/apocalypse_zombies/advancements/recipes/` 十个解锁进度（护甲四件＝有铜锭；五把工具＝
     有铜锭＋有棍；火把两条）—— 进度 criteria 里**不许出现未注册物品 id**（1.20.1 的进度解析
     会因此把整条作废，这是本版踩到并写进门禁的第二个教训）；
  2. `compat/RecipeUnlockCompat`：玩家登录时把 apocalypse_zombies 命名空间下全部配方写进配方书
     （awardRecipesByKey，既有存档立刻可合，不必等下一次背包变动触发进度判定）；
  3. 删掉 1.2.2 排查期的探针 / 启动自检临时代码。

判据：
  1. 构建产物存在、包内 mods.toml 版本 == 1.2.3；
  2. 包内：CopperGearRecipeCompat（去重保留）+ RecipeUnlockCompat（新）都在；编译产物引用
     replaceRecipes（m_44024_）与 awardRecipesByKey（m_7902_）；日志前缀「铜装备兼容」「配方解锁」在；
     **探针字符串（铜装备探针 / 铜装备自检）一个都不在**；十个解锁进度 json 在包里；五张短木棍条件配方在；
  3. 源码：去重判定与登录解锁接线都在、主类两处 register；解锁进度源码 criteria 里无外家物品 id；
  4. 四条门禁实跑全绿（新增 check_recipe_unlocks.py：每条配方都必须被解锁进度覆盖）；
  5. 文档：readme 有 1.2.3 条目 + 头表 1.2.3；gradle.properties / mod.toml == 1.2.3；
  6. 基线：mods/ 里当前那个包必须是本版或上一版（按包内 mods.toml 版本认）；
  7. 换包：旧包挪到 mods_backup/（保 3 份）；其它模组 md5 全等；mods/ 下不许有子目录；
     游戏客户端没在跑（PCL/Forge 启动器命令行标记一并认）。
  8. 换包后复核 + 9. 实机复核提示。

跑法（*游戏须完全关闭*）：
    py tools/_deploy_123.py --build        # 先 ./gradlew build 再出货
    py tools/_deploy_123.py --no-install   # 只校验、不换包
"""
import argparse
import hashlib
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

VER = '1.2.3'
PREV = '1.2.2'
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
    m = re.search(r'^version\s*=\s*"([^"]+)"', txt, re.M) or \
        re.search(r'mod_version\s*=\s*"([^"]+)"', txt)
    return m.group(1) if m else '?'


def game_state():
    """探测游戏是否在跑；探测失败返回 (None, None) 按未在跑处理。"""
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

    print('=== 2/9 包内 class 与数据 ===')
    with zipfile.ZipFile(SRC) as z:
        names = set(z.namelist())
        compat = z.read('com/apocalypse/zombies/compat/CopperGearRecipeCompat.class') \
            if 'com/apocalypse/zombies/compat/CopperGearRecipeCompat.class' in names else b''
        unlock = z.read('com/apocalypse/zombies/compat/RecipeUnlockCompat.class') \
            if 'com/apocalypse/zombies/compat/RecipeUnlockCompat.class' in names else b''
    check(bool(compat), '包内有 CopperGearRecipeCompat（去重保留）')
    check(bool(unlock), '包内有 RecipeUnlockCompat（登录写入配方书，新）')
    anon = [n for n in names if n.startswith('com/apocalypse/zombies/compat/CopperGearRecipeCompat$')]
    check(bool(anon), '匿名监听器类在（PreparableReloadListener 的实现）', anon)
    check(b'm_44024_' in compat, '编译产物引用 replaceRecipes（m_44024_ = 重铺配方表）')
    check('铜装备兼容'.encode('utf-8') in compat, '日志前缀「铜装备兼容」在（UTF-8 字符串常量）')
    check('铜装备探针'.encode('utf-8') not in compat and '铜装备自检'.encode('utf-8') not in compat,
          '探针 / 自检临时代码已删净（字符串常量不在）')
    check(b'm_7902_' in unlock, '编译产物引用 awardRecipesByKey（m_7902_ = 写进配方书）')
    check('[配方解锁]'.encode('utf-8') in unlock, '日志前缀「[配方解锁]」在（UTF-8 字符串常量）')
    adv = sorted(n for n in names if n.startswith('data/apocalypse_zombies/advancements/')
                 and n.endswith('.json'))
    check(len(adv) == 10, '包内十个配方解锁进度', [a.split('/')[-1] for a in adv])
    short_stick_files = ['data/apocalypse_zombies/recipes/%s_short_stick.json' % t
                         for t in ('copper_axe', 'copper_hoe', 'copper_pickaxe',
                                   'copper_shovel', 'copper_sword')]
    check(all(f in names for f in short_stick_files), '包内五张短木棍版条件配方',
          [f.split('/')[-1] for f in short_stick_files])
    check(not any(n.startswith('data/apocalypse_zombies/tags/') for n in names),
          '包内没有手柄标签（标签方案已废弃）')

    print('=== 3/9 源码接线 ===')
    src = open(ROOT + '/src/main/java/com/apocalypse/zombies/compat/CopperGearRecipeCompat.java',
               encoding='utf-8').read()
    check('competes(' in src and 'cellsOverlap(' in src,
          '去重口径 = 抢同一批网格（类型/尺寸 + 逐格材料集合有交集）')
    check('Config.COPPER_RECIPE_DEDUP.get()' in src, '开关真的被读（关掉就回到原样）')
    check('barrier.wait(Unit.INSTANCE)' in src,
          '等 PreparationBarrier 再动手（否则跑在 RecipeManager.apply 之前，配方还是空的）')
    usrc = open(ROOT + '/src/main/java/com/apocalypse/zombies/compat/RecipeUnlockCompat.java',
                encoding='utf-8').read()
    check('awardRecipesByKey' in usrc and 'PlayerLoggedInEvent' in usrc,
          '登录解锁：PlayerLoggedInEvent + awardRecipesByKey')
    check('ApocalypseZombies.MOD_ID.equals' in usrc, '只解锁自家命名空间')
    check('catch (Exception e)' in usrc and 'warn' in usrc, '解锁失败只记 warn、不拦进世界')
    _main = open(ROOT + '/src/main/java/com/apocalypse/zombies/ApocalypseZombies.java',
                 encoding='utf-8').read()
    check('CopperGearRecipeCompat.register()' in _main and 'RecipeUnlockCompat.register()' in _main,
          '主类构造里两处接线')

    print('=== 3b/9 解锁进度自检 ===')
    adv_dir = ROOT + '/src/main/resources/data/apocalypse_zombies/advancements'
    adv_files = sorted(glob.glob(adv_dir + '/**/*.json', recursive=True))
    check(len(adv_files) == 10, '源码里十个解锁进度文件', len(adv_files))
    foreign = []
    for p in adv_files:
        data = json.load(open(p, encoding='utf-8'))
        for crit in data.get('criteria', {}).values():
            for entry in crit.get('conditions', {}).get('items', []):
                for item_id in entry.get('items', []):
                    if not item_id.startswith(('minecraft:', 'apocalypse_zombies:')):
                        foreign.append('%s -> %s' % (os.path.basename(p), item_id))
    check(not foreign,
          'criteria 里没有未注册物品 id（1.20.1 进度解析会整条作废）', foreign or '干净')
    tool_adv = json.load(open(adv_dir + '/recipes/copper_axe.json', encoding='utf-8'))
    check(sorted(tool_adv.get('rewards', {}).get('recipes', [])) ==
          sorted(['apocalypse_zombies:copper_axe', 'apocalypse_zombies:copper_axe_mirror',
                  'apocalypse_zombies:copper_axe_short_stick']),
          '工具进度 rewards 覆盖 canonical + 镜像 + 短木棍三条')

    print('=== 4/9 门禁实跑 ===')
    for script in ('check_hcsurvival_conflict.py', 'check_recipes.py', 'check_gun_resources.py',
                   'check_recipe_unlocks.py'):
        rc = subprocess.call([sys.executable, ROOT + '/tools/' + script], cwd=ROOT)
        check(rc == 0, '%s 全绿' % script, 'exit %d' % rc)

    print('=== 5/9 文档 ===')
    rd = open(ROOT + '/readme.md', encoding='utf-8').read()
    check('### 1.2.3 —' in rd, 'readme 有 1.2.3 条目')
    check('| **当前版本** | `1.2.3` |' in rd, 'readme 头表 == 1.2.3')
    check('doLimitedCrafting' in rd and 'setRecipeUsed' in rd,
          'readme 写清真因（限制合成 + 配方书闸门）')
    check('check_recipe_unlocks.py' in rd and 'advancements/recipes' in rd,
          'readme 写清解锁进度与新门禁')
    check('mod_version=1.2.3' in open(ROOT + '/gradle.properties', encoding='utf-8').read(),
          'gradle.properties == 1.2.3')
    check('mod_version = "1.2.3"' in open(ROOT + '/mod.toml', encoding='utf-8').read(),
          'mod.toml == 1.2.3')

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
    check(md5(os.path.join(MODS, os.path.basename(SRC))) == md5(SRC), '装机包 md5 == 构建产物')

    print('=== 9/9 实机复核提示 ===')
    print('  装机完成。进游戏后：')
    print('  1) 合成台摆铜斧图案（XX/XS/ S，铜锭 ×3 + 木棍 ×2）→ 产物格应立刻出本模组铜斧；')
    print('  2) 打开配方书 → 铜装备条目应在（登录解锁写进去的）；')
    print('  3) 日志里应有「[铜装备兼容] 扫描配方 … 本模组铜装备配方 11 条」；')
    print('  4) 世界里开着 doLimitedCrafting 也不影响：配方已解锁在配方书里。')
    print('\n★ 出货完成：mods/ = %s' % [f for f in now if f.startswith(PREFIX)])
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
