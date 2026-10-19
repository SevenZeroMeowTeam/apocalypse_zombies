#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P5 总门禁：天陨武库 4.0.0 的 jar / 资源 / 数据 / 文档一致性一次查完。

用法：
    python tools/check_skyfall.py                 # 查 build/libs 里当前版本的 jar
    python tools/check_skyfall.py --jar <path>    # 查指定 jar
    python tools/check_skyfall.py --skip-art      # 跳过两张贴图门禁（仅调试用）

退出码：0 = 全部通过；1 = 有失败。
不启游戏、不写工作区（只读 jar 与源码/文档）。
"""
import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VER_RE = re.compile(r'^mod_version\s*=\s*([0-9][^\s#]*)', re.M)

A = 'assets/apocalypse_zombies/'
D = 'data/apocalypse_zombies/'

CORES = ['cinder', 'fault', 'quarantine', 'swarm', 'dawn', 'black_rain']
STRIKE_PROTOCOLS = ['cinder', 'fault', 'quarantine', 'swarm', 'dawn', 'black_rain']
CARRIERS = ['carrier_cannon', 'carrier_lance', 'carrier_singularity',
            'carrier_plasma', 'carrier_asteroid']
SPACE = ['earth', 'nebula', 'sat_body', 'sat_panel', 'sat_dish']
JAVA_CLASSES = [
    'com/apocalypse/zombies/block/SkyfallTerminalBlock.class',
    'com/apocalypse/zombies/block/SkyfallTerminalBlockEntity.class',
    'com/apocalypse/zombies/orbital/terminal/SkyfallTerminalManager.class',
    'com/apocalypse/zombies/orbital/terminal/ProtocolCoreItem.class',
    'com/apocalypse/zombies/network/TerminalSyncPacket.class',
    'com/apocalypse/zombies/network/TerminalActionPacket.class',
    'com/apocalypse/zombies/network/StrikePhasePacket.class',
    'com/apocalypse/zombies/network/StrikeCancelPacket.class',
    'com/apocalypse/zombies/client/gui/SkyfallTerminalScreen.class',
]
LANG_KEYS = [
    'block.apocalypse_zombies.skyfall_terminal',
    'item.apocalypse_zombies.skyfall_core_cinder',
    'skyfall.terminal.quick_charge',
    'skyfall.gui.title',
    'skyfall.strike.busy',
]

EXPECTED_CONFIGS = 221
FAILS = []


def report(ok, label, detail=None):
    print(('  OK   ' if ok else '  FAIL ') + label + (('  [' + str(detail) + ']') if detail is not None else ''))
    if not ok:
        FAILS.append(label)
    return ok


def project_version():
    with open(os.path.join(ROOT, 'gradle.properties'), encoding='utf-8') as fh:
        m = VER_RE.search(fh.read())
    return m.group(1) if m else '?'


def png_size(blob):
    if blob[:8] != b'\x89PNG\r\n\x1a\n':
        return None, None, None
    width, height = struct.unpack('>II', blob[16:24])
    bit_depth, color_type = blob[24], blob[25]
    mode = {(8, 2): 'RGB', (8, 6): 'RGBA', (8, 0): 'L'}.get((bit_depth, color_type), 'CT%d' % color_type)
    return width, height, mode


def jar_version(path):
    with zipfile.ZipFile(path) as z:
        txt = z.read('META-INF/mods.toml').decode('utf-8', 'replace')
    m = re.search(r'^version\s*=\s*"([^"]+)"', txt, re.M)
    return m.group(1) if m else '?'


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

    ap = argparse.ArgumentParser()
    ap.add_argument('--jar', default=None)
    ap.add_argument('--skip-art', action='store_true')
    args = ap.parse_args()

    ver = project_version()
    jar = args.jar or os.path.join(ROOT, 'build', 'libs', 'apocalypse_zombies-%s.jar' % ver)
    print('== skyfall gate: %s ==' % ver)
    print('jar: %s' % jar)
    if not report(os.path.isfile(jar), 'jar 存在'):
        return 1

    names = set()
    blobs = {}
    with zipfile.ZipFile(jar) as z:
        names = set(z.namelist())
        blobs['mods.toml'] = z.read('META-INF/mods.toml')

        def read(name):
            try:
                return z.read(name)
            except KeyError:
                return None

        blobs['zh'] = read(A + 'lang/zh_cn.json')
        blobs['en'] = read(A + 'lang/en_us.json')

    print('\n[1] 版本与元数据')
    report(jar_version(jar) == ver, 'jar 内 mods.toml 版本 == %s' % ver, jar_version(jar))
    template = os.path.join(ROOT, 'src', 'main', 'resources', 'META-INF', 'mods.toml')
    if os.path.isfile(template):
        with open(template, encoding='utf-8') as fh:
            tmpl = fh.read()
        report('${mod_version}' in tmpl, 'mods.toml 模板使用 ${mod_version} 占位')
        report('geckolib' in tmpl.lower(), 'mods.toml 声明 GeckoLib 依赖')

    print('\n[2] 终端与六核心资产链')
    blockstates = A + 'blockstates/skyfall_terminal.json'
    block_model = A + 'models/block/skyfall_terminal.json'
    block_tex = A + 'textures/block/skyfall_terminal.png'
    for name in (blockstates, block_model, block_tex, A + 'models/item/skyfall_terminal.json'):
        report(name in names, '存在 ' + name)
    if block_model in names:
        with zipfile.ZipFile(jar) as z:
            model = json.loads(z.read(block_model))
        texture_ref = model.get('textures', {}).get('all', '')
        report(texture_ref == 'apocalypse_zombies:block/skyfall_terminal',
               'block model 指向 skyfall_terminal 贴图', texture_ref)
    for core in CORES:
        item_model = A + 'models/item/skyfall_core_%s.json' % core
        core_tex = A + 'textures/item/skyfall_core_%s.png' % core
        report(item_model in names and core_tex in names, '核心 %s 模型+贴图齐全' % core)

    print('\n[3] 数据（配方 / 掉落 / 协议）')
    recipes = [D + 'recipes/skyfall_terminal.json', D + 'recipes/skyfall_core_cinder.json']
    for r in recipes:
        ok = r in names
        if ok:
            with zipfile.ZipFile(jar) as z:
                json.loads(z.read(r))
        report(ok, '配方存在且 JSON 合法 ' + r)
    loot = D + 'loot_tables/blocks/skyfall_terminal.json'
    report(loot in names, '终端掉落表存在')
    for proto in STRIKE_PROTOCOLS:
        path = A + 'strike/%s.xml' % proto
        ok = path in names
        if ok:
            with zipfile.ZipFile(jar) as z:
                ET.fromstring(z.read(path))
        report(ok, '协议 XML 存在且可解析 %s' % proto)

    print('\n[4] 语言键（zh/en 对齐）')
    try:
        zh = json.loads(blobs['zh'].decode('utf-8')) if blobs['zh'] else {}
        en = json.loads(blobs['en'].decode('utf-8')) if blobs['en'] else {}
    except Exception as exc:
        zh, en = {}, {}
        report(False, '语言文件 JSON 解析', exc)
    report(len(zh) > 0 and len(en) > 0, 'zh/en 均非空', '%d / %d' % (len(zh), len(en)))
    only_zh = sorted(set(zh) - set(en))
    only_en = sorted(set(en) - set(zh))
    report(not only_zh and not only_en, 'zh/en 键集合一致',
           ('zh-only=%s en-only=%s' % (only_zh[:3], only_en[:3])) if (only_zh or only_en) else '%d keys' % len(zh))
    missing = [k for k in LANG_KEYS if k not in zh or k not in en]
    report(not missing, '关键 skyfall 键齐全', missing[:5] if missing else 'ok')

    print('\n[5] 代码与配置')
    for cls in JAVA_CLASSES:
        report(cls in names, '类在包内 ' + cls.split('/')[-1])
    config_java = os.path.join(ROOT, 'src', 'main', 'java', 'com', 'apocalypse', 'zombies', 'Config.java')
    with open(config_java, encoding='utf-8') as fh:
        source = fh.read()
    count = len(re.findall(r'public static final ForgeConfigSpec\.(?:BooleanValue|IntValue|LongValue|DoubleValue|ConfigValue)', source))
    report(count == EXPECTED_CONFIGS, '配置项数量 == %d' % EXPECTED_CONFIGS, count)

    print('\n[6] P4 资产原创性')
    for name in CARRIERS:
        path = A + 'textures/environment/%s.png' % name
        if path not in names:
            report(False, '载体板存在 ' + name)
            continue
        with zipfile.ZipFile(jar) as z:
            w, h, mode = png_size(z.read(path))
        report((w, h, mode) == (1408, 768, 'RGB'), '载体板 %s 1408x768 RGB' % name, '%sx%s %s' % (w, h, mode))
    cut = A + 'textures/environment/carrier_asteroid_cutout.png'
    if cut in names:
        with zipfile.ZipFile(jar) as z:
            w, h, mode = png_size(z.read(cut))
        report((w, h, mode) == (600, 600, 'RGBA'), '小行星抠图 600x600 RGBA', '%sx%s %s' % (w, h, mode))
    else:
        report(False, '小行星抠图存在')
    for name in SPACE:
        path = A + 'textures/environment/%s.png' % name
        report(path in names, '太空舞台贴图存在 ' + name)

    if args.skip_art:
        print('\n[7] 贴图门禁（--skip-art 跳过）')
    else:
        print('\n[7] 贴图门禁')
        for script in ('tools/check_orbital_art.py', 'tools/check_carrier_art.py'):
            path = os.path.join(ROOT, script)
            if not os.path.isfile(path):
                report(False, '门禁脚本存在 ' + script)
                continue
            out = subprocess.run([sys.executable, script], cwd=ROOT,
                                 capture_output=True, text=True, encoding='utf-8', errors='replace')
            tail = (out.stdout or '').strip().splitlines()[-1:] or ['(no output)']
            report(out.returncode == 0, '门禁通过 ' + script, tail[0][:80])

    print('\n[8] 文档 / 四处版本')
    with open(os.path.join(ROOT, 'readme.md'), encoding='utf-8') as fh:
        readme = fh.read()
    m = re.search(r'\|\s*\*\*当前版本\*\*\s*\|\s*`([^`]+)`', readme)
    report(bool(m) and m.group(1) == ver, 'readme 头表版本 == %s' % ver, m.group(1) if m else 'missing')
    report(('### %s —' % ver) in readme, 'readme 有 %s 更新日志段' % ver)
    with open(os.path.join(ROOT, 'mod.toml'), encoding='utf-8') as fh:
        root_toml = fh.read()
    m2 = re.search(r'^mod_version\s*=\s*"([^"]+)"', root_toml, re.M)
    report(bool(m2) and m2.group(1) == ver, '根 mod.toml 版本 == %s' % ver, m2.group(1) if m2 else 'missing')
    probe = os.path.join(ROOT, 'tools', 'skyfall_probe.py')
    report(os.path.isfile(probe), '专服探针脚本存在 tools/skyfall_probe.py')

    print('\n[9] 包体指纹')
    with open(jar, 'rb') as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    print('  sha256 %s  (%d bytes)' % (digest, os.path.getsize(jar)))

    print()
    if FAILS:
        print('RESULT: FAIL (%d) — %s' % (len(FAILS), '; '.join(FAILS[:3])))
        return 1
    print('RESULT: PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
