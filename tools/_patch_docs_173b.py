# -*- coding: utf-8 -*-
"""Wiki 二次更新：版本台账补真摘要（上次抽空成了「详见 readme」）+ 清掉过期的 _deploy_140/1.1.40/脚本数。"""
import re
import shutil
import subprocess
from pathlib import Path

NL = chr(10)
ROOT = Path('F:/mcmod')
WIKI = ROOT / 'docs/wiki'
CLONE = Path('C:/Users/Administrator/AppData/Local/Temp/az_wiki')

fails = []


def sub(p: Path, old: str, new: str, label: str, count: int = 1) -> str:
    s = p.read_text(encoding='utf-8')
    if old not in s:
        fails.append('%s ｜ 锚点没找到：%s' % (label, old[:60].replace(NL, ' ')))
        return s
    s = s.replace(old, new, count)
    p.write_text(s, encoding='utf-8')
    print('  [OK] ' + label)
    return s


# ---------------------------------------------------------------- ① readme → 台账行（取段首行，不再只看 bullet）
readme = (ROOT / 'readme.md').read_text(encoding='utf-8')
rows = []
for m in re.finditer(r'^### (1\.1\.(\d+))[^\n]*\n(.*?)(?=^### |\Z)', readme, re.M | re.S):
    ver, num, body = m.group(1), int(m.group(2)), m.group(3)
    if num < 41:
        continue
    first = ''
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('|') or line.startswith('---'):
            continue
        first = line
        break
    b = re.match(r'\*\*(.+?)\*\*', first)
    if b:
        first = b.group(1)
    first = re.sub(r'`([^`]*)`', r'\1', first)
    first = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', first)
    first = first.lstrip('-*# ').strip()
    if len(first) > 78:
        first = first[:76] + '…'
    rows.append((ver, first or '（见 readme）'))
rows.sort(key=lambda r: [int(x) for x in r[0].split('.')])
print('readme 抽出 %d 行：%s → %s' % (len(rows), rows[0][1][:30], rows[-1][1][:30]))

# ---------------------------------------------------------------- ② 07 重构台账
p = WIKI / '07-出货与版本管理.md'
s = p.read_text(encoding='utf-8')
marker = '## 版本台账（1.1.41'
idx = s.find(marker)
assert idx >= 0, '07 台账标记没找到'
block = ['']
block.append(marker + ' → 1.1.73）')
block.append('')
block.append('> 以 `readme.md` 的更新日志为准；每一版都有自己的 `tools/_deploy_<ver>.py` 门禁。')
block.append('')
block.append('| 版本 | 主要内容 |')
block.append('|---|---|')
for ver, txt in rows:
    block.append('| %s | %s |' % (ver, txt))
block.append('')
block.append('> **1.1.66 → 1.1.73 全是猫耳娘线**：v4 模型（126 块 / 31 骨 / 128² 皮肤）→ 配方表（1433 条）→')
block.append('> 工具即指令 → 界面与背包同布局 → 全无敌不死 + 弓弩完整蓄力 → 拾取 / 自制 / 按工种换装（含盔甲）/')
block.append('> 无耐久 / 砸矿必掉 → 订做指定物品 / 3×3 摆放 / 盔甲渲染层（`CatGirlArmorLayer`，GeckoLib 的')
block.append('> `GeoArmorRenderer` 只服务 `GeoArmorItem`，对原版甲无效） / 内部熔炉 / 月亮三项（tint 对齐 CD + 血月主动刷怪）。')
block.append('')
p.write_text(s[:idx] + NL.join(block) + NL, encoding='utf-8')
print('  [OK] 07：台账 %d 行（真摘要）' % len(rows))

# ---------------------------------------------------------------- ③ 清理过期引用
sub(WIKI / '07-出货与版本管理.md',
    '一版一个（已有 `_deploy_124.py` … `_deploy_140.py`）',
    '一版一个（已有 `_deploy_124.py` … `_deploy_173.py`）', '07 脚本区间')
sub(WIKI / '07-出货与版本管理.md',
    'python tools/_deploy_140.py                       # 自升版号 → 构建 → 对账 → 探锁部署',
    'python tools/_deploy_173.py                       # 自升版号 → 构建 → 对账 → 探锁部署',
    '07 出货命令')
sub(WIKI / '05-武器制作流程.md',
    'python tools/_deploy_140.py        # 自升版号 + 构建 + 三向对账 + 探锁部署',
    'python tools/_deploy_173.py        # 自升版号 + 构建 + 三向对账 + 探锁部署',
    '05 出货命令')

n_deploy = len(list((ROOT / 'tools').glob('_deploy_*.py')))
p = WIKI / '06-工具脚本手册.md'
s = p.read_text(encoding='utf-8')
s2 = re.sub(r'（共 \d+ 个，一版一个）', '（共 %d 个，一版一个）' % n_deploy, s)
if s2 != s:
    p.write_text(s2, encoding='utf-8')
    print('  [OK] 06 出货脚本数 → %d' % n_deploy)
else:
    fails.append('06 出货脚本数没改到')

sub(WIKI / '09-文档状态与待清理.md',
    '`mod_version = "1.1.5"`（当前 1.1.40）',
    '`mod_version = "1.1.5"`（当前 1.1.73）', '09 mod.toml 行')

p = WIKI / '09-文档状态与待清理.md'
s = p.read_text(encoding='utf-8')
old_row = '| `readme.md` 头表写"当前版本 `1.1.40`"，但更新日志里有一条 `### 1.1.41 — 2026-09-28` | 要么 1.1.41 已回退/未发，要么头表该改。`gradle.properties` 的 `mod_version` 是 **1.1.40**，以它为准 |'
new_row = '| ~~`readme.md` 头表写"当前版本 `1.1.40`"，但日志里有 `### 1.1.41`~~ | **已解决**：头表现在每版手升（当前 `1.1.73`），`gradle.properties` 的 `mod_version` 是唯一来源 |'
if old_row in s:
    p.write_text(s.replace(old_row, new_row, 1), encoding='utf-8')
    print('  [OK] 09 头表版本行 → 已解决')
else:
    fails.append('09 头表版本行锚点没找到（可能行内引号是中文引号）')

sub(WIKI / '03-构建运行与排障.md',
    'cp build/libs/apocalypse_zombies-1.1.40.jar \\',
    'cp build/libs/apocalypse_zombies-1.1.73.jar \\', '03 部署示例 jar 名')

# ---------------------------------------------------------------- ④ Home：当前版本 / 出货脚本 / 脚本数
p = CLONE / 'Home.md'
if not p.is_file():
    fails.append('找不到 Wiki 克隆 Home.md：%s' % p)
else:
    s = p.read_text(encoding='utf-8')
    n_check = len(list((ROOT / 'tools').glob('check_*.py')))
    reps = [
        ('python tools/_deploy_140.py            # 当前最新；每版一个脚本，见「07 出货与版本管理」',
         'python tools/_deploy_173.py            # 当前最新；每版一个脚本，见「07 出货与版本管理」'),
        ('（13 个脚本，判据是退出码）', '（%d 个脚本，判据是退出码）' % n_check),
        ('更新日志（514 行）', '更新日志（每版必写）'),
    ]
    for old, new in reps:
        if old in s:
            s = s.replace(old, new, 1)
            print('  [OK] Home：%s' % old[:34])
        else:
            fails.append('Home 锚点没找到：%s' % old[:40])
    p.write_text(s, encoding='utf-8')

print(NL + ('全部命中' if not fails else '失败 %d 条：' % len(fails)))
for f in fails:
    print('  [FAIL] ' + f)
Path('F:/mcmod/build/wiki_note.txt').write_text(NL.join(fails), encoding='utf-8')
