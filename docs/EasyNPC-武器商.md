# EasyNPC 武器商

用 [Easy NPC](https://www.curseforge.com/minecraft/mc-mods/easy-npc)（已装 `easy_npc-forge-1.20.1-7.14.0`）
开一个卖本模组枪械的 NPC —— 外观、名字、商品、价格全都可以自己改，不需要动代码。

## 预设已经放好了

```
src/main/resources/data/easy_npc/api/preset/apocalypse_zombies/weapon_merchant.npc.snbt
```

它随本模组的 jar 一起分发。装进游戏后在 EasyNPC 的预设列表里能找到
**「武器商 Weapon Merchant」**（分类：Apocalypse Zombies），摆下去右键就会打开交易界面。

这份预设做的事只有四件：

| 字段 | 值 | 作用 |
|---|---|---|
| `entityTypeId` | `easy_npc:villager` | 用村民当模型基底 |
| `VillagerData.profession` | `minecraft:weaponsmith` | 外观上是武器匠（有围裙和护目镜） |
| `VillagerData.level` | `5` | 大师级外观 |
| `ActionData.ON_INTERACTION` | `OPEN_TRADING_SCREEN` | **右键直接开交易界面** |
| `TradingDataSet.Type` | `CUSTOM` | 交易表由你自己配，而不是套原版职业表 |

`Invulnerable:1b` 与各项 `DropChances:0` 是为了让它别在末日里被打死、也别掉一地东西 —— 想要能被打死就改掉这两处。

## 改商品与价格（不用改文件）

EasyNPC 把交易数据存在**实体身上**（`TradingDataSet` + 交易表），不是存在预设文件里，
所以配商品请**在游戏内**做：

1. 摆一个武器商 NPC（或用 `/summon`）
2. 潜行 + 右键（或按 EasyNPC 的配置键，默认在它的配置界面里）打开 **EasyNPC 配置界面**
3. 进 **Trading / 交易** 页，把 `Type` 保持 `CUSTOM`，然后逐条加商品：
   - **左格**放你要卖的物品（从背包拖过去，或直接用物品选择器）
   - **右格**放你要收的货币（比如绿宝石、金锭）
   - `MaxUses` 是这条交易能被用几次，`RewardedXP` 是成交给的职业经验
4. **改价格**就在这一步改：换右格的物品与数量即可。想让枪更贵，把右格改成 32 绿宝石这种。
5. 配好后**把 NPC 存成预设**（EasyNPC 的 "Save as preset"），下次直接复用 —— 也就是说
   **你不必改仓库里这个文件，改完在游戏里存一份自己的预设就行**。

> `ResetsEveryMin:0` = 永不自动补货（`MaxUses` 用完就没了）。想让商店自动恢复，把它改成分钟数。

## 本模组可以卖的物品 ID

六把枪（物品 ID 就是注册名，`easy_npc` 的商品槽里直接搜名字即可）：

| ID | 说明 |
|---|---|
| `apocalypse_zombies:awm` | 栓动狙击步枪，.338 |
| `apocalypse_zombies:m1_garand` | M1 加兰德，8 发漏夹 |
| `apocalypse_zombies:mosin_nagant` | 莫辛-纳甘 M91/30 |
| `apocalypse_zombies:uzi` | Uzi 冲锋枪，全自动 |
| `apocalypse_zombies:s686` | 金板 S686 折开式双管霰弹枪 |
| `apocalypse_zombies:crossbow` | 十字弩（右键透明瞄准镜） |

**注意：本模组没有"弹药物品"。** 枪的弹量与弹种都存在物品 NBT 里（`Ammo` / `Shell`），
靠 `R` 键轮盘切换、不消耗背包 —— 所以**商店卖不出子弹**，也没有子弹可卖。
要"补给"就让玩家用绿宝石直接买**装满弹的枪**，或者搭配别的模组（比如 TaCZ 的弹匣）来卖。

## 已知不确定 / 需要实机确认

这份预设是我按 EasyNPC 7.14.0 的类结构反推写出来的（`TradingDataSet` 的 NBT 键为
`Type` / `MaxUses` / `RewardedXP` / `ResetsEveryMin` / `LastReset`，取自
`de.markusbordihn.easynpc.data.trading.TradingDataSet` 的常量），**没有实机验证过**：

- 预设里带 `TradingDataSet` 是否会被 EasyNPC 接受，还是只在实体上生效 —— 若预设列表里看不到它，
  就把这段删掉，改用游戏内配置界面配完再存预设。
- `Type:"CUSTOM"` 是否需要额外的交易表字段（`Offers`）才能出货。商品在界面里加得进去就不需要。

这两点实机一试就知道。如果哪一步对不上，把 EasyNPC 报的错或界面截图给我，我按实际格式改。
