#!/usr/bin/env python3
"""把 tools/win94_paint3.py 画好的 512² 贴图**通过 MCP** 装进 Blockbench 工程。

顺序：删掉旧贴图（旧 UV 时代的残留）→ import_texture 新图 → apply_texture 重绑所有方块。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import bbmcp  # noqa: E402

TEX = ROOT / 'src' / 'main' / 'resources' / 'assets' / 'apocalypse_zombies' / 'textures' / 'item' / 'win94.png'

DROP_JS = """
const n = Texture.all.length;
Texture.all.slice().forEach((t) => t.remove());
return { removed: n, left: Texture.all.length };
"""

# import_texture 会用**文件名**当贴图名（win94.png），这里改回工程约定的短名。
RENAME_JS = """
const t = Texture.all[Texture.all.length - 1];
if (!t) return { error: 'no texture' };
const old = t.name;
t.name = 'win94';
return { old, now: t.name, w: t.width, h: t.height };
"""


def main():
    if not TEX.exists():
        print('贴图不存在，先跑 tools/win94_paint3.py:', TEX)
        return 1
    steps = [
        ('drop textures', 'execute_script', {'code': DROP_JS}),
        ('import', 'import_texture', {'path': str(TEX.resolve()), 'name': 'win94'}),
        ('rename', 'execute_script', {'code': RENAME_JS}),
        ('apply', 'apply_texture', {'texture': 'win94'}),
        ('list', 'list_textures', {}),
        ('check', 'check_model', {}),
    ]
    for label, action, params in steps:
        res = bbmcp.call(action, params, timeout=300)
        if not res.get('ok'):
            print(f'[{label}] FAIL :: {json.dumps(res, ensure_ascii=False)[:700]}')
            return 1
        out = res.get('result')
        brief = json.dumps(out, ensure_ascii=False)
        print(f'[{label}] OK :: {brief[:300]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
