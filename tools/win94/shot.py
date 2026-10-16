# -*- coding: utf-8 -*-
"""win94 截图 —— 把相机摆到固定机位再截，方便目视核对几何/动画。

用法：
  python tools/win94/shot.py                 # 侧视（默认）
  python tools/win94/shot.py side iso top    # 多机位
  python tools/win94/shot.py side --t 0.5    # 动画时间轴（需先 preview_animation）
  python tools/win94/shot.py iso --anim bolt --t 0.52   # 指定动画 + 时间点

机位（模型 bounds：x ±0.4、y −3.32…1.19、z −10.77…7.06，中心 ≈ (0, −1.1, −1.9)）：
  side  = 从 +X 侧看（枪的右侧），iso = 斜前上方，top = 俯视
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'tools'))
import bbmcp  # noqa: E402

OUT = ROOT / 'build' / 'win94' / 'shots'

CAM = {
    'side':   {'position': [26, -1.0, -1.9], 'target': [0, -1.0, -1.9]},
    'side2':  {'position': [-26, -1.0, -1.9], 'target': [0, -1.0, -1.9]},
    'iso':    {'position': [17, 9, -16], 'target': [0, -0.8, -1.9]},
    'top':    {'position': [0, 22, -1.9], 'target': [0, -0.8, -1.9]},
    'lever':  {'position': [10, -2.2, 1.0], 'target': [0, -1.3, -0.3]},
    'joint':  {'position': [5.5, -1.15, -1.3], 'target': [0, -1.75, 0.20]},   # 杆↔环连接处特写
    'action': {'position': [9, 3.0, -1.6], 'target': [0, -0.6, -1.6]},
    'scope':  {'position': [9, 3.4, -3.5], 'target': [0, 0.55, -3.5]},
    'muzzle': {'position': [7, 1.2, -12.5], 'target': [0, -0.2, -9.0]},
}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    views = args or ['side']
    anim = None
    t = None
    for i, a in enumerate(sys.argv):
        if a == '--anim':
            anim = sys.argv[i + 1]
        if a == '--t':
            t = float(sys.argv[i + 1])

    if anim and t is not None:
        r = bbmcp.call('execute_script', {'code': """
const a = Animation.all.find((x) => x.name === params.name);
if (!a) return { error: 'no anim ' + params.name, have: Animation.all.map((x) => x.name) };
a.selected = true;
if (Animator && Animator.preview) Animator.preview();
a.setTime ? a.setTime(params.time) : (Timeline.time = params.time);
if (Animator && Animator.preview) Animator.preview();
return { name: a.name, time: (typeof Timeline !== 'undefined' ? Timeline.time : null) };
""", 'params': {'name': anim, 'time': t}}, timeout=120)
        print('[anim]', json.dumps(r.get('result'), ensure_ascii=False)[:200], 'ok=', r.get('ok'))

    OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%H%M%S')
    for v in views:
        cam = CAM.get(v)
        if not cam:
            print('!! 未知机位', v, '可用：', ', '.join(CAM))
            continue
        bbmcp.call('set_camera_angle', cam, timeout=120)
        res = bbmcp.call('screenshot', {'width': 1400, 'height': 700, 'annotate': False}, timeout=300)
        if not res.get('ok'):
            print(f'[{v}] FAIL {json.dumps(res, ensure_ascii=False)[:300]}')
            continue
        out = res['result']
        b64 = out.get('base64') or ''
        import base64
        p = OUT / f'{v}_{anim or "static"}_{str(t).replace(".", "p") if t is not None else ""}_{stamp}.png'
        p.write_bytes(base64.b64decode(b64))
        print(f'[{v}] -> {p.relative_to(ROOT)}  ({p.stat().st_size} B)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
