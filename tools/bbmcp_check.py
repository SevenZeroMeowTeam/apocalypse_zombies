#!/usr/bin/env python3
"""check_model / check_rig / audit_complexity 的汇总器 —— 只看分类计数与前几条，别刷屏。

用法：
  python tools/bbmcp_check.py              # check_model 汇总
  python tools/bbmcp_check.py check_rig
  python tools/bbmcp_check.py audit_complexity
  python tools/bbmcp_check.py check_model --all     # 每类全列（默认每类 6 条）
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bbmcp  # noqa: E402


def main():
    action = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('-') else 'check_model'
    show_all = '--all' in sys.argv
    res = bbmcp.call(action, {}, timeout=300)
    if not res.get('ok'):
        print('FAIL', json.dumps(res, ensure_ascii=False)[:600])
        return 1
    out = res.get('result') or {}

    print(f'== {action} ==')
    for k in ('cubes', 'groups', 'textures', 'texture_size', 'animation_format',
              'max_cubes', 'max_bones', 'cube_count', 'bone_count', 'complexity', 'verdict'):
        if k in out:
            print(f'{k}: {out[k]}')

    # audit_complexity 的结构不同：可能有 counts / issues / notes
    issues = out.get('issues') or []
    by = out.get('by_type') or dict(Counter(i.get('issue') for i in issues))
    print(f"issue_count: {out.get('issue_count', len(issues))}")
    print('by_type:', json.dumps(by, ensure_ascii=False))

    per = 10 ** 9 if show_all else 6
    cnt = Counter()
    for it in issues:
        t = it.get('issue')
        cnt[t] += 1
        if cnt[t] > per:
            continue
        brief = {k: v for k, v in it.items() if k not in ('hint',)}
        print(f"  [{t}] {json.dumps(brief, ensure_ascii=False)[:320]}")
        if it.get('hint'):
            print(f"        hint: {str(it['hint'])[:200]}")
    for t, n in cnt.items():
        if n > per:
            print(f'  [{t}] ... 另有 {n - per} 条同类型（--all 看全部）')

    for k in ('notes', 'warnings', 'next'):
        if out.get(k):
            v = out[k]
            print(f'{k}: {json.dumps(v, ensure_ascii=False)[:900]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
