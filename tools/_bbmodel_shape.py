# -*- coding: utf-8 -*-
"""打印 win94.bbmodel 的 outliner 结构（写门禁脚本前先确认字段名）。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
d = json.loads((ROOT / 'win94.bbmodel').read_text(encoding='utf-8'))
print('top keys:', sorted(d.keys()))
print('elements:', len(d.get('elements', [])))
print('outliner type:', type(d.get('outliner')).__name__, 'len:', len(d.get('outliner') or []))


def shape(node, depth=0, maxdepth=3):
    pad = '  ' * depth
    if isinstance(node, str):
        print(f'{pad}- uuid {node[:8]}')
        return
    print(f'{pad}- group name={node.get("name")!r} keys={sorted(node.keys())}')
    if depth >= maxdepth:
        return
    for ch in node.get('children') or []:
        shape(ch, depth + 1, maxdepth)


for n in (d.get('outliner') or [])[:2]:
    shape(n)
e0 = (d.get('elements') or [{}])[0]
print('element[0] keys:', sorted(e0.keys()))
print('element[0]:', json.dumps({k: e0[k] for k in list(e0)[:8]}, ensure_ascii=False)[:300])
