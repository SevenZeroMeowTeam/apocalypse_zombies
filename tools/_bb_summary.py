#!/usr/bin/env python3
"""解析 .bbmodel，打印骨骼树 / 动画通道 / 纹理摘要。

用法：
  python tools/_bb_summary.py win94.bbmodel
  python tools/_bb_summary.py win94.bbmodel --anim lever     # 只详列名字含 lever 的动画
  python tools/_bb_summary.py win94.bbmodel --cubes U         # 详列名字含 U 的 cube
"""
import json
import sys


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


ELEMS = {}
GROUPS = {}


def node_of(n):
    """outliner 项可能是 group 对象（含 uuid+children）、cube 的 uuid 字符串。"""
    if isinstance(n, str):
        return ELEMS.get(n) or {'name': n, 'type': 'cube', 'missing': True}
    if 'name' not in n and n.get('uuid') in GROUPS:
        g = dict(GROUPS[n['uuid']])
        g['children'] = n.get('children') or g.get('children') or []
        return g
    return n


def walk(nodes, depth, out):
    for raw in nodes:
        n = node_of(raw)
        if n.get('type') == 'cube':
            f, t = n.get('from', [0, 0, 0]), n.get('to', [0, 0, 0])
            out.append(f"{'  ' * depth}- [cube] {n.get('name')}  "
                       f"from={[round(v, 2) for v in f]} to={[round(v, 2) for v in t]} "
                       f"rot={[round(v, 1) for v in n.get('rotation', [0, 0, 0])]} "
                       f"origin={[round(v, 2) for v in n.get('origin', [0, 0, 0])]} "
                       f"faces={sum(1 for v in (n.get('faces') or {}).values() if v.get('texture'))}")
        else:
            nm = n.get('name') or ('group:' + str(n.get('uuid'))[:8])
            out.append(f"{'  ' * depth}- {nm} origin={[round(v, 2) for v in n.get('origin', [0, 0, 0])]} "
                       f"rot={[round(v, 1) for v in n.get('rotation', [0, 0, 0])]}")
            walk(n.get('children') or [], depth + 1, out)


def main():
    path = sys.argv[1]
    out_path = None
    if '--out' in sys.argv:
        out_path = sys.argv[sys.argv.index('--out') + 1]
    if out_path:
        import io
        buf = io.StringIO()
        real = sys.stdout
        sys.stdout = buf
        try:
            _main(path)
        finally:
            sys.stdout = real
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(buf.getvalue())
        print(out_path, len(buf.getvalue()), 'chars')
        return
    _main(path)


def _main(path):
    d = load(path)
    ELEMS.clear()
    for e in d.get('elements') or []:
        if e.get('uuid'):
            ELEMS[e['uuid']] = e
    GROUPS.clear()
    for g in d.get('groups') or []:
        if g.get('uuid'):
            GROUPS[g['uuid']] = g
    print(f"# {path}")
    print(f"name={d.get('name')} format={d.get('meta', {}).get('format') or d.get('format')} "
          f"res={d.get('resolution', {}).get('width')}x{d.get('resolution', {}).get('height')}")
    print(f"cubes={len(d.get('elements') or [])} groups={len(d.get('groups') or [])} "
          f"textures={len(d.get('textures') or [])} animations={len(d.get('animations') or [])}")

    flag = sys.argv[2] if len(sys.argv) > 2 else None
    val = sys.argv[3] if len(sys.argv) > 3 else None

    if flag == '--keys':
        print('\n== first group raw keys ==')
        g = (d.get('groups') or [{}])[0]
        print(json.dumps({k: (v if not isinstance(v, list) else f'<list {len(v)}>')
                          for k, v in g.items()}, ensure_ascii=False, indent=1)[:1500])
        print('\n== first animation raw keys ==')
        a = (d.get('animations') or [{}])[0]
        print(json.dumps({k: (v if not isinstance(v, (list, dict)) else f'<{type(v).__name__} {len(v)}>')
                          for k, v in a.items()}, ensure_ascii=False, indent=1)[:1500])
        print('\n== animators raw ==')
        print(json.dumps(list((a.get('animators') or {}).items())[:1] if isinstance(a.get('animators'), dict)
                         else (a.get('animators') or [])[:1], ensure_ascii=False)[:1500])
        return

    if flag == '--anim' and val:
        for a in d.get('animations') or []:
            if val.lower() in (a.get('name') or '').lower():
                print(f"\n== anim {a.get('name')} loop={a.get('loop')} length={a.get('length')} "
                      f"snapping={a.get('snapping')} anim_time_update={a.get('anim_time_update')}")
                anims = a.get('animators') or {}
                for key, an in (anims.items() if isinstance(anims, dict) else []):
                    kfs = an.get('keyframes') or []
                    bych = {}
                    for k in kfs:
                        bych.setdefault(k.get('channel'), []).append(k)
                    for ch, arr in bych.items():
                        times = sorted(k.get('time') for k in arr)
                        print(f"   {an.get('name')}.{ch}: n={len(arr)} t={times}")
                        if '--full' in sys.argv:
                            for k in sorted(arr, key=lambda x: x.get('time', 0)):
                                print(f"      t={k.get('time')} dp={k.get('data_points')} "
                                      f"interp={k.get('interpolation')}")
        return

    if flag == '--cubes' and val:
        for e in d.get('elements') or []:
            if val.lower() in (e.get('name') or '').lower():
                print(json.dumps(e, ensure_ascii=False, indent=1)[:1200])
        return

    print("\n== outline ==")
    out = []
    walk(d.get('outliner') or [], 0, out)
    print('\n'.join(out))

    print("\n== animations ==")
    for a in d.get('animations') or []:
        anims = a.get('animators') or {}
        pairs = list(anims.items()) if isinstance(anims, dict) else []
        bones = []
        nkf = 0
        for key, an in pairs:
            bych = {}
            for k in (an.get('keyframes') or []):
                bych.setdefault(k.get('channel'), []).append(k)
            nkf += len(an.get('keyframes') or [])
            bones.append(f"{an.get('name') or key}[{','.join(f'{c}:{len(v)}' for c, v in bych.items())}]")
        print(f"- {a.get('name')}  loop={a.get('loop')} length={a.get('length')} kf={nkf}")
        print(f"    {', '.join(bones)}")

    print("\n== textures ==")
    for t in d.get('textures') or []:
        print(f"- {t.get('name')} {t.get('width')}x{t.get('height')} uv_mode={t.get('uv_mode')} "
              f"src_len={len(str(t.get('source') or ''))}")


if __name__ == '__main__':
    main()
