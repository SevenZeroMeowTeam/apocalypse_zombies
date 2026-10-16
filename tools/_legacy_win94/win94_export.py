# -*- coding: utf-8 -*-
"""win94 交付导出 —— 把 Blockbench 里的工程落成 Java 侧要的两个资源文件。

  1) save_project       把内存里的最新工程写回 win94.bbmodel（后面要读它取动画）
  2) execute_script     设模型 identifier = "geometry.win94"（与旧资源/JAVA 侧保持一致）
  3) export_model       用 bedrock codec 导出 geo/win94.geo.json（GeckoLib 就是 bedrock 派生）
  4) 本地转换           把 bbmodel 的 animations 转成 GeckoLib 的 animation.json 写法：
                          {format_version, animations:{<clip>:{loop, animation_length, bones:{...}}}}
                        每个关键帧写成 {"post":{"vector":[x,y,z]},"lerp_mode":...}

GeckoLib 的动画 codec 在 MCP 里调不到（export 会弹保存对话框），而 bbmodel 里本来就存着
完整关键帧，所以这一步在本地做 —— 数据来源仍是 Blockbench 写出的 bbmodel，没有手改。

用法：python tools/win94_export.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import bbmcp  # noqa: E402

BBMODEL = ROOT / 'win94.bbmodel'
GEO_OUT = ROOT / 'src' / 'main' / 'resources' / 'assets' / 'apocalypse_zombies' / 'geo' / 'win94.geo.json'
ANIM_OUT = ROOT / 'src' / 'main' / 'resources' / 'assets' / 'apocalypse_zombies' / 'animations' / 'win94.animation.json'

SET_ID_JS = """
Project.model_identifier = 'win94';
if (Project.geckolib_model_identifier !== undefined) Project.geckolib_model_identifier = 'win94';
return { identifier: Project.model_identifier, name: Project.name };
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
    return out


def main():
    # 1) 把 Blockbench 内存里的最新工程写盘
    r = bbmcp.call('save_project', {'path': str(BBMODEL)}, timeout=300)
    if not r.get('ok'):
        print('save_project FAIL', json.dumps(r, ensure_ascii=False)[:400])
        return 1
    print('[save_project]', json.dumps(r.get('result'), ensure_ascii=False)[:200])

    # 2) identifier 与旧资源对齐
    r = bbmcp.call('execute_script', {'code': SET_ID_JS}, timeout=120)
    print('[identifier]', json.dumps(r.get('result'), ensure_ascii=False)[:200])

    # 3) geo 导出
    GEO_OUT.parent.mkdir(parents=True, exist_ok=True)
    r = bbmcp.call('export_model', {'codec': 'bedrock', 'path': str(GEO_OUT)}, timeout=600)
    if not r.get('ok'):
        print('export_model FAIL', json.dumps(r, ensure_ascii=False)[:400])
        return 1
    print('[geo]', json.dumps(r.get('result'), ensure_ascii=False)[:200])

    geo = json.loads(GEO_OUT.read_text(encoding='utf-8'))
    desc = geo['minecraft:geometry'][0]['description']
    n_cubes = len(geo['minecraft:geometry'][0].get('bones', []))
    print(f'  identifier={desc.get("identifier")} tex={desc.get("texture_width")}x{desc.get("texture_height")} bones={n_cubes}')

    # 4) 动画转换
    data = json.loads(BBMODEL.read_text(encoding='utf-8'))
    anims = convert_animations(data)
    payload = {'format_version': '1.8.0', 'animations': anims}
    ANIM_OUT.parent.mkdir(parents=True, exist_ok=True)
    ANIM_OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    print(f'[anim] {ANIM_OUT.name}: {len(anims)} clips')
    for name, a in anims.items():
        nk = sum(len(ks) for ch in a['bones'].values() for ks in ch.values())
        print(f'  {name:18s} loop={str(a["loop"]):5s} len={a["animation_length"]:4} '
              f'ticks={int(a["animation_length"] * 20 + 0.999):3d} bones={len(a["bones"]):2d} kf={nk:3d}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
