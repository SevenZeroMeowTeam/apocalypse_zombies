# -*- coding: utf-8 -*-
"""猫耳娘尾巴摆动：按「逐节相位波」重写 tail1..tail4 的 rotation 通道。

为什么单开一个工具：动画文件是**可复跑生成**的，不能手改（改一次就再也对不上）。
这个脚本把尾巴四节的通道按同一套参数算出来，跑几次结果都一样。

参数（想调尾巴手感改这里）：
  idle  周期 2.0s：摆幅 20/13/11/9 度（Y 轴左右摆），Z 轴扭转 4/5/6/7 度，
        四节相位依次 +0.00 / +0.12 / +0.24 / +0.36 个周期 —— 波从尾根往尾尖走，才是猫甩尾。
  walk  周期 1.0s：左右摆小一点、扭转大一点（走路时尾巴甩得更「活」）。

用法：
    py tools/cat_girl_tail_sway.py            # 写入（自动留 .bak.json）
    py tools/cat_girl_tail_sway.py --check    # 只校验当前文件是否就是本参数算出来的
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANIM = ROOT / 'src' / 'main' / 'resources' / 'assets' / 'apocalypse_zombies' / 'animations' / 'cat_girl.animation.json'

#           尾根 → 尾尖
TAIL = ['tail1', 'tail2', 'tail3', 'tail4']

SPECS = {
    #                      X 基准   左右摆  扭转   相位    周期  关键帧数
    'idle': [(0.0, -10.0), (20.0, 4.0), (13.0, 5.0), (11.0, 6.0), (9.0, 7.0)],
    'walk': [(0.0, -16.0), (16.0, 5.0), (12.0, 6.0), (10.0, 7.0), (8.0, 8.0)],
}
PERIOD = {'idle': 2.0, 'walk': 1.0}
PHASE = [0.00, 0.12, 0.24, 0.36]
STEPS = 4  # 每周期 4 段 → 5 个关键帧（含收尾），正弦够顺


def wave(amp_y: float, amp_z: float, base_x: float, phase: float, period: float) -> dict:
    """返回一个 rotation 通道：X 固定基准，Y/Z 走相位差正弦 —— 逐节相位差 = 波的传播。"""
    keys = {}
    for i in range(STEPS + 1):
        t = round(period * i / STEPS, 2)
        ph = (i / STEPS + phase) * 2.0 * math.pi
        keys['%.1f' % t] = {
            'easing': 'easeInOutSine',
            'vector': [round(base_x, 1),
                       round(amp_y * math.sin(ph), 1),
                       round(amp_z * math.cos(ph), 1)],
        }
    return {'rotation': keys}


def build_tails(anim_name: str) -> dict:
    spec = SPECS[anim_name]
    period = PERIOD[anim_name]
    base_x = spec[0][1]          # 第一项第二格 = 尾巴整体的固定 X 基准（抬头角）
    out = {}
    for i, bone in enumerate(TAIL):
        amp_y, amp_z = spec[1 + i]   # 左右摆、扭转；四节相位依次后移 = 波从尾根往尾尖走
        out[bone] = wave(amp_y, amp_z, base_x, PHASE[i], period)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()

    if not ANIM.is_file():
        print('动画文件不存在：%s' % ANIM)
        return 1
    original = ANIM.read_text(encoding='utf-8')
    data = json.loads(original)
    animations = data.get('animations', data)

    changed = []
    for name in ('idle', 'walk'):
        if name not in animations:
            print('动画里没有 %s，跳过' % name)
            continue
        tails = build_tails(name)
        bones = animations[name].setdefault('bones', {})
        for bone, channel in tails.items():
            if bones.get(bone) != channel:
                changed.append('%s/%s' % (name, bone))
            bones[bone] = channel

    new_text = json.dumps(data, ensure_ascii=False, indent=1) + '\n'
    same = hashlib.sha256(new_text.encode('utf-8')).hexdigest() == hashlib.sha256(original.encode('utf-8')).hexdigest()

    if a.check:
        if same:
            print('尾巴摆动已是当前参数（idle/walk 各 4 节，无差异）')
            return 0
        print('尾巴摆动与当前参数不一致，需要重跑：%s' % ', '.join(changed))
        return 1

    if same:
        print('尾巴摆动已是最新，无需写入')
        return 0

    shutil.copyfile(ANIM, ANIM.with_suffix('.json.bak.json'))
    ANIM.write_text(new_text, encoding='utf-8')
    print('尾巴摆动已写入（%d 处）：%s' % (len(changed), ', '.join(changed)))
    for name in ('idle', 'walk'):
        t = data['animations'][name]['bones']
        print('  %-5s 周期 %.1fs  尾尖 %s Y %s' % (
            name, animations[name].get('animation_length', 0), 'tail4',
            [v['vector'][1] for _, v in sorted(t['tail4']['rotation'].items(), key=lambda kv: float(kv[0]))]))
    print('  备份：%s' % ANIM.with_suffix('.json.bak.json').name)
    return 0


if __name__ == '__main__':
    sys.exit(main())
