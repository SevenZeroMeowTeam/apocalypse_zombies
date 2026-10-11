#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1.1.89 出货：**老实例的本地 AI 端点自动迁移**（Ollama 口径 → LM Studio 口径）+ 两个探针改齐。

本版内容：一次性的配置迁移（`Config.migrateLegacyAiConfig` + `ApocalypseZombies` 里的调用点）
与两个探针脚本的口径换代，**资产与 Java 逻辑一行未动**。
  * **根因**：Forge 的配置**只写默认值、从不覆盖已经存在的值**（越界值也只在读取时校正）。
    于是 1.1.84 把接线换成 LM Studio 之后，老实例的 `apocalypse_zombies-common.toml` 里
    仍然躺着 1.1.76 写下的 `endpoint = "http://127.0.0.1:11434"` 与 Ollama 形状的模型名
    （`fableforge-ai/nexus-coder:q4_k_m`）—— 注释是新的、值是旧的，她每次都回
    「连不上本地模型 http://127.0.0.1:11434」。
  * **迁移**：`Config.migrateLegacyAiConfig()` 在 `ModConfigEvent.Loading` 里跑一次（配置进内存
    之后才读得出值，构造阶段读会抛 `Cannot get config value before config is loaded`），
    改完 `SPEC.save()` 让 Forge 把文件按新值重写；判定收窄到「确实是那套旧默认值」，
    自己填的地址 / 模型名一律不碰。
  * **探针**：`tools/_ai_probe.py` 从 Ollama 的 `/api/chat` 换成 LM Studio 的
    `/v1/chat/completions`（`chat_template_kwargs` / `json_schema` / `usage.completion_tokens`），
    不传模型名会自动从 `GET /v1/models` 挑；`tools/_ai_jobprobe.py` 直接复用它的线，不再各写一份。
  * 不回归：RSC M1917 资产（19 骨 / 577 方块 / 512² / 8 条片段）、其余 6 把枪、猫耳娘 v4、
    Java 逻辑全部未动。

跑法（**游戏须完全关闭**）：
    py tools/_deploy_189.py --build        # 先 ./gradlew build 再出货
    py tools/_deploy_189.py                # 用 build/libs 里已构建好的包
    py tools/_deploy_189.py --no-install   # 只跑判据，不动 mods/

判据（任一条不过就退出，不动 mods/）：
  1. 构建产物存在、包内 mods.toml 版本 == 1.1.89；
  2. 包内 RSC 资产齐全且规格正确（19 骨 / 577 方块 / 512² / 8 条片段长度逐条对得上 Java 常量），
     且剪影对表过门禁（IoU ≥ 0.90、上缘 RMS ≤ 3.0 mm、下缘 RMS ≤ 5.0 mm、单列 >10 mm 的列数 == 0）；
  3. 四条门禁在本机实跑全绿：rsc_1917_silhouette.py（轮廓对表）、check_gun_resources.py、
     check_rsc_1917_art.py、check_rsc_1917_anim.py；
  4. 不回归：另外 6 把枪的 geo/动画在包、动画文件 13 个、猫耳娘 128²、
     LmStudioWire 在且 OllamaWire 已删、ai.json_schema 仍在；
  5. 文档：readme 有 1.1.89 条目与头表、1.1.76 那段的旧默认值加了指路、wiki 07 记一笔、
     wiki 06 收录迁移入口与新口径探针、gradle.properties == 1.1.89；
  6. 1.1.89 本体：迁移入口 / 调用点 / 日志都在，判定收窄，src 下 11434 只剩迁移判定，
     两个探针都不再打 Ollama；
  7. 基线：mods/ 里当前那个包必须是本版或上一版（按包内 mods.toml 版本认）；
  8. 换包：旧包挪到 mods/ 同级 mods_backup/（保 3 份），mods/ 里只留一个本模组包；
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

VER = '1.1.89'
PREV = '1.1.88'
# 认三版：1.1.87（只在 GitHub 上，没装机）、1.1.88（装机在册的上一版）、本版。
ACCEPT = ('1.1.87', PREV, VER)
SRC = 'F:/mcmod/build/libs/apocalypse_zombies-%s.jar' % VER
DEV = 'F:/.minecraft/versions/1.20.1-Forge_47.4.26'
MODS, BACKUP = DEV + '/mods', DEV + '/mods_backup'
PREFIX = 'apocalypse_zombies-'
KEEP_BACKUPS = 3
A = 'assets/apocalypse_zombies/'
D = 'data/apocalypse_zombies/'
# 「游戏在跑」的判定串：原版/Forge 启动器给 net.minecraft.client.main.Main，
# 而 PCL2 这类启动器走自己的 bootstrap，命令行里只有 --launchTarget forgeclient
# 与 --fml.forgeVersion —— 只认主类会**漏判**（游戏开着也照样换包），所以几个都认。
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
        if 'commandline' in out:
            return (any(m.lower() in out for m in CLIENT_MARKERS), 'server' in out)
    except Exception:
        pass
    try:
        ps = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'javaw.exe' -or "
              "$_.Name -eq 'java.exe' } | ForEach-Object { $_.CommandLine }")
        out = subprocess.run(['powershell', '-NoProfile', '-Command', ps],
                             capture_output=True, text=True, timeout=45).stdout.lower()
        if 'commandline' in out or 'net.minecraft' in out:
            return (any(m.lower() in out for m in CLIENT_MARKERS), 'server' in out)
    except Exception:
        pass
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
        print('=== 0/9 构建 ===')
        # COMSPEC / 绝对路径：某些 python（如 graalpy）不做 PATHEXT 补全，光写 'cmd' 会
        # FileNotFoundError；System32 也不一定在解释器的 PATH 里。
        _cmd = os.environ.get('COMSPEC') or r'C:\Windows\System32\cmd.exe'
        rc = subprocess.call([_cmd, '/c', 'gradlew.bat', 'build', '--console=plain'], cwd='F:/mcmod')
        check(rc == 0, './gradlew build exit 0', 'exit %d' % rc)

    print('=== 1/9 产物与版本 ===')
    check(os.path.isfile(SRC), '构建产物存在', SRC)
    if not os.path.isfile(SRC):
        raise SystemExit(1)
    check(jar_version(SRC) == VER, '包内 mods.toml 版本 == %s' % VER, jar_version(SRC))

    print('=== 2/9 包内 RSC 资产规格 ===')
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
            check(cubes == 577, 'geo 577 方块', cubes)
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

    print('=== 3/9 门禁实跑（本机） ===')
    # 剪影对表要用 py -3.13（numpy 只在 3.13 解释器里），故单独一条
    subprocess.call(['node', 'tools/rsc_1917_geo.js', '--emit', 'build/rsc_1917_gen.geo.json'], cwd='F:/mcmod',
                    stdout=subprocess.DEVNULL)
    rc = subprocess.call(['py', '-3.13', 'tools/rsc_1917_silhouette.py',
                          '--geo', 'build/rsc_1917_gen.geo.json'], cwd='F:/mcmod')
    check(rc == 0, 'tools/rsc_1917_silhouette.py 全绿（IoU/上下缘 RMS/单列 ≤10mm）', 'exit %d' % rc)
    for script in ('tools/check_gun_resources.py', 'tools/check_rsc_1917_art.py', 'tools/check_rsc_1917_anim.py'):
        rc = subprocess.call(['py', script], cwd='F:/mcmod')
        check(rc == 0, '%s 全绿' % script, 'exit %d' % rc)

    print('=== 4/9 不回归 ===')
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

    print('=== 5/9 文档 ===')
    rd = open('F:/mcmod/readme.md', encoding='utf-8').read()
    check('### 1.1.89 —' in rd, 'readme 有 1.1.89 条目')
    check('| **当前版本** | `1.1.89` |' in rd, 'readme 头表 == 1.1.89')
    check('RSC M1917' in rd and '弹匣盖' in rd, 'readme 写明新枪与其机构特点')
    w7 = open('F:/mcmod/docs/wiki/07-出货与版本管理.md', encoding='utf-8').read()
    check('1.1.89' in w7, 'wiki 07 记了 1.1.89 一笔')
    w6 = open('F:/mcmod/docs/wiki/06-工具脚本手册.md', encoding='utf-8').read()
    check('rsc_1917_geo.js' in w6 and 'check_rsc_1917_anim.py' in w6, 'wiki 06 收录 RSC 生成器与门禁')
    check('migrateLegacyAiConfig' in w6, 'wiki 06 收录配置迁移入口')
    check('_ai_probe.py' in w6 and 'LM Studio' in w6, 'wiki 06 的探针条目已改 LM Studio 口径')
    w4 = open('F:/mcmod/docs/wiki/04-美术规范速查.md', encoding='utf-8').read()
    check('rsc_1917' in w4, 'wiki 04 美术规范记了这把枪的口径')
    gp = open('F:/mcmod/gradle.properties', encoding='utf-8').read()
    check('mod_version=1.1.89' in gp, 'gradle.properties mod_version=1.1.89')

    print('=== 6/9 1.1.89：老实例的本地 AI 端点自动迁移（Ollama 口径 → LM Studio 口径） ===')
    # 这一版的根因不在模组、在磁盘：Forge 的配置只写默认值、**从不覆盖已经存在的值**，
    # 所以 1.1.84 把接线换成 LM Studio 之后，老实例的 apocalypse_zombies-common.toml 里
    # 仍旧躺着 1.1.76 写下的 endpoint = http://127.0.0.1:11434 与 Ollama 形状的模型名，
    # 表现就是「注释是新的、值是旧的」。判据分三层：
    #   ①迁移入口与调用点都在（且挂在「配置已进内存」之后）；
    #   ②判定收窄（用户自己填的地址/模型名不许被改掉）；
    #   ③src 下旧值只在迁移判定里出现 —— 别处再冒出来就是接线没清干净。

    _cfg = open('F:/mcmod/src/main/java/com/apocalypse/zombies/Config.java', encoding='utf-8').read()
    check('public static String migrateLegacyAiConfig()' in _cfg,
          'Config 有一次性迁移入口 migrateLegacyAiConfig()')
    check('http://127.0.0.1:11434' in _cfg and 'http://localhost:11434' in _cfg,
          '迁移认得那套旧 Ollama 默认值（127.0.0.1 与 localhost 两种写法）')
    check('/api/chat' in _cfg and '/api/generate' in _cfg,
          '连旧写法里的 /api/chat、/api/generate 尾巴也认（老配置里真出现过）')
    check('isOllamaShapedModel' in _cfg,
          '模型名只按「旧默认那个」或 Ollama 的 :量化标签 形状认（LM Studio 的 作者/模型 不动）')
    check('SPEC.save()' in _cfg, '改完让 Forge 把文件按新值重写（只在内存里改等于没改）')

    _M = open('F:/mcmod/src/main/java/com/apocalypse/zombies/ApocalypseZombies.java', encoding='utf-8').read()
    check('Config.migrateLegacyAiConfig()' in _M, '在 ApocalypseZombies 里被调用')
    check('event.getConfig().getSpec() == Config.SPEC' in _M, '只在自家 spec 上跑（别人的配置不碰）')
    check('ModConfigEvent.Loading' in _M and _M.index('ModConfigEvent.Loading') < _M.index('migrateLegacyAiConfig'),
          '挂在「配置已进内存」之后（构造阶段读值会抛 Cannot get config value before config is loaded）')
    check('Migrated legacy cat_girl.ai config' in _M, '迁移发生时会写一行日志（实机探针认这一行）')

    # src 下 11434 只许出现在迁移判定与其注释里
    _old = []
    for _root, _dirs, _files in os.walk('F:/mcmod/src'):
        for _f in _files:
            if _f.endswith('.java'):
                _p2 = os.path.join(_root, _f)
                if '11434' in open(_p2, encoding='utf-8').read():
                    _old.append(os.path.relpath(_p2, 'F:/mcmod').replace('\\', '/'))
    check(sorted(_old) == ['src/main/java/com/apocalypse/zombies/Config.java'],
          'src 下 11434 只出现在迁移判定里（没有残留的 Ollama 接线）', _old)

    # 两个探针也得跟着换口径 —— 留着打 Ollama 的话，「本地模型体检」自己先坏了
    _pp = open('F:/mcmod/tools/_ai_probe.py', encoding='utf-8').read()
    check('chat_template_kwargs' in _pp and 'json_schema' in _pp,
          '体检探针走 LM Studio 口径（chat_template_kwargs + json_schema）')
    check('completion_tokens' in _pp, '探针的 tok/s 读 usage.completion_tokens（Ollama 的 eval_count 已没有）')
    check('/v1/models' in _pp, '探针不传模型名时从 GET /v1/models 挑')
    _ollama_hits = re.findall(r"['\"](/api/chat|/api/generate)['\"]", _pp) + re.findall(r'11434', _pp)
    check(not _ollama_hits,
          '体检探针里不再有打 Ollama 的地址或旧端口（模块文档里提一句历史不算）', _ollama_hits)
    check('ENDPOINT = os.environ.get("AI_ENDPOINT"' in _pp, '端点可用 AI_ENDPOINT 覆盖（指到别处时不改源码）')
    _jp = open('F:/mcmod/tools/_ai_jobprobe.py', encoding='utf-8').read()
    check('import _ai_probe as wire' in _jp, '派活探针复用 _ai_probe 的线（不再各写一份实现）')
    check('/api/chat' not in _jp and '11434' not in _jp, '派活探针里 Ollama 那套已清掉')

    _rd = open('F:/mcmod/readme.md', encoding='utf-8').read()
    check('1.1.76 当版的口径' in _rd,
          'readme 1.1.76 那段的旧默认值加了指路（历史不改写，但要说清已被换掉）')

    # 「游戏在跑」的判定：PCL2 这类启动器命令行里没有 net.minecraft.client.main.Main，
    # 只认主类会漏判 → 游戏开着也照样换包（Win 上还会因 jar 被占用而静默失败）。
    _dp = open('F:/mcmod/tools/_deploy_189.py', encoding='utf-8').read()
    for _mk in ('launchtarget forgeclient', 'fml.forgeversion'):
        check(_mk in _dp, '游戏探针认 PCL/Forge 启动器的命令行标记（%s）' % _mk)
    check('if \'commandline\' in out:' in _dp and 'Get-CimInstance Win32_Process' in _dp,
          '游戏探针有第二条探法兜底（wmic 在 Win11 上常缺，会静默降级成「没在跑」）')
    check("os.environ.get('COMSPEC') or r'C:\\Windows\\System32\\cmd.exe'" in _dp,
          '构建调 cmd 走 COMSPEC/绝对路径（有的 python 不做 PATHEXT 补全，光写 cmd 会 FileNotFoundError）')
    print('=== 7/9 基线校验 ===')
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

    print('=== 8/9 换包 ===')
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

    print('=== 9/9 换包后复核 ===')
    now = {f: md5(os.path.join(MODS, f)) for f in os.listdir(MODS) if f.lower().endswith('.jar')}
    same = all(now.get(f) == m for f, m in other_md5.items())
    check(same, '其它模组 md5 全等（没被误伤）', '%d 个' % len(others))
    check(jar_version(os.path.join(MODS, os.path.basename(SRC))) == VER, '装机包版本 == %s' % VER)
    print('\n★ 出货完成：mods/ = %s' % [f for f in now if f.startswith(PREFIX)])
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
