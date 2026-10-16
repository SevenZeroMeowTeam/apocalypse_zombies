# -*- coding: utf-8 -*-
"""打印 GeckoLib animation.json 的通道结构（写导出器前先看清 shape）。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
d = json.loads((ROOT / 'tools' / 'win94_anim_backup.json').read_text(encoding='utf-8'))
print('format_version =', d.get('format_version'))
print('animations =', list(d['animations'].keys()))
for name, anim in d['animations'].items():
    print(f'\n=== {name}  loop={anim.get("loop")}  len={anim.get("animation_length")}')
    print('  top keys:', [k for k in anim.keys() if k != 'bones'])
    for bone, chans in list(anim['bones'].items()):
        print(f'  bone {bone}: channels={list(chans.keys())}')
        for ch, keys in chans.items():
            t0 = sorted(keys.keys(), key=float)[0]
            print(f'    {ch} @{t0} -> {json.dumps(keys[t0], ensure_ascii=False)[:220]}')
            break
        break
    # 找一个含 scale 的骨骼
    for bone, chans in anim['bones'].items():
        if 'scale' in chans:
            t0 = sorted(chans['scale'].keys(), key=float)[0]
            print(f'    [scale sample] bone={bone} @{t0} -> {json.dumps(chans["scale"][t0], ensure_ascii=False)[:220]}')
            break
    for bone, chans in anim['bones'].items():
        if 'position' in chans:
            t0 = sorted(chans['position'].keys(), key=float)[0]
            print(f'    [position sample] bone={bone} @{t0} -> {json.dumps(chans["position"][t0], ensure_ascii=False)[:220]}')
            break
    # step 插值的写法
    for bone, chans in anim['bones'].items():
        for ch, keys in chans.items():
            for t, v in keys.items():
                if isinstance(v, dict) and v.get('lerp_mode') not in (None, 'catmullrom'):
                    print(f'    [lerp sample] {bone}.{ch} @{t} -> {json.dumps(v, ensure_ascii=False)[:200]}')
                    break
            else:
                continue
            break
        else:
            continue
        break
