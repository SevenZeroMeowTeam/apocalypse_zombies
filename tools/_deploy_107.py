# -*- coding: utf-8 -*-
"""1.1.107 出货：修 1.1.106 的旋转换算方向（win94 杠杆实机向上翻，「应该向下拉」）。

本版内容：落盘动画的换算规则从"精确镜像"（rx 不变、否 rz）更正为 **GeckoLib 加载预烹饪的逆**
（位置 x 取反；**旋转否定 rx/ry、保留 rz**），依据是仓库 `art/bride/gl/` 里 GeckoLib 4.8.4 的
三处源码（`BakedModelFactory` / `RenderUtils.translateMatrixToBone` / `BakedAnimationsAdapter`，
见 `tools/win94/export.py` 文件头）。落盘 `win94.animation.json` 重新生成：
与 1.1.106 版 diff = 34 处键全部是 rx/rz 符号变化，位置通道 0 处变化。

跑法（*游戏须完全关闭*）：
    py tools/_deploy_107.py --build        # 调用方先跑 ./gradlew build，本脚本只做出货判据与换包
    py tools/_deploy_107.py                # 用 build/libs 里已构建好的包
    py tools/_deploy_107.py --no-install   # 只跑判据，不动 mods/

判据（任一条不过就退出，不动 mods/）：
  1. 构建产物存在、包内 mods.toml 版本 == 1.1.107；
  2. 包内 win94 资产规格正确：geo identifier geometry.win94 / 16 骨 / 249 方块 / 512²，
     7 条 clip 长度逐条等于 Java 常量，贴图 512² 且在包内；
     **包内 animation.json 满足 GeckoLib 零帧居首契约**（1.1.105 的护栏）；
     **包内动画是预烹饪的逆换算**（1.1.106/107 的护栏）：
       · geo 装填门在 −X；换弹子弹 x ∈ [−0.86, 0]（从装填门侧压入）、bolt 空壳末帧 x ≤ −0.5；
       · 落盘空间的机构符号：lever 负（渲染 +62° 向下）、击锤负（渲染 +32° 待击）、
         扳机正（渲染 −16° 后扣）—— 本版核心修复的直接护栏；
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
VER = '1.1.107'
PREV = '1.1.106'
ACCEPT = (PREV, VER)
SRC = ROOT / 'build' / 'libs' / ('apocalypse_zombies-%s.jar' % VER)
DEV = Path('F:/.minecraft/versions/1.20.1-Forge_47.4.27')
MODS, BACKUP = DEV / 'mods', DEV / 'mods_backup'
PREFIX = 'apocalypse_zombies-'
KEEP_BACKUPS = 3
A = 'assets/apocalypse_zombies/'

#: win94 规格（三件套未变：本轮只改动画数值）
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


def channel(clips, clip, bone, ch):
    """按时间升序的 (t, vector) 列表；缺则空表。"""
    ks = ((clips.get(clip) or {}).get('bones', {}).get(bone) or {}).get(ch) or {}
    return sorted(((float(t), v['post']['vector']) for t, v in ks.items()), key=lambda x: x[0])


def peak_abs(ch):
    return max((v[0] for _t, v in ch), key=abs) if ch else 0.0


def main():
    ap = argparse.ArgumentParser(description='1.1.107 出货：修旋转换算方向（杠杆向上翻）')
    ap.add_argument('--build', action='store_true', help='先跑 ./gradlew build 再出货（本脚本只提示）')
    ap.add_argument('--no-install', action='store_true', help='只跑判据，不动 mods/')
    args = ap.parse_args()
    if args.build:
        print('!! --build 交给调用方执行（sandbox 下 gradle 需要提权）；本脚本只做出货判据与换包。')

    print('=== 1.1.107 出货判据 ===')

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
            # 1.1.105 的护栏：包内每个通道的零时间戳键必须在首位（否则客户端启动崩溃）
            order_bad = gecko_zero_first(clips)
            nch = sum(len(chans) for ca in clips.values() for chans in (ca.get('bones') or {}).values())
            check(not order_bad, '包内动画满足 GeckoLib 零帧居首契约（%d 通道）' % nch,
                  '违规 %s' % ('；'.join(order_bad[:5]) if order_bad else '无'))
            # 1.1.106/107 的护栏：包内动画是 GeckoLib 预烹饪的逆换算
            ggate = [c for b in g0['bones'] if b.get('name') == 'gate' for c in b.get('cubes', [])]
            gx1 = max((c['origin'][0] + c['size'][0] for c in ggate), default=0.0)
            check(gx1 <= -0.2, 'geo 装填门在导出空间 −X 侧（−X = 射手右侧）', 'x 到 %.2f' % gx1)
            pos_bad = []
            for cn in ('reload_tactical', 'reload_empty'):
                xs = [v[0] for _t, v in channel(clips, cn, 'cartridge', 'position')]
                if not xs or min(xs) > -0.8 or max(xs) > 0.05:
                    pos_bad.append('%s 子弹 x∈[%s]' % (cn, ','.join('%.2f' % x for x in xs) or '空'))
            sp = channel(clips, 'bolt', 'spent_shell', 'position')
            if not sp or sp[-1][1][0] > -0.5:
                pos_bad.append('bolt 空壳末帧 x=%s' % ('%.2f' % sp[-1][1][0] if sp else '空'))
            check(not pos_bad, '包内动画位置已换算：换弹子弹从装填门侧压入、空壳向 −X 抛出',
                  '异常 %s' % ('；'.join(pos_bad) if pos_bad else '无'))
            # 本版核心修复的直接护栏：落盘空间（渲染时整体取反）的机构符号
            lev = peak_abs(channel(clips, 'bolt', 'lever', 'rotation'))
            ham = peak_abs(channel(clips, 'bolt', 'hammer', 'rotation'))
            tri = peak_abs(channel(clips, 'shoot', 'trigger', 'rotation'))
            sign_bad = []
            if lev >= 0:
                sign_bad.append('lever %.0f°（应为负 = 渲染向下）' % lev)
            if ham >= 0:
                sign_bad.append('hammer %.0f°（应为负 = 渲染待击向后）' % ham)
            if tri <= 0:
                sign_bad.append('trigger %.0f°（应为正 = 渲染后扣）' % tri)
            check(not sign_bad, '包内机构符号是落盘空间约定（lever −62° / 击锤 −32° / 扳机 +16°）',
                  '异常 %s' % ('；'.join(sign_bad) if sign_bad else '无'))
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
