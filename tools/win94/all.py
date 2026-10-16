# -*- coding: utf-8 -*-
"""win94 一键重建：几何 → 经 MCP 建进 Blockbench → 贴图 → 动画 → 导出。

同进程内依次调用各模块的 main()（不 spawn 子进程，沙箱下最稳）。

用法：
  python tools/win94/all.py              # 全链路
  python tools/win94/all.py geom         # 只生成几何 JSON（不动 Blockbench）
  python tools/win94/all.py build        # 几何 JSON + 建进 Blockbench + 贴图
  python tools/win94/all.py anim         # 只写动画
  python tools/win94/all.py export       # 只导出资源
"""
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import model  # noqa: E402
import build  # noqa: E402
import tex  # noqa: E402


def step(label, fn):
    print(f'\n===== {label} =====', flush=True)
    rc = fn()
    if rc:
        print(f'!! {label} 失败 rc={rc}', flush=True)
        raise SystemExit(rc)
    return rc


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    try:
        step('1/5 几何 JSON', model.main)
        if mode == 'geom':
            return 0
        step('2/5 建进 Blockbench', build.main)
        step('3/5 贴图', tex.main)
        if mode == 'build':
            return 0
        import anim
        import export
        step('4/5 动画', anim.main)
        if mode == 'anim':
            return 0
        step('5/5 导出资源', export.main)
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        return 1
    print('\n全部完成。', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
