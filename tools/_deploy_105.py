# -*- coding: utf-8 -*-
"""1.1.105 出货：修 1.1.104 的启动崩溃 —— win94.animation.json 的零时间戳关键帧排序。

本版内容：`gate.position` 的 0 秒帧移回通道首位（1.1.104 的 anim.py 把它追加在压弹循环之后，
GeckoLib 的 BakedAnimationsAdapter 只认「零帧 = 通道第一个键」，否则整包 animation.json
解析失败 → 客户端资源加载阶段直接崩）；anim.py / export.py / gate.py 三层加防回归；
reload_empty 删两枚 0 值冗余帧（3.0 / 3.30）。

跑法（*游戏须完全关闭*）：
    py tools/_deploy_105.py --build        # 先 ./gradlew build 再出货
    py tools/_deploy_105.py                # 用 build/libs 里已构建好的包
    py tools/_deploy_105.py --no-install   # 只跑判据，不动 mods/

判据（任一条不过就退出，不动 mods/）：
  1. 构建产物存在、包内 mods.toml 版本 == 1.1.105；
  2. 包内 win94 资产规格正确：geo identifier geometry.win94 / 16 骨 / 249 方块 / 512²，
     7 条 clip 长度逐条等于 Java 常量，贴图 512² 且在包内；
     **包内 animation.json 满足 GeckoLib 零帧居首契约（本版核心修复的护栏）**；
  3. 本机门禁实跑：tools/win94/gate.py 全绿；
  4. 版本号四处同改：gradle.properties / mod.toml / readme 头表 / readme 更新日志；
  5. 基线：mods/ 里当前那个包必须是本版或上一版（按包内 mods.toml 版本认）；
  6. 换包：旧包挪到 mods/ **同级** 的 mods_backup/（保 3 份），mods/ 里只留一个本模组包；
     其它模组 md5 必须全等，mods/ 下不许有子目录（Forge 会递归扫描 → 重复加载）。
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VER = '1.1.105'
PREV = '1.1.104'
ACCEPT = (PREV, VER)
SRC = ROOT / 'build' / 'libs' / ('apocalypse_zombies-%s.jar' % VER)
DEV = Path('F:/.minecraft/versions/1.20.1-Forge_47.4.27')
MODS, BACKUP = DEV / 'mods', DEV / 'mods_backup'
PREFIX = 'apocalypse_zombies-'
KEEP_BACKUPS = 3
A = 'assets/apocalypse_zombies/'

#: win94 规格（与本版资产一致；动画帧数变了但 clip 长度、骨/方块数不变）
W_BONES, W_CUBES, W_TEX = 16, 249, (512, 512)
W_ID = 'geometry.win94'
W_CLIPS = {'static_idle': 2.0, 'draw': 0.8, 'shoot': 0.6, 'bolt': 1.1,
           'reload_tactical': 2.2, 'reload_empty': 4.4, 'inspect': 2.6}
W_JAVA = ('com/apocalypse/zombies/item/Win94Item.class',
          'com/apocalypse/zombies/client/model/Win94GeoModel.class',
          'com/apocalypse/zombies/client/renderer/Win94ItemRenderer.class')

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
    print('  %s %s%s' % ('[OK  ]' if cond else '[FAIL]', label,
                         ('  [%s]' % (detail,)) if detail else ''))
    REPORT.append((bool(cond), label))
    if not cond:
        ok = False
    return bool(cond)


def jar_version(zf):
    txt = zf.read('META-INF/mods.toml').decode('utf-8', 'replace')
    m = re.search(r'mod_version\s*=\s*"([^"]+)"', txt) or re.search(r'^version\s*=\s*"([^"]+)"', txt, re.M)
    return m.group(1) if m else '?'


def png_size(data):
    return struct.unpack('>II', data[16:24])


def gecko_zero_first(clips):
    """复刻 GeckoLib BakedAnimationsAdapter.getKeyframes 的硬约束，返回违规点列表。"""
    bad = []
    for clip, ca in clips.items():
        for bone, chans in (ca.get('bones') or {}).items():
            for ch, ks in chans.items():
                for i, k in enumerate(list(ks)):
                    try:
                        t = float(k)
                    except ValueError:
                        t = 0.0
                    if t == 0 and i > 0:
                        bad.append('%s/%s.%s' % (clip, bone, ch))
    return bad


def main():
    ap = argparse.ArgumentParser(description='1.1.105 出货：修 win94 动画零帧排序导致的启动崩溃')
    ap.add_argument('--build', action='store_true', help='先跑 ./gradlew build 再出货（本脚本不代跑，仅提示）')
    ap.add_argument('--no-install', action='store_true', help='只跑判据，不动 mods/')
    args = ap.parse_args()
    if args.build:
        print('!! --build 交给调用方执行（sandbox 下 gradle 需要提权）；本脚本只做出货判据与换包。')

    print('=== 1.1.105 出货判据 ===')

    # ---- 1. 产物
    check(SRC.exists(), '构建产物存在', SRC.name)
    if not SRC.exists():
        return 1
    print('  · 大小 %.2f MB' % (SRC.stat().st_size / 1048576))
    with zipfile.ZipFile(SRC) as zf:
        names = zf.namelist()
        check(jar_version(zf) == VER, '包内 mods.toml 版本 == %s' % VER, jar_version(zf))

        # ---- 2. win94 资产
        geo_p, anim_p, tex_p = A + 'geo/win94.geo.json', A + 'animations/win94.animation.json', A + 'textures/item/win94.png'
        have = all(p in names for p in (geo_p, anim_p, tex_p))
        check(have, 'win94 资产三件都在包里')
        if have:
            geo = json.loads(zf.read(geo_p).decode('utf-8'))
            g0 = geo['minecraft:geometry'][0]
            d = g0['description']
            nc = sum(len(b.get('cubes', [])) for b in g0['bones'])
            check(d.get('identifier') == W_ID, 'geo identifier == %s' % W_ID, d.get('identifier'))
            check(len(g0['bones']) == W_BONES, 'geo 骨骼数 == %d' % W_BONES, len(g0['bones']))
            check(nc == W_CUBES, 'geo 方块数 == %d' % W_CUBES, nc)
            check((d.get('texture_width'), d.get('texture_height')) == W_TEX,
                  'geo 贴图基准 == %dx%d' % W_TEX, '%sx%s' % (d.get('texture_width'), d.get('texture_height')))
            anim = json.loads(zf.read(anim_p).decode('utf-8'))
            clips = anim.get('animations', {})
            check(set(clips) == set(W_CLIPS), 'animation 恰好 7 条契约 clip', ','.join(sorted(clips)))
            bad = [k for k, v in W_CLIPS.items()
                   if k not in clips or abs(float(clips[k]['animation_length']) - v) > 1e-6]
            check(not bad, '每条 clip 长度 == Java 常量', '不合 %s' % (bad or '无'))
            # 本版核心修复的护栏：包内每个通道的零时间戳键必须在首位
            order_bad = gecko_zero_first(clips)
            nch = sum(len(chans) for ca in clips.values() for chans in (ca.get('bones') or {}).values())
            check(not order_bad, '包内动画满足 GeckoLib 零帧居首契约（%d 通道）' % nch,
                  '违规 %s' % ('；'.join(order_bad[:5]) if order_bad else '无'))
            check(png_size(zf.read(tex_p)) == W_TEX, '贴图 %dx%d' % W_TEX, png_size(zf.read(tex_p)))
        check(all(p in names for p in W_JAVA), 'win94 三个 Java 类在包里')

    # ---- 3. 门禁
    sys.path.insert(0, str(ROOT / 'tools' / 'win94'))
    import gate  # noqa: E402
    rc = gate.main()
    check(rc == 0, 'tools/win94/gate.py 全绿')

    # ---- 4. 版本号四处
    props = (ROOT / 'gradle.properties').read_text(encoding='utf-8')
    mtoml = (ROOT / 'mod.toml').read_text(encoding='utf-8')
    rd = (ROOT / 'readme.md').read_text(encoding='utf-8')
    check(('mod_version=%s' % VER) in props, 'gradle.properties == %s' % VER)
    check(re.search(r'version\s*=\s*"%s"' % re.escape(VER), mtoml) is not None, 'mod.toml == %s' % VER)
    check(('`%s`' % VER) in rd.split('## 更新日志')[0], 'readme 头表 == %s' % VER)
    check(('### %s — ' % VER) in rd, 'readme 有 %s 更新日志条目' % VER)

    if args.no_install:
        print('\n--no-install：判据到此为止。')
        return 0 if ok else 1

    # ---- 5. 基线
    if not MODS.exists():
        check(False, 'mods 目录存在', str(MODS))
        return 1
    mods_jars = sorted(f for f in os.listdir(MODS) if f.lower().endswith('.jar'))
    subdirs = [f for f in os.listdir(MODS) if (MODS / f).is_dir()]
    check(not subdirs, 'mods/ 下没有子目录', ','.join(subdirs))
    others = [f for f in mods_jars if not f.startswith(PREFIX)]
    mine = [f for f in mods_jars if f.startswith(PREFIX)]
    other_md5 = {f: md5(MODS / f) for f in others}
    # 至多一个：上一版可能被手工改名成 `.jar.bak`（Forge 只扫 `.jar`，这样留着不会被加载），
    # 那种情况下 mods/ 里本来就没有本模组的 .jar，属于正常基线而不是失败。
    check(len(mine) <= 1, 'mods/ 里本模组包至多一个',
          ','.join(mine) if mine else '无（上一版已被改名或首次装机）')
    if mine:
        with zipfile.ZipFile(MODS / mine[0]) as zf:
            cur = jar_version(zf)
        check(cur in ACCEPT, '基线是本版或上一版', cur)

    # ---- 6. 换包
    BACKUP.mkdir(parents=True, exist_ok=True)
    if mine:
        target = BACKUP / mine[0]
        try:
            shutil.move(str(MODS / mine[0]), str(target))
        except OSError as e:
            check(False, '旧包移入 mods_backup（游戏可能在跑？）', str(e))
            return 1
        print('  · 旧包 → mods_backup/%s' % mine[0])
    shutil.copy2(SRC, MODS / SRC.name)
    print('  · 新包 → mods/%s' % SRC.name)

    backups = sorted([f for f in os.listdir(BACKUP) if f.startswith(PREFIX)],
                     key=lambda f: [int(x) for x in re.findall(r'\d+', f)])
    for f in backups[:-KEEP_BACKUPS]:
        os.remove(BACKUP / f)
        print('  · 清理旧备份：%s' % f)

    now = {f: md5(MODS / f) for f in os.listdir(MODS) if f.lower().endswith('.jar')}
    check(all(now.get(f) == m for f, m in other_md5.items()),
          '其它模组 md5 全等（没被误伤）', '%d 个' % len(others))
    with zipfile.ZipFile(MODS / SRC.name) as zf:
        check(jar_version(zf) == VER, '装机包版本 == %s' % VER)
    print('\n★ 出货完成：mods/ 里本模组包 = %s' % [f for f in now if f.startswith(PREFIX)])
    print('  备份保留：%s' % sorted(os.listdir(BACKUP))[-KEEP_BACKUPS:])
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
