# -*- coding: utf-8 -*-
"""1.1.82 文档同步：wiki 02（地图/配置项）与 07（版本表 + 高亮说明 + 自测）。

用文件方式跑（不走 heredoc），避免多层转义。
"""
import io

ROOT = 'F:/mcmod/docs/wiki/'
NL = chr(10)
BS = chr(92)


def load(name):
    p = ROOT + name
    s = io.open(p, encoding='utf-8', newline='').read()
    return p, s


def save(p, s):
    io.open(p, 'w', encoding='utf-8', newline='').write(s)
    print('写回', p, len(s), 'chars')


def rep(s, old, new, n=1, tag=''):
    assert s.count(old) == n, (tag, s.count(old), old[:60])
    return s.replace(old, new, n)


# ---------------- 02 · 代码与资源地图 ----------------
p2, s2 = load('02-代码与资源地图.md')
CRLF2 = '\r\n' if '\r\n' in s2 else NL

# 1) event/ 行：补 preview 是唯一出口
old = ('`PlayerVeinMine`（**1.1.81 玩家一键挖掘**：`@Mod.EventBusSubscriber(bus = FORGE)` + '
       '`BlockEvent.BreakEvent` → 以被砸那格为种子 flood fill / 半径扫描，`Block.getDrops` + '
       '`destroyBlock(pos, false)` 自己发产物；安全判定复用 `CatGirlHarvest.isMineable`，配置全在 '
       '`[player_mine]`。**没有按键、没有网络包**） |')
new = ('`PlayerVeinMine`（**1.1.81 玩家一键挖掘**：`@Mod.EventBusSubscriber(bus = FORGE)` + '
       '`BlockEvent.BreakEvent` → 以被砸那格为种子 flood fill / 半径扫描，`Block.getDrops` + '
       '`destroyBlock(pos, false)` 自己发产物；安全判定复用 `CatGirlHarvest.isMineable`，配置全在 '
       '`[player_mine]`。**没有按键、没有网络包**。**1.1.82**：选块逻辑收成一个公开出口 '
       '`preview(LevelReader, BlockPos, ItemStack)` —— 服务端拿它决定砸哪些、客户端拿它画高亮，'
       '**一份判定两处用**，所以「画出来的框 = 真的会砸的」） |')
s2 = rep(s2, old, new, 1, '02 event 行')

# 2) client/renderer/ 行：加 VeinMineHighlighter
old = '| `client/renderer/` | 渲染器 | `*ItemRenderer`（枪）、`*Renderer`（生物） |'
new = ('| `client/renderer/` | 渲染器 | `*ItemRenderer`（枪）、`*Renderer`（生物）、'
       '`VeinMineHighlighter`（**1.1.82 玩家挖掘高亮**） |')
s2 = rep(s2, old, new, 1, '02 renderer 行')

# 3) 客户端每帧入口那条：见 client/ 行
old = '| `client/` | 客户端总入口 | `ClientEvents`（745 行）、`ClientModBusEvents`、`KeyBindings`、`GunAimState`、`ZombieRenderEvents` |'
new = ('| `client/` | 客户端总入口 | `ClientEvents`（745 行；**1.1.82** 起在 `onRenderLevelStage` '
       '开头调一句 `VeinMineHighlighter.render(event)`）、`ClientModBusEvents`、`KeyBindings`、'
       '`GunAimState`、`ZombieRenderEvents` |')
s2 = rep(s2, old, new, 1, '02 client 行')

# 4) 配置项追加 1.1.82 一条
anchor = ('  `to_inventory`(true 产物进背包) / `protected`([] 追加保护名单，与 `cat_girl.mine_protected` 合并)'
          + CRLF2)
assert s2.count(anchor) == 1
s2 = s2.replace(anchor, anchor + CRLF2.join([
    '- 1.1.82（新增 1 项 → 界面共 **168 项**，`[player_mine]` 段）：`highlight`(true '
    '瞄准的方块会连带的那些在**客户端描一圈青边** —— 画的一定是真会砸的；纯观感，关掉照样能一键挖掘)',
    '',
]) + CRLF2, 1)
save(p2, s2)

# ---------------- 07 · 出货与版本管理 ----------------
p7, s7 = load('07-出货与版本管理.md')
CRLF7 = '\r\n' if '\r\n' in s7 else NL

# 版本表加 1.1.82 行（1.1.80 那行之后）
row80 = '| 1.1.80 | ①她的库存扩到 **36 格**'
i = s7.find(row80)
assert i >= 0
j = s7.find(CRLF7, i)
assert j > 0
row82 = (CRLF7 + '| 1.1.82 | **玩家挖掘高亮**：瞄着矿脉时，会连带的方块在客户端描青边；'
         '选块复用服务端同一个 `PlayerVeinMine.preview`（画框 = 会砸）；纯观感，'
         '`[player_mine] highlight` 默认 true |')
s7 = s7[:j] + row82 + s7[j:]

# 末尾补 1.1.82 说明块（含一个坑：事件不带 MultiBufferSource）
tail = CRLF7 + CRLF7 + CRLF7.join([
    '## 1.1.82 · 玩家挖掘高亮（客户端描边）',
    '',
    '- **它是纯观感**：开关在 `[player_mine] highlight`（默认 true）。关掉只影响看不看得见，',
    '  不影响挖到什么 —— 判定始终在服务端。',
    '- **为什么画的一定对**：高亮调的 `PlayerVeinMine.preview(...)` 就是服务端决定「砸哪些」的',
    '  同一份方法（同一份配置 + 同一套安全判定）。没有第二条选块路径，所以不会画了不砸。',
    '- **1.20.1 的坑**：`RenderLevelStageEvent` **没有** `getMultiBufferSource()`（那是更晚的版本才有的）。',
    '  要借 `Minecraft.getInstance().renderBuffers().bufferSource()` 拿 `RenderType.lines()` 的 buffer，',
    '  画完自己 `endBatch(RenderType.lines())` —— 原版 `LevelRenderer.renderHitOutline` 用的是同一只笔。',
    '- **另一个小坑**：瞄准的那一格**不要**自己画 —— 原版已经给它画了黑框，同一批像素上叠两层会闪。',
    '  所以只画「会连带下来的那些」。',
    '- **不卡**：瞄准格 + 影响结果的配置（半径 / 上限 / 目标集合 / 是否只认连通 / 是否要求工具）没变就不重算。',
    '',
    '**怎么自测**：拿铁镐瞄着铁矿脉（不按左键）→ 整簇冒青边；挪开视线 → 青边消失；',
    '配置里 `highlight=false` → 青边再也没有（但左键照样整簇下来）；',
    '`targets=2` 后对着自己盖的房子 → 现在会画出来了（这时它真的会砸，别怪没提醒）。',
])
s7 = s7.rstrip(CRLF7) + tail + CRLF7
save(p7, s7)
print('07 OK')
