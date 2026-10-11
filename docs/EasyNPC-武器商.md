# EasyNPC 武器商

用 [Easy NPC](https://www.curseforge.com/minecraft/mc-mods/easy-npc)（本机已装 `easy_npc-forge-1.20.1-7.14.0`）
开一个卖本模组枪械的 NPC —— 外观、名字、商品、价格全都可以自己改，不需要动代码。

## 预设在哪、怎么用

```
src/main/resources/data/easy_npc/default_preset/villager/weapon_merchant.npc.snbt
```

随模组 jar 分发，放在 EasyNPC 认的 `default_preset/<实体类型>/` 下（与它自带的 24 个默认预设同级；
原来的 `api/preset/apocalypse_zombies/` 不是 EasyNPC 的约定路径，已挪走）。装进游戏后在 EasyNPC
的预设列表里能找到 **「武器商 Weapon Merchant」**（分类：Apocalypse Zombies），摆下去**右键直接开交易界面**。

## 修复记录（2026-10-11，实机验证后）

这份预设原来有两个真问题，都是实机导入后才暴露的：

1. **`TradingDataSet` 挂错了层** —— 原来直接写在 `data:` 下，而 EasyNPC 读的是
   **`data.TradingData.TradingDataSet`**（见 `TradingDataCapable` 的字段表）。
   写成顶层就意味着**交易设置整段被忽略**。
2. **商品表 `Offers` 整个缺失** —— 摆出来的武器商是个**空商店**（右键能开界面，里面什么都没有）。

修法就是照 EasyNPC 官方带交易的预设（`default_preset/villager/welcome_coin_trader.npc.snbt`）逐字段对齐，
并把自己缺的字段补齐：`Offers` / `PresetUUID` / `Profession` / `SkinData` / `SoundData` / `EntityAttribute`。

> 教训：**别按类结构反推 SNBT 再直接发**。`javap` 能告诉你字段名，但告诉不了你**层级**与**嵌套**。
> 正确做法是先找一个官方同类预设当模板。

**已实机验证**（2026-10-11）：修好后重新导入，七条商品都正常出现在交易界面里 —— `Offers` 与
`TradingData` 这段结构确实是对的。`security.cfg` 抬到 `OWNERS` 之后，导入提示里也不再出现
`Action permission levels were reduced`（`Owner data was updated` 仍会打，那是每个预设都会有的）。

## 预设自带的商品

七条交易，全部**装满弹**（弹量写在物品 NBT 的 `Ammo` 键里），货币是绿宝石：

| 商品 | 弹量 | 价格 | maxUses | xp |
|---|---|---|---|---|
| `apocalypse_zombies:uzi` | 32 | 18 绿宝石 | 16 | 8 |
| `apocalypse_zombies:crossbow` | 1 | 20 | 16 | 8 |
| `apocalypse_zombies:s686` | 2 | 24 | 12 | 10 |
| `apocalypse_zombies:mosin_nagant` | 5 | 32 | 12 | 12 |
| `apocalypse_zombies:m1_garand` | 8 | 36 | 12 | 14 |
| `apocalypse_zombies:rsc_1917` | 5 | 40 | 8 | 16 |
| `apocalypse_zombies:awm` | 5 | 48 | 8 | 20 |

`TradingData.TradingDataSet.ResetsEveryMin = 30` —— 每 30 分钟自动补货（设 `0` = 永不补货，
`maxUses` 用完就没了）。

## 改商品与价格

两条路：

**A. 改预设文件**（改了所有人都有）—— 编辑 `Offers.Recipes.Recipes` 数组，每条是一个标准原版
`MerchantOffer` 的序列化：

```
buy:{  Count:18b, id:"minecraft:emerald" }                          // 玩家付的（第一货币）
buyB:{ Count:-1b, id:"minecraft:air" }                              // 第二货币，-1b + air = 不用
sell:{ Count:1b,  id:"apocalypse_zombies:uzi", tag:{ Ammo:32 } }    // 玩家拿到的
demand:0, maxUses:16, priceMultiplier:1.0f, rewardExp:1b,
specialPrice:0, uses:0, xp:8
```

**B. 游戏内改**（只影响这一个 NPC）—— 潜行右键（或按 EasyNPC 的配置键）打开配置界面 →
**Trading / 交易** 页逐条加改商品；改完用 "Save as preset" 存成自己的预设。

## 导入时的两条提示不是错误

导入任何预设时聊天栏都会打：

```
Preset imported, but some features were limited by server rules.
- Owner data was updated.
- Action permission levels were reduced.
```

**这是 EasyNPC 对每个预设都会做的净化**（`PresetAccess` + `sanitize.*` 文案），官方内置预设
（比如 `welcome_coin_trader`）导入时**一字不差地打同样两条**。含义：

- `Owner data was updated`（`sanitize.owner_rewritten`）—— 预设里的主人信息被改写成**导入者**。
  正常且预期，不用管。
- `Action permission levels were reduced`（`sanitize.action_permission_clamped`）—— 动作的权限等级
  被**夹**到 `config/easy_npc/security.cfg` 里 `creativePlayerCommandLevel`（默认 `MODERATORS`）的上限。

要让它别夹，就抬 `security.cfg` 里的上限（本机已按此调整过）：

```
creativePlayerCommandLevel=OWNERS
maxAdminImportedCommandLevel=OWNERS
serverTrustedCommandLevel=OWNERS
```

## 本模组可以卖的物品

几把枪（物品 ID 就是注册名，EasyNPC 的商品槽里直接搜名字即可）：

| ID | 说明 | 匣容 |
|---|---|---|
| `apocalypse_zombies:awm` | 栓动狙击步枪，.338 | 5 |
| `apocalypse_zombies:m1_garand` | M1 加兰德，8 发漏夹 | 8 |
| `apocalypse_zombies:mosin_nagant` | 莫辛-纳甘 M91/30 | 5 |
| `apocalypse_zombies:rsc_1917` | RSC M1917 | 5 |
| `apocalypse_zombies:uzi` | Uzi 冲锋枪，全自动 | 32 |
| `apocalypse_zombies:s686` | 金板 S686 折开式双管霰弹枪 | 2 |
| `apocalypse_zombies:crossbow` | 十字弩（右键透明瞄准镜） | 1 |

七件铜装备也可以卖：`copper_sword` / `copper_pickaxe` / `copper_hoe` / `copper_axe` /
`copper_helmet` / `copper_chestplate` / `copper_leggings` / `copper_boots`。

**注意：本模组没有"弹药物品"。** 枪的弹量与弹种都存在物品 NBT 里（`Ammo` / `Shell`），
靠 `R` 键轮盘切换、不消耗背包 —— 所以**商店卖不出子弹**，也没有子弹可卖。
要"补给"就让玩家用绿宝石直接买**装满弹的枪**，或者搭配别的模组（比如 TaCZ 的弹匣）来卖。
