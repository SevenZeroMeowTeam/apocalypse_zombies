# -*- coding: utf-8 -*-
"""1.1.83：把文档（docs/wiki 02/06/07）改到「挖掘数字」这一版。"""
import io

def load(p):
    return io.open(p, encoding='utf-8', newline='').read()

def save(p, s):
    io.open(p, 'w', encoding='utf-8', newline='').write(s)

def rep(p, s, old, new, n=1, tag=''):
    c = s.count(old)
    assert c == n, (p, tag, c, old[:80])
    return s.replace(old, new, n)

# ================= 02-代码与资源地图.md =================
p = 'F:/mcmod/docs/wiki/02-代码与资源地图.md'
s = load(p)

s = rep(p, s,
    '**一份判定两处用**，所以「画出来的框 = 真的会砸的」）',
    '**一份判定两处用**，所以「画出来的框 = 真的会砸的」。'
    '**1.1.83**：`preview` 再收一个 `boolean sneaking` —— 「潜行只挖一格」也挪进这个出口，'
    '客户端才可能跟着算对（1.1.82 那会儿蹲着还照画一整簇，那是个谎））', tag='event 表行')

s = rep(p, s,
    '`ClientEvents`（745 行；**1.1.82** 起在 `onRenderLevelStage` 开头调一句 `VeinMineHighlighter.render(event)`）',
    '`ClientEvents`（**1.1.82** 起在 `onRenderLevelStage` 开头调一句 `VeinMineHighlighter.render(event)`；'
    '**1.1.83** 起在 `onRenderWeaponGui` 里再调一句 `VeinMineHighlighter.renderCount(graphics, minecraft)` 画数字）',
    tag='client 表行')

s = rep(p, s,
    '`VeinMineHighlighter`（**1.1.82 玩家挖掘高亮**）',
    '`VeinMineHighlighter`（**1.1.82 玩家挖掘高亮** + **1.1.83 准星下方的「会连挖几格」**；'
    '两者共用同一份缓存，数字不会跟框打架）', tag='renderer 表行')

s = rep(p, s,
    '`highlight`(true 瞄准的方块会连带的那些在**客户端描一圈青边** —— 画的一定是真会砸的；纯观感，关掉照样能一键挖掘)',
    '`highlight`(true 瞄准的方块会连带的那些在**客户端描一圈青边** —— 画的一定是真会砸的；纯观感，关掉照样能一键挖掘)\n'
    '- 1.1.83（新增 1 项 → 界面共 **169 项**，`[player_mine]` 段）：'
    '`count`(true **准星下方报「会连挖 N 格」**，含你瞄的那一格；只报 2 格以上，'
    '撞 `max_blocks` 时写成「已到上限」；与 `highlight` 各管各的，可以只要框、只要数字，或者都要)',
    tag='配置清单')

save(p, s)
print('02 OK')

# ================= 06-工具脚本手册.md =================
p = 'F:/mcmod/docs/wiki/06-工具脚本手册.md'
s = load(p)

s = rep(p, s,
    '| `tools/_deploy_<ver>.py` | 出货门禁（`_deploy_182.py` 是本轮最新；含 1.1.81「玩家一键挖掘」不回归 + 1.1.82「挖掘高亮：客户端渲染 / 复用 preview / 11 项配置 / 168 项总数」） |',
    '| `tools/_deploy_<ver>.py` | 出货门禁（`_deploy_183.py` 是本轮最新；含 1.1.81「玩家一键挖掘」不回归 + 1.1.82「挖掘高亮」+ 1.1.83「挖掘数字：HUD 报数 / 与描边同一份缓存 / 潜行判定收进 preview / 12 项配置 / 169 项总数」，实跑 **382 项全绿**） |',
    tag='deploy 行')

s = rep(p, s,
    '| `tools/_mk_deploy_180.py` |',
    '| `tools/_mk_deploy_183.py` | 从 `_deploy_182.py` 派生 183 门禁（换版号 + 换头注释 + **插入 1.1.83 那一整段** + 把历史段里四处「配置项总数 168 / 界面共 168 项」往前挪到 169）。'
    '**这一段不再写进生成器**：断言正文单独放 `tools/_assert_183.py`，生成器读进来再拼 —— 免得在生成器的字符串里再套一层转义（`_mk_deploy_182.py` 那两行 zip 续行符就是这么被坑的） |\n'
    '| `tools/_assert_183.py` | 1.1.83 的断言正文（**片段**，本身不能直接跑：`check` / `_p` / `SRC` 都由 `_deploy_183.py` 提供）。'
    '写新一版时照抄这个套路：正文独立成文件、生成器只拼不转义 |',
    tag='生成器行')

save(p, s)
print('06 OK')

# ================= 07-出货与版本管理.md =================
p = 'F:/mcmod/docs/wiki/07-出货与版本管理.md'
s = load(p)

s = rep(p, s,
    '| 1.1.82 | **玩家挖掘高亮**：',
    '| 1.1.83 | **挖掘数字**：瞄着矿脉时，准星下方报「会连挖 N 格」（含你瞄的那一格）；份数与描边取自同一份缓存；只报 2 格以上；撞 `max_blocks` 补「已到上限」；`[player_mine] count` 默认 true。**顺手补谎**：「潜行只挖一格」收进 `PlayerVeinMine.preview`，蹲下时框和数字一起消失 |\n'
    '| 1.1.82 | **玩家挖掘高亮**：',
    tag='版本表')

sec = (
    '## 1.1.83 · 挖掘数字（准星下方报数）\n'
    '\n'
    '- **数字与框同源**：`renderCount` 用的是 `render()` 同一份缓存（同一个 `PlayerVeinMine.preview`\n'
    '  结果），所以不会出现「框画了 12 个、数字说 11」。\n'
    '- **框比数字少 1 个不是 bug**：瞄准的那一格由原版画黑框（我们故意不叠），但数字是这一下左键的\n'
    '  **总账**，含它自己。两个都对，wiki/readme 里都写明了。\n'
    '- **只报 2 格以上**：只砸一格时原版本来就是这样，没必要常驻一行字。\n'
    '- **撞上限要说**：`count >= min(max_blocks, 64)` 时文案换成「会连挖 64 格（已到上限）」，\n'
    '  否则你会以为眼前那一簇就这么大。\n'
    '- **两个开关各管各的**：`highlight` / `count` 互不影响 —— 只要框、只要数字、都要、都不要都行。\n'
    '- **顺手补了个谎**：1.1.82 的高亮在你**潜行**时还会照画一整簇，可实际上潜行只砸一格。\n'
    '  根因是「潜行不连带」当时写在 `onBreak` 里、`preview` 不知道；现在这条判定收进 `preview`\n'
    '  （服务端与客户端读同一份），潜行状态也进了客户端缓存键 → 蹲下立刻改画面。\n'
    '- **文案走 lang**：`hud.apocalypse_zombies.vein_count` / `..._vein_count_capped`，中英各一份。\n'
    '\n'
    '**怎么自测**：拿铁镐瞄铁矿脉（不按左键）→ 准星下方出「会连挖 N 格」，整簇同时冒青边；\n'
    '**蹲下** → 数字和框一起消失（只砸一格）；把 `max_blocks` 改小（比如 8）再瞄一簇大的 →\n'
    '文案变「已到上限」；`count=false` → 只剩框；`highlight=false, count=true` → 只剩数字。\n'
    '\n'
)
anchor = '## 1.1.82 · 玩家挖掘高亮（客户端描边）'
i = s.index(anchor)
s = s[:i] + sec + s[i:]
save(p, s)
print('07 OK')
