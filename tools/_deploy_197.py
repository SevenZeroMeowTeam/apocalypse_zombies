#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1.1.97 出货：**全部 readme 过一次账**（只改文档，没碰代码）。

本版内容：8 份 readme / 台账里的过期描述改成现状 + 版本号与日志。**没有 Java 改动。**
  * **四处实证错误**：
      - art/crossbow/DELIVERY.md 偏差 #9「物品栏图标约 4 px，未修待定」→ 1.1.95 已修（0.30→1.20）；
        紧跟的「待定 #2 是否四把枪一起放大」也随之已决。
      - art/uzi/DELIVERY.md「Java 同步：未做，UziItem 尚未落地」→ 早已落地（八个 clip 五個在用）。
      - art/awm/README.md 与 art/m1garand/README.md 的署名表「22 个 TaCZ 音效 = 未修改副本，
        只留在自用包」→ 1.1.93 已全部换成项目自备录音。
      - art/m1garand/README.md 的 clip 表与待办 4「draw 尚未接线」→ 已接线（M1GarandItem.ANIM_DRAW）。
  * **wiki 索引的数字对不上现状**（docs/wiki/README.md）：_deploy_140.py → 196；readme「514 行」
    → 1975 行；门禁「13 个脚本」→ 18 个；tools「100+ 个脚本」→ 235 个；mod.toml 那条改准确
    （build.gradle 只认 META-INF/mods.toml，根目录这个不参与构建）。
  * **待办列表加了重核结论**（awm / m1garand）：WeaponMount 常量类确实仍未做、AWM 那 5 段 clip
    仍未接线、持枪微动仍缺；但加兰德的 draw 已接线。核过的结论写进待办区顶部，免得照旧结论干活。
  * **顺带记一笔**：art/awm/sounds/*.ogg（22 个 TaCZ 副本）仍在仓库里 —— 模组已不用它们，
    但作为留档没删，所以与 art/awm/awm.animation.json 一样仍在公开仓库中（见 NOTICE.md）。
  * 不回归：1.1.96 的村民管门与种地、1.1.95 的八把枪图标缩放、1.1.94 的铜斧、1.1.93 的音效换源、
    1.1.92 的七件铜装备、1.1.91 的爆炸弹与十字弩弦姿态、猫耳娘 v4、RSC M1917 全套。

跑法（**游戏须完全关闭**）：
    py tools/_deploy_197.py --build        # 先 ./gradlew build 再出货
    py tools/_deploy_197.py                # 用 build/libs 里已构建好的包
    py tools/_deploy_197.py --no-install   # 只跑判据，不动 mods/

判据（任一条不过就退出，不动 mods/）：
  1. 构建产物存在、包内 mods.toml 版本 == 1.1.97；
  2. 包内 RSC 资产齐全且规格正确，剪影对表过门禁；
  3. 四条门禁在本机实跑全绿：rsc_1917_silhouette.py、check_gun_resources.py、
     check_rsc_1917_art.py、check_rsc_1917_anim.py；
  4. 1.1.97 本体：四处实证错误都改成了现状、wiki 索引的四个数字都对得上实物
     （readme 行数 / tools 脚本数 / check_*.py 数都是**量出来的**）、核过「仍未做」的条目仍在；
  5. 不回归：1.1.96 的 VillagerChores 与三个配置项、1.1.95 的八把枪 gui.scale、1.1.94 的铜斧、
     1.1.93 的音效（guns/ 17 个）、1.1.92 的铜装备、1.1.91 的 AmmoEffects、1.1.90 的 BulletRay、
     猫耳娘 128²、LmStudioWire 在且 OllamaWire 已删；
  6. 文档：readme 有 1.1.97 条目与头表、wiki 07 同步、gradle.properties == 1.1.97；
  7. 基线：mods/ 里当前那个包必须是本版或上一版（按包内 mods.toml 版本认）；
  8. 换包：旧包挪到 mods/ 同级 mods_backup/（保 3 份），mods/ 里只留一个本模组包；
     其它模组 md5 必须全等，mods/ 下不许有子目录（Forge 会递归扫描 → 重复加载）。
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

VER = '1.1.97'
PREV = '1.1.96'
# 认三版：1.1.95（正式版，未装机）、1.1.96（装机在册的上一版）、本版。
ACCEPT = ('1.1.95', PREV, VER)
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
        print('=== 0/17 构建 ===')
        # COMSPEC / 绝对路径：某些 python（如 graalpy）不做 PATHEXT 补全，光写 'cmd' 会
        # FileNotFoundError；System32 也不一定在解释器的 PATH 里。
        _cmd = os.environ.get('COMSPEC') or r'C:\Windows\System32\cmd.exe'
        rc = subprocess.call([_cmd, '/c', 'gradlew.bat', 'build', '--console=plain'], cwd='F:/mcmod')
        check(rc == 0, './gradlew build exit 0', 'exit %d' % rc)

    print('=== 1/17 产物与版本 ===')
    check(os.path.isfile(SRC), '构建产物存在', SRC)
    if not os.path.isfile(SRC):
        raise SystemExit(1)
    check(jar_version(SRC) == VER, '包内 mods.toml 版本 == %s' % VER, jar_version(SRC))

    print('=== 2/17 包内 RSC 资产规格 ===')
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

    print('=== 3/17 门禁实跑（本机） ===')
    # 剪影对表要用 py -3.13（numpy 只在 3.13 解释器里），故单独一条
    subprocess.call(['node', 'tools/rsc_1917_geo.js', '--emit', 'build/rsc_1917_gen.geo.json'], cwd='F:/mcmod',
                    stdout=subprocess.DEVNULL)
    rc = subprocess.call(['py', '-3.13', 'tools/rsc_1917_silhouette.py',
                          '--geo', 'build/rsc_1917_gen.geo.json'], cwd='F:/mcmod')
    check(rc == 0, 'tools/rsc_1917_silhouette.py 全绿（IoU/上下缘 RMS/单列 ≤10mm）', 'exit %d' % rc)
    for script in ('tools/check_gun_resources.py', 'tools/check_rsc_1917_art.py', 'tools/check_rsc_1917_anim.py'):
        rc = subprocess.call(['py', script], cwd='F:/mcmod')
        check(rc == 0, '%s 全绿' % script, 'exit %d' % rc)

    print('=== 4/17 不回归 ===')
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

    print('=== 5/17 文档 ===')
    rd = open('F:/mcmod/readme.md', encoding='utf-8').read()
    check('### 1.1.97 —' in rd, 'readme 有 1.1.97 条目')
    check('| **当前版本** | `1.1.97` |' in rd, 'readme 头表 == 1.1.97')
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
    check('mod_version=1.1.97' in gp, 'gradle.properties mod_version=1.1.97')

    print('=== 6/17 1.1.89：老实例的本地 AI 端点自动迁移（Ollama 口径 → LM Studio 口径） ===')
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
    _dp = open('F:/mcmod/tools/_deploy_197.py', encoding='utf-8').read()
    for _mk in ('launchtarget forgeclient', 'fml.forgeversion'):
        check(_mk in _dp, '游戏探针认 PCL/Forge 启动器的命令行标记（%s）' % _mk)
    check('if \'commandline\' in out:' in _dp and 'Get-CimInstance Win32_Process' in _dp,
          '游戏探针有第二条探法兜底（wmic 在 Win11 上常缺，会静默降级成「没在跑」）')
    check("os.environ.get('COMSPEC') or r'C:\\Windows\\System32\\cmd.exe'" in _dp,
          '构建调 cmd 走 COMSPEC/绝对路径（有的 python 不做 PATHEXT 补全，光写 cmd 会 FileNotFoundError）')
    print('=== 10/17 1.1.90：子弹穿叶 / 打碎玻璃 + 猫耳娘手持物品摆正 ===')
    # 两件事的共同点都是「口径」：一是把七份一字不差抄来的射线收成一处、并给方块定规矩；
    # 二是发现 1.1.80 给她的模型补错了坐标系（多补了一步 YP 180）。判据分四块：
    #   ①BulletRay 本身的分寸（认标签/声音类型、不打不动的、有连穿上限）；
    #   ②调用点全换（七把枪 + 实体子弹），枪文件里不留裸的 level.clip；
    #   ③三个配置键与默认值；④她那条链只剩 XP -90，held_item_mirror 全库清零。

    _br = open('F:/mcmod/src/main/java/com/apocalypse/zombies/item/BulletRay.java', encoding='utf-8').read()
    check('public static BlockHitResult trace(Level level, Entity shooter, Vec3 from, Vec3 to)' in _br,
          'BulletRay 有玩家那条射线入口 trace()')
    check('public static boolean resolveProjectileHit(Level level, Entity bullet, BlockHitResult hit)' in _br,
          'BulletRay 有实体子弹那条 resolveProjectileHit()')
    check('state.is(BlockTags.LEAVES)' in _br, '树叶认原版 leaves 标签（带这个标签的模组树叶照样放行）')
    check('state.getSoundType() == SoundType.GLASS' in _br, '玻璃认原版 SoundType.GLASS（不写死方块 id）')
    check('getDestroySpeed(level, pos) < 0.0F' in _br and 'state.hasBlockEntity()' in _br,
          '打不动的（硬度 -1）与带方块实体的方块排除在外（子弹不该能拆家）')
    check('level.destroyBlock(pos, true)' in _br,
          '碎玻璃走原版 destroyBlock(pos, true)（掉落表 / 音效 / 粒子都照原版）')
    check('MAX_SKIPS' in _br and 'exitOf(' in _br, '穿叶按碰撞盒算出口点，且有连穿上限兜底')
    check('ClipContext.Block.COLLIDER' in _br, '射线仍只认碰撞体（流体 / 无碰撞方块照旧不算挡路）')

    # 七把在册的枪 + 那份归档副本（AWMItem_bytes）都换过来
    _GUNS = ('AWMItem', 'AWMItem_bytes', 'M1GarandItem', 'MosinNagantItem',
             'Rsc1917Item', 'S686Item', 'UziItem', 'CrossbowItem')
    for _g in _GUNS:
        _src = open('F:/mcmod/src/main/java/com/apocalypse/zombies/item/%s.java' % _g, encoding='utf-8').read()
        check('BulletRay.trace(level, player, eye, reach)' in _src, '%s 走 BulletRay.trace' % _g)
        check('level.clip(' not in _src, '%s 里不再有裸的 level.clip' % _g)
        check('ClipContext' not in _src, '%s 的 ClipContext 导入已清' % _g)

    _bp = open('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/BulletProjectile.java', encoding='utf-8').read()
    check('BulletRay.resolveProjectileHit(this.level(), this, result)' in _bp,
          '实体子弹撞方块时问 BulletRay（叶子不消散 / 玻璃按同一份配置碎）')

    # 三个配置键与默认值
    _cfg = open('F:/mcmod/src/main/java/com/apocalypse/zombies/Config.java', encoding='utf-8').read()
    check('.push("bullets")' in _cfg, '配置新增 bullets 段')
    for _k, _d in (('pass_leaves', 'true'), ('break_glass', 'true'), ('pass_glass', 'false')):
        check('.define("%s", %s)' % (_k, _d) in _cfg, 'bullets.%s 默认 %s' % (_k, _d))
    check('BULLETS_PASS_LEAVES' in _cfg and 'BULLETS_BREAK_GLASS' in _cfg and 'BULLETS_PASS_GLASS' in _cfg,
          '三个配置值都有字段声明')

    # 她那条链只剩 XP -90；多补的那一步与 held_item_mirror 开关全库清零
    _ren = open('F:/mcmod/src/main/java/com/apocalypse/zombies/client/renderer/CatGirlGeoRenderer.java',
                encoding='utf-8').read()
    check('poseStack.mulPose(Axis.XP.rotationDegrees(-90.0F))' in _ren, '仍是 XP -90（这一步是真的要）')
    check('Axis.YP' not in _ren, '不再补 YP 180（她这套空间已经是原版「翻转之后」那个）')
    check('ItemDisplayContext.THIRD_PERSON_RIGHT_HAND' in _ren and 'THIRD_PERSON_LEFT_HAND' not in _ren,
          '走右手 display 上下文（镜像那条路已删）')
    _hm = []
    for _root, _dirs, _files in os.walk('F:/mcmod/src'):
        for _f in _files:
            if _f.endswith('.java'):
                _p2 = os.path.join(_root, _f)
                if 'held_item_mirror' in open(_p2, encoding='utf-8').read():
                    _hm.append(os.path.relpath(_p2, 'F:/mcmod').replace('\\', '/'))
    check(not _hm, 'held_item_mirror 在 src 下已清零（开关退休）', _hm or '清零')

    # 文档
    _rd = open('F:/mcmod/readme.md', encoding='utf-8').read()
    check('### 1.1.90 —' in _rd, 'readme 有 1.1.90 条目')
    check('| **当前版本** | `1.1.97` |' in _rd, 'readme 头表 == 1.1.97')
    check('bullets.pass_leaves' in _rd and 'bullets.break_glass' in _rd, 'readme 写明两个 bullets 开关')
    check('这个开关随之退休' in _rd and 'held_item_mirror' in _rd, 'readme 写明镜像开关退休')
    check('`cat_girl.held_item_mirror`（默认 false）' in _rd and '**1.1.90 已删这个开关**' in _rd,
          'readme 1.1.80 那段加了「已被换掉」的指路')
    _w7 = open('F:/mcmod/docs/wiki/07-出货与版本管理.md', encoding='utf-8').read()
    check('## 1.1.90 —— 子弹穿叶 / 打碎玻璃' in _w7, 'wiki 07 有 1.1.90 小节')
    check('F · XP(-90) · YP(180) ≡ XP(-90)' in _w7, 'wiki 07 记了坐标系那步推导（后人别再补错）')
    check('**1.1.90 已删**' in _w7, 'wiki 07 的 1.1.80 段也加了指路')
    _w2 = open('F:/mcmod/docs/wiki/02-代码与资源地图.md', encoding='utf-8').read()
    check('BulletRay' in _w2 and 'BulletRay.resolveProjectileHit' in _w2, 'wiki 02 代码地图收录 BulletRay 与两条调用路')
    _w6 = open('F:/mcmod/docs/wiki/06-工具脚本手册.md', encoding='utf-8').read()
    check('_assert_190.py' in _w6 and '_deploy_190.py' in _w6, 'wiki 06 收录本轮门禁')

    print('=== 7/17 1.1.91：爆炸弹只有特效没有伤害（防递归闸补齐） ===')
    # 这一版只改一处：event/AmmoEffects 里那道闸原来「只有检查、没有合闸」。
    # 判据分四块：①闸的四件（声明 / 检查 / 上锁 / 解锁）都在，且各自不许有第二处；
    # ②位置对（检查在事件里、上锁在 detonate 里 —— 放错位置等于没修）；
    # ③try/finally 收口（异常路径也必须复位，否则闸永久锁死 = 爆炸弹连特效都没了）；
    # ④口径一字未动，并且别把「士兵僵尸免疫爆炸」那个刻意设定当成同一个 bug。

    _am = open('F:/mcmod/src/main/java/com/apocalypse/zombies/event/AmmoEffects.java',
               encoding='utf-8').read()

    # ① 闸的四件，各自唯一
    check('private static boolean detonating;' in _am, '闸的声明还在（服务端单线程，一个静态布尔就够）')
    check(_am.count('detonating = true;') == 1, '上锁只有一处（多了就是新漏洞）',
          '实得 %d' % _am.count('detonating = true;'))
    check(_am.count('detonating = false;') == 1, '解锁只有一处',
          '实得 %d' % _am.count('detonating = false;'))
    check(_am.count('if (detonating)') == 2, '检查出现两次：事件开头一次、detonate 进门一次',
          '实得 %d' % _am.count('if (detonating)'))

    # ② 位置对：检查在事件处理器里、上锁在 detonate 里 —— 这一句就是 1.1.90 缺的那行
    _i_on = _am.index('public static void onLivingHurt(')
    _i_det = _am.index('private static void detonate(')
    _oh = _am[_i_on:_i_det]   # 事件处理器那一段
    _dt = _am[_i_det:]        # detonate 那一段（到文件尾）
    check('if (detonating)' in _oh, '检查那一半在 onLivingHurt 里（爆炸引发的 hurt 从这里被挡回去）')
    check('detonating = true;' in _dt, '上锁那一半在 detonate 里 —— 1.1.90 缺的正是这一句')
    check('detonating = false;' in _dt, '解锁也在 detonate 里')

    # ③ try/finally：中途抛异常也要复位，否则闸永久锁死（那比原 bug 更难查：连特效都没了）
    check(_dt.index('detonating = true;') < _dt.index('try {'), '先合闸、再进 try（顺序反了等于没受保护）')
    check('finally {' in _dt and 'detonating = false;' in _dt[_dt.index('finally {'):],
          '解锁写在 finally 里（异常路径也复位）')
    check(_dt.index('victim.hurt(source, damage)') < _dt.index('finally {'),
          '伤害结算在 try 内、finally 之前')

    # ④ 口径一字未动（这一版只补闸，不许顺手改数值），且与「免疫爆炸」是两回事
    _at = open('F:/mcmod/src/main/java/com/apocalypse/zombies/item/AmmoType.java', encoding='utf-8').read()
    for _sig in ('EXPLOSION_RADIUS = 2.5D', 'EXPLOSION_DAMAGE = 14.0F', 'EXPLOSIVE_IMPACT_DAMAGE = 6.0F'):
        check(_sig in _at, 'AmmoType 口径未动：%s' % _sig)
    check('victim instanceof Enemy' in _am, '爆炸仍然只伤敌对生物')
    check('victim == player' in _am, '玩家自己永远不在伤害范围内')
    check('damageSources().explosion(player, player)' in _am,
          '伤害来源仍是原版爆炸（击杀算玩家头上、免疫规则跟着走）')
    check('destroyBlock' not in _am, '爆炸弹仍然不破坏地形（碎玻璃是 BulletRay 的事，别串台）')
    check('setSecondsOnFire' in _am, '铝热弹那条点燃路径没被牵连')
    _sol = open('F:/mcmod/src/main/java/com/apocalypse/zombies/entity/SoldierZombie.java',
                encoding='utf-8').read()
    check('DamageTypeTags.IS_EXPLOSION' in _sol,
          '士兵僵尸免疫爆炸仍是刻意设定（拿爆炸弹打它没伤害是设计，不是这个 bug）')

    # 产物级：反编译 jar 里那个 class —— 确认修的是真的进了包，而不是「源码好看、包里还是旧的」
    #
    # 输出走临时文件、不用管道：sandbox 下用管道捕获子进程输出会随机踩到
    # `filedescriptor out of range in select()`（判据一多就容易撞），而它报出来的却是
    # 「javap 不可用」，把人往环境问题上带（1.1.93 与 1.1.95 各撞过一次，重跑有时还不绿）。
    # 写文件没有这个问题，顺带留下一份现场。
    _jv = 'F:/mcmod/run/javap_ammo.txt'
    try:
        # 让 **shell 自己**做重定向，不经 Python 的 fd 传递：门禁跑到这里时进程里已经开了很多
        # 句柄，把 fd 交给子进程会静默失败 —— javap 返回 0，却一个字节都没写进文件，
        # 于是下游三条判据一起报「实得 0」，看起来像 class 编错了（1.1.93/1.1.95 都撞过）。
        _rc = subprocess.call(
            'javap -p -c -cp "%s" com.apocalypse.zombies.event.AmmoEffects > "%s"'
            % (SRC, _jv), shell=True)
        _bc = open(_jv, encoding='utf-8', errors='replace').read() if _rc == 0 else ''
        if _rc != 0:
            check(False, 'javap 可用（产物级验证的前提）', 'javap 退出码 %d' % _rc)
        elif not _bc:
            check(False, 'javap 可用（产物级验证的前提）', 'javap 返回 0 但没写出内容')
    except Exception as _e:      # javap 不在 PATH 这类环境问题：报红，但别把整个门禁崩掉
        _bc = ''
        check(False, 'javap 可用（产物级验证的前提）', str(_e)[:80])
    check(_bc.count('putstatic') == 3,
          '产物级：class 里 putstatic(detonating) 恰好 3 处 —— 上锁 1 次 + finally 的正常/异常两条路各 1 次',
          '实得 %d' % _bc.count('putstatic'))
    check(_bc.count('detonating:Z') == 5,
          '产物级：detonating 共 5 处引用（两处检查 getstatic + 三处 putstatic）',
          '实得 %d' % _bc.count('detonating:Z'))

    # ---- 十字弩的弦（同版第二件事）----
    # 三处：①静止类片段的弦必须挂在牙上（装弹后不许再弹回去）；②shoot 末帧要放弦；
    # ③右键瞄准把画面交给镜片。真正的运动学由 check_crossbow_anim.py 逐帧算，这里查源码/生成器/装机数据。
    import json as _json

    _cb2 = open('F:/mcmod/tools/crossbow_v2.py', encoding='utf-8').read()
    check('SPANNED = 1.0' in _cb2, '生成器有了「弦挂在牙上」的常量 SPANNED')
    check(_cb2.count('bow_pose(p, SPANNED)') == 4,
          '四处 SPANNED 覆盖五个静止类片段（ADS_up / ADS_down 共用同一个循环体）',
          '实得 %d' % _cb2.count('bow_pose(p, SPANNED)'))
    check(_cb2.count('bow_pose(p, ease)') == 2,
          'draw 与 shoot 仍走 ease（真正会经过松弛位的只有这两段）',
          '实得 %d' % _cb2.count('bow_pose(p, ease)'))

    _cbow = open('F:/mcmod/src/main/java/com/apocalypse/zombies/item/CrossbowItem.java',
                 encoding='utf-8').read()
    check('public boolean hidesModelWhileAimed() {\n        return true;' in _cbow,
          '瞄准过半把弩与双手交给镜片（hidesModelWhileAimed = true）')
    check('GunItem.SightStyle.CLEAR_SIGHT' in _cbow and 'hasScopeOverlay' in _cbow,
          '透明镜那两条契约没被牵连（仍是 CLEAR_SIGHT + hasScopeOverlay）')

    _anim = _json.load(open(
        'F:/mcmod/src/main/resources/assets/apocalypse_zombies/animations/crossbow.animation.json',
        encoding='utf-8'))['animations']
    check(len(_anim) == 7, '弩仍是 7 段剪辑', sorted(_anim))
    for _c in ('static_idle', 'reload_tactical', 'ADS_up', 'ADS_down', 'inspect', 'shoot'):
        check('rotation' in _anim[_c]['bones'].get('string_l', {}),
              '%s 里弦有 rotation 通道（不回落松弛位 / 放弦真做了）' % _c)

    # 弦缆门禁自己那个「整段只算第一帧」的缓存 bug 不许复活；判据也要留在新口径上
    _cca = open('F:/mcmod/tools/check_crossbow_anim.py', encoding='utf-8').read()
    check('(name, round(float(t), 6))' in _cca,
          '弦缆门禁的缓存键带时间（1.1.91 修的就是「整段只算第一帧」）')
    check('SPANNED_CLIPS' in _cca and 'SPANNED_TOL' in _cca, '静止类片段的「不许离开牙」判据在位')
    _teeth = open('F:/mcmod/tools/_teeth_sight_contract.py', encoding='utf-8').read()
    check('关掉 hidesModelWhileAimed' in _teeth,
          '咬齿测试跟着反转（把 true 改回 false 时必须咬住）')

    # 文档（这三条别漏：改完代码忘了写文档，是这套门禁最常抓到的形式主义）
    _w7b = open('F:/mcmod/docs/wiki/07-出货与版本管理.md', encoding='utf-8').read()
    check('十字弩的弦' in _w7b, 'wiki 07 记了十字弩这一节（含门禁那个缓存 bug）')
    _w6b = open('F:/mcmod/docs/wiki/06-工具脚本手册.md', encoding='utf-8').read()
    check('crossbow_anim_only.py' in _w6b, 'wiki 06 收录「只重生成动画」这个工具')
    check('_deploy_191.py' in _w6b, 'wiki 06 已把最新门禁指到 191')
    _w2b = open('F:/mcmod/docs/wiki/02-代码与资源地图.md', encoding='utf-8').read()
    check('CrossbowItem' in _w2b and '置 true' in _w2b, 'wiki 02 记了 CrossbowItem 这次改动')

    # 文档
    _rd = open('F:/mcmod/readme.md', encoding='utf-8').read()
    check('### 1.1.91 —' in _rd, 'readme 有 1.1.91 条目')
    check('| **当前版本** | `1.1.97` |' in _rd, 'readme 头表 == 1.1.97')
    check('没有一处把它设成 `true`' in _rd, 'readme 写明根因（闸只装了一半）')
    check('StackOverflowError' in _rd, 'readme 写明递归到栈溢出')
    check('try/finally' in _rd, 'readme 写明 finally 收口，以及为什么不能在末尾复位')
    _w7 = open('F:/mcmod/docs/wiki/07-出货与版本管理.md', encoding='utf-8').read()
    check('## 1.1.91 —— 爆炸弹只有特效没有伤害' in _w7, 'wiki 07 有 1.1.91 小节')
    check('一道只装了一半的闸' in _w7, 'wiki 07 写清根因')
    check('SoldierZombie' in _w7 and '免疫' in _w7, 'wiki 07 提醒「免疫爆炸」是另一个设定，别混')
    _w2 = open('F:/mcmod/docs/wiki/02-代码与资源地图.md', encoding='utf-8').read()
    check('**1.1.91**' in _w2 and 'AmmoEffects' in _w2, 'wiki 02 代码地图记了这次补齐')
    _w6 = open('F:/mcmod/docs/wiki/06-工具脚本手册.md', encoding='utf-8').read()
    check('_assert_191.py' in _w6 and '_deploy_191.py' in _w6, 'wiki 06 收录本轮门禁')

    print('=== 9/17 1.1.92：一整套铜装备（剑 / 镐 / 锄 / 头盔 / 胸甲 / 护腿 / 靴） ===')
    # 三条口径是玩家点名的，这里对原版数值逐条验：
    #   ① 耐久比石高；② 武器伤害与石一样；③ 护甲比皮革高、比铁低（落在整套总和上）。
    # 另外查七件物品的「五件套」——注册 / 模型 / 贴图 / lang / 配方，缺一样就是物品栏里的紫黑方块。
    import json as _json
    import re as _re

    # 原版参照值（1.20.1 Tiers / ArmorMaterials），钉成常量：谁改了铜，这里就得跟着解释一遍
    _STONE_USES, _STONE_DMG, _STONE_SPEED, _STONE_ENCH = 131, 1.0, 4.0, 5
    _LEATHER_DEF, _IRON_DEF, _COPPER_DEF = 7, 15, 10

    _ITEMS = ('copper_sword', 'copper_pickaxe', 'copper_hoe',
              'copper_helmet', 'copper_chestplate', 'copper_leggings', 'copper_boots')
    _RES = 'F:/mcmod/src/main/resources/assets/apocalypse_zombies'

    # ---- ① 工具档 ----
    _tiers = open('F:/mcmod/src/main/java/com/apocalypse/zombies/registry/ModTiers.java',
                  encoding='utf-8').read()
    check('public static final Tier COPPER = new ForgeTier(' in _tiers, 'ModTiers 里有 COPPER 这一档')
    # 参数之间的行尾注释要先剥掉，否则 \s* 跨不过 "// 耐久：石 131 → 高"
    _m = _re.search(r'new ForgeTier\((.*?)\);', _tiers, _re.S)
    _args = _re.sub(r'//[^\n]*', '', _m.group(1)) if _m else ''
    _nums = _re.findall(r'\d+(?:\.\d+)?', _args)
    check(len(_nums) >= 5, 'ForgeTier 的五个数值能从源码里读出来', str(_nums))
    if len(_nums) >= 5:
        _lvl, _uses, _speed, _dmg, _ench = (int(_nums[0]), int(_nums[1]), float(_nums[2]),
                                            float(_nums[3]), int(_nums[4]))
        check(_uses > _STONE_USES, '① 铜工具耐久 %d 比石 %d 高' % (_uses, _STONE_USES))
        check(abs(_dmg - _STONE_DMG) < 1e-6,
              '② 铜攻击加成 %g 与石 %g 相同（⇒ 铜剑伤害 == 石剑）' % (_dmg, _STONE_DMG))
        check(_lvl == 1, '挖掘等级同石（能挖铁矿石、挖不动钻石）')
        check(_STONE_SPEED < _speed < 6.0, '效率 %.1f 落在石 %.1f 与铁 6.0 之间' % (_speed, _STONE_SPEED))
        check(_STONE_ENCH < _ench < 14, '附魔性 %d 落在石 %d 与铁 14 之间' % (_ench, _STONE_ENCH))
    check('Items.COPPER_INGOT' in _tiers, '修复材料是铜锭')
    check('BlockTags.NEEDS_STONE_TOOL' in _tiers, '可采方块标签与等级 1 配套（NEEDS_STONE_TOOL）')

    # ---- ③ 护甲材质 ----
    _arm = open('F:/mcmod/src/main/java/com/apocalypse/zombies/registry/ModArmorMaterials.java',
                encoding='utf-8').read()
    check('implements ArmorMaterial' in _arm, '铜甲是自建 ArmorMaterial')
    for _slot, _v in (('HELMET', 2), ('CHESTPLATE', 4), ('LEGGINGS', 3), ('BOOTS', 1)):
        check('case %s -> %d;' % (_slot, _v) in _arm, '③ 护甲值 %s = %d' % (_slot, _v))
    check(_LEATHER_DEF < _COPPER_DEF < _IRON_DEF,
          '③ 整套护甲合计 %d 落在皮革 %d 与铁 %d 之间' % (_COPPER_DEF, _LEATHER_DEF, _IRON_DEF))
    check('return type.getDurability' not in _arm,
          '没再用 1.20.1 不存在的 ArmorItem.Type.getDurability(int)（那是 1.20.5 才加的）')
    check('case HELMET -> 11;' in _arm and 'case BOOTS -> 13;' in _arm,
          '耐久按部位写明基础值（头 11 / 胸 16 / 腿 15 / 靴 13）')
    check('ApocalypseZombies.MOD_ID + ":" + name' in _arm,
          '穿戴贴图名带命名空间（copper_layer_1/2.png 才对得上）')

    # ---- 五件套 ----
    _items = open('F:/mcmod/src/main/java/com/apocalypse/zombies/registry/ModItems.java',
                  encoding='utf-8').read()
    for _n in _ITEMS:
        check('ITEMS.register("%s"' % _n in _items, '注册了 %s' % _n)
    check('CreativeModeTabs.TOOLS_AND_UTILITIES' in _items, '镐与锄进了工具页')
    for _c in ('COPPER_SWORD', 'COPPER_HELMET', 'COPPER_CHESTPLATE', 'COPPER_LEGGINGS', 'COPPER_BOOTS'):
        check('event.accept(%s);' % _c in _items, '%s 进了创造页' % _c)

    _ARMOURY = ('helmet', 'chestplate', 'leggings', 'boots')
    for _n in _ITEMS:
        _mj = _json.load(open('%s/models/item/%s.json' % (_RES, _n), encoding='utf-8'))
        _want = 'minecraft:item/generated' if any(k in _n for k in _ARMOURY) else 'minecraft:item/handheld'
        check(_mj.get('parent') == _want, '%s 的模型 parent = %s' % (_n, _want))
        check(_mj['textures']['layer0'] == 'apocalypse_zombies:item/' + _n,
              '%s 的模型指向自己的贴图' % _n)
        check(os.path.isfile('%s/textures/item/%s.png' % (_RES, _n)), '%s 的物品贴图在' % _n)
    for _n in ('copper_layer_1', 'copper_layer_2'):
        check(os.path.isfile('%s/textures/models/armor/%s.png' % (_RES, _n)),
              '穿戴图层 %s.png 在（文件名必须与 getName() 一致）' % _n)

    for _lang, _names in (('zh_cn', ('铜剑', '铜镐', '铜锄', '铜头盔', '铜胸甲', '铜护腿', '铜靴')),
                          ('en_us', ('Copper Sword', 'Copper Pickaxe', 'Copper Hoe', 'Copper Helmet',
                                     'Copper Chestplate', 'Copper Leggings', 'Copper Boots'))):
        _lj = _json.load(open('%s/lang/%s.json' % (_RES, _lang), encoding='utf-8'))
        for _k, _v in zip(_ITEMS, _names):
            check(_lj.get('item.apocalypse_zombies.' + _k) == _v,
                  '%s 里 %s = %s' % (_lang, _k, _v))

    for _n in _ITEMS:
        _rj = _json.load(open('F:/mcmod/src/main/resources/data/apocalypse_zombies/recipes/%s.json'
                              % _n, encoding='utf-8'))
        check(_rj['type'] == 'minecraft:crafting_shaped', '%s 是有序合成' % _n)
        check(_rj['result']['item'] == 'apocalypse_zombies:' + _n, '%s 的产物指向自己' % _n)
        check('minecraft:copper_ingot' in {v['item'] for v in _rj['key'].values()},
              '%s 用铜锭合成' % _n)

    # ---- 文档 ----
    _rd = open('F:/mcmod/readme.md', encoding='utf-8').read()
    check('### 1.1.92 —' in _rd, 'readme 有 1.1.92 条目')
    check('| **当前版本** | `1.1.97` |' in _rd, 'readme 头表 == 1.1.97')
    _w7 = open('F:/mcmod/docs/wiki/07-出货与版本管理.md', encoding='utf-8').read()
    check('## 1.1.92 ——' in _w7, 'wiki 07 有 1.1.92 小节')
    _w6 = open('F:/mcmod/docs/wiki/06-工具脚本手册.md', encoding='utf-8').read()
    check('copper_gear_art.py' in _w6, 'wiki 06 收录了贴图生成器')
    _w2 = open('F:/mcmod/docs/wiki/02-代码与资源地图.md', encoding='utf-8').read()
    check('ModTiers' in _w2 and 'ModArmorMaterials' in _w2, 'wiki 02 记了两个新注册表')

    print('=== 9/17 1.1.93：枪械音效换成项目自备录音 ===')
    # 五件事：① TaCZ 的 sounds/awm/（22 个副本）已删、sounds/guns/ 17 个自备录音到位；
    # ② sounds.json 每个键都指到 guns/ 下的文件、且文件真在（漏一个就是那一枪静音）；
    # ③ 事件名与 Java 常量没变（七把枪的 tick→cue 时刻表因此一行都不用动），
    #    两条新事件 uzi_shoot / crossbow_shoot 有人用；④ build.gradle 不再排除音效
    #    （这一步决定纯净包有没有声音）；⑤ 文档同步。
    import json as _json

    _SND = 'F:/mcmod/src/main/resources/assets/apocalypse_zombies/sounds'
    _JSON = _SND + '.json'

    check(not os.path.isdir(_SND + '/awm'),
          'TaCZ 的 sounds/awm/ 目录已删除（22 个借用副本不再随包）')
    _guns = sorted(f for f in os.listdir(_SND + '/guns') if f.endswith('.ogg'))
    check(len(_guns) == 17, 'sounds/guns/ 里 17 个自备录音', '实得 %d' % len(_guns))
    for _f in ('awp_shot_1.ogg', 'awp_reload_1.ogg', 'ak47_shot_1.ogg', 'akm_bolt_1.ogg',
               'akm_bolt_2.ogg', 'akm_reload_1.ogg', 'akm_reload_2.ogg', 'bolt_1.ogg',
               'crossbow_shot_1.ogg', 'crossbow_hit_1.ogg'):
        check(_f in _guns, 'sounds/guns/ 里有 %s' % _f)

    _sj = _json.load(open(_JSON, encoding='utf-8'))
    check(_sj['music_friends_wine']['sounds'][0]['stream'] is True, '背景音乐仍然是 stream')
    for _k, _v in _sj.items():
        for _e in _v['sounds']:
            _n = _e['name'].split(':', 1)[1]
            _want = 'music/' if _k == 'music_friends_wine' else 'guns/'
            check(_n.startswith(_want), '%s 指向 %s（不再指向 awm/）' % (_k, _want), _n)
            check(os.path.isfile('%s/%s.ogg' % (_SND, _n)),
                  '%s 的文件真的在 -> %s.ogg' % (_k, _n))
    check(not any('/awm/' in e['name'] for v in _sj.values() for e in v['sounds']),
          'sounds.json 里不再有任何 awm/ 路径')

    # 变体：同一条 event 下挂多支，播放时随机挑 —— 连发才不像复读
    check(len(_sj['uzi_shoot']['sounds']) == 4, 'uzi_shoot 挂了 4 支 AK 录音')
    check(len(_sj['crossbow_shoot']['sounds']) == 3, 'crossbow_shoot 挂了 3 支弩弦')

    _ms = open('F:/mcmod/src/main/java/com/apocalypse/zombies/registry/ModSounds.java',
               encoding='utf-8').read()
    for _n in ('awm_shoot', 'awm_shoot_3p', 'awm_rechamber_out', 'awm_rechamber_ejectclick',
               'awm_rechamber_in', 'awm_rechamber_end', 'awm_reload_raise', 'awm_reload_rattle',
               'awm_reload_ejectclick', 'awm_reload_magout', 'awm_reload_fast_rattle',
               'awm_reload_maghit', 'awm_reload_magin', 'awm_reload_end',
               'awm_reload_empty_raise', 'awm_reload_empty_magout', 'awm_reload_empty_mag_drop',
               'awm_reload_empty_rattle', 'awm_reload_empty_maghit', 'awm_reload_empty_magin',
               'awm_reload_empty_boltclose', 'awm_reload_empty_end', 'ammo_clip_pop'):
        check('sound("%s")' % _n in _ms, 'ModSounds 仍保留事件名 %s（时刻表契约）' % _n)
    check('UZI_SHOOT = sound("uzi_shoot")' in _ms, 'ModSounds 新增 UZI_SHOOT')
    check('CROSSBOW_SHOOT = sound("crossbow_shoot")' in _ms, 'ModSounds 新增 CROSSBOW_SHOOT')
    check('CROSSBOW_HIT = sound("crossbow_hit")' in _ms, 'ModSounds 已注册 CROSSBOW_HIT（素材就位、暂无调用点）')
    check('音源换成项目自备' in _ms, 'ModSounds 类注释声明了音源换自备（不再自称借用副本）')
    check('不再排除音效' in _ms, 'ModSounds 类注释记了 borrowedEntries 的收窄')

    _uzi = open('F:/mcmod/src/main/java/com/apocalypse/zombies/item/UziItem.java', encoding='utf-8').read()
    check('ModSounds.UZI_SHOOT.get()' in _uzi, 'Uzi 的枪声用 UZI_SHOOT')
    check('ModSounds.AWM_SHOOT' not in _uzi, 'Uzi 不再引用 AWM_SHOOT')
    _cb = open('F:/mcmod/src/main/java/com/apocalypse/zombies/item/CrossbowItem.java', encoding='utf-8').read()
    check('ModSounds.CROSSBOW_SHOOT.get()' in _cb, '十字弩的枪声用 CROSSBOW_SHOOT')
    check('ModSounds.AWM_SHOOT' not in _cb, '十字弩不再引用 AWM_SHOOT')
    _gp = open('F:/mcmod/src/main/java/com/apocalypse/zombies/item/GunProfile.java', encoding='utf-8').read()
    check('ModSounds.CROSSBOW_SHOOT' in _gp, '怪物手里的弩也用 CROSSBOW_SHOOT')

    _bg = open('F:/mcmod/build.gradle', encoding='utf-8').read()
    _i = _bg.index('def borrowedEntries = [')
    _blk = _bg[_i:_bg.index(']', _i)]
    check('sounds/**' not in _blk, 'borrowedEntries 不再排除 sounds/**（纯净包从此有声音）')
    check('sounds.json' not in _blk, 'borrowedEntries 不再排除 sounds.json')
    check('awm.animation.json' in _blk, '转录动画仍在借用清单里（那一项还得靠手工动画兜）')
    check('sounds' not in _bg[_bg.index("tasks.register('borrowedPack'"):],
          'borrowedPack 不再打包音效（只剩动画）')

    for _p, _needle, _label in (
            ('F:/mcmod/readme.md', '### 1.1.93 —', 'readme 有 1.1.93 条目'),
            ('F:/mcmod/readme.md', '| **当前版本** | `1.1.97` |', 'readme 头表 == 1.1.97'),
            ('F:/mcmod/docs/wiki/07-出货与版本管理.md', '## 1.1.93 ——', 'wiki 07 有 1.1.93 小节'),
            ('F:/mcmod/docs/wiki/02-代码与资源地图.md', 'sounds/guns/', 'wiki 02 记了新的音效目录'),
            ('F:/mcmod/docs/wiki/08-CI与发布.md', '`.ogg` 数必须为 **17**', 'wiki 08 的纯净包核对改成 17'),
            ('F:/mcmod/docs/wiki/03-构建运行与排障.md', '仅转录动画一项', 'wiki 03 的产物表改了'),
            ('F:/mcmod/NOTICE.md', '1.1.93 起：音效不再借用', 'NOTICE 记了音效换源')):
        check(_needle in open(_p, encoding='utf-8').read(), _label)

    print('=== 10/17 1.1.94：铜装备补齐铜斧 ===')
    # 1.1.92 那批只做了剑/镐/锄 + 四件甲，漏了斧。这里除了查铜斧自己的「五件套」，还要盯住那条
    # **最容易抄错**的数值 —— 斧抄的是石斧（9 点），不是石剑（5 点）：
    #   原版 STONE_AXE = new AxeItem(Tiers.STONE, 7.0F, -3.2F) ⇒ 1 + 7 + 1 = 9
    #   原版 STONE_SWORD = new SwordItem(Tiers.STONE, 3, -2.4F) ⇒ 1 + 3 + 1 = 5
    import json as _json
    import re as _re

    _RES = 'F:/mcmod/src/main/resources/assets/apocalypse_zombies'
    _items = open('F:/mcmod/src/main/java/com/apocalypse/zombies/registry/ModItems.java',
                  encoding='utf-8').read()

    check('ITEMS.register("copper_axe"' in _items, '注册了 copper_axe')
    check('event.accept(COPPER_AXE);' in _items, '铜斧进了创造页')

    # 数值：AxeItem(Tier, 伤害修正, 攻速修正)
    _m = _re.search(r'new AxeItem\(ModTiers\.COPPER,\s*([\d.]+)F,\s*(-[\d.]+)F', _items)
    check(_m is not None, '铜斧的 AxeItem 参数能从源码里读出来')
    if _m:
        _dmg, _spd = float(_m.group(1)), float(_m.group(2))
        check(abs(_dmg - 7.0) < 1e-6,
              '铜斧伤害修正 %g == 石斧的 7.0（⇒ 都是 1+7+1 = 9 点，与石斧完全一致）' % _dmg)
        check(abs(_spd - (-3.2)) < 1e-6, '铜斧攻速修正 %g == 石斧的 -3.2' % _spd)
    check('Tiers.STONE' not in _items, '没有误用原版 Tiers（铜走自己的 ModTiers.COPPER）')
    check('new AxeItem(ModTiers.COPPER' in _items, '铜斧用铜那一档的 Tier（耐久/效率/挖掘等级随之）')

    # 五件套
    _mj = _json.load(open('%s/models/item/copper_axe.json' % _RES, encoding='utf-8'))
    check(_mj['parent'] == 'minecraft:item/handheld', '铜斧模型走 handheld（与另三件工具一致）')
    check(_mj['textures']['layer0'] == 'apocalypse_zombies:item/copper_axe', '模型指向自己的贴图')
    check(os.path.isfile('%s/textures/item/copper_axe.png' % _RES), '铜斧贴图在')
    for _lang, _v in (('zh_cn', '铜斧'), ('en_us', 'Copper Axe')):
        _lj = _json.load(open('%s/lang/%s.json' % (_RES, _lang), encoding='utf-8'))
        check(_lj.get('item.apocalypse_zombies.copper_axe') == _v, '%s 里 copper_axe = %s' % (_lang, _v))
    _rj = _json.load(open('F:/mcmod/src/main/resources/data/apocalypse_zombies/recipes/copper_axe.json',
                          encoding='utf-8'))
    check(_rj['type'] == 'minecraft:crafting_shaped', '铜斧是有序合成')
    check(_rj['pattern'] == ['XXX', 'XSX', ' S '], '配方是原版斧形（三锭 + 两棍）', str(_rj['pattern']))
    check(_rj['result']['item'] == 'apocalypse_zombies:copper_axe', '产物指向自己')
    check('minecraft:copper_ingot' in {v['item'] for v in _rj['key'].values()}, '用铜锭合成')

    # 生成器的映射表也得有它，否则下次重跑贴图会漏掉这一张
    _art = open('F:/mcmod/tools/copper_gear_art.py', encoding='utf-8').read()
    check("'textures/item/iron_axe.png', 'textures/item/copper_axe.png'" in _art,
          '贴图生成器映射表里有 iron_axe → copper_axe')
    check(_art.count("'textures/item/copper_") == 8,
          '映射表覆盖 8 件物品贴图（1.1.92 的 7 件 + 斧）',
          '实得 %d' % _art.count("'textures/item/copper_"))

    # 上一版那七件别在这次改动里被碰坏：全库铜装备共 8 件
    for _n in ('copper_sword', 'copper_pickaxe', 'copper_hoe', 'copper_axe',
               'copper_helmet', 'copper_chestplate', 'copper_leggings', 'copper_boots'):
        check('ITEMS.register("%s"' % _n in _items, '铜装备 %s 仍在册' % _n)
    check(_items.count('event.accept(COPPER_') == 8, '八件铜装备都进了创造页',
          '实得 %d' % _items.count('event.accept(COPPER_'))

    # 文档
    _rd = open('F:/mcmod/readme.md', encoding='utf-8').read()
    check('### 1.1.94 —' in _rd, 'readme 有 1.1.94 条目')
    check('| **当前版本** | `1.1.97` |' in _rd, 'readme 头表 == 1.1.97')
    check('## 1.1.94 ——' in open('F:/mcmod/docs/wiki/07-出货与版本管理.md', encoding='utf-8').read(),
          'wiki 07 有 1.1.94 小节')
    check('铜斧' in open('F:/mcmod/docs/wiki/02-代码与资源地图.md', encoding='utf-8').read(),
          'wiki 02 记了铜斧')

    print('=== 11/17 1.1.95：枪械物品栏显示放大 ===')
    # 枪走 builtin/entity（GeckoLib 画 3D 模型），物品栏里多大**只由 display.gui.scale 决定** ——
    # 贴图内容本来就是占满画布的，所以这是一次纯显示参数的改动。
    # 这里把八把枪的新值钉住，并**验算**「枪长 × scale ≈ 14.5 像素（格子 16）」这条口径：
    # 谁改了新值，就得同时解释为什么它不再占满格子。
    import json as _json

    _MODELS = 'F:/mcmod/src/main/resources/assets/apocalypse_zombies/models/item'
    _GEO = 'F:/mcmod/src/main/resources/assets/apocalypse_zombies/geo'

    # 目标：枪长占格子宽度的约 90%（14.5 / 16 像素）
    WANT = {'awm': 0.60, 'mosin_nagant': 0.63, 'rsc_1917': 0.69, 's686': 0.74,
            'm1_garand': 0.82, 'uzi': 0.92, 'colt_1878': 0.97, 'crossbow': 1.20}


    def _geo_length(name):
        """所有 cube 的联合包围盒最长边（模型单位；÷16 = 格）。"""
        g = _json.load(open('%s/%s.geo.json' % (_GEO, name), encoding='utf-8'))
        lo = [1e9] * 3
        hi = [-1e9] * 3
        for geo in g['minecraft:geometry']:
            for b in geo.get('bones', []):
                for c in b.get('cubes', []):
                    o, s = c['origin'], c.get('size', [0, 0, 0])
                    for i in range(3):
                        lo[i] = min(lo[i], o[i])
                        hi[i] = max(hi[i], o[i] + s[i])
        return max(hi[i] - lo[i] for i in range(3))


    check(len(WANT) == 8, '覆盖八把枪（七把枪 + 十字弩）')
    for _n in sorted(WANT):
        _g = _json.load(open('%s/%s.json' % (_MODELS, _n), encoding='utf-8'))
        check(_g['parent'] == 'builtin/entity', '%s 仍是 builtin/entity（GeckoLib 渲染）' % _n)
        _s = _g['display']['gui']['scale'][0]
        check(abs(_s - WANT[_n]) < 1e-6, '%s 的 gui.scale = %g' % (_n, WANT[_n]), '实得 %g' % _s)
        # 反向断言：只有 gui 被改过。其余槽位是「手里持枪」的构图，动的会改坏手感。
        for _slot in ('thirdperson_righthand', 'thirdperson_lefthand', 'firstperson_righthand',
                      'firstperson_lefthand', 'ground', 'fixed', 'head'):
            _o = _g['display'][_slot]['scale'][0]
            check(_o < 0.95, '%s 的 %s 保持原有小值（没被这次改动碰）' % (_n, _slot), '实得 %g' % _o)
        _L = _geo_length(_n)
        _px = _L * _s                       # 单位 × scale = 格 × 16 = 像素
        check(13.5 <= _px <= 15.5,
              '%s 显示长度 %.1f 像素（格子 16，目标 ~14.5）' % (_n, _px), '实得 %.1f' % _px)

    _rd = open('F:/mcmod/readme.md', encoding='utf-8').read()
    check('### 1.1.95 —' in _rd, 'readme 有 1.1.95 条目')
    check('| **当前版本** | `1.1.97` |' in _rd, 'readme 头表 == 1.1.97')
    check('## 1.1.95 ——' in open('F:/mcmod/docs/wiki/07-出货与版本管理.md', encoding='utf-8').read(),
          'wiki 07 有 1.1.95 小节')
    check('gui.scale' in open('F:/mcmod/docs/wiki/02-代码与资源地图.md', encoding='utf-8').read(),
          'wiki 02 记了「物品栏大小由 gui.scale 决定」')

    print('=== 11/17 1.1.96：村民自己管门与种地 ===')
    # 三件事：① VillagerChores 的两件事都在（门 / 农活），且走的是**村民 tick**那一支，
    # 不是往 goalSelector 里塞 Goal —— 村民的移动归 Brain 管，塞 Goal 会抢 Flag.MOVE；
    # ② 门那三条最容易写漏的规矩（不碰铁门 / 两半手动同步 / 门边有活物不动手）；
    # ③ 配置三项到位，两处写死的「151 项」与文档跟着改成 154。
    _AI = 'F:/mcmod/src/main/java/com/apocalypse/zombies/entity/ai/VillagerChores.java'
    _MOB = 'F:/mcmod/src/main/java/com/apocalypse/zombies/event/MobAiEnhanced.java'
    _CFG = 'F:/mcmod/src/main/java/com/apocalypse/zombies/Config.java'

    _ch = open(_AI, encoding='utf-8').read()
    check('class VillagerChores' in _ch, '新增 entity/ai/VillagerChores')
    check('public static void run(Villager villager, int radius, boolean doors, boolean farm)' in _ch,
          '出口是 run(村民, 半径, 管门?, 管农活?)')
    # ---- 门 ----
    check('instanceof DoorBlock' in _ch, '认得出门方块')
    check('state.getBlock() == Blocks.IRON_DOOR' in _ch, '铁门被排除（那是玩家上锁用的，替它开=绕过门禁）')
    check('level.isDay()' in _ch, '以 isDay 定目标状态：白天开、夜里关')
    check('new AABB(pos).inflate(DOOR_CLEARANCE)' in _ch, '门边有活物就不动手（免得把谁夹在门里）')
    check('DoubleBlockHalf.LOWER' in _ch and 'pos.above() : pos.below()' in _ch,
          '两半手动同步 —— setBlock 不会像玩家交互那样联动另一半')
    check(_ch.count('setValue(DoorBlock.OPEN') == 2, '门的两半各设一次 OPEN',
          '实得 %d' % _ch.count('setValue(DoorBlock.OPEN'))
    # ---- 农活 ----
    check('crop.isMaxAge(state)' in _ch, '只收成熟的（isMaxAge）')
    check('crop.defaultBlockState()' in _ch, '补种用作物方块的默认状态（age 0）')
    check('Block.getDrops(state, level, pos, null, villager,' in _ch, '产物按原版掉落表算')
    check('level.destroyBlock(pos, false, villager)' in _ch, 'destroyBlock(false) —— 掉落自己发，不发两份')
    check('getInventory().addItem' in _ch, '收进村民自己的背包（与原版农民一致）')
    check('Block.popResource(' in _ch, '背包装不下就丢在脚边，不让作物凭空蒸发')
    for _b, _s in (('Blocks.WHEAT', 'Items.WHEAT_SEEDS'), ('Blocks.CARROTS', 'Items.CARROT'),
                   ('Blocks.POTATOES', 'Items.POTATO'), ('Blocks.BEETROOTS', 'Items.BEETROOT_SEEDS')):
        check(_b in _ch and _s in _ch, '种子映射含 %s → %s' % (_b, _s))
    check(_ch.count('getBaseSeedId') == 1,
          '只在注释里提到 getBaseSeedId（1.20.1 上不对外），代码里没调用它',
          '实得 %d 次' % _ch.count('getBaseSeedId'))
    check('offset(-radius, -2, -radius)' in _ch, '扫描带 y 只上下探 2 格（门与庄稼都在地面附近）')

    # ---- 挂载点：必须是村民 tick，不是 goalSelector ----
    _mb = open(_MOB, encoding='utf-8').read()
    check('import com.apocalypse.zombies.entity.ai.VillagerChores;' in _mb, 'MobAiEnhanced import 就位')
    check('VillagerChores.run(villager,' in _mb, 'MobAiEnhanced 调用了它')
    _iv = _mb.index('private static void tickVillager')
    _seg = _mb[_iv:_iv + 1800]
    check('VillagerChores.run' in _seg, '调用点在 tickVillager 里')
    check('VillagerChores.run' in _seg.split('nearestThreat')[0],
          '杂活在恐慌判定**之前**跑 —— 否则一有敌人就再也不关门、不收地了')
    check('goalSelector, 1, VillagerChores' not in _mb,
          '没有把它塞进 goalSelector（村民的移动归 Brain，塞 Goal 会抢 Flag.MOVE）')

    # ---- 配置 ----
    _cf = open(_CFG, encoding='utf-8').read()
    for _f in ('AI_VILLAGER_DOOR_ENABLED', 'AI_VILLAGER_FARM_ENABLED', 'AI_VILLAGER_CHORE_RADIUS'):
        check(_cf.count(_f) == 2, '%s 在 Config 里出现 2 次（字段声明 + define）' % _f,
              '实得 %d' % _cf.count(_f))
    for _k in ('"villager_door_enabled", true', '"villager_farm_enabled", true'):
        check(_k in _cf, 'define %s' % _k)
    check('"villager_chore_radius", 6, 2, 24' in _cf, 'define villager_chore_radius（默认 6，域 2~24）')
    check('Config.AI_VILLAGER_DOOR_ENABLED.get()' in _mb
          and 'Config.AI_VILLAGER_FARM_ENABLED.get()' in _mb
          and 'Config.AI_VILLAGER_CHORE_RADIUS.get()' in _mb, '三项都被 MobAiEnhanced 读上了')

    # ---- 配置总数 151 → 154 ----
    check('154 个字段' in open('F:/mcmod/src/main/java/com/apocalypse/zombies/ApocalypseZombies.java',
                               encoding='utf-8').read(), '启动自检的注释改成 154')
    check('全部 154 项' in open('F:/mcmod/src/main/java/com/apocalypse/zombies/client/gui/'
                                'ApocalypseConfigScreen.java', encoding='utf-8').read(),
          '配置界面注释改成 154')
    _w2 = open('F:/mcmod/docs/wiki/02-代码与资源地图.md', encoding='utf-8').read()
    check('全部 154 项' in _w2, 'wiki 02 记了 154 项')
    check('VillagerChores' in _w2, 'wiki 02 记了 VillagerChores')
    _rd = open('F:/mcmod/readme.md', encoding='utf-8').read()
    check('全部 154 项' in _rd, 'readme 记了 154 项')
    check('### 1.1.96 —' in _rd, 'readme 有 1.1.96 条目')
    check('| **当前版本** | `1.1.97` |' in _rd, 'readme 头表 == 1.1.97')
    check('## 1.1.96 ——' in open('F:/mcmod/docs/wiki/07-出货与版本管理.md', encoding='utf-8').read(),
          'wiki 07 有 1.1.96 小节')

    print('=== 12/17 1.1.97：全部 readme 过一次账 ===')
    # 这一版只改文档。所以判据不是"改了没有"，而是**文档与现状是否一致**：
    # 把每条核过的结论钉成断言 —— 谁再把过期的说法写回去，或者把"仍未做"顺手改成"已做"，就红。
    import os as _os

    _rd = open('F:/mcmod/readme.md', encoding='utf-8').read()
    _w7 = open('F:/mcmod/docs/wiki/07-出货与版本管理.md', encoding='utf-8').read()
    _wr = open('F:/mcmod/docs/wiki/README.md', encoding='utf-8').read()
    _awm = open('F:/mcmod/art/awm/README.md', encoding='utf-8').read()
    _m1 = open('F:/mcmod/art/m1garand/README.md', encoding='utf-8').read()
    _xb = open('F:/mcmod/art/crossbow/DELIVERY.md', encoding='utf-8').read()
    _uz = open('F:/mcmod/art/uzi/DELIVERY.md', encoding='utf-8').read()

    # ---- ① 四处实证错误都改成了现状 ----
    check('已修（1.1.95，2026-10-11 重核更正）' in _xb, 'crossbow 偏差 #9 已标注 1.1.95 修好')
    check('未修，待定' not in _xb, 'crossbow 不再有「图标未修，待定」的说法')
    check('已决（1.1.95）' in _xb, 'crossbow 待定 #2（是否一起放大）已标注已决')
    check('**已做**（本条曾长期停在"未做"' in _uz, 'uzi 的 Java 同步已标注「已做」')
    check('Java 同步 | **未做**' not in _uz, 'uzi 不再自称 Java 同步未做')
    check('1.1.93 起已全部替换' in _awm, 'awm 的音效署名已改成「已替换」')
    check('1.1.93 起已全部替换' in _m1, 'm1garand 的音效署名已改成「已替换」')
    check('未修改副本**（md5 与原件逐一相同）' not in _awm, 'awm 不再自称音效是「未修改副本」')
    check('已接线**：`M1GarandItem.ANIM_DRAW`' in _m1, '加兰德的 draw 已标注接线')
    check('掏枪（尚未接线）' not in _m1, '加兰德 clip 表里不再写 draw「尚未接线」')

    # ---- ② wiki 索引的数字对上了 ----
    check('_deploy_196.py' in _wr, 'wiki 索引指向 _deploy_196.py')
    check('_deploy_140.py' not in _wr, 'wiki 索引不再指向 _deploy_140.py')
    check('1975 行' in _wr, 'wiki 索引写的是 readme 的真实行数（1975）')
    check('238 个 `.py`' in _wr, 'wiki 索引写的是 tools 当前脚本数（238）')
    check('共 18 个' in _wr, 'wiki 索引写的是 check_*.py 的真实数量（18）')
    check('不参与构建' in _wr, 'wiki 索引说清了 mod.toml 不参与构建')

    # ---- ③ 数字是量出来的，别让文档又漂走 ----
    _lines = len(open('F:/mcmod/readme.md', encoding='utf-8').read().split('\n'))
    check(abs(_lines - 1975) <= 40, 'readme 行数仍与文档里写的 1975 同一量级',
          '实得 %d 行' % _lines)
    # 注意：tools/*.py 每出一版会 +3（_deploy_<ver> / _assert_<ver> / _mk_deploy_<ver>），
    # 所以这里给容差 —— 只在"数量级出了大事"（比如误删一批脚本）时才红。写成精确相等是自找的红：
    # 生成门禁这个动作本身就会把这个数顶上去。
    _py = [f for f in _os.listdir('F:/mcmod/tools') if f.endswith('.py')]
    check(abs(len(_py) - 238) <= 15, 'tools/*.py 数量在 238 附近（每版 +3）', '实得 %d' % len(_py))
    _chk = [f for f in _py if f.startswith('check_')]
    check(len(_chk) == 18, 'tools/check_*.py 仍是 18 个', '实得 %d' % len(_chk))

    # ---- ④ 核过「仍未做」的那些要留住，别被顺手改成已做 ----
    check('仍未做' in _awm and 'WeaponMount' in _awm, 'AWM 待办重核：WeaponMount 确实仍未做')
    check('仍未接线' in _awm, 'AWM 待办重核：五段 clip 确实仍未接线')
    check('已接线' in _m1, '加兰德待办重核：draw 已接线')
    check('ANIM_DRAW' in _m1 and 'ANIM_INSPECT' not in _m1.split('## 待办')[-1],
          '加兰德只接了 draw（inspect 仍未做）')

    # ---- ⑤ 版本与日志 ----
    check('### 1.1.97 —' in _rd, 'readme 有 1.1.97 条目')
    check('| **当前版本** | `1.1.97` |' in _rd, 'readme 头表 == 1.1.97')
    check('## 1.1.97 ——' in _w7, 'wiki 07 有 1.1.97 小节')

    print('=== 11/17 基线校验 ===')
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

    print('=== 12/17 换包 ===')
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

    print('=== 13/17 换包后复核 ===')
    now = {f: md5(os.path.join(MODS, f)) for f in os.listdir(MODS) if f.lower().endswith('.jar')}
    same = all(now.get(f) == m for f, m in other_md5.items())
    check(same, '其它模组 md5 全等（没被误伤）', '%d 个' % len(others))
    check(jar_version(os.path.join(MODS, os.path.basename(SRC))) == VER, '装机包版本 == %s' % VER)
    print('\n★ 出货完成：mods/ = %s' % [f for f in now if f.startswith(PREFIX)])
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
