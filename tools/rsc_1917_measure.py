#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 本脚本 import numpy/PIL（Windows 的 py 会按 shebang 选解释器）→ 用 py -3.13 跑。
"""RSC M1917 参考图量取 v2 —— 逐列给出**木质/金属分段**，供生成器直接放样。

输入：art/rsc_1917/ref_rsc1917_side.png（侧视照片，白底；枪口在右）
输出：art/rsc_1917/profile2.json
    {mm_per_px, y_axis, total_mm, cols:[{z_mm, top, bot, runs:[{mat:'W'|'M', top, bot}]}]}
       top/bot/runs 均为**相对膛线轴**的 mm（上正下负）

分类：先按“够暗”取剪影（排除白底与投影），再按 HSV 分木/金：
    木 = 暖色（R>G>B 且饱和度够）；金 = 冷/中性暗色（低饱和）。

用法：py -3.13 tools/rsc_1917_measure.py [--show 输出验证图]
"""

import argparse
import json

import numpy as np
from PIL import Image

REF = 'art/rsc_1917/ref_rsc1917_side.png'
OUT = 'art/rsc_1917/profile2.json'
OLD = 'art/rsc_1917/profile.json'


def classify(img):
    """返回 0=背景 1=金属 2=木质（用 alpha 定剪影，别用亮度 —— 透明背景转 RGB 会变黑）"""
    a = np.array(img.convert('RGBA')).astype(np.float32)
    alpha = a[..., 3]
    rgb = a[..., :3] / 255.0
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    v = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    sat = np.where(v > 1e-6, (v - mn) / np.maximum(v, 1e-6), 0)
    sil = alpha > 128
    warm = (r > g * 1.04) & (g >= b * 1.02) & (sat > 0.16)   # 木：暖棕
    out = np.zeros(v.shape, np.uint8)
    out[sil] = 1
    out[sil & warm] = 2
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--show', default='art/rsc_1917/_seg_check.png')
    a = ap.parse_args()
    ref = json.load(open(OLD, encoding='utf-8'))
    mm_px = ref['mm_per_px']
    img = Image.open(REF)
    cls = classify(img)
    img = img.convert('RGB')
    H, W = cls.shape

    ink = cls > 0
    cols_any = np.where(ink.any(axis=0))[0]
    x_muz, x_butt = int(cols_any.max()), int(cols_any.min())
    total_mm = (x_muz - x_butt) * mm_px
    # 膛线轴：用“裸露枪管”段（枪口附近）的上下缘中点推定
    # 只取“纯净枪管段”估计轴：z 70~110mm 之间（避开准星 z15~45 与拖曳钩 z>110）
    seg = np.arange(x_muz - int(110 / mm_px), x_muz - int(70 / mm_px))
    tops, bots = [], []
    for x in seg:
        ys = np.where(ink[:, x])[0]
        if len(ys) > 3:
            tops.append(ys.min())
            bots.append(ys.max())
    y_axis = (np.median(tops) + np.median(bots)) / 2.0

    cols = []
    for x in range(x_butt, x_muz + 1):
        ys = np.where(ink[:, x])[0]
        if len(ys) < 2:
            continue
        z_mm = (x_muz - x) * mm_px
        runs = []
        y = ys.min()
        while y <= ys.max():
            c = cls[y, x]
            y0 = y
            while y + 1 <= ys.max() and cls[y + 1, x] == c:
                y += 1
            if c > 0 and (y - y0 + 1) >= 2:          # 丢掉 1px 噪声
                runs.append({
                    'mat': 'W' if c == 2 else 'M',
                    'top': round((y_axis - y0) * mm_px, 2),
                    'bot': round((y_axis - y) * mm_px, 2),
                })
            y += 1
        # 合并同材质相邻段（中间夹着的杂色小段并过去）
        merged = []
        for r in runs:
            if merged and merged[-1]['mat'] == r['mat']:
                merged[-1]['bot'] = r['bot']
            else:
                merged.append(dict(r))
        # 单列里只保留最长的木段与最长的金段各一段（消除高光/阴影造成的碎片）
        best = {}
        for r in merged:
            k = r['mat']
            if k not in best or (r['top'] - r['bot']) > (best[k]['top'] - best[k]['bot']):
                best[k] = r
        cols.append({
            'z_mm': round(z_mm, 2),
            'top': round((y_axis - ys.min()) * mm_px, 2),
            'bot': round((y_axis - ys.max()) * mm_px, 2),
            'runs': [best[k] for k in ('W', 'M') if k in best],
        })

    doc = {
        'src': REF, 'mm_per_px': mm_px, 'y_axis_px': round(float(y_axis), 2),
        'total_mm': round(total_mm, 1), 'x_muzzle_px': x_muz, 'x_butt_px': x_butt,
        'cols': cols,
    }
    json.dump(doc, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
    print('%s：%d 列，全长 %.0f mm，轴 %.1f px，枪口 x=%d 托底 x=%d'
          % (OUT, len(cols), total_mm, y_axis, x_muz, x_butt))

    # 验证图：木=橙 金=蓝 底=白
    vis = np.full((H, W, 3), 255, np.uint8)
    vis[cls == 1] = (60, 90, 200)
    vis[cls == 2] = (210, 130, 40)
    vis[int(y_axis), :] = (0, 200, 0)
    Image.fromarray(vis).save(a.show)
    print('验证图 %s（木=橙 金=蓝 绿线=膛线轴）' % a.show)


if __name__ == '__main__':
    main()
