print('=== 12/17 1.1.97：全部 readme 过一次账 ===')
# 这一版只改文档。所以判据不是"改了没有"，而是**文档与现状是否一致**：
# 把每条核过的结论钉成断言 —— 谁再把过期的说法写回去，或者把"仍未做"顺手改成"已做"，就红。
import os as _os

_rd = open('F:/mcmod/readme.md', encoding='utf-8').read()
_w7 = open('F:/mcmod/docs/wiki/07-出货与版本管理.md', encoding='utf-8').read()
_wr = open('F:/mcmod/docs/wiki/README.md', encoding='utf-8').read()
_awm = open('F:/mcmod/art/awm/README.md', encoding='utf-8').read()
_m1 = open('F:/mcmod/art/m1garand/README.md', encoding='utf-8').read()
_xb = open('F:/mcmod/art/crossbow/DELIVERY.md', encoding='utf-8').read()
_uz = open('F:/mcmod/art/uzi/DELIVERY.md', encoding='utf-8').read()

# ---- ① 四处实证错误都改成了现状 ----
check('已修（1.1.95，2026-10-11 重核更正）' in _xb, 'crossbow 偏差 #9 已标注 1.1.95 修好')
check('未修，待定' not in _xb, 'crossbow 不再有「图标未修，待定」的说法')
check('已决（1.1.95）' in _xb, 'crossbow 待定 #2（是否一起放大）已标注已决')
check('**已做**（本条曾长期停在"未做"' in _uz, 'uzi 的 Java 同步已标注「已做」')
check('Java 同步 | **未做**' not in _uz, 'uzi 不再自称 Java 同步未做')
check('1.1.93 起已全部替换' in _awm, 'awm 的音效署名已改成「已替换」')
check('1.1.93 起已全部替换' in _m1, 'm1garand 的音效署名已改成「已替换」')
check('未修改副本**（md5 与原件逐一相同）' not in _awm, 'awm 不再自称音效是「未修改副本」')
check('已接线**：`M1GarandItem.ANIM_DRAW`' in _m1, '加兰德的 draw 已标注接线')
check('掏枪（尚未接线）' not in _m1, '加兰德 clip 表里不再写 draw「尚未接线」')

# ---- ② wiki 索引的数字对上了 ----
check('_deploy_196.py' in _wr, 'wiki 索引指向 _deploy_196.py')
check('_deploy_140.py' not in _wr, 'wiki 索引不再指向 _deploy_140.py')
check('1975 行' in _wr, 'wiki 索引写的是 readme 的真实行数（1975）')
check('238 个 `.py`' in _wr, 'wiki 索引写的是 tools 当前脚本数（238）')
check('共 18 个' in _wr, 'wiki 索引写的是 check_*.py 的真实数量（18）')
check('不参与构建' in _wr, 'wiki 索引说清了 mod.toml 不参与构建')

# ---- ③ 数字是量出来的，别让文档又漂走 ----
_lines = len(open('F:/mcmod/readme.md', encoding='utf-8').read().split('\n'))
check(abs(_lines - 1975) <= 40, 'readme 行数仍与文档里写的 1975 同一量级',
      '实得 %d 行' % _lines)
# 注意：tools/*.py 每出一版会 +3（_deploy_<ver> / _assert_<ver> / _mk_deploy_<ver>），
# 所以这里给容差 —— 只在"数量级出了大事"（比如误删一批脚本）时才红。写成精确相等是自找的红：
# 生成门禁这个动作本身就会把这个数顶上去。
_py = [f for f in _os.listdir('F:/mcmod/tools') if f.endswith('.py')]
check(abs(len(_py) - 238) <= 15, 'tools/*.py 数量在 238 附近（每版 +3）', '实得 %d' % len(_py))
_chk = [f for f in _py if f.startswith('check_')]
check(len(_chk) == 18, 'tools/check_*.py 仍是 18 个', '实得 %d' % len(_chk))

# ---- ④ 核过「仍未做」的那些要留住，别被顺手改成已做 ----
check('仍未做' in _awm and 'WeaponMount' in _awm, 'AWM 待办重核：WeaponMount 确实仍未做')
check('仍未接线' in _awm, 'AWM 待办重核：五段 clip 确实仍未接线')
check('已接线' in _m1, '加兰德待办重核：draw 已接线')
check('ANIM_DRAW' in _m1 and 'ANIM_INSPECT' not in _m1.split('## 待办')[-1],
      '加兰德只接了 draw（inspect 仍未做）')

# ---- ⑤ 版本与日志 ----
check('### 1.1.97 —' in _rd, 'readme 有 1.1.97 条目')
check('| **当前版本** | `1.1.97` |' in _rd, 'readme 头表 == 1.1.97')
check('## 1.1.97 ——' in _w7, 'wiki 07 有 1.1.97 小节')
