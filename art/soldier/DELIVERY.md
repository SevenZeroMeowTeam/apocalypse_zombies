# 残兵 · 军装僵尸士兵（SoldierZombie）交付台账

> 需求原文：**「添加变种僵尸手持弓箭，投掷点燃 tnt 丢向玩家，添加一个僵尸模型参考图片内容
> 进行 blockbench 建模及特殊动画」**
> 参考图：`E:\Administrator\Pictures\R-C-1.jpg`（三只二战风格军装僵尸士兵）

出货版本 **1.1.21**　md5 `87d93825505d91cdd21a657f24b5edf1`
（1.1.20 → 已改名 `.old.bak`，mods 内只留一个生效版本）

---

## 1. 需求 → 实现对照

| 需求 | 实现 |
| --- | --- |
| 变种僵尸手持弓箭 | 新实体 `soldier_zombie`（中文名「残兵」）。主手挂原版弓供原版 AI 判定，**玩家看到的弓是建进骨骼树的**（`bow` / `bow_limb_up` / `bow_limb_low` / `bow_string_up` / `bow_string_down`），所以弓弦能跟着拉弓动作真的拉成 V 形 |
| （同样）远程射击 | 原版 `RangedBowAttackGoal` + `RangedAttackMob.performRangedAttack`，1.6 初速带仰角补偿，射程 15 |
| 投掷点燃 TNT 丢向玩家 | 自定义 `ThrowTntGoal`：1.5s 抡臂出手，**第 13 tick 生成原版 `PrimedTnt`**（引信 50 tick ≈ 2.5s，给玩家躲的余地），按抛物线解初速 |
| 参考图片建模 | 几何 + 贴图由 `tools/soldier_v2.py` 生成（纯标准库、可重复）：**24 骨 / 61 块 / 图集 23.1%**，128×128 双层皮肤，1u = 1px，朝向 −Z |
| 特殊动画 | `tools/soldier_anim.py` 生成 4 个剪辑：`idle`(3.0s 循环) / `walk`(1.0s 循环) / `shoot`(1.0s 单次，拉弓到释放) / `throw_tnt`(1.5s 单次，引臂到出手) |

**两个贴图变种**（对应参考图里三只兵的不同装具）：`VARIANT_ARCHER`（背箭袋）/
`VARIANT_SAPPER`（背工兵铲），服务端 `finalizeSpawn` 随机后同步。

---

## 2. GeckoLib 坐标约定（全部查源码定案，不是猜的）

| 通道 | 事实 | 出处 |
| --- | --- | --- |
| 动画 `rotation` 的 x / y | **取负**后转弧度（z 不取） | `loading/json/typeadapter/BakedAnimationsAdapter.java:200-202` |
| 动画 `position` | 不取负、不换算 | 同上，`isForRotation` 分支之外 |
| 位置单位 | **u（1 = 1 模型像素 = 1/16 格）** —— 与 `.geo.json` 坐标同域 | `util/RenderUtils.translateMatrixToBone`：`translate(−posX/16, +posY/16, +posZ/16)` |
| 位置 x | **取负**（y / z 不取） | 同上（与 rotation 的 x/y 取负同源，GeckoLib 的模型空间 x 是镜像的） |
| 旋转矩阵合成顺序 | Z → Y → X（点先绕 X 转，再 Y，再 Z） | `RenderUtils.rotateMatrixAroundBone` 的 mulPose 顺序 |
| 骨骼层级 | 本工程用 **平铺 + `parent` 字段**（GeckoLib 认，`loading/json/raw/Bone.java` 读 `"parent"`，`GeometryTree` 据此建树） | 不是 Blockbench 的 `children` 嵌套 |

**由此得到的编排口诀**：
* 肢体（在 pivot 之下）：**JSON `x` 为负 = 向前摆**；
* 躯干/头（在 pivot 之上）：**JSON `x` 为正 = 向前俯**；
* 绕 Z：右手边肢体 `z` 为正 = 向 +X 摆（成对骨骼外展异号）；
* 绕 Y：`y` 为正 = 身体向**其右侧**转。

---

## 3. 本轮踩到并修掉的坑（都会重犯，写在这里）

1. **骨骼树是平的时候，"转大臂"不会带动小臂/手/弓** —— 预览器只认 `children`，
   而 geo 用的是 `parent` 字段，于是所有姿势看起来"没生效"。修的是工具，不是模型。
2. **预览器屏幕 x 映射反了** —— 相机在 −z 侧朝 +z 看时相机右方是 −x，
   写成 `+p[0]` 会得到镜像图，用它判断"东西在左手还是右手"会全部反过来。
3. **`rot_x()` 自己会做度→弧度转换**，传弧度进去等于只转了 1/60 的角度（86° → 1.5°），
   姿势"有反应但幅度极小"就是它。
4. **弓挂在 hand_r 上，手臂一抬弓就跟着横躺** —— 持弓臂抬多少度，`bow` 骨就要反向补多少度，
   四个剪辑都得补。这是道具骨骼的标准代价，不是 bug。
5. **射击剪辑长度必须钉死 1.0s** —— 原版 `RangedBowAttackGoal` 的拉弓时长不对外开放
   （20 tick 拉满即射），1.2s 的剪辑会在箭出膛前被 STOP 掐断，释放段根本看不到。
6. **拉弓剪辑里不要写腿部通道** —— 原版弓 Goal 会让怪边走边拉，腿部要留给行走控制器，
   否则两个控制器抢同一根骨头（后注册的赢，腿就僵住）。
7. **投掷 Goal 的优先级必须高于近战** —— 否则玩家一贴近，近战 Goal 永远压着投掷不放。
8. **血渍贴片要"掩膜"不要"实心块"** —— 朝外的面用带噪声的椭圆掩膜（掩膜外 alpha=0，
   透出底下军装），其余五面填实色；实心矩形在模型上读起来像一块贴纸。
9. **藏面（hidden face）概念有害** —— 把面标成"不画"会在模型上戳洞、透出背后部件。所有面都上色。
10. **眼睛等关键细节至少 2u 高** —— 1px 高的眼睛在渲染里几乎不可见。

---

## 4. 产物与校验

| 文件 | 说明 |
| --- | --- |
| `art/soldier/DESIGN.md` | 设计规格（配色 / 体块唯一依据） |
| `tools/soldier_v2.py` | 几何 + 贴图生成器（纯标准库），自检：面重叠、镜像对称、图集越界、确定性哈希 |
| `tools/soldier_anim.py` | 动画生成器，自检：通道仅 rotation/position、两端键齐、循环两端等值、非循环末帧归零、位移量级体检 |
| `tools/model_preview.py` | 纯标准库正交软渲染预览器（Blender 禁用、Blockbench MCP 建的项目 3D 视口不挂 UI，视觉核对只能走它），支持 `--anim/--clip/--time` 摆姿势 |
| `art/soldier/soldier_zombie.geo.json` | 24 骨 / 61 块 |
| `art/soldier/soldier_zombie.animation.json` | 4 剪辑 / 55 条骨骼通道 |
| `art/soldier/soldier_{archer,sapper}.png` | 128×128 双层贴图 |

**量化验证记录**（不是"看着像"）：

* 拉弓：弦中点位移 **4.04u**（t=0.70 满弓），方向主要朝身体 +z，与弓轴近乎垂直（平行度 0.26）
  —— 即弦确实被拉成 V 形，而不是平移。
* 投掷：左手虎口世界坐标　身侧 (−5.4, 10.3, −0.6) → 引臂顶点 (0.9, **32.7**, +10.5)
  → 出手 (**z −20.4**, y 19.1) → 归位。是一次先上举后引、再前甩下压的标准过肩投。
* 弓在投掷出手瞬间仍在手上（`hand_r` 与 `bow` 把位同步移动）。
* geo 内置自检全过；动画铁律自检全过。

---

## 5. 接入点（改了哪些既有文件）

| 文件 | 改动 |
| --- | --- |
| `registry/ModEntities.java` | 注册 `soldier_zombie`（0.6×2.0，`clientTrackingRange` 12）+ 属性（HP 26 / 速度 0.24 / 伤害 4 / 护甲 3 / 视野 40） |
| `registry/ModItems.java` | 刷怪蛋 `soldier_zombie_spawn_egg` + 加入创造栏「刷怪蛋」页 |
| `client/ClientModBusEvents.java` | 注册 `SoldierGeoRenderer` |
| `horde/HordeManager.java` | 尸潮精英出场表 5 → **6**（等概率） |
| `registry/ModSpawns.java` | `registerElite(SOLDIER)` |
| `world/EliteSpawnBiomeModifier.java` | 群系刷怪权重表加入 SOLDIER |
| `lang/{zh_cn,en_us}.json` | 实体名「残兵」/ Remnant Soldier + 刷怪蛋名 |

---

## 6. 尚未在真实客户端验证的部分（诚实清单）

写了代码、编译通过、资源确认在 jar 内、动画做了数值判定，但**本机游戏进程当时正在运行，
没有重启实测**。需要在客户端里确认的：

1. 模型朝向与贴图是否正确（GeckoLib 的 x 镜像约定在本工程里是否与预览器一致）；
2. 三个控制器混合是否符合预期（拉弓时腿部仍在走、投掷时站定）；
3. 原版 `RangedBowAttackGoal` 是否真的拿主手那把弓开火（`isHoldingBow` 判定）；
4. TNT 抛物线的落点手感（`THROW_GRAVITY = 0.05` 是含阻力补偿的经验值）；
5. 尸潮与群系刷怪里新兵出现比例是否合适。

**快速验证**：`/summon apocalypse_zombies:soldier_zombie ~ ~ ~`，或创造栏「刷怪蛋」页取蛋；
站在 4~14 格外让它投弹，15 格外看它射箭。

---

## 7. 顺带发现（不在本次改动范围，供决策）

美女僵尸线的**整体位移量级偏小 16 倍**：该线动画里 `move` 骨的最大位移是
`y −1.5`（`skill_consort`）、`y +0.45`（`summon.crown`）。按本次定案的单位（1 = 1u = 1/16 格），
1.5u ≈ 9mm，在游戏里是看不见的 —— 也就是说那套技能动画的"全身下沉/腾起"实际没有生效，
视觉冲击全靠旋转通道撑着。已出货枪械线可以反证单位：莫辛枪机行程 2.9u、连发器供弹 14u
（若按"格"算是 14 格，荒谬）。

是否把这批位移按 u 重标（例如 `−1.5` → `−24`），需要单独一轮，且要逐条核对意图，
本轮不动。


---

## 附：生成约束落地（1.1.22）

用户四项要求：**可自然生成 / 不畏惧光 / 控制生成数量不要太多 / 有碰撞箱**。

| 要求 | 落地位置 | 关键证据 |
| --- | --- | --- |
| 可自然生成 | `ModSpawns.register(ModEntities.SOLDIER, ...)` + `EliteSpawnBiomeModifier` 加条目 | 缺 `SpawnPlacements` 登记时 biome modifier 的条目会被静默跳过（两者配套，缺一不可） |
| 不畏惧光 | `isSunSensitive()=false` **且** `isSunBurnTick()=false`（双保险） | 部署包方法表出现 `public boolean m_5884_()` / `protected boolean m_21527_()`；对照 `client_mappings.txt`（`isSunSensitive -> X_`、`isSunBurnTick -> fT`）与 `mcp_mappings.tsrg`（`X_ ()Z -> m_5884_`、`fT ()Z -> m_21527_`），实名逐条对上 |
| 控制数量 | ① 独立权重 `soldier_spawn_weight`（默认 2，其余精英共用 `elite_spawn_weight`=3）② 同伙上限 `soldier_max_nearby`（默认 2，半径 48 格，在刷怪判定里数）③ 尸潮里占 1/6 且受 `elite_horde_max_per_wave` 约束 ④ 群系条目 minCount=maxCount=1（永不成群刷） | `canSoldierSpawn` 命中；权重 2 对原版杂兵合计约 415 ⇒ 约每 210 次怪物刷新出 1 只 |
| 有碰撞箱 | `EntityType.Builder.sized(0.6F, 2.0F)` + `clientTrackingRange(12)` | 模型脚底 y=0、头顶 y=33.60u=2.100 格 ⇒ 顶部 0.1 格（≈6cm，只有头盔）露出碰撞箱，与既有新娘（33u/2.0）同一口径 |

新增 config（`config/apocalypse-zombies-common.toml` 的 `specials` 段）：
`soldier_spawn_weight`（0 = 退出自然生成，尸潮与刷怪蛋不受影响）、`soldier_max_nearby`。

**取舍说明**：碰撞箱高度取 2.0 而非贴齐模型的 2.1 —— 与既有精英同口径，且 2.1 会让它进不去两格高的门洞（原版僵尸 1.95 正是为此）。要贴齐改 `.sized(0.6F, 2.1F)` 一处即可，代价是过门洞要三格高。

**未在真实客户端验证**：自然生成的实测频率、同伙上限是否够"稀"、日光下确实不燃烧 —— 需要重启客户端后开新档案或 `/kill` 周边怪再观察；判定逻辑本身已编译进部署包（方法表已核）。
