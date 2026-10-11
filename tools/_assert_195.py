print('=== 11/15 1.1.95：枪械物品栏显示放大 ===')
# 枪走 builtin/entity（GeckoLib 画 3D 模型），物品栏里多大**只由 display.gui.scale 决定** ——
# 贴图内容本来就是占满画布的，所以这是一次纯显示参数的改动。
# 这里把八把枪的新值钉住，并**验算**「枪长 × scale ≈ 14.5 像素（格子 16）」这条口径：
# 谁改了新值，就得同时解释为什么它不再占满格子。
import json as _json

_MODELS = 'F:/mcmod/src/main/resources/assets/apocalypse_zombies/models/item'
_GEO = 'F:/mcmod/src/main/resources/assets/apocalypse_zombies/geo'

# 目标：枪长占格子宽度的约 90%（14.5 / 16 像素）
WANT = {'awm': 0.60, 'mosin_nagant': 0.63, 'rsc_1917': 0.69, 's686': 0.74,
        'm1_garand': 0.82, 'uzi': 0.92, 'colt_1878': 0.97, 'crossbow': 1.20}


def _geo_length(name):
    """所有 cube 的联合包围盒最长边（模型单位；÷16 = 格）。"""
    g = _json.load(open('%s/%s.geo.json' % (_GEO, name), encoding='utf-8'))
    lo = [1e9] * 3
    hi = [-1e9] * 3
    for geo in g['minecraft:geometry']:
        for b in geo.get('bones', []):
            for c in b.get('cubes', []):
                o, s = c['origin'], c.get('size', [0, 0, 0])
                for i in range(3):
                    lo[i] = min(lo[i], o[i])
                    hi[i] = max(hi[i], o[i] + s[i])
    return max(hi[i] - lo[i] for i in range(3))


check(len(WANT) == 8, '覆盖八把枪（七把枪 + 十字弩）')
for _n in sorted(WANT):
    _g = _json.load(open('%s/%s.json' % (_MODELS, _n), encoding='utf-8'))
    check(_g['parent'] == 'builtin/entity', '%s 仍是 builtin/entity（GeckoLib 渲染）' % _n)
    _s = _g['display']['gui']['scale'][0]
    check(abs(_s - WANT[_n]) < 1e-6, '%s 的 gui.scale = %g' % (_n, WANT[_n]), '实得 %g' % _s)
    # 反向断言：只有 gui 被改过。其余槽位是「手里持枪」的构图，动的会改坏手感。
    for _slot in ('thirdperson_righthand', 'thirdperson_lefthand', 'firstperson_righthand',
                  'firstperson_lefthand', 'ground', 'fixed', 'head'):
        _o = _g['display'][_slot]['scale'][0]
        check(_o < 0.95, '%s 的 %s 保持原有小值（没被这次改动碰）' % (_n, _slot), '实得 %g' % _o)
    _L = _geo_length(_n)
    _px = _L * _s                       # 单位 × scale = 格 × 16 = 像素
    check(13.5 <= _px <= 15.5,
          '%s 显示长度 %.1f 像素（格子 16，目标 ~14.5）' % (_n, _px), '实得 %.1f' % _px)

_rd = open('F:/mcmod/readme.md', encoding='utf-8').read()
check('### 1.1.95 —' in _rd, 'readme 有 1.1.95 条目')
check('| **当前版本** | `1.1.95` |' in _rd, 'readme 头表 == 1.1.95')
check('## 1.1.95 ——' in open('F:/mcmod/docs/wiki/07-出货与版本管理.md', encoding='utf-8').read(),
      'wiki 07 有 1.1.95 小节')
check('gui.scale' in open('F:/mcmod/docs/wiki/02-代码与资源地图.md', encoding='utf-8').read(),
      'wiki 02 记了「物品栏大小由 gui.scale 决定」')
