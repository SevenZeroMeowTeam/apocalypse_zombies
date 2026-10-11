#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1.1.85 出货：**新枪 RSC M1917**（法国 Fusil Automatique Modèle 1917 半自动步枪）。

本版内容：
  * 资产线：geo + 512² 逐面 UV 贴图 + 8 条片段（static_idle / draw / shoot / shoot_last /
    bolt / reload_tactical / reload_empty / single_load），全部由生成器产出，
    art/rsc_1917/ 与 assets/ 两份同步；
  * Java 线：Rsc1917Item / Rsc1917GeoModel / Rsc1917ItemRenderer + ModItems 注册 +
    lang 中英 + models/item/rsc_1917.json + damage_type/rsc_1917_bullet.json，
    手持姿势（握位/护木/拉机柄/弹匣盖四个手部目标点）从本枪 geo 量出来；
  * 真机口径：5 发漏夹从**下方**插进固定弹匣、弹匣盖铰链在**前端**、**无空仓挂机**。
  * 不回归：1.1.84 的 LM Studio 接线 / 1.1.83 挖掘数字 / 1.1.82 高亮 / 1.1.81 一键挖掘 /
    1.1.80 36 格库存 / 猫耳娘 v4；另外 6 把枪与柯尔特 1878 规格未变。

跑法（**游戏须完全关闭**）：
    py tools/_deploy_185.py --build        # 先 ./gradlew build 再出货
    py tools/_deploy_185.py                # 用 build/libs 里已构建好的包
    py tools/_deploy_185.py --no-install   # 只跑判据，不动 mods/

判据（任一条不过就退出，不动 mods/）：
  1. 构建产物存在、包内 mods.toml 版本 == 1.1.85；
  2. 包内 RSC 资产齐全且规格正确（19 骨 / 282 方块 / 512² / 8 条片段长度逐条对得上 Java 常量）；
  3. 三条门禁在本机实跑全绿：check_gun_resources.py、check_rsc_1917_art.py、check_rsc_1917_anim.py；
  4. 不回归：另外 6 把枪的 geo/动画在包、动画文件 13 个、猫耳娘 128²、
     LmStudioWire 在且 OllamaWire 已删、ai.json_schema 仍在；
  5. 文档：readme 有 1.1.85 条目与头表、wiki 07 记一笔、wiki 06 收录新脚本；
  6. 基线：mods/ 里当前那个包必须是本版或上一版（按包内 mods.toml 版本认）；
  7. 换包：旧包挪到 mods/ 同级 mods_backup/（保 3 份），mods/ 里只留一个本模组包；
     其它模组 md5 必须全等，mods/ 下不许有子目录（Forge 会递归扫描）。
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import zipfile

VER = '1.1.85'
PREV = '1.1.84'
# 认三版：1.1.83（装机在册的上一版）、1.1.84（只在 GitHub 上，没装机）、本版。
ACCEPT = ('1.1.83', PREV, VER)
SRC = 'F:/mcmod/build/libs/apocalypse_zombies-%s.jar' % VER
DEV = 'F:/.minecraft/versions/1.20.1-Forge_47.4.26'
MODS, BACKUP = DEV + '/mods', DEV + '/mods_backup'
PREFIX = 'apocalypse_zombies-'
KEEP_BACKUPS = 3
A = 'assets/apocalypse_zombies/'
D = 'data/apocalypse_zombies/'
CLIENT_MARKERS = ('net.minecraft.client.main.Main',)

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
    mark = '  ✓' if cond else '  ✗'
    line = '%s %s' % (mark, label)
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
    m = re.search(r'mod_version\s*=\s*"([^"]+)"', txt) or re.search(r'^version\s*=\s*"([^"]+)"', txt, re.M)
    return m.group(1) if m else '?'


def game_state():
    """探测游戏是否在跑（javaw 命令行里有客户端主类）；探测失败返回 (None, None) 按未在跑处理"""
    try:
        out = subprocess.run(['wmic', 'process', 'where', "name='javaw.exe'", 'get', 'CommandLine'],
                             capture_output=True, text=True, timeout=20).stdout.lower()
        return (any(m.lower() in out for m in CLIENT_MARKERS), 'server' in out)
    except Exception:
        return (None, None)


def png_size(blob):
    return struct.unpack('>II', blob[16:24])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--no-install', action='store_true')
    ap.add_argument('--allow-dev-server', action='store_true')
    args = ap.parse_args()

    if args.build:
        print('=== 0/8 构建 ===')
        rc = subprocess.call(['./gradlew', 'build', '--console=plain'], cwd='F:/mcmod')
        check(rc == 0, './gradlew build exit 0', 'exit %d' % rc)

    print('=== 1/8 产物与版本 ===')
    check(os.path.isfile(SRC), '构建产物存在', SRC)
    if not os.path.isfile(SRC):
        raise SystemExit(1)
    check(jar_version(SRC) == VER, '包内 mods.toml 版本 == %s' % VER, jar_version(SRC))

    print('=== 2/8 包内 RSC 资产规格 ===')
    with zipfile.ZipFile(SRC) as z:
        names = set(z.namelist())

        def has(p):
            return p in names

        geo_p = A + 'geo/rsc_1917.geo.json'
        anim_p = A + 'animations/rsc_1917.animation.json'
        tex_p = A + 'textures/item/rsc_1917.png'
        for p in (geo_p, anim_p, tex_p, A + 'models/item/rsc_1917.json',
                  D + 'damage_type/rsc_1917_bullet.json'):
            check(has(p), '包内 %s' % p)
        for cls in ('item/Rsc1917Item', 'client/model/Rsc1917GeoModel', 'client/renderer/Rsc1917ItemRenderer'):
            check(any(n.startswith('com/apocalypse/zombies/%s' % cls) and n.endswith('.class') for n in names),
                  '包内 class %s' % cls)

        if has(geo_p):
            geo = json.loads(z.read(geo_p))
            g = geo['minecraft:geometry'][0]
            bones = g['bones']
            cubes = sum(len(b.get('cubes', [])) for b in bones)
            d = g['description']
            check(len(bones) == 19, 'geo 19 骨', len(bones))
            check(cubes == 282, 'geo 282 方块', cubes)
            check(d.get('identifier') == 'geometry.rsc_1917', 'identifier geometry.rsc_1917', d.get('identifier'))
            check((d.get('texture_width'), d.get('texture_height')) == (512, 512),
                  'geo 贴图基准 512²', '%sx%s' % (d.get('texture_width'), d.get('texture_height')))
            bn = {b['name'] for b in bones}
            for need in ('move', 'body', 'bolt', 'mag_cover', 'clip', 'clip_empty', 'casing', 'round_in', 'forend'):
                check(need in bn, 'geo 有骨 %s' % need)
            # 逐面 UV
            faceless = [b['name'] for b in bones for c in b.get('cubes', []) if not isinstance(c.get('uv'), dict)]
            check(not faceless, '每个方块都是逐面 uv', '%d 个例外' % len(faceless))
        if has(anim_p):
            anim = json.loads(z.read(anim_p))['animations']
            want = {'static_idle': 2.0, 'draw': 1.0, 'shoot': 0.6, 'shoot_last': 1.2, 'bolt': 1.1,
                    'reload_tactical': 2.6, 'reload_empty': 3.6, 'single_load': 1.5}
            check(set(anim) == set(want), '动画 8 条且名称对齐',
                  sorted(set(anim) ^ set(want)) or '一致')
            for k, ln in want.items():
                if k in anim:
                    check(abs(anim[k]['animation_length'] - ln) < 1e-6,
                          '%s 长度 %.2fs' % (k, ln), anim[k]['animation_length'])
        if has(tex_p):
            w, h = png_size(z.read(tex_p))
            check((w, h) == (512, 512), '贴图 512²', '%dx%d' % (w, h))

    print('=== 3/8 门禁实跑（本机） ===')
    for script in ('tools/check_gun_resources.py', 'tools/check_rsc_1917_art.py', 'tools/check_rsc_1917_anim.py'):
        rc = subprocess.call(['py', script], cwd='F:/mcmod')
        check(rc == 0, '%s 全绿' % script, 'exit %d' % rc)

    print('=== 4/8 不回归 ===')
    with zipfile.ZipFile(SRC) as z:
        names = set(z.namelist())
        for gun in ('m1_garand', 'colt_1878', 's686', 'mosin_nagant', 'uzi', 'awm'):
            check(A + 'geo/%s.geo.json' % gun in names and A + 'animations/%s.animation.json' % gun in names,
                  '旧枪 %s 仍在包' % gun)
        anims = sorted(n for n in names if n.startswith(A + 'animations/') and n.endswith('.animation.json'))
        check(len(anims) == 13, '动画文件 13 个（含 rsc_1917）', len(anims))
        if A + 'textures/entity/cat_girl.png' in names:
            w, h = png_size(z.read(A + 'textures/entity/cat_girl.png'))
            check((w, h) == (128, 128), '猫耳娘 v4 皮肤 128²', '%dx%d' % (w, h))
        has_wire = any(n.startswith('com/apocalypse/zombies/ai/LmStudioWire') for n in names)
        old_wire = any(n.startswith('com/apocalypse/zombies/ai/OllamaWire') for n in names)
        check(has_wire and not old_wire, 'LM Studio 接线在、Ollama 接线已删')
    src_ai = 'F:/mcmod/src/main/java/com/apocalypse/zombies/ai/LmStudioWire.java'
    if os.path.isfile(src_ai):
        ai = open(src_ai, encoding='utf-8').read()
        check('json_schema' in ai, 'LmStudioWire 仍按 json_schema 发 response_format')
        check('reasoning_content' in ai, 'LmStudioWire 仍认 reasoning_content 兜底')

    print('=== 5/8 文档 ===')
    rd = open('F:/mcmod/readme.md', encoding='utf-8').read()
    check('### 1.1.85 —' in rd, 'readme 有 1.1.85 条目')
    check('| **当前版本** | `1.1.85` |' in rd, 'readme 头表 == 1.1.85')
    check('RSC M1917' in rd and '弹匣盖' in rd, 'readme 写明新枪与其机构特点')
    w7 = open('F:/mcmod/docs/wiki/07-出货与版本管理.md', encoding='utf-8').read()
    check('1.1.85' in w7, 'wiki 07 记了 1.1.85 一笔')
    w6 = open('F:/mcmod/docs/wiki/06-工具脚本手册.md', encoding='utf-8').read()
    check('rsc_1917_geo.js' in w6 and 'check_rsc_1917_anim.py' in w6, 'wiki 06 收录 RSC 生成器与门禁')
    w4 = open('F:/mcmod/docs/wiki/04-美术规范速查.md', encoding='utf-8').read()
    check('rsc_1917' in w4, 'wiki 04 美术规范记了这把枪的口径')
    gp = open('F:/mcmod/gradle.properties', encoding='utf-8').read()
    check('mod_version=1.1.85' in gp, 'gradle.properties mod_version=1.1.85')

    print('=== 6/8 基线校验 ===')
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

    print('=== 7/8 换包 ===')
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

    print('=== 8/8 换包后复核 ===')
    now = {f: md5(os.path.join(MODS, f)) for f in os.listdir(MODS) if f.lower().endswith('.jar')}
    same = all(now.get(f) == m for f, m in other_md5.items())
    check(same, '其它模组 md5 全等（没被误伤）', '%d 个' % len(others))
    check(jar_version(os.path.join(MODS, os.path.basename(SRC))) == VER, '装机包版本 == %s' % VER)
    print('\n★ 出货完成：mods/ = %s' % [f for f in now if f.startswith(PREFIX)])
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
