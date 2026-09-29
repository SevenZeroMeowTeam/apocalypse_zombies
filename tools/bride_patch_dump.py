"""按图集清单统计每块面的「细节密度」，给出最平的部位排序。

用法:
    python tools/bride_patch_dump.py                # 平整度排行榜（面积 x 平坦度）
    python tools/bride_patch_dump.py skirt n        # 打印 skirt 各面里 face=n 的像素网格
    python tools/bride_patch_dump.py skirt n 8      # 只打行 0..7

判据说明:
    邻域差 = 相邻像素的 RGB 通道差绝对值均值。它衡量的是「这块面上有没有纹理信息」:
        <= 2   → 几乎纯色（等于没画）
        3..7   → 有渐变/轻微纹理
        >= 8   → 有结构（褶皱、蕾丝、血迹等）
    面积用「像素数」而不是「u 数」: 图集里每 u 的像素数（tpu）逐块不同，
    换算过的面积才是玩家真正看到的面积。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from bride_face_crop import read_png  # noqa: E402

ART = os.path.join(ROOT, 'art', 'bride')
MANIFEST = os.path.join(ART, 'bride_atlas.json')
TEX = os.path.join(ROOT, 'src/main/resources/assets/apocalypse_zombies/textures/entity/bride/bride_zombie.png')


def patch_stats(tex, rect):
    """返回 (不透明像素数, 不同颜色数, 邻域差均值, 覆盖率)。

    透明像素（alpha=0）不计入: 头纱这类部件大部分是镂空蕾丝，
    把透明区域算进"平坦度"会把镂空误判成"没画"。
    """
    x0, y0, w, h = rect
    px = tex[2]
    tw = tex[0]
    total = 0
    n = 0
    opaque = 0
    colors = set()
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            i = (y * tw + x) * 4
            if px[i + 3] == 0:
                continue
            opaque += 1
            c = (px[i], px[i + 1], px[i + 2], px[i + 3])
            colors.add(c)
            if x + 1 < x0 + w:
                j = i + 4
                if px[j + 3] > 0:
                    total += (abs(px[i] - px[j]) + abs(px[i + 1] - px[j + 1]) + abs(px[i + 2] - px[j + 2])) / 3.0
                    n += 1
            if y + 1 < y0 + h:
                j = i + tw * 4
                if px[j + 3] > 0:
                    total += (abs(px[i] - px[j]) + abs(px[i + 1] - px[j + 1]) + abs(px[i + 2] - px[j + 2])) / 3.0
                    n += 1
    return opaque, len(colors), (total / n if n else 0.0), (opaque / float(w * h))


def dump_grid(tex, rect, row_from=0, row_to=None):
    x0, y0, w, h = rect
    px = tex[2]
    tw = tex[0]
    row_to = h if row_to is None else min(row_to, h)
    print('    ' + ''.join('%3d' % x for x in range(w)))
    for y in range(row_from, row_to):
        cells = []
        for x in range(x0, x0 + w):
            i = ((y0 + y) * tw + x) * 4
            if px[i + 3] == 0:
                cells.append('  .')
            else:
                cells.append('%02x' % (px[i] >> 4 << 4 | px[i + 1] >> 4))
        print('行%2d ' % y + ' '.join(cells))


def main():
    args = sys.argv[1:]
    tex = read_png(TEX)
    m = json.load(open(MANIFEST, encoding='utf-8'))
    faces = m['faces']

    if args:
        want = args[0].lower()
        face_want = args[1].lower() if len(args) > 1 else None
        hits = [f for f in faces if want in f['part'].lower() or want in f['bone'].lower()]
        if face_want:
            hits = [f for f in hits if f['face'] == face_want]
        for f in hits:
            area, colors, flat, cov = patch_stats(tex, f['rect'])
            print('%s / %s / face=%s  rect=%s  不透明=%dpx 覆盖率=%.0f%%  色数=%d  邻域差=%.2f'
                  % (f['bone'], f['part'], f['face'], f['rect'], area, cov * 100, colors, flat))
            dump_grid(tex, f['rect'], int(args[2]) if len(args) > 2 else 0)
        if not hits:
            print('没有匹配', args)
        return 0

    rows = []
    for f in faces:
        area, colors, flat, cov = patch_stats(tex, f['rect'])
        rows.append((flat, area, colors, cov, f))
    # 只关心「看得见的大面」: 不透明区 >= 24px，按 平坦度 从低到高
    big = [r for r in rows if r[1] >= 24]
    big.sort(key=lambda r: (r[0], -r[1]))
    print('最平的大面（不透明区>=24px，按邻域差升序）—— 这些是最值得补细节的地方:')
    print('  邻域差  不透明  色数  bone / part / face')
    for flat, area, colors, cov, f in big[:28]:
        print('  %6.2f  %5d  %4d  %s / %s / %s' % (flat, area, colors, f['bone'], f['part'], f['face']))
    print()
    print('最细的大面（前 8）:')
    for flat, area, colors, cov, f in sorted(big, key=lambda r: -r[0])[:8]:
        print('  %6.2f  %5d  %4d  %s / %s / %s' % (flat, area, colors, f['bone'], f['part'], f['face']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
