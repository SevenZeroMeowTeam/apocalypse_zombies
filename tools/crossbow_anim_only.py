# -*- coding: utf-8 -*-
"""只重生成弩的**动画**文件（跳过 geo 与贴图）。

为什么必须有这个工具：`crossbow_v2.py` 的 `write_all()` 会一口气重写四份文件
（art/geo、art/动画、art/贴图 + res 里的对应三份）。但仓库里的 **geo 与贴图来自比该生成器
更新的版本** —— 原样重跑会让它们倒退回旧版。实测（1.1.91）：重跑后
`crossbow.geo.json`（art 与 res 两份）与两张 `crossbow*.png` 的 md5 全都变了，
只有 `crossbow.animation.json` 逐字节一致。

所以改动画时只取 `write_all()` 的动画那一半：动画是可复现的，geo / 贴图交给仓库里的版本。

跑法（在 F:/mcmod 下）：
    python tools/crossbow_anim_only.py

产出（两份内容相同，与 write_all 的约定一致）：
    art/crossbow/crossbow.animation.json
    src/main/resources/assets/apocalypse_zombies/animations/crossbow.animation.json

安全边界：本工具**只写这两个动画文件**，绝不碰 geo / png。
"""
import copy
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(HERE, 'tools', 'crossbow_v2.py')

spec = importlib.util.spec_from_file_location('crossbow_v2', GEN)
cb2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cb2)

anims = cb2.build_anims()
doc = {'format_version': '1.8.0', 'animations': anims, 'geckolib_format_version': 2}
# 必须过这一层取反：build_anims 写的是内部坐标约定，与游戏里那份差一次取反。
out = cb2.cb1.game_convention_anims(copy.deepcopy(doc))
text = json.dumps(out, ensure_ascii=False, indent=2)

targets = [
    os.path.join(cb2.ART, cb2.NAME + '.animation.json'),
    os.path.join(cb2.RES, 'animations', cb2.NAME + '.animation.json'),
]
for p in targets:
    before = os.path.getsize(p) if os.path.isfile(p) else -1
    with open(p, 'w', encoding='utf-8') as f:
        f.write(text)
    print('  %-70s %d → %d 字节' % (os.path.relpath(p, HERE).replace('\\', '/'),
                                    before, os.path.getsize(p)))

print('片段 %d 段：%s' % (len(out['animations']),
                         ', '.join('%s(%.2fs%s)' % (k, v['animation_length'],
                                                    ',loop' if v.get('loop') else '')
                                   for k, v in out['animations'].items())))
print('（geo / 贴图未动 —— 它们由仓库里的版本作准，见本文件顶部说明）')
