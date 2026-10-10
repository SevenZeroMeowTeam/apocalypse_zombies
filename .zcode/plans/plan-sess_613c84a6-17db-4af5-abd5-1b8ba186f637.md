# 猫耳娘随从（Cat Girl Companion）—— 完整实施计划

模组：`apocalypse_zombies`（Forge 1.20.1 + GeckoLib 4.8.4，F:\mcmod，分支 feat/awm-9217）
已确认的玩法决策：**鱼驯服** · **以物易物菜单** · **敌对生物伤害无效** · **空手右键循环切换任务模式**。

---

## 第一部分：Blockbench 建模（blockbench-mcp）

### 1.1 新建工程
- `create_project(name="cat_girl", format="geckolib_model")`（GeckoLib Animated Model，直接产出 geo.json + animation.json，和项目现有 `geo/*.geo.json`、`animations/*.animation.json` 管线一致）。
- 纹理分辨率 64x64（按 agent.md §6.4 六要素模板：小体型角色用 64x64）。

### 1.2 模型结构（成人比例，总高约 32u / 2.0 格，碰撞箱 `sized(0.6f, 1.95f)`）
按 agent.md「标准玩家骨架 + 猫特征」扩展：

```
Root (0,0,0)
├── 右腿 RightLeg  (pivot 2,12,0)      ← 标准 4×12×4
├── 左腿 LeftLeg   (pivot -2,12,0)
├── 身体 Body       (pivot 0,12,0)      ← 水手服/深色连衣裙 8×12×4
│   └── 尾巴 Tail    (pivot 0,14,-2)    ← 分 3 节，可摆动
├── 右臂 RightArm   (pivot -5,14,0)     ← 右手末端加子骨骼 item_righthand（持物挂点）
├── 左臂 LeftArm    (pivot 5,14,0)
└── 头 Head         (pivot 0,24,0)      ← 8×8×8
    ├── 右猫耳 RightEar (pivot -2,31,0) ← 2×3×1 三角感小方块
    ├── 左猫耳 LeftEar  (pivot 2,31,0)
    └── 双马尾/长发 Hair (pivot 0,27,-3)
```

Cube 数值表（origin / size / uv，rotation 默认 0，pivot 关节处）在建模时逐个填入；UV 用 UV 面板 `C` 自动展开后目检无重叠。`item_righthand` 是空骨骼（无 cube），专供手持物品渲染层挂接。

### 1.3 纹理
- 写 `tools/cat_girl_texture.py`（沿用 `tools/bride_v2.py` 等脚本生成贴图的项目惯例）生成 64x64 PNG：动漫配色——肤色、深蓝水手服白襟、深色短裙、黑长靴、粉色内耳猫尾尖；输出到 `src/main/resources/assets/apocalypse_zombies/textures/entity/cat_girl.png`。
- Blockbench 里加载该贴图，绑定各骨骼 UV。

### 1.4 动画（Animate 模式，关键帧按 agent.md §3 第 5 步姿态数值）

| 动画名 | 触发条件 | 关键帧要点 |
|---|---|---|
| `idle` | 静止（空手） | 呼吸：Body y ±0.3；尾巴 rx 摆 ±10°；耳朵微动；头 ry ±5° |
| `walk` | 行走（空手） | 双腿 rx ±30° 反相，双臂反相摆，尾巴随动 |
| `idle_hold` | 静止（手持武器/工具） | 右臂抬起持握姿 rx ≈ -60°，护住胸前 |
| `walk_hold` | 行走（手持） | 同 walk 但右臂保持持握姿 |
| `equip` | 拿取武器/工具瞬间（one-shot） | 右臂 0→0.25s 抬起接过物品→回位，easeOut |
| `attack` | 打怪攻击（one-shot） | 单臂前挥 rx ≈ -70°，0→0.3s easeOut |
| `chop` | 伐木挥砍（循环） | 双臂抡砍 rx -80°，0→0.4s 循环 |
| `mine` | 挖矿敲击（循环） | 单臂镐击 rx -60°，0→0.5s 循环 |
| `hurt` | 被玩家/环境伤害（one-shot） | 躯干后仰 ry ≈ 10° |
| `death` | 死亡（one-shot） | 缓慢倒地 |

### 1.5 导出与保存
- `Ctrl+S` 保存 `.bbmodel` 到 `art/cat_girl/cat_girl.bbmodel`（可复现工程）。
- 用导出 codec（`bedrock`/`project`，MCP `list_export_formats` 已确认可用）导出 geo + animation JSON 到：
  - `src/main/resources/assets/apocalypse_zombies/geo/cat_girl.geo.json`
  - `src/main/resources/assets/apocalypse_zombies/animations/cat_girl.animation.json`
- 用 offscreen view + screenshot 截图自查模型外观。

---

## 第二部分：Java / Forge 集成

### 2.1 实体 `entity/CatGirlEntity.java`
`extends TamableAnimal implements GeoEntity` —— 用 `TamableAnimal` 的理由：自带 owner NBT/广播，且 **`AllyJudge.isPlayerSide()` 直接认它为玩家阵营**（零改动获得 NoInfighting、AllySafeHurtByTargetGoal 全套友军逻辑）。

- **GeckoLib 管线**：照抄 `BrideZombie` 模式——`AnimatableInstanceCache`、两个动画控制器：
  - `"movement"`：按 `手持类别 × 移动状态` 选择 `idle/walk/idle_hold/walk_hold`（level 3 平滑过渡）
  - `"action"`：one-shot/循环动作（`equip/attack/chop/mine/hurt/death`），由同步数据 flag 驱动，`forceTransmission` 触发
- **属性**：`createAttributes()` = MAX_HEALTH 40、MOVEMENT_SPEED 0.24、ATTACK_DAMAGE 4、ARMOR 2、FOLLOW_RANGE 32 → 注册进 `ModEntities.registerAttributes`。
- **无敌（已确认范围：敌对生物无效）**：
  ```java
  @Override public boolean isInvulnerableTo(DamageSource source) {
      if (source.getEntity() instanceof LivingEntity le && AllyJudge.isHorde(le)) return true;
      if (source.is(DamageTypeTags.WITHER_SKULL)...  // 由 shooter Monster 覆盖
      return super.isInvulnerableTo(source);
  }
  ```
  玩家攻击、摔落、岩浆等照常。
- **不消失**：`removeWhenFarAway → false`、`setPersistenceRequired()`、非日晒敏感。

### 2.2 交互（`mobInteract`，服务端判定，按序）
1. **未驯服 + 手持鱼（`ItemTags.FISHES`）** → 50% 成功（失败有提示音），成功 `setTamed(true)`、`setOwner(player)`、爱心粒子；再喂鱼=回血。
2. **已驯服 + 手持武器/工具（斧/剑/镐/锹/锄 或 `TieredItem`/`DiggerItem`）** → 转移进她主手（`setItemSlot(MAINHAND)`），触发 `equip` 动画。
3. **已驯服 + 潜行右键（空手或她持物时）** → 空手：收回主手物品；持物空手潜击：不，收回条件改为「潜行+空手右键」= 打开交易菜单（若主手为空）；主手持物时潜行右键=收回物品。**（实现时简化为：潜行右键永远打开交易菜单，菜单里有"收回"按钮格。）**
   —— 最终定稿：
   - 空手右键（不潜行）= **循环切换任务模式**：跟随 → 伐木 → 挖矿 → 战斗 → 跟随，聊天栏 + 她的语音粒子提示当前模式。
   - 潜行右键 = **打开交易菜单**。
4. 空手右键之外的普通物品（非鱼非工具）= 无动作（防止误操作）。

### 2.3 任务 AI（`entity/ai/`，全新；`goalSelector` 用 项目惯例把远程目标放优先级 1）
模式存在同步数据 `SynchedEntityData`（`JOB_MODE: FOLLOW/LUMBER/MINE/FIGHT`），各目标 `canUse()` 读模式：

| 模式 | 目标 | 行为 |
|---|---|---|
| FOLLOW | 原版 `FollowOwnerGoal` + `WaterAvoidingRandomStrollGoal` | 距离 > 6 传送到主人身边（原版逻辑） |
| LUMBER | **新 `ChopBlockGoal`** | 在半径 12 内找 `BlockTags.LOGS` → 走过去 → 播 `chop` 动画 → 计时 N tick（原木 40t，按有无斧头减半）→ `level.destroyBlock(pos, false)`，掉落进她 18 格库存（满则掉脚边） |
| MINE | **新 `MineBlockGoal`**（复用 `ChopBlockGoal`，过滤器换成 `BlockTags.BASE_STONE_OVERWORLD` + `#forge:ores`） | 同上，播 `mine` 动画 |
| FIGHT | `NearestAttackableTargetGoal`（过滤 `AllyJudge.isHorde`，半径 16）+ `MeleeAttackGoal` + 现有 `GunAttackGoal` 若她持枪 | 打怪，攻击时播 `attack` |

通用：`FloatGoal`、`LookAtPlayerGoal`、`SwimGoal`；死亡回主手物品给经验零掉落。

### 2.4 交易系统（以物易物菜单，全新——项目里目前没有任何 Menu/Screen）
- **货币**：新物品 `love_coin`（爱心币，`stacksTo(64)`），图标用现有 `models/item` 模板。
- **菜单** `entity/menu/CatGirlTradeMenu extends AbstractContainerMenu`（新 `registry/ModMenus.java`，`IForgeMenuType.create`）：
  - **给予格**（任意物品可放入，含模组物品；爱心币除外）→ 服务端按 **价值表** 计算 → **回报格** 显示等值爱心币，拿取即成交。
  - **她的库存 9 格**（= 实体的 18 格库存前 9 格，即伐木/挖矿产物）展示为可购买货物，**价格 = 同一价值表**；`clicked()` 覆写：扣玩家背包爱心币 → 给物品（钱不够发失败粒子）。
  - 下半部照搬原版玩家背包 36 格。
- **价值表** 进 `Config.java`（common）：`默认 1`；工具/武器/盔甲（有 `attack_damage` 或 `mineable/tag` 属性）= 3；可 `config` 追加覆盖（`值 = "modid:item=数字"` 列表）。**模组物品走默认值 1，天然支持任意模组物品。**
- **Screen** `client/gui/CatGirlTradeScreen extends AbstractContainerScreen`，在 `ClientModBusEvents` 新增 `RegisterMenuScreensEvent` 处理器注册。
- 打开方式：`player.openMenu(menuProvider)`（无需新网络包；`NetworkHandler` 不动）。

### 2.5 注册与资源（改动清单）

**新文件**
| 文件 | 内容 |
|---|---|
| `entity/CatGirlEntity.java` | 实体主体 |
| `entity/ai/ChopBlockGoal.java`（含 Mine 变体） | 伐木/挖矿 |
| `entity/menu/CatGirlTradeMenu.java` | 交易菜单 |
| `client/gui/CatGirlTradeScreen.java` | 交易界面 |
| `client/model/CatGirlGeoModel.java` | geo/texture/anim 路径常量（照 `BrideGeoModel`） |
| `client/renderer/CatGirlGeoRenderer.java` | `GeoEntityRenderer` + **`BlockAndItemGeoLayer`**（`stackForBone`: bone 名 `item_righthand` → 主手物品；`getTransformTypeForStack` 返回 `GROUND`），实现「拿着玩家给的武器/工具」渲染 |
| `registry/ModMenus.java` | `DeferredRegister<MenuType<?>>` |
| `registry/ModItems.java` 内新增 | `CAT_GIRL_SPAWN_EGG`、`LOVE_COIN` |
| `tools/cat_girl_texture.py` | 生成贴图 |
| `assets/.../geo/cat_girl.geo.json`、`animations/cat_girl.animation.json`、`textures/entity/cat_girl.png` | Blockbench 导出 |
| `assets/.../models/item/cat_girl_spawn_egg.json`、`love_coin.json` | `{"parent":"minecraft:item/template_spawn_egg"}` / 普通平面图标 |
| `art/cat_girl/cat_girl.bbmodel` | 工程存档 |

**改文件**
- `registry/ModEntities.java`：注册 `CAT_GIRL`（`MobCategory.CREATURE`, `sized(0.6f,1.95f)`）+ `event.put(..., CatGirlEntity.createAttributes().build())`
- `registry/ModItems.java`：蛋 + 爱心币 + 创造标签（SPAWN_EGGS / 交易类进 `MISC`）
- `client/ClientModBusEvents.java`：`registerEntityRenderer(CAT_GIRL, CatGirlGeoRenderer::new)` + 菜单 Screen 注册
- `ApocalypseZombies.java`：`ModMenus.register(modBus)`
- `Config.java`：交易价值表 + 跟随距离/工作半径
- `lang/zh_cn.json` / `en_us.json`：`entity.apocalypse_zombies.cat_girl = 猫耳娘`、蛋、爱心币、4 种模式提示语、GUI 标题

### 2.6 实体注册位置的兼容性（已验证）
`AllyJudge.isPlayerSide()` 已兼容 `TamableAnimal`；`NoInfighting` 会自动保护她 vs 敌怪互不误伤——**无需改动阵营系统**。

---

## 第三部分：验证

1. `gradlew compileJava`（快）确认编译通过。
2. `gradlew build` 全量产物。
3. Blockbench offscreen 截图自查模型/动画；如本地能起 `runClient` 则实测：驯服 → 切模式 → 伐木/挖矿 → 打怪（被怪打不掉血）→ 潜行右键交易（卖模组物品得币、买她的产物）。
4. 更新 `readme.md` 版本横幅与变更条目（沿用 1.1.65 的条目格式）。

## 顺序与里程碑
1. Blockbench 模型 + 贴图 + 导出（先出可视资产）
2. 动画 + 导出
3. 实体 + 注册 + 渲染（进游戏能看见、能驯服、跟随）
4. 任务 AI（伐木/挖矿/打怪 + 模式切换）
5. 无敌 + 交易菜单
6. 编译/构建验证 + readme
