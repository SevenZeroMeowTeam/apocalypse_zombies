# -*- coding: utf-8 -*-
"""1.1.73 文档线：readme 加 1.1.73 段 + 头表；docs/wiki 三页补 1.1.66→1.1.73 内容；
然后把 docs/wiki 整批同步到 GitHub Wiki 克隆（链接去掉 .md）。"""
import re
import shutil
from pathlib import Path

NL = chr(10)
ROOT = Path('F:/mcmod')
WIKI = ROOT / 'docs/wiki'
CLONE = Path('D:/hermes-agent/cache/scratch') / 'az_wiki'
if not CLONE.is_dir():
    import os
    CLONE = Path(os.environ.get('TMPDIR', 'D:/hermes-agent/cache/scratch')) / 'az_wiki'

DATE = '2026-10-10'
V = '1.1.73'

# ---------------------------------------------------------------- readme
rd = ROOT / 'readme.md'
s = rd.read_text(encoding='utf-8')
NEW_SEC = """### {v} — {d}

**猫耳娘会「接单」了：你说做哪件，她掏自己的料做给你。**

- **订做指定物品**：`/apocalypse catgirl craft <物品id> [数量]`（找 16 格内属于你的那只猫耳娘）。
  材料从**她的库存**扣，手续费按 `craft_fee`（默认 2 枚）从**你的爱心币**里扣，成品直接进你背包。
  她界面里也多了一格「样品槽」：放一件样品 → 右边出成品，样品不收，取走成品就再做一件（想停就把样品拿回去）。
- **3×3 摆放**（这次的重头）：她不再「按材料堆凑」，而是把配方自己的形状铺进一张 3×3 网格再让原版 `matches` 点头 ——
  「3 木板 + 2 木棍」到底是斧还是镐，看形状，不再掷骰子看配方表顺序。
- **盔甲看得见了**（`CatGirlArmorLayer`）：GeckoLib 自带的 `GeoArmorRenderer` 只认自注册的几何盔甲，
  对原版/模组盔甲物品无效，所以这里把原版盔甲网格（`HumanoidModel` 的内/外层）按骨骼包围盒**贴合**到她的
  头 / 身 / 双臂 / 双腿 / 双脚上，走路甩尾会带着甲一起动。开关 `armor_render`（默认开）。
- **内部熔炉**：她的库存里有矿石 + 一份燃料（原版熔炉认什么她就认什么）→ 自动烧成锭（铁矿石→铁锭、生铁→铁块那类
  走原版 `minecraft:smelting`）。开关 `smelt`（默认开）。燃料本身不会被烧掉（不然她会把木头全烧成炭）。
- **月亮三项**：①月相颜色逐条对齐 Crafting Dead（蓝月 `0x55AAFF`、血月 `0xFF5555`、黄月 `0xFFE055`、
  超级血月 `0xCC44FF`…），HUD 的月相字色跟着 tint 走；②**血月会主动刷怪**了：每 `blood_moon_spawn_interval`
  (200 tick) 在每名玩家 20~40 格外放 `blood_moon_spawn_count`(2) 只僵尸，走 `finalizeSpawn` 吃尸潮倍率；
  ③闸门复用已有的 `isBloodMoon()`。

### 1.1.72 — 2026-10-10"""
assert '### 1.1.72 — 2026-10-10' in s, 'readme 1.1.72 段锚点'
s = s.replace('### 1.1.72 — 2026-10-10', NEW_SEC.replace('{v}', V).replace('{d}', DATE), 1)

# 头表：把含 1.1.72 的第一行复制成 1.1.73 行
lines = s.split(NL)
done = False
for i, line in enumerate(lines):
    if done:
        break
    if line.lstrip().startswith('|') and '1.1.72' in line:
        new = line.replace('1.1.72', V, 1)
        new = re.sub(r'猫耳娘[^|]*', '猫耳娘接单：订做指定物品 / 3×3 摆放 / 盔甲看得见 / 内部熔炉 / 月亮三项 ', new, count=1)
        lines.insert(i, new)
        done = True
        print('  readme 头表插入行：', new.strip()[:110])
assert done, 'readme 头表没找到 1.1.72 行'
rd.write_text(NL.join(lines), encoding='utf-8')
print('(1) readme：+ ### 1.1.73 段 + 头表行')

# ---------------------------------------------------------------- 版本台账行（从 readme 抽）
src = rd.read_text(encoding='utf-8')
rows = []
for m in re.finditer(r'^### (1\.1\.(\d+))[^\n]*\n+((?:[-*|>].*\n|[^\n#].*\n)*)', src, re.M):
    ver, num, body = m.group(1), int(m.group(2)), m.group(3)
    if num < 41:
        continue
    first = ''
    for bl in body.splitlines():
        bl = bl.strip()
        if bl.startswith(('- ', '* ')):
            first = bl[2:]
            break
    first = re.sub(r'\*\*', '', first)
    first = re.sub(r'`', '', first)
    first = re.sub(r'\s+', ' ', first).strip()
    if len(first) > 78:
        first = first[:76] + '…'
    rows.append((ver, first or '（详见 readme）'))
rows.sort(key=lambda r: [int(x) for x in r[0].split('.')])
print('   台账行 %d 条：%s → %s' % (len(rows), rows[0][0], rows[-1][0]))

# ---------------------------------------------------------------- 07 版本台账
p = WIKI / '07-出货与版本管理.md'
s = p.read_text(encoding='utf-8')
if '1.1.73' not in s:
    table = [NL, '## 版本台账（1.1.41 → 1.1.73）', NL,
             '> 以 `readme.md` 的更新日志为准；每一版都有自己的 `tools/_deploy_<ver>.py` 门禁。', NL,
             '| 版本 | 主要内容 |', '|---|---|']
    for ver, txt in rows:
        table.append('| %s | %s |' % (ver, txt))
    table.append('')
    table.append('> **1.1.66 → 1.1.73 全是猫耳娘线**：v4 模型（126 块 / 31 骨 / 128² 皮肤）→ 配方表（1433 条）→')
    table.append('> 工具即指令 → 界面与背包同布局 → 全无敌不死 + 弓弩完整蓄力 → 拾取 / 自制 / 按工种换装（含盔甲）/')
    table.append('> 无耐久 / 砸矿必掉 → 订做指定物品 / 3×3 摆放 / 盔甲渲染层 / 内部熔炉 / 月亮三项。')
    table.append('')
    p.write_text(s.rstrip() + NL.join(table), encoding='utf-8')
    print('(2) 07：版本台账补齐 1.1.41 → 1.1.73（%d 行）' % len(rows))
else:
    print('(2) 07：台账已到 1.1.73，跳过')

# ---------------------------------------------------------------- 06 新增脚本
p = WIKI / '06-工具脚本手册.md'
s = p.read_text(encoding='utf-8')
if 'cat_girl_tail_sway.py' not in s:
    add = NL.join([
        '', '## 1.1.66 → 1.1.73 新增/在用的脚本', '',
        '| 脚本 | 干什么 |', '|---|---|',
        '| `tools/cat_girl_v4_build.py` | 猫耳娘 v4 唯一真相源：128² 皮肤 + 逐面 UV 装机 geo + `.bbmodel` |',
        '| `tools/cat_girl_v4_audit.py` / `cat_girl_v4_bands.py` | v4 自检：UV 重叠 / 越界 / 面部分区核验 |',
        '| `tools/cat_girl_tail_sway.py` | 尾巴摆动：逐节相位波重写 `tail1..tail4` 的 rotation（`--check` 校验盘上文件） |',
        '| `tools/cat_girl_recipes_sync.py` | 配方表同步（原版 + 实机模组 + 本模组，1433 条，指纹 `--check`） |',
        '| `tools/_patch_recipes_runtime.py` | 配方表运行期接线（`CatGirlRecipeTable`） |',
        '| `tools/_patch_catgirl_ui.py` / `_ui2.py` | 猫耳娘 GUI 布局（原版 9 列、面板 226） |',
        '| `tools/_patch_catgirl_tools.py` | 工具即指令（斧→伐木 / 镐→挖矿 / 剑·弓·弩→战斗） |',
        '| `tools/_patch_catgirl_171.py` | 全无敌不死 + 弓弩完整蓄力 |',
        '| `tools/_patch_catgirl_172.py` | 拾取 / 自制 / 按工种换装（含盔甲）/ 无耐久 / 砸矿必掉 |',
        '| `tools/_patch_catgirl_173a.py` / `_173b_moon.py` / `_fix_173.py` | 1.1.73：订做 + 3×3 摆放 + 熔炼 / 月亮三项 / 编译修正 |',
        '| `tools/_deploy_<ver>.py` | 出货门禁（`_deploy_173.py` 是本轮最新） |',
        '| `tools/reload_press_vertical.py` | 换弹「压入件」位移必须纯竖直（+Y、z 分量恒 0） |',
        '', '> **规矩**：动画/几何 JSON 一律**由生成器算出**，不许手改；改完本仓库 `docs/wiki` 必须**手动**同步到 GitHub Wiki。',
        '',
    ])
    p.write_text(s.rstrip() + add, encoding='utf-8')
    print('(3) 06：+ 1.1.66→1.1.73 脚本表')
else:
    print('(3) 06：已含，跳过')

# ---------------------------------------------------------------- 02 代码地图
p = WIKI / '02-代码与资源地图.md'
s = p.read_text(encoding='utf-8')
if 'CatGirlArmorLayer' not in s:
    add = NL.join([
        '', '## 猫耳娘（com.apocalypse.zombies.entity / client）', '',
        '| 类 | 干什么 |', '|---|---|',
        '| `entity/CatGirlEntity` | 本体：`Job` 状态机、`pickupNearby`（1.5 格 / 5 tick）、',
        '| | `ensureMainHand`（工种→原版标签）、`ensureArmor`、`keepGearPristine`（20 tick 修满）、全无敌兜底 |',
        '| `entity/CatGirlCrafting` | **1.1.73 主干**：3×3 摆放（配方形状 → 网格 → 原版 `matches`）、`craftOne`（自己用）、',
        '| | `craftOrder`（玩家订做，材料她的 + 爱心币手续费）、`smeltOne`（内部熔炉，原版 `smelting` + `isFuel`） |',
        '| `entity/CatGirlRecipeTable` | 载入装机配方表 `data/apocalypse_zombies/cat_girl/recipes.json`（1433 条） |',
        '| `entity/ai/WorkBlockGoal` | 伐木/挖矿；drops 为空且需对口工具时用下界合金镐/斧补取（`always_drops`） |',
        '| `entity/ai/CatGirlBowGoal` | 弓 20 tick 满弦 / 弩 25 tick 装填（`BOW_DRAW` / `CROSSBOW_LOAD`） |',
        '| `entity/menu/CatGirlTradeMenu` | 面板：货架 + 下单槽（样品槽 / 成品槽 / `updateOrder` 在 `broadcastChanges` 里跑） |',
        '| `client/gui/CatGirlTradeScreen` | 屏幕：原版 9 列布局、下单标签与手续费 |',
        '| `client/renderer/CatGirlGeoRenderer` | GeckoLib 渲染器 + `HeldItemLayer`（手持）+ `CatGirlArmorLayer`（盔甲） |',
        '| `client/renderer/CatGirlArmorLayer` | **1.1.73 新增**：把原版盔甲网格（内/外层 `HumanoidModel`）按骨骼包围盒贴到头部/躯干/四肢 |',
        '', '**配置（`Config.java`，`config/apocalypse_zombies-common.toml`）**：', '',
        '- 1.1.71：`invulnerable`（全无敌，默认开）',
        '- 1.1.72：`pickup` / `auto_equip` / `auto_craft` / `no_durability` / `always_drops`（默认全开）',
        '- 1.1.73：`craft_fee`(2) / `smelt`(true) / `armor_render`(true) / `blood_moon_spawn`(true) /',
        '  `blood_moon_spawn_interval`(200) / `blood_moon_spawn_count`(2)',
        '- 更早：`CAT_GIRL_WORK_RADIUS`(12) / `CHOP_TICKS`(40) / `MINE_TICKS`(60) / `TOOL_SPEEDUP`(0.5)',
        '',
    ])
    p.write_text(s.rstrip() + add, encoding='utf-8')
    print('(4) 02：+ 猫耳娘类地图与配置清单')
else:
    print('(4) 02：已含，跳过')

# ---------------------------------------------------------------- 同步到 Wiki 克隆
if CLONE.is_dir():
    n = 0
    for f in sorted(WIKI.glob('*.md')):
        if f.name == '_Sidebar.md':
            continue
        text = f.read_text(encoding='utf-8')
        text = re.sub(r'\((\d\d-[^)]+?)\.md(#[^)]*)?\)', r'(\1\2)', text)
        (CLONE / f.name).write_text(text, encoding='utf-8')
        n += 1
    print('(5) 同步 %d 页到 Wiki 克隆（链接已去 .md）：%s' % (n, CLONE))
else:
    print('(5) 找不到 Wiki 克隆目录：%s' % CLONE)
