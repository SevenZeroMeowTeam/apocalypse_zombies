# -*- coding: utf-8 -*-
"""1.1.83：readme + gradle.properties 升版（挖掘数字显示）。"""
import io

def load(p):
    s = io.open(p, encoding='utf-8', newline='').read()
    return s, ('\r\n' if '\r\n' in s else '\n')

def save(p, s):
    io.open(p, 'w', encoding='utf-8', newline='').write(s)

def rep(s, old, new, n=1, tag=''):
    assert s.count(old) == n, (tag, s.count(old), old[:70])
    return s.replace(old, new, n)

# ---- readme ----
p = 'F:/mcmod/readme.md'
s, NL = load(p)

s = rep(s, '| **当前版本** | `1.1.82` |', '| **当前版本** | `1.1.83` |', 1, '版本')

old_row = '`highlight`（瞄准时把会连带的方块描边画出来，默认开） |'
new_row = ('`highlight`（瞄准时把会连带的方块描边画出来，默认开）、'
           '`count`（瞄准时在准星下方显示「会连挖几格」，默认开） |')
s = rep(s, old_row, new_row, 1, 'player_mine 行')

s = rep(s, '列出**全部 168 项配置**', '列出**全部 169 项配置**', 1, '配置计数')

log = NL.join([
    '### 1.1.83 — 2026-10-10',
    '',
    '**瞄准的时候准星下面会报数了：这一下左键会连挖几格 —— 跟画出来的框是同一份数字。**',
    '',
    '- 数字画在准星正下方（`client/renderer/VeinMineHighlighter.renderCount`），含你瞄的那一格 ——',
    '  那是这一下左键的总账；描边只画「连带下来的那些」，所以框会比数字少 1 个，两个都对。',
    '- **只报 2 格以上**：只砸一格的时候原版本来就是这样，没必要在准星底下常驻一行字。',
    '- **到上限会说明**：撞到 `max_blocks`（默认 64）时写成「会连挖 64 格（已到上限）」，',
    '  免得你以为眼前那一簇就这么大。',
    '- `player_mine.count = false` 可以只留框不要数字；两个开关各管各的（只要数字、不要框也行）。',
    '- **顺手补了个谎**：1.1.82 的高亮在你**潜行**时还会照画一整簇，可实际上潜行只砸一格。',
    '  现在「潜行不连带」这条判定收进了 `PlayerVeinMine.preview` 这个共用出口（服务端与客户端读的是同一份），',
    '  蹲下时框和数字会一起消失 —— 依旧是那条规矩：画的一定是真会砸的。',
    '',
])

anchor = '### 1.1.82 — 2026-10-10'
i = s.index(anchor)
s = s[:i] + log + s[i:]
save(p, s)
print('readme ->1.1.83 OK')

# ---- gradle.properties ----
p2 = 'F:/mcmod/gradle.properties'
s2, _ = load(p2)
s2 = rep(s2, 'mod_version=1.1.82', 'mod_version=1.1.83', 1, 'gradle 版本')
save(p2, s2)
print('gradle.properties ->1.1.83 OK')
