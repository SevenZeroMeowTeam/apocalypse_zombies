# -*- coding: utf-8 -*-
"""win94 导出 —— 把 Blockbench 里的工程落成 Java 侧要的资源文件。

  1) save_project   把内存里的最新工程写回 win94.bbmodel（也是动画的原始数据来源）
  2) execute_script 设 identifier（Bedrock 侧导出成 geometry.win94，与 Java 侧一致）
  3) export_model   bedrock codec 导出 geo/win94.geo.json
  4) 本地转换       bbmodel 的 animations → GeckoLib 的 animation.json：
                    {format_version, animations:{<clip>:{loop, animation_length, bones:{...}}}}
                    每个关键帧写成 {"post":{"vector":[x,y,z]},"lerp_mode":...}
                    每个通道的键按时间升序（零时间戳在首）—— GeckoLib 的硬约束，
                    违反会令客户端在资源加载阶段崩溃（2026-10-16 事故）。

GeckoLib 的动画 codec 在 MCP 里调不到（export 会弹保存对话框），而 bbmodel 本来就存着完整关键帧，
所以这一步在本地做 —— 数据来源仍是 Blockbench 写出的 bbmodel，没有手改。

用法：python tools/win94/export.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'tools'))
import bbmcp  # noqa: E402
import spec as S  # noqa: E402

BBMODEL = S.BBMODEL
ASSETS = S.ASSETS
GEO_OUT = ASSETS / 'geo' / 'win94.geo.json'
ANIM_OUT = ASSETS / 'animations' / 'win94.animation.json'

SET_ID_JS = """
Project.model_identifier = 'win94';
if (Project.geckolib_model_identifier !== undefined) Project.geckolib_model_identifier = 'win94';
Project.name = 'win94';
return { identifier: Project.model_identifier, name: Project.name, format: Format.id };
"""

LERP = {'catmullrom': 'catmullrom', 'linear': 'linear', 'step': 'step', 'bezier': 'catmullrom'}
LOOP = {'loop': True, 'once': False, 'hold': 'hold'}


def tkey(t):
    s = f'{float(t):.4f}'.rstrip('0').rstrip('.')
    return s if s else '0'


def convert_animations(data):
    out = {}
    for anim in data.get('animations', []):
        name = (anim.get('name') or '').replace('animation.', '')
        bones = {}
        for _uuid, an in (anim.get('animators') or {}).items():
            bone = an.get('name')
            if not bone:
                continue
            for k in an.get('keyframes', []):
                dps = k.get('data_points') or []
                if not dps:
                    continue
                d0 = dps[0]
                vec = [float(d0.get('x', 0)), float(d0.get('y', 0)), float(d0.get('z', 0))]
                ch = bones.setdefault(bone, {}).setdefault(k['channel'], {})
                ch[tkey(k['time'])] = {
                    'post': {'vector': vec},
                    'lerp_mode': LERP.get(k.get('interpolation'), 'catmullrom'),
                }
        out[name] = {
            'loop': LOOP.get(anim.get('loop'), False),
            'animation_length': round(float(anim.get('length') or 0), 4),
            'bones': bones,
        }
    # GeckoLib 契约：每个通道的键必须按时间升序（零时间戳在首）。
    # 违反时 BakedAnimationsAdapter 抛 "multiple starting keyframes"，
    # 整包动画解析失败 → 客户端在资源加载阶段崩溃（bbmodel 里的数组顺序不保证）。
    for a in out.values():
        for chans in a['bones'].values():
            for chan, ks in chans.items():
                chans[chan] = {k: ks[k] for k in sorted(ks, key=float)}
    return out


def check_geckolib(anims):
    """复刻 GeckoLib BakedAnimationsAdapter.getKeyframes 的硬约束，返回问题列表。"""
    problems = []
    for name, a in anims.items():
        for bone, chans in a['bones'].items():
            for chan, ks in chans.items():
                for i, k in enumerate(ks):
                    try:
                        t = float(k)
                    except ValueError:
                        t = 0.0
                    if t == 0 and i > 0:
                        problems.append(f'{name}/{bone}.{chan}: 零时间戳键 "{k}" 不在首位')
    return problems


def main():
    r = bbmcp.call('save_project', {'path': str(BBMODEL)}, timeout=300)
    if not r.get('ok'):
        print('save_project FAIL', json.dumps(r, ensure_ascii=False)[:400])
        return 1
    print('[save_project]', json.dumps(r.get('result'), ensure_ascii=False)[:180])

    r = bbmcp.call('execute_script', {'code': SET_ID_JS}, timeout=120)
    print('[identifier]', json.dumps(r.get('result'), ensure_ascii=False)[:180])

    GEO_OUT.parent.mkdir(parents=True, exist_ok=True)
    r = bbmcp.call('export_model', {'codec': 'bedrock', 'path': str(GEO_OUT)}, timeout=600)
    if not r.get('ok'):
        print('export_model FAIL', json.dumps(r, ensure_ascii=False)[:400])
        return 1
    print('[geo]', json.dumps(r.get('result'), ensure_ascii=False)[:180])

    geo = json.loads(GEO_OUT.read_text(encoding='utf-8'))
    g0 = geo['minecraft:geometry'][0]
    desc = g0['description']
    print(f"  identifier={desc.get('identifier')} tex={desc.get('texture_width')}x"
          f"{desc.get('texture_height')} bones={len(g0.get('bones', []))} "
          f"cubes={sum(len(b.get('cubes', [])) for b in g0.get('bones', []))}")

    data = json.loads(BBMODEL.read_text(encoding='utf-8'))
    anims = convert_animations(data)
    gecko_bad = check_geckolib(anims)
    if gecko_bad:
        print('!! GeckoLib 关键帧契约不通过（写出会让客户端启动崩溃）：')
        for b in gecko_bad[:10]:
            print('   [x]', b)
        return 1
    payload = {'format_version': '1.8.0', 'animations': anims}
    ANIM_OUT.parent.mkdir(parents=True, exist_ok=True)
    ANIM_OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    print(f'[anim] {ANIM_OUT.name}: {len(anims)} clips')
    missing = [a for a in S.CONTRACT_ANIMS if a not in anims]
    for name, a in anims.items():
        nk = sum(len(ks) for chn in a['bones'].values() for ks in chn.values())
        mark = '' if name in S.CONTRACT_ANIMS else '  <-- 契约外的 clip'
        print(f'  {name:18s} loop={str(a["loop"]):5s} len={a["animation_length"]:4} '
              f'ticks={int(a["animation_length"] * 20 + 0.999):3d} '
              f'bones={len(a["bones"]):2d} kf={nk:3d}{mark}')
    if missing:
        print('!! 缺契约 clip:', missing)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
